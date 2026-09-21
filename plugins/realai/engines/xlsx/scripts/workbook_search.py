#!/usr/bin/env python3
"""
Regex search across a workbook's cells.

Usage:
    python skills/xlsx/scripts/workbook_search.py <file> --pattern "fee"
        [--in values|formulas|both]   default both (xlsx/xlsm only)
        [--sheets "Sheet1,Sheet2"]    filter (xlsx/xlsm only)
        [--limit N]                   default 200 (safety cap)
        [--case-sensitive]            default case-insensitive

Returns JSON with cell-level matches. Each match records sheet + coord, plus
the value and formula (if any). `matched_in` lists which view(s) hit the
pattern so an agent can tell whether a match was on a computed value or
a formula string.
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path

from openpyxl import load_workbook


def _search_pass(path, data_only, match_key, sheet_filter, regex, match_map, limit):
    wb = load_workbook(path, read_only=True, data_only=data_only)
    truncated = False
    for ws in wb.worksheets:
        if sheet_filter and ws.title not in sheet_filter:
            continue
        for row in ws.iter_rows(values_only=False):
            for cell in row:
                v = cell.value
                if v is None:
                    continue
                if match_key == "formula":
                    if not (isinstance(v, str) and v.startswith("=")):
                        continue
                try:
                    if not regex.search(str(v)):
                        continue
                except Exception:
                    continue
                key = (ws.title, cell.coordinate)
                entry = match_map.get(key)
                if entry is None:
                    entry = {
                        "sheet": ws.title,
                        "coord": cell.coordinate,
                        "value": None,
                        "formula": None,
                        "matched_in": [],
                    }
                    match_map[key] = entry
                entry[match_key] = v
                label = "value" if match_key == "value" else "formula"
                if label not in entry["matched_in"]:
                    entry["matched_in"].append(label)
                if len(match_map) >= limit:
                    truncated = True
                    break
            if truncated:
                break
        if truncated:
            break
    wb.close()
    return truncated


def search_workbook(path, pattern, scope, sheet_filter, limit, case_sensitive):
    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        regex = re.compile(pattern, flags)
    except re.error as exc:
        raise ValueError(f"Invalid regex: {exc}")

    match_map = {}
    truncated = False

    if scope in ("values", "both"):
        truncated = _search_pass(path, True, "value", sheet_filter, regex, match_map, limit)
    if not truncated and scope in ("formulas", "both"):
        truncated = _search_pass(path, False, "formula", sheet_filter, regex, match_map, limit)

    # Also capture the computed value for cells that matched on formula, for
    # agent context. Only run if we have formula-only matches and limit budget.
    if scope == "formulas":
        missing_values = [k for k, v in match_map.items() if v.get("value") is None]
        if missing_values:
            wb = load_workbook(path, read_only=True, data_only=True)
            want = set(missing_values)
            for ws in wb.worksheets:
                for key in list(want):
                    sheet, coord = key
                    if sheet != ws.title:
                        continue
                    try:
                        match_map[key]["value"] = ws[coord].value
                    except Exception:
                        pass
                    want.discard(key)
                if not want:
                    break
            wb.close()

    return sorted(match_map.values(), key=lambda m: (m["sheet"], m["coord"])), truncated


def search_delimited(path, delimiter, pattern, limit, case_sensitive):
    flags = 0 if case_sensitive else re.IGNORECASE
    regex = re.compile(pattern, flags)

    matches = []
    truncated = False

    with open(path, "r", encoding="utf-8", errors="replace", newline="") as fh:
        reader = csv.reader(fh, delimiter=delimiter)
        for i, row in enumerate(reader, start=1):
            for j, cell in enumerate(row, start=1):
                if regex.search(cell):
                    matches.append({
                        "sheet": path.name,
                        "coord": f"r{i}c{j}",
                        "row": i,
                        "col": j,
                        "value": cell,
                        "formula": None,
                        "matched_in": ["value"],
                    })
                    if len(matches) >= limit:
                        truncated = True
                        break
            if truncated:
                break
    return matches, truncated


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("file")
    parser.add_argument("--pattern", required=True, help="Regex (Python re syntax)")
    parser.add_argument(
        "--in",
        dest="scope",
        choices=["values", "formulas", "both"],
        default="both",
        help="xlsx/xlsm only; delimited files always search values",
    )
    parser.add_argument("--sheets", help="Comma-separated sheet names to include (xlsx/xlsm)")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--case-sensitive", action="store_true")
    args = parser.parse_args()

    path = Path(args.file).expanduser()
    if not path.exists():
        print(json.dumps({"status": "error", "error": f"File does not exist: {path}"}))
        sys.exit(1)

    suffix = path.suffix.lower()
    if suffix == ".xls":
        print(json.dumps({
            "status": "error",
            "error": ".xls is not supported by openpyxl. Convert to .xlsx first."
        }))
        sys.exit(1)

    sheet_filter = None
    if args.sheets:
        sheet_filter = {s.strip() for s in args.sheets.split(",") if s.strip()}

    try:
        if suffix in (".xlsx", ".xlsm"):
            matches, truncated = search_workbook(
                path, args.pattern, args.scope, sheet_filter, args.limit, args.case_sensitive
            )
            scope = args.scope
        elif suffix == ".csv":
            matches, truncated = search_delimited(
                path, ",", args.pattern, args.limit, args.case_sensitive
            )
            scope = "values"
        elif suffix == ".tsv":
            matches, truncated = search_delimited(
                path, "\t", args.pattern, args.limit, args.case_sensitive
            )
            scope = "values"
        else:
            print(json.dumps({
                "status": "error",
                "error": f"Unsupported file type: {suffix}",
            }))
            sys.exit(1)

        result = {
            "status": "success",
            "source_file": str(path),
            "pattern": args.pattern,
            "scope": scope,
            "case_sensitive": args.case_sensitive,
            "limit": args.limit,
            "truncated": truncated,
            "total_matches": len(matches),
            "matches": matches,
        }
        print(json.dumps(result, indent=2, default=str))
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
