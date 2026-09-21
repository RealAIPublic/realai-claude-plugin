#!/usr/bin/env python3
"""
Structural and presentation integrity scanner for Excel models.

Usage:
    python skills/xlsx/scripts/workbook_integrity_scan.py <file.xlsx> [options]

Options:
    --sheets "Sheet1,Sheet2"   Limit the scan to named sheets (default: all).
    --json output.json         Also write the full report to a JSON file.
    --max-per-category N       Cap findings reported per category (default: 200).

Purpose:
    A workbook with ZERO Excel errors can still be wrong. This scanner surfaces
    the silent, error-free defects that recalc.py cannot see, because the file
    computes cleanly even when a value is structurally wrong, plus the
    presentation defects that make a correct number get misread.

    STRUCTURAL (integrity):
      numbers_as_text        A calculated quantity stored as a presentation
                             string ("$24.0M", "12.5%", "(1,234)") instead of a
                             numeric cell with a number format.
      hardcoded_outputs      A computed-surface sheet (pro forma, schedule,
                             sensitivity, ...) with almost no formulas: the
                             values are pasted, so the model is dead.
      no_formulas            A workbook with substantial numbers across 2+ sheets
                             but ZERO formulas anywhere: every computed value is
                             pasted. Name-agnostic (catches a comps/summary book).
      derived_hardcode       A hardcoded number under a derived ANALYSIS header
                             (Adjusted Rent, Implied Premium/Discount, Total Adj,
                             Margin, Yield): a dead analysis cell, not a formula.
      static_paste           A hardcoded number sitting between two formula
                             cells in the same row or column: the classic
                             pasted-over period that no longer recalculates.
      blank_table_header     An Excel table whose header row has an empty cell;
                             references that key off it resolve to the wrong column.
      label_link_mismatch    A link cell (=OtherSheet!X) whose row label names a
                             different metric than the cell it points at, or that
                             resolves to a blank cell. Catches the off-by-one
                             summary cascade and the wrong-but-plausible reference.
      blank_reference        A formula referencing an EMPTY cell (e.g. =-D6*C22
                             where C22 is blank), so that term silently evaluates
                             to 0. Catches a wrong reference buried in arithmetic,
                             which label_link_mismatch (pure links only) cannot.
      stored_formula_error   A cached Excel error already in the file.
      formula_literal        ADVISORY. A rate, margin, or multiple baked as a
                             numeric literal inside a formula instead of
                             referenced from a locked input cell.
      orphaned_name          ADVISORY. A defined name (named range) that no
                             formula references: defined but disconnected.

    PRESENTATION:
      stray_symbol           A decorative glyph in a cell where words or numbers
                             belong: emoji, status icons, arrows, bullets, and em
                             or en dashes (HIGH); math-operator symbols (ADVISORY).
      merged_cells           ADVISORY. A merge that fragments the grid: a
                             multi-row merge, or a multi-column merge inside the
                             body, which breaks sorting, filtering, and references.
      color_role             ADVISORY. A formula cell with blue font, the color
                             convention reserves for hardcoded inputs.
      narrow_column          ADVISORY. Unwrapped text wider than its column whose
                             neighbor is occupied, so it is cut off (shoved).
                             Width is allowed to vary; only real clipping flags.
      freeze_panes           ADVISORY. A freeze pane on a sheet that fits on
                             screen, or freeze positions inconsistent across the
                             workbook. Looks haphazard.
      font_consistency       ADVISORY. Body (non-bold) text mixing font sizes or
                             families on one sheet. The amateur tell.
      embedded_newline       ADVISORY. A hard line break typed inside a cell;
                             prefer wrap-text alignment so wrapping adapts.
      number_format          ADVISORY. A column mixing formatted numbers with
                             unformatted (General) cells.
      alignment              ADVISORY. Numeric cells not right-aligned, or a sheet
                             mixing vertical alignments in its data region.
      total_row_style        ADVISORY. A total/subtotal row, identified by a
                             formula that sums, adds, or subtracts other cells
                             (SUM, SUMIFS, SUMPRODUCT, COUNTIFS, +/-, ...), that
                             is not bold, so it does not read as a total.
      clipped_row            ADVISORY. A fixed row height too short to show its
                             wrapped text, so content is clipped. Height is
                             allowed to vary; only clipping flags.
      number_too_wide        ADVISORY. A formatted number wider than its column,
                             so the cell shows #### instead of the value.
      unlocked_anchor        ADVISORY. A single anchor cell referenced by a run of
                             sibling formulas with a relative address, so a fill
                             would drift off it. Should be $-locked.
      header_style           ADVISORY. Header bars using more than one fill color
                             across the workbook.

    HIGH-severity findings (numbers_as_text, hardcoded_outputs, no_formulas,
    derived_hardcode, static_paste, blank_table_header, label_link_mismatch,
    blank_reference, stored_formula_error, stray_symbol decorative subset) drive a
    non-zero exit so the scan gates a build in a
    feedback loop. ADVISORY findings never fail the gate; they are review prompts.

    To check the gate, use the EXIT CODE (non-zero means HIGH findings exist) or
    read the "GATE: PASS/FAIL" line printed to stderr. Do NOT grep the JSON for a
    severity string: severities are lowercase ("high"), and a case-mismatched
    grep ("HIGH") silently matches nothing and makes a failing model look clean. The scan is a net, not
    a substitute for reading: it still cannot catch a wrong reference between two
    unlabeled cells or the same metric computed two ways on two sheets, which is
    why SKILL.md pairs it with the Reconcile Before Delivery step.

    The scanner is read-only. It never modifies the workbook.
"""

import argparse
import json
import re
import sys
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter, column_index_from_string
from openpyxl.utils.cell import range_boundaries, coordinate_from_string

EXCEL_ERRORS = {"#REF!", "#DIV/0!", "#VALUE!", "#N/A", "#NAME?", "#NULL!", "#NUM!", "#SPILL!", "#CALC!"}

# A string cell is flagged as numbers_as_text only when the WHOLE value is a
# numeric token carrying a presentation marker: a currency sign, a percent, a
# multiple suffix, a scale suffix (K/M/MM/B), a thousands-separator comma, or
# accounting parentheses. A bare integer ("2024") is NOT flagged: the skill
# deliberately stores years as text.
_NUM_TEXT_PATTERNS = [
    re.compile(r"^\(?\s*-?\$\s*[\d,]+(\.\d+)?\s*(k|m|mm|bn|b)?\s*\)?$", re.IGNORECASE),   # $1,234 / $24.0M / ($1,234)
    re.compile(r"^\(?\s*-?[\d,]+(\.\d+)?\s*%\s*\)?$"),                                     # 12.5% / (3%)
    re.compile(r"^\s*-?[\d,]+(\.\d+)?\s*x\s*$", re.IGNORECASE),                            # 8.5x
    re.compile(r"^\(?\s*-?[\d,]+(\.\d+)?\s*(k|mm|bn)\s*\)?$", re.IGNORECASE),              # 24MM / 1.2bn
    re.compile(r"^\(\s*-?[\d,]+(\.\d+)?\s*\)$"),                                           # (1,234) accounting negative
    re.compile(r"^-?\d{1,3}(,\d{3})+(\.\d+)?$"),                                           # 1,234,567 thousands-separated
]

# Cell-reference tokens stripped from a formula before scanning for literals:
# Sheet!$A$1 style refs, ranges, and quoted-sheet refs.
_REF_TOKEN = re.compile(r"('[^']+'|\b[A-Za-z_][A-Za-z0-9_.]*)?!?\$?[A-Z]{1,3}\$?\d+", re.IGNORECASE)
_NUMERIC_LITERAL = re.compile(r"(?<![A-Za-z0-9_.$])\d+(\.\d+)?(?![A-Za-z0-9_.])")

# Integer literals that are almost always structural, not assumptions.
_BENIGN_INTS = {0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 24, 30, 31, 52, 60, 90,
                100, 120, 180, 252, 360, 365, 366, 1000, 10000, 100000, 1000000}

# Decorative characters that should not appear in a cell (HIGH). Words or a
# plain hyphen belong there instead.
_DECORATIVE_NAMES = ("EM DASH", "EN DASH", "HORIZONTAL BAR", "BULLET")


def _is_decorative_symbol(ch):
    o = ord(ch)
    if o >= 0x1F000:                      # emoji and pictographs
        return True
    if 0x2600 <= o <= 0x27BF:             # misc symbols and dingbats (check marks, crosses, stars)
        return True
    if 0x2190 <= o <= 0x21FF:             # arrows
        return True
    if 0x25A0 <= o <= 0x25FF:             # geometric shapes (filled squares, bullets)
        return True
    if o in (0x2014, 0x2013, 0x2015, 0x2022):  # em dash, en dash, horizontal bar, bullet
        return True
    if o == 0xFE0F:                       # emoji variation selector
        return True
    return False


# Math-operator glyphs that read fine but belong as words or ASCII (ADVISORY).
_MATH_SYMBOLS = {0x00D7: "x (times)", 0x00F7: "/ (divide)", 0x2212: "- (minus)",
                 0x2260: "<> (not equal)", 0x2264: "<= (less or equal)",
                 0x2265: ">= (greater or equal)", 0x00B1: "+/- (plus or minus)",
                 0x2248: "~ (approx)"}

# A formula that is exactly one cell reference and nothing else (a link), e.g.
# ='NOI Model'!C7 or =Assumptions!C45 or =C26. These are summary/link cells, and
# the label beside them should match the label beside the cell they point at.
_PURE_REF_RE = re.compile(
    r"^=\s*((?:'(?:[^']|'')+'|[A-Za-z_][\w.]*)!)?(\$?[A-Z]{1,3}\$?\d+)\s*$"
)
# Directional/structural words that do not establish a metric's identity.
_LABEL_STOP = {"less", "plus", "of", "the", "a", "at", "per", "to", "vs", "and", "as"}


def _norm_sheet(token):
    if token is None:
        return None
    if token.startswith("'") and token.endswith("'"):
        return token[1:-1].replace("''", "'")
    return token


def _label_tokens(text):
    if not isinstance(text, str):
        return set()
    # Keep parenthetical acronyms like (NOI)/(EGI) because they ARE the identity;
    # drop pure-numeric tokens (years, percentages) which are not identity-bearing.
    toks = re.split(r"[^a-z0-9]+", text.lower())
    return {w for w in toks if w and w not in _LABEL_STOP and not w.isdigit()}


def _row_label(ws, row, col, reach=8):
    """Nearest non-empty text cell to the left on the same row (the metric label)."""
    for c in range(col - 1, max(1, col - reach) - 1, -1):
        if c < 1:
            break
        v = ws.cell(row=row, column=c).value
        if isinstance(v, str) and v.strip() and not v.startswith("="):
            return v.strip()
    return None


def _looks_like_year(n):
    return float(n).is_integer() and 1900 <= int(n) <= 2100


def _font_rgb(cell):
    try:
        color = cell.font.color
        if color is None:
            return None
        rgb = getattr(color, "rgb", None)
        if isinstance(rgb, str) and len(rgb) >= 6:
            return rgb[-6:].upper()
    except Exception:
        return None
    return None


def _formula_text(v):
    """Formula source as a string, whatever shape openpyxl handed us.

    openpyxl returns an `ArrayFormula` object — not a string — for a CSE/spill
    formula's anchor cell. Every consumer of the formulas grid treats its values
    as text (regex substitution, `in` tests, `.join`), so an unnormalized
    ArrayFormula reaching them raised
    `TypeError: expected string or bytes-like object, got 'ArrayFormula'` and
    aborted the whole scan. Normalizing here fixes it once for all consumers
    rather than at each call site.
    """
    text = getattr(v, "text", None)
    if isinstance(text, str):
        return text
    return v if isinstance(v, str) else str(v)


def _build_grids(ws):
    """Return (types, formulas) keyed by (row, col) for non-empty cells.

    types value is one of 'f' (formula), 'n' (number), 's' (string).
    formulas values are always strings — see _formula_text.
    """
    types = {}
    formulas = {}
    for row in ws.iter_rows():
        for cell in row:
            v = cell.value
            if v is None:
                continue
            if (cell.data_type == "f"
                    or (isinstance(v, str) and v.startswith("="))
                    or getattr(v, "text", None) is not None):
                types[(cell.row, cell.column)] = "f"
                formulas[(cell.row, cell.column)] = _formula_text(v)
            elif isinstance(v, (int, float)) and not isinstance(v, bool):
                types[(cell.row, cell.column)] = "n"
            elif isinstance(v, str):
                types[(cell.row, cell.column)] = "s"
    return types, formulas


def scan_numbers_as_text(ws, cap):
    findings = []
    for row in ws.iter_rows():
        for cell in row:
            v = cell.value
            if not isinstance(v, str) or v.startswith("="):
                continue
            s = v.strip()
            if not any(ch.isdigit() for ch in s):
                continue
            if any(p.match(s) for p in _NUM_TEXT_PATTERNS):
                findings.append({
                    "category": "numbers_as_text",
                    "severity": "high",
                    "sheet": ws.title,
                    "cell": cell.coordinate,
                    "value": v,
                    "reason": "Calculated quantity stored as a presentation string; "
                              "store the number and apply a number format instead.",
                })
                if len(findings) >= cap:
                    return findings, True
    return findings, False


# Sheet names that imply the sheet computes something, so it should be formula-driven.
_COMPUTED_SHEET_RE = re.compile(
    r"pro\s*forma|proforma|sensitivit|scenario|schedule|cash\s*flow|projection|waterfall|"
    r"amortiz|operating\s*statement|\bnoi\b|\bdcf\b|return|debt\s*service|build[\s-]?up|model",
    re.IGNORECASE,
)


def scan_hardcoded_outputs(ws, types, formulas, cap):
    """A computed-surface sheet (by name) that contains almost no formulas: its
    numbers are pasted values, so the model is dead and will not recalculate.

    static_paste only catches a literal sitting between formulas; this catches the
    worse case where an entire pro forma, schedule, or sensitivity has no formulas
    at all and static_paste therefore never fires.
    """
    if not _COMPUTED_SHEET_RE.search(ws.title):
        return [], False
    numeric = sum(1 for t in types.values() if t == "n")
    if numeric >= 10 and len(formulas) < numeric * 0.1:
        return [{
            "category": "hardcoded_outputs",
            "severity": "high",
            "sheet": ws.title,
            "numeric_cells": numeric,
            "formula_cells": len(formulas),
            "reason": "This sheet's name implies it computes results, but it has almost no formulas; "
                      "the values are hardcoded. A model must be live: calculated outputs are formulas "
                      "that update when inputs change. Rebuild the cells as formulas referencing the inputs.",
        }], False
    return [], False


def scan_static_pastes(ws, types, cap):
    """A numeric literal interrupting a line that is OTHERWISE formulas.

    A true static paste sits in a row or column that is formula-driven (a
    projection period pasted over). A legitimate input (a unit-mix rent, a
    concession schedule) sits in a line that is mostly literals: an input row or
    column. To avoid flagging inputs, a row-orientation hit is suppressed when the
    cell's COLUMN is mostly literals (an input column), and a column-orientation
    hit is suppressed when the cell's ROW is mostly literals (an input row).
    """
    findings = []
    seen = set()
    for (r, c), t in types.items():
        if t != "n":
            continue
        left = types.get((r, c - 1))
        right = types.get((r, c + 1))
        up = types.get((r - 1, c))
        down = types.get((r + 1, c))
        orientation = None
        # A true paste is a literal isolated AMONG formulas: its formula neighbors
        # run one way and the orthogonal neighbors are not themselves literals. If an
        # orthogonal neighbor is a literal, the cell sits in a run of inputs (a
        # unit-mix column, a concession row), not a pasted-over formula series.
        if left == "f" and right == "f" and up != "n" and down != "n":
            orientation = "row"
        elif up == "f" and down == "f" and left != "n" and right != "n":
            orientation = "column"
        if orientation and (r, c) not in seen:
            seen.add((r, c))
            findings.append({
                "category": "static_paste",
                "severity": "high",
                "sheet": ws.title,
                "cell": f"{get_column_letter(c)}{r}",
                "value": ws.cell(row=r, column=c).value,
                "orientation": orientation,
                "reason": f"Hardcoded number between formula cells along its {orientation}; "
                          "likely a pasted-over value that no longer recalculates.",
            })
            if len(findings) >= cap:
                return findings, True
    return findings, False


def scan_formula_literals(ws, formulas, cap):
    findings = []
    for (r, c), f in formulas.items():
        stripped = _REF_TOKEN.sub(" ", f)
        suspicious = []
        for m in _NUMERIC_LITERAL.finditer(stripped):
            tok = m.group(0)
            num = float(tok)
            if "." in tok:
                suspicious.append(tok)
            elif num in _BENIGN_INTS or _looks_like_year(num):
                continue
            else:
                suspicious.append(tok)
        if suspicious:
            findings.append({
                "category": "formula_literal",
                "severity": "advisory",
                "sheet": ws.title,
                "cell": f"{get_column_letter(c)}{r}",
                "formula": f,
                "literals": suspicious,
                "reason": "Numeric literal embedded in a formula; if it is an assumption "
                          "(rate, margin, multiple) move it to a locked input cell and reference it.",
            })
            if len(findings) >= cap:
                return findings, True
    return findings, False


def scan_blank_table_headers(ws, cap):
    findings = []
    try:
        tables = list(ws.tables.values())
    except Exception:
        tables = []
    for table in tables:
        ref = getattr(table, "ref", None)
        if not ref:
            continue
        min_col, min_row, max_col, _max_row = range_boundaries(ref)
        for col in range(min_col, max_col + 1):
            cell = ws.cell(row=min_row, column=col)
            if cell.value is None or (isinstance(cell.value, str) and not cell.value.strip()):
                findings.append({
                    "category": "blank_table_header",
                    "severity": "high",
                    "sheet": ws.title,
                    "cell": cell.coordinate,
                    "table": getattr(table, "name", None),
                    "reason": "Empty header cell in an Excel table; references that key off "
                              "the header silently resolve to the wrong column.",
                })
                if len(findings) >= cap:
                    return findings, True
    return findings, False


def scan_stored_errors(ws_values, cap):
    findings = []
    for row in ws_values.iter_rows():
        for cell in row:
            v = cell.value
            if isinstance(v, str) and v in EXCEL_ERRORS:
                findings.append({
                    "category": "stored_formula_error",
                    "severity": "high",
                    "sheet": ws_values.title,
                    "cell": cell.coordinate,
                    "value": v,
                    "reason": "Cached Excel error in the workbook; run recalc.py to confirm and fix the source.",
                })
                if len(findings) >= cap:
                    return findings, True
    return findings, False


def scan_stray_symbols(ws, cap):
    findings = []
    for row in ws.iter_rows():
        for cell in row:
            v = cell.value
            if not isinstance(v, str) or v.startswith("="):
                continue
            decorative = sorted({ch for ch in v if _is_decorative_symbol(ch)})
            math_ops = sorted({ch for ch in v if ord(ch) in _MATH_SYMBOLS})
            if decorative:
                findings.append({
                    "category": "stray_symbol",
                    "severity": "high",
                    "sheet": ws.title,
                    "cell": cell.coordinate,
                    "value": v,
                    "symbols": [f"U+{ord(ch):04X} {ch}" for ch in decorative],
                    "reason": "Decorative glyph, icon, or em/en dash in a cell; use words or a plain hyphen.",
                })
            elif math_ops:
                findings.append({
                    "category": "stray_symbol",
                    "severity": "advisory",
                    "sheet": ws.title,
                    "cell": cell.coordinate,
                    "value": v,
                    "symbols": [_MATH_SYMBOLS[ord(ch)] for ch in math_ops],
                    "reason": "Math-operator symbol used as text; prefer words or ASCII operators.",
                })
            if len(findings) >= cap:
                return findings, True
    return findings, False


def scan_merged_cells(ws, cap):
    findings = []
    try:
        ranges = list(ws.merged_cells.ranges)
    except Exception:
        ranges = []
    for rng in ranges:
        multi_row = rng.max_row > rng.min_row
        multi_col = rng.max_col > rng.min_col
        # A single-row banner across columns at the very top is acceptable; flag
        # vertical merges and multi-column merges that sit in the body.
        if multi_row or (multi_col and rng.min_row > 2):
            findings.append({
                "category": "merged_cells",
                "severity": "advisory",
                "sheet": ws.title,
                "range": str(rng),
                "reason": "Merge in the data body; breaks sorting, filtering, copy-paste, and "
                          "formula references. Prefer a wider column or center-across-selection.",
            })
            if len(findings) >= cap:
                return findings, True
    return findings, False


def scan_color_roles(ws, types, cap):
    findings = []
    for (r, c), t in types.items():
        if t != "f":
            continue
        rgb = _font_rgb(ws.cell(row=r, column=c))
        if rgb == "0000FF":
            findings.append({
                "category": "color_role",
                "severity": "advisory",
                "sheet": ws.title,
                "cell": f"{get_column_letter(c)}{r}",
                "reason": "Formula cell with blue font; blue is reserved for hardcoded inputs. "
                          "Color by role workbook-wide: formulas black, inputs blue, cross-sheet links green.",
            })
            if len(findings) >= cap:
                return findings, True
    return findings, False


def _col_width(ws, col):
    dim = ws.column_dimensions.get(get_column_letter(col))
    w = getattr(dim, "width", None) if dim else None
    return w if w else 8.43


def scan_narrow_columns(ws, cap):
    """Text that is actually cut off: too wide for its column AND blocked.

    Column width is allowed and expected to vary. A long label is NOT truncated
    when it can overflow into an empty neighbor, and wrapped text is not truncated
    horizontally at all. This flags only the real defect: an unwrapped value wider
    than its column whose right neighbor is occupied, so the text is shoved/clipped.
    """
    findings = []
    flagged = set()
    for row in ws.iter_rows():
        for cell in row:
            v = cell.value
            if not isinstance(v, str) or v.startswith("=") or "\n" in v:
                continue
            if cell.alignment.wrap_text:
                continue  # wrapping shows the text on multiple lines; width is fine
            if cell.column in flagged:
                continue
            width = _col_width(ws, cell.column)
            if len(v) <= width * 1.1:
                continue  # fits within the column
            neighbor = ws.cell(row=cell.row, column=cell.column + 1).value
            if neighbor is None:
                continue  # overflows into an empty cell, so it is fully visible
            flagged.add(cell.column)
            findings.append({
                "category": "narrow_column",
                "severity": "advisory",
                "sheet": ws.title,
                "cell": cell.coordinate,
                "column": get_column_letter(cell.column),
                "content_length": len(v),
                "width": round(width, 1),
                "reason": "Text is wider than its column and the next cell is occupied, so it is cut off "
                          "(shoved together). Widen the column, or wrap the text and raise the row height.",
            })
            if len(findings) >= cap:
                return findings, True
    return findings, False


def scan_embedded_newlines(ws, cap):
    findings = []
    for row in ws.iter_rows():
        for cell in row:
            v = cell.value
            if isinstance(v, str) and not v.startswith("=") and "\n" in v:
                findings.append({
                    "category": "embedded_newline",
                    "severity": "advisory",
                    "sheet": ws.title,
                    "cell": cell.coordinate,
                    "value": v.replace("\n", "\\n"),
                    "reason": "Hard line break typed inside the cell; use wrap-text alignment with a "
                              "single string so the wrapping adapts to column width instead of breaking at a fixed point.",
                })
                if len(findings) >= cap:
                    return findings, True
    return findings, False


def scan_number_format_consistency(ws, cap):
    """A column that mixes formatted numbers with unformatted (General) cells."""
    findings = []
    col_formats = {}
    col_general = {}
    for row in ws.iter_rows():
        for cell in row:
            if isinstance(cell.value, (int, float)) and not isinstance(cell.value, bool):
                col_formats.setdefault(cell.column, set()).add(cell.number_format)
                if cell.number_format == "General":
                    col_general.setdefault(cell.column, []).append(cell.coordinate)
    for col, fmts in col_formats.items():
        real = fmts - {"General"}
        if "General" in fmts and real:
            findings.append({
                "category": "number_format",
                "severity": "advisory",
                "sheet": ws.title,
                "column": get_column_letter(col),
                "unformatted_cells": col_general.get(col, [])[:10],
                "other_formats": sorted(real),
                "reason": "Column mixes formatted numbers with unformatted (General) cells; "
                          "apply one consistent number format down the whole column.",
            })
            if len(findings) >= cap:
                return findings, True
    return findings, False


def scan_font_consistency(ws, cap):
    """A sheet whose body (non-bold) cells use more than one font size or family."""
    sizes = {}
    names = {}
    for row in ws.iter_rows():
        for cell in row:
            if cell.value is None:
                continue
            if cell.font.bold:
                continue   # headers are allowed to differ
            sz = cell.font.size
            nm = cell.font.name
            if sz is not None:
                sizes[sz] = sizes.get(sz, 0) + 1
            if nm is not None:
                names[nm] = names.get(nm, 0) + 1
    findings = []
    big_sizes = sorted([s for s, n in sizes.items() if n >= 3])
    if len(big_sizes) > 1:
        findings.append({
            "category": "font_consistency",
            "severity": "advisory",
            "sheet": ws.title,
            "body_font_sizes": big_sizes,
            "reason": f"Body text mixes font sizes {big_sizes}; pick one body size and use it throughout.",
        })
    if len([n for n, c in names.items() if c >= 3]) > 1:
        findings.append({
            "category": "font_consistency",
            "severity": "advisory",
            "sheet": ws.title,
            "body_font_names": sorted(names),
            "reason": f"Body text mixes font families {sorted(names)}; use one consistent font.",
        })
    return findings, False


def scan_alignment(ws, cap):
    """Numbers not right-aligned, and mixed vertical alignment in the data region."""
    findings = []
    not_right = []
    verticals = set()
    for row in ws.iter_rows():
        for cell in row:
            if cell.value is None:
                continue
            if cell.alignment.vertical is not None:
                verticals.add(cell.alignment.vertical)
            if isinstance(cell.value, (int, float)) and not isinstance(cell.value, bool):
                if cell.alignment.horizontal in ("left", "center"):
                    not_right.append(cell.coordinate)
    if not_right:
        findings.append({
            "category": "alignment", "severity": "advisory", "sheet": ws.title,
            "cells": not_right[:10], "count": len(not_right),
            "reason": "Numeric cells are left- or center-aligned; numbers read and compare best "
                      "right-aligned (or left at default). Right-align numbers consistently.",
        })
    if len(verticals) > 1:
        findings.append({
            "category": "alignment", "severity": "advisory", "sheet": ws.title,
            "vertical_alignments": sorted(verticals),
            "reason": f"Data cells mix vertical alignment {sorted(verticals)}; pick one (usually center) "
                      "for the data region so rows sit on a common baseline.",
        })
    return findings, False


# Functions that combine many cells into a total. Not exhaustive by design; the
# arithmetic test below covers plain addition and subtraction of cell references.
_AGG_FUNC_RE = re.compile(
    r"\b(SUM|SUMIFS?|SUMPRODUCT|SUBTOTAL|AGGREGATE|COUNT|COUNTA|COUNTIFS?|"
    r"AVERAGE|AVERAGEIFS?|DSUM)\s*\(", re.IGNORECASE
)
_CELL_REF_RE_AGG = re.compile(
    r"(?<![A-Za-z0-9_])(?:'[^']+'|[A-Za-z_][\w.]*)?!?\$?[A-Z]{1,3}\$?\d+"
)


def _is_aggregating_formula(value):
    """True if the formula combines multiple cells into a total: an aggregation
    function (SUM, SUMIFS, SUMPRODUCT, SUBTOTAL, COUNTIFS, ...) or a plain
    addition/subtraction of two or more cell references (=C6+C7+C8, =C11-C23)."""
    if not isinstance(value, str) or not value.startswith("="):
        return False
    body = value[1:]
    if _AGG_FUNC_RE.search(body):
        return True
    refs = _CELL_REF_RE_AGG.findall(body)
    # A binary + or - (preceded by a ref, number, or close paren) joining 2+ refs.
    if len(refs) >= 2 and re.search(r"[A-Za-z0-9_$)]\s*[+\-]", body):
        return True
    return False


def scan_total_row_style(ws, cap):
    """Total/subtotal rows that are not visually distinguished (bold).

    Keyed on rows that read like a total AND whose formula actually aggregates
    other cells, so a labeled input like "Total Units" (a hardcoded value) or a
    product like "Total Rentable SF" (=C7*C6) is not mistaken for a totals row.
    """
    total_words = {"total", "totals", "subtotal", "grand"}
    findings = []
    for row in ws.iter_rows():
        cells = [c for c in row if c.value is not None]
        if not cells:
            continue
        label = next((c.value for c in cells if isinstance(c.value, str) and not c.value.startswith("=")), None)
        if not label or not (_label_tokens(label) & total_words):
            continue
        if not any(_is_aggregating_formula(c.value) for c in cells):
            continue  # a metric label that merely contains "total", not a totals row
        if not any(c.font.bold for c in cells):
            findings.append({
                "category": "total_row_style", "severity": "advisory", "sheet": ws.title,
                "row": cells[0].row, "label": label,
                "reason": "Total/subtotal row is not bold; total rows should be visually distinct "
                          "(bold, often a top border) and styled the same way everywhere.",
            })
            if len(findings) >= cap:
                return findings, True
    return findings, False


def scan_clipped_rows(ws, cap):
    """A row whose explicit height is too small to show its wrapped text.

    Row height is allowed and expected to vary so content stays visible. The
    defect is the opposite: a wrapped, multi-line cell squeezed into a fixed,
    too-short row, so the text is clipped. Auto-sized rows (no explicit height)
    are skipped because the application fits them.
    """
    findings = []
    line_pts = 15.0  # approximate rendered height of one line of body text
    # Cells inside a merge are skipped: a merged region spans several columns or
    # rows, so a single cell's width/height estimate is unreliable (and would
    # over-report clipping). Estimating only single cells keeps this trustworthy.
    merged = set()
    try:
        for rng in ws.merged_cells.ranges:
            for r in range(rng.min_row, rng.max_row + 1):
                for c in range(rng.min_col, rng.max_col + 1):
                    merged.add((r, c))
    except Exception:
        pass
    for row in ws.iter_rows():
        if not row:
            continue
        dim = ws.row_dimensions.get(row[0].row)
        height = getattr(dim, "height", None) if dim else None
        if not height:
            continue  # auto-sized; the app fits the content
        worst_lines, culprit = 1, None
        for cell in row:
            v = cell.value
            if not isinstance(v, str) or v.startswith("=") or not cell.alignment.wrap_text:
                continue
            if (cell.row, cell.column) in merged:
                continue
            chars = max(int(_col_width(ws, cell.column)), 1)
            lines = sum(max(1, (len(seg) + chars - 1) // chars) for seg in v.split("\n"))
            if lines > worst_lines:
                worst_lines, culprit = lines, cell.coordinate
        if worst_lines >= 2:
            needed = worst_lines * line_pts
            if height < needed * 0.6:
                findings.append({
                    "category": "clipped_row", "severity": "advisory", "sheet": ws.title,
                    "row": row[0].row, "cell": culprit, "height": round(height, 1),
                    "needed_estimate": round(needed),
                    "reason": "Row height is too small to show its wrapped text, so content is clipped. "
                              "Raise the row height or let it auto-size.",
                })
                if len(findings) >= cap:
                    return findings, True
    return findings, False


def _solid_fill_rgb(cell):
    try:
        if cell.fill and cell.fill.patternType == "solid":
            rgb = cell.fill.fgColor.rgb
            if isinstance(rgb, str) and rgb not in ("00000000",):
                return rgb.upper()
    except Exception:
        return None
    return None


def scan_header_style(wb, sheet_filter, cap):
    """Header bars using more than one fill color across the table set.

    A header bar is a run of two or more adjacent bold, same-filled cells across a
    row. Keying on the run excludes lone status badges (red/amber/green severity
    cells), which are single cells, not bars.
    """
    header_fills = set()
    for ws in wb.worksheets:
        if sheet_filter is not None and ws.title not in sheet_filter:
            continue
        for row in ws.iter_rows():
            run_fill, run_len = None, 0
            for cell in row:
                fill = _solid_fill_rgb(cell) if (cell.value is not None and cell.font.bold) else None
                if fill and fill == run_fill:
                    run_len += 1
                else:
                    if run_fill and run_len >= 2:
                        header_fills.add(run_fill)
                    run_fill, run_len = fill, (1 if fill else 0)
            if run_fill and run_len >= 2:
                header_fills.add(run_fill)
    if len(header_fills) > 1:
        return [{
            "category": "header_style", "severity": "advisory",
            "header_fill_colors": sorted(header_fills),
            "reason": "Header bars use more than one fill color across the workbook; standardize a single "
                      "header fill across the full table set (a second, distinct subheader fill is fine if used consistently).",
        }], False
    return [], False


def scan_freeze_panes(wb, sheet_filter, cap):
    """Freeze panes that are inconsistent across the workbook or on a sheet that fits on screen."""
    findings = []
    present = {}
    for ws in wb.worksheets:
        if sheet_filter is not None and ws.title not in sheet_filter:
            continue
        if ws.freeze_panes:
            present[ws.title] = ws.freeze_panes
    distinct = set(present.values())
    for ws in wb.worksheets:
        if sheet_filter is not None and ws.title not in sheet_filter:
            continue
        fp = ws.freeze_panes
        if not fp:
            continue
        reasons = []
        if (ws.max_row or 0) <= 25 and (ws.max_column or 0) <= 12:
            reasons.append("the sheet fits on screen without scrolling, so a freeze adds nothing")
        if len(distinct) > 1:
            reasons.append(f"freeze position {fp} is inconsistent with other sheets ({sorted(distinct)})")
        if reasons:
            findings.append({
                "category": "freeze_panes",
                "severity": "advisory",
                "sheet": ws.title,
                "freeze_panes": fp,
                "reason": "; ".join(reasons) + ". Use freeze panes only on large scrollable sheets, "
                          "at the header boundary, and apply the same convention across the workbook.",
            })
            if len(findings) >= cap:
                return findings, True
    return findings, False


def scan_orphaned_names(wb, all_formula_text, cap):
    findings = []
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
        if re.search(r"(?<![A-Za-z0-9_])" + re.escape(name) + r"(?![A-Za-z0-9_])", all_formula_text):
            continue
        findings.append({
            "category": "orphaned_name",
            "severity": "advisory",
            "name": name,
            "value": getattr(dn, "value", None),
            "reason": "Defined name referenced by no formula; either wire it in or remove it. "
                      "(May be used by a chart or data validation, which this scan does not see.)",
        })
        if len(findings) >= cap:
            return findings, True
    return findings, False


def scan_label_link_mismatch(wb, wb_values, sheet_filter, cap):
    """A link cell whose row label does not match the label of the cell it points at.

    Catches the wrong-but-plausible reference and the off-by-one summary cascade:
    a row labeled "Effective Gross Income" that links to a cell labeled "Total
    Operating Expenses", or a link that resolves to a blank cell. This is the
    failure recalc and the other checks cannot see, because the link is valid and
    the number is believable.
    """
    findings = []
    sheet_names = set(wb.sheetnames)
    for ws in wb.worksheets:
        if sheet_filter is not None and ws.title not in sheet_filter:
            continue
        for row in ws.iter_rows():
            for cell in row:
                v = cell.value
                if not isinstance(v, str) or not v.startswith("="):
                    continue
                m = _PURE_REF_RE.match(v)
                if not m:
                    continue
                sheet_tok, coord = m.group(1), m.group(2).replace("$", "")
                tgt_sheet = _norm_sheet(sheet_tok[:-1]) if sheet_tok else ws.title
                if tgt_sheet not in sheet_names:
                    continue
                try:
                    tcol, trow = coordinate_from_string(coord)
                    tcol_i = column_index_from_string(tcol)
                except Exception:
                    continue
                # Skip the totals/carry-forward pattern: a cell that pulls the
                # last data row up to a totals row (E27 = E26), same sheet/column.
                if tgt_sheet == ws.title and tcol_i == cell.column and trow == cell.row - 1:
                    continue
                src_label = _row_label(ws, cell.row, cell.column)
                if not src_label:
                    continue  # no label beside the link; nothing to reconcile
                tgt_ws = wb[tgt_sheet]
                tgt_val = None
                if tgt_sheet in wb_values.sheetnames:
                    tgt_val = wb_values[tgt_sheet].cell(row=trow, column=tcol_i).value
                # (a) The link resolves to a blank cell: it points at nothing.
                if tgt_val is None and tgt_ws.cell(row=trow, column=tcol_i).value is None:
                    findings.append({
                        "category": "label_link_mismatch", "severity": "high",
                        "sheet": ws.title, "cell": cell.coordinate,
                        "label": src_label, "links_to": f"{tgt_sheet}!{coord}",
                        "reason": f"'{src_label}' links to {tgt_sheet}!{coord}, which is empty. "
                                  "The reference is off or the target moved.",
                    })
                    if len(findings) >= cap:
                        return findings, True
                    continue
                # (b) Both rows have labels but they name different metrics.
                tgt_label = _row_label(tgt_ws, trow, tcol_i)
                if tgt_label:
                    st, tt = _label_tokens(src_label), _label_tokens(tgt_label)
                    if st and tt and not (st & tt):
                        findings.append({
                            "category": "label_link_mismatch", "severity": "high",
                            "sheet": ws.title, "cell": cell.coordinate,
                            "label": src_label, "links_to": f"{tgt_sheet}!{coord}",
                            "target_label": tgt_label,
                            "reason": f"'{src_label}' links to a cell labeled '{tgt_label}'. "
                                      "The label and the value it shows are different metrics.",
                        })
                        if len(findings) >= cap:
                            return findings, True
    return findings, False


# A single cell reference (not a range member), capturing $ lock state.
_SINGLE_REF_RE = re.compile(
    r"(?<![A-Za-z0-9_:])(?:('(?:[^']|'')+'|[A-Za-z_][\w.]*)!)?(\$?)([A-Z]{1,3})(\$?)(\d+)(?![\d(:])"
)
# Functions that handle a blank reference on purpose; skip blank-reference checks here.
_BLANK_TOLERANT_RE = re.compile(
    r"\b(IF|IFS|IFERROR|IFNA|ISBLANK|ISERROR|ISNA|ISNUMBER|ISTEXT|COUNTBLANK|COUNTA|N|NA)\s*\(",
    re.IGNORECASE,
)


def _iter_single_refs(body, default_sheet, sheet_names):
    """Yield (sheet, col_idx, row, abs_col, abs_row) for each single-cell ref."""
    for m in _SINGLE_REF_RE.finditer(body):
        sheet_tok, dcol, col, drow, row = m.groups()
        sheet = _norm_sheet(sheet_tok) if sheet_tok else default_sheet
        if sheet_tok and sheet not in sheet_names:
            continue
        try:
            ci = column_index_from_string(col)
        except Exception:
            continue
        yield sheet, ci, int(row), (dcol == "$"), (drow == "$")


def scan_blank_reference(wb, sheet_filter, cap):
    """A formula referencing an EMPTY cell, so that term silently evaluates to 0.

    Catches the wrong-reference-buried-in-arithmetic case (e.g. =-D6*Assumptions!C22
    where C22 is the blank placeholder row and the real rate is in C23), which the
    pure-link label_link_mismatch check cannot see.
    """
    sheet_names = set(wb.sheetnames)
    # Group by (referencing sheet, referenced blank target) so one bad reference
    # repeated down a column is a single finding, not dozens.
    groups = {}
    for ws in wb.worksheets:
        if sheet_filter is not None and ws.title not in sheet_filter:
            continue
        for row in ws.iter_rows():
            for cell in row:
                v = cell.value
                if not (isinstance(v, str) and v.startswith("=")):
                    continue
                if _BLANK_TOLERANT_RE.search(v):
                    continue
                for sheet, ci, ri, _ac, _ar in _iter_single_refs(v[1:], ws.title, sheet_names):
                    if sheet not in sheet_names:
                        continue
                    if wb[sheet].cell(row=ri, column=ci).value is None:
                        key = (ws.title, sheet, get_column_letter(ci), ri)
                        g = groups.setdefault(key, {"cells": [], "formula": v})
                        g["cells"].append(cell.coordinate)
                        break
    findings = []
    for (ref_sheet, tsheet, tcol, tri), g in groups.items():
        n = len(g["cells"])
        findings.append({
            "category": "blank_reference", "severity": "high",
            "sheet": ref_sheet, "cell": g["cells"][0], "formula": g["formula"],
            "references": f"{tsheet}!{tcol}{tri}",
            "count": n,
            "reason": f"Formula references the empty cell {tsheet}!{tcol}{tri}"
                      + (f" ({n} cells do this)" if n > 1 else "")
                      + ", so that term silently evaluates to 0. Likely a wrong or stale "
                        "reference (often one row off the intended input).",
        })
        if len(findings) >= cap:
            return findings, True
    return findings, False


_DEC_RE = re.compile(r"\.(0+|#+)")


def _num_display_len(value, fmt):
    """Estimated character width of a number as displayed under its number format.

    Returns None for General/text formats (the app auto-fits those rather than
    showing ####)."""
    if not fmt or fmt in ("General", "@"):
        return None
    neg = value < 0
    av = abs(value)
    if "%" in fmt:
        av *= 100
    m = _DEC_RE.search(fmt)
    dec = len(m.group(1)) if m else 0
    intpart = f"{int(av):d}"
    length = len(intpart)
    if "," in fmt:
        length += (len(intpart) - 1) // 3
    if dec > 0:
        length += 1 + dec
    if any(sym in fmt for sym in ("$", "£", "€")):
        length += 1
    if "%" in fmt:
        length += 1
    if neg:
        length += 2 if "(" in fmt else 1
    return length


def scan_number_too_wide(ws, cap):
    """A formatted number wider than its column, so the cell shows #### not the value."""
    findings = []
    flagged_cols = set()
    for row in ws.iter_rows():
        for cell in row:
            if not isinstance(cell.value, (int, float)) or isinstance(cell.value, bool):
                continue
            if cell.column in flagged_cols:
                continue
            disp = _num_display_len(cell.value, cell.number_format)
            if disp is None:
                continue
            width = _col_width(ws, cell.column)
            if disp > width:
                flagged_cols.add(cell.column)
                findings.append({
                    "category": "number_too_wide", "severity": "advisory",
                    "sheet": ws.title, "cell": cell.coordinate, "value": cell.value,
                    "number_format": cell.number_format,
                    "est_display_chars": disp, "width": round(width, 1),
                    "reason": "Number is wider than its column, so the preview shows #### instead of the value. "
                              "Widen the column to fit the formatted number.",
                })
                if len(findings) >= cap:
                    return findings, True
    return findings, False


def scan_unlocked_anchor(wb, sheet_filter, cap):
    """A single anchor cell referenced by a run of sibling formulas with a relative
    address on the run's axis, so a fill would drift off the anchor. Should be $-locked."""
    findings = []
    sheet_names = set(wb.sheetnames)
    refs = {}
    for ws in wb.worksheets:
        if sheet_filter is not None and ws.title not in sheet_filter:
            continue
        for row in ws.iter_rows():
            for cell in row:
                v = cell.value
                if not (isinstance(v, str) and v.startswith("=")):
                    continue
                for sheet, ci, ri, ac, ar in _iter_single_refs(v[1:], ws.title, sheet_names):
                    refs.setdefault((sheet, ci, ri), []).append((ws.title, cell.row, cell.column, ac, ar))
    for (tsheet, tci, tri), users in refs.items():
        if len(users) < 3:
            continue
        col_counts, row_counts = {}, {}
        for u in users:
            col_counts[u[2]] = col_counts.get(u[2], 0) + 1
            row_counts[u[1]] = row_counts.get(u[1], 0) + 1
        top_col, top_col_n = max(col_counts.items(), key=lambda x: x[1])
        top_row, top_row_n = max(row_counts.items(), key=lambda x: x[1])
        anchor = f"{tsheet}!{get_column_letter(tci)}{tri}"
        if top_col_n >= 4:  # a column of formulas references this anchor
            run = [u for u in users if u[2] == top_col]
            if sum(1 for u in run if not u[4]) >= len(run) * 0.6:  # rows not locked
                findings.append({
                    "category": "unlocked_anchor", "severity": "advisory",
                    "sheet": run[0][0], "anchor": anchor,
                    "referenced_by": f"{len(run)} formulas down column {get_column_letter(top_col)}",
                    "reason": f"A column of formulas references the anchor {anchor} with a relative row; "
                              f"a fill would drift off it. Lock the row: {get_column_letter(tci)}${tri}.",
                })
        elif top_row_n >= 4:  # a row of formulas references this anchor
            run = [u for u in users if u[1] == top_row]
            if sum(1 for u in run if not u[3]) >= len(run) * 0.6:  # cols not locked
                findings.append({
                    "category": "unlocked_anchor", "severity": "advisory",
                    "sheet": run[0][0], "anchor": anchor,
                    "referenced_by": f"{len(run)} formulas across row {top_row}",
                    "reason": f"A row of formulas references the anchor {anchor} with a relative column; "
                              f"a fill would drift off it. Lock the column: ${get_column_letter(tci)}{tri}.",
                })
        if len(findings) >= cap:
            return findings, True
    return findings, False


# Column headers that denote a COMPUTED ANALYSIS RESULT (not an input or imported
# datum). A hardcoded number under one of these is a dead derived value. Kept
# narrow on purpose: "adj"/"per unit"/"$/SF"/"avg" are excluded because a
# "Location Adj (%)" column is an analyst input, a comp "$/SF" column is imported
# data, and "MSA Avg Rent" is a market-benchmark input, none of which are derived
# in-sheet. Only unambiguous results count.
_DERIVED_HEADER_RE = re.compile(
    r"implied|premium|discount|\bmargin\b|\byield\b|spread|weighted|"
    r"adj\w*\s+\w*\s*rent|adjusted\s*rent|total\s*adj|net\s*effective|effective\s*rent",
    re.IGNORECASE,
)


def _col_header(ws, row, col, reach=30):
    for r in range(row - 1, max(1, row - reach) - 1, -1):
        if r < 1:
            break
        v = ws.cell(row=r, column=col).value
        if isinstance(v, str) and v.strip() and not v.startswith("="):
            return v.strip()
    return None


def scan_derived_hardcode(ws, types, cap):
    """A hardcoded number where a computed value belongs: under a derived column
    header (Adjusted Rent, Implied Premium/Discount, /SF, % of EGI) or in a derived
    summary row (Average/Subtotal). Catches a dead analysis grid even on a sheet
    whose name is not a computed surface (e.g. a 'Rent Comps' adjustment grid)."""
    findings = []
    col_numeric = {}
    for (r, c), t in types.items():
        if t in ("n", "f"):
            col_numeric[c] = col_numeric.get(c, 0) + 1
    for (r, c), t in types.items():
        if t != "n":
            continue
        header = _col_header(ws, r, c)
        hit = None
        if header and col_numeric.get(c, 0) >= 2 and _DERIVED_HEADER_RE.search(header):
            hit = header
        if hit:
            findings.append({
                "category": "derived_hardcode", "severity": "high",
                "sheet": ws.title, "cell": f"{get_column_letter(c)}{r}",
                "value": ws.cell(row=r, column=c).value,
                "derived_as": hit.replace("\n", " "),
                "reason": "A derived value is a hardcoded number, not a formula, so it does not update "
                          "and cannot be audited. Compute it from its inputs with a formula.",
            })
            if len(findings) >= cap:
                return findings, True
    return findings, False


def main():
    parser = argparse.ArgumentParser(description="Integrity scanner for Excel models.")
    parser.add_argument("file")
    parser.add_argument("--sheets", default=None, help="Comma-separated sheet names to scan.")
    parser.add_argument("--json", dest="json_out", default=None, help="Write full report to this JSON file.")
    parser.add_argument("--max-per-category", type=int, default=200)
    args = parser.parse_args()

    path = Path(args.file).expanduser()
    if not path.exists():
        print(json.dumps({"status": "error", "error": f"File does not exist: {path}"}))
        sys.exit(1)
    if path.suffix.lower() not in (".xlsx", ".xlsm"):
        print(json.dumps({
            "status": "error",
            "error": f"Integrity scan supports .xlsx/.xlsm only, got {path.suffix}. "
                     "CSV/TSV files have no formulas, formats, or tables to scan.",
        }))
        sys.exit(1)

    wanted = None
    if args.sheets:
        wanted = {s.strip() for s in args.sheets.split(",") if s.strip()}

    cap = args.max_per_category
    try:
        wb = load_workbook(path, data_only=False)
        wb_values = load_workbook(path, data_only=True)
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}))
        sys.exit(1)

    findings = []
    truncated = set()
    sheets_scanned = []
    all_formula_text_parts = []
    total_formula_cells = 0
    total_numeric_cells = 0

    for ws in wb.worksheets:
        types, formulas = _build_grids(ws)
        all_formula_text_parts.extend(formulas.values())  # all sheets, for orphan check
        if wanted is not None and ws.title not in wanted:
            continue
        sheets_scanned.append(ws.title)
        total_formula_cells += sum(1 for t in types.values() if t == "f")
        total_numeric_cells += sum(1 for t in types.values() if t == "n")

        sheet_scans = [
            lambda: scan_numbers_as_text(ws, cap),
            lambda: scan_hardcoded_outputs(ws, types, formulas, cap),
            lambda: scan_static_pastes(ws, types, cap),
            lambda: scan_formula_literals(ws, formulas, cap),
            lambda: scan_blank_table_headers(ws, cap),
            lambda: scan_stray_symbols(ws, cap),
            lambda: scan_merged_cells(ws, cap),
            lambda: scan_color_roles(ws, types, cap),
            lambda: scan_narrow_columns(ws, cap),
            lambda: scan_embedded_newlines(ws, cap),
            lambda: scan_number_format_consistency(ws, cap),
            lambda: scan_font_consistency(ws, cap),
            lambda: scan_alignment(ws, cap),
            lambda: scan_total_row_style(ws, cap),
            lambda: scan_clipped_rows(ws, cap),
            lambda: scan_number_too_wide(ws, cap),
            lambda: scan_derived_hardcode(ws, types, cap),
        ]
        for fn in sheet_scans:
            f, trunc = fn()
            findings.extend(f)
            if trunc and f:
                truncated.add(f[0]["category"])

        if ws.title in wb_values.sheetnames:
            f, trunc = scan_stored_errors(wb_values[ws.title], cap)
            findings.extend(f)
            if trunc and f:
                truncated.add("stored_formula_error")

    orphan_findings, orphan_trunc = scan_orphaned_names(wb, " ".join(all_formula_text_parts), cap)
    findings.extend(orphan_findings)
    if orphan_trunc and orphan_findings:
        truncated.add("orphaned_name")

    mismatch_findings, mismatch_trunc = scan_label_link_mismatch(wb, wb_values, wanted, cap)
    findings.extend(mismatch_findings)
    if mismatch_trunc and mismatch_findings:
        truncated.add("label_link_mismatch")

    freeze_findings, freeze_trunc = scan_freeze_panes(wb, wanted, cap)
    findings.extend(freeze_findings)
    if freeze_trunc and freeze_findings:
        truncated.add("freeze_panes")

    header_findings, _ = scan_header_style(wb, wanted, cap)
    findings.extend(header_findings)

    blankref_findings, blankref_trunc = scan_blank_reference(wb, wanted, cap)
    findings.extend(blankref_findings)
    if blankref_trunc and blankref_findings:
        truncated.add("blank_reference")

    anchor_findings, anchor_trunc = scan_unlocked_anchor(wb, wanted, cap)
    findings.extend(anchor_findings)
    if anchor_trunc and anchor_findings:
        truncated.add("unlocked_anchor")

    # Workbook-level: an analysis with substantial numbers across 2+ sheets but
    # zero formulas anywhere is a dead workbook (every computed value is pasted).
    # Name-agnostic, so it catches a comps or summary workbook whose sheet names
    # do not match the computed-surface list. A single raw-data sheet is exempt.
    if total_formula_cells == 0 and total_numeric_cells >= 20 and len(sheets_scanned) >= 2:
        findings.append({
            "category": "no_formulas", "severity": "high",
            "sheets": sheets_scanned, "numeric_cells": total_numeric_cells,
            "reason": "The workbook has no formulas anywhere but holds substantial numeric content across "
                      "multiple sheets; every computed value (averages, adjustments, ratios, totals) is "
                      "hardcoded. The analysis is not live or auditable. Build computed cells as formulas.",
        })

    wb.close()
    wb_values.close()

    by_category = {}
    by_severity = {"high": 0, "advisory": 0}
    for f in findings:
        by_category[f["category"]] = by_category.get(f["category"], 0) + 1
        by_severity[f["severity"]] = by_severity.get(f["severity"], 0) + 1

    high_count = by_severity.get("high", 0)
    result = {
        "status": "issues_found" if findings else "clean",
        "file": str(path),
        "sheets_scanned": sheets_scanned,
        "high_severity_count": high_count,
        "advisory_count": by_severity.get("advisory", 0),
        "counts_by_category": by_category,
        "truncated_categories": sorted(truncated),
        "findings": findings,
    }

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2, default=str)

    print(json.dumps(result, indent=2, default=str))
    # Unambiguous gate line on stderr so callers never have to grep JSON severity
    # casing. Pair with the exit code: non-zero means HIGH findings exist.
    if high_count > 0:
        print(f"GATE: FAIL - {high_count} high-severity finding(s); {by_severity.get('advisory', 0)} advisory.",
              file=sys.stderr)
    else:
        print(f"GATE: PASS - 0 high-severity findings; {by_severity.get('advisory', 0)} advisory to review.",
              file=sys.stderr)
    sys.exit(1 if high_count > 0 else 0)


if __name__ == "__main__":
    main()
