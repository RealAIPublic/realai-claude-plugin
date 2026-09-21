#!/usr/bin/env python3
"""Build a conservative sheet-level dependency trace for workbook cleanup.

This script is intentionally sheet-level, not a full Excel calc graph. It traces
formulas, defined names, data validation formulas, conditional formatting
formulas where accessible, and chart references where openpyxl exposes them.

Deletion candidates are only suggestions. The LLM/user must approve deletion.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

import openpyxl

SHEET_REF_RE = re.compile(r"(?:'([^']+)'|([A-Za-z0-9_ .&()\-]+))!\$?[A-Z]{1,3}\$?\d+(?::\$?[A-Z]{1,3}\$?\d+)?")


def clean_sheet_name(name: str | None) -> str | None:
    if not name:
        return None
    return name.strip().strip("'")


def refs_from_formula(text: Any, sheetnames: set[str]) -> set[str]:
    refs = set()
    if not isinstance(text, str):
        return refs
    for m in SHEET_REF_RE.finditer(text):
        s = clean_sheet_name(m.group(1) or m.group(2))
        if s in sheetnames:
            refs.add(s)
    return refs


def defined_name_items(wb) -> list[tuple[str, Any]]:
    dn = wb.defined_names
    try:
        return list(dn.items())
    except Exception:
        pass
    try:
        return [(d.name, d) for d in dn.definedName]
    except Exception:
        return []


def attr_text(obj: Any) -> str:
    for attr in ["attr_text", "value", "text"]:
        try:
            v = getattr(obj, attr)
            if v:
                return str(v)
        except Exception:
            pass
    return str(obj or "")


def transitive_closure(start: set[str], deps: dict[str, set[str]]) -> set[str]:
    seen = set(start)
    q = deque(start)
    while q:
        cur = q.popleft()
        for nxt in deps.get(cur, set()):
            if nxt not in seen:
                seen.add(nxt)
                q.append(nxt)
    return seen


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workbook")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    wb = openpyxl.load_workbook(args.workbook, data_only=False, keep_links=False)
    sheetnames = set(wb.sheetnames)
    deps: dict[str, set[str]] = defaultdict(set)
    evidence: list[dict[str, Any]] = []

    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                val = cell.value
                if isinstance(val, str) and val.startswith("="):
                    refs = refs_from_formula(val, sheetnames)
                    for ref in refs:
                        deps[ws.title].add(ref)
                        evidence.append({"from_sheet": ws.title, "to_sheet": ref, "type": "formula", "cell": cell.coordinate})

        try:
            for dv in ws.data_validations.dataValidation:
                for f in [getattr(dv, "formula1", None), getattr(dv, "formula2", None)]:
                    for ref in refs_from_formula(f, sheetnames):
                        deps[ws.title].add(ref)
                        evidence.append({"from_sheet": ws.title, "to_sheet": ref, "type": "data_validation"})
        except Exception:
            pass

        try:
            for cf_rules in ws.conditional_formatting._cf_rules.values():
                for rule in cf_rules:
                    for f in getattr(rule, "formula", []) or []:
                        for ref in refs_from_formula(f, sheetnames):
                            deps[ws.title].add(ref)
                            evidence.append({"from_sheet": ws.title, "to_sheet": ref, "type": "conditional_format"})
        except Exception:
            pass

        try:
            for chart in getattr(ws, "_charts", []) or []:
                txt = repr(chart)
                for ref in refs_from_formula(txt, sheetnames):
                    deps[ws.title].add(ref)
                    evidence.append({"from_sheet": ws.title, "to_sheet": ref, "type": "chart_repr"})
        except Exception:
            pass

    for name, defn in defined_name_items(wb):
        text = attr_text(defn)
        for ref in refs_from_formula(text, sheetnames):
            # Defined names are global; conservatively mark all visible sheets as possibly depending on them.
            for ws in wb.worksheets:
                if ws.sheet_state == "visible":
                    deps[ws.title].add(ref)
            evidence.append({"defined_name": name, "to_sheet": ref, "type": "defined_name"})

    visible = {ws.title for ws in wb.worksheets if ws.sheet_state == "visible"}
    hidden = {ws.title for ws in wb.worksheets if ws.sheet_state != "visible"}
    support_closure = transitive_closure(visible, deps)
    deletion_candidates = sorted(hidden - support_closure)
    retained_hidden_support = sorted(hidden & support_closure)

    result = {
        "workbook": str(args.workbook),
        "visible_sheets": sorted(visible),
        "hidden_sheets": sorted(hidden),
        "sheet_dependencies": {k: sorted(v) for k, v in deps.items()},
        "visible_sheet_support_closure": sorted(support_closure),
        "retained_hidden_support_sheets": retained_hidden_support,
        "hidden_sheet_deletion_candidates": deletion_candidates,
        "evidence": evidence[:10000],
        "deletion_policy_note": "Deletion candidates require LLM/user approval and should be deleted only if no unsupported references remain.",
    }
    Path(args.out).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"status": "ok", "out": args.out, "hidden_candidates": len(deletion_candidates)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# END dependency_trace_report.py
