#!/usr/bin/env python3
"""Build a lightweight dependency graph with range-aware candidate checks."""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import openpyxl
from openpyxl.utils.cell import column_index_from_string, coordinate_from_string

EXTERNAL_RE = re.compile(r"\[[^\]]+\.(?:xlsx|xlsm|xlsb|xls)\]", re.I)
CELL_REF_RE = re.compile(
    r"(?:(?:'(?P<qsheet>[^']+)'|(?P<sheet>[A-Za-z_][A-Za-z0-9_ .&-]*))!)?"
    r"(?P<start>\$?[A-Z]{1,3}\$?\d+)"
    r"(?::(?P<end>\$?[A-Z]{1,3}\$?\d+))?"
)


def strip_dollars(coord: str) -> str:
    return coord.replace("$", "")


def norm_cell(sheet: str, coord: str) -> str:
    return f"{sheet}!{strip_dollars(coord)}"


def parse_coord(coord: str) -> tuple[int, int]:
    col, row = coordinate_from_string(strip_dollars(coord))
    return int(row), int(column_index_from_string(col))


def parse_formula_refs(formula: str, current_sheet: str) -> tuple[list[str], list[dict], list[str]]:
    direct: list[str] = []
    ranges: list[dict] = []
    external = EXTERNAL_RE.findall(formula or "")
    for match in CELL_REF_RE.finditer(formula or ""):
        sheet = match.group("qsheet") or match.group("sheet") or current_sheet
        start = strip_dollars(match.group("start"))
        end = strip_dollars(match.group("end")) if match.group("end") else None
        # Avoid obvious false positives from structured references or function text.
        if not sheet:
            sheet = current_sheet
        if end:
            ranges.append({"sheet": sheet, "start": start, "end": end})
        else:
            direct.append(norm_cell(sheet, start))
    return sorted(set(direct)), ranges, sorted(set(external))


def cell_in_range(cell_ref: str, range_ref: dict) -> bool:
    if "!" not in cell_ref:
        return False
    sheet, coord = cell_ref.split("!", 1)
    if sheet != range_ref["sheet"]:
        return False
    row, col = parse_coord(coord)
    r1, c1 = parse_coord(range_ref["start"])
    r2, c2 = parse_coord(range_ref["end"])
    return min(r1, r2) <= row <= max(r1, r2) and min(c1, c2) <= col <= max(c1, c2)


def load_candidate_cells(path: str | None) -> list[str]:
    if not path:
        return []
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    cells = []
    for item in data.get("candidate_inputs", []):
        if item.get("cell"):
            cells.append(item["cell"])
    return cells


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_file")
    parser.add_argument("--surface-json", help="Optional extract_surface output for range membership checks")
    parser.add_argument("--out")
    args = parser.parse_args()

    wb = openpyxl.load_workbook(args.input_file, data_only=False, read_only=False, keep_links=True)
    precedents: dict[str, list[str]] = {}
    dependents: dict[str, list[str]] = defaultdict(list)
    formula_ranges: dict[str, list[dict]] = {}
    external_refs: dict[str, list[str]] = {}

    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if isinstance(cell.value, str) and cell.value.startswith("="):
                    fcell = norm_cell(ws.title, cell.coordinate)
                    direct, ranges, external = parse_formula_refs(cell.value, ws.title)
                    precedents[fcell] = direct
                    formula_ranges[fcell] = ranges
                    for dep in direct:
                        dependents[dep].append(fcell)
                    if external:
                        external_refs[fcell] = external

    candidate_membership = []
    candidates = load_candidate_cells(args.surface_json)
    if candidates:
        for cand in candidates:
            direct_count = len(dependents.get(cand, []))
            range_dependents = []
            for fcell, ranges in formula_ranges.items():
                if any(cell_in_range(cand, r) for r in ranges):
                    range_dependents.append(fcell)
            candidate_membership.append(
                {
                    "cell": cand,
                    "direct_dependent_count": direct_count,
                    "range_dependent_count": len(range_dependents),
                    "sample_dependents": sorted(set((dependents.get(cand, []) + range_dependents)))[:20],
                    "has_any_dependent": bool(direct_count or range_dependents),
                }
            )

    result = {
        "file": args.input_file,
        "formula_cell_count": len(precedents),
        "precedents": precedents,
        "dependents": {k: sorted(set(v)) for k, v in dependents.items()},
        "formula_ranges": formula_ranges,
        "external_refs": external_refs,
        "candidate_dependency_membership": candidate_membership,
        "range_handling": "ranges are preserved and candidates are tested for range membership; ranges are not globally expanded",
    }
    text = json.dumps(result, indent=2, default=str)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# END build_dependency_graph.py
