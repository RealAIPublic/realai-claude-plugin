#!/usr/bin/env python3
"""
Validate claims.json structure, provenance completeness, and expression refs.

Usage:
    python skills/xlsx/scripts/workbook_claims_schema_check.py output/claims.json

Expected top-level keys:
    values   - object of {name: value} available to expressions
    facts    - array of {id, label, value, source_sheet, source_range, extraction_method}
    claims   - array of {id, name, expr, expected, tolerance?, based_on_facts[], derivation}

Every claim.expr is parsed and its referenced names are verified against
`values`. Unknown variable references are hard errors.

`tolerance` is treated as an ABSOLUTE tolerance downstream.
"""

import ast
import json
import sys
from pathlib import Path


# Names safe to reference in expressions besides values keys.
EXPR_BUILTIN_NAMES = {"abs", "min", "max", "round", "True", "False", "None"}


def is_nonempty_string(v):
    return isinstance(v, str) and v.strip() != ""


def collect_expr_names(expr):
    """Return (names, syntax_error). names is a set of ast.Name ids."""
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        return set(), f"invalid syntax: {exc.msg}"
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
    return names, None


def verify_expr_refs(label, expr, value_keys, errors):
    names, syntax_err = collect_expr_names(expr)
    if syntax_err:
        errors.append(f"{label}: {syntax_err}")
        return
    unknown = [n for n in sorted(names) if n not in value_keys and n not in EXPR_BUILTIN_NAMES]
    for n in unknown:
        errors.append(f"{label} references variable '{n}' which is not in 'values'")


def validate_fact(index, fact):
    errors = []
    warnings = []
    if not isinstance(fact, dict):
        return [f"facts[{index}] must be an object"], warnings

    if not is_nonempty_string(fact.get("id")):
        errors.append(f"facts[{index}].id is required and must be a non-empty string")
    if not is_nonempty_string(fact.get("label")):
        errors.append(f"facts[{index}].label is required and must be a non-empty string")
    if "value" not in fact:
        errors.append(f"facts[{index}].value is required")

    if not is_nonempty_string(fact.get("source_sheet")):
        errors.append(f"facts[{index}].source_sheet is required")
    if not is_nonempty_string(fact.get("source_range")):
        errors.append(f"facts[{index}].source_range is required")
    if not is_nonempty_string(fact.get("extraction_method")):
        errors.append(f"facts[{index}].extraction_method is required")

    note = fact.get("note")
    if note is not None and not isinstance(note, str):
        errors.append(f"facts[{index}].note must be a string when present")

    return errors, warnings


def validate_claim(index, claim, fact_ids, value_keys):
    errors = []
    warnings = []
    if not isinstance(claim, dict):
        return [f"claims[{index}] must be an object"], warnings

    if not is_nonempty_string(claim.get("id")):
        errors.append(f"claims[{index}].id is required and must be a non-empty string")
    if not is_nonempty_string(claim.get("name")):
        errors.append(f"claims[{index}].name is required and must be a non-empty string")
    if not is_nonempty_string(claim.get("expr")):
        errors.append(f"claims[{index}].expr is required and must be a non-empty string")
    if "expected" not in claim:
        errors.append(f"claims[{index}].expected is required")

    based_on = claim.get("based_on_facts")
    if not isinstance(based_on, list) or len(based_on) == 0:
        errors.append(f"claims[{index}].based_on_facts must be a non-empty array")
    else:
        for j, fid in enumerate(based_on):
            if not is_nonempty_string(fid):
                errors.append(
                    f"claims[{index}].based_on_facts[{j}] must be a non-empty string"
                )
            elif fid not in fact_ids:
                warnings.append(
                    f"claims[{index}].based_on_facts[{j}] references unknown fact id '{fid}'"
                )

    if not is_nonempty_string(claim.get("derivation")):
        errors.append(f"claims[{index}].derivation is required (human-readable calc path)")

    tolerance = claim.get("tolerance")
    if tolerance is not None and not isinstance(tolerance, (int, float)):
        errors.append(f"claims[{index}].tolerance must be numeric when present")

    expr = claim.get("expr")
    if is_nonempty_string(expr):
        verify_expr_refs(f"claims[{index}].expr", expr, value_keys, errors)

    return errors, warnings


def run_validation(payload):
    errors = []
    warnings = []

    if not isinstance(payload, dict):
        return {
            "status": "error",
            "errors": ["claims payload must be a JSON object"],
            "warnings": [],
        }

    values = payload.get("values")
    facts = payload.get("facts")
    claims = payload.get("claims")

    if not isinstance(values, dict):
        errors.append("'values' must be an object")
        values = {}
    if not isinstance(facts, list):
        errors.append("'facts' must be an array")
        facts = []
    if not isinstance(claims, list):
        errors.append("'claims' must be an array")
        claims = []

    value_keys = set(values.keys())

    fact_ids = set()
    for i, fact in enumerate(facts):
        e, w = validate_fact(i, fact)
        errors.extend(e)
        warnings.extend(w)
        if isinstance(fact, dict) and is_nonempty_string(fact.get("id")):
            if fact["id"] in fact_ids:
                errors.append(f"Duplicate fact id: {fact['id']}")
            fact_ids.add(fact["id"])

    claim_ids = set()
    for i, claim in enumerate(claims):
        e, w = validate_claim(i, claim, fact_ids, value_keys)
        errors.extend(e)
        warnings.extend(w)
        if isinstance(claim, dict):
            cid = claim.get("id")
            if is_nonempty_string(cid):
                if cid in claim_ids:
                    errors.append(f"Duplicate claim id: {cid}")
                claim_ids.add(cid)

    effective_checks = [
        c for c in claims
        if isinstance(c, dict) and "expected" in c and is_nonempty_string(c.get("expr"))
    ]

    seen_check_names = set()
    for i, check in enumerate(effective_checks):
        if isinstance(check, dict):
            nm = check.get("name")
            if is_nonempty_string(nm):
                if nm in seen_check_names:
                    errors.append(f"Duplicate check name: {nm}")
                seen_check_names.add(nm)

    return {
        "status": "success" if len(errors) == 0 else "error",
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "summary": {
            "values_keys": len(values),
            "facts": len(facts),
            "claims": len(claims),
            "checks": len(effective_checks),
        },
    }


def main():
    if len(sys.argv) != 2:
        print("Usage: python skills/xlsx/scripts/workbook_claims_schema_check.py <claims.json>")
        sys.exit(1)

    claims_path = Path(sys.argv[1]).expanduser()
    if not claims_path.exists():
        print(json.dumps({"status": "error", "errors": [f"File does not exist: {claims_path}"]}))
        sys.exit(1)

    try:
        payload = json.loads(claims_path.read_text(encoding="utf-8"))
        result = run_validation(payload)
        print(json.dumps(result, indent=2))
        if result["status"] == "error":
            sys.exit(1)
    except Exception as exc:
        print(json.dumps({"status": "error", "errors": [str(exc)]}))
        sys.exit(1)


if __name__ == "__main__":
    main()
