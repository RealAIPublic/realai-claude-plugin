#!/usr/bin/env python3
"""structural_text_surgery.py — plan the resolution of STRUCTURAL prior-deal
leakage and the blockers that cannot be resolved automatically (v4.8).

Phase 2 clears *values*. This script covers the surfaces that hold no value and
so survive every clearing pass:

  * sheet tab names            'Modera Walsh DD Checklist'
  * banner / title cells        'MODERA WALSH - DEBT STRUCTURE'
  * label cells                 a prior lender's name under a `Lender` label
  * checklist rows              '☐ Market study on Walsh Ranch absorption'

and the one class of leak that must NOT be resolved automatically:

  * formula-baked deal amounts  '=C6/91327500'  — a live formula with the prior
                                deal's dollar figure welded into its body.

Blanking a title deletes the title; rewriting a formula changes the model's
logic. So this script does neither. It emits a PLAN:

    structural_redactions[]   text -> generic equivalent, per cell
    sheet_renames[]           tab  -> generic equivalent, with a safety verdict
    blockers[]                findings that need a user decision, with the
                              recommendation to put in front of them

The plan is reviewed, the reviewed items are merged into `decisions.json` under
`structural_redactions` / `sheet_renames`, and `prepare_clean_template_v2.py`
applies them with a `_PreparationAudit` row each. Nothing here writes to the
workbook.

A sheet rename is `dependency_safe` only when every reference to it can be
rewritten deterministically in the same pass — formulas, defined names,
validation and conditional-format formulas. Charts and pivot caches carry their
own copies of sheet-qualified references that the applier does not rewrite, so
their presence makes a rename unsafe and it becomes an ask_user blocker instead.

Usage:
    python skills/clean-a-template/scripts/structural_text_surgery.py model.xlsx \\
        --decisions-json decisions.json \\
        --leak-scan leak_scan.json \\
        --out structural_surgery_plan.json

`--decisions-json` supplies `deal_strings`. `--leak-scan` is optional; when
given, the plan reconciles against the scan's structural and formula-baked
findings so a surface the scan flagged cannot be silently absent from the plan.

Redacted like every other artifact in this bundle: prior-deal text appears in
the plan ONLY as the proposed `before`/`replacement` pair, which the reviewer
needs in order to approve the substitution. It never reaches the cleanliness
report or the chat transcript.
"""

from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from tp_common import (  # shared primitives; see tp_common.py
    hash_value,
    is_formula,
    is_normalization_scale,
)

import argparse
import json
import re
import zipfile
from typing import Any

import openpyxl

INTERNAL_SHEETS = {"_PreparationAudit"}

# Kept in step with post_clean_leak_scan.py — same surfaces, same vocabulary.
GENERIC_DEAL_TOKEN_STOPWORDS = {
    "the", "and", "at", "of", "on", "in", "a", "an", "llc", "lp", "llp", "inc",
    "ltd", "co", "company", "holdings", "partners", "capital", "group", "fund",
    "apartments", "apartment", "residences", "residence", "villas", "lofts",
    "towers", "tower", "place", "park", "plaza", "commons", "crossing", "pointe",
    "point", "ridge", "creek", "landing", "station", "square", "village",
    "gardens", "garden", "heights", "manor", "estates", "club", "house",
    "north", "south", "east", "west", "old", "new", "phase", "one", "two",
    "property", "properties", "portfolio", "project", "development", "deal",
    "acquisition", "proforma", "pro", "forma", "model", "template", "analysis",
    "street", "st", "avenue", "ave", "road", "rd", "drive", "dr", "boulevard",
    "blvd", "lane", "ln", "court", "ct", "way", "circle", "cir", "suite",
}
DEAL_TOKEN_MIN_LEN = 4

CHECKLIST_ROW_RE = re.compile(r"^\s*(?:[☐☑✓✔□■●○*\-•]|\[\s*[xX ]?\s*\])\s+\S")
BANNER_TITLE_RE = re.compile(r"^[A-Z0-9][A-Z0-9 \-&/(),.'’—–:|]{6,}$")
SEPARATORS = r"[\s]*[-–—:|,]+[\s]*"

CELL_REF_IN_FORMULA_RE = re.compile(r"(?<![A-Za-z0-9_$!])\$?[A-Z]{1,3}\$?\d{1,7}(?![A-Za-z0-9_(])")
NUM_LITERAL_RE = re.compile(r"(?<![A-Za-z0-9_])[-+]?\d{4,}(?:\.\d+)?(?![A-Za-z0-9_])")
EXCLUDE_FORMULA_LITERALS = {"1900", "1904", "9999", "1000", "10000", "100000", "1000000"}
FORMULA_BAKED_AMOUNT_MIN = 10_000

# The placeholder a redaction leaves behind when the deal name is load-bearing
# inside a sentence ("Market study on <X> absorption"). Neutral, obvious to the
# user, and greppable.
SUBJECT_PLACEHOLDER = "[subject]"


def deal_tokens(deal_strings: list[str]) -> list[str]:
    out: list[str] = []
    for s in deal_strings:
        for tok in re.split(r"[^A-Za-z0-9]+", str(s).lower()):
            if len(tok) < DEAL_TOKEN_MIN_LEN or tok in GENERIC_DEAL_TOKEN_STOPWORDS or tok.isdigit():
                continue
            if tok not in out:
                out.append(tok)
    return out


def structural_surface_kind(ws, cell) -> str | None:
    v = cell.value
    if not isinstance(v, str) or not v.strip():
        return None
    s = v.strip()
    if CHECKLIST_ROW_RE.match(s):
        return "checklist_row"
    if cell.row <= 3 and cell.column <= 3:
        return "banner_title"
    if BANNER_TITLE_RE.match(s):
        return "banner_title"
    right = ws.cell(cell.row, cell.column + 1).value
    if right not in (None, ""):
        return "label_cell"
    return None


def propose_redaction(text: str, deal_strings: list[str], tokens: list[str]) -> tuple[str | None, str]:
    """Return (replacement, strategy). replacement is None when no safe generic
    equivalent exists — the surface then becomes an ask_user blocker rather than
    a guess."""
    s = text

    # 1. Whole deal phrase plus an adjacent separator, anywhere in the string.
    #    'MODERA WALSH - DEBT STRUCTURE' -> 'DEBT STRUCTURE'
    for ds in sorted([d for d in deal_strings if d], key=len, reverse=True):
        pat = re.compile(rf"(?:^|{SEPARATORS})?{re.escape(ds)}(?:{SEPARATORS})?", re.I)
        if pat.search(s):
            candidate = pat.sub(" ", s, count=1)
            candidate = re.sub(r"\s{2,}", " ", candidate).strip(" -–—:|,")
            if candidate.strip():
                return candidate, "strip_deal_phrase_and_separator"
            return None, "would_blank_surface"

    # 2. A distinctive token plus the proper-noun run it belongs to, replaced by
    #    a neutral placeholder so the sentence still reads.
    #    '☐ Market study on Walsh Ranch absorption'
    #      -> '☐ Market study on [subject] absorption'
    #
    #    The run is expanded word by word rather than by one greedy regex: a
    #    case-insensitive `[A-Z]\w*` also matches ordinary lower-case words, so
    #    a single pattern swallows the whole sentence up to the token and leaves
    #    '☐ [subject]'. Expansion is therefore case-SENSITIVE (proper nouns
    #    only) while the token match itself is case-insensitive.
    words = list(re.finditer(r"[\w’'\-]+", s))
    for tok in tokens:
        hit = next((i for i, w in enumerate(words) if tok in w.group(0).lower()), None)
        if hit is None:
            continue
        first = last = hit
        while first - 1 >= 0 and words[first - 1].group(0)[:1].isupper():
            first -= 1
        while last + 1 < len(words) and words[last + 1].group(0)[:1].isupper():
            last += 1
        candidate = s[:words[first].start()] + SUBJECT_PLACEHOLDER + s[words[last].end():]
        candidate = re.sub(r"\s{2,}", " ", candidate).strip()
        stripped = candidate.replace(SUBJECT_PLACEHOLDER, "").strip(" -–—:|,☐☑✓✔□■●○*•[]")
        if stripped:
            return candidate, "replace_proper_noun_run_with_placeholder"
        return None, "would_blank_surface"

    return None, "no_match"


def propose_sheet_name(title: str, deal_strings: list[str], tokens: list[str],
                       existing: set[str]) -> tuple[str | None, str]:
    replacement, strategy = propose_redaction(title, deal_strings, tokens)
    if replacement is None:
        return None, strategy
    replacement = replacement.replace(SUBJECT_PLACEHOLDER, "").strip(" -–—:|,")
    replacement = re.sub(r"\s{2,}", " ", replacement)
    # Excel sheet-name constraints: 1-31 chars, no : \ / ? * [ ]
    replacement = re.sub(r"[:\\/?*\[\]]", "", replacement)[:31].strip()
    if not replacement:
        return None, "would_blank_surface"
    if replacement in existing and replacement != title:
        return None, "name_collision"
    return replacement, strategy


def sheet_rename_safety(workbook: str, sheet: str) -> tuple[bool, list[str]]:
    """A rename is safe only when every reference to the sheet is one the
    applier rewrites. Charts and pivot caches keep their own sheet-qualified
    refs and are not rewritten, so their presence blocks."""
    reasons: list[str] = []
    try:
        with zipfile.ZipFile(workbook) as zf:
            names = zf.namelist()
    except Exception as exc:
        return False, [f"package_unreadable: {exc}"]

    quoted = f"'{sheet}'!"
    bare = f"{sheet}!"
    for part in names:
        if part.startswith("xl/charts/") and part.endswith(".xml"):
            try:
                text = zf_read(workbook, part)
            except Exception:
                reasons.append(f"chart_part_unreadable:{part}")
                continue
            if quoted in text or bare in text:
                reasons.append(f"chart_references_sheet:{part}")
        elif part.startswith("xl/pivotCache/") or part.startswith("xl/pivotTables/"):
            reasons.append(f"pivot_present:{part}")
        elif part.startswith("xl/externalLinks/") or part == "xl/connections.xml":
            reasons.append(f"external_link_present:{part}")
    return (not reasons), reasons


def zf_read(workbook: str, part: str) -> str:
    with zipfile.ZipFile(workbook) as zf:
        return zf.read(part).decode("utf-8", "replace")


def scan_formula_baked_amounts(wb) -> list[dict]:
    """Formulas that carry references AND a large hardcoded amount. Never
    rewritten: extracting the constant into an input cell changes the model, so
    the user decides."""
    out: list[dict] = []
    for ws in wb.worksheets:
        if ws.title in INTERNAL_SHEETS:
            continue
        max_row = min(ws.max_row or 0, 8000)
        max_col = min(ws.max_column or 0, 250)
        for row in ws.iter_rows(min_row=1, max_row=max_row, min_col=1, max_col=max_col):
            for cell in row:
                v = cell.value
                if not is_formula(v):
                    continue
                if not CELL_REF_IN_FORMULA_RE.search(str(v)):
                    continue      # arithmetic-only: the disguised-constant rule owns it
                body = CELL_REF_IN_FORMULA_RE.sub("", str(v))
                baked = [n for n in NUM_LITERAL_RE.findall(body)
                         if n not in EXCLUDE_FORMULA_LITERALS
                         and abs(float(n)) >= FORMULA_BAKED_AMOUNT_MIN]
                if not baked:
                    continue
                # v4.9 — kept in step with post_clean_leak_scan.py. Range bounds
                # inside a clamp are a normalization scale; they are not a deal
                # amount and must not become a blocker the user has to resolve.
                scale_literals = [n for n in NUM_LITERAL_RE.findall(body)
                                  if n not in EXCLUDE_FORMULA_LITERALS]
                if is_normalization_scale(str(v), scale_literals):
                    continue
                out.append({
                    "cell": f"{ws.title}!{cell.coordinate}",
                    "finding": "formula_baked_deal_amount",
                    "formula_hash": hash_value(v),
                    "baked_literal_count": len(baked),
                    "baked_magnitudes": sorted({len(n.split('.')[0].lstrip('+-')) for n in baked}),
                    "sheet_state": ws.sheet_state,
                })
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("workbook")
    p.add_argument("--decisions-json", required=True,
                   help="decisions.json (or any JSON carrying deal_strings)")
    p.add_argument("--leak-scan",
                   help="Optional leak_scan.json; reconciles the plan against the scan's "
                        "structural and formula-baked findings")
    p.add_argument("--out", required=True)
    args = p.parse_args()

    decisions = json.loads(Path(args.decisions_json).read_text(encoding="utf-8"))
    deal_strings = [s for s in decisions.get("deal_strings", []) if s]
    if not deal_strings:
        print(json.dumps({
            "status": "no_deal_strings",
            "note": "decisions.json carries no deal_strings; structural surgery cannot "
                    "be planned without the approved deal-string list.",
        }, indent=2))
        return 2
    tokens = deal_tokens(deal_strings)

    wb = openpyxl.load_workbook(args.workbook, data_only=False, keep_links=False)
    existing = set(wb.sheetnames)

    redactions: list[dict] = []
    renames: list[dict] = []
    blockers: list[dict] = []

    # ── sheet tab names ──────────────────────────────────────────────────────
    for ws in wb.worksheets:
        if ws.title in INTERNAL_SHEETS:
            continue
        low = ws.title.lower()
        hit = (any(ds.lower() in low for ds in deal_strings)
               or any(t in low for t in tokens))
        if not hit:
            continue
        new_name, strategy = propose_sheet_name(ws.title, deal_strings, tokens, existing)
        safe, reasons = sheet_rename_safety(args.workbook, ws.title)
        if new_name is None:
            blockers.append({
                "location": f"sheet:{ws.title}",
                "finding": "sheet_name_carries_deal_name",
                "reason": strategy,
                "recommendation": "Give the sheet a generic name yourself — no safe generic "
                                  "equivalent could be derived from the current name.",
                "before": ws.title,
            })
            continue
        if not safe:
            blockers.append({
                "location": f"sheet:{ws.title}",
                "finding": "sheet_rename_not_dependency_safe",
                "reason": "; ".join(reasons),
                "recommendation": "Rename the tab in Excel (which updates chart and pivot "
                                  "references) and re-run, or approve leaving the name as-is.",
                "before": ws.title,
                "proposed": new_name,
            })
            continue
        existing.discard(ws.title)
        existing.add(new_name)
        renames.append({
            "sheet": ws.title,
            "new_name": new_name,
            "dependency_safe": True,
            "strategy": strategy,
            "rationale": "Sheet tab named after the prior deal; renamed to a generic "
                         "equivalent with all references rewritten in the same pass",
            "confidence": "high",
        })

    # ── structural text cells ────────────────────────────────────────────────
    for ws in wb.worksheets:
        if ws.title in INTERNAL_SHEETS:
            continue
        max_row = min(ws.max_row or 0, 8000)
        max_col = min(ws.max_column or 0, 250)
        for row in ws.iter_rows(min_row=1, max_row=max_row, min_col=1, max_col=max_col):
            for cell in row:
                v = cell.value
                if not isinstance(v, str) or is_formula(v) or not v.strip():
                    continue
                low = v.lower()
                if not (any(ds.lower() in low for ds in deal_strings)
                        or any(t in low for t in tokens)):
                    continue
                surface = structural_surface_kind(ws, cell)
                ref = f"{ws.title}!{cell.coordinate}"
                if surface is None:
                    # An ordinary VALUE cell holding the deal name. Not this
                    # script's job — the clearing pass owns it, and if it is
                    # still here after Phase 2 the leak scan blocks on it.
                    continue
                replacement, strategy = propose_redaction(v, deal_strings, tokens)
                if replacement is None:
                    blockers.append({
                        "location": ref,
                        "finding": "structural_text_carries_deal_name",
                        "structural_surface": surface,
                        "reason": strategy,
                        "recommendation": "Supply the replacement text — redacting the deal "
                                          "name here would leave the surface blank.",
                        "before": v[:160],
                    })
                    continue
                redactions.append({
                    "cell": ref,
                    "structural_surface": surface,
                    "before": v[:160],
                    "replacement": replacement[:160],
                    "strategy": strategy,
                    "runtime_source_class": "structural_text",
                    "rationale": f"Prior-deal name in a {surface}; replaced with a generic equivalent",
                    "confidence": "high" if strategy == "strip_deal_phrase_and_separator" else "medium",
                })

    # ── formula-baked deal amounts (never auto-resolved) ─────────────────────
    for f in scan_formula_baked_amounts(wb):
        blockers.append({
            "location": f["cell"],
            "finding": "formula_baked_deal_amount",
            "reason": "formula carries cell references AND a hardcoded amount "
                      f">= {FORMULA_BAKED_AMOUNT_MIN:,} in its body",
            "formula_hash": f["formula_hash"],
            "baked_literal_count": f["baked_literal_count"],
            "baked_magnitudes": f["baked_magnitudes"],
            "recommendation": "Extract the amount into an input cell and reference it, so the "
                              "next deal's number flows through — or approve it as a genuine "
                              "template constant if the figure is policy rather than deal data. "
                              "Not rewritten automatically: either choice changes the model.",
        })

    reconciliation: dict[str, Any] = {"status": "not_requested"}
    if args.leak_scan:
        try:
            scan = json.loads(Path(args.leak_scan).read_text(encoding="utf-8"))
        except Exception as exc:
            reconciliation = {"status": "unreadable", "error": str(exc)}
        else:
            planned = ({r["cell"] for r in redactions}
                       | {f"sheet:{r['sheet']}" for r in renames}
                       | {b["location"] for b in blockers})
            structural_codes = {
                "deal_string_in_sheet_name", "deal_token_in_sheet_name",
                "deal_token_in_structural_text", "formula_baked_deal_amount",
            }
            unaddressed = [
                {"location": f.get("cell") or f.get("location"), "finding": f.get("finding")}
                for f in scan.get("findings", [])
                if f.get("finding") in structural_codes
                and (f.get("cell") or f.get("location")) not in planned
            ]
            structural_deal_strings = [
                {"location": f.get("cell"), "finding": f.get("finding"),
                 "structural_surface": f.get("structural_surface")}
                for f in scan.get("findings", [])
                if f.get("finding") == "deal_string_retained" and f.get("structural_surface")
                and f.get("cell") not in planned
            ]
            reconciliation = {
                "status": "reconciled",
                "unaddressed_structural_findings": unaddressed + structural_deal_strings,
                "unaddressed_count": len(unaddressed) + len(structural_deal_strings),
                "note": "Every structural finding in the scan must appear in this plan as a "
                        "redaction, a rename, or a blocker. A non-empty list here means the "
                        "plan is incomplete — do not proceed to Phase 2 with it.",
            }

    result = {
        "workbook": str(args.workbook),
        "planner_version": 1,
        "deal_string_count": len(deal_strings),
        "deal_tokens": tokens,
        "structural_redactions": redactions,
        "sheet_renames": renames,
        "blockers": blockers,
        "counts": {
            "structural_redactions": len(redactions),
            "sheet_renames": len(renames),
            "blockers": len(blockers),
            "formula_baked_deal_amounts": sum(1 for b in blockers
                                              if b["finding"] == "formula_baked_deal_amount"),
        },
        "reconciliation": reconciliation,
        "readiness_note": (
            "Merge structural_redactions and sheet_renames into decisions.json under those "
            "same keys. Every blocker must be resolved with the user before the workbook can "
            "be delivered as `ready`; unresolved formula_baked_deal_amount blockers cap "
            "readiness at needs_review, because the template still computes off the prior "
            "deal's numbers."
        ),
    }
    Path(args.out).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"status": "ok", "out": args.out, **result["counts"],
                      "reconciliation": reconciliation.get("status"),
                      "unaddressed": reconciliation.get("unaddressed_count")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# END structural_text_surgery.py
