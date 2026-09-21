#!/usr/bin/env python3
"""Redacted post-clean leak scan for prepared templates.

Surface coverage (per SKILL contract):

  Cell-level (openpyxl walk over every visible/hidden sheet):
    - Cell text values
    - Formula text (full text, not just broken-ref short-circuit)
    - Embedded numeric hardcodes inside formulas (magic-number leakage)
    - Nearby-label suspicious-deal-fact context

  Workbook-level (openpyxl):
    - Defined names (broken refs, external refs, deal-string in name)

  OOXML package-level (zipfile + regex/XPath):
    - xl/media/* parts (unapproved media)
    - xl/comments*.xml and xl/threadedComments/*.xml (text + author identity)
    - xl/persons/*.xml (author identity)
    - docProps/core.xml and docProps/app.xml (creator, last modified, company)
    - xl/worksheets/sheet*.xml: headerFooter elements, conditional-format formulas,
      data-validation list values, drawing alt text references
    - xl/charts/*.xml (chart titles, embedded chart data refs)
    - xl/pivotCache/*.xml and xl/pivotTables/*.xml (cached field data)
    - xl/customXml/* (deal-data caches)
    - xl/externalLinks/* (external workbook references)
    - xl/_rels/workbook.xml.rels (external relationships)

  Optional cross-check (--cross-check):
    - xlsx-skill workbook_search.py against deal strings and broken-formula tokens,
      so a discrepancy between this scan and the skill helper surfaces immediately.

Findings are redacted: only sheet/coordinate/finding-code/hash/value-class are stored.
Raw prior-deal values never appear in the output.
"""

from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from tp_common import (  # shared primitives; see tp_common.py
    find_excel_skill_root,
    is_normalization_scale,
)

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

import openpyxl

# Broadened from the prior version. Also matches PH/Penthouse, Loft, Live/Work, plan names
# that begin with letters followed by digits (A1, A1A, B2, C3, AA, etc.), and common
# alphanumeric codes used for unit plans. Anchored with start-of-string OR start-of-cell-text.
# Split into two tiers (v4.4). STRONG matches explicit unit-program vocabulary
# and is BLOCKING. PLANCODE matches bare alphanumeric plan codes (A1, B2, AA1)
# — a pattern that also matches quarter labels, footnote markers, and column
# codes — and is REVIEW severity: reported for the LLM to verify against the
# label column, never failing the scan on its own.
UNIT_ROW_STRONG_RE = re.compile(
    r"^("
    r"studio|stu|jr\.?\s*(?:1|one)?\b|"
    r"[1234]\s*(?:br|bd|bed|bedroom)\b|"
    r"[1234]\s*(?:b/?[ab])\b|"
    r"penthouse|ph\b|loft|live[- ]?work|"
    r"townhome|townhouse|th\b"
    r")\b",
    re.I,
)
UNIT_ROW_PLANCODE_RE = re.compile(
    r"^[a-z]{1,3}\s*[0-9]{1,3}[a-z]?\b",  # plan codes like A1, A1A, B2, C3, AA1
    re.I,
)

# v4.9. A unit-mix ROW LABEL names a unit type and nothing else — "Studio",
# "2 BR / 2 BA", "A1". A template CATEGORY HEADER pairs that unit type with a
# measure — "Studio — In-Place Rent", "1 BR Occupancy". The header is the
# template's own scaffolding: it carries no deal data, it is identical in every
# copy of the workbook, and blanking it deletes the row's meaning. Blocking on
# it made five fixed headers on our own Rent Comps tab fail the scan.
UNIT_ROW_METRIC_RE = re.compile(
    r"\b(?:rent|occupancy|vacancy|sf|square\s*feet|psf|count|units?|mix|"
    r"retention|turnover|absorption|concession|premium|growth|average|avg|"
    r"total|in[-\s]?place|asking|effective|net|gross|share|ratio|per\s*unit)\b",
    re.I,
)

# "T12" / "T-12" is universal CRE vocabulary that the bare plan-code pattern
# reads as plan "T" number "12". Never a unit plan.
PLANCODE_EXCLUDE_RE = re.compile(r"^t-?\s*(?:3|6|12|24)\b", re.I)

SUSPICIOUS_LABEL_RE = re.compile(
    r"\b(property|address|units?|unit mix|studio|[1234]\s*br|rentable|square feet|"
    r"sq\.?\s*ft|sf|parking|acre|rent roll|in[- ]?place|market rent|hard cost|"
    r"soft cost|budget|loan amount|purchase price|land cost|partner|lender|broker|"
    r"developer|borrower|sponsor|equity partner|asset manager|placement|origination)\b",
    re.I,
)

BROKEN_RE = re.compile(r"#REF!|#NAME\?", re.I)
EXTERNAL_REF_RE = re.compile(r"\[[^\]]+\.(?:xlsx|xlsm|xlsb|xls)\]", re.I)
NUM_LITERAL_RE = re.compile(r"(?<![A-Za-z0-9_])[-+]?\d{4,}(?:\.\d+)?(?![A-Za-z0-9_])")
# 4-digit minimum reduces noise from year/period/count constants like 12, 30, 365.
EXCLUDE_FORMULA_LITERALS = {
    "1900", "1904", "9999", "1000", "10000", "100000", "1000000",
}

# ── STRUCTURAL SURFACES (v4.8) ───────────────────────────────────────────────
#
# The existing deal-string test is a whole-string containment check: a deal
# string of "Modera Walsh" does not match "Market study on Walsh Ranch
# absorption". Real models re-use the deal's distinctive tokens in structural
# text — banner titles, tab names, checklist rows, a lender label — where the
# numeric heuristics never look and the whole-string test misses.
#
# So: derive distinctive TOKENS from the approved deal strings and match those
# on structural surfaces. Generic CRE vocabulary is excluded, because a deal
# named "Midtown Apartments" must not make the word "apartments" a leak.
GENERIC_DEAL_TOKEN_STOPWORDS = {
    "the", "and", "at", "of", "on", "in", "a", "an", "llc", "lp", "llp", "inc",
    "ltd", "co", "company", "holdings", "partners", "capital", "group", "fund",
    "apartments", "apartment", "residences", "residence", "villas", "lofts",
    "towers", "tower", "place", "park", "plaza", "commons", "crossing", "pointe",
    "point", "ridge", "creek", "landing", "station", "square", "village",
    "gardens", "garden", "heights", "manor", "estates", "club", "house",
    "north", "south", "east", "west", "old", "new", "phase", "one", "two",
    "property", "properties", "portfolio", "project", "development", "deal",
    "acquisition", "proforma", "pro", "forma", "model", "template", "analysis",
    "street", "st", "avenue", "ave", "road", "rd", "drive", "dr", "boulevard",
    "blvd", "lane", "ln", "court", "ct", "way", "circle", "cir", "suite",
}
DEAL_TOKEN_MIN_LEN = 4

# Checklist rows: "☐ Market study on ...", "[ ] Phase I", "- [ ] Tax appeal".
CHECKLIST_ROW_RE = re.compile(r"^\s*(?:[☐☑✓✔□■●○*\-•]|\[\s*[xX ]?\s*\])\s+\S")
# Banner titles: an ALL-CAPS text cell, which in every template convention we
# have seen is a sheet or section title rather than a data value.
BANNER_TITLE_RE = re.compile(r"^[A-Z0-9][A-Z0-9 \-&/(),.'’—–:|]{6,}$")

# A formula-baked deal amount: the formula carries cell references (so it is
# real model logic, not an arithmetic-only disguised constant) AND a large
# hardcoded dollar figure in its body. `=C6/91327500` is the shape — the prior
# deal's total cost welded into the LTC calculation.
CELL_REF_IN_FORMULA_RE = re.compile(r"(?<![A-Za-z0-9_$!])\$?[A-Z]{1,3}\$?\d{1,7}(?![A-Za-z0-9_(])")
FORMULA_BAKED_AMOUNT_MIN = 10_000

XML_TEXT_RE = re.compile(r">([^<]+)<")
HEADER_FOOTER_RE = re.compile(r"<headerFooter[^>]*?(?:/>|>(.*?)</headerFooter>)", re.S | re.I)
DATA_VALIDATION_FORMULA_RE = re.compile(r"<formula1>([^<]+)</formula1>", re.I | re.S)
CONDITIONAL_FORMAT_FORMULA_RE = re.compile(r"<formula>([^<]+)</formula>", re.I | re.S)
CHART_TITLE_RE = re.compile(r"<a:t>([^<]+)</a:t>", re.I | re.S)
CORE_PROP_RE = re.compile(
    r"<dc:(?:creator|title|subject|description)>([^<]+)</dc:(?:creator|title|subject|description)>"
    r"|<cp:(?:lastModifiedBy|category|keywords)>([^<]+)</cp:(?:lastModifiedBy|category|keywords)>",
    re.I,
)
APP_PROP_RE = re.compile(r"<(?:Company|Manager|Application)>([^<]+)</(?:Company|Manager|Application)>", re.I)
COMMENT_AUTHOR_RE = re.compile(r"<author>([^<]+)</author>", re.I)
PERSON_DISPLAYNAME_RE = re.compile(r'displayName="([^"]+)"', re.I)


def h(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return "sha256:" + hashlib.sha256(repr(value).encode("utf-8", "replace")).hexdigest()


def value_class(value: Any) -> str:
    if value is None:
        return "blank"
    if isinstance(value, str) and value.startswith("="):
        return "formula"
    if isinstance(value, str):
        return "text"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        v = abs(float(value))
        if v >= 1_000_000:
            return "large_number"
        if v >= 1_000:
            return "medium_number"
        if 0 <= v <= 1:
            return "rate_or_ratio"
        return "number"
    return type(value).__name__


def deal_tokens(deal_strings: list[str]) -> list[str]:
    """Distinctive lower-cased tokens from the approved deal strings.

    "Modera Walsh" -> ["modera", "walsh"], which is what catches "Walsh Ranch"
    in a checklist row. "The Midtown Apartments" -> ["midtown"], because "the"
    and "apartments" are generic and would flag half of every CRE template.
    """
    out: list[str] = []
    for s in deal_strings:
        for tok in re.split(r"[^A-Za-z0-9]+", str(s).lower()):
            if len(tok) < DEAL_TOKEN_MIN_LEN:
                continue
            if tok in GENERIC_DEAL_TOKEN_STOPWORDS:
                continue
            if tok.isdigit():
                continue
            if tok not in out:
                out.append(tok)
    return out


def structural_surface_kind(ws, cell) -> str | None:
    """Classify a text cell as a structural surface, or None if it is ordinary
    content. Structural surfaces carry the template's own scaffolding — they are
    never cleared by the value-clearing pipeline, so a deal name parked in one
    survives an otherwise clean run."""
    v = cell.value
    if not isinstance(v, str) or not v.strip():
        return None
    s = v.strip()
    if CHECKLIST_ROW_RE.match(s):
        return "checklist_row"
    if cell.row <= 3 and cell.column <= 3:
        return "banner_title"
    if BANNER_TITLE_RE.match(s):
        return "banner_title"
    # A label cell: text with a value to its right, i.e. it names something.
    right = ws.cell(cell.row, cell.column + 1).value
    if right not in (None, ""):
        return "label_cell"
    return None


def scan_sheet_names(wb, deal_strings: list[str], tokens: list[str]) -> list[dict]:
    """Tab names. The openpyxl cell walk never sees them and neither does the
    package-parts scan (they live in xl/workbook.xml), so a sheet named after
    the prior deal survived every existing surface — while being the single most
    visible thing in the delivered file."""
    findings: list[dict] = []
    deal_strings_lower = [s.lower() for s in deal_strings if s]
    for ws in wb.worksheets:
        title = ws.title
        low = title.lower()
        matched = next((ds for ds in deal_strings_lower if ds and ds in low), None)
        if matched:
            findings.append({
                "location": f"sheet:{title}",
                "finding": "deal_string_in_sheet_name",
                "value_class": "sheet_name",
                "hash": h(title),
                "text": title[:80],
                "sheet_state": ws.sheet_state,
            })
            continue
        tok = next((t for t in tokens if t in low), None)
        if tok:
            findings.append({
                "location": f"sheet:{title}",
                "finding": "deal_token_in_sheet_name",
                "value_class": "sheet_name",
                "hash": h(title),
                "text": title[:80],
                "matched_token": tok,
                "sheet_state": ws.sheet_state,
            })
    return findings


def nearby_text(ws, row: int, col: int) -> str:
    """Label context for a cell: up to 3 cells left and 3 above. The cell
    ITSELF is excluded (v4.4) — including it made every text label cell
    self-match SUSPICIOUS_LABEL_RE and flag itself as its own deal-fact
    context, which produced a blocking finding per label on clean templates."""
    vals = []
    for dc in range(-3, 0):
        if col + dc >= 1:
            vals.append(ws.cell(row, col + dc).value)
    for dr in range(-3, 0):
        if row + dr >= 1:
            vals.append(ws.cell(row + dr, col).value)
    return " | ".join(str(v) for v in vals if v not in (None, ""))[:300]


def load_decisions(path: str | None) -> dict:
    if not path:
        return {}
    return json.loads(Path(path).read_text(encoding="utf-8"))


def defined_name_items(wb) -> list[tuple[str, Any]]:
    try:
        return list(wb.defined_names.items())
    except Exception:
        pass
    try:
        return [(d.name, d) for d in wb.defined_names.definedName]
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


# Well-known install locations differ by surface:
    #   claude.ai web/app        : /mnt/skills/public/xlsx
    #   Claude desktop / Cowork  : ~/.claude/skills/xlsx  (under /sessions/<id>/mnt)
    known_candidates: list[Path] = [
        Path("/mnt/skills/public/xlsx"),
        Path.home() / ".claude" / "skills" / "xlsx",
    ]
    try:
        known_candidates += sorted(Path("/sessions").glob("*/mnt/.claude/skills/xlsx"))
    except Exception:
        pass
    for known in known_candidates:
        if (known / "scripts" / "recalc.py").exists():
            return known
    return None


def cross_check_via_workbook_search(workbook: str, deal_strings: list[str], skill_root: Path) -> dict:
    """Use the xlsx-skill workbook_search.py as a second opinion. Returns dict of
    pattern → match-count. Discrepancies between this scan's findings and the helper's
    hits should be investigated."""
    helper = skill_root / "scripts" / "workbook_search.py"
    if not helper.exists():
        return {"status": "helper_missing"}
    out: dict = {"status": "ran", "patterns": {}}
    patterns: list[tuple[str, str]] = [
        ("broken_ref", r"#REF!"),
        ("broken_name", r"#NAME\?"),
        ("external_ref_marker", r"\[[^\]]+\.(xlsx|xlsm|xlsb|xls)\]"),
    ]
    for ds in deal_strings[:10]:  # cap to keep cost predictable
        patterns.append((f"deal_string:{h(ds)}", re.escape(ds)))
    for label, pattern in patterns:
        proc = subprocess.run(
            [sys.executable, str(helper), workbook, "--pattern", pattern, "--in", "both", "--limit", "200"],
            capture_output=True, text=True, timeout=60,
        )
        out["patterns"][label] = {
            "returncode": proc.returncode,
            "stdout_tail": (proc.stdout or "")[-200:],
        }
    return out


def scan_cells_and_formulas(wb, deal_strings: list[str], tokens: list[str] | None = None) -> list[dict]:
    findings: list[dict] = []
    deal_strings_lower = [s.lower() for s in deal_strings if s]
    tokens = tokens or []
    for ws in wb.worksheets:
        if ws.title == "_PreparationAudit":
            # Our own audit artifact: contains classification hashes that the
            # plan-code heuristic misreads (sha256:... matches letter+digit).
            # The audit sheet is verified by its own rule (no raw prior values)
            # in prepare_clean_template_v2, not by the cell heuristics.
            continue
        max_row = min(ws.max_row or 0, 8000)
        max_col = min(ws.max_column or 0, 250)
        for row in ws.iter_rows(min_row=1, max_row=max_row, min_col=1, max_col=max_col):
            for cell in row:
                value = cell.value
                if value in (None, ""):
                    continue
                coord = f"{ws.title}!{cell.coordinate}"
                if isinstance(value, str) and value.startswith("="):
                    formula = value
                    fl = formula.lower()
                    if BROKEN_RE.search(formula):
                        findings.append({"cell": coord, "finding": "broken_or_external_formula", "value_class": "formula", "hash": h(formula), "sheet_state": ws.sheet_state})
                    if EXTERNAL_REF_RE.search(formula):
                        findings.append({"cell": coord, "finding": "external_workbook_reference_in_formula", "value_class": "formula", "hash": h(formula), "sheet_state": ws.sheet_state})
                    # Deal-string in formula text (e.g., string literal or sheet name).
                    for ds in deal_strings_lower:
                        if ds and ds in fl:
                            findings.append({"cell": coord, "finding": "deal_string_in_formula", "value_class": "formula", "hash": h(formula), "sheet_state": ws.sheet_state})
                            break
                    # Magic-number leakage: numeric literals >= 1000 inside formulas often
                    # encode prior-deal values (loan amounts, prices, costs). Skip well-known
                    # constants and small integers.
                    literals = NUM_LITERAL_RE.findall(formula)
                    suspicious = [n for n in literals if n not in EXCLUDE_FORMULA_LITERALS]
                    if suspicious:
                        # v4.8 split. A formula that carries cell references is
                        # live model logic; a large dollar figure welded into its
                        # body is the prior deal's number driving this template's
                        # arithmetic forever. That is a different, worse defect
                        # than the arithmetic-only disguised constant this code
                        # used to lump it with — and it cannot be auto-fixed,
                        # because extracting the constant to an input cell
                        # changes the model's logic. It blocks instead.
                        body = CELL_REF_IN_FORMULA_RE.sub("", formula)
                        baked = [n for n in NUM_LITERAL_RE.findall(body)
                                 if n not in EXCLUDE_FORMULA_LITERALS
                                 and abs(float(n)) >= FORMULA_BAKED_AMOUNT_MIN]
                        has_refs = bool(CELL_REF_IN_FORMULA_RE.search(formula))
                        # v4.9. Range bounds inside a clamp are a normalization
                        # scale, not a deal amount, and blocking on them meant
                        # the skill could never certify our own house template.
                        # Reported, not dropped: a genuinely odd one stays
                        # visible as info. Tested against the whole clamp
                        # construct, so the same shape below the magnitude floor
                        # lands here too rather than under a review code.
                        scale_literals = [n for n in NUM_LITERAL_RE.findall(body)
                                          if n not in EXCLUDE_FORMULA_LITERALS]
                        if has_refs and is_normalization_scale(formula, scale_literals):
                            findings.append({
                                "cell": coord,
                                "finding": "formula_scale_constant",
                                "value_class": "formula",
                                "hash": h(formula),
                                "scale_literal_count": len(scale_literals),
                                "distinct_scale_literals": len({n.lstrip("+") for n in scale_literals}),
                                "sheet_state": ws.sheet_state,
                            })
                        elif has_refs and baked:
                            findings.append({
                                "cell": coord,
                                "finding": "formula_baked_deal_amount",
                                "value_class": "formula",
                                "hash": h(formula),
                                "baked_literal_count": len(baked),
                                "baked_magnitudes": sorted({len(n.split(".")[0].lstrip("+-")) for n in baked}),
                                "sheet_state": ws.sheet_state,
                            })
                        else:
                            findings.append({
                                "cell": coord,
                                "finding": "formula_embedded_hardcoded_numeric",
                                "value_class": "formula",
                                "hash": h(formula),
                                "literal_count": len(suspicious),
                                "sheet_state": ws.sheet_state,
                            })
                    continue

                lower = str(value).lower()
                if any(ds and ds in lower for ds in deal_strings_lower):
                    matched = next(ds for ds in deal_strings_lower if ds and ds in lower)
                    finding = {"cell": coord, "finding": "deal_string_retained", "value_class": value_class(value), "hash": h(value), "matched_deal_string": matched, "sheet_state": ws.sheet_state}
                    surface = structural_surface_kind(ws, cell)
                    if surface:
                        finding["structural_surface"] = surface
                        finding["text"] = str(value)[:120]
                    findings.append(finding)
                    continue

                # Distinctive deal TOKEN on a structural surface (v4.8): the tab
                # title, the banner, a checklist row, a label. The whole-string
                # test above misses these because real models reuse a fragment
                # of the deal name ("Walsh Ranch" from "Modera Walsh"), and no
                # value-clearing pass touches structural text.
                if isinstance(value, str) and tokens:
                    surface = structural_surface_kind(ws, cell)
                    if surface:
                        tok = next((t for t in tokens if t in lower), None)
                        if tok:
                            findings.append({
                                "cell": coord,
                                "finding": "deal_token_in_structural_text",
                                "value_class": "text",
                                "hash": h(value),
                                "text": str(value)[:120],
                                "matched_token": tok,
                                "structural_surface": surface,
                                "sheet_state": ws.sheet_state,
                            })
                            continue
                if isinstance(value, str) and UNIT_ROW_STRONG_RE.search(value.strip()):
                    # Reported, not dropped: a header that turns out to carry a
                    # deal fact is still visible, it just does not block.
                    code = ("unit_mix_metric_header"
                            if UNIT_ROW_METRIC_RE.search(value)
                            else "unit_mix_or_program_row_label_retained")
                    findings.append({"cell": coord, "finding": code, "value_class": "text", "hash": h(value), "text": str(value)[:80], "sheet_state": ws.sheet_state})
                    continue
                if (isinstance(value, str)
                        and UNIT_ROW_PLANCODE_RE.search(value.strip())
                        and not PLANCODE_EXCLUDE_RE.search(value.strip())):
                    findings.append({"cell": coord, "finding": "possible_plan_code_label", "value_class": "text", "hash": h(value), "text": str(value)[:80], "sheet_state": ws.sheet_state})
                    continue
                context = nearby_text(ws, cell.row, cell.column)
                # Label-on-label suppression (v4.4): a text cell whose own value
                # matches the generic deal-fact vocabulary ("Units", "Purchase
                # Price", "Address") is itself a template label sitting under
                # other labels — structure, not leakage. Name-like text (a
                # property or partner name) does NOT match the generic vocab
                # and still gets flagged.
                if (isinstance(value, str)
                        and SUSPICIOUS_LABEL_RE.search(value)
                        and not any(ch.isdigit() for ch in value)):
                    continue
                if SUSPICIOUS_LABEL_RE.search(context) and value_class(value) in {"large_number", "medium_number", "number", "text"}:
                    finding = {
                        "cell": coord,
                        "finding": "suspicious_deal_fact_context",
                        "value_class": value_class(value),
                        "hash": h(value),
                        # Label context in CLEAR TEXT (v4.4): these are template
                        # labels, not deal values — triage needs them readable.
                        # The cell VALUE stays hashed unless it is itself text
                        # (text near a deal-fact label is usually a name and the
                        # LLM must read it to judge). Numeric values: hash only.
                        "label_context": context[:120],
                        "sheet_state": ws.sheet_state,
                    }
                    if isinstance(value, str):
                        finding["text"] = str(value)[:80]
                    findings.append(finding)
    return findings


def load_table_region_cells(path: str | None) -> set[tuple[str, int, int]]:
    """Build the set of (sheet, row, col) cells that fall inside any detected
    runtime-input table region (tall OR wide). Used as a regression detector:
    any non-blank, non-formula cell remaining inside such a region after
    Phase 2 cleanup is a leak — the cleanup pipeline failed to clear it.

    This is distinct from the suspicious_deal_fact_context heuristic, which
    only catches numeric cells near deal-fact labels. A wide region (comp
    table) is mostly text cells holding property names and city/state strings,
    none of which the heuristic detects.
    """
    if not path:
        return set()
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return set()
    try:
        from openpyxl.utils import column_index_from_string
    except Exception:
        return set()
    cells: set[tuple[str, int, int]] = set()
    for region in data.get("regions", []):
        sheet = region["sheet"]
        kind = region.get("region_kind", "tall")
        if kind == "wide":
            try:
                first_c = column_index_from_string(region["first_data_col"])
                last_c = column_index_from_string(region["last_data_col"])
            except Exception:
                continue
            for r in region.get("belong_rows", []):
                for c in range(first_c, last_c + 1):
                    cells.add((sheet, r, c))
        else:
            try:
                col_idx = column_index_from_string(region["value_col"])
            except Exception:
                continue
            for r in region.get("belong_rows", []):
                cells.add((sheet, r, col_idx))
    return cells


def load_region_exception_cells(path: str | None) -> set[str]:
    if not path:
        return set()
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return set()
    return {e["cell"] for e in data.get("cells") or []
            if isinstance(e, dict) and e.get("approved_region_exception") and e.get("cell")}


def scan_table_region_residue(wb, region_cells: set[tuple[str, int, int]], exception_cells: set[str] = frozenset()) -> list[dict]:
    """Regression scan: every cell inside a detected table region should be
    blank or a formula in a properly cleaned template. Anything else — a text
    string, a number — is a leak the Phase 2 force-clear missed.
    """
    if not region_cells:
        return []
    findings: list[dict] = []
    for ws in wb.worksheets:
        for (sheet, row, col) in region_cells:
            if sheet != ws.title:
                continue
            try:
                v = ws.cell(row, col).value
            except Exception:
                continue
            if v in (None, ""):
                continue
            if isinstance(v, str) and v.startswith("="):
                # Formulas inside a region are unusual but not necessarily leaks
                # (the LLM may have authored a structural formula). Flag as info,
                # not blocking.
                findings.append({
                    "cell": f"{ws.title}!{ws.cell(row, col).coordinate}",
                    "finding": "formula_in_detected_table_region",
                    "value_class": "formula",
                    "hash": h(v),
                    "sheet_state": ws.sheet_state,
                })
                continue
            coord = f"{ws.title}!{ws.cell(row, col).coordinate}"
            if coord in exception_cells:
                findings.append({
                    "cell": coord,
                    "finding": "approved_region_exception_preserved",
                    "value_class": value_class(v),
                    "hash": h(v),
                    "sheet_state": ws.sheet_state,
                })
                continue
            findings.append({
                "cell": coord,
                "finding": "text_or_value_in_detected_table_region",
                "value_class": value_class(v),
                "hash": h(v),
                "sheet_state": ws.sheet_state,
            })
    return findings


def load_gated_regions(path: str | None) -> tuple[set[str], dict[str, dict]]:
    """Gated cells and toggle controls from table_regions.json — the regression
    side of the toggle-aware clearing rule."""
    if not path:
        return set(), {}
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return set(), {}
    gated: set[str] = set()
    for region in data.get("gated_regions", []):
        gated.update(region.get("gated_cells", []))
    toggles = {t["cell"]: t for t in data.get("toggle_cells", []) if isinstance(t, dict) and t.get("cell")}
    return gated, toggles


def scan_gated_region_residue(wb, gated_cells: set[str], toggle_cells: dict[str, dict],
                              exception_cells: set[str] = frozenset()) -> list[dict]:
    """Two-sided regression check on toggle-aware clearing:

    - a value still sitting in a gated region means the clearing pass believed
      the toggle instead of the rule, and
    - a missing toggle control means the clearing pass took the control with it,
      leaving the user a template whose mode switch is gone.
    """
    findings: list[dict] = []
    for coord_full in sorted(gated_cells):
        if coord_full in exception_cells:
            findings.append({"cell": coord_full, "finding": "approved_region_exception_preserved", "value_class": "exempted"})
            continue
        sheet, _, coord = coord_full.partition("!")
        if sheet not in wb.sheetnames:
            continue
        value = wb[sheet][coord].value
        if value in (None, ""):
            continue
        if isinstance(value, str) and value.startswith("="):
            continue          # a formula here is model logic, not residue
        findings.append({
            "cell": coord_full,
            "finding": "value_in_toggle_gated_region",
            "value_class": value_class(value),
            "hash": h(value),
            "sheet_state": wb[sheet].sheet_state,
        })
    for coord_full, meta in sorted(toggle_cells.items()):
        sheet, _, coord = coord_full.partition("!")
        if sheet not in wb.sheetnames:
            findings.append({"cell": coord_full, "finding": "toggle_control_sheet_missing", "value_class": "toggle"})
            continue
        if wb[sheet][coord].value in (None, ""):
            findings.append({
                "cell": coord_full,
                "finding": "toggle_control_cleared",
                "value_class": "toggle",
                "toggle_label": str(meta.get("label", ""))[:80],
            })
    return findings


def scan_defined_names(wb, deal_strings: list[str]) -> list[dict]:
    findings: list[dict] = []
    deal_strings_lower = [s.lower() for s in deal_strings if s]
    for name, defn in defined_name_items(wb):
        text = attr_text(defn)
        if "#REF!" in text:
            findings.append({"location": f"defined_name:{name}", "finding": "broken_defined_name", "hash": h(text)})
        if EXTERNAL_REF_RE.search(text):
            findings.append({"location": f"defined_name:{name}", "finding": "external_defined_name", "hash": h(text)})
        if any(ds in str(name).lower() for ds in deal_strings_lower):
            findings.append({"location": f"defined_name:{name}", "finding": "deal_string_in_defined_name", "hash": h(name)})
    return findings


def _scan_text_for_strings(text: str, deal_strings_lower: list[str]) -> bool:
    if not deal_strings_lower:
        return False
    lower = text.lower()
    return any(ds in lower for ds in deal_strings_lower)


def scan_package_parts(workbook: str, allowed_media: set[str], deal_strings: list[str]) -> list[dict]:
    """Scan OOXML package parts for surfaces that openpyxl cell-walk doesn't reach."""
    findings: list[dict] = []
    deal_strings_lower = [s.lower() for s in deal_strings if s]

    with zipfile.ZipFile(workbook) as zf:
        names = zf.namelist()

        # Media (kept from prior version, with normalization)
        for part in names:
            if not part.startswith("xl/media/"):
                continue
            normalized = "/" + part
            if normalized in allowed_media or part in allowed_media:
                continue
            findings.append({"location": part, "finding": "unapproved_media_remaining", "value_class": "media"})

        # Document properties: creator, lastModifiedBy, company, title/subject/description
        for prop_part in ("docProps/core.xml", "docProps/app.xml"):
            if prop_part not in names:
                continue
            try:
                text = zf.read(prop_part).decode("utf-8", "replace")
            except Exception:
                continue
            for match in CORE_PROP_RE.finditer(text):
                content = match.group(1) or match.group(2) or ""
                if content.strip():
                    findings.append({"location": prop_part, "finding": "document_property_present", "hash": h(content)})
            for match in APP_PROP_RE.finditer(text):
                content = match.group(1) or ""
                if content.strip():
                    findings.append({"location": prop_part, "finding": "app_property_present", "hash": h(content)})

        # Comments and threaded comments + person identity
        for part in names:
            if not (part.startswith("xl/comments") or part.startswith("xl/threadedComments/") or part.startswith("xl/persons/")):
                continue
            try:
                text = zf.read(part).decode("utf-8", "replace")
            except Exception:
                continue
            for match in COMMENT_AUTHOR_RE.finditer(text):
                author = match.group(1) or ""
                if author.strip() and author.strip().lower() != "anonymous":
                    findings.append({"location": part, "finding": "comment_author_identity", "hash": h(author)})
            for match in PERSON_DISPLAYNAME_RE.finditer(text):
                name = match.group(1) or ""
                if name.strip() and name.strip().lower() != "anonymous":
                    findings.append({"location": part, "finding": "person_display_name_identity", "hash": h(name)})
            # Comment text bodies
            for match in XML_TEXT_RE.finditer(text):
                body = match.group(1)
                if _scan_text_for_strings(body, deal_strings_lower):
                    findings.append({"location": part, "finding": "deal_string_in_comment", "hash": h(body)})
                if UNIT_ROW_STRONG_RE.search(body):
                    findings.append({"location": part, "finding": "unit_mix_label_in_comment", "hash": h(body)})

        # Worksheet XML: headerFooter, data validation list, conditional formatting formulas
        for part in names:
            if not (part.startswith("xl/worksheets/sheet") and part.endswith(".xml")):
                continue
            try:
                text = zf.read(part).decode("utf-8", "replace")
            except Exception:
                continue
            for match in HEADER_FOOTER_RE.finditer(text):
                content = match.group(1) or ""
                if content.strip():
                    findings.append({"location": part, "finding": "headerFooter_present", "hash": h(content)})
                    if _scan_text_for_strings(content, deal_strings_lower):
                        findings.append({"location": part, "finding": "deal_string_in_headerFooter", "hash": h(content)})
            for match in DATA_VALIDATION_FORMULA_RE.finditer(text):
                f = match.group(1) or ""
                if BROKEN_RE.search(f) or EXTERNAL_REF_RE.search(f):
                    findings.append({"location": part, "finding": "broken_or_external_data_validation", "hash": h(f)})
                if _scan_text_for_strings(f, deal_strings_lower):
                    findings.append({"location": part, "finding": "deal_string_in_data_validation", "hash": h(f)})
            for match in CONDITIONAL_FORMAT_FORMULA_RE.finditer(text):
                f = match.group(1) or ""
                if BROKEN_RE.search(f) or EXTERNAL_REF_RE.search(f):
                    findings.append({"location": part, "finding": "broken_or_external_conditional_format", "hash": h(f)})
                # CF formulas with embedded large numeric literals are a common deal-fact leak
                # (e.g., highlight cells > prior-loan-amount).
                literals = NUM_LITERAL_RE.findall(f)
                suspicious = [n for n in literals if n not in EXCLUDE_FORMULA_LITERALS]
                if suspicious:
                    findings.append({"location": part, "finding": "conditional_format_embedded_numeric", "hash": h(f), "literal_count": len(suspicious)})

        # Chart titles and embedded chart text
        for part in names:
            if not (part.startswith("xl/charts/") and part.endswith(".xml")):
                continue
            try:
                text = zf.read(part).decode("utf-8", "replace")
            except Exception:
                continue
            for match in CHART_TITLE_RE.finditer(text):
                title = match.group(1) or ""
                if _scan_text_for_strings(title, deal_strings_lower):
                    findings.append({"location": part, "finding": "deal_string_in_chart_text", "hash": h(title)})
                if UNIT_ROW_STRONG_RE.search(title):
                    findings.append({"location": part, "finding": "unit_mix_label_in_chart_text", "hash": h(title)})

        # Pivot caches: any cached field can hold prior-deal data.
        for part in names:
            if not (part.startswith("xl/pivotCache/") and part.endswith(".xml")):
                continue
            try:
                text = zf.read(part).decode("utf-8", "replace")
            except Exception:
                continue
            if _scan_text_for_strings(text, deal_strings_lower):
                findings.append({"location": part, "finding": "deal_string_in_pivot_cache", "hash": h(text[:500])})
            # Cached numeric fields with very large values are also suspicious.
            literals = NUM_LITERAL_RE.findall(text)
            suspicious = [n for n in literals if n not in EXCLUDE_FORMULA_LITERALS and len(n) >= 6]
            if suspicious:
                findings.append({"location": part, "finding": "pivot_cache_large_numeric_present", "literal_count": len(suspicious)})

        # Custom XML: deal-data caches commonly embedded by add-ins.
        for part in names:
            if not part.startswith("customXml/"):
                continue
            findings.append({"location": part, "finding": "custom_xml_part_present"})

        # External links: any retained external link is a cleanup violation.
        for part in names:
            if part.startswith("xl/externalLinks/") or part == "xl/connections.xml":
                findings.append({"location": part, "finding": "external_link_or_connection_present"})

        # workbook.xml.rels: external relationships (file:// or http:// targets)
        rels_part = "xl/_rels/workbook.xml.rels"
        if rels_part in names:
            try:
                text = zf.read(rels_part).decode("utf-8", "replace")
            except Exception:
                text = ""
            for match in re.finditer(r'Target="([^"]+)"\s+TargetMode="External"', text):
                findings.append({"location": rels_part, "finding": "external_relationship_present", "hash": h(match.group(1))})

    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workbook")
    parser.add_argument("--decisions-json")
    parser.add_argument(
        "--preserved-defaults",
        help="Optional path to preserved_defaults.json. Cells flagged "
             "'approved_region_exception': true are user-approved scalar "
             "defaults inside detected regions — the residue check exempts "
             "them (reported as info: approved_region_exception_preserved) "
             "instead of flagging blocking residue. The manifest must still "
             "account for them as protected defaults (manifest_lint leakage "
             "check enforces that side).")
    parser.add_argument("--out", required=True)
    parser.add_argument(
        "--table-regions",
        help="Optional path to table_regions.json from candidate_mapping.py. "
             "Enables a regression check: any non-blank value remaining inside "
             "a detected table region after Phase 2 cleanup is flagged as a leak.",
    )
    parser.add_argument(
        "--cross-check",
        action="store_true",
        help="Run a second-opinion scan via the xlsx-skill workbook_search.py if the skill root is available.",
    )
    args = parser.parse_args()

    decisions = load_decisions(args.decisions_json)
    allowed_media = set(decisions.get("template_owner_logo_media_paths_to_keep", []))
    deal_strings = [s for s in decisions.get("deal_strings", []) if s]
    table_region_cells = load_table_region_cells(args.table_regions)
    gated_cells, toggle_cells = load_gated_regions(args.table_regions)
    exception_cells = load_region_exception_cells(args.preserved_defaults)
    tokens = deal_tokens(deal_strings)

    wb = openpyxl.load_workbook(args.workbook, data_only=False, keep_links=False)
    findings: list[dict] = []
    findings.extend(scan_cells_and_formulas(wb, deal_strings, tokens))
    findings.extend(scan_sheet_names(wb, deal_strings, tokens))
    findings.extend(scan_defined_names(wb, deal_strings))
    findings.extend(scan_package_parts(args.workbook, allowed_media, deal_strings))
    if table_region_cells:
        findings.extend(scan_table_region_residue(wb, table_region_cells, exception_cells))
    if gated_cells or toggle_cells:
        findings.extend(scan_gated_region_residue(wb, gated_cells, toggle_cells, exception_cells))

    cross_check = None
    if args.cross_check:
        skill_root = find_excel_skill_root()
        if skill_root is None:
            cross_check = {"status": "skipped_no_skill_root"}
        else:
            cross_check = cross_check_via_workbook_search(args.workbook, deal_strings, skill_root)

    # Severity: any finding that touches required deliverable surfaces is blocking. The few
    # informational categories (document_property_present without deal-string content, the bare
    # custom_xml_part_present, etc.) are reported but kept so the manifest's leak_scan section
    # has full visibility.
    # Three tiers (v4.4):
    #   blocking — deterministic deal-data or integrity leaks. The scan FAILS.
    #   review   — heuristic context hits the LLM must verify cell-by-cell
    #              against the workbook; reported, never failing on their own.
    #   info     — everything else (properties, bare custom XML, etc.).
    # Previous behavior treated every heuristic hit as blocking, which on real
    # institutional models produced thousands of label false-positives and made
    # "return to remediation until the scan passes" literally unsatisfiable.
    blocking_codes = {
        "broken_or_external_formula",
        "external_workbook_reference_in_formula",
        "deal_string_in_formula",
        "deal_string_retained",
        "unit_mix_or_program_row_label_retained",
        "broken_defined_name",
        "external_defined_name",
        "deal_string_in_defined_name",
        "unapproved_media_remaining",
        "deal_string_in_comment",
        "unit_mix_label_in_comment",
        "deal_string_in_headerFooter",
        "broken_or_external_data_validation",
        "deal_string_in_data_validation",
        "broken_or_external_conditional_format",
        "deal_string_in_chart_text",
        "unit_mix_label_in_chart_text",
        "deal_string_in_pivot_cache",
        "external_link_or_connection_present",
        "external_relationship_present",
        "text_or_value_in_detected_table_region",
        # v4.8 — structural surfaces and toggle-gated regions. Each of these is
        # deterministic (an approved deal string or one of its distinctive
        # tokens on a surface the user reads, or a value in a region the
        # clearing pass was required to empty), so each fails the scan.
        "deal_string_in_sheet_name",
        "deal_token_in_sheet_name",
        "deal_token_in_structural_text",
        "value_in_toggle_gated_region",
        "toggle_control_cleared",
        "toggle_control_sheet_missing",
        # A formula whose body welds a prior-deal dollar amount into live model
        # logic. Blocking because it cannot be resolved by clearing: the fix
        # changes the model, so it goes back to the user as a decision.
        "formula_baked_deal_amount",
    }
    review_codes = {
        "suspicious_deal_fact_context",
        "possible_plan_code_label",
        "formula_embedded_hardcoded_numeric",
        "conditional_format_embedded_numeric",
        "pivot_cache_large_numeric_present",
    }
    for f in findings:
        code = f.get("finding")
        f["severity"] = ("blocking" if code in blocking_codes
                         else "review" if code in review_codes
                         else "info")
    blocking_count = sum(1 for f in findings if f["severity"] == "blocking")
    review_count = sum(1 for f in findings if f["severity"] == "review")
    informational_count = len(findings) - blocking_count - review_count
    status = "passed" if blocking_count == 0 else "failed"

    result = {
        "workbook": str(args.workbook),
        "status": status,
        "passed": blocking_count == 0,
        "finding_count": len(findings),
        "blocking_count": blocking_count,
        "review_count": review_count,
        "informational_count": informational_count,
        "severity_note": (
            "blocking findings fail the scan and force re-remediation; review "
            "findings are heuristic context hits the LLM must verify against "
            "the workbook before sign-off (verification recorded in the "
            "manifest leak_scan.remaining_findings); info findings are "
            "recorded for visibility only."
        ),
        "findings": findings[:5000],
        "cross_check": cross_check,
        "raw_prior_values_stored": False,
    }
    Path(args.out).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"status": status, "out": args.out, "blocking": blocking_count, "review": review_count, "informational": informational_count}, indent=2))
    return 0 if blocking_count == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())

# END post_clean_leak_scan.py
