#!/usr/bin/env python3
"""Post-clean coverage verification.

Compares the pre-clean comprehensive input inventory against the post-clean
workbook. Reports which 'clear'-disposition cells were actually cleared and
which still have values. Fails (exit code 2) if more than --max-uncleared
inventory cells remain populated.

USAGE
-----
  python tp_scripts/coverage_verify.py model_cleaned.xlsx \\
    --inventory input_inventory.json \\
    --out coverage_report.json \\
    --max-uncleared 20

This is the post-Phase-2 gate that catches the "the orchestrator missed cells"
failure mode. If you ran the full workflow (inventory → review → decisions.json
→ cleanup), this should pass with zero uncleared cells. A non-zero count means
either the orchestrator pruned cells that shouldn't have been pruned, or new
populated cells were introduced during cleanup.
"""

from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from tp_common import (  # shared primitives; see tp_common.py
    split_cell,
)

import argparse
import json
from pathlib import Path
from typing import Any

import openpyxl


def value_is_populated(value: Any) -> bool:
    if value is None or value == "":
        return False
    if isinstance(value, str) and not value.strip():
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workbook", help="Cleaned workbook to verify")
    parser.add_argument("--inventory", required=True, help="comprehensive_input_inventory.py output JSON")
    parser.add_argument("--out", required=True, help="Verification result JSON")
    parser.add_argument("--max-uncleared", type=int, default=20)
    args = parser.parse_args()

    inventory = json.loads(Path(args.inventory).read_text(encoding="utf-8"))
    expected_clear = [e for e in inventory.get("inventory", []) if e.get("disposition") == "clear"]

    wb = openpyxl.load_workbook(args.workbook, data_only=False, keep_links=False)

    cleared: list[str] = []
    uncleared: list[dict] = []
    missing_sheet: list[str] = []
    became_formula: list[str] = []  # cleared by replacement with a formula — fine

    for entry in expected_clear:
        ref = entry["cell"]
        try:
            sheet, coord = split_cell(ref)
        except ValueError:
            continue
        if sheet not in wb.sheetnames:
            missing_sheet.append(ref)
            continue
        try:
            cell = wb[sheet][coord]
        except Exception:
            missing_sheet.append(ref)
            continue
        v = cell.value
        if isinstance(v, str) and v.startswith("="):
            became_formula.append(ref)
            continue
        if value_is_populated(v):
            uncleared.append({
                "cell": ref,
                "value_class": entry.get("value_class"),
                "rationale": entry.get("rationale"),
            })
        else:
            cleared.append(ref)

    coverage_ratio = len(cleared) / len(expected_clear) if expected_clear else 1.0
    blocked = len(uncleared) > args.max_uncleared

    result = {
        "workbook": str(args.workbook),
        "inventory_file": args.inventory,
        "expected_clear_count": len(expected_clear),
        "cleared_count": len(cleared),
        "uncleared_count": len(uncleared),
        "missing_sheet_count": len(missing_sheet),
        "became_formula_count": len(became_formula),
        "coverage_ratio": round(coverage_ratio, 4),
        "blocked_due_to_uncleared": blocked,
        "max_uncleared_threshold": args.max_uncleared,
        "uncleared_sample": uncleared[:200],
        "missing_sheets_sample": missing_sheet[:50],
    }
    Path(args.out).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": "blocked" if blocked else "passed",
        "out": args.out,
        "coverage_ratio": round(coverage_ratio, 3),
        "uncleared": len(uncleared),
        "expected": len(expected_clear),
    }, indent=2))
    return 2 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())

# END coverage_verify.py

