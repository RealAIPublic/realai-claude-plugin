#!/usr/bin/env python3
"""
Targeted extractor for spreadsheet windows (sheet + row range + columns).

Usage examples:
    python skills/xlsx/scripts/workbook_extract.py model.xlsx \\
        --sheet "Rent Roll" --start-row 2 --end-row 500 --columns A:C,F \\
        --output output/extract.csv [--mode values|formulas|both]

    python skills/xlsx/scripts/workbook_extract.py data.csv \\
        --start-row 1 --end-row 10000 --columns 1-4,8 \\
        --output output/extract.csv

Modes (xlsx/xlsm only; delimited files always emit values):
    values    - computed values only
    formulas  - formula text where present, raw value otherwise
    both      - writes both files, derived from --output
                (e.g. --output extract.csv -> extract.values.csv + extract.formulas.csv)
                Default. Agents should prefer both.
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils.cell import column_index_from_string

# Excel column ceiling; used to resolve column specs up-front for CSV/TSV
# so we don't need a pre-scan pass just to learn the max column count.
EXCEL_MAX_COLS = 16384


def parse_column_spec(spec, max_col):
    """Parse column spec into sorted 1-based indices + warnings."""
    if not spec:
        return list(range(1, max_col + 1)), []

    tokens = [t.strip() for t in spec.split(",") if t.strip()]
    cols = set()
    dropped_ranges = []

    for token in tokens:
        if "-" in token and ":" in token:
            raise ValueError(f"Invalid token (mix of '-' and ':'): {token}")

        if ":" in token:
            left, right = token.split(":", 1)
            start = parse_single_col(left)
            end = parse_single_col(right)
            if end < start:
                start, end = end, start
            _add_range(cols, dropped_ranges, start, end, max_col)
            continue

        if "-" in token:
            left, right = token.split("-", 1)
            start = parse_single_col(left)
            end = parse_single_col(right)
            if end < start:
                start, end = end, start
            _add_range(cols, dropped_ranges, start, end, max_col)
            continue

        idx = parse_single_col(token)
        if idx <= max_col:
            cols.add(idx)
        else:
            dropped_ranges.append((idx, idx))

    if not cols:
        raise ValueError("No valid columns selected from column spec")

    warnings = []
    if dropped_ranges:
        warnings.append(
            f"Dropped column indices beyond source max_col ({max_col}): "
            + ", ".join(f"{a}-{b}" if a != b else f"{a}" for a, b in dropped_ranges)
        )
    return sorted(cols), warnings


def _add_range(cols, dropped, start, end, max_col):
    clipped = False
    for idx in range(start, end + 1):
        if idx <= max_col:
            cols.add(idx)
        else:
            clipped = True
    if clipped:
        dropped.append((max(start, max_col + 1), end))


def parse_single_col(token):
    t = token.strip()
    if re.fullmatch(r"[A-Za-z]+", t):
        return column_index_from_string(t.upper())
    if re.fullmatch(r"\d+", t):
        value = int(t)
        if value < 1:
            raise ValueError(f"Invalid column index: {value}")
        return value
    raise ValueError(f"Invalid column token: {token}")


def resolve_sheet(wb, sheet_name, sheet_index):
    if sheet_name:
        if sheet_name not in wb.sheetnames:
            raise ValueError(f"Sheet not found: {sheet_name}")
        return wb[sheet_name]
    if sheet_index is None:
        return wb[wb.sheetnames[0]]
    if sheet_index < 1 or sheet_index > len(wb.sheetnames):
        raise ValueError(f"sheet-index out of range: {sheet_index}")
    return wb[wb.sheetnames[sheet_index - 1]]


def derive_output_paths(output_path, mode):
    if mode == "both":
        stem = output_path.stem
        suffix = output_path.suffix or ".csv"
        parent = output_path.parent
        return {
            "values": parent / f"{stem}.values{suffix}",
            "formulas": parent / f"{stem}.formulas{suffix}",
        }
    return {mode: output_path}


def extract_workbook_mode(
    path, output_path, data_only, sheet_name, sheet_index, start_row, end_row, columns
):
    wb = load_workbook(path, read_only=True, data_only=data_only)
    ws = resolve_sheet(wb, sheet_name, sheet_index)

    max_row = ws.max_row or 0
    max_col = ws.max_column or 0
    if max_row == 0 or max_col == 0:
        wb.close()
        return {
            "rows_written": 0,
            "sheet_name": ws.title,
            "source_max_row": max_row,
            "source_max_col": max_col,
            "selected_columns": [],
            "warnings": [],
        }

    effective_start = max(1, start_row)
    effective_end = min(end_row if end_row is not None else max_row, max_row)
    if effective_end < effective_start:
        wb.close()
        raise ValueError("end-row must be >= start-row")

    selected_cols, warnings = parse_column_spec(columns, max_col)

    rows_written = 0
    with open(output_path, "w", encoding="utf-8", newline="") as out_fh:
        writer = csv.writer(out_fh)
        for row in ws.iter_rows(
            min_row=effective_start, max_row=effective_end, values_only=True
        ):
            out = []
            for col_idx in selected_cols:
                value = row[col_idx - 1] if col_idx - 1 < len(row) else None
                out.append("" if value is None else value)
            writer.writerow(out)
            rows_written += 1

    wb.close()
    return {
        "rows_written": rows_written,
        "sheet_name": ws.title,
        "source_max_row": max_row,
        "source_max_col": max_col,
        "selected_columns": selected_cols,
        "effective_start_row": effective_start,
        "effective_end_row": effective_end,
        "warnings": warnings,
    }


def extract_delimited(path, output_path, delimiter, start_row, end_row, columns):
    """Single-pass delimited extract.

    Columns are resolved against the Excel max-col ceiling so we don't need a
    pre-scan. Actual max_col is observed post-hoc during extraction.
    """
    selected_cols, warnings = parse_column_spec(columns, EXCEL_MAX_COLS)

    effective_start = max(1, start_row)
    end_cap = end_row if end_row is not None else None
    if end_cap is not None and end_cap < effective_start:
        raise ValueError("end-row must be >= start-row")

    rows_written = 0
    max_cols_seen = 0
    rows_scanned = 0

    with open(path, "r", encoding="utf-8", errors="replace", newline="") as in_fh, open(
        output_path, "w", encoding="utf-8", newline=""
    ) as out_fh:
        reader = csv.reader(in_fh, delimiter=delimiter)
        writer = csv.writer(out_fh)
        for current_row_num, row in enumerate(reader, start=1):
            rows_scanned = current_row_num
            if len(row) > max_cols_seen:
                max_cols_seen = len(row)
            if current_row_num < effective_start:
                continue
            if end_cap is not None and current_row_num > end_cap:
                break
            out = []
            for col_idx in selected_cols:
                out.append(row[col_idx - 1] if col_idx - 1 < len(row) else "")
            writer.writerow(out)
            rows_written += 1

    effective_cols = [c for c in selected_cols if c <= max_cols_seen]
    effective_end_reported = (
        end_cap
        if end_cap is not None and rows_scanned >= end_cap
        else rows_scanned
    )

    return {
        "rows_written": rows_written,
        "source_max_row_scanned": rows_scanned,
        "source_max_col": max_cols_seen,
        "selected_columns": effective_cols,
        "effective_start_row": effective_start,
        "effective_end_row": effective_end_reported,
        "warnings": warnings,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("file")
    parser.add_argument("--sheet", help="Sheet name for .xlsx/.xlsm")
    parser.add_argument("--sheet-index", type=int, help="1-based sheet index for .xlsx/.xlsm")
    parser.add_argument("--start-row", type=int, default=1, help="1-based start row (inclusive)")
    parser.add_argument("--end-row", type=int, default=None, help="1-based end row (inclusive)")
    parser.add_argument("--columns", default=None, help='Column spec, e.g. "A:C,F" or "1-3,8"')
    parser.add_argument("--output", required=True, help="Output CSV path")
    parser.add_argument(
        "--mode",
        choices=["values", "formulas", "both"],
        default="both",
        help="xlsx/xlsm only; delimited files always emit values. Default: both.",
    )
    args = parser.parse_args()

    path = Path(args.file).expanduser()
    if not path.exists():
        print(json.dumps({"status": "error", "error": f"File does not exist: {path}"}))
        sys.exit(1)

    output_path = Path(args.output).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    suffix = path.suffix.lower()
    if suffix == ".xls":
        print(json.dumps({
            "status": "error",
            "error": ".xls is not supported by openpyxl. Convert to .xlsx first."
        }))
        sys.exit(1)

    try:
        if suffix in (".xlsx", ".xlsm"):
            output_paths = derive_output_paths(output_path, args.mode)
            outputs = {}
            for mode_label, opath in output_paths.items():
                data_only = (mode_label == "values")
                meta = extract_workbook_mode(
                    path=path,
                    output_path=opath,
                    data_only=data_only,
                    sheet_name=args.sheet,
                    sheet_index=args.sheet_index,
                    start_row=args.start_row,
                    end_row=args.end_row,
                    columns=args.columns,
                )
                outputs[mode_label] = {"path": str(opath), **meta}
            result = {
                "status": "success",
                "source_file": str(path),
                "mode": args.mode,
                "start_row": args.start_row,
                "end_row": args.end_row,
                "columns": args.columns,
                "outputs": outputs,
            }
        elif suffix in (".csv", ".tsv"):
            delimiter = "," if suffix == ".csv" else "\t"
            meta = extract_delimited(
                path=path,
                output_path=output_path,
                delimiter=delimiter,
                start_row=args.start_row,
                end_row=args.end_row,
                columns=args.columns,
            )
            result = {
                "status": "success",
                "source_file": str(path),
                "output_file": str(output_path),
                "mode": "values",
                "start_row": args.start_row,
                "end_row": args.end_row,
                "columns": args.columns,
                **meta,
            }
        else:
            print(json.dumps({
                "status": "error",
                "error": f"Unsupported file type: {suffix}",
            }))
            sys.exit(1)

        print(json.dumps(result, indent=2, default=str))
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
