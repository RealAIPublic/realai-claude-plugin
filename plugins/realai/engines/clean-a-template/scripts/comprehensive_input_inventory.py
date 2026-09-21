#!/usr/bin/env python3
"""Comprehensive input-cell inventory for Template Prep cleanup planning.

WHAT CHANGED IN THIS VERSION
----------------------------
A new --table-regions argument accepts the JSON output of candidate_mapping.py.

Cells that fall inside a detected runtime-input table region are FORCE-CLEARED
regardless of preserved_defaults.json. This codifies a basic invariant:

    A cell inside a runtime-input table is, by definition, runtime input.
    It cannot also be a reusable template default.

Without this override, the LLM's preserved-defaults allowlist could (and did)
keep entire prior-deal budget tables alive in the cleaned workbook because the
LLM, scanning labels in chat, plausibly classified "Land Acquisition",
"GMAX Construction Budget", etc. as structural budget categories with default
values. The values themselves are deal-specific; the labels are structural.
The fix is to clear values mechanically and let the LLM map the table in the
manifest, not to ask the LLM to disambiguate label-vs-value cell-by-cell.

The allowlist still applies to scalar cells that are NOT inside a detected
table region — that is where reusable defaults like rent growth %, vacancy %,
exit cap default, etc. legitimately live.

USAGE
-----
  python tp_scripts/comprehensive_input_inventory.py model.xlsx \\
    --table-regions table_regions.json \\
    --preserved-defaults preserved_defaults.json \\
    --out input_inventory.json \\
    --emit-decisions decisions_clear_cells_draft.json

The --table-regions argument is OPTIONAL but strongly recommended. If omitted,
no force-clear override applies and the script behaves as before. Phase 1 of
the skill always supplies it.

PRESERVED DEFAULTS FILE FORMAT (unchanged)
------------------------------------------
{
  "cells": [
    {"cell": "Operating Assumptions!H48", "rationale": "$250/unit reserve default"}
  ],
  "ranges": [
    {"sheet": "Operating Assumptions", "range": "D53:M53", "rationale": "rent growth default"}
  ],
  "structural_text_regions": [
    {"sheet": "Operating Assumptions", "range": "B1:B100", "rationale": "section header column"}
  ]
}

OUTPUT
------
Inventory entries gain a new field: "force_cleared_reason", populated when a
cell that would otherwise have been preserved was force-cleared because it
fell inside a detected table region. The audit trail makes the override
explicit.
"""

from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from tp_common import (  # shared primitives; see tp_common.py
    hash_value,
)

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import openpyxl
from openpyxl.utils import column_index_from_string, get_column_letter
from openpyxl.utils.cell import range_boundaries

INTERNAL_SHEETS = {"_PreparationAudit"}

# Pure-text label heuristic: alpha start, label-shaped chars, no digits, length cap.
LABEL_PATTERN = re.compile(r"^[A-Za-z][A-Za-z\s\-/&,\.\(\)']{0,79}$")

TOGGLE_VOCAB = {
    "yes", "no", "y", "n", "true", "false",
    "sofr", "fixed", "ftm", "ttm", "ntm",
    "monthly", "quarterly", "annual", "annually",
    "active", "inactive", "on", "off",
    "primary", "secondary", "default",
}

DATE_TEXT_RE = re.compile(r"^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}$")


def value_class(value: Any) -> str:
    if value is None or value == "":
        return "blank"
    if isinstance(value, str) and value.startswith("="):
        return "formula"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        v = abs(float(value))
        if v == 0:
            return "zero"
        if v < 1:
            return "rate"
        if v >= 1_000_000:
            return "large_number"
        if v >= 1000:
            return "medium_number"
        return "small_number"
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return "blank"
        low = s.lower()
        if low in TOGGLE_VOCAB:
            return "toggle_text"
        if DATE_TEXT_RE.match(s):
            return "date_text"
        if LABEL_PATTERN.match(s) and not any(c.isdigit() for c in s):
            return "label_text"
        return "other_text"
    cls = type(value).__name__
    if "date" in cls.lower() or "time" in cls.lower():
        return "datetime"
    return f"other_{cls}"


def nearby_label(ws, row: int, col: int, max_left: int = 5, max_up: int = 2) -> str | None:
    for dc in range(1, max_left + 1):
        c = col - dc
        if c < 1:
            break
        v = ws.cell(row=row, column=c).value
        if isinstance(v, str) and v.strip() and not v.strip().startswith("="):
            return v.strip()[:80]
    for dr in range(1, max_up + 1):
        r = row - dr
        if r < 1:
            break
        v = ws.cell(row=r, column=col).value
        if isinstance(v, str) and v.strip() and not v.strip().startswith("="):
            return v.strip()[:80]
    return None


# ── FORMULA-ANCHOR DETECTION ────────────────────────────────────────────────
# A "formula-anchor constant" is a hardcoded scalar that INTERRUPTS a fill
# series — a run of formulas that are translations of one another (same skeleton
# with shifted cell refs), as produced by a fill-right or fill-down. Clearing it
# orphans the cascade even though the cell looks like an ordinary scalar input.
# It is NOT in a detected table region (those are handled by the force-clear
# path), which is why it slips through to the scalar fallthrough and gets
# silently cleared. We surface it to manual_review instead, where it is left
# intact unless a human/LLM explicitly decides to map or clear it.

_ANCHOR_CELLREF_RE = re.compile(r"\$?[A-Z]{1,3}\$?\d+")
_ANCHOR_WINDOW = 12          # cells scanned on each side along the axis
_ANCHOR_MIN_RUN = 4          # matching-skeleton formulas required (both sides combined)
_ANCHOR_ELIGIBLE_CLASSES = {"rate", "small_number"}


def _formula_skeleton(v: str) -> str:
    """Normalize a formula to its fill-series skeleton: drop sheet qualifiers and
    replace every cell reference with '#', so fill-right/fill-down siblings collapse
    to one string. '=IF(AND(SUM(AJ111:$EK$111)=0,AI111>1),1,0)' -> '=IF(AND(SUM(#:#)=0,#>1),1,0)'.
    """
    s = v.upper()
    s = re.sub(r"'[^']*'!", "", s)        # 'Sheet Name'!
    s = re.sub(r"\b[A-Z0-9_ ]+!", "", s)  # SheetName!
    return _ANCHOR_CELLREF_RE.sub("#", s)


def _interrupts_formula_series(ws, row: int, col: int, axis: str) -> bool:
    """True when one formula skeleton appears on BOTH sides of (row, col) within
    _ANCHOR_WINDOW along `axis` ('row' or 'col'), with >= _ANCHOR_MIN_RUN
    occurrences total. Both-sides is the key discriminator: a leading input
    (formulas only to one side) is not wedged, and a heterogeneous dashboard
    column (different formula each row) shares no common skeleton across sides.
    """
    from collections import Counter
    left: Counter = Counter()
    right: Counter = Counter()
    for d in range(1, _ANCHOR_WINDOW + 1):
        if axis == "row":
            lcell, rcell = (row, col - d), (row, col + d)
        else:
            lcell, rcell = (row - d, col), (row + d, col)
        if lcell[0] >= 1 and lcell[1] >= 1:
            lv = ws.cell(*lcell).value
            if isinstance(lv, str) and lv.startswith("="):
                left[_formula_skeleton(lv)] += 1
        rv = ws.cell(*rcell).value
        if isinstance(rv, str) and rv.startswith("="):
            right[_formula_skeleton(rv)] += 1
    for sk in set(left) & set(right):
        if left[sk] >= 1 and right[sk] >= 1 and (left[sk] + right[sk]) >= _ANCHOR_MIN_RUN:
            return True
    return False


def detect_formula_anchor(ws, row: int, col: int, cls: str) -> bool:
    """A scalar (rate/small_number) that interrupts a fill-formula series along its
    row or its column. Restricted to scalar policy classes so deal-size dollar
    values (medium/large numbers) are never retained by this path."""
    if cls not in _ANCHOR_ELIGIBLE_CLASSES:
        return False
    if col <= 2:                      # columns A/B are labels, not series cells
        return False
    return (_interrupts_formula_series(ws, row, col, "row")
            or _interrupts_formula_series(ws, row, col, "col"))


def load_preserved(path: str | None) -> dict:
    if not path:
        return {"cells": [], "ranges": [], "structural_text_regions": []}
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_array_formula_cells(wb) -> set[tuple[str, int, int]]:
    """Return {(sheet, row, col_idx)} for every cell that is part of an
    array-formula (CSE / spill) output range.

    Why this exists: openpyxl reports the value of an array-formula OUTPUT cell
    (a cell in the spill range OTHER than the anchor) as its CACHED scalar
    result — e.g. a spilled 480000 reads back as a plain int. value_class() then
    classifies it as a medium_number and the scalar fallthrough CLEARS it. The
    post-clean LibreOffice normalization recalc then RE-SPILLS the array formula
    and writes the value straight back into the 'cleared' cell, silently undoing
    the clear. The cleared template ships with a stale deal value restored.

    The fix is to recognize spill-range membership up front and treat those
    cells as derived_formula (do_not_write) — never clearable scalar inputs.
    openpyxl exposes ws.array_formulae as {anchor_coord: ArrayFormula}, whose
    .ref is the full spill rectangle (e.g. 'AQ34:AT34'). Every cell in that
    rectangle — anchor included — is derived.
    """
    out: set[tuple[str, int, int]] = set()
    for ws in wb.worksheets:
        if ws.title in INTERNAL_SHEETS:
            continue
        af = getattr(ws, "array_formulae", None)
        if not af:
            continue
        for anchor_coord, arr in af.items():
            ref = getattr(arr, "ref", None) or anchor_coord
            try:
                min_col, min_row, max_col, max_row = range_boundaries(ref)
            except Exception:
                # single-cell ref like 'AQ34'
                m = re.match(r"^([A-Za-z]+)(\d+)$", str(ref))
                if not m:
                    continue
                c = column_index_from_string(m.group(1)); r = int(m.group(2))
                min_col = max_col = c; min_row = max_row = r
            for r in range(min_row, max_row + 1):
                for c in range(min_col, max_col + 1):
                    out.add((ws.title, r, c))
    return out


def load_table_regions(path: str | None) -> dict[tuple[str, int, int], dict]:
    """Return {(sheet, row, col_idx): region_meta} for cells inside any detected
    runtime-input table region (tall OR wide). These cells are force-cleared.

    region_meta carries {"sum_confirmed": bool, "region_kind": str} so the
    region-exception gate (see classify_disposition) can distinguish a
    sum-confirmed budget/T12 (no exceptions, ever) from a medium-confidence
    label/value run that may in fact be a scalar assumptions block.

    Tall regions contribute (sheet, row, value_col_idx) for each row in
    belong_rows.

    Wide regions contribute the full rectangle: every (sheet, row, col_idx)
    where row is in belong_rows and col_idx ranges from first_data_col to
    last_data_col. The label column is intentionally excluded — labels are
    structural template scaffolding (e.g., "Property", "Address", "Sale Price"
    in a comp table) and are preserved. Only the data cells (which hold the
    prior deal's comp names, addresses, numbers) are force-cleared.
    """
    if not path:
        return {}
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    cells: dict[tuple[str, int, int], dict] = {}
    for region in data.get("regions", []):
        sheet = region["sheet"]
        kind = region.get("region_kind", "tall")
        meta = {
            "sum_confirmed": bool(region.get("has_sum_confirmation")),
            "region_kind": kind,
        }
        if kind == "wide":
            first_c = column_index_from_string(region["first_data_col"])
            last_c = column_index_from_string(region["last_data_col"])
            for r in region.get("belong_rows", []):
                for c in range(first_c, last_c + 1):
                    key = (sheet, r, c)
                    if key not in cells or meta["sum_confirmed"]:
                        cells[key] = meta
        else:
            col_idx = column_index_from_string(region["value_col"])
            for r in region.get("belong_rows", []):
                key = (sheet, r, col_idx)
                if key not in cells or meta["sum_confirmed"]:
                    cells[key] = meta
    return cells


def load_gated_regions(path: str | None) -> tuple[set[str], dict[str, dict]]:
    """Return (gated_cell_coords, toggle_cells) from the same table-regions file.

    Gated cells sit behind a binary mode toggle ("Use Staged Inputs = No").
    They are runtime input whatever the toggle currently reads: the toggle is a
    user choice, not evidence about what the region holds, and the next person
    to flip it activates whatever is sitting there.

    Toggle cells go the other way — the control itself is template structure and
    is preserved in the position the template's author left it.
    """
    if not path:
        return set(), {}
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    gated: set[str] = set()
    for region in data.get("gated_regions", []):
        gated.update(region.get("gated_cells", []))
    toggles = {t["cell"]: t for t in data.get("toggle_cells", []) if isinstance(t, dict) and t.get("cell")}
    return gated, toggles


# Value classes eligible for an approved region exception. Scalar policy/
# assumption shapes only — never property facts (medium/large numbers,
# dates) and never anything inside a sum-confirmed region.
# A backstop candidate whose OWN text is generic label vocabulary is a label
# stacked under an identity label (label columns trigger the up-fallback in
# nearby_label), not a deal-fact value. Skip those — they are structural.
STRUCTURAL_LABEL_VOCAB_RE = re.compile(
    r"^(type|state|city|county|location|developer|sponsor|borrower|owner|lender|"
    r"property|address|name|status|date|notes?|market|submarket|msa|region|"
    r"asset\s*type|product\s*type|deal\s*type)\s*[:#]?\s*$",
    re.I,
)


REGION_EXCEPTION_ELIGIBLE_CLASSES = {"rate", "small_number", "toggle_text", "boolean", "zero"}


def load_region_exceptions(preserved: dict) -> set[str]:
    """Cells in preserved_defaults.json explicitly flagged
    "approved_region_exception": true. These are the ONLY allowlist entries
    that may survive inside a detected table region, and only when the region
    is not sum-confirmed and the value class is exception-eligible. The flag
    must come from an explicit user approval in the Phase 1 form — the LLM
    must not set it unilaterally."""
    out: set[str] = set()
    for entry in preserved.get("cells") or []:
        if isinstance(entry, dict) and entry.get("approved_region_exception") and entry.get("cell"):
            out.add(entry["cell"])
    return out


# Label signatures for text-valued hard deal facts. The tall detector requires
# a numeric value column, so a property name or address sitting next to its
# label never lands inside a detected region — historically those cells (the
# MOST sensitive values in the workbook) fell to manual_review and relied on
# the LLM to sweep them up. This backstop auto-clears text cells whose
# adjacent label matches a deal-identity signature.
TEXT_FACT_LABEL_RE = re.compile(
    # Compound identity signatures may appear anywhere in the label:
    r"(property\s*name|deal\s*name|project\s*name|asset\s*name|portfolio\s*name|"
    r"development\s*name|community\s*name|"
    r"property\s*address|site\s*address|street\s*address|"
    # Bare role/identity words must constitute the ENTIRE label (v4.5 fix:
    # substring matching cleared structural headers like 'Owner Hard Cost',
    # 'Sponsor Equity', 'LENDER SUMMARY', 'County, Muni, Independent Tax Rate' —
    # generic CRE template vocabulary, not deal facts):
    r"^(?:address|property|borrower|sponsor|seller|buyer|lender|guarantor|"
    r"owner(?:ship)?|general\s*partner|location|msa|submarket|county|city|state|"
    r"city,?\s*state)\s*[:#]?\s*$)",
    re.I,
)


def cell_in_set(coord_full: str, cell_set: list) -> bool:
    if not cell_set:
        return False
    for entry in cell_set:
        target = entry.get("cell") if isinstance(entry, dict) else entry
        if target == coord_full:
            return True
    return False


def cell_in_range_set(coord: str, sheet: str, range_set: list) -> bool:
    if not range_set:
        return False
    m = re.match(r"^([A-Za-z]+)(\d+)$", coord)
    if not m:
        return False
    col = column_index_from_string(m.group(1))
    row = int(m.group(2))
    for entry in range_set:
        if not isinstance(entry, dict):
            continue
        entry_sheet = entry.get("sheet")
        entry_range = entry.get("range")
        if entry_sheet != sheet or not entry_range:
            continue
        try:
            min_col, min_row, max_col, max_row = range_boundaries(entry_range)
        except Exception:
            continue
        if min_col <= col <= max_col and min_row <= row <= max_row:
            return True
    return False


def classify_disposition(
    cls: str,
    in_preserved_cells: bool,
    in_preserved_ranges: bool,
    in_structural_region: bool,
    in_table_region: bool,
    has_region_exception: bool = False,
    region_sum_confirmed: bool = False,
    is_formula_anchor: bool = False,
    is_array_formula_output: bool = False,
    in_gated_region: bool = False,
    is_toggle_control: bool = False,
) -> tuple[str, str, str | None]:
    """Return (disposition, rationale, force_cleared_reason).

    The in_table_region flag triggers a clear that overrides the allowlist —
    the structural invariant: a cell inside a runtime-input table is runtime
    input. ONE narrow escape exists: a user-approved region exception
    (preserved_defaults entry with "approved_region_exception": true) is
    honored when BOTH (a) the region is not sum-confirmed — a SUM-confirmed
    run is a budget/T12/schedule and never an assumptions block — and (b) the
    value class is exception-eligible (rate / small_number / toggle / boolean /
    zero — scalar policy shapes, never medium/large numbers or dates). This
    exists because the tall detector cannot distinguish a vertical assumptions
    stack (the most common layout for true template defaults) from a budget;
    without the gate the allowlist could never converge for any default that
    happens to sit in a label/value run. force_cleared_reason is non-None when
    an override actually fired (i.e., the cell would otherwise have been
    preserved) — including refused exceptions, so the audit shows WHY.
    """
    if cls == "formula":
        return "do_not_write", "formula cell — preserved by being a formula", None
    if cls == "blank":
        return "do_not_write", "blank — nothing to do", None

    # Array-formula spill-range membership fires BEFORE the table-region
    # override and before any scalar/clear path. openpyxl reports a spilled
    # cell's cached scalar result, so it would otherwise be misread as a
    # clearable number; clearing it is futile because the next recalc re-spills
    # the value back. These cells are derived model logic, not inputs.
    if is_array_formula_output:
        return ("do_not_write",
                "cell is part of an array-formula (CSE/spill) output range; "
                "derived model logic, not a clearable input — clearing is undone "
                "by the next recalc re-spill",
                None)

    # ── TOGGLE-GATED REGIONS (v4.8) ──────────────────────────────────────────
    # Fires before the table-region override so the audit records the more
    # specific reason. A binary mode toggle ("Use Staged Inputs = No") makes its
    # block LOOK inert; it is not. Gated cells are cleared regardless of the
    # toggle's current value, and the only escape is the same explicit,
    # user-approved region exception the table-region path uses — never
    # `parallel_siblings`, which a gated block satisfies by construction (a
    # uniform 3% across ten periods is what a staged-input grid looks like AND
    # what a policy rate looks like, so the shape proves nothing here).
    if is_toggle_control:
        return ("preserve_default",
                "binary mode toggle / selector control: template structure, not "
                "runtime input — preserved in the position the template's author left it",
                None)
    if in_gated_region:
        if has_region_exception:
            if cls not in REGION_EXCEPTION_ELIGIBLE_CLASSES:
                return ("clear",
                        f"approved_region_exception REFUSED: value class {cls} not "
                        "exception-eligible (scalar policy shapes only)",
                        "region_exception_refused_value_class")
            return ("preserve_default",
                    "user-approved region exception: scalar default inside a "
                    "toggle-gated region",
                    None)
        # Deliberately NOT a `needs_decision_*` reason: gated cells go straight
        # into clear_cells and are not surfaced for triage. Surfacing them is
        # what let them be reasoned back into `preserved_defaults.json` — the
        # region's own documentation is persuasive and wrong.
        reason = ("in_gated_region_overrides_allowlist"
                  if (in_preserved_cells or in_preserved_ranges)
                  else "in_toggle_gated_region")
        return ("clear",
                "cell sits in a region gated by a binary mode toggle; a gated "
                "region is runtime input whatever the toggle currently reads — "
                "toggle state is a user choice, not evidence about the contents",
                reason)

    if in_table_region:
        if has_region_exception:
            if region_sum_confirmed:
                return ("clear",
                        "approved_region_exception REFUSED: region is sum-confirmed "
                        "(budget/T12/schedule shape) — no exceptions inside aggregated tables",
                        "region_exception_refused_sum_confirmed")
            if cls not in REGION_EXCEPTION_ELIGIBLE_CLASSES:
                return ("clear",
                        f"approved_region_exception REFUSED: value class {cls} not "
                        "exception-eligible (scalar policy shapes only)",
                        "region_exception_refused_value_class")
            return ("preserve_default",
                    "user-approved region exception: scalar default inside a "
                    "non-sum-confirmed detected region",
                    None)
        force_reason = None
        if in_preserved_cells or in_preserved_ranges:
            force_reason = "in_detected_table_region_overrides_allowlist"
        return ("clear",
                "cell sits inside a detected runtime-input table region; "
                "table cells are runtime input by definition",
                force_reason)

    if in_preserved_cells:
        return "preserve_default", "cell in preserved_defaults.cells allowlist", None
    if in_preserved_ranges:
        return "preserve_default", "cell in preserved_defaults.ranges allowlist", None
    if in_structural_region:
        return "preserve_structural", "cell in approved structural-text region", None
    if cls == "label_text":
        return "manual_review", "label-shaped text not in allowlist; LLM must decide structural vs deal-specific", None
    # ── SCALAR / ZERO / TOGGLE INPUTS (v4.7) ─────────────────────────────────
    # PRIOR BEHAVIOR (the Thompson leak): these classes returned manual_review,
    # and NOTHING downstream consumed manual_review — the recommended sequence
    # had no resolution step, so every one of these cells silently survived
    # into the cleaned workbook with its prior-deal value intact (zeros under
    # 'Free Months'/'Contingency'/'Rate Floor', phasing constants, etc.).
    #
    # NEW BEHAVIOR: an un-allowlisted scalar in an underwriting model is treated
    # as runtime INPUT and CLEARED by default. Preservation now requires an
    # affirmative signal — the preserved_defaults allowlist (handled above) or a
    # formula-anchor (clearing would orphan a fill cascade). The cell is still
    # surfaced (needs_decision=True in the emitted draft) so a reviewer can move
    # a genuine reusable default onto the allowlist and re-run; but the SAFE
    # DEFAULT is now clear, not silent-retain.
    if cls in {"toggle_text", "boolean"}:
        return ("clear",
                "controlled-vocab toggle not on preserved-defaults allowlist; "
                "treated as runtime input (add to preserved_defaults.json to keep)",
                "needs_decision_scalar_cleared_by_default")
    if cls == "zero":
        return ("clear",
                "zero value not on preserved-defaults allowlist; in an underwriting "
                "model a bare 0 under a deal label is a cleared-to-zero input, not a "
                "structural default (add to preserved_defaults.json to keep)",
                "needs_decision_zero_cleared_by_default")
    if cls in {"rate", "small_number", "medium_number", "large_number", "datetime", "date_text"}:
        if is_formula_anchor and cls in {"rate", "small_number"}:
            return ("manual_review",
                    "hardcoded scalar interrupts a fill-formula series (formula-anchor "
                    "constant); clearing would orphan the dependent cascade — preserve as a "
                    "default or map it explicitly, do not silently clear",
                    None)
        if cls in {"rate", "small_number"}:
            return ("clear",
                    f"{cls} input cell not on preserved-defaults allowlist; treated as "
                    "runtime input (add to preserved_defaults.json to keep as a default)",
                    "needs_decision_scalar_cleared_by_default")
        return "clear", f"{cls} input cell, no preservation rule matched", None
    if cls == "other_text":
        return "manual_review", "other text — likely deal-specific but may be a header", None
    return "manual_review", f"unrecognized class {cls}", None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workbook")
    parser.add_argument("--table-regions",
                        help="JSON file from candidate_mapping.py listing detected runtime-input "
                             "table regions. Cells inside these regions are force-cleared regardless "
                             "of the preserved-defaults allowlist. The same file's gated_regions / "
                             "toggle_cells keys drive toggle-aware clearing: cells behind a binary "
                             "mode toggle are cleared whatever the toggle reads, and the toggle "
                             "control itself is preserved.")
    parser.add_argument("--preserved-defaults", help="JSON file with cells/ranges/structural_text_regions to preserve")
    parser.add_argument("--out", required=True, help="Full inventory JSON output path")
    parser.add_argument("--emit-decisions", help="Write a draft clear_cells JSON for decisions.json merge")
    parser.add_argument("--include-hidden", action="store_true", default=True)
    parser.add_argument("--max-rows-per-sheet", type=int, default=8000)
    parser.add_argument("--max-cols-per-sheet", type=int, default=250)
    args = parser.parse_args()

    preserved = load_preserved(args.preserved_defaults)
    region_exceptions = load_region_exceptions(preserved)
    preserved_cells = preserved.get("cells") or []
    preserved_ranges = preserved.get("ranges") or []
    structural_regions = preserved.get("structural_text_regions") or []
    table_region_cells = load_table_regions(args.table_regions)
    gated_cells, toggle_cells = load_gated_regions(args.table_regions)

    wb = openpyxl.load_workbook(args.workbook, data_only=False, keep_links=False)
    array_output_cells = load_array_formula_cells(wb)
    inventory: list[dict] = []
    summary = {
        "by_disposition": {"clear": 0, "preserve_default": 0, "preserve_structural": 0, "manual_review": 0, "do_not_write": 0},
        "by_value_class": {},
        "by_sheet": {},
        "force_cleared_overrides": 0,
        "region_exceptions_applied": 0,
        "region_exceptions_refused": 0,
        "text_fact_backstop_cleared": 0,
        "table_region_cells_total": len(table_region_cells),
        "gated_region_cells_total": len(gated_cells),
        "gated_region_cells_cleared": 0,
        "gated_region_allowlist_overrides": 0,
        "toggle_controls_preserved": 0,
        "formula_anchors_flagged": 0,
        "array_formula_output_cells_protected": 0,
        "scalars_cleared_by_default_needs_decision": 0,
    }

    for ws in wb.worksheets:
        if ws.title in INTERNAL_SHEETS:
            continue
        if not args.include_hidden and ws.sheet_state != "visible":
            continue
        max_row = min(ws.max_row or 0, args.max_rows_per_sheet)
        max_col = min(ws.max_column or 0, args.max_cols_per_sheet)
        sheet_total = 0
        for row in ws.iter_rows(min_row=1, max_row=max_row, min_col=1, max_col=max_col):
            for cell in row:
                cls = value_class(cell.value)
                if cls == "blank":
                    continue
                if cls == "formula":
                    summary["by_value_class"][cls] = summary["by_value_class"].get(cls, 0) + 1
                    summary["by_disposition"]["do_not_write"] += 1
                    continue
                coord = cell.coordinate
                coord_full = f"{ws.title}!{coord}"
                in_cells = cell_in_set(coord_full, preserved_cells)
                in_ranges = cell_in_range_set(coord, ws.title, preserved_ranges)
                in_structural = cell_in_range_set(coord, ws.title, structural_regions)
                region_meta = table_region_cells.get((ws.title, cell.row, cell.column))
                in_table = region_meta is not None
                has_exception = coord_full in region_exceptions
                sum_confirmed = bool(region_meta and region_meta.get("sum_confirmed"))
                in_gated = coord_full in gated_cells
                is_toggle = coord_full in toggle_cells
                anchor = (not in_table) and (not in_gated) and detect_formula_anchor(ws, cell.row, cell.column, cls)
                is_array_out = (ws.title, cell.row, cell.column) in array_output_cells

                disposition, rationale, force_cleared_reason = classify_disposition(
                    cls, in_cells, in_ranges, in_structural, in_table,
                    has_region_exception=has_exception,
                    region_sum_confirmed=sum_confirmed,
                    is_formula_anchor=anchor,
                    is_array_formula_output=is_array_out,
                    in_gated_region=in_gated,
                    is_toggle_control=is_toggle,
                )
                if is_array_out and disposition == "do_not_write":
                    summary["array_formula_output_cells_protected"] += 1
                if force_cleared_reason and force_cleared_reason.startswith("needs_decision_"):
                    summary["scalars_cleared_by_default_needs_decision"] += 1
                if anchor and disposition == "manual_review":
                    summary["formula_anchors_flagged"] += 1
                if force_cleared_reason and force_cleared_reason.startswith("in_detected_table_region"):
                    summary["force_cleared_overrides"] += 1
                if force_cleared_reason and force_cleared_reason.startswith("in_gated_region_overrides_allowlist"):
                    summary["gated_region_allowlist_overrides"] += 1
                if in_gated and disposition == "clear":
                    summary["gated_region_cells_cleared"] += 1
                if is_toggle:
                    summary["toggle_controls_preserved"] += 1
                if force_cleared_reason and force_cleared_reason.startswith("region_exception_refused"):
                    summary["region_exceptions_refused"] += 1
                if in_table and disposition == "preserve_default":
                    summary["region_exceptions_applied"] += 1

                label = nearby_label(ws, cell.row, cell.column)

                # Text deal-fact backstop: text cells adjacent to a deal-identity
                # label (property name, address, borrower, ...) are hard deal
                # facts even though they never land inside a numeric-column
                # region. Auto-clear instead of manual_review.
                if (disposition == "manual_review"
                        and cls in {"other_text", "label_text"}
                        and label and TEXT_FACT_LABEL_RE.search(label)
                        and not STRUCTURAL_LABEL_VOCAB_RE.match(str(cell.value).strip())):
                    disposition = "clear"
                    rationale = ("text deal fact via label-signature backstop "
                                 "(adjacent label matches deal-identity signature)")
                    summary["text_fact_backstop_cleared"] += 1
                inventory.append({
                    "cell": coord_full,
                    "value_class": cls,
                    "value_hash": hash_value(cell.value),
                    "nearby_label_hash": hash_value(label) if label else None,
                    "disposition": disposition,
                    "rationale": rationale,
                    "force_cleared_reason": force_cleared_reason,
                    "in_table_region": in_table,
                    "in_gated_region": in_gated,
                    "is_toggle_control": is_toggle,
                    "sheet_state": ws.sheet_state,
                })
                summary["by_disposition"][disposition] += 1
                summary["by_value_class"][cls] = summary["by_value_class"].get(cls, 0) + 1
                sheet_total += 1
        summary["by_sheet"][ws.title] = sheet_total

    summary["total_inventoried"] = len(inventory)

    result = {
        "workbook": str(args.workbook),
        "scan_summary": summary,
        "preserved_defaults_loaded": bool(args.preserved_defaults),
        "table_regions_loaded": bool(args.table_regions),
        "raw_prior_values_stored": False,
        "inventory": inventory,
    }
    Path(args.out).write_text(json.dumps(result, indent=2), encoding="utf-8")

    if args.emit_decisions:
        clear_cells = []
        needs_decision = []
        for entry in inventory:
            if entry["disposition"] != "clear":
                continue
            rationale = "comprehensive_input_inventory: " + entry["rationale"]
            fcr = entry.get("force_cleared_reason")
            if fcr:
                rationale += f" [force-clear: {fcr}]"
            row = {
                "cell": entry["cell"],
                "rationale": rationale,
                "runtime_source_class": (
                    "user_required_table_input"
                    if entry.get("in_table_region")
                    else ("datamart_preferred_user_fallback"
                          if "label-signature backstop" in entry["rationale"]
                          else "user_required_or_datamart")
                ),
                "confidence": "high" if entry.get("in_table_region") else "medium",
            }
            clear_cells.append(row)
            if fcr and fcr.startswith("needs_decision_"):
                needs_decision.append({"cell": entry["cell"], "reason": fcr,
                                       "value_class": entry["value_class"]})
        decisions_fragment = {
            "_comment": (
                "Draft clear_cells generated by comprehensive_input_inventory.py. "
                "Cells with [force-clear: in_detected_table_region_overrides_allowlist] "
                "were cleared even though preserved_defaults.json marked them as defaults; "
                "table-shaped regions are runtime input by definition. Cells with "
                "[force-clear: needs_decision_*] are un-allowlisted scalars/zeros/toggles "
                "now CLEARED BY DEFAULT (v4.7) — previously these went to manual_review and "
                "silently survived. If any is a genuine reusable template default, add it to "
                "preserved_defaults.json and re-run. Review the cleared_by_default_needs_decision "
                "list before Phase 2."
            ),
            "clear_cells": clear_cells,
            "cleared_by_default_needs_decision": needs_decision,
            "manual_review_cells": [
                {
                    "cell": e["cell"],
                    "value_class": e["value_class"],
                    "rationale": e["rationale"],
                }
                for e in inventory if e["disposition"] == "manual_review"
            ],
        }
        Path(args.emit_decisions).write_text(json.dumps(decisions_fragment, indent=2), encoding="utf-8")

    print(json.dumps({
        "status": "ok",
        "out": args.out,
        "draft_decisions": args.emit_decisions,
        "summary": summary,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# END comprehensive_input_inventory.py
