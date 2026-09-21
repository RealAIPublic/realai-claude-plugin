#!/usr/bin/env python3
"""
cross_check.py - mechanical verifications for cross-sectional analysis.

Bundled with the multi-entity-analysis skill. The domain analysis decides
what to pull and what a score means; this script makes the generic checks
mechanical instead of prose promises: superlative verification, coverage
audits, bucket-distribution sanity, and the standard z-composite. Every
check operates on the assembled records the caller passes in - the script
fetches nothing.

Usage:
    python cross_check.py --check <name> [options] --file records.json
    cat records.json | python cross_check.py --check <name> [options] -

Input: a JSON array of records (or {"records": [...]}), one object per
entity. The entity identifier field defaults to "entity" (--entity to
override).

Checks:
    coverage    per-field non-null counts across the set; names the
                entities missing each partially-covered field
    reliability sample-size / confidence floor: --field <sample-col>,
                --min N; lists entities below the floor (a value can be
                non-null and still too thin to score)
    extremum    verify a highest/lowest claim: --field, --direction max|min,
                optional --claim <entity>
    predicate   verify an "only X with ..." claim: --field, --op, --value,
                optional --claim <entity>
    buckets     label-distribution sanity: --field <label-col>, optional
                --expected "A,B,C"
    composite   standard z-sum composite normalized to mean 50 / std 10:
                --components a,b,c, optional --weights 0.5,0.3,-0.2
                (negative weight inverts a lower-is-better component)

Output: a single JSON object printed to stdout. Errors return
{"status": "error", ...} rather than a traceback.

Dependencies: standard library only
"""

import sys
import json
import math
import argparse
import statistics


def _is_null(v):
    # Datamart JSON frequently carries numerics as strings; empty and
    # null-ish strings are nulls, and numeric strings coerce downstream.
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return True
    if isinstance(v, str) and v.strip().lower() in ("", "null", "none", "n/a", "na"):
        return True
    return False


def _load_records(args):
    if args.file == "-":
        data = json.load(sys.stdin)
    else:
        with open(args.file) as f:
            data = json.load(f)
    if isinstance(data, dict):
        data = data.get("records")
    if not isinstance(data, list) or not data:
        raise ValueError("input must be a non-empty JSON array of records "
                         "(or an object with a 'records' array)")
    return data


def _entity(row, entity_field, idx):
    v = row.get(entity_field)
    return v if v is not None else f"<row {idx}>"


def check_coverage(records, entity_field):
    """Rule 5's coverage audit: a null silently distorts a mean, corrupts
    every z-score in the column, and can invalidate a superlative."""
    fields = sorted({k for r in records for k in r} - {entity_field})
    n = len(records)
    out, partial = {}, []
    for f in fields:
        missing = [_entity(r, entity_field, i) for i, r in enumerate(records)
                   if _is_null(r.get(f))]
        out[f] = {"non_null": n - len(missing), "of": n,
                  "missing_entities": missing}
        if missing and len(missing) < n:
            partial.append(f)
    return {
        "status": "ok",
        "check": "coverage",
        "entities": n,
        "fields": out,
        "partial_coverage_fields": partial,
        "note": ("partial-coverage fields must be restricted to the covered "
                 "subset, imputed explicitly, or dropped before scoring - "
                 "and the choice recorded" if partial
                 else "full coverage on every field"),
    }


def check_reliability(records, entity_field, field, minimum):
    """Coverage's sibling trap: a value can be present and still rest on a
    sample too thin to score. Given the sample-size/confidence column and a
    floor, list who clears it and who doesn't - the exclusion rule becomes
    an auditable artifact instead of ad-hoc filtering."""
    passing, excluded, nulls = [], [], []
    for i, r in enumerate(records):
        e = _entity(r, entity_field, i)
        v = r.get(field)
        if _is_null(v):
            nulls.append(e)
        elif float(v) < minimum:
            excluded.append({"entity": e, "value": float(v)})
        else:
            passing.append(e)
    return {
        "status": "ok",
        "check": "reliability",
        "field": field,
        "floor": minimum,
        "passing": passing,
        "excluded": excluded,
        "no_sample_field": nulls,
        "note": ("score only the passing set and state the exclusion rule "
                 "in the output" if excluded or nulls
                 else "all entities clear the floor"),
    }


def check_extremum(records, entity_field, field, direction, claim):
    """Verify a "highest/lowest X" claim against the actual column."""
    rows = [(_entity(r, entity_field, i), r.get(field))
            for i, r in enumerate(records)]
    valued = [(e, float(v)) for e, v in rows if not _is_null(v)]
    excluded = [e for e, v in rows if _is_null(v)]
    if not valued:
        return {"status": "error", "error": f"no non-null values in {field!r}"}
    best = max(v for _, v in valued) if direction == "max" else \
           min(v for _, v in valued)
    holders = [e for e, v in valued if v == best]
    result = {
        "status": "ok",
        "check": "extremum",
        "field": field,
        "direction": direction,
        "value": best,
        "holders": holders,
        "tied": len(holders) > 1,
        "nulls_excluded": excluded,
    }
    if claim is not None:
        result["claim"] = claim
        result["claim_holds"] = (holders == [claim])
        if not result["claim_holds"]:
            result["rewrite_hint"] = (
                f"claim fails: {direction} of {field!r} is held by "
                f"{holders}; weaken or drop the superlative")
    return result


_OPS = {
    "gt": lambda a, b: a > b, "ge": lambda a, b: a >= b,
    "lt": lambda a, b: a < b, "le": lambda a, b: a <= b,
    "eq": lambda a, b: a == b,
}


def check_predicate(records, entity_field, field, op, value, claim):
    """Verify an "only X with <condition>" claim: list every qualifier."""
    fn = _OPS[op]
    qualifying, excluded = [], []
    for i, r in enumerate(records):
        v = r.get(field)
        e = _entity(r, entity_field, i)
        if _is_null(v):
            excluded.append(e)
        elif fn(float(v), value):
            qualifying.append({"entity": e, "value": v})
    result = {
        "status": "ok",
        "check": "predicate",
        "condition": f"{field} {op} {value}",
        "qualifying": qualifying,
        "count": len(qualifying),
        "nulls_excluded": excluded,
        "only_claim_safe": len(qualifying) == 1 and (
            claim is None or (qualifying and qualifying[0]["entity"] == claim)),
    }
    if not result["only_claim_safe"] and claim is not None:
        result["rewrite_hint"] = (
            f"'only' claim fails: {len(qualifying)} entities qualify; "
            f"rewrite as 'one of {len(qualifying)}' or drop")
    return result


def check_buckets(records, entity_field, field, expected):
    """Rule 3's distribution sanity: an empty bucket means miscalibrated
    thresholds; a single occupied bucket means the label earns nothing."""
    counts = {}
    nulls = []
    for i, r in enumerate(records):
        v = r.get(field)
        if _is_null(v):
            nulls.append(_entity(r, entity_field, i))
        else:
            counts[str(v)] = counts.get(str(v), 0) + 1
    flags = []
    if expected:
        empty = [lbl for lbl in expected if lbl not in counts]
        if empty:
            flags.append(f"empty bucket(s) {empty}: thresholds are "
                         "miscalibrated")
        unexpected = [lbl for lbl in counts if lbl not in expected]
        if unexpected:
            flags.append(f"unexpected label(s) {unexpected}: not in the "
                         "declared vocabulary")
    if len(counts) == 1 and len(records) > 1:
        flags.append("all entities share one bucket: the categorical is not "
                     "earning its keep - tighten thresholds or drop the label")
    return {"status": "ok", "check": "buckets", "field": field,
            "counts": counts, "unlabeled": nulls, "flags": flags}


def check_composite(records, entity_field, components, weights):
    """The standard composite: per-component z-scores, weighted sum,
    normalized to mean 50 / std 10. Refuses nulls (Rule 5) and zero-variance
    components rather than silently distorting the score."""
    if weights is None:
        weights = [1.0] * len(components)
    if len(weights) != len(components):
        return {"status": "error",
                "error": f"{len(weights)} weights for {len(components)} components"}
    offenders = {}
    for c in components:
        missing = [_entity(r, entity_field, i) for i, r in enumerate(records)
                   if _is_null(r.get(c))]
        if missing:
            offenders[c] = missing
    if offenders:
        return {"status": "error",
                "error": "null components: restrict to the covered subset, "
                         "impute explicitly, or drop the component first "
                         "(run --check coverage)",
                "offenders": offenders}
    if len(records) < 2:
        return {"status": "error", "error": "composite needs 2+ entities"}

    zcols = {}
    for c in components:
        vals = [float(r[c]) for r in records]
        mean, std = statistics.mean(vals), statistics.stdev(vals)
        if std == 0:
            return {"status": "error",
                    "error": f"zero variance in component {c!r}: it cannot "
                             "differentiate entities - drop it"}
        zcols[c] = [(v - mean) / std for v in vals]

    raw = [sum(w * zcols[c][i] for c, w in zip(components, weights))
           for i in range(len(records))]
    rmean = statistics.mean(raw)
    rstd = statistics.stdev(raw)
    scores = [50.0 if rstd == 0 else 50 + (x - rmean) / rstd * 10 for x in raw]

    ranked = sorted(
        ({"entity": _entity(r, entity_field, i),
          "score": round(scores[i], 1),
          # per-component contribution, so a winner that lost the lead
          # component is explainable (never publish only the total)
          "contributions": {c: round(w * zcols[c][i], 3)
                           for c, w in zip(components, weights)}}
         for i, r in enumerate(records)),
        key=lambda x: x["score"], reverse=True)
    return {"status": "ok", "check": "composite", "components": components,
            "weights": weights, "normalization": "z-sum to mean 50 / std 10",
            "ranked": ranked}


def main(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--check", required=True,
                   choices=["coverage", "reliability", "extremum", "predicate",
                            "buckets", "composite"])
    p.add_argument("--entity", default="entity")
    p.add_argument("--field")
    p.add_argument("--min", type=float, dest="minimum")
    p.add_argument("--direction", choices=["max", "min"])
    p.add_argument("--op", choices=sorted(_OPS))
    p.add_argument("--value", type=float)
    p.add_argument("--claim")
    p.add_argument("--expected")
    p.add_argument("--components")
    p.add_argument("--weights")
    p.add_argument("file", nargs="?", default="-")
    args = p.parse_args(argv)

    records = _load_records(args)
    if args.check == "coverage":
        return check_coverage(records, args.entity)
    if args.check == "reliability":
        if not args.field or args.minimum is None:
            return {"status": "error",
                    "error": "reliability needs --field and --min"}
        return check_reliability(records, args.entity, args.field,
                                 args.minimum)
    if args.check == "extremum":
        if not args.field or not args.direction:
            return {"status": "error",
                    "error": "extremum needs --field and --direction"}
        return check_extremum(records, args.entity, args.field,
                              args.direction, args.claim)
    if args.check == "predicate":
        if not args.field or not args.op or args.value is None:
            return {"status": "error",
                    "error": "predicate needs --field, --op, and --value"}
        return check_predicate(records, args.entity, args.field, args.op,
                               args.value, args.claim)
    if args.check == "buckets":
        if not args.field:
            return {"status": "error", "error": "buckets needs --field"}
        expected = [s.strip() for s in args.expected.split(",")] \
            if args.expected else None
        return check_buckets(records, args.entity, args.field, expected)
    if args.check == "composite":
        if not args.components:
            return {"status": "error", "error": "composite needs --components"}
        components = [s.strip() for s in args.components.split(",")]
        weights = [float(s) for s in args.weights.split(",")] \
            if args.weights else None
        return check_composite(records, args.entity, components, weights)


if __name__ == "__main__":
    try:
        result = main(sys.argv[1:])
    except Exception as e:
        result = {"status": "error", "error": str(e)}
    print(json.dumps(result, indent=2))
