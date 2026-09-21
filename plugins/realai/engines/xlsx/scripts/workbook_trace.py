#!/usr/bin/env python3
"""
Formula dependency tracer for Excel models.

Usage:
    python skills/xlsx/scripts/workbook_trace.py <file.xlsx> --cell "Sheet1!B10"
    python skills/xlsx/scripts/workbook_trace.py <file.xlsx> --cell "Calc!B2:B13"
    python skills/xlsx/scripts/workbook_trace.py <file.xlsx> --orphans
    python skills/xlsx/scripts/workbook_trace.py <file.xlsx> --orphans --sheets "Inputs,Calc"

Purpose:
    recalc.py proves the formulas run; workbook_integrity_scan.py catches silent
    structural defects. Neither answers the two questions behind the hardest
    failure classes:

      "Does this total actually reference the cells it should?"  (wrong-but-
      plausible references: a SUM that swept B2:B9 when the data runs B2:B12, a
      formula pointing one column off, a metric reading a similar neighbor.)

      "Is this logic connected?"  (disconnected / orphaned logic: an input
      defined but referenced nowhere, a schedule that computes but feeds nothing.)

    --cell REF reports the precedents (what the target's formula references,
    ranges and named ranges resolved) and the dependents (every formula that
    references the target). Reading the resolved precedents against intent is how
    you catch a wrong-but-plausible range; a dependent count of zero on something
    that should feed downstream flags disconnected logic.

    --orphans reports unreferenced inputs (non-formula values no formula reads),
    unreferenced defined names, and terminal formulas (results nothing consumes).
    Terminal formulas are expected for true outputs; the list is a review prompt,
    not a defect list.

    The tracer is read-only. It resolves cell and range references including
    cross-sheet refs. Limitations: it does not expand references that route
    through a named range when computing dependents, and it does not see chart or
    data-validation references. Treat it as a strong aid to reading, not proof.
"""

import argparse
import json
import re
import sys
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter, column_index_from_string
from openpyxl.utils.cell import range_boundaries, coordinate_from_string

# A reference: optional sheet prefix, then a cell or a range. The leading
# lookbehind keeps us from matching the "G10" inside a name like "LOG10".
_SHEET = r"(?:'(?:[^']|'')+'|[A-Za-z_\\][\w.]*)"
_CELL = r"\$?[A-Za-z]{1,3}\$?\d+"
_REF_RE = re.compile(
    rf"(?<![A-Za-z0-9_])(?:({_SHEET})!)?({_CELL}(?::{_CELL})?)"
)


def _norm_sheet(token):
    if token is None:
        return None
    if token.startswith("'") and token.endswith("'"):
        return token[1:-1].replace("''", "'")
    return token


def _bounds_of(ref):
    """Return (min_col, min_row, max_col, max_row) for a cell or range ref."""
    ref = ref.replace("$", "")
    if ":" in ref:
        return range_boundaries(ref)
    col, row = coordinate_from_string(ref)
    c = column_index_from_string(col)
    return (c, row, c, row)


def _formula_text(v):
    """Formula source as a string, whatever shape openpyxl handed us.

    openpyxl returns an `ArrayFormula` object — not a string — for a CSE/spill
    formula's anchor cell. Reference parsing and every caller below treat a
    formula as text, so an unnormalized ArrayFormula raised
    `TypeError: expected string or bytes-like object, got 'ArrayFormula'` and
    aborted the trace. Any workbook using a spill formula was untraceable.
    """
    text = getattr(v, "text", None)
    if isinstance(text, str):
        return text
    return v if isinstance(v, str) else str(v)


def _is_formula_cell(cell, v):
    """True for an ordinary formula string, a formula cell by data_type, or an
    ArrayFormula object."""
    return (cell.data_type == "f"
            or (isinstance(v, str) and v.startswith("="))
            or getattr(v, "text", None) is not None)


def parse_refs(formula, default_sheet, sheet_names):
    """Yield (sheet, min_col, min_row, max_col, max_row, raw) for each reference."""
    refs = []
    formula = _formula_text(formula)
    for m in _REF_RE.finditer(formula):
        sheet_tok, body = m.group(1), m.group(2)
        sheet = _norm_sheet(sheet_tok) or default_sheet
        # Skip a sheet token that is not a real sheet (likely a false match).
        if sheet_tok is not None and sheet not in sheet_names:
            continue
        try:
            min_col, min_row, max_col, max_row = _bounds_of(body)
        except Exception:
            continue
        refs.append((sheet, min_col, min_row, max_col, max_row, (sheet_tok or "") + body))
    return refs


def _rect_intersects(a, b):
    """a, b are (sheet, min_col, min_row, max_col, max_row)."""
    if a[0] != b[0]:
        return False
    return not (a[3] < b[1] or b[3] < a[1] or a[4] < b[2] or b[4] < a[2])


def _collect_formulas(wb, sheet_filter):
    """Return list of (sheet, row, col, coord, formula)."""
    out = []
    for ws in wb.worksheets:
        if sheet_filter is not None and ws.title not in sheet_filter:
            continue
        for row in ws.iter_rows():
            for cell in row:
                v = cell.value
                if _is_formula_cell(cell, v):
                    out.append((ws.title, cell.row, cell.column, cell.coordinate, _formula_text(v)))
    return out


def _value_at(wb_values, sheet, row, col):
    try:
        return wb_values[sheet].cell(row=row, column=col).value
    except Exception:
        return None


def trace_cell(wb, wb_values, target, cap):
    sheet_names = set(wb.sheetnames)
    if "!" in target:
        sheet_tok, body = target.split("!", 1)
        sheet = _norm_sheet(sheet_tok)
    else:
        sheet, body = wb.sheetnames[0], target
    if sheet not in sheet_names:
        return {"status": "error", "error": f"Sheet not found: {sheet}. Available: {sorted(sheet_names)}"}
    try:
        t_min_col, t_min_row, t_max_col, t_max_row = _bounds_of(body)
    except Exception as exc:
        return {"status": "error", "error": f"Bad cell/range '{body}': {exc}"}
    target_rect = (sheet, t_min_col, t_min_row, t_max_col, t_max_row)

    ws = wb[sheet]
    precedents = []
    target_formulas = []
    seen_prec = set()
    for r in range(t_min_row, t_max_row + 1):
        for c in range(t_min_col, t_max_col + 1):
            cell = ws.cell(row=r, column=c)
            v = cell.value
            if _is_formula_cell(cell, v):
                v = _formula_text(v)
                target_formulas.append({"cell": cell.coordinate, "formula": v})
                for (psheet, pmin_c, pmin_r, pmax_c, pmax_r, raw) in parse_refs(v, sheet, sheet_names):
                    key = (psheet, pmin_c, pmin_r, pmax_c, pmax_r)
                    if key in seen_prec:
                        continue
                    seen_prec.add(key)
                    is_range = (pmin_c != pmax_c or pmin_r != pmax_r)
                    entry = {
                        "ref": f"{psheet}!{get_column_letter(pmin_c)}{pmin_r}"
                               + (f":{get_column_letter(pmax_c)}{pmax_r}" if is_range else ""),
                        "kind": "range" if is_range else "cell",
                        "cells": (pmax_c - pmin_c + 1) * (pmax_r - pmin_r + 1),
                    }
                    if not is_range:
                        entry["value"] = _value_at(wb_values, psheet, pmin_r, pmin_c)
                    else:
                        sample = []
                        for rr in range(pmin_r, min(pmax_r, pmin_r + 4) + 1):
                            for cc in range(pmin_c, min(pmax_c, pmin_c + 4) + 1):
                                sample.append(_value_at(wb_values, psheet, rr, cc))
                        entry["value_sample"] = sample[:8]
                    precedents.append(entry)

    # Dependents: any formula whose reference rectangle intersects the target.
    dependents = []
    truncated = False
    for (fsheet, frow, fcol, fcoord, formula) in _collect_formulas(wb, None):
        if fsheet == sheet and t_min_col <= fcol <= t_max_col and t_min_row <= frow <= t_max_row:
            continue  # don't list the target's own cells
        for ref in parse_refs(formula, fsheet, sheet_names):
            if _rect_intersects(ref[:5], target_rect):
                dependents.append({"sheet": fsheet, "cell": fcoord, "formula": formula})
                break
        if len(dependents) >= cap:
            truncated = True
            break

    return {
        "status": "ok",
        "mode": "cell",
        "target": f"{sheet}!{body}",
        "target_formulas": target_formulas,
        "precedents": precedents,
        "precedent_count": len(precedents),
        "dependents": dependents,
        "dependent_count": len(dependents),
        "dependents_truncated": truncated,
        "note": "Read precedents against intent to catch a wrong range or neighbor cell. "
                "Zero dependents on something that should feed downstream flags disconnected logic.",
    }


def trace_orphans(wb, wb_values, sheet_filter, cap):
    sheet_names = set(wb.sheetnames)
    all_formulas = _collect_formulas(wb, None)  # reference graph spans all sheets

    # Build the set of referenced rectangles and a flat text of all formulas.
    ref_rects = []
    all_text_parts = []
    for (fsheet, frow, fcol, fcoord, formula) in all_formulas:
        all_text_parts.append(formula)
        for ref in parse_refs(formula, fsheet, sheet_names):
            ref_rects.append(ref[:5])
    all_text = " ".join(all_text_parts)

    def is_referenced(sheet, row, col):
        cell_rect = (sheet, col, row, col, row)
        for rect in ref_rects:
            if _rect_intersects(cell_rect, rect):
                return True
        return False

    unreferenced_inputs = []
    terminal_formulas = []
    inputs_trunc = terminals_trunc = False
    for ws in wb.worksheets:
        if sheet_filter is not None and ws.title not in sheet_filter:
            continue
        for row in ws.iter_rows():
            for cell in row:
                v = cell.value
                if v is None:
                    continue
                is_formula = _is_formula_cell(cell, v)
                if is_formula:
                    if not is_referenced(ws.title, cell.row, cell.column) and len(terminal_formulas) < cap:
                        terminal_formulas.append({"sheet": ws.title, "cell": cell.coordinate, "formula": _formula_text(v)})
                    elif len(terminal_formulas) >= cap:
                        terminals_trunc = True
                elif isinstance(v, (int, float)) and not isinstance(v, bool):
                    if not is_referenced(ws.title, cell.row, cell.column) and len(unreferenced_inputs) < cap:
                        unreferenced_inputs.append({"sheet": ws.title, "cell": cell.coordinate, "value": v})
                    elif len(unreferenced_inputs) >= cap:
                        inputs_trunc = True

    unreferenced_names = []
    try:
        keys = list(wb.defined_names)
    except Exception:
        keys = []
    for key in keys:
        try:
            dn = wb.defined_names[key]
        except Exception:
            continue
        name = getattr(dn, "name", key)
        if not name or name.startswith("_xlnm"):
            continue
        if not re.search(r"(?<![A-Za-z0-9_])" + re.escape(name) + r"(?![A-Za-z0-9_])", all_text):
            unreferenced_names.append({"name": name, "value": getattr(dn, "value", None)})

    return {
        "status": "ok",
        "mode": "orphans",
        "unreferenced_inputs": unreferenced_inputs,
        "unreferenced_inputs_count": len(unreferenced_inputs),
        "unreferenced_inputs_truncated": inputs_trunc,
        "unreferenced_defined_names": unreferenced_names,
        "terminal_formulas": terminal_formulas,
        "terminal_formulas_count": len(terminal_formulas),
        "terminal_formulas_truncated": terminals_trunc,
        "note": "Unreferenced inputs and defined names are likely dead or disconnected logic. "
                "Terminal formulas are EXPECTED for true model outputs; review them, do not assume defects.",
    }


def main():
    parser = argparse.ArgumentParser(description="Formula dependency tracer for Excel models.")
    parser.add_argument("file")
    parser.add_argument("--cell", default=None, help='Target cell or range, e.g. "Calc!B10" or "Calc!B2:B13".')
    parser.add_argument("--orphans", action="store_true", help="Report unreferenced inputs, names, and terminal formulas.")
    parser.add_argument("--sheets", default=None, help="Comma-separated sheets to limit --orphans scope.")
    parser.add_argument("--json", dest="json_out", default=None)
    parser.add_argument("--max-results", type=int, default=200)
    args = parser.parse_args()

    if not args.cell and not args.orphans:
        print(json.dumps({"status": "error", "error": "Provide --cell REF or --orphans."}))
        sys.exit(1)

    path = Path(args.file).expanduser()
    if not path.exists():
        print(json.dumps({"status": "error", "error": f"File does not exist: {path}"}))
        sys.exit(1)
    if path.suffix.lower() not in (".xlsx", ".xlsm"):
        print(json.dumps({"status": "error", "error": f"Tracer supports .xlsx/.xlsm only, got {path.suffix}."}))
        sys.exit(1)

    sheet_filter = None
    if args.sheets:
        sheet_filter = {s.strip() for s in args.sheets.split(",") if s.strip()}

    try:
        wb = load_workbook(path, data_only=False)
        wb_values = load_workbook(path, data_only=True)
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}))
        sys.exit(1)

    if args.cell:
        result = trace_cell(wb, wb_values, args.cell, args.max_results)
    else:
        result = trace_orphans(wb, wb_values, sheet_filter, args.max_results)

    wb.close()
    wb_values.close()

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2, default=str)
    print(json.dumps(result, indent=2, default=str))
    sys.exit(0 if result.get("status") == "ok" else 1)


if __name__ == "__main__":
    main()
