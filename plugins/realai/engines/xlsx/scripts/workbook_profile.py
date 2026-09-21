#!/usr/bin/env python3
"""
Workbook profiler for large-file triage.

Usage:
    python skills/xlsx/scripts/workbook_profile.py <file>

Supports:
    - .xlsx, .xlsm (openpyxl)
    - .csv, .tsv (csv module)

Returns JSON with:
    - File size + size tier (small | medium | large | very_large)
    - Per-sheet dimensions, formula counts, merged cell count, Excel tables
    - Workbook-level defined names
    - Recommended next actions

Files >= 100MB short-circuit: they return "very_large" without a cell walk.
Use workbook_sample.py for actual inspection of huge files.
"""

import csv
import json
import sys
from pathlib import Path

from openpyxl import load_workbook


LARGE_FILE_SHORT_CIRCUIT_MB = 100


def classify_size(file_size_bytes, estimated_cells, sheet_count, total_formula_cells):
    size_mb = file_size_bytes / (1024 * 1024)
    # Strictest rules first so "very_large" is reachable via complexity.
    if (
        (sheet_count >= 20 and total_formula_cells >= 100_000)
        or size_mb >= 100
        or estimated_cells >= 10_000_000
    ):
        return "very_large"
    if (
        (sheet_count >= 12 and total_formula_cells >= 50_000)
        or size_mb >= 25
        or estimated_cells >= 2_000_000
    ):
        return "large"
    if size_mb >= 8 or estimated_cells >= 500_000:
        return "medium"
    return "small"


def collect_defined_names(wb):
    names = []
    try:
        for name_key in wb.defined_names:
            dn = wb.defined_names[name_key]
            destinations = []
            try:
                for dest_sheet, dest_coord in dn.destinations:
                    destinations.append({"sheet": dest_sheet, "coord": dest_coord})
            except Exception:
                pass
            names.append({
                "name": getattr(dn, "name", name_key),
                "value": getattr(dn, "value", None),
                "destinations": destinations,
            })
    except Exception:
        pass
    return names


def collect_sheet_structure(ws):
    merged_cell_count = 0
    try:
        merged_cell_count = len(ws.merged_cells.ranges)
    except Exception:
        pass

    tables = []
    try:
        for table in ws.tables.values():
            tables.append({
                "name": getattr(table, "name", None),
                "display_name": getattr(table, "displayName", None),
                "ref": getattr(table, "ref", None),
            })
    except Exception:
        pass

    return merged_cell_count, tables


def profile_workbook(path):
    # Non-read-only load so tables + merged_cells are populated.
    # values_only=True in iter_rows keeps memory bounded.
    wb = load_workbook(path, data_only=False)
    sheets = []
    total_estimated_cells = 0
    total_formula_cells = 0

    for ws in wb.worksheets:
        max_row = ws.max_row or 0
        max_col = ws.max_column or 0
        estimated_cells = max_row * max_col
        total_estimated_cells += estimated_cells

        formula_cells = 0
        non_empty_rows = 0

        for row in ws.iter_rows(values_only=True):
            row_has_value = False
            for value in row:
                if value is not None:
                    row_has_value = True
                    if isinstance(value, str) and value.startswith("="):
                        formula_cells += 1
            if row_has_value:
                non_empty_rows += 1

        total_formula_cells += formula_cells
        merged_cell_count, tables = collect_sheet_structure(ws)

        sheets.append({
            "sheet_name": ws.title,
            "max_row": max_row,
            "max_col": max_col,
            "estimated_cells": estimated_cells,
            "non_empty_rows": non_empty_rows,
            "formula_cells": formula_cells,
            "merged_cell_count": merged_cell_count,
            "tables": tables,
        })

    defined_names = collect_defined_names(wb)
    wb.close()

    return {
        "sheet_count": len(sheets),
        "sheets": sheets,
        "total_estimated_cells": total_estimated_cells,
        "total_formula_cells": total_formula_cells,
        "defined_names": defined_names,
        "profile_skipped": False,
    }


def profile_workbook_fast(file_size_mb):
    """Short-circuit for huge files: skip cell walk and structure."""
    return {
        "sheet_count": None,
        "sheets": [],
        "total_estimated_cells": None,
        "total_formula_cells": None,
        "defined_names": [],
        "profile_skipped": True,
        "profile_skipped_reason": (
            f"File is {file_size_mb:.1f}MB (>= {LARGE_FILE_SHORT_CIRCUIT_MB}MB); "
            f"full profile skipped. Run workbook_sample.py to inspect sheets."
        ),
    }


def profile_delimited(path, delimiter):
    row_count = 0
    max_col_count = 0

    with open(path, "r", encoding="utf-8", errors="replace", newline="") as fh:
        reader = csv.reader(fh, delimiter=delimiter)
        for row in reader:
            row_count += 1
            if len(row) > max_col_count:
                max_col_count = len(row)

    estimated_cells = row_count * max_col_count
    return {
        "sheet_count": 1,
        "sheets": [{
            "sheet_name": path.name,
            "max_row": row_count,
            "max_col": max_col_count,
            "estimated_cells": estimated_cells,
            "non_empty_rows": row_count,
            "formula_cells": 0,
            "merged_cells": [],
            "tables": [],
        }],
        "total_estimated_cells": estimated_cells,
        "total_formula_cells": 0,
        "defined_names": [],
        "profile_skipped": False,
    }


def recommend_actions(size_tier):
    if size_tier in ("large", "very_large"):
        return [
            "Run workbook_sample.py before detailed analysis.",
            "Use targeted sheet/column extraction (workbook_extract.py), not full dumps.",
            "Use workbook_search.py to locate specific terms across sheets.",
            "Write outputs to files and print concise summaries only.",
        ]
    if size_tier == "medium":
        return [
            "Prefer sampled inspection first for unfamiliar workbooks.",
            "Scope analysis to required sheets and columns.",
        ]
    return [
        "Full workbook inspection is generally acceptable.",
    ]


def main():
    if len(sys.argv) != 2:
        print("Usage: python skills/xlsx/scripts/workbook_profile.py <file>")
        sys.exit(1)

    path = Path(sys.argv[1]).expanduser()
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

    file_size_bytes = path.stat().st_size
    file_size_mb = file_size_bytes / (1024 * 1024)

    try:
        if suffix in (".xlsx", ".xlsm"):
            if file_size_mb >= LARGE_FILE_SHORT_CIRCUIT_MB:
                profile = profile_workbook_fast(file_size_mb)
                size_tier = "very_large"
            else:
                profile = profile_workbook(path)
                size_tier = classify_size(
                    file_size_bytes=file_size_bytes,
                    estimated_cells=profile["total_estimated_cells"] or 0,
                    sheet_count=profile["sheet_count"] or 0,
                    total_formula_cells=profile["total_formula_cells"] or 0,
                )
        elif suffix == ".csv":
            profile = profile_delimited(path, ",")
            size_tier = classify_size(
                file_size_bytes=file_size_bytes,
                estimated_cells=profile["total_estimated_cells"],
                sheet_count=profile["sheet_count"],
                total_formula_cells=profile["total_formula_cells"],
            )
        elif suffix == ".tsv":
            profile = profile_delimited(path, "\t")
            size_tier = classify_size(
                file_size_bytes=file_size_bytes,
                estimated_cells=profile["total_estimated_cells"],
                sheet_count=profile["sheet_count"],
                total_formula_cells=profile["total_formula_cells"],
            )
        else:
            print(json.dumps({
                "status": "error",
                "error": f"Unsupported file type: {suffix}",
            }))
            sys.exit(1)

        result = {
            "status": "success",
            "file": str(path),
            "file_size_bytes": file_size_bytes,
            "file_size_mb": round(file_size_mb, 2),
            "size_tier": size_tier,
            **profile,
            "recommended_actions": recommend_actions(size_tier),
        }
        print(json.dumps(result, indent=2, default=str))
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
