#!/usr/bin/env python3
"""Candidate mapping inventory for Template Prep.

REPLACES source_plan_inventory.py.

Emits two artifacts the rest of the pipeline consumes:

  1. table_regions.json   — detected runtime-input table regions. Used by
                            comprehensive_input_inventory.py as a force-clear
                            mask: cells inside a detected region are cleared
                            REGARDLESS of preserved_defaults.json. (Tables are
                            runtime input, not reusable defaults.)

  2. cell_candidates.json — per-input-cell label inventory. Used by the LLM in
                            Phase 3 to map cells to semantic roles confidently.
                            For every non-formula non-blank cell, emits the
                            text labels found to the left, above, and in the
                            most recent section header — the structured surface
                            the LLM matches against to assign payload paths.

Why this exists
---------------
The previous source_plan_inventory.py ran a thin keyword regex over labels
and produced "candidate runtime inputs" with a vague suggested_runtime_source
like "datamart_preferred_user_fallback". It did not produce table regions, did
not surface section context, and did not give the LLM a structured per-cell
candidate surface for Phase-3 mapping.

The result was twofold:

  - Phase 2 cleanup leaned on preserved_defaults.json (LLM-supplied) to decide
    what to keep. When the LLM marked an entire budget table as "structural
    defaults", real prior-deal numbers (land cost, GMAX, contingency) survived
    cleanup. Table regions are now detected mechanically and force-cleared.

  - Phase 3 mapping (semantic_role -> Excel cell) was the LLM scanning the
    workbook from scratch in chat. Now the LLM gets a per-cell labels payload
    with section headers, so each map is grounded in deterministic evidence.

Usage
-----
  python tp_scripts/candidate_mapping.py model.xlsx \
      --out-tables table_regions.json \
      --out-candidates cell_candidates.json

Both outputs are redacted: only label text, value class, and hashes are stored.
No raw prior-deal numeric values appear in either JSON.

Table-detection algorithm
-------------------------
Two detectors run; both feed the force-clear mask.

TALL detector (single-value-column tables: budgets, T12s, capex schedules):
For each adjacent (label_col, value_col) pair on each visible or hidden sheet:

  - Walk rows. A row "belongs" to a candidate run when label_col holds text
    AND value_col holds a numeric or formula value (not blank, not text).
  - Group belonging rows into runs allowing up to max_gap intervening rows
    (section headers, blank separators).
  - A run of >= min_rows belonging rows is a candidate region.
  - If any SUM/SUBTOTAL/SUMPRODUCT formula referencing the same column letter
    appears within or shortly after the run, the region is sum-confirmed.
  - Sub-runs of an already-claimed value column are suppressed.

A region with sum-confirmation is high-confidence. A region without is still
emitted but flagged confidence=medium; the LLM (and ultimately the user) can
override by approval, but Phase 2 force-clears either way: table-shaped
regions are runtime input, period.

WIDE detector (multi-column tables: rent comps, sales comps, unit-mix-by-type):
For each candidate row-label column on each sheet:

  - Find vertical runs of text-labelled rows (label_col holds text on
    >= min_rows consecutive or near-consecutive rows).
  - For each such row-label run, scan adjacent columns to the right (and one
    to the left of the label column) and identify any "data column" whose
    cells on those rows are >= MIN_FILL_RATIO non-blank — text OR numeric
    OR formula. Comp tables are heterogeneous: property names are text,
    unit counts are numeric, sale dates may be either.
  - If >= MIN_DATA_COLS such columns exist contiguously, emit a single
    wide_region covering the full rectangle (label_col plus data cols ×
    the row run).
  - Suppress wide regions that are wholly contained inside an already-emitted
    tall region (the tall detector wins on the overlap).

Wide regions are always confidence=medium (no SUM confirmation pattern fits
naturally for heterogeneous tables). The LLM can downgrade or approve via
preserved_defaults, but Phase 2 force-clears the rectangle. Inside a wide
region every cell is runtime input regardless of value class — that catches
text property names and pre-redacted city/state strings that tall detection
misses.

Cell-candidate algorithm
------------------------
For every non-blank, non-formula cell on every sheet:

  - Collect text labels in the columns immediately to the left (up to 3
    columns), the rows immediately above (up to 3 rows), and the most recent
    "section header" — the nearest preceding row where the same column holds
    plain text with no value in adjacent value columns.
  - Record the cell's value_class (rate/percent/medium/large_number/datetime/
    text), the named range it falls in (if any), and whether the cell sits
    inside a detected table region.
  - Do NOT assign a semantic role. The LLM does that in Phase 3 from this
    structured surface, with full visibility of the labels it was given.
"""

from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from tp_common import (  # shared primitives; see tp_common.py
    is_formula, is_text, is_numeric, hash_value,
)

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import openpyxl
from openpyxl.utils import get_column_letter

INTERNAL_SHEETS = {"_PreparationAudit"}
SUM_RE = re.compile(r"(?i)\b(SUM|SUBTOTAL|SUMPRODUCT|AGGREGATE)\s*\(")
COL_LETTER_RE = re.compile(r"\b([A-Z]{1,3})\$?\d+\b")

DEFAULT_MIN_RUN = 3
DEFAULT_MAX_GAP = 3

# Wide-table detection thresholds. Comp tables are short-and-wide:
# a row-label column + many data columns with heterogeneous (text + numeric)
# content. These thresholds are deliberately conservative to avoid false
# positives on prose-like sheets.
WIDE_MIN_DATA_COLS = 3        # at least this many adjacent data columns
WIDE_MIN_FILL_RATIO = 0.30    # a data col must be >=30% filled across the run
WIDE_MAX_SCAN_COLS = 20       # don't scan more than this many cols past label


def value_class(v: Any) -> str:
    if v is None or v == "":
        return "blank"
    if is_formula(v):
        return "formula"
    if isinstance(v, bool):
        return "boolean"
    if isinstance(v, (int, float)):
        a = abs(float(v))
        if a == 0:
            return "zero"
        if a < 1:
            return "rate_or_pct"
        if a >= 1_000_000:
            return "large_number"
        if a >= 1_000:
            return "medium_number"
        return "small_number"
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return "blank"
        return "text"
    cls = type(v).__name__
    if "date" in cls.lower() or "time" in cls.lower():
        return "datetime"
    return f"other_{cls}"


# ── TOGGLE-GATED REGION DETECTION (v4.8) ────────────────────────────────────
#
# A mode toggle ("Use Staged Inputs? No", "Co-Invest / Promote Structure? No")
# gates a block of input cells that the model ignores while the toggle is off.
# Those cells are still runtime input: the next user of the template flips the
# toggle and the prior deal's numbers go live, silently.
#
# This detector exists because the toggle's own documentation is a trap. Real
# templates explain themselves in the rows next to the toggle ('"No" = uses the
# single rates above'), and a reasonable reader concludes the gated block is
# inert and therefore not deal data. Worse, gated blocks are usually filled
# uniformly across periods or tiers, which is exactly the `parallel_siblings`
# shape the evidenced-defaults rule accepts as proof of a reusable default.
# So the region has to be marked deterministically, here, before any judgment
# gets applied to it.

# Binary on/off vocabularies only. A multi-way MODE selector ("Interest Only /
# IO Then Amortizing / Fully Amortizing") picks between branches that are all
# live; it does not create an inert region, and treating it as a gate would
# sweep ordinary deal inputs into the force-clear mask for no benefit.
BINARY_TOGGLE_VOCABS = (
    {"yes", "no"},
    {"y", "n"},
    {"true", "false"},
    {"on", "off"},
    {"enabled", "disabled"},
    {"enable", "disable"},
    {"include", "exclude"},
    {"included", "excluded"},
    {"1", "0"},
)

# An ALL-CAPS label with no value beside it is a section banner in every
# template convention we have seen. Used to bound a gated block.
SECTION_HEADER_RE = re.compile(r"^[A-Z0-9][A-Z0-9 \-&/(),.'—–]{3,}$")

# Rows that merely explain the toggle. Never cleared, never counted as gated
# input — they are the template's own documentation.
TOGGLE_EXPLAINER_RE = re.compile(r'["“”\']\s*(yes|no|y|n|true|false|on|off)\s*["“”\']', re.I)

GATED_BLOCK_MAX_ROWS = 40


def _toggle_options(ws, cell) -> set[str] | None:
    """Return the lower-cased option set of an explicit list data-validation on
    this cell, or None when the cell carries no list validation."""
    coord = cell.coordinate
    for dv in ws.data_validations.dataValidation:
        if dv.type != "list" or not dv.formula1:
            continue
        try:
            in_range = coord in dv.sqref
        except Exception:
            in_range = False
        if not in_range:
            continue
        raw = str(dv.formula1).strip()
        if not (raw.startswith('"') and raw.endswith('"')):
            # A range-backed list (=Lists!$A$1:$A$5). Options are not inline,
            # so the binary test cannot be applied — decline rather than guess.
            return set()
        return {o.strip().lower() for o in raw.strip('"').split(",") if o.strip()}
    return None


def _is_binary_toggle_value(v: Any) -> bool:
    if not isinstance(v, str):
        return False
    s = v.strip().lower()
    return any(s in vocab and len(vocab) == 2 for vocab in BINARY_TOGGLE_VOCABS)


def _nearest_section_header_row(ws, col: int, row: int, *, direction: int) -> int | None:
    """Walk up (direction -1) or down (+1) from `row` in column `col` looking for
    a section banner: ALL-CAPS text with nothing in the column to its right."""
    limit = 1 if direction < 0 else min(ws.max_row or row, row + GATED_BLOCK_MAX_ROWS)
    r = row + direction
    while (direction < 0 and r >= limit) or (direction > 0 and r <= limit):
        v = ws.cell(r, col).value
        if isinstance(v, str) and SECTION_HEADER_RE.match(v.strip()):
            right = ws.cell(r, col + 1).value
            if right in (None, ""):
                return r
        r += direction
    return None


def detect_gated_regions(ws) -> tuple[list[dict], list[dict]]:
    """Find binary mode toggles and the input regions they gate.

    Returns (gated_regions, toggle_cells). A gated region is emitted only when
    the toggle is corroborated — an explicit binary list validation, an
    explainer row quoting its own options, or a formula elsewhere on the sheet
    that branches on the toggle cell. One signal alone is enough; requiring all
    three would miss the common hand-rolled toggle with no data validation.
    """
    max_row = min(ws.max_row or 0, 8000)
    max_col = min(ws.max_column or 0, 250)
    if max_row < 2 or max_col < 2:
        return [], []

    # Formula references to each cell on this sheet, for the branch-evidence test.
    formula_refs: dict[str, int] = {}
    for row in ws.iter_rows(min_row=1, max_row=max_row, min_col=1, max_col=max_col):
        for cell in row:
            if not is_formula(cell.value):
                continue
            for m in re.finditer(r"\$?([A-Z]{1,3})\$?(\d+)", str(cell.value)):
                key = f"{m.group(1)}{m.group(2)}"
                formula_refs[key] = formula_refs.get(key, 0) + 1

    gated: list[dict] = []
    toggles: list[dict] = []

    for row in ws.iter_rows(min_row=1, max_row=max_row, min_col=1, max_col=max_col):
        for cell in row:
            v = cell.value
            if v is None or is_formula(v):
                continue
            options = _toggle_options(ws, cell)
            has_list_validation = bool(options)
            if has_list_validation:
                if not any(options == vocab for vocab in BINARY_TOGGLE_VOCABS):
                    continue          # multi-way mode selector — not a gate
            elif not _is_binary_toggle_value(v):
                continue

            label_col = None
            for off in (-1, -2):
                if cell.column + off >= 1:
                    lv = ws.cell(cell.row, cell.column + off).value
                    if isinstance(lv, str) and lv.strip() and not is_formula(lv):
                        label_col = cell.column + off
                        break
            if label_col is None:
                continue              # a bare Yes/No with no label is not a control

            explainer_rows: list[int] = []
            for dr in range(1, 4):
                r = cell.row + dr
                if r > max_row:
                    break
                for c in (label_col, cell.column):
                    ev = ws.cell(r, c).value
                    if isinstance(ev, str) and TOGGLE_EXPLAINER_RE.search(ev):
                        explainer_rows.append(r)
                        break

            branch_refs = formula_refs.get(cell.coordinate, 0)
            evidence = []
            if has_list_validation:
                evidence.append("binary_list_validation")
            if explainer_rows:
                evidence.append("explainer_row_quotes_options")
            if branch_refs:
                evidence.append("formula_branches_on_toggle")
            if not evidence:
                continue

            toggle_full = f"{ws.title}!{cell.coordinate}"
            toggles.append({
                "cell": toggle_full,
                "label": str(ws.cell(cell.row, label_col).value).strip()[:80],
                "option_count": len(options) if options else 2,
                "evidence": evidence,
            })

            # Bound the gated block: from the row after the toggle (skipping its
            # explainer rows) to the row before the next section banner.
            start = cell.row + 1
            while start in explainer_rows:
                start += 1
            next_header = _nearest_section_header_row(ws, label_col, cell.row, direction=1)
            end = (next_header - 1) if next_header else min(max_row, cell.row + GATED_BLOCK_MAX_ROWS)
            if end < start:
                continue

            # Gated input cells: non-formula, non-blank, NUMERIC-ish values in
            # any column at or right of the toggle's value column. Text cells in
            # the block are period headers ("Year 1".."Year 10") and other
            # scaffolding — structural, left to the ordinary path.
            cells: list[str] = []
            for r in range(start, end + 1):
                if r in explainer_rows:
                    continue
                for c in range(cell.column, max_col + 1):
                    cv = ws.cell(r, c).value
                    if cv is None or is_formula(cv) or isinstance(cv, str):
                        continue
                    if isinstance(cv, bool):
                        continue
                    cells.append(f"{ws.title}!{get_column_letter(c)}{r}")
            if not cells:
                continue

            gated.append({
                "sheet": ws.title,
                "sheet_state": ws.sheet_state,
                "toggle_cell": toggle_full,
                "toggle_label": str(ws.cell(cell.row, label_col).value).strip()[:80],
                "first_row": start,
                "last_row": end,
                "gated_cells": cells,
                "gated_cell_count": len(cells),
                "evidence": evidence,
                "confidence": "high" if len(evidence) >= 2 else "medium",
                "region_kind": "gated",
            })

    return gated, toggles


# ── TABLE-REGION DETECTION ──────────────────────────────────────────────────

def detect_table_regions(ws, *, min_rows: int = DEFAULT_MIN_RUN, max_gap: int = DEFAULT_MAX_GAP) -> list[dict]:
    """Find adjacent (label_col, value_col) pairs forming a runtime-input table."""
    max_row = ws.max_row or 0
    max_col = ws.max_column or 0
    if max_row < min_rows or max_col < 2:
        return []

    candidates: list[dict] = []

    # Try each value column against label columns immediately to the left or right.
    # Tables in real-estate models commonly put labels on either side of values
    # (e.g. construction-budget labels in column E with values in D, or unit-mix
    # labels in column B with values in C and beyond).
    for value_col in range(1, max_col + 1):
        for label_offset in (-1, 1, 2):
            label_col = value_col + label_offset
            if label_col < 1 or label_col > max_col or label_col == value_col:
                continue

            belongs: list[int] = []
            for row in range(1, max_row + 1):
                lv = ws.cell(row, label_col).value
                vv = ws.cell(row, value_col).value
                if is_text(lv) and (is_numeric(vv) or is_formula(vv)):
                    belongs.append(row)

            if len(belongs) < min_rows:
                continue

            # Group into runs allowing gaps
            run = [belongs[0]]
            runs: list[list[int]] = []
            for r in belongs[1:]:
                if r - run[-1] <= max_gap + 1:
                    run.append(r)
                else:
                    if len(run) >= min_rows:
                        runs.append(run)
                    run = [r]
            if len(run) >= min_rows:
                runs.append(run)

            for run in runs:
                first, last = run[0], run[-1]
                # Check for SUM-style aggregator referencing the value column,
                # within the run or within ~20 rows after.
                col_letter = get_column_letter(value_col)
                has_sum = False
                aggregator_cell = None
                for r in range(first, min(max_row, last + 25) + 1):
                    fv = ws.cell(r, value_col).value
                    if is_formula(fv) and SUM_RE.search(fv):
                        cols_used = COL_LETTER_RE.findall(fv.upper())
                        if col_letter in cols_used:
                            has_sum = True
                            aggregator_cell = ws.cell(r, value_col).coordinate
                            break

                candidates.append({
                    "sheet": ws.title,
                    "sheet_state": ws.sheet_state,
                    "label_col": get_column_letter(label_col),
                    "value_col": col_letter,
                    "first_row": first,
                    "last_row": last,
                    "belong_rows": run,
                    "row_count": len(run),
                    "has_sum_confirmation": has_sum,
                    "aggregator_cell": aggregator_cell,
                    "confidence": "high" if has_sum else "medium",
                })

    # De-dup: prefer sum-confirmed and larger runs; suppress sub-runs of an
    # already-claimed value column on the same sheet.
    candidates.sort(key=lambda t: (-int(t["has_sum_confirmation"]),
                                    -(t["last_row"] - t["first_row"])))
    claimed: list[tuple[str, str, int, int]] = []
    deduped: list[dict] = []
    for t in candidates:
        sup = False
        for s, vc, f, l in claimed:
            if s == t["sheet"] and vc == t["value_col"] and f <= t["first_row"] and l >= t["last_row"]:
                sup = True
                break
        if not sup:
            deduped.append(t)
            claimed.append((t["sheet"], t["value_col"], t["first_row"], t["last_row"]))
    return deduped


# ── WIDE TABLE-REGION DETECTION ─────────────────────────────────────────────

def _is_data_cell(v: Any) -> bool:
    """A 'data cell' for wide-table purposes: any non-blank cell except a
    formula whose role is structural (SUM, header). For wide-region detection
    we care that the cell *holds content* — text or numeric — because comp
    tables mix both.
    """
    if v is None or v == "":
        return False
    if is_formula(v):
        # Treat formulas as data; comp tables can have formula cells
        # (e.g., calculated price-per-unit).
        return True
    if isinstance(v, str):
        return v.strip() != ""
    return True


def detect_wide_table_regions(
    ws,
    tall_regions: list[dict],
    *,
    min_rows: int = DEFAULT_MIN_RUN,
    max_gap: int = DEFAULT_MAX_GAP,
) -> list[dict]:
    """Detect short-and-wide table regions: a row-label column with multiple
    adjacent heterogeneous (text + numeric) data columns.

    This catches rent-comp and sales-comp tables, which the tall detector
    misses because their data columns are text-heavy (property names, addresses,
    city/state strings interleaved with the numeric rows).

    `tall_regions` is the output of detect_table_regions for this same sheet;
    wide regions wholly contained inside a tall region are suppressed.
    """
    max_row = ws.max_row or 0
    max_col = ws.max_column or 0
    if max_row < min_rows or max_col < (WIDE_MIN_DATA_COLS + 1):
        return []

    # Precompute tall-region rectangles on this sheet for containment check.
    tall_rects: list[tuple[int, int, int, int]] = []
    for t in tall_regions:
        if t["sheet"] != ws.title:
            continue
        from openpyxl.utils import column_index_from_string
        vc = column_index_from_string(t["value_col"])
        lc = column_index_from_string(t["label_col"])
        c_lo, c_hi = min(lc, vc), max(lc, vc)
        tall_rects.append((t["first_row"], t["last_row"], c_lo, c_hi))

    def inside_any_tall(first_r: int, last_r: int, first_c: int, last_c: int) -> bool:
        for r1, r2, c1, c2 in tall_rects:
            if r1 <= first_r and last_r <= r2 and c1 <= first_c and last_c <= c2:
                return True
        return False

    out: list[dict] = []

    # Try every column as the row-label column. A row-label column is one with
    # >= min_rows text cells in some near-contiguous vertical run.
    for label_col in range(1, max_col + 1):
        # Find vertical runs of text in this column.
        text_rows: list[int] = []
        for row in range(1, max_row + 1):
            v = ws.cell(row, label_col).value
            if is_text(v):
                text_rows.append(row)
        if len(text_rows) < min_rows:
            continue

        # Group into runs allowing gaps.
        run = [text_rows[0]]
        runs: list[list[int]] = []
        for r in text_rows[1:]:
            if r - run[-1] <= max_gap + 1:
                run.append(r)
            else:
                if len(run) >= min_rows:
                    runs.append(run)
                run = [r]
        if len(run) >= min_rows:
            runs.append(run)

        for run in runs:
            first_row, last_row = run[0], run[-1]
            row_span = last_row - first_row + 1

            # For each candidate "start of data block" column, scan rightward
            # and find the longest contiguous block of columns where >= 30%
            # of the run rows hold a data cell.
            # Comp tables typically start one or two columns after the label;
            # we begin the scan at label_col+1 and allow gaps of up to 1
            # (a divider column).
            data_cols: list[int] = []
            gap = 0
            for col in range(label_col + 1, min(label_col + 1 + WIDE_MAX_SCAN_COLS, max_col + 1)):
                filled = sum(1 for r in run if _is_data_cell(ws.cell(r, col).value))
                fill_ratio = filled / row_span
                if fill_ratio >= WIDE_MIN_FILL_RATIO:
                    data_cols.append(col)
                    gap = 0
                else:
                    gap += 1
                    if gap > 1:
                        break

            # Trim trailing low-fill columns (we may have included one before
            # we knew the run ended).
            while data_cols and (
                sum(1 for r in run if _is_data_cell(ws.cell(r, data_cols[-1]).value)) / row_span
                < WIDE_MIN_FILL_RATIO
            ):
                data_cols.pop()

            if len(data_cols) < WIDE_MIN_DATA_COLS:
                continue

            # Must be contiguous (allow single-column gaps already filtered above).
            first_data_col = data_cols[0]
            last_data_col = data_cols[-1]

            # Suppress if wholly inside any tall region.
            if inside_any_tall(first_row, last_row, label_col, last_data_col):
                continue

            out.append({
                "sheet": ws.title,
                "sheet_state": ws.sheet_state,
                "region_kind": "wide",
                "label_col": get_column_letter(label_col),
                "first_data_col": get_column_letter(first_data_col),
                "last_data_col": get_column_letter(last_data_col),
                "first_row": first_row,
                "last_row": last_row,
                "belong_rows": run,
                "data_col_count": len(data_cols),
                "row_count": row_span,
                "confidence": "medium",
            })

    # De-dup overlapping wide regions on the same sheet: keep the largest.
    out.sort(key=lambda t: -(t["row_count"] * t["data_col_count"]))
    accepted: list[dict] = []
    for t in out:
        from openpyxl.utils import column_index_from_string
        t_first_c = column_index_from_string(t["label_col"])
        t_last_c = column_index_from_string(t["last_data_col"])
        overlap = False
        for a in accepted:
            a_first_c = column_index_from_string(a["label_col"])
            a_last_c = column_index_from_string(a["last_data_col"])
            if (a["sheet"] == t["sheet"]
                and a["first_row"] <= t["last_row"]
                and t["first_row"] <= a["last_row"]
                and a_first_c <= t_last_c
                and t_first_c <= a_last_c):
                overlap = True
                break
        if not overlap:
            accepted.append(t)
    return accepted


# ── CELL-CANDIDATE INVENTORY ────────────────────────────────────────────────

def _collect_left_labels(ws, row: int, col: int, max_left: int = 3) -> list[str]:
    out = []
    for dc in range(1, max_left + 1):
        c = col - dc
        if c < 1:
            break
        v = ws.cell(row, c).value
        if is_text(v):
            out.append(v.strip()[:80])
    return out


def _collect_above_labels(ws, row: int, col: int, max_up: int = 3) -> list[str]:
    out = []
    for dr in range(1, max_up + 1):
        r = row - dr
        if r < 1:
            break
        v = ws.cell(r, col).value
        if is_text(v):
            out.append(v.strip()[:80])
    return out


def _section_header(ws, row: int, col: int, max_lookback: int = 30) -> str | None:
    """A 'section header' is the nearest preceding row where the SAME column
    has plain text that is STANDALONE — i.e., not itself a labeled value.
    Captures patterns like 'Hard Costs' on D14 above a run of D15..D28 numeric
    inputs.

    v4.5 fix: in label/value layouts (labels in B, values in C) the nearest
    text above a value cell in column C is just the previous text VALUE — e.g.
    the asset-type value 'Garden' above the acreage cell — which then shipped
    in cell_candidates.json as section_header_above and misled Phase 3
    mapping evidence. A text cell with a text label immediately to its left is
    a value, not a header: skip it and keep walking.
    """
    for dr in range(1, max_lookback + 1):
        r = row - dr
        if r < 1:
            break
        v = ws.cell(r, col).value
        if is_text(v):
            left = ws.cell(r, col - 1).value if col > 1 else None
            if is_text(left):
                continue  # labeled value row, not a section header
            return v.strip()[:80]
    return None


def _cells_in_named_ranges(wb) -> dict[str, str]:
    """Map 'Sheet!Coord' -> defined-name string, for cells in defined names."""
    mapping: dict[str, str] = {}
    for dn in wb.defined_names.values():
        try:
            for sheet, coord in dn.destinations:
                # only single-cell mappings; range entries left alone
                if ":" not in coord:
                    mapping[f"{sheet}!{coord}"] = dn.name
        except Exception:
            continue
    return mapping


def collect_cell_candidates(wb, table_regions: list[dict]) -> list[dict]:
    """Walk every non-blank, non-formula cell and capture the structured
    surface the LLM will use to map it.
    """
    from openpyxl.utils import column_index_from_string
    # Build region lookup. For tall regions, key by (sheet, value_col) ->
    # list of (first, last, region_id). For wide regions, key by
    # (sheet, "wide") -> list of (first_row, last_row, first_col, last_col, region_id).
    tall_by_sheet_col: dict[tuple[str, str], list[tuple[int, int, int]]] = {}
    wide_by_sheet: dict[str, list[tuple[int, int, int, int, int]]] = {}
    for idx, t in enumerate(table_regions):
        if t.get("region_kind") == "wide":
            first_c = column_index_from_string(t["label_col"])
            last_c = column_index_from_string(t["last_data_col"])
            wide_by_sheet.setdefault(t["sheet"], []).append(
                (t["first_row"], t["last_row"], first_c, last_c, idx)
            )
        else:
            key = (t["sheet"], t["value_col"])
            tall_by_sheet_col.setdefault(key, []).append((t["first_row"], t["last_row"], idx))

    named = _cells_in_named_ranges(wb)
    out: list[dict] = []

    for ws in wb.worksheets:
        if ws.title in INTERNAL_SHEETS:
            continue
        max_row = min(ws.max_row or 0, 8000)
        max_col = min(ws.max_column or 0, 250)

        for r in range(1, max_row + 1):
            for c in range(1, max_col + 1):
                v = ws.cell(r, c).value
                cls = value_class(v)
                if cls in {"blank", "formula", "text"}:
                    # text cells are labels, not input candidates
                    continue
                if cls.startswith("other_"):
                    continue

                col_letter = get_column_letter(c)
                coord_full = f"{ws.title}!{col_letter}{r}"

                # In a detected table region? Tall regions are checked by
                # (sheet, value_col); wide regions are checked by rectangle.
                in_region_id: int | None = None
                tall_key = (ws.title, col_letter)
                for first, last, idx in tall_by_sheet_col.get(tall_key, []):
                    if first <= r <= last:
                        in_region_id = idx
                        break
                if in_region_id is None:
                    for first_r, last_r, first_c, last_c, idx in wide_by_sheet.get(ws.title, []):
                        if first_r <= r <= last_r and first_c <= c <= last_c:
                            in_region_id = idx
                            break

                left_labels = _collect_left_labels(ws, r, c)
                above_labels = _collect_above_labels(ws, r, c)
                section = _section_header(ws, r, c)

                out.append({
                    "cell": coord_full,
                    "sheet_state": ws.sheet_state,
                    "value_class": cls,
                    "value_hash": hash_value(v),
                    "left_labels": left_labels,
                    "above_labels": above_labels,
                    "section_header_above": section,
                    "in_named_range": named.get(coord_full),
                    "in_table_region_id": in_region_id,
                })

    return out


# ── ENTRY POINT ─────────────────────────────────────────────────────────────

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("workbook")
    p.add_argument("--out-tables", required=True,
                   help="JSON output: detected table regions (force-clear mask for Phase 2)")
    p.add_argument("--out-candidates", required=True,
                   help="JSON output: per-cell label inventory for Phase-3 mapping")
    p.add_argument("--include-hidden", action="store_true", default=True)
    p.add_argument("--min-rows", type=int, default=DEFAULT_MIN_RUN)
    p.add_argument("--max-gap", type=int, default=DEFAULT_MAX_GAP)
    args = p.parse_args()

    wb = openpyxl.load_workbook(args.workbook, data_only=False, keep_links=False)

    tall_regions: list[dict] = []
    wide_regions: list[dict] = []
    gated_regions: list[dict] = []
    toggle_cells: list[dict] = []
    for ws in wb.worksheets:
        if ws.title in INTERNAL_SHEETS:
            continue
        if not args.include_hidden and ws.sheet_state != "visible":
            continue
        sheet_tall = detect_table_regions(ws, min_rows=args.min_rows, max_gap=args.max_gap)
        for t in sheet_tall:
            t["region_kind"] = "tall"
        tall_regions.extend(sheet_tall)
        wide_regions.extend(detect_wide_table_regions(
            ws, sheet_tall, min_rows=args.min_rows, max_gap=args.max_gap,
        ))
        sheet_gated, sheet_toggles = detect_gated_regions(ws)
        gated_regions.extend(sheet_gated)
        toggle_cells.extend(sheet_toggles)

    # Combine for downstream consumers: comprehensive_input_inventory.py reads
    # the "regions" key, which now contains both kinds. region_kind distinguishes
    # them; consumers that want only tall regions can filter.
    regions = tall_regions + wide_regions

    candidates = collect_cell_candidates(wb, regions)

    Path(args.out_tables).write_text(
        json.dumps({
            "workbook": str(args.workbook),
            "detector_version": 2,
            "min_rows": args.min_rows,
            "max_gap": args.max_gap,
            "regions": regions,
            "tall_region_count": len(tall_regions),
            "wide_region_count": len(wide_regions),
            # Toggle-gated regions are kept in their own key, NOT merged into
            # "regions": their shape is a cell list rather than a
            # label_col/value_col run, and every consumer of "regions" assumes
            # the run shape. comprehensive_input_inventory.py and
            # post_clean_leak_scan.py read these keys explicitly.
            "gated_regions": gated_regions,
            "gated_region_count": len(gated_regions),
            "gated_cell_count": sum(g["gated_cell_count"] for g in gated_regions),
            "toggle_cells": toggle_cells,
        }, indent=2),
        encoding="utf-8",
    )
    Path(args.out_candidates).write_text(
        json.dumps({
            "workbook": str(args.workbook),
            "raw_prior_values_stored": False,
            "candidates": candidates,
        }, indent=2),
        encoding="utf-8",
    )

    print(json.dumps({
        "status": "ok",
        "tables_out": args.out_tables,
        "candidates_out": args.out_candidates,
        "table_region_count": len(regions),
        "tall_region_count": len(tall_regions),
        "wide_region_count": len(wide_regions),
        "table_region_high_confidence": sum(1 for t in regions if t.get("has_sum_confirmation")),
        "gated_region_count": len(gated_regions),
        "gated_cell_count": sum(g["gated_cell_count"] for g in gated_regions),
        "toggle_cell_count": len(toggle_cells),
        "candidate_cell_count": len(candidates),
        "candidate_cells_in_table_regions": sum(1 for c in candidates if c["in_table_region_id"] is not None),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# END candidate_mapping.py
