# Template Preparation - Scripts v4.6

This file packages deterministic helper scripts for the RealAI template-preparation skill. Extract each `~~~python` block to `tp_scripts/<filename>` before running. Do not extract these scripts into the Excel skill's `scripts/` directory.

The SKILL file is the controlling execution contract. These scripts provide mechanical evidence, execute approved cleanup, lint the manifest, and perform write/recalc verification.

## Required extraction rule

- Every required script must contain its `# END <filename>` sentinel after extraction.
- If a required script is missing, truncated, or missing its sentinel, stop with `blocked_script_extraction_failure`.
- Do not recreate a truncated script from memory.
- Extract `tp_common.py` FIRST. The other scripts import shared primitives from it (`from tp_common import ...`). It must be present in `tp_scripts/` before any other script runs, and it carries its own `# END tp_common.py` sentinel.

## Important Phase 3 execution rule

- Do not copy, recreate, or edit the Excel skill's `scripts/recalc.py`.
- Do not create a local `tp_scripts/recalc.py`.
- Do not check for calculation-engine binaries directly. Do not call `which libreoffice` or `soffice` from any tp_script.
- Do not run Phase 3 from inside `tp_scripts`.
- Do not pass `--recalc-script` (deprecated, removed in v3).
- `sniff_test.py` invokes the Excel skill helper as `cd <excel_skill_root> && python scripts/recalc.py <absolute_workbook> <timeout_seconds>`. Note that `recalc.py` accepts `[timeout_seconds]` as optional with a 30s default; sniff_test always passes an explicit value.

## Known recalc-engine limitation: dynamic-array functions

LibreOffice may return `#NAME?` for modern Excel dynamic-array functions
(`_xlfn._xlws.SORT`, `FILTER`, `XLOOKUP`, `LAMBDA`, ...). This applies to any
workbook — xlsx or converted xlsm — and is an engine coverage gap, NOT a
preparation defect. `sniff_test.py`'s baseline-vs-after comparison prevents
these from being misread as regressions, but an output cell whose chain
depends on a dynamic-array function cannot be L3-verified: document it as a
`ready_with_limitations` sub-reason rather than chasing the `#NAME?`.

## Excel skill root resolution

Set `REALAI_XLSX_SKILL_ROOT=/absolute/path/to/skills/xlsx` once in your environment. All scripts that need the xlsx skill (sniff_test, prepare_clean_template_v2's normalization step, post_clean_leak_scan's --cross-check, post_clean_package_surgery) will use it. The filesystem-walk fallback is provided for convenience but is fragile — explicit is better.

## Manifest format contract

The manifest MUST be a `.md` file containing exactly one fenced YAML block:

~~~markdown
# My Template Manifest

```yaml
template_id: my_template_v1
manifest_version: 3
status: pending
cells:
  capital.entry_price:
    semantic_role: acquisition_price
    writes: [{cell: "Pro Forma!E8"}]
    ...
tables:
  unit_mix:
    sheet: "Operating Assumptions"
    ...
outputs:
  year1_noi:
    cell: "Returns!E20"
    ...
```
~~~

Do NOT produce prose-style markdown manifests with header tables and embedded JSON output blocks. The lint, preflight, and sniff tools will fail with `manifest_not_machine_readable` on those.

## Write-only preflight vs sniff

- `verify_write_preflight.py` confirms mapped values can be written. It is not production verification.
- `sniff_test.py` writes the payload, calls the Excel-skill `recalc.py` from the Excel skill root, reads outputs, and returns the production-readiness result.

## Recommended sequence (v4.5)

~~~bash
mkdir -p tp_scripts
# extract all python blocks below into tp_scripts/<filename>
# verify each extracted script contains its '# END <filename>' sentinel
# tp_common.py holds shared primitives (manifest loader, cell-ref parsing,
# skill-root resolver, value helpers). Extract it first; every other script
# imports from it via a sys.path shim. No standalone invocation.

# Point the pipeline at the xlsx skill once. The mount path differs by surface:
#   claude.ai web/app        : /mnt/skills/public/xlsx
#   Claude desktop / Cowork  : ~/.claude/skills/xlsx
# Export whichever one actually contains scripts/recalc.py:
export REALAI_XLSX_SKILL_ROOT="$(for d in /mnt/skills/public/xlsx "$HOME/.claude/skills/xlsx" /sessions/*/mnt/.claude/skills/xlsx; do [ -f "$d/scripts/recalc.py" ] && echo "$d" && break; done)"
# (Scripts now also check all of these as built-in fallbacks, but explicit is better.)

# Step 0 — xlsm gate (ONLY when the upload is .xlsm or triage reports
# requires_xlsm_gate). Analyzes the VBA project without executing it, scans it
# for deal-string leakage, and emits a macro-stripped .xlsx when the proof
# obligations hold (no UDFs referenced by formulas, no auto-exec). verdict
# routing: strippable -> continue on model_converted.xlsx and carry the
# report's removed_macro_inventory into _PreparationAudit; needs_review ->
# present the Function/event inventory via ask_user, then re-run with
# --approve-strip; not_strippable -> refuse with the report's reason.
# python tp_scripts/xlsm_triage_convert.py model.xlsm \
#     --out xlsm_report.json \
#     --convert-out model_converted.xlsx

# Phase 1 — analysis and source-of-truth classification
python tp_scripts/initial_triage.py model.xlsx --out triage.json
python tp_scripts/extract_surface.py model.xlsx --out surface.json
python tp_scripts/build_dependency_graph.py model.xlsx --surface-json surface.json --out graph.json
python tp_scripts/dependency_trace_report.py model.xlsx --out dependency_trace.json
python tp_scripts/detect_conventions.py model.xlsx --out conventions.json
python tp_scripts/diagnose_workbook.py model.xlsx --out diagnostics.json
python tp_scripts/media_inventory.py model.xlsx --out media.json
python tp_scripts/classify_architecture.py model.xlsx --out architecture.json

# Phase 1 — table-region detection and per-cell candidate surface.
# candidate_mapping.py REPLACED source_plan_inventory.py (removed in v4.x);
# its two outputs drive everything downstream: table_regions.json is the
# Phase 2 force-clear mask AND the manifest_lint W.14 input; cell_candidates.json
# is the Phase 3 semantic-mapping evidence surface.
python tp_scripts/candidate_mapping.py model.xlsx \
    --out-tables table_regions.json \
    --out-candidates cell_candidates.json

# Phase 1 — comprehensive input inventory and draft decisions.
# ALWAYS pass --table-regions: without it the force-clear mask is silently
# skipped and table cells fall back to allowlist-trusting behavior.
# Iterate this step: first run produces a draft; identify true defaults; add
# them to preserved_defaults.json; re-run; repeat until the draft contains
# only true deal facts. Defaults trapped inside a detected (non-sum-confirmed)
# region need "approved_region_exception": true on their preserved_defaults
# entry — set ONLY after explicit user approval in the Phase 1 form.
python tp_scripts/comprehensive_input_inventory.py model.xlsx \
    --table-regions table_regions.json \
    --out input_inventory.json \
    --emit-decisions decisions_clear_cells_draft.json
# (after manual review, iterate with --preserved-defaults preserved_defaults.json)

# Phase 2 — remediation
# REQUIRED BEFORE THIS STEP: decisions.json MUST contain a "clear_cells" array
# populated by merging decisions_clear_cells_draft.json (from --emit-decisions above).
# Do NOT hand-author clear_cells. Do NOT call prepare_clean_template_v2.py without it.
# A decisions.json missing "clear_cells" causes prepare_clean_template_v2.py to clear
# nothing silently — the workbook will appear cleaned but retain all prior-deal values.
# Merge command (example): python -c "import json; d=json.load(open('decisions.json'));
#   draft=json.load(open('decisions_clear_cells_draft.json'));
#   d['clear_cells']=draft['clear_cells']; json.dump(d, open('decisions.json','w'))"
python tp_scripts/prepare_clean_template_v2.py model.xlsx decisions.json --out model_cleaned.xlsx

# Phase 2 verification — coverage gate
python tp_scripts/coverage_verify.py model_cleaned.xlsx \
    --inventory input_inventory.json \
    --out coverage_report.json \
    --max-uncleared 20

# Phase 2B — leak scan. ALWAYS pass --table-regions so region residue is caught.
# v4.4 severity tiers: `blocking` findings fail the scan; `review` findings are
# heuristic hits the LLM verifies against the workbook (label_context and text
# fields are included in clear text for exactly that triage); `info` is FYI.
python tp_scripts/post_clean_leak_scan.py model_cleaned.xlsx \
    --decisions-json decisions.json \
    --table-regions table_regions.json \
    --preserved-defaults preserved_defaults.json \
    --out leak_scan.json

# Phase 3 — manifest verification. ALWAYS pass --cleaned-workbook (leakage
# accounting) and --table-regions (W.14 unmapped-wide-region check).
python tp_scripts/manifest_lint.py model_manifest.md \
    --cleaned-workbook model_cleaned.xlsx \
    --table-regions table_regions.json \
    --cell-candidates cell_candidates.json \
    --out manifest_lint.json
python tp_scripts/verify_write_preflight.py model_cleaned.xlsx model_manifest.md --out preflight_written.xlsx
python tp_scripts/sniff_test.py model_cleaned.xlsx model_manifest.md --out sniff_recalculated.xlsx --recalc-timeout 120
~~~

The scripts below are conservative. They produce evidence and execute approved decisions. The LLM still performs business classification, but the final workbook cannot be marked ready unless deterministic scans pass and L3 formula-reevaluation-backed economic sniff passes.

## `tp_common.py`

~~~python
#!/usr/bin/env python3
"""Shared primitives for the RealAI template-preparation scripts.

Single source of truth for the helpers that were previously copy-pasted across
tp_scripts/*. Centralizing them removes duplication AND eliminates the drift
class of bug (e.g. one script's formula/manifest check silently diverging from
another's). Each consuming script adds, near the top:

    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from tp_common import (
        is_formula, is_text, is_numeric, hash_value, split_cell,
        col_letter_to_idx, idx_to_col_letter,
        FENCE_RE, ManifestFormatError, load_manifest,
        find_excel_skill_root,
    )

NOTE: `value_class` is intentionally NOT centralized here. The per-script copies
return different label vocabularies on purpose (e.g. "rate" vs "rate_or_pct",
flat "text" vs split "label_text"/"toggle_text") and downstream logic branches on
those exact strings. Keep each script's value_class local unless you migrate it to
an explicitly parameterized variant and diff-test every call site.
"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # load_manifest will raise a clear error if actually called
    yaml = None  # type: ignore


# ── value primitives ─────────────────────────────────────────────────────────

def is_formula(v: Any) -> bool:
    return isinstance(v, str) and v.startswith("=")


def is_text(v: Any) -> bool:
    return isinstance(v, str) and not v.startswith("=") and v.strip() != ""


def is_numeric(v: Any) -> bool:
    if v is None or v == "":
        return False
    if isinstance(v, bool):
        return False
    if is_formula(v):
        return False
    return isinstance(v, (int, float))


def hash_value(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return "sha256:" + hashlib.sha256(repr(value).encode("utf-8", "replace")).hexdigest()


# ── cell-ref parsing ─────────────────────────────────────────────────────────

def split_cell(ref: str) -> tuple[str, str]:
    """'Sheet!A1' -> ('Sheet', 'A1'). Raises ValueError if not sheet-qualified."""
    if "!" not in ref:
        raise ValueError(f"Cell reference must be sheet-qualified: {ref}")
    sheet, coord = ref.split("!", 1)
    return sheet.strip("'"), coord


def col_letter_to_idx(letter: str) -> int:
    """'A' -> 1, 'Z' -> 26, 'AA' -> 27. (1-based, matches openpyxl.)"""
    idx = 0
    for ch in letter:
        idx = idx * 26 + (ord(ch.upper()) - ord("A") + 1)
    return idx


def idx_to_col_letter(idx: int) -> str:
    """1 -> 'A', 27 -> 'AA'. (1-based, matches openpyxl.)"""
    out = ""
    while idx > 0:
        idx, rem = divmod(idx - 1, 26)
        out = chr(ord("A") + rem) + out
    return out


# ── manifest loading ─────────────────────────────────────────────────────────

# Match yaml/yml fenced blocks specifically; the language tag is required so a JSON
# sniff-output block at the bottom of a prose-style manifest cannot be silently
# treated as the manifest.
FENCE_RE = re.compile(r"`{3}\s*(yaml|yml)\b\s*\n(.*?)\n`{3}", re.S | re.I)


class ManifestFormatError(ValueError):
    """Raised when the manifest file is not a single fenced YAML block with manifest content."""


def load_manifest(path: str) -> dict:
    """Read a manifest .md and return the largest fenced YAML block as a dict.

    Raises ManifestFormatError when the file has no YAML block, the block does not
    parse to a mapping, or the mapping has no cells/tables/outputs to act on.
    """
    if yaml is None:
        raise ManifestFormatError("PyYAML not installed; cannot parse manifest.")
    text = Path(path).read_text(encoding="utf-8")
    blocks = [content for _tag, content in FENCE_RE.findall(text)]
    if not blocks:
        raise ManifestFormatError(
            f"No fenced YAML block found in {path}. The manifest must be a markdown file "
            f"containing a single fenced YAML block (```yaml ... ```). Prose/table/header-style "
            f"manifests are not machine-readable and cannot drive lint, preflight, or the sniff test."
        )
    blocks.sort(key=len, reverse=True)
    try:
        data = yaml.safe_load(blocks[0]) or {}
    except yaml.YAMLError as exc:
        raise ManifestFormatError(f"Largest YAML block in {path} did not parse: {exc}") from exc
    if not isinstance(data, dict):
        raise ManifestFormatError(
            f"Manifest YAML block in {path} did not parse to a mapping/dict; "
            f"got {type(data).__name__}."
        )
    if not (data.get("cells") or data.get("tables") or data.get("outputs")):
        raise ManifestFormatError(
            f"Manifest in {path} is parseable YAML but contains no 'cells', 'tables', or "
            f"'outputs' sections."
        )
    return data


# ── Excel skill root resolution ──────────────────────────────────────────────

def find_excel_skill_root() -> Path | None:
    """Locate the Excel skill root (the directory containing scripts/recalc.py).

    Union of every prior copy's resolution order:
      1. REALAI_XLSX_SKILL_ROOT, EXCEL_SKILL_ROOT, XLSX_SKILL_ROOT env vars.
      2. Filesystem walk up from cwd and __file__ for .../scripts/recalc.py under
         the dir itself or its skills/xlsx or skills/xls subdir.
      3. Well-known install locations (claude.ai, Cowork/desktop, /sessions/*).

    Returns None if not found. Callers decide whether that is fatal; for the
    post-clean normalization step it is a soft skip.
    """
    for env_var in ("REALAI_XLSX_SKILL_ROOT", "EXCEL_SKILL_ROOT", "XLSX_SKILL_ROOT"):
        value = os.environ.get(env_var)
        if not value:
            continue
        try:
            root = Path(value).expanduser().resolve()
        except Exception:
            continue
        if (root / "scripts" / "recalc.py").exists():
            return root

    bases: list[Path] = [Path.cwd()]
    try:
        bases.append(Path(__file__).resolve().parent)
    except NameError:
        pass
    seen: set[Path] = set()
    for base in bases:
        for candidate in [base, *base.parents]:
            for sub in (candidate, candidate / "skills" / "xlsx", candidate / "skills" / "xls"):
                try:
                    sub_resolved = sub.resolve()
                except Exception:
                    continue
                if sub_resolved in seen or sub_resolved.name in {"tp_scripts", "template_prep_scripts"}:
                    continue
                seen.add(sub_resolved)
                if (sub_resolved / "scripts" / "recalc.py").exists():
                    return sub_resolved

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


# ── synthetic payload generation (prep-time verification) ────────────────────

def _synth_value(role: str, key: str):
    """Plausible dummy value for a mapped input, from its semantic_role/key.

    Goal is structural: populate every mapped surface so write-preflight and the
    recalc-backed sniff fire without type errors — NOT economic realism.
    """
    s = f"{role} {key}".lower()
    def has(*terms): return any(t in s for t in terms)
    if has("name","label","msa","city","state","address","zip","sponsor",
           "description","county","market","submarket","type","category","class",
           "plan","tier","status","use"):
        return "TEST"
    if has("date","close","completion","delivery","start"):
        return "2025-01-01"
    if has("occupancy"): return 0.93
    if has("exit_cap","entry_cap","cap_rate","cap rate"): return 0.055
    if has("ltv","ltc"): return 0.65
    if has("dscr","coverage"): return 1.25
    if has("rate","pct","percent","ratio","vacancy","growth","spread","margin","yield"):
        return 0.05
    if has("bed","bath"): return 2
    if has("stories","floors"): return 5
    if has("units","unit_count","count","spaces","parking","keys"): return 100
    if has("avg_sqft","avg sqft","unit_sf","per_unit_sf"): return 800
    if has("sf","sqft","square","footage","area"): return 50000
    if has("acre"): return 5
    if has("term","amort","interest_only","io_","period","months","years","hold",
           "age","year_built","vintage"):
        return 10
    if has("rent","income"): return 1500
    if has("reserve"): return 250
    if has("price","cost","loan","debt","budget","proceeds","value","equity",
           "mezz","pref","land","fee","tax","insurance","amount","expense",
           "payroll","capex","contingency","noi","gpr"):
        return 1_000_000
    return 1000


def _set_path(d: dict, dotted: str, value) -> None:
    parts = dotted.split(".")
    cur = d
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = value


def synthesize_payload(manifest: dict, rows_per_table: int = 3) -> dict:
    """Build a manifest-driven synthetic payload for prep-time verification.

    Walks manifest.cells and manifest.tables and emits a plausible dummy value
    for every mapped scalar plus a few representative rows per table, so
    write-preflight and sniff_test run on ANY template/deal type without a real
    deal. Values are structurally plausible, not economically realistic.
    """
    payload: dict = {}
    for key, cfg in (manifest.get("cells") or {}).items():
        role = (cfg.get("semantic_role") if isinstance(cfg, dict) else "") or ""
        _set_path(payload, key, _synth_value(role, key))
    for tname, tdef in (manifest.get("tables") or {}).items():
        if not isinstance(tdef, dict):
            continue
        cols = tdef.get("columns") or {}
        first, last = tdef.get("first_data_row"), tdef.get("last_data_row")
        cap = rows_per_table
        if isinstance(first, int) and isinstance(last, int):
            cap = max(1, min(rows_per_table, last - first + 1))
        rows = []
        for _ in range(cap):
            row = {}
            for field, spec in cols.items():
                src = spec.get("source") if isinstance(spec, dict) else None
                if src == "structural_label":
                    continue
                role = spec.get("semantic_role") if isinstance(spec, dict) else ""
                row[field] = _synth_value(role or "", field)
            if row:
                rows.append(row)
        _set_path(payload, tdef.get("payload_path") or f"tables.{tname}", rows)
    return payload


# Back-compat alias: sniff_test.py referenced this name.
infer_excel_skill_root = find_excel_skill_root

# END tp_common.py
~~~

## `candidate_mapping.py`

~~~python
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
        "candidate_cell_count": len(candidates),
        "candidate_cells_in_table_regions": sum(1 for c in candidates if c["in_table_region_id"] is not None),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# END candidate_mapping.py
~~~

## `comprehensive_input_inventory.py`

~~~python
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

    # Table-region override fires before the allowlist is consulted.
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
    if cls in {"toggle_text", "boolean"}:
        return "manual_review", "controlled-vocab toggle; may be a default the user wants to preserve", None
    if cls == "zero":
        return "manual_review", "zero value — may be intentional or empty placeholder", None
    if cls in {"rate", "small_number", "medium_number", "large_number", "datetime", "date_text"}:
        if is_formula_anchor and cls in {"rate", "small_number"}:
            return ("manual_review",
                    "hardcoded scalar interrupts a fill-formula series (formula-anchor "
                    "constant); clearing would orphan the dependent cascade — preserve as a "
                    "default or map it explicitly, do not silently clear",
                    None)
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
                             "of the preserved-defaults allowlist.")
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

    wb = openpyxl.load_workbook(args.workbook, data_only=False, keep_links=False)
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
        "formula_anchors_flagged": 0,
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
                anchor = (not in_table) and detect_formula_anchor(ws, cell.row, cell.column, cls)

                disposition, rationale, force_cleared_reason = classify_disposition(
                    cls, in_cells, in_ranges, in_structural, in_table,
                    has_region_exception=has_exception,
                    region_sum_confirmed=sum_confirmed,
                    is_formula_anchor=anchor,
                )
                if anchor and disposition == "manual_review":
                    summary["formula_anchors_flagged"] += 1
                if force_cleared_reason:
                    summary["force_cleared_overrides"] += 1
                    if force_cleared_reason.startswith("region_exception_refused"):
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
        for entry in inventory:
            if entry["disposition"] != "clear":
                continue
            rationale = "comprehensive_input_inventory: " + entry["rationale"]
            if entry.get("force_cleared_reason"):
                rationale += f" [force-clear: {entry['force_cleared_reason']}]"
            clear_cells.append({
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
            })
        decisions_fragment = {
            "_comment": (
                "Draft clear_cells generated by comprehensive_input_inventory.py. "
                "Cells with [force-clear: in_detected_table_region_overrides_allowlist] "
                "were cleared even though preserved_defaults.json marked them as defaults; "
                "table-shaped regions are runtime input by definition. Review and prune "
                "any non-table cells that should actually be preserved as template defaults; "
                "add those to preserved_defaults.json and re-run for a cleaner draft."
            ),
            "clear_cells": clear_cells,
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
~~~

## `dependency_trace_report.py`

~~~python
#!/usr/bin/env python3
"""Build a conservative sheet-level dependency trace for workbook cleanup.

This script is intentionally sheet-level, not a full Excel calc graph. It traces
formulas, defined names, data validation formulas, conditional formatting
formulas where accessible, and chart references where openpyxl exposes them.

Deletion candidates are only suggestions. The LLM/user must approve deletion.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

import openpyxl

SHEET_REF_RE = re.compile(r"(?:'([^']+)'|([A-Za-z0-9_ .&()\-]+))!\$?[A-Z]{1,3}\$?\d+(?::\$?[A-Z]{1,3}\$?\d+)?")


def clean_sheet_name(name: str | None) -> str | None:
    if not name:
        return None
    return name.strip().strip("'")


def refs_from_formula(text: Any, sheetnames: set[str]) -> set[str]:
    refs = set()
    if not isinstance(text, str):
        return refs
    for m in SHEET_REF_RE.finditer(text):
        s = clean_sheet_name(m.group(1) or m.group(2))
        if s in sheetnames:
            refs.add(s)
    return refs


def defined_name_items(wb) -> list[tuple[str, Any]]:
    dn = wb.defined_names
    try:
        return list(dn.items())
    except Exception:
        pass
    try:
        return [(d.name, d) for d in dn.definedName]
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


def transitive_closure(start: set[str], deps: dict[str, set[str]]) -> set[str]:
    seen = set(start)
    q = deque(start)
    while q:
        cur = q.popleft()
        for nxt in deps.get(cur, set()):
            if nxt not in seen:
                seen.add(nxt)
                q.append(nxt)
    return seen


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workbook")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    wb = openpyxl.load_workbook(args.workbook, data_only=False, keep_links=False)
    sheetnames = set(wb.sheetnames)
    deps: dict[str, set[str]] = defaultdict(set)
    evidence: list[dict[str, Any]] = []

    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                val = cell.value
                if isinstance(val, str) and val.startswith("="):
                    refs = refs_from_formula(val, sheetnames)
                    for ref in refs:
                        deps[ws.title].add(ref)
                        evidence.append({"from_sheet": ws.title, "to_sheet": ref, "type": "formula", "cell": cell.coordinate})

        try:
            for dv in ws.data_validations.dataValidation:
                for f in [getattr(dv, "formula1", None), getattr(dv, "formula2", None)]:
                    for ref in refs_from_formula(f, sheetnames):
                        deps[ws.title].add(ref)
                        evidence.append({"from_sheet": ws.title, "to_sheet": ref, "type": "data_validation"})
        except Exception:
            pass

        try:
            for cf_rules in ws.conditional_formatting._cf_rules.values():
                for rule in cf_rules:
                    for f in getattr(rule, "formula", []) or []:
                        for ref in refs_from_formula(f, sheetnames):
                            deps[ws.title].add(ref)
                            evidence.append({"from_sheet": ws.title, "to_sheet": ref, "type": "conditional_format"})
        except Exception:
            pass

        try:
            for chart in getattr(ws, "_charts", []) or []:
                txt = repr(chart)
                for ref in refs_from_formula(txt, sheetnames):
                    deps[ws.title].add(ref)
                    evidence.append({"from_sheet": ws.title, "to_sheet": ref, "type": "chart_repr"})
        except Exception:
            pass

    for name, defn in defined_name_items(wb):
        text = attr_text(defn)
        for ref in refs_from_formula(text, sheetnames):
            # Defined names are global; conservatively mark all visible sheets as possibly depending on them.
            for ws in wb.worksheets:
                if ws.sheet_state == "visible":
                    deps[ws.title].add(ref)
            evidence.append({"defined_name": name, "to_sheet": ref, "type": "defined_name"})

    visible = {ws.title for ws in wb.worksheets if ws.sheet_state == "visible"}
    hidden = {ws.title for ws in wb.worksheets if ws.sheet_state != "visible"}
    support_closure = transitive_closure(visible, deps)
    deletion_candidates = sorted(hidden - support_closure)
    retained_hidden_support = sorted(hidden & support_closure)

    result = {
        "workbook": str(args.workbook),
        "visible_sheets": sorted(visible),
        "hidden_sheets": sorted(hidden),
        "sheet_dependencies": {k: sorted(v) for k, v in deps.items()},
        "visible_sheet_support_closure": sorted(support_closure),
        "retained_hidden_support_sheets": retained_hidden_support,
        "hidden_sheet_deletion_candidates": deletion_candidates,
        "evidence": evidence[:10000],
        "deletion_policy_note": "Deletion candidates require LLM/user approval and should be deleted only if no unsupported references remain.",
    }
    Path(args.out).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"status": "ok", "out": args.out, "hidden_candidates": len(deletion_candidates)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# END dependency_trace_report.py
~~~

## `media_inventory.py`

~~~python
#!/usr/bin/env python3
"""Inventory workbook media and drawing parts for Template Prep."""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path
from typing import Any

import openpyxl


def anchor_to_text(anchor: Any) -> str:
    try:
        marker = anchor._from
        return f"row={marker.row + 1},col={marker.col + 1}"
    except Exception:
        return str(anchor)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workbook")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    wb = openpyxl.load_workbook(args.workbook, data_only=False, keep_links=False)
    sheet_images = []
    for ws in wb.worksheets:
        for idx, img in enumerate(getattr(ws, "_images", []) or [], start=1):
            sheet_images.append({
                "sheet": ws.title,
                "image_index_on_sheet": idx,
                "openpyxl_path": getattr(img, "path", None),
                "anchor": anchor_to_text(getattr(img, "anchor", None)),
                "width": getattr(img, "width", None),
                "height": getattr(img, "height", None),
                "recommended_default_action": "remove_unless_template_owner_logo",
            })

    package_media = []
    drawing_parts = []
    rel_parts = []
    with zipfile.ZipFile(args.workbook) as zf:
        for name in zf.namelist():
            if name.startswith("xl/media/"):
                info = zf.getinfo(name)
                package_media.append({"part": name, "size": info.file_size})
            elif name.startswith("xl/drawings/"):
                drawing_parts.append(name)
            elif "drawings/_rels" in name or name.endswith(".rels") and "drawing" in name:
                rel_parts.append(name)

    result = {
        "workbook": str(args.workbook),
        "sheet_images": sheet_images,
        "package_media": package_media,
        "drawing_parts": drawing_parts,
        "drawing_relationship_parts": rel_parts,
        "policy": "Only template-owner logos may remain. Photos, non-owner logos, and unknown images should be removed unless explicitly approved.",
    }
    Path(args.out).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"status": "ok", "out": args.out, "images": len(sheet_images), "media_parts": len(package_media)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# END media_inventory.py
~~~

## `prepare_clean_template_v2.py`

~~~python
#!/usr/bin/env python3
"""Apply approved Template Prep v2 remediation to a macro-free .xlsx workbook.

The decisions file is JSON. Supported keys include:

{
  "deal_strings": ["Prior Deal Name"],
  "template_owner_logo_media_paths_to_keep": ["/xl/media/image1.png"],
  "media_cleanup_approved": true,
  "remove_media_not_in_keep_list": true,
  "dependency_trace_confirmed": true,
  "delete_sheets": [{"sheet": "Old Scratch", "rationale": "No retained dependents"}],
  "clear_cells": [{"cell": "Sheet!A1", "runtime_source_class": "datamart_preferred_user_fallback", "rationale": "Deal fact"}],
  "clear_ranges": [{"sheet": "Unit Mix", "range": "A5:F30", "clear_formulas": false, "rationale": "Clear unit mix labels and values"}],
  "clear_tables": [{"sheet": "Rent Roll", "range": "A5:Z200", "clear_row_labels": true, "rationale": "Clear prior rent roll"}],
  "defined_names": {"remove_invalid_or_broken": true, "remove_external": true, "remove_names": ["OldName"]},
  "broken_formulas": [{"cell": "Sheet!B10", "action": "replace", "replacement_formula": "=B9+B8", "confidence": "high"}, {"cell": "Sheet!C10", "action": "clear", "confidence": "low"}]
}

Raw prior values are never written to the audit sheet. The audit stores value
classes and hashes only.
"""

from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from tp_common import (  # shared primitives; see tp_common.py
    split_cell, find_excel_skill_root,
)

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import openpyxl
from openpyxl.utils.cell import range_boundaries

AUDIT_SHEET = "_PreparationAudit"
BROKEN_REF_RE = re.compile(r"#REF!|#NAME\?|\[[^\]]+\]", re.I)


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


def value_hash(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return "sha256:" + hashlib.sha256(repr(value).encode("utf-8", "replace")).hexdigest()


def ensure_audit_sheet(wb):
    if AUDIT_SHEET in wb.sheetnames:
        del wb[AUDIT_SHEET]
    ws = wb.create_sheet(AUDIT_SHEET)
    ws.sheet_state = "hidden"
    ws.append([
        "timestamp_utc", "location", "action", "value_class_before", "prior_value_redacted",
        "before_hash", "after_state", "category", "runtime_source_class", "rationale",
        "approved_by_user", "confidence",
    ])
    return ws


def audit(ws, location: str, action: str, before: Any, after_state: str, category: str, runtime_source: str, rationale: str, approved: bool = True, confidence: str = "high"):
    ws.append([
        datetime.now(timezone.utc).isoformat(), location, action, value_class(before),
        bool(before not in (None, "")), value_hash(before), after_state, category,
        runtime_source, rationale, bool(approved), confidence,
    ])


def strip_metadata(wb, audit_ws, deal_strings: list[str]):
    props = wb.properties
    for field in ["creator", "lastModifiedBy", "company", "manager", "lastPrinted"]:
        if hasattr(props, field):
            before = getattr(props, field)
            if before not in (None, ""):
                try:
                    setattr(props, field, None)
                    audit(audit_ws, f"workbook.properties.{field}", "strip_metadata", before, "blank", "I.1", "metadata", "Removed workbook metadata")
                except Exception:
                    pass
    for field in ["title", "subject", "keywords", "category", "description"]:
        if hasattr(props, field):
            before = getattr(props, field)
            if isinstance(before, str) and any(s and s.lower() in before.lower() for s in deal_strings):
                setattr(props, field, None)
                audit(audit_ws, f"workbook.properties.{field}", "strip_deal_metadata", before, "blank", "C.9", "prior_deal_specific", "Removed deal-specific workbook metadata")


def clear_cells(wb, audit_ws, items: list[dict]):
    for item in items:
        ref = item["cell"]
        sheet, coord = split_cell(ref)
        if sheet not in wb.sheetnames:
            audit(audit_ws, ref, "skip_missing_sheet", None, "unchanged", "C.12", item.get("runtime_source_class", "manual_review"), "Sheet not found", False, "low")
            continue
        cell = wb[sheet][coord]
        before = cell.value
        if isinstance(before, str) and before.startswith("=") and not item.get("clear_formula", False):
            audit(audit_ws, ref, "skip_formula", before, "unchanged", "W.5", item.get("runtime_source_class", "manual_review"), "Formula cells are not cleared by scalar cleanup", False, "medium")
            continue
        cell.value = None
        audit(audit_ws, ref, "clear_value", before, "blank", "C.9", item.get("runtime_source_class", "runtime_input"), item.get("rationale", "Cleared runtime deal input"), True, item.get("confidence", "high"))


def clear_ranges(wb, audit_ws, items: list[dict], category: str):
    for item in items:
        sheet = item["sheet"]
        if sheet not in wb.sheetnames:
            audit(audit_ws, sheet, "skip_missing_sheet", None, "unchanged", category, item.get("runtime_source_class", "manual_review"), "Sheet not found", False, "low")
            continue
        ws = wb[sheet]
        min_col, min_row, max_col, max_row = range_boundaries(item["range"])
        clear_formulas = bool(item.get("clear_formulas", False))
        cleared = 0
        hashed_summary = hashlib.sha256()
        for row in ws.iter_rows(min_row=min_row, max_row=max_row, min_col=min_col, max_col=max_col):
            for cell in row:
                before = cell.value
                if before in (None, ""):
                    continue
                if isinstance(before, str) and before.startswith("=") and not clear_formulas:
                    continue
                hashed_summary.update(repr(before).encode("utf-8", "replace"))
                cell.value = None
                cleared += 1
        audit(audit_ws, f"{sheet}!{item['range']}", item.get("action", "clear_range_values_and_labels"), f"{cleared}_values_hash:{hashed_summary.hexdigest()}", "blank_non_formula_cells", category, item.get("runtime_source_class", "runtime_input"), item.get("rationale", "Cleared prior-deal range while preserving schema"), True, item.get("confidence", "high"))


def remove_media(wb, audit_ws, decisions: dict):
    if not decisions.get("media_cleanup_approved"):
        return
    if not decisions.get("remove_media_not_in_keep_list", True):
        return
    keep = set(decisions.get("template_owner_logo_media_paths_to_keep", []))
    for ws in wb.worksheets:
        images = list(getattr(ws, "_images", []) or [])
        retained = []
        removed = 0
        for img in images:
            path = getattr(img, "path", None)
            if path in keep:
                retained.append(img)
            else:
                removed += 1
                audit(audit_ws, f"{ws.title}:{path or 'image'}", "remove_media", path or "image", "removed", "C.10", "media_cleanup", "Removed non-template-owner or unapproved media", True, "high")
        try:
            ws._images = retained
        except Exception:
            if removed:
                audit(audit_ws, ws.title, "media_remove_failed", f"{removed}_images", "unchanged", "C.10", "media_cleanup", "Could not update worksheet image collection", False, "low")


def defined_name_items(wb) -> list[tuple[str, Any]]:
    dn = wb.defined_names
    try:
        return list(dn.items())
    except Exception:
        pass
    try:
        return [(d.name, d) for d in dn.definedName]
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


def remove_defined_name(wb, name: str) -> bool:
    try:
        del wb.defined_names[name]
        return True
    except Exception:
        pass
    try:
        wb.defined_names.delete(name)
        return True
    except Exception:
        pass
    return False


def clean_defined_names(wb, audit_ws, decisions: dict):
    cfg = decisions.get("defined_names", {}) or {}
    explicit = set(cfg.get("remove_names", []))
    remove_invalid = bool(cfg.get("remove_invalid_or_broken", True))
    remove_external = bool(cfg.get("remove_external", True))
    for name, defn in defined_name_items(wb):
        text = attr_text(defn)
        should_remove = name in explicit
        reason = "explicitly approved removal"
        if not should_remove and remove_invalid and ("#REF!" in text or text.strip() in {"", "None"}):
            should_remove = True
            reason = "broken or empty defined name"
        if not should_remove and remove_external and ("[" in text and "]" in text):
            should_remove = True
            reason = "external workbook defined name"
        if should_remove:
            before = f"{name}:{text}"
            ok = remove_defined_name(wb, name)
            audit(audit_ws, f"defined_name:{name}", "remove_defined_name" if ok else "remove_defined_name_failed", before, "removed" if ok else "unchanged", "C.4", "defined_name_cleanup", reason, ok, "high")


def apply_broken_formula_plan(wb, audit_ws, items: list[dict]):
    for item in items:
        ref = item["cell"]
        sheet, coord = split_cell(ref)
        if sheet not in wb.sheetnames:
            audit(audit_ws, ref, "broken_formula_skip_missing_sheet", None, "unchanged", "C.1", "derived_formula", "Sheet not found", False, "low")
            continue
        cell = wb[sheet][coord]
        before = cell.value
        action = item.get("action")
        confidence = item.get("confidence", "low")
        if action == "replace":
            repl = item.get("replacement_formula")
            if not repl or not str(repl).startswith("=") or confidence != "high":
                audit(audit_ws, ref, "skip_low_confidence_formula_repair", before, "unchanged", "C.1", "derived_formula", "Formula repair missing high confidence replacement", False, confidence)
                continue
            cell.value = repl
            audit(audit_ws, ref, "repair_formula", before, "repaired", "C.1", "derived_formula", item.get("rationale", "High-confidence broken formula repair"), True, confidence)
        elif action == "clear":
            cell.value = None
            audit(audit_ws, ref, "remove_unrepairable_formula", before, "blank", "C.1", "derived_formula", item.get("rationale", "Removed unrepairable broken formula after dependency trace"), True, confidence)


def delete_sheets(wb, audit_ws, decisions: dict):
    items = decisions.get("delete_sheets", []) or []
    if not items:
        return
    if not decisions.get("dependency_trace_confirmed"):
        for item in items:
            audit(audit_ws, item.get("sheet", "unknown"), "skip_delete_sheet_no_dependency_trace", None, "unchanged", "C.11", "sheet_cleanup", "Sheet deletion requires confirmed dependency trace", False, "low")
        return
    for item in items:
        sheet = item["sheet"]
        if sheet in wb.sheetnames and sheet != AUDIT_SHEET:
            before = f"sheet_state:{wb[sheet].sheet_state}"
            del wb[sheet]
            audit(audit_ws, f"sheet:{sheet}", "delete_sheet", before, "removed", "C.11", "sheet_cleanup", item.get("rationale", "Deleted dependency-proven dead sheet"), True, item.get("confidence", "high"))


def _office_helper_paths(skill_root: Path) -> dict:
    """Locate the xlsx skill's office/ helpers. Returns {} if the suite is incomplete."""
    base = skill_root / "scripts" / "office"
    paths = {
        "unpack": base / "unpack.py",
        "pack": base / "pack.py",
        "validate": base / "validate.py",
    }
    if not all(p.exists() for p in paths.values()):
        return {}
    return {k: str(v) for k, v in paths.items()}


def _list_referenced_media(unpack_dir: Path) -> set[str]:
    """Walk all *.rels files under the unpacked directory and collect every Target
    that points into xl/media/. Used to identify orphan media after openpyxl save."""
    referenced: set[str] = set()
    for rels_file in unpack_dir.rglob("*.rels"):
        try:
            text = rels_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        # Targets look like Target="../media/image1.png" (relative to part directory)
        for match in re.finditer(r'Target="([^"]+)"', text):
            target = match.group(1)
            # Resolve relative to the rels file's parent's parent (one above _rels)
            base_dir = rels_file.parent.parent
            try:
                resolved = (base_dir / target).resolve().relative_to(unpack_dir.resolve())
            except (ValueError, OSError):
                continue
            posix = resolved.as_posix()
            if posix.startswith("xl/media/"):
                referenced.add(posix)
    return referenced


def post_clean_package_surgery(
    wb_path: Path,
    decisions: dict,
    skill_root: Path | None = None,
) -> dict:
    """OOXML-level cleanup that openpyxl cannot do reliably. Runs after the openpyxl
    save and before recalc normalization.

    Performs:
      1. Initial validate.py --auto-repair on the openpyxl-saved file.
      2. Unpack via office/unpack.py.
      3. Surgical edits:
         - Delete orphan xl/media/* files (no remaining rel references).
         - Scrub author identity from xl/comments*.xml and xl/threadedComments/*.xml.
         - Drop xl/customXml/* parts (often retain deal-data caches).
         - Strip headers/footers from worksheet XML when decisions.media_cleanup_approved
           or decisions.strip_headers_footers is set.
      4. Repack via office/pack.py --validate true (auto-validates on repack).
      5. Final validate.py --auto-repair pass.

    Returns a dict suitable for inclusion in the cleanup result JSON. Any non-'packaged'
    status indicates degraded cleanup; the cleaned file is still produced but the
    workflow should mark readiness as needs_review per the SKILL contract.
    """
    if skill_root is None:
        skill_root = find_excel_skill_root()
    if skill_root is None:
        return {
            "status": "skipped_no_skill_root",
            "reason": (
                "Set REALAI_XLSX_SKILL_ROOT to enable office/-based package cleanup. "
                "Without it, openpyxl-based media removal may leave orphan parts that "
                "trigger Excel repair on first open."
            ),
        }
    helpers = _office_helper_paths(skill_root)
    if not helpers:
        return {
            "status": "skipped_office_helpers_missing",
            "reason": f"office/ helper suite incomplete under {skill_root / 'scripts' / 'office'}",
        }

    actions: list[dict] = []
    deal_strings_present = bool(decisions.get("deal_strings"))
    strip_hf = bool(decisions.get("strip_headers_footers", decisions.get("media_cleanup_approved", False)))

    # 1. Initial validation pass to fix common openpyxl-introduced issues (hex IDs, whitespace).
    pre_validate = subprocess.run(
        [sys.executable, helpers["validate"], str(wb_path), "--auto-repair"],
        capture_output=True, text=True, timeout=60,
    )

    with tempfile.TemporaryDirectory() as td:
        unpack_dir = Path(td) / "unpacked"
        unpack_proc = subprocess.run(
            [sys.executable, helpers["unpack"], str(wb_path), str(unpack_dir)],
            capture_output=True, text=True, timeout=120,
        )
        if unpack_proc.returncode != 0:
            return {
                "status": "unpack_failed",
                "reason": (unpack_proc.stderr or unpack_proc.stdout or "unknown")[-500:],
                "pre_validate_returncode": pre_validate.returncode,
            }

        # 2a. Identify referenced media after openpyxl serialization. Anything in
        #     xl/media/ not referenced by any rel is an orphan and gets deleted.
        media_dir = unpack_dir / "xl" / "media"
        if media_dir.exists():
            referenced = _list_referenced_media(unpack_dir)
            for media_file in sorted(media_dir.iterdir()):
                if not media_file.is_file():
                    continue
                rel_path = f"xl/media/{media_file.name}"
                if rel_path not in referenced:
                    media_file.unlink()
                    actions.append({"action": "remove_orphan_media", "path": rel_path})

        # 2b. Scrub comment author identity. Threaded comments use personList; classic
        #     comments use <author> elements directly.
        for pattern in ("comments*.xml", "threadedComments/*.xml", "persons/*.xml"):
            for comments_file in (unpack_dir / "xl").glob(pattern):
                try:
                    text = comments_file.read_text(encoding="utf-8")
                except OSError:
                    continue
                new_text = re.sub(r"(<author>)[^<]*(</author>)", r"\1Anonymous\2", text)
                new_text = re.sub(r'(displayName=")[^"]*(")', r"\1Anonymous\2", new_text)
                if new_text != text:
                    comments_file.write_text(new_text, encoding="utf-8")
                    actions.append({"action": "scrub_comment_author", "file": str(comments_file.relative_to(unpack_dir))})

        # 2c. Drop customXml parts (frequent deal-data leakage vector). Keep customXml
        #     only if user explicitly opted to retain it.
        if not decisions.get("retain_custom_xml"):
            custom_xml = unpack_dir / "customXml"
            if custom_xml.exists():
                removed: list[str] = []
                for f in custom_xml.rglob("*"):
                    if f.is_file():
                        try:
                            f.unlink()
                            removed.append(str(f.relative_to(unpack_dir)))
                        except OSError:
                            pass
                if removed:
                    actions.append({"action": "drop_custom_xml_parts", "count": len(removed)})

        # 2d. Strip headers/footers. Only do this when decisions opt in, since some
        #     templates use headers/footers as legitimate branding (template-owner logo
        #     in a header is rare but possible).
        if strip_hf:
            sheets_dir = unpack_dir / "xl" / "worksheets"
            if sheets_dir.exists():
                for sheet_file in sorted(sheets_dir.glob("sheet*.xml")):
                    try:
                        text = sheet_file.read_text(encoding="utf-8")
                    except OSError:
                        continue
                    new_text = re.sub(
                        r"<headerFooter[^/]*?/>|<headerFooter[\s>].*?</headerFooter>",
                        "",
                        text,
                        flags=re.S,
                    )
                    if new_text != text:
                        sheet_file.write_text(new_text, encoding="utf-8")
                        actions.append({"action": "strip_headers_footers", "sheet": sheet_file.name})

        # 2e. If deal strings are present, scan worksheet XML for any retained occurrences
        #     and replace them with a redaction marker. This catches deal-name leakage in
        #     header rows that survived cell-level cleanup.
        if deal_strings_present:
            deal_strings = [s for s in decisions["deal_strings"] if isinstance(s, str) and s]
            if deal_strings:
                scrubbed_files: list[str] = []
                for sheet_file in (unpack_dir / "xl" / "worksheets").glob("sheet*.xml"):
                    try:
                        text = sheet_file.read_text(encoding="utf-8")
                    except OSError:
                        continue
                    new_text = text
                    for ds in deal_strings:
                        # Case-insensitive replace, only inside string-table-bypass inline strings
                        # to avoid corrupting formula text. Conservative: only inline <t>...</t>.
                        new_text = re.sub(
                            r"(<t[^>]*>)([^<]*?)(" + re.escape(ds) + r")([^<]*?)(</t>)",
                            lambda m: m.group(1) + m.group(2) + "[REDACTED]" + m.group(4) + m.group(5),
                            new_text,
                            flags=re.I,
                        )
                    if new_text != text:
                        sheet_file.write_text(new_text, encoding="utf-8")
                        scrubbed_files.append(sheet_file.name)
                # Also scrub the shared strings table
                shared_strings = unpack_dir / "xl" / "sharedStrings.xml"
                if shared_strings.exists():
                    try:
                        text = shared_strings.read_text(encoding="utf-8")
                    except OSError:
                        text = None
                    if text is not None:
                        new_text = text
                        for ds in deal_strings:
                            new_text = re.sub(
                                r"(<t[^>]*>)([^<]*?)(" + re.escape(ds) + r")([^<]*?)(</t>)",
                                lambda m: m.group(1) + m.group(2) + "[REDACTED]" + m.group(4) + m.group(5),
                                new_text,
                                flags=re.I,
                            )
                        if new_text != text:
                            shared_strings.write_text(new_text, encoding="utf-8")
                            scrubbed_files.append("sharedStrings.xml")
                if scrubbed_files:
                    actions.append({"action": "redact_deal_strings_in_xml", "files": scrubbed_files})

        # 3. Repack — pack.py runs validate.py with auto-repair as part of its default flow.
        pack_proc = subprocess.run(
            [sys.executable, helpers["pack"], str(unpack_dir), str(wb_path), "--validate", "true"],
            capture_output=True, text=True, timeout=120,
        )
        if pack_proc.returncode != 0:
            return {
                "status": "pack_failed",
                "reason": (pack_proc.stderr or pack_proc.stdout or "unknown")[-500:],
                "actions_attempted": actions,
            }

    # 4. Final validation pass on the packed file (defense in depth).
    final_validate = subprocess.run(
        [sys.executable, helpers["validate"], str(wb_path), "--auto-repair"],
        capture_output=True, text=True, timeout=60,
    )

    return {
        "status": "packaged",
        "skill_root": str(skill_root),
        "actions": actions,
        "pre_validate_returncode": pre_validate.returncode,
        "final_validate_returncode": final_validate.returncode,
        "final_validate_stdout_tail": (final_validate.stdout or "")[-300:],
    }


# Patterns used by the post-save defined-name scrub. Module-level so they're compiled once.
_BROKEN_REF_RE = re.compile(r"#REF!")
_EXTERNAL_LINK_RE = re.compile(r"\[\d+\]")
_OOXML_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def scrub_broken_defined_names(wb_path: Path) -> dict:
    """Remove defined names with broken (#REF!) or external-link ([N]) targets
    directly from xl/workbook.xml.

    Why this exists: openpyxl's defined-name removal does not always propagate
    cleanly to the saved workbook.xml — especially for names that originated as
    external links — and orchestrators sometimes preserve broken named ranges
    intentionally despite the SKILL contract. Either path leaves a name that
    Excel cannot resolve, which triggers the recovery-on-open dialog:

        Removed Records: Named range from /xl/workbook.xml part (Workbook)

    The recovery itself is "soft" (Excel removes the name and continues), but
    per the SKILL contract a workbook that triggers any Excel repair on open
    cannot be marked ready. This scrub is therefore non-overridable: any
    defined name whose target contains #REF! or [N] is removed regardless of
    what decisions.json says.

    Operates at the OOXML level (zipfile + ElementTree) so it works even when
    openpyxl's in-memory removal didn't take. Runs after wb.save() and before
    package surgery / recalc normalization, so subsequent steps see a workbook
    with already-clean defined names.

    Returns a dict suitable for inclusion in the cleanup result JSON. A non-zero
    removed_count indicates that the orchestrator's decisions.json had broken
    or external names that should not have been preserved; the scrub overrode
    that choice.
    """
    if not wb_path.exists():
        return {"status": "missing_workbook", "reason": str(wb_path)}

    try:
        with zipfile.ZipFile(wb_path, "r") as zf:
            if "xl/workbook.xml" not in zf.namelist():
                return {"status": "no_workbook_xml"}
            wb_xml = zf.read("xl/workbook.xml").decode("utf-8")
    except (zipfile.BadZipFile, OSError) as exc:
        return {"status": "read_failed", "reason": f"{type(exc).__name__}: {exc}"}

    ET.register_namespace("", _OOXML_MAIN_NS)
    try:
        root = ET.fromstring(wb_xml)
    except ET.ParseError as exc:
        return {"status": "parse_failed", "reason": str(exc)}

    # Find all <definedNames> wrapper elements. Excel produces one per workbook in
    # practice, but openpyxl can occasionally emit an empty one followed by a
    # populated one in malformed-edit cases — iterate all to be defensive.
    defined_names_wrappers = root.findall(f"{{{_OOXML_MAIN_NS}}}definedNames")
    if not defined_names_wrappers:
        return {"status": "no_defined_names_in_workbook_xml", "removed_count": 0, "removed_names": []}

    removed: list[dict] = []
    for defined_names in defined_names_wrappers:
        for dn in list(defined_names):
            text = (dn.text or "").strip()
            name = dn.get("name", "")
            if _BROKEN_REF_RE.search(text) or _EXTERNAL_LINK_RE.search(text):
                defined_names.remove(dn)
                removed.append({"name": name, "target_hash": value_hash(text)})

    # Drop any <definedNames> wrappers that are now empty — avoids empty elements
    # that some downstream parsers complain about.
    for defined_names in list(defined_names_wrappers):
        if len(list(defined_names)) == 0:
            root.remove(defined_names)

    if not removed:
        return {"status": "no_broken_or_external_names", "removed_count": 0, "removed_names": []}

    new_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)

    tmp_path = wb_path.with_suffix(".scrub_tmp" + wb_path.suffix)
    try:
        with zipfile.ZipFile(wb_path, "r") as zin, zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                if item.filename == "xl/workbook.xml":
                    zout.writestr(item, new_xml)
                else:
                    zout.writestr(item, zin.read(item.filename))
        shutil.move(str(tmp_path), str(wb_path))
    except OSError as exc:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        return {"status": "rewrite_failed", "reason": f"{type(exc).__name__}: {exc}"}

    return {
        "status": "scrubbed",
        "removed_count": len(removed),
        "removed_names": removed,
        "note": (
            "Removed broken/external defined names directly from xl/workbook.xml. "
            "These would have triggered Excel recovery-on-open. Removal is non-"
            "overridable per the SKILL workbook-integrity contract; if the "
            "orchestrator's decisions.json preserved any of these, that choice "
            "was overridden here."
        ),
    }


def normalize_workbook_via_recalc(wb_path: Path, timeout_seconds: int = 90) -> dict:
    """Run a no-op recalc via the xlsx-skill recalc.py to normalize the OOXML.

    Why this exists: LibreOffice's store() (called by recalc.py's RecalculateAndSave
    macro) rewrites the workbook XML. openpyxl's saved files differ from LibreOffice's
    in ways that can trigger Excel repair on first open or that cause the downstream
    populated workbook to look subtly different from the delivered template. Running
    recalc once on the cleaned file before delivery means the file the user gets is
    byte-identical to what every downstream recalc will produce.

    Returns a dict suitable for inclusion in the cleanup result JSON. A non-'normalized'
    status does NOT block delivery — the cleaned file is still produced.
    """
    skill_root = find_excel_skill_root()
    if skill_root is None:
        return {
            "status": "skipped_no_skill_root",
            "reason": (
                "Set REALAI_XLSX_SKILL_ROOT to the xlsx skill directory to enable "
                "post-clean OOXML normalization. The cleaned file is still valid; "
                "downstream consumers will normalize it on their first recalc."
            ),
        }
    cmd = [sys.executable, "scripts/recalc.py", str(wb_path.resolve()), str(timeout_seconds)]
    try:
        proc = subprocess.run(cmd, cwd=str(skill_root), capture_output=True,
                              text=True, timeout=max(timeout_seconds + 60, 180))
    except (subprocess.TimeoutExpired, OSError) as exc:
        return {
            "status": "recalc_invocation_failed",
            "reason": f"{type(exc).__name__}: {exc}",
            "skill_root": str(skill_root),
        }
    try:
        meta = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        meta = {"raw_stdout_tail": proc.stdout[-500:] if proc.stdout else None}
    if "error" in meta:
        return {
            "status": "recalc_failed",
            "reason": meta["error"],
            "skill_root": str(skill_root),
        }
    status = str(meta.get("status", "")).lower()
    if status not in {"success", "errors_found"}:
        return {
            "status": "recalc_failed",
            "reason": f"Unexpected recalc status: {status!r}",
            "recalc_meta": meta,
            "skill_root": str(skill_root),
        }
    # total_errors > 0 is EXPECTED here — cleared runtime tables produce #N/A, #DIV/0!
    # until populated. That's not a normalization failure; it's just the post-clean
    # baseline that the manifest's runtime-input limitations rule already accounts for.
    return {
        "status": "normalized",
        "recalc_status": status,
        "total_errors": meta.get("total_errors"),
        "total_formulas": meta.get("total_formulas"),
        "note": (
            "Workbook XML rewritten by LibreOffice; downstream first-recalc will "
            "produce identical output. Errors counted here are runtime-input baseline."
        ),
    }


def reset_excel_table_refs(wb, audit_ws) -> int:
    """After table-range clearing, Excel Tables (ListObjects) may still claim the prior
    row count via their `ref` attribute. When downstream writes new rows, formulas using
    structured refs (Table[Column]) will average over stale blank rows.

    This shrinks each table's ref to the smallest rectangle that contains its header row
    plus any rows where at least one column still has a non-None value. Header is always
    preserved. Returns the number of tables whose ref was changed.
    """
    changed = 0
    for ws in wb.worksheets:
        if ws.sheet_state == "veryHidden":
            continue
        for table_name, table in list(getattr(ws, "tables", {}).items()):
            try:
                min_col, min_row, max_col, max_row = range_boundaries(table.ref)
            except Exception:
                continue
            header_row = min_row  # tables always have at least one header row
            last_data_row = header_row
            for r in range(header_row + 1, max_row + 1):
                row_has_value = False
                for c in range(min_col, max_col + 1):
                    v = ws.cell(row=r, column=c).value
                    if v not in (None, ""):
                        row_has_value = True
                        break
                if row_has_value:
                    last_data_row = r
            # Excel requires at least one data row in a table; preserve a single empty
            # data row if the table is now logically empty.
            if last_data_row == header_row:
                last_data_row = header_row + 1
            if last_data_row < max_row:
                from openpyxl.utils import get_column_letter
                new_ref = (
                    f"{get_column_letter(min_col)}{header_row}:"
                    f"{get_column_letter(max_col)}{last_data_row}"
                )
                old_ref = table.ref
                table.ref = new_ref
                changed += 1
                audit(
                    audit_ws,
                    f"{ws.title}!table:{table_name}",
                    "shrink_table_ref",
                    f"old_ref:{old_ref}",
                    f"new_ref:{new_ref}",
                    "I.6",
                    "table_ref_normalization",
                    "Shrank Excel Table ref after row clearing so structured refs do not span stale blank rows",
                    True,
                    "high",
                )
    return changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_file")
    parser.add_argument("decisions_json")
    parser.add_argument("--out", required=True)
    parser.add_argument(
        "--skip-normalization",
        action="store_true",
        help="Skip the post-clean recalc-based XML normalization. Use only when LibreOffice is unavailable; the cleaned file will be openpyxl-serialized and may differ subtly from what downstream produces.",
    )
    parser.add_argument(
        "--normalization-timeout",
        type=int,
        default=90,
        help="Timeout (seconds) for the post-clean recalc normalization step.",
    )
    parser.add_argument(
        "--skip-package-surgery",
        action="store_true",
        help="Skip the office/-based OOXML cleanup (orphan media removal, comment scrubbing, customXml drop, header/footer strip). Use only when the xlsx skill office/ helpers are unavailable; the cleaned file will not have OOXML-level cleanup.",
    )
    args = parser.parse_args()

    if Path(args.input_file).suffix.lower() != ".xlsx":
        raise SystemExit("Only macro-free .xlsx files are supported.")
    decisions = json.loads(Path(args.decisions_json).read_text(encoding="utf-8"))
    wb = openpyxl.load_workbook(args.input_file, data_only=False, keep_links=False)
    audit_ws = ensure_audit_sheet(wb)

    strip_metadata(wb, audit_ws, decisions.get("deal_strings", []))
    clear_cells(wb, audit_ws, decisions.get("clear_cells", []))
    clear_ranges(wb, audit_ws, decisions.get("clear_ranges", []), "C.9")
    clear_ranges(wb, audit_ws, decisions.get("clear_tables", []), "W.11")
    apply_broken_formula_plan(wb, audit_ws, decisions.get("broken_formulas", []))
    clean_defined_names(wb, audit_ws, decisions)
    # In-memory image removal: drops openpyxl-tracked images so the openpyxl save emits
    # a drawing XML without those images. Underlying xl/media/* parts may persist as
    # orphans and are cleaned up by the post-save package surgery step below.
    remove_media(wb, audit_ws, decisions)
    delete_sheets(wb, audit_ws, decisions)
    tables_shrunk = reset_excel_table_refs(wb, audit_ws)

    wb.save(args.out)

    # Post-save defined-name scrub — removes any broken (#REF!) or external ([N])
    # named ranges from xl/workbook.xml directly. Non-overridable per the SKILL
    # workbook-integrity contract: a broken named range guarantees Excel recovery
    # on open and disqualifies ready, regardless of orchestrator preference.
    # Runs BEFORE package surgery so subsequent steps see a clean workbook.xml.
    defined_name_scrub = scrub_broken_defined_names(Path(args.out))

    skill_root_for_post_clean = find_excel_skill_root()

    package_surgery: dict
    if args.skip_package_surgery:
        package_surgery = {"status": "skipped_by_flag", "reason": "--skip-package-surgery passed"}
    else:
        package_surgery = post_clean_package_surgery(
            Path(args.out), decisions, skill_root=skill_root_for_post_clean
        )

    normalization: dict
    if args.skip_normalization:
        normalization = {"status": "skipped_by_flag", "reason": "--skip-normalization passed"}
    else:
        normalization = normalize_workbook_via_recalc(Path(args.out), args.normalization_timeout)

    result = {
        "status": "cleaned",
        "output_file": args.out,
        "audit_sheet": AUDIT_SHEET,
        "raw_prior_values_stored": False,
        "tables_ref_shrunk": tables_shrunk,
        "post_clean_defined_name_scrub": defined_name_scrub,
        "post_clean_package_surgery": package_surgery,
        "post_clean_normalization": normalization,
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# END prepare_clean_template_v2.py
~~~

## `post_clean_leak_scan.py`

~~~python
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


def scan_cells_and_formulas(wb, deal_strings: list[str]) -> list[dict]:
    findings: list[dict] = []
    deal_strings_lower = [s.lower() for s in deal_strings if s]
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
                    findings.append({"cell": coord, "finding": "deal_string_retained", "value_class": value_class(value), "hash": h(value), "matched_deal_string": matched, "sheet_state": ws.sheet_state})
                    continue
                if isinstance(value, str) and UNIT_ROW_STRONG_RE.search(value.strip()):
                    findings.append({"cell": coord, "finding": "unit_mix_or_program_row_label_retained", "value_class": "text", "hash": h(value), "text": str(value)[:80], "sheet_state": ws.sheet_state})
                    continue
                if isinstance(value, str) and UNIT_ROW_PLANCODE_RE.search(value.strip()):
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
    exception_cells = load_region_exception_cells(args.preserved_defaults)

    wb = openpyxl.load_workbook(args.workbook, data_only=False, keep_links=False)
    findings: list[dict] = []
    findings.extend(scan_cells_and_formulas(wb, deal_strings))
    findings.extend(scan_defined_names(wb, deal_strings))
    findings.extend(scan_package_parts(args.workbook, allowed_media, deal_strings))
    if table_region_cells:
        findings.extend(scan_table_region_residue(wb, table_region_cells, exception_cells))

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
~~~

## `coverage_verify.py`

~~~python
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

~~~

## `repair_broken_named_ranges.py`

~~~python
#!/usr/bin/env python3
"""One-shot repair: remove broken/external defined names from a cleaned .xlsx.

The Excel "recovery dialog" with the message:
  "Removed Records: Named range from /xl/workbook.xml part (Workbook)"
is caused by a defined name whose target contains #REF! (broken reference) or
external-link syntax ([N]Sheet!Range). This script removes those entries
directly from xl/workbook.xml so the file opens cleanly.

USAGE
-----
  python tp_scripts/repair_broken_named_ranges.py model_cleaned.xlsx \\
    --out model_cleaned_repaired.xlsx

  # Inspect without modifying:
  python tp_scripts/repair_broken_named_ranges.py model_cleaned.xlsx --dry-run

The script operates at the OOXML level (zipfile + ElementTree) rather than via
openpyxl, because openpyxl's defined-name removal does not always propagate to
the saved workbook.xml — especially for names that were originally external
links. This is the same surface the office/ helpers operate on, but targeted
to the named-range failure mode.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
ET.register_namespace("", NS_MAIN)

BROKEN_REF_RE = re.compile(r"#REF!")
EXTERNAL_LINK_RE = re.compile(r"\[\d+\]")  # [1]Sheet!Range, [2]External!Range, etc.


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workbook", help="Cleaned xlsx to repair")
    parser.add_argument("--out", help="Output path (defaults to input + '_repaired.xlsx')")
    parser.add_argument("--dry-run", action="store_true", help="Report findings without modifying the file")
    args = parser.parse_args()

    wb_path = Path(args.workbook)
    if not wb_path.exists():
        print(f"ERROR: file not found: {wb_path}", file=sys.stderr)
        return 2

    if args.dry_run:
        target_path = wb_path
    else:
        out_path = Path(args.out) if args.out else wb_path.with_name(wb_path.stem + "_repaired.xlsx")
        shutil.copy(wb_path, out_path)
        target_path = out_path

    with zipfile.ZipFile(target_path, "r") as zf:
        if "xl/workbook.xml" not in zf.namelist():
            print("ERROR: xl/workbook.xml not found in package", file=sys.stderr)
            return 2
        wb_xml = zf.read("xl/workbook.xml").decode("utf-8")

    root = ET.fromstring(wb_xml)
    defined_names = root.find(f"{{{NS_MAIN}}}definedNames")
    if defined_names is None:
        print("No <definedNames> element in workbook.xml; nothing to do.")
        return 0

    removed: list[tuple[str, str]] = []
    for dn in list(defined_names):
        text = (dn.text or "").strip()
        name = dn.get("name", "")
        if BROKEN_REF_RE.search(text) or EXTERNAL_LINK_RE.search(text):
            defined_names.remove(dn)
            removed.append((name, text[:120]))

    # Also drop the <definedNames> wrapper if it's now empty (avoids an empty element
    # that some parsers complain about).
    if len(list(defined_names)) == 0:
        root.remove(defined_names)

    if not removed:
        print("No broken or external defined names found. Nothing to repair.")
        return 0

    print(f"Found {len(removed)} broken/external defined name(s):")
    for name, text in removed:
        print(f"  - {name!r:<40s} -> {text}")

    if args.dry_run:
        print("\n--dry-run specified; no changes written.")
        return 0

    new_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)

    # Rewrite the zip with the modified workbook.xml. zipfile doesn't support in-place
    # edits, so build a new archive and replace the original.
    tmp_path = target_path.with_suffix(".tmp" + target_path.suffix)
    with zipfile.ZipFile(target_path, "r") as zin, zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            if item.filename == "xl/workbook.xml":
                zout.writestr(item, new_xml)
            else:
                zout.writestr(item, zin.read(item.filename))
    shutil.move(tmp_path, target_path)
    print(f"\nWrote repaired workbook: {target_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# END repair_broken_named_ranges.py

~~~

## `manifest_lint.py`

~~~python
#!/usr/bin/env python3
"""Lint a RealAI prepared-template manifest for source-policy safety.

The leakage check requires the cleaned workbook to be present (passed via
--cleaned-workbook). When omitted, the check is skipped and the script
behaves as before.

USAGE
-----
  python tp_scripts/manifest_lint.py manifest.md \\
    --cleaned-workbook cleaned_template.xlsx \\
    --out lint_report.json
"""

from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from tp_common import (  # shared primitives; see tp_common.py
    FENCE_RE, ManifestFormatError, load_manifest,
)

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml

try:
    import openpyxl
except ImportError:
    openpyxl = None  # leakage check is skipped if openpyxl is unavailable

HARD_FACT_RE = re.compile(
    r"(unit|rentable|square|sf|parking|rent_roll|in_place|in-place|unit_mix|hard_cost|"
    r"soft_cost|budget|loan|debt|purchase|price|land|capital_stack|address|property\.name|"
    r"total_units)",
    re.I,
)


def walk_writes(cells: dict) -> set[str]:
    refs = set()
    for _, cfg in (cells or {}).items():
        if not isinstance(cfg, dict):
            continue
        for w in cfg.get("writes", []) or []:
            if isinstance(w, dict) and w.get("cell"):
                refs.add(w["cell"])
    return refs


def allowed_cell_refs(allowed: dict) -> set[str]:
    refs = set()
    for item in allowed.get("cells", []) or []:
        if isinstance(item, dict) and item.get("cell"):
            refs.add(item["cell"])
        elif isinstance(item, str):
            refs.add(item)
    return refs


def has_template_default_fallback(cfg: dict) -> bool:
    return (
        cfg.get("template_default_allowed") is True
        or str(cfg.get("default_behavior", "")).lower()
        in {"use_template_default_if_missing", "preserve_existing", "use_template_default"}
        or "template_default" in str(cfg.get("source_policy", "")).lower()
    )


# ── LEAKAGE CHECK ───────────────────────────────────────────────────────────

def _manifest_accounted_cells(manifest: dict) -> set[str]:
    """Return the set of cells the manifest accounts for as legitimate
    remaining values. A cell is accounted if it appears in:

      - cells.<key>.writes[].cell with write_class: protected_default
      - cells.<key>.cell with write_class: protected_default
      - defaults.<key>.cell

    Cells that are merely "writable" (write_class: scalar_input, etc.) do
    NOT account for the cell's REMAINING value — those cells should be
    blank in the cleaned workbook and only get values written at runtime.
    """
    accounted: set[str] = set()
    for _, cfg in (manifest.get("cells") or {}).items():
        if not isinstance(cfg, dict):
            continue
        wp = cfg.get("write_policy") or {}
        write_class = (wp.get("write_class") or cfg.get("write_class") or "").lower()
        if write_class in {"protected_default", "do_not_write"}:
            for w in cfg.get("writes", []) or []:
                if isinstance(w, dict) and w.get("cell"):
                    accounted.add(w["cell"])
            if cfg.get("cell"):
                accounted.add(cfg["cell"])
    for _, cfg in (manifest.get("defaults") or {}).items():
        if isinstance(cfg, dict) and cfg.get("cell"):
            accounted.add(cfg["cell"])
    return accounted


def leakage_scan(manifest: dict, cleaned_workbook_path: str) -> dict:
    """Find non-formula non-text values remaining in the cleaned workbook
    that are NOT accounted for by the manifest as protected defaults.

    Returns a result dict with:
      - leaked: list of {cell, value_class} for unaccounted non-zero values
      - accounted_count: number of remaining values the manifest does justify
      - skipped_zero_count: zero-valued cells (treated as harmless empty slots)
    """
    if openpyxl is None:
        return {"skipped": True, "reason": "openpyxl not installed"}
    accounted = _manifest_accounted_cells(manifest)
    wb = openpyxl.load_workbook(cleaned_workbook_path, data_only=False, keep_links=False)
    leaked: list[dict] = []
    accounted_count = 0
    skipped_zero = 0

    for ws in wb.worksheets:
        if ws.title.startswith("_"):
            continue
        max_row = min(ws.max_row or 0, 8000)
        max_col = min(ws.max_column or 0, 250)
        for row in ws.iter_rows(min_row=1, max_row=max_row, min_col=1, max_col=max_col):
            for cell in row:
                v = cell.value
                if v is None or v == "":
                    continue
                if isinstance(v, str) and v.startswith("="):
                    continue  # formulas are preserved by being formulas
                if isinstance(v, str):
                    continue  # text labels are not numeric leakage
                if isinstance(v, bool):
                    continue
                if not isinstance(v, (int, float)):
                    # datetimes, etc. — treat conservatively as potential leakage
                    coord_full = f"{ws.title}!{cell.coordinate}"
                    if coord_full not in accounted:
                        leaked.append({
                            "cell": coord_full,
                            "value_class": "datetime_or_other",
                        })
                    else:
                        accounted_count += 1
                    continue
                if v == 0:
                    skipped_zero += 1
                    continue
                coord_full = f"{ws.title}!{cell.coordinate}"
                if coord_full in accounted:
                    accounted_count += 1
                    continue
                a = abs(float(v))
                if a < 1:
                    cls = "rate_or_pct"
                elif a >= 1_000_000:
                    cls = "large_number"
                elif a >= 1_000:
                    cls = "medium_number"
                else:
                    cls = "small_number"
                leaked.append({"cell": coord_full, "value_class": cls})

    return {
        "skipped": False,
        "leaked": leaked,
        "leaked_count": len(leaked),
        "accounted_count": accounted_count,
        "skipped_zero_count": skipped_zero,
        "manifest_accounted_cell_count": len(accounted),
    }


def check_mapping_evidence(mf: dict, cell_candidates_path: str) -> list[dict]:
    """Verify manifest mapping_evidence against the deterministic candidate
    records (v4.5). The claim model: every left_label the manifest cites must
    appear among the labels the scan recorded for that cell (left, above, or
    section header; case-insensitive containment either direction), and a cited
    section_header_above must match the recorded one. Evidence the scan never
    saw is fabrication — error, with the actual record attached so the author
    can correct rather than guess."""
    errors: list[dict] = []
    try:
        data = json.loads(Path(cell_candidates_path).read_text(encoding="utf-8"))
    except Exception as exc:
        return [{"code": "cell_candidates_unreadable",
                 "message": f"--cell-candidates file could not be read: {exc}"}]
    recs = {r.get("cell"): r for r in data.get("candidates") or []}

    def label_ok(claim: str, rec: dict) -> bool:
        c = (claim or "").strip().lower()
        if not c:
            return True
        pool = [str(x).strip().lower() for x in
                (rec.get("left_labels") or []) + (rec.get("above_labels") or [])]
        if rec.get("section_header_above"):
            pool.append(str(rec["section_header_above"]).strip().lower())
        return any(c in p or p in c for p in pool if p)

    for key, entry in (mf.get("cells") or {}).items():
        ev = entry.get("mapping_evidence")
        if not isinstance(ev, dict):
            continue
        writes = entry.get("writes") or []
        cells = [w.get("cell") for w in writes if isinstance(w, dict) and w.get("cell")]
        for cell in cells:
            rec = recs.get(cell)
            if rec is None:
                # The cell was blank/formula at scan time (e.g., already cleared
                # when candidates were captured) — nothing to verify against.
                continue
            bad_labels = [l for l in (ev.get("left_labels") or []) if not label_ok(l, rec)]
            claimed_hdr = ev.get("section_header_above")
            hdr_ok = True
            if claimed_hdr:
                actual = (rec.get("section_header_above") or "").strip().lower()
                ch = str(claimed_hdr).strip().lower()
                hdr_ok = bool(actual) and (ch in actual or actual in ch)
            if bad_labels or not hdr_ok:
                errors.append({
                    "code": "mapping_evidence_mismatch",
                    "key": key,
                    "cell": cell,
                    "message": ("mapping_evidence does not match the deterministic candidate record. "
                                "Copy evidence verbatim from cell_candidates.json; do not paraphrase."),
                    "claimed": {"left_labels": ev.get("left_labels"),
                                "section_header_above": claimed_hdr},
                    "actual": {"left_labels": rec.get("left_labels"),
                               "above_labels": rec.get("above_labels"),
                               "section_header_above": rec.get("section_header_above")},
                })
    return errors


def check_cleanup_claims(mf: dict, wb) -> list[dict]:
    """Verify table cleanup claims against the cleaned workbook (v4.5). A
    manifest that misreports what the template contains is the most dangerous
    artifact this pipeline can ship. Checked claim: tables.<key> with
    prior_row_labels_removed: true must have a blank label column over its
    data rows. Requires `label_col` on the table entry; without it the claim
    is unverifiable (warning)."""
    errors: list[dict] = []
    warnings: list[dict] = []
    for key, spec in (mf.get("tables") or {}).items():
        if spec.get("prior_row_labels_removed") is not True:
            continue
        sheet = spec.get("sheet")
        label_col = spec.get("label_col")
        first = spec.get("first_data_row")
        last = spec.get("last_data_row")
        if not (sheet and first and last):
            continue
        if not label_col:
            warnings.append({"code": "label_claim_unverifiable", "key": key,
                             "message": "prior_row_labels_removed: true but no label_col declared; "
                                        "claim cannot be verified against the workbook."})
            continue
        if sheet not in wb.sheetnames:
            errors.append({"code": "cleanup_claim_contradicted", "key": key,
                           "message": f"table sheet {sheet!r} not found in cleaned workbook"})
            continue
        ws = wb[sheet]
        retained = []
        for r in range(int(first), int(last) + 1):
            v = ws[f"{label_col}{r}"].value
            if v not in (None, "") and not (isinstance(v, str) and v.startswith("=")):
                retained.append(f"{label_col}{r}")
        if retained:
            errors.append({
                "code": "cleanup_claim_contradicted",
                "key": key,
                "message": (f"Manifest claims prior_row_labels_removed: true but {len(retained)} "
                            f"label cells remain populated in {sheet}!{label_col} "
                            f"({', '.join(retained[:6])}{'...' if len(retained) > 6 else ''}). "
                            "Either remove the labels or record the retention truthfully "
                            "(prior_row_labels_removed: false, with rationale)."),
                "retained_cells": retained[:50],
            })
    return errors, warnings


def check_unmapped_wide_regions(mf: dict, table_regions_path: str) -> list[dict]:
    """W.14 (v4.4): every detected wide region must be consumable at population
    time — either as a writable `tables` entry or as a `comp_requirements`
    entry whose named runtime skill fills the rectangle. Matching is by sheet
    plus any row overlap, which tolerates off-by-one header decisions between
    the detector and the manifest author."""
    errors: list[dict] = []
    try:
        data = json.loads(Path(table_regions_path).read_text(encoding="utf-8"))
    except Exception as exc:
        return [{"code": "table_regions_unreadable",
                 "message": f"--table-regions file could not be read: {exc}"}]

    def overlaps(sheet, first, last, espec):
        if (espec.get("sheet") or "") != sheet:
            return False
        e_first = espec.get("first_data_row") or espec.get("first_row")
        e_last = espec.get("last_data_row") or espec.get("last_row")
        if e_first is None or e_last is None:
            return False
        try:
            return int(e_first) <= int(last) and int(e_last) >= int(first)
        except (TypeError, ValueError):
            return False

    tables = (mf.get("tables") or {})
    comps = (mf.get("comp_requirements") or {})
    # Escape hatch (v4.5): the wide detector over-detects on dashboard display
    # grids and summary rectangles that are genuinely NOT runtime inputs. The
    # manifest may exclude a detected region by listing it under
    # `excluded_table_regions` with a reason; W.14 respects the exclusion. An
    # exclusion without a reason does not count.
    exclusions = mf.get("excluded_table_regions") or []
    def excluded(sheet, first, last):
        for ex in exclusions:
            if not isinstance(ex, dict) or not (ex.get("reason") or "").strip():
                continue
            if overlaps(sheet, first, last, ex):
                return True
        return False
    for region in data.get("regions", []):
        if region.get("region_kind") != "wide":
            continue
        sheet = region.get("sheet")
        rows = region.get("belong_rows") or []
        if not rows:
            continue
        first, last = min(rows), max(rows)
        if excluded(sheet, first, last):
            continue
        mapped = (any(overlaps(sheet, first, last, t) for t in tables.values())
                  or any(overlaps(sheet, first, last, c) for c in comps.values()))
        if not mapped:
            errors.append({
                "code": "unmapped_table_region",
                "message": (f"Detected wide region {sheet}!rows {first}-{last} is not mapped to "
                            "any `tables` or `comp_requirements` entry (W.14). Map it, or add an "
                            "`excluded_table_regions` entry (sheet, first_row, last_row, reason) "
                            "explaining why it is not a runtime input."),
                "sheet": sheet,
                "first_row": first,
                "last_row": last,
            })
    return errors

# ── WRITE-TARGET FORMULA CHECK ──────────────────────────────────────────────

def write_target_formula_scan(manifest: dict, cleaned_workbook_path: str) -> dict:
    """Confirm every declared write target is a blank / non-formula cell.

    apply_payload.py refuses to overwrite a formula at runtime ("Refusing to
    overwrite formula", exit 4). A manifest that maps an input onto a formula
    cell therefore lints clean on every other check but fails on first use.

    Scans:
      - every cell in allowed_write_surfaces.cells
      - every (mapped table column x declared data row) in tables.<t>

    Returns {formula_targets: [...], cells_checked: N}. Any formula_target is a
    hard lint error.
    """
    if openpyxl is None:
        return {"skipped": True, "reason": "openpyxl not installed"}
    wb = openpyxl.load_workbook(cleaned_workbook_path, data_only=False, keep_links=False)
    formula_targets: list[dict] = []
    checked = 0

    def _is_formula(v: Any) -> bool:
        return isinstance(v, str) and v.startswith("=")

    # 1) scalar write surfaces
    for ref in allowed_cell_refs(manifest.get("allowed_write_surfaces") or {}):
        checked += 1
        if "!" not in ref:
            formula_targets.append({"cell": ref, "kind": "scalar", "error": "unqualified_ref"})
            continue
        sheet, coord = ref.split("!", 1)
        sheet = sheet.strip("'")
        try:
            v = wb[sheet][coord].value
        except Exception as exc:  # noqa: BLE001
            formula_targets.append({"cell": ref, "kind": "scalar", "error": str(exc)})
            continue
        if _is_formula(v):
            formula_targets.append({"cell": ref, "kind": "scalar", "formula": True})

    # 2) table write surfaces — each mapped column across its declared rows.
    #    One formula hit per column is enough to flag the mapping.
    for tname, tdef in (manifest.get("tables") or {}).items():
        if not isinstance(tdef, dict):
            continue
        sheet = tdef.get("sheet")
        first = tdef.get("first_data_row")
        last = tdef.get("last_data_row")
        cols = tdef.get("columns") or {}
        if not (sheet and isinstance(first, int) and isinstance(last, int)):
            continue
        try:
            ws = wb[sheet]
        except Exception:
            formula_targets.append({"table": tname, "sheet": sheet, "error": "sheet_not_found"})
            continue
        for field, spec in cols.items():
            col = spec.get("column") if isinstance(spec, dict) else (spec if isinstance(spec, str) else None)
            if not col or not re.fullmatch(r"[A-Z]{1,3}", str(col)):
                continue
            for r in range(first, last + 1):
                checked += 1
                if _is_formula(ws[f"{col}{r}"].value):
                    formula_targets.append({
                        "table": tname, "field": field, "cell": f"{sheet}!{col}{r}", "formula": True,
                    })
                    break

    return {
        "skipped": False,
        "formula_targets": formula_targets,
        "formula_target_count": len(formula_targets),
        "cells_checked": checked,
    }

# ── ENTRY POINT ─────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest")
    parser.add_argument("--cleaned-workbook",
                        help="Path to the cleaned .xlsx. When provided, runs a leakage scan: "
                             "every remaining numeric value must be accounted for in the manifest "
                             "as a protected default, otherwise the manifest fails lint.")
    parser.add_argument("--cell-candidates",
                        help="Path to cell_candidates.json from candidate_mapping.py. When provided, "
                             "verifies every cells.<key>.mapping_evidence against the deterministic "
                             "candidate record for the written cell. Evidence the workbook scan never "
                             "recorded (paraphrased labels, invented section headers) fails lint with "
                             "mapping_evidence_mismatch — the manifest is a contract, and fabricated "
                             "evidence misleads re-mapping and breaks silently when rows shift.")
    parser.add_argument("--table-regions",
                        help="Path to table_regions.json from candidate_mapping.py. When provided, "
                             "runs the W.14 check: every detected WIDE region must be mapped to a "
                             "manifest `tables` entry or a `comp_requirements` entry (matched by "
                             "sheet + row overlap). A detected wide region the manifest cannot "
                             "populate is a Phase 3 defect — the runner would leave a structural "
                             "table empty with no way to ask for its contents.")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    try:
        mf = load_manifest(args.manifest)
    except ManifestFormatError as exc:
        result = {
            "passed": False,
            "error_count": 1,
            "warning_count": 0,
            "errors": [{
                "code": "manifest_not_machine_readable",
                "message": str(exc),
                "remediation": "Re-emit the manifest as a single fenced YAML block.",
            }],
            "warnings": [],
        }
        Path(args.out).write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps({"status": "failed", "out": args.out, "errors": 1, "warnings": 0}, indent=2))
        return 2

    errors: list[dict] = []
    warnings: list[dict] = []

    if mf.get("manifest_version") not in {3, "3", 4, "4"}:
        warnings.append({"code": "manifest_version", "message": "Expected manifest_version 3 or 4."})

    allowed = mf.get("allowed_write_surfaces") or {}
    if allowed.get("formulas_editable") is not False:
        errors.append({"code": "formulas_editable", "message": "formulas_editable must be false."})

    mapped_refs = walk_writes(mf.get("cells") or {})
    allowed_refs = allowed_cell_refs(allowed)

    # Reverse check: every cell that cells.<key> writes to must be in
    # allowed_write_surfaces.cells. Otherwise the runner would refuse the write.
    missing = sorted(mapped_refs - allowed_refs)
    if missing:
        errors.append({
            "code": "allowed_write_surfaces_missing_cells",
            "message": "Mapped write cells missing from allowed_write_surfaces.",
            "cells": missing,
        })

    # Forward check: every cell in allowed_write_surfaces.cells must have a
    # corresponding cells.<key>.writes[].cell entry. Otherwise the manifest
    # claims a cell is writable but provides no semantic mapping for it — the
    # runner has nowhere to send a value the manifest accepts, so user data
    # silently drops on the floor. (This is a real failure mode observed in
    # production: user supplied a financing input, manifest listed the cell
    # as writable but had no semantic key for it, runner wrote nothing,
    # workbook recalculated against zero.)
    unmapped = sorted(allowed_refs - mapped_refs)
    if unmapped:
        errors.append({
            "code": "unmapped_writable_cells",
            "message": (
                f"{len(unmapped)} cell(s) appear in allowed_write_surfaces.cells but have no "
                f"corresponding cells.<key>.writes[].cell entry. The manifest claims these "
                f"cells are writable but provides no semantic mapping for them; runtime values "
                f"intended for these cells will silently drop. Add a cells entry for each "
                f"(at minimum: semantic_role, write_class, missing_behavior, allowed_sources) "
                f"or remove the cell from allowed_write_surfaces."
            ),
            "cells": unmapped,
        })

    # Hard-fact policy checks. NOTE: with the simplified manifest schema there
    # is no longer a separate runtime_source_plan section; cells carries all
    # of policy + write target. The 'defaults' section is for protected
    # defaults whose value remains in the cleaned workbook.
    for section in ["cells", "defaults"]:
        for key, cfg in (mf.get(section) or {}).items():
            if not isinstance(cfg, dict):
                continue
            blob = f"{key} {cfg.get('semantic_role','')} {cfg.get('source_policy','')}"
            if HARD_FACT_RE.search(blob) and has_template_default_fallback(cfg):
                errors.append({
                    "code": "hard_fact_template_default",
                    "section": section, "key": key,
                    "message": "Hard deal facts cannot allow template default fallback.",
                })
            if HARD_FACT_RE.search(blob) and cfg.get("ai_estimate_allowed") is True:
                errors.append({
                    "code": "hard_fact_ai_estimate",
                    "section": section, "key": key,
                    "message": "Hard deal facts cannot allow AI estimates.",
                })

    # Table-mapping checks
    for key, cfg in (mf.get("tables") or {}).items():
        if not isinstance(cfg, dict):
            continue
        blob = f"{key} {cfg.get('semantic_role','')}"
        if HARD_FACT_RE.search(blob):
            if cfg.get("template_default_allowed") is True:
                errors.append({
                    "code": "table_template_default",
                    "key": key,
                    "message": "Runtime tables cannot allow template fallback.",
                })
            if not (cfg.get("source_policy_by_mode") or cfg.get("source_policy")):
                errors.append({
                    "code": "table_missing_source_policy",
                    "key": key,
                    "message": "Runtime table missing source policy.",
                })

        columns = cfg.get("columns") or {}
        if not isinstance(columns, dict) or not columns:
            errors.append({
                "code": "table_missing_columns",
                "key": key,
                "message": "Runtime table must define a non-empty columns mapping.",
            })
        else:
            reversed_columns = []
            invalid_columns = []
            for field, spec in columns.items():
                if isinstance(spec, dict):
                    if not spec.get("column"):
                        invalid_columns.append(str(field))
                elif isinstance(spec, str):
                    if re.fullmatch(r"[A-Z]{1,3}", str(field)) and not re.fullmatch(r"[A-Z]{1,3}", spec):
                        reversed_columns.append(f"{field}: {spec}")
                else:
                    invalid_columns.append(str(field))

            if reversed_columns:
                errors.append({
                    "code": "table_columns_reversed",
                    "key": key,
                    "message": "Table columns must be field_name: {column: A}, not A: field_name.",
                    "examples": reversed_columns[:10],
                })
            if invalid_columns:
                errors.append({
                    "code": "table_columns_invalid",
                    "key": key,
                    "fields": invalid_columns[:10],
                    "message": "One or more table columns are missing a usable Excel column letter.",
                })

            if cfg.get("clear_policy") not in {
                "clear_rows_and_labels_preserve_schema",
                "clear_existing_rows_preserve_schema",
            }:
                warnings.append({"code": "table_clear_policy", "key": key,
                                 "message": "Runtime table should define clear policy."})

    # ── W.14: UNMAPPED WIDE REGIONS ──────────────────────────────────────
    if args.table_regions:
        errors.extend(check_unmapped_wide_regions(mf, args.table_regions))

    # ── MAPPING-EVIDENCE VERIFICATION (v4.5) ─────────────────────────────
    if args.cell_candidates:
        errors.extend(check_mapping_evidence(mf, args.cell_candidates))

    # ── READY_WITH_LIMITATIONS EVIDENCE REQUIREMENT (v4.5) ───────────────
    # ready_with_limitations is an EARNED status: recalc attempted and write
    # preflight passed, with limitations naming what is deferred. A manifest
    # that defers the checks themselves must be needs_review, not RWL.
    if mf.get("status") == "ready_with_limitations":
        ver = mf.get("verification") or {}
        _recalc_ok = ver.get("recalc_attempted") is True or str(ver.get("recalc_status", "")).lower() in {"engine_unavailable", "deferred_no_recalc_engine"}
        if not _recalc_ok or ver.get("write_preflight_passed") is not True:
            errors.append({
                "code": "rwl_without_verification_evidence",
                "message": ("status ready_with_limitations requires verification.write_preflight_passed: true "
                            "AND either verification.recalc_attempted: true OR a documented recalc deferral "
                            "(verification.recalc_status: engine_unavailable plus a deferral limitation). "
                            "Pending or skipped checks otherwise mean needs_review."),
            })

    # ── LEAKAGE CHECK ────────────────────────────────────────────────────
    leakage_report: dict = {"skipped": True, "reason": "no --cleaned-workbook supplied"}
    if args.cleaned_workbook:
        leakage_report = leakage_scan(mf, args.cleaned_workbook)

        # ── CLEANUP-CLAIM VERIFICATION (v4.5) ────────────────────────────
        if openpyxl is not None:
            try:
                _wb = openpyxl.load_workbook(args.cleaned_workbook, data_only=False, keep_links=False)
                claim_errors, claim_warnings = check_cleanup_claims(mf, _wb)
                errors.extend(claim_errors)
                warnings.extend(claim_warnings)
            except Exception as exc:  # noqa: BLE001
                warnings.append({"code": "cleanup_claims_unverified",
                                 "message": f"could not open cleaned workbook for claim verification: {exc}"})
        if not leakage_report.get("skipped") and leakage_report.get("leaked_count", 0) > 0:
            errors.append({
                "code": "unaccounted_value_leakage",
                "message": (
                    f"{leakage_report['leaked_count']} non-formula numeric values remain in "
                    f"the cleaned workbook but are not accounted for in the manifest as "
                    f"protected defaults. Either clear them in Phase 2, or add manifest "
                    f"entries declaring them as defaults with a real rationale."
                ),
                "sample": leakage_report["leaked"][:20],
            })
    # ── WRITE-TARGET FORMULA CHECK ───────────────────────────────────────
    formula_target_report: dict = {"skipped": True, "reason": "no --cleaned-workbook supplied"}
    if args.cleaned_workbook:
        formula_target_report = write_target_formula_scan(mf, args.cleaned_workbook)
        if not formula_target_report.get("skipped") and formula_target_report.get("formula_target_count", 0) > 0:
            errors.append({
                "code": "write_target_is_formula",
                "message": (
                    f"{formula_target_report['formula_target_count']} declared write target(s) hold a "
                    f"formula in the cleaned workbook. apply_payload.py will refuse to overwrite these "
                    f"at runtime (exit 4). A mapped scalar cell or table column must be a blank, "
                    f"non-formula input cell. Re-map to the true input surface (e.g. the upstream "
                    f"sheet a roll-up references) or remove the target."
                ),
                "sample": formula_target_report["formula_targets"][:20],
            })

    leak_scan = mf.get("leak_scan") or {}
    verification = mf.get("verification") or {}
    status = mf.get("status")
    # apply_payload.py accepts BOTH 'ready' and 'ready_with_limitations' as runnable,
    # so every gate below must apply to both. Gating only 'ready' previously let a
    # never-preflighted, never-recalc'd manifest ship as 'ready_with_limitations'
    # (the Brookwood failure). A manifest whose recalc could not execute must use
    # 'blocked_recalc_execution_failure'; one whose mappings are unresolved must use
    # 'needs_review' — neither is shippable here.
    SHIPPABLE = {"ready", "ready_with_limitations"}
    if status in SHIPPABLE:
        if leak_scan.get("passed") is not True and verification.get("leak_scan_passed") is not True:
            errors.append({"code": f"{status}_without_leak_scan",
                           "message": f"Manifest cannot be {status} without a passed leak scan."})
        if verification.get("workbook_opens_without_repair") is not True:
            errors.append({"code": f"{status}_without_open_repair_check",
                           "message": f"Manifest cannot be {status} unless the workbook opens without repair."})
        if verification.get("write_preflight_passed") is not True:
            errors.append({"code": f"{status}_without_write_preflight",
                           "message": f"Manifest cannot be {status} without a passed write-only preflight."})
        recalc_done = verification.get("recalc_attempted") is True
        recalc_deferred = str(verification.get("recalc_status", "")).lower() in {"engine_unavailable", "deferred_no_recalc_engine"}
        if not (recalc_done or recalc_deferred):
            errors.append({"code": f"{status}_without_recalc_attempt",
                           "message": (f"Manifest cannot be {status} unless recalc was attempted, OR recalc "
                                       f"was deferred because the engine is unavailable (set "
                                       f"verification.recalc_status: engine_unavailable plus a documented "
                                       f"deferral entry in manifest.limitations). If recalc was attempted and "
                                       f"failed or was killed, use 'blocked_recalc_execution_failure'.")})
        if recalc_deferred and not any("defer" in str(l).lower() for l in (mf.get("limitations") or [])):
            errors.append({"code": f"{status}_recalc_deferral_undocumented",
                           "message": (f"verification.recalc_status indicates the economic sniff was deferred, "
                                       f"but manifest.limitations documents no deferral. Add a limitation noting "
                                       f"the economic sniff is deferred to first underwrite.")})
    if status == "ready":
        # Stricter L3 gate reserved for fully-ready manifests.
        if verification.get("formula_recalc_passed") is not True or verification.get("economic_sniff_passed") is not True:
            errors.append({"code": "ready_without_l3",
                           "message": "Manifest cannot be ready without formula recalc and economic sniff."})
    result = {
        "passed": not errors,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "leakage_report": leakage_report,
        "formula_target_report": formula_target_report,
    }
    Path(args.out).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": "passed" if not errors else "failed",
        "out": args.out,
        "errors": len(errors),
        "warnings": len(warnings),
        "leakage_skipped": leakage_report.get("skipped", True),
        "leaked_value_count": leakage_report.get("leaked_count", 0),
    }, indent=2))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())

# END manifest_lint.py
~~~

---

## `sniff_test.py`

~~~python
#!/usr/bin/env python3
"""Excel-skill recalc.py-backed sniff test for prepared Excel templates.

This script writes a sample payload into a temporary workbook, then runs the
Excel skill helper from the Excel skill root:

  cd <excel_skill_root> && python scripts/recalc.py <absolute_workbook> <timeout>

It does not look for or call LibreOffice/soffice directly, and it does not use a
copied recalc.py from tp_scripts.
"""

from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from tp_common import (  # shared primitives; see tp_common.py
    find_excel_skill_root as infer_excel_skill_root, split_cell, FENCE_RE,
    ManifestFormatError, load_manifest, synthesize_payload,
)

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import openpyxl
import yaml

ERROR_VALUES = {"#DIV/0!", "#N/A", "#NAME?", "#NULL!", "#NUM!", "#REF!", "#VALUE!", "#GETTING_DATA"}
# Match yaml/yml fenced blocks specifically; the language tag is required so a JSON sniff-output
# block at the bottom of a prose-style manifest cannot be silently treated as the manifest.


def sample_payload() -> dict:
    return {
        "property": {"name": "SNIFF TEST", "units": 100, "rentable_sf": 85000},
        "capital": {"entry_price": 21370000, "exit_cap": 0.0575, "hold_period_years": 5, "closing_costs_pct": 0.02, "disposition_costs_pct": 0.02},
        "revenue": {"gpr_year0": 2481000, "vacancy_credit_loss_year0": -173000, "other_income_year0": 62000, "rent_growth_pct": 0.031},
        "expenses": {"line_items": {"real_estate_taxes": 267000, "insurance": 91000, "utilities": 112000, "repairs_maintenance": 143000, "management_fees": 94000, "payroll_benefits": 158000, "general_admin": 38000, "advertising_marketing": 17000, "other": 24000}, "expense_growth_pct": 0.026, "reserves_per_unit": 250},
        "financing": {"senior": {"enabled": True, "ltv": 0.65, "rate": 0.061, "amort_years": 30, "io_period_years": 0, "loan_term_years": 10}},
    }


def load_payload(path: str | None) -> dict:
    if not path:
        return sample_payload()
    text = Path(path).read_text(encoding="utf-8")
    if path.lower().endswith(".json"):
        return json.loads(text)
    return yaml.safe_load(text) or {}


def get_path(payload: dict, path: str) -> Any:
    cur: Any = payload
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    if isinstance(cur, dict) and "value" in cur:
        return cur["value"]
    return cur


def apply_transform(value: Any, transform_name: str, manifest: dict) -> Any:
    spec = (manifest.get("transforms") or {}).get(transform_name, {})
    if value is None or not isinstance(spec, dict):
        return value
    op = spec.get("operation")
    if op == "divide":
        return value / spec.get("factor", 1)
    if op == "multiply":
        return value * spec.get("factor", 1)
    if op == "ensure_sign" and isinstance(value, (int, float)):
        return -abs(value) if spec.get("sign") == "negative" else abs(value)
    if op == "lookup":
        return (spec.get("table") or {}).get(value, value)
    return value


def mapping_writes(entry: Any) -> list[dict]:
    if isinstance(entry, str):
        return [{"cell": entry}]
    if isinstance(entry, dict):
        if "writes" in entry:
            return entry.get("writes") or []
        if "cell" in entry:
            return [{"cell": entry["cell"], "transforms": entry.get("transforms", [])}]
    return []


def write_cells(wb, manifest: dict, payload: dict) -> dict:
    result = {"written": [], "missing_required": [], "errors": []}
    for payload_path, entry in (manifest.get("cells") or {}).items():
        value = get_path(payload, payload_path)
        required = bool(entry.get("required", False)) if isinstance(entry, dict) else False
        if value is None:
            default_behavior = entry.get("default_behavior") if isinstance(entry, dict) else None
            if default_behavior == "use_template_default_if_missing":
                continue
            if required:
                result["missing_required"].append(payload_path)
            continue
        for write in mapping_writes(entry):
            out_value = value
            transforms = write.get("transforms") or (entry.get("transforms") if isinstance(entry, dict) else []) or []
            for t in transforms:
                out_value = apply_transform(out_value, t, manifest)
            try:
                sheet, coord = split_cell(write["cell"])
                existing = wb[sheet][coord].value
                if isinstance(existing, str) and existing.startswith("="):
                    # Mirror apply_payload.py's runtime guard (exit 4). Preflight must
                    # fail here too, or it certifies writes the engine rejects.
                    result["errors"].append({
                        "path": payload_path, "cell": write["cell"],
                        "error": "write_target_is_formula",
                        "detail": "target holds a formula; apply_payload.py will refuse this write",
                    })
                    continue
                wb[sheet][coord].value = out_value
                result["written"].append({"path": payload_path, "cell": write["cell"]})
            except Exception as exc:  # noqa: BLE001
                result["errors"].append({"path": payload_path, "cell": write.get("cell"), "error": str(exc)})
    return result


def _unwrap_sourced_value(value: Any) -> Any:
    """Return the primitive value from a sourced RealAI payload leaf.

    Acquisitions payloads may wrap values as:
      {"value": X, "source": "..."}
      {"value": X, "source_class": "...", "source_detail": "...", "confidence": "...", "note": "..."}
      {"value": X}

    For workbook writes, only the primitive X should be written.
    """
    if isinstance(value, dict) and "value" in value:
        return value["value"]
    return value



def _normalize_table_columns(columns: dict) -> tuple[dict, list[str]]:
    """Normalize manifest table columns to {payload_field: column_letter}.

    Preferred manifest shape:
      columns:
        unit_type: {column: B, required: true}
        unit_count: {column: C, required: true}

    Also tolerates the older/reversed shape:
      columns:
        B: unit_type
        C: unit_count

    Returns (normalized_columns, warnings).
    """
    normalized: dict = {}
    warnings: list[str] = []

    if not isinstance(columns, dict):
        return normalized, ["table columns is not a mapping"]

    for key, spec in columns.items():
        # Preferred shape: field_name: {column: B}
        if isinstance(spec, dict):
            col = spec.get("column")
            if not col:
                warnings.append(f"column spec for field {key!r} is missing 'column'")
                continue
            normalized[key] = {
                "column": str(col),
                "required": bool(spec.get("required", False)),
                "source": spec.get("source"),
                "write_class": spec.get("write_class"),
            }
            continue

        # Tolerated legacy/reversed shape: B: unit_type
        if isinstance(spec, str) and isinstance(key, str) and re.fullmatch(r"[A-Z]{1,3}", key):
            warnings.append(
                f"table columns use reversed shape {key}: {spec}; "
                "prefer field_name: {column: A}"
            )
            normalized[spec] = {
                "column": key,
                "required": False,
                "source": None,
                "write_class": None,
            }
            continue

        # Simple shape: field_name: B
        if isinstance(spec, str) and re.fullmatch(r"[A-Z]{1,3}", spec):
            normalized[key] = {
                "column": spec,
                "required": False,
                "source": None,
                "write_class": None,
            }
            continue

        warnings.append(f"unsupported column spec for {key!r}: {type(spec).__name__}")

    return normalized, warnings


def _copy_style_from_template_row(ws, source_row: int, target_row: int, columns: dict) -> None:
    """Preserve formatting when writing rows beyond the prepared row footprint."""
    from copy import copy

    if target_row <= source_row:
        return

    for spec in columns.values():
        col = spec.get("column")
        if not col:
            continue
        src = ws[f"{col}{source_row}"]
        dst = ws[f"{col}{target_row}"]

        if src.has_style:
            dst._style = copy(src._style)
        if src.number_format:
            dst.number_format = src.number_format
        if src.font:
            dst.font = copy(src.font)
        if src.fill:
            dst.fill = copy(src.fill)
        if src.border:
            dst.border = copy(src.border)
        if src.alignment:
            dst.alignment = copy(src.alignment)
        if src.protection:
            dst.protection = copy(src.protection)


def write_tables(wb, manifest: dict, payload: dict) -> dict:
    result = {
        "written_rows": [],
        "written_cells": [],
        "missing_required": [],
        "errors": [],
        "warnings": [],
        "skipped_fields": [],
    }

    for table_name, spec in (manifest.get("tables") or {}).items():
        if not isinstance(spec, dict):
            result["errors"].append({"table": table_name, "error": "table spec is not a mapping"})
            continue

        payload_path = spec.get("payload_path") or f"tables.{table_name}"
        rows = get_path(payload, payload_path)

        if rows is None:
            # Backward compatibility: try table_name at root.
            rows = get_path(payload, table_name)

        is_required = bool(spec.get("required") or spec.get("required_runtime_input"))
        if rows is None:
            if is_required:
                result["missing_required"].append(payload_path)
            continue

        if not isinstance(rows, list):
            result["errors"].append({
                "table": table_name,
                "payload_path": payload_path,
                "error": "payload table value is not a list",
            })
            continue

        try:
            ws = wb[spec["sheet"]]
        except Exception as exc:
            result["errors"].append({"table": table_name, "error": f"sheet not found: {exc}"})
            continue

        start_row = int(spec.get("first_data_row", 2))
        last_data_row = int(spec.get("last_data_row", start_row + len(rows) - 1))
        raw_columns = spec.get("columns", {}) or {}
        columns, warnings = _normalize_table_columns(raw_columns)
        for warning in warnings:
            result["warnings"].append({"table": table_name, "warning": warning})

        if not columns:
            result["errors"].append({"table": table_name, "error": "no usable table columns mapped"})
            continue

        template_style_row = start_row

        for offset, row_data in enumerate(rows):
            excel_row = start_row + offset

            if excel_row > last_data_row:
                if spec.get("overflow_behavior", "copy_template_row") == "block":
                    result["errors"].append({
                        "table": table_name,
                        "excel_row": excel_row,
                        "error": f"payload has more rows than mapped table footprint ending at row {last_data_row}",
                    })
                    continue
                _copy_style_from_template_row(ws, template_style_row, excel_row, columns)

            if not isinstance(row_data, dict):
                result["errors"].append({
                    "table": table_name,
                    "excel_row": excel_row,
                    "error": "table row payload is not a mapping",
                })
                continue

            row_written = 0
            for field, col_spec in columns.items():
                col = col_spec.get("column")
                if not col:
                    continue

                cell_value = _unwrap_sourced_value(row_data.get(field))

                if cell_value in (None, ""):
                    if col_spec.get("required"):
                        result["missing_required"].append(f"{payload_path}[{offset}].{field}")
                    else:
                        result["skipped_fields"].append({
                            "table": table_name,
                            "excel_row": excel_row,
                            "field": field,
                            "reason": "blank_or_missing_optional",
                        })
                    continue

                existing = ws[f"{col}{excel_row}"].value
                if isinstance(existing, str) and existing.startswith("="):
                    result["errors"].append({
                        "table": table_name,
                        "field": field,
                        "cell": f"{spec['sheet']}!{col}{excel_row}",
                        "error": "write_target_is_formula",
                        "detail": "target holds a formula; apply_payload.py will refuse this write",
                    })
                    continue
                ws[f"{col}{excel_row}"].value = cell_value
                row_written += 1
                result["written_cells"].append({
                    "table": table_name,
                    "field": field,
                    "cell": f"{ws.title}!{col}{excel_row}",
                })

            result["written_rows"].append({
                "table": table_name,
                "excel_row": excel_row,
                "written_cell_count": row_written,
            })

        if is_required and not any(r["table"] == table_name and r["written_cell_count"] > 0 for r in result["written_rows"]):
            result["errors"].append({
                "table": table_name,
                "payload_path": payload_path,
                "error": "required runtime table received no written cells",
            })

    return result


def count_errors(path: Path) -> dict:
    wb = openpyxl.load_workbook(path, data_only=True, read_only=False, keep_links=False)
    by_type: dict[str, int] = {}
    by_sheet: dict[str, int] = {}
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if isinstance(cell.value, str) and cell.value in ERROR_VALUES:
                    by_type[cell.value] = by_type.get(cell.value, 0) + 1
                    by_sheet[ws.title] = by_sheet.get(ws.title, 0) + 1
    return {"total": sum(by_type.values()), "by_type": by_type, "by_sheet": by_sheet}


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


def parse_recalc_json(stdout: str) -> dict:
    text = stdout.strip()
    if not text:
        return {}
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        matches = re.findall(r"\{.*\}", text, flags=re.S)
        if not matches:
            return {}
        try:
            data = json.loads(matches[-1])
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}


def run_recalc(input_path: Path, timeout_seconds: int, excel_skill_root: Path | None) -> tuple[bool, dict, str | None]:
    display = "cd <excel_skill_root> && python scripts/recalc.py <absolute_workbook> [timeout_seconds]"
    if excel_skill_root is None:
        return False, {"command": display, "cwd": None}, "Excel skill root not found; cannot execute scripts/recalc.py from its owning skill directory"
    workbook_abs = input_path.resolve()
    cmd = [sys.executable, "scripts/recalc.py", str(workbook_abs), str(timeout_seconds)]
    try:
        proc = subprocess.run(cmd, cwd=str(excel_skill_root), capture_output=True, text=True, timeout=max(timeout_seconds + 45, 90))
    except subprocess.TimeoutExpired:
        return False, {"command": display, "cwd": str(excel_skill_root)}, f"recalc.py timed out after {max(timeout_seconds + 45, 90)} seconds"
    except Exception as exc:
        return False, {"command": display, "cwd": str(excel_skill_root)}, f"recalc.py could not be invoked: {type(exc).__name__}: {exc}"
    meta = parse_recalc_json(proc.stdout)
    meta.update({"command": display, "cwd": str(excel_skill_root), "returncode": proc.returncode})
    if proc.stderr.strip():
        meta["stderr_tail"] = proc.stderr.strip()[-1000:]
    if proc.stdout.strip() and not meta.get("status"):
        meta["stdout_tail"] = proc.stdout.strip()[-1000:]

    # recalc.py contract: a successful run prints JSON with status in {"success","errors_found"}
    # and no top-level "error" key. Failure paths (macro setup failed, file missing, exception in
    # post-recalc inspection) print {"error": "..."} and Python exits 0, so returncode alone is
    # not a reliable signal. Trust the JSON contract over the exit code.
    status = str(meta.get("status", "")).lower()
    recalc_error = meta.get("error")
    status_ok = status in {"success", "errors_found"}
    # 124 is the timeout(1)/gtimeout(1) exit signal that recalc.py treats as continuing-with-
    # inspection; any other nonzero code means recalc.py itself never reached a clean return.
    executed = status_ok and not recalc_error and proc.returncode in (0, 124)

    if not executed:
        if recalc_error:
            msg = f"recalc.py reported error: {recalc_error}"
        elif not status_ok and proc.returncode == 0:
            msg = (
                f"recalc.py exited 0 but returned no recognized status "
                f"(got status={status!r}); treating as failed execution"
            )
        else:
            msg = f"recalc.py exited with code {proc.returncode}"
            if proc.stderr.strip():
                msg += f": {proc.stderr.strip()[-500:]}"
            elif proc.stdout.strip():
                msg += f": {proc.stdout.strip()[-500:]}"
        return False, meta, msg
    return True, meta, None


def read_output_values(path: Path, manifest: dict) -> dict:
    wb = openpyxl.load_workbook(path, data_only=True, read_only=False, keep_links=False)
    values = {}
    for name, spec in (manifest.get("outputs") or {}).items():
        cell_ref = spec.get("cell") if isinstance(spec, dict) else spec
        if not cell_ref:
            continue
        try:
            sheet, coord = split_cell(cell_ref)
            values[name] = wb[sheet][coord].value
        except Exception as exc:
            values[name] = {"error": str(exc)}
    return values


def as_number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace(",", "").replace("%", "")) / (100 if "%" in value else 1)
        except ValueError:
            return None
    return None


def maybe_scale_output(value: float, manifest: dict) -> float:
    """Apply convention-derived currency scale if the output cell is suspiciously small for its
    expected magnitude. Used as a fallback when the manifest doesn't declare an explicit
    read-side transform."""
    conv = manifest.get("conventions") or {}
    scale = conv.get("output_currency_scale") or conv.get("currency_scale") or conv.get("units")
    if scale == "$000" and abs(value) < 100_000:
        return value * 1000
    if scale == "$M" and abs(value) < 1_000:
        return value * 1_000_000
    return value


def _payload_noi_components(payload: dict) -> dict | None:
    """Extract the four payload values needed for the Year 1 NOI identity. Returns None if
    any of revenue or expenses is missing — the claims-based check requires all four."""
    gpr = as_number(get_path(payload, "revenue.gpr_year0"))
    vacancy = as_number(get_path(payload, "revenue.vacancy_credit_loss_year0"))
    other = as_number(get_path(payload, "revenue.other_income_year0"))
    line_items = get_path(payload, "expenses.line_items") or {}
    if not isinstance(line_items, dict) or not line_items:
        return None
    opex = sum(abs(as_number(v) or 0.0) for v in line_items.values())
    return {
        "gpr": gpr or 0.0,
        "vacancy": vacancy or 0.0,
        "other": other or 0.0,
        "opex": opex,
    }


def _select_noi_output(manifest: dict, outputs: dict) -> tuple[str | None, float | None]:
    """Identify the Year 1 NOI output cell from the manifest and read its post-recalc value.
    Apply any read-side transforms declared on the output. Returns (key, value) or (None, None)."""
    output_specs = manifest.get("outputs") or {}
    noi_key = None
    for name, spec in output_specs.items():
        nm = name.lower()
        if "noi" in nm and ("year1" in nm or "year_1" in nm or "yr1" in nm or "year 1" in nm or nm == "noi" or nm.endswith("_noi")):
            noi_key = name
            break
    if noi_key is None:
        # Fall back to any output named noi anywhere
        for name in output_specs:
            if "noi" in name.lower():
                noi_key = name
                break
    if noi_key is None:
        return None, None
    raw = outputs.get(noi_key)
    val = as_number(raw)
    if val is None:
        return noi_key, None
    spec = output_specs.get(noi_key) or {}
    if isinstance(spec, dict):
        for transform in spec.get("transforms", []) or []:
            val = apply_transform(val, transform, manifest)
    val = maybe_scale_output(val, manifest)
    return noi_key, val


def _build_claims_payload(payload: dict, manifest: dict, outputs: dict) -> dict | None:
    """Build a claims.json structure for the xlsx-skill workbook_claims_check.py.

    Implements the SKILL's dual-provenance protocol: the workbook's displayed Year 1 NOI
    cell is treated as a fact AND used as the expected value for the payload-derived
    reconciliation. If they don't match within tolerance, claims_check fails.
    """
    components = _payload_noi_components(payload)
    if components is None:
        return None
    noi_key, workbook_noi = _select_noi_output(manifest, outputs)
    if noi_key is None or workbook_noi is None:
        return None
    abs_tol = max(abs(workbook_noi) * 0.03, 1000.0)
    return {
        "values": {
            "gpr": components["gpr"],
            "vacancy": components["vacancy"],
            "other": components["other"],
            "opex": components["opex"],
        },
        "facts": [
            {"id": "fact_gpr", "label": "Gross Potential Rent (Yr 1)", "value": components["gpr"], "source_sheet": "payload", "source_range": "revenue.gpr_year0", "extraction_method": "payload"},
            {"id": "fact_vacancy", "label": "Vacancy/Credit Loss (Yr 1)", "value": components["vacancy"], "source_sheet": "payload", "source_range": "revenue.vacancy_credit_loss_year0", "extraction_method": "payload"},
            {"id": "fact_other", "label": "Other Income (Yr 1)", "value": components["other"], "source_sheet": "payload", "source_range": "revenue.other_income_year0", "extraction_method": "payload"},
            {"id": "fact_opex", "label": "Sum of expense line items (Yr 1)", "value": components["opex"], "source_sheet": "payload", "source_range": "expenses.line_items", "extraction_method": "payload_sum"},
            {"id": "fact_workbook_noi", "label": f"Workbook output: {noi_key}", "value": workbook_noi, "source_sheet": "manifest.outputs", "source_range": noi_key, "extraction_method": "post_recalc_read"},
        ],
        "claims": [
            {
                "id": "claim_year1_noi_reconciliation",
                "name": "year1_noi_reconciliation",
                "expr": "gpr + vacancy + other - opex",
                "expected": workbook_noi,
                "tolerance": abs_tol,
                "based_on_facts": ["fact_gpr", "fact_vacancy", "fact_other", "fact_opex", "fact_workbook_noi"],
                "derivation": (
                    "Year 1 NOI computed from payload economic identity; expected value is the "
                    "workbook's displayed NOI cell after recalc (dual-provenance reconciliation per "
                    "xlsx-skill anti-smoothing protocol)."
                ),
            },
        ],
    }


def _run_claims_check(claims_path: Path, skill_root: Path) -> dict:
    """Invoke workbook_claims_schema_check.py then workbook_claims_check.py on a temp claims.json.
    Returns a status dict the caller can store in the sniff result."""
    schema_check = skill_root / "scripts" / "workbook_claims_schema_check.py"
    main_check = skill_root / "scripts" / "workbook_claims_check.py"
    if not (schema_check.exists() and main_check.exists()):
        return {"status": "helpers_missing", "looked_in": str(skill_root / "scripts")}
    try:
        schema_proc = subprocess.run(
            [sys.executable, str(schema_check), str(claims_path)],
            capture_output=True, text=True, timeout=30,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return {"status": "schema_invocation_failed", "reason": f"{type(exc).__name__}: {exc}"}
    if schema_proc.returncode != 0:
        return {
            "status": "schema_failed",
            "returncode": schema_proc.returncode,
            "stdout_tail": (schema_proc.stdout or "")[-500:],
            "stderr_tail": (schema_proc.stderr or "")[-500:],
        }
    try:
        check_proc = subprocess.run(
            [sys.executable, str(main_check), str(claims_path)],
            capture_output=True, text=True, timeout=60,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return {"status": "check_invocation_failed", "reason": f"{type(exc).__name__}: {exc}"}
    return {
        "status": "passed" if check_proc.returncode == 0 else "failed",
        "returncode": check_proc.returncode,
        "stdout_tail": (check_proc.stdout or "")[-2000:],
        "stderr_tail": (check_proc.stderr or "")[-500:] if check_proc.stderr else None,
    }


def economic_checks(outputs: dict, manifest: dict, payload: dict, skill_root: Path | None = None) -> dict:
    """Reconcile payload-derived Year 1 NOI against the workbook's displayed NOI cell.

    Primary path: build a claims.json and run xlsx-skill workbook_claims_check.py for
    proper dual-provenance reconciliation with absolute-tolerance semantics.

    Fallback (when claims helpers are unreachable): inline reconciliation using the same
    expression and tolerance the claims_check would apply, so the verdict is consistent.
    """
    checks: dict = {"passed": False, "checks": [], "blocking_reasons": []}

    claims_doc = _build_claims_payload(payload, manifest, outputs)
    if claims_doc is None:
        checks["blocking_reasons"].append(
            "Insufficient inputs for NOI reconciliation: need both a Year 1 NOI output mapping "
            "and a payload with revenue.gpr_year0 + revenue.vacancy_credit_loss_year0 + "
            "revenue.other_income_year0 + expenses.line_items. Missing one or more."
        )
        return checks

    payload_noi_expr_value = (
        claims_doc["values"]["gpr"]
        + claims_doc["values"]["vacancy"]
        + claims_doc["values"]["other"]
        - claims_doc["values"]["opex"]
    )
    workbook_noi = claims_doc["claims"][0]["expected"]
    tolerance = claims_doc["claims"][0]["tolerance"]
    delta = abs(payload_noi_expr_value - workbook_noi)

    # Try claims_check first
    claims_result = None
    if skill_root is not None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tf:
            json.dump(claims_doc, tf, indent=2)
            tf_path = tf.name
        try:
            claims_result = _run_claims_check(Path(tf_path), skill_root)
        finally:
            try:
                Path(tf_path).unlink()
            except OSError:
                pass
        checks["claims_check"] = claims_result
        if claims_result and claims_result.get("status") == "passed":
            checks["passed"] = True
            checks["checks"].append({
                "name": "year1_noi_reconciliation",
                "method": "workbook_claims_check",
                "payload_derived": payload_noi_expr_value,
                "workbook_value": workbook_noi,
                "delta_abs": delta,
                "tolerance_abs": tolerance,
                "result": "pass",
            })
            return checks
        if claims_result and claims_result.get("status") == "failed":
            checks["blocking_reasons"].append(
                "workbook_claims_check.py reported failure on year1_noi_reconciliation; "
                "see economic_checks.claims_check.stdout_tail for the per-claim breakdown."
            )
            checks["checks"].append({
                "name": "year1_noi_reconciliation",
                "method": "workbook_claims_check",
                "payload_derived": payload_noi_expr_value,
                "workbook_value": workbook_noi,
                "delta_abs": delta,
                "tolerance_abs": tolerance,
                "result": "fail",
            })
            return checks
        # Otherwise fall through to inline fallback (helpers_missing, schema_failed,
        # or invocation errors).

    passed = delta <= tolerance
    checks["checks"].append({
        "name": "year1_noi_reconciliation",
        "method": "inline_fallback",
        "payload_derived": payload_noi_expr_value,
        "workbook_value": workbook_noi,
        "delta_abs": delta,
        "tolerance_abs": tolerance,
        "result": "pass" if passed else "fail",
        "fallback_reason": (
            "claims_check helpers unreachable — used inline reconciliation with same expr/tolerance"
            if claims_result and claims_result.get("status") in {"helpers_missing", "schema_failed", "schema_invocation_failed", "check_invocation_failed"}
            else "no skill root provided; inline reconciliation"
        ),
    })
    checks["passed"] = passed
    if not passed:
        checks["blocking_reasons"].append(
            f"Year 1 NOI reconciliation: payload-derived {payload_noi_expr_value:,.0f} vs "
            f"workbook {workbook_noi:,.0f}; delta {delta:,.0f} exceeds tolerance {tolerance:,.0f}"
        )
    return checks


def missing_runtime_tables(manifest: dict, payload: dict) -> list[str]:
    missing: list[str] = []
    for table_name, spec in (manifest.get("tables") or {}).items():
        if not isinstance(spec, dict):
            continue
        is_runtime = bool(spec.get("required_runtime_input") or spec.get("required_for_full_economic_verification"))
        if not is_runtime:
            continue
        payload_path = spec.get("payload_path") or table_name
        if not get_path(payload, payload_path):
            missing.append(table_name)
    return missing


def classify_readiness(after_errors: dict, recalc_meta: dict, econ: dict, outputs: dict, runtime_missing: list[str]) -> tuple[str, str, bool, list[str]]:
    status = str(recalc_meta.get("status", "")).lower()
    has_errors = after_errors["total"] > 0 or status in {"errors_found", "error", "failed"}

    # Pass condition: clean recalc, economic check passed, at least one output read.
    if not has_errors and econ["passed"] and bool(outputs):
        return "passed", "L3_economic_sniff_passed", True, []

    # ready_with_limitations: recalc executed and the only failures trace to required runtime
    # tables that were not populated in the sniff payload. The economic check may still have
    # failed (NOI reconciliation needs unit-mix-driven revenue to make sense), so we tolerate
    # econ.passed=False here as long as the runtime-missing tables explain it.
    if has_errors and runtime_missing:
        return "ready_with_limitations", "L2_formula_reevaluated_runtime_inputs_missing", False, [
            "Formula reevaluation executed, but required runtime tables were not populated in the sniff payload.",
            "Promote to ready_with_limitations only after documenting those tables and confirming remaining errors are runtime-input-driven, not structural.",
        ]

    # Distinguish "no economic check performed" (insufficient inputs) from "economic check ran
    # and failed". The first is benign when runtime tables are also missing; the second is real.
    blocking_econ = econ.get("blocking_reasons") or []
    no_check_blocked_by_inputs = (
        not econ["passed"]
        and any("Insufficient inputs" in r for r in blocking_econ)
    )
    if not has_errors and no_check_blocked_by_inputs and bool(outputs):
        return "ready_with_limitations", "L2_formula_reevaluated_econ_check_skipped_for_input_shape", False, [
            "Formula reevaluation passed and outputs are readable, but the NOI reconciliation "
            "could not run because the sniff payload lacks revenue/expense components. This is a "
            "documented limitation for unit-mix-driven payloads; mark ready only after a full "
            "payload-shape sniff or human review.",
        ]

    return "failed_formula_or_economic_checks", "L2_formula_reevaluated_not_economically_verified", False, []


def run(input_file: str, manifest_file: str, payload_file: str | None, out_file: str | None, recalc_timeout: int) -> dict:
    manifest = load_manifest(manifest_file)
    payload = load_payload(payload_file) if payload_file else synthesize_payload(manifest)
    baseline_errors = count_errors(Path(input_file))
    excel_skill_root = infer_excel_skill_root()

    with tempfile.TemporaryDirectory() as td:
        written_path = Path(td) / "sniff_written.xlsx"
        wb = openpyxl.load_workbook(input_file, data_only=False, keep_links=False)
        cell_result = write_cells(wb, manifest, payload)
        table_result = write_tables(wb, manifest, payload)
        wb.save(written_path)
        if out_file:
            shutil.copyfile(written_path, out_file)
        if cell_result["errors"] or table_result["errors"] or cell_result["missing_required"] or table_result["missing_required"]:
            return {"status": "failed_write_preflight", "verification_level": "L1_write_only_preflight_failed", "production_ready": False, "cells": cell_result, "tables": table_result}

        executed, recalc_meta, recalc_error = run_recalc(written_path, recalc_timeout, excel_skill_root)
        if not executed:
            return {
                "status": "blocked_recalc_execution_failure",
                "verification_level": "L1_write_only_preflight",
                "production_ready": False,
                "execution_blocker": "recalc_py_failed_or_not_executed",
                "reason": recalc_error,
                "formula_recalc_method": "excel_skill_scripts_recalc_py_from_excel_skill_root",
                "formula_recalc_command": "cd <excel_skill_root> && python scripts/recalc.py <absolute_workbook> [timeout_seconds]",
                "formula_recalc_attempted": True,
                "recalc_result": recalc_meta,
                "baseline_errors": baseline_errors,
                "cells": cell_result,
                "tables": table_result,
            }

        if out_file:
            shutil.copyfile(written_path, out_file)
        after_errors = count_errors(written_path)
        outputs = read_output_values(written_path, manifest)
        econ = economic_checks(outputs, manifest, payload, skill_root=excel_skill_root)
        runtime_missing = missing_runtime_tables(manifest, payload)
        status, level, production_ready, notes = classify_readiness(after_errors, recalc_meta, econ, outputs, runtime_missing)
        return {
            "status": status,
            "verification_level": level,
            "production_ready": production_ready,
            "formula_recalc_method": "excel_skill_scripts_recalc_py_from_excel_skill_root",
            "formula_recalc_command": "cd <excel_skill_root> && python scripts/recalc.py <absolute_workbook> [timeout_seconds]",
            "formula_recalc_attempted": True,
            "recalc_result": recalc_meta,
            "output_file": out_file,
            "baseline_errors": baseline_errors,
            "after_errors": after_errors,
            "new_error_count": max(0, after_errors["total"] - baseline_errors["total"]),
            "outputs_read": outputs,
            "economic_checks": econ,
            "missing_runtime_tables": runtime_missing,
            "readiness_notes": notes,
            "cells": cell_result,
            "tables": table_result,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_file")
    parser.add_argument("manifest_file")
    parser.add_argument("--payload")
    parser.add_argument("--out")
    parser.add_argument("--recalc-timeout", type=int, default=120)
    args = parser.parse_args()
    result = run(args.input_file, args.manifest_file, args.payload, args.out, args.recalc_timeout)
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# END sniff_test.py
~~~

## `verify_write_preflight.py`

~~~python
#!/usr/bin/env python3
"""Write-only manifest preflight. This does not recalculate formulas."""

from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from tp_common import (  # shared primitives; see tp_common.py
    split_cell, FENCE_RE, synthesize_payload,
)

import argparse
import json
import re
from copy import copy
from pathlib import Path
from typing import Any

import openpyxl
import yaml

# Match yaml/yml fenced blocks specifically; the language tag is required so a JSON sniff-output
# block at the bottom of a prose-style manifest cannot be silently treated as the manifest.


class ManifestFormatError(ValueError):
    """Raised when the manifest file is not a single fenced YAML block with manifest content."""


def load_yaml_or_md(path: str) -> dict:
    text = Path(path).read_text(encoding="utf-8")
    blocks = [content for _tag, content in FENCE_RE.findall(text)]
    if not blocks:
        raise ManifestFormatError(
            f"No fenced YAML block found in {path}. The manifest must be a markdown file "
            f"containing a single fenced YAML block (```yaml ... ```)."
        )
    blocks.sort(key=len, reverse=True)
    try:
        data = yaml.safe_load(blocks[0]) or {}
    except yaml.YAMLError as exc:
        raise ManifestFormatError(f"Largest YAML block in {path} did not parse: {exc}") from exc
    if not isinstance(data, dict):
        raise ManifestFormatError(
            f"Manifest YAML block in {path} did not parse to a mapping/dict; "
            f"got {type(data).__name__}."
        )
    if not (data.get("cells") or data.get("tables") or data.get("outputs")):
        raise ManifestFormatError(
            f"Manifest in {path} is parseable YAML but contains no 'cells', 'tables', or "
            f"'outputs' sections; preflight cannot write anything against it."
        )
    return data


def load_payload(path: str | None) -> dict:
    if not path:
        return sample_payload()
    text = Path(path).read_text(encoding="utf-8")
    if path.lower().endswith(".json"):
        return json.loads(text)
    return yaml.safe_load(text) or {}


def sample_payload() -> dict:
    return {
        "property": {"name": "SNIFF TEST", "units": 100, "rentable_sf": 85000},
        "capital": {"entry_price": 21370000, "exit_cap": 0.0575, "hold_period_years": 5, "closing_costs_pct": 0.02, "disposition_costs_pct": 0.02},
        "revenue": {"gpr_year0": 2481000, "vacancy_credit_loss_year0": -173000, "other_income_year0": 62000, "rent_growth_pct": 0.031},
        "expenses": {"line_items": {"real_estate_taxes": 267000, "insurance": 91000, "utilities": 112000, "repairs_maintenance": 143000, "management_fees": 94000, "payroll_benefits": 158000, "general_admin": 38000, "advertising_marketing": 17000, "other": 24000}, "expense_growth_pct": 0.026, "reserves_per_unit": 250},
        "financing": {"senior": {"enabled": True, "ltv": 0.65, "rate": 0.061, "amort_years": 30, "io_period_years": 0, "loan_term_years": 10}},
    }


def get_path(payload: dict, path: str) -> Any:
    cur: Any = payload
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    if isinstance(cur, dict) and "value" in cur:
        return cur["value"]
    return cur


def apply_transform(value: Any, transform_name: str, manifest: dict) -> Any:
    transforms = manifest.get("transforms", {}) or {}
    spec = transforms.get(transform_name, {}) if isinstance(transforms, dict) else {}
    op = spec.get("operation")
    if value is None or not spec:
        return value
    if op == "divide":
        return value / spec.get("factor", 1)
    if op == "multiply":
        return value * spec.get("factor", 1)
    if op == "ensure_sign":
        sign = spec.get("sign")
        if isinstance(value, (int, float)):
            return -abs(value) if sign == "negative" else abs(value)
    if op == "lookup":
        return (spec.get("table") or {}).get(value, value)
    return value


def mapping_writes(entry: Any) -> list[dict]:
    if isinstance(entry, str):
        return [{"cell": entry}]
    if isinstance(entry, dict):
        if "writes" in entry:
            return entry["writes"] or []
        if "cell" in entry:
            return [{"cell": entry["cell"], "transforms": entry.get("transforms", [])}]
    return []


def write_cells(wb, manifest: dict, payload: dict) -> dict:
    result = {"written": [], "missing_required": [], "skipped": [], "errors": []}
    for payload_path, entry in (manifest.get("cells") or {}).items():
        value = get_path(payload, payload_path)
        required = bool(entry.get("required", False)) if isinstance(entry, dict) else False
        if value is None:
            default_behavior = entry.get("default_behavior") if isinstance(entry, dict) else None
            if default_behavior == "use_template_default_if_missing":
                result["skipped"].append({"path": payload_path, "reason": "using_template_default"})
                continue
            if required:
                result["missing_required"].append(payload_path)
            continue
        for write in mapping_writes(entry):
            out_value = value
            transforms = write.get("transforms") or (entry.get("transforms") if isinstance(entry, dict) else []) or []
            for t in transforms:
                out_value = apply_transform(out_value, t, manifest)
            try:
                sheet, coord = split_cell(write["cell"])
                wb[sheet][coord].value = out_value
                result["written"].append({"path": payload_path, "cell": write["cell"]})
            except Exception as exc:  # noqa: BLE001
                result["errors"].append({"path": payload_path, "cell": write.get("cell"), "error": str(exc)})
    return result


def _normalize_table_columns(columns: dict) -> tuple[dict, list[str]]:
    """Normalize manifest table columns to {payload_field: column_letter}.

    Preferred manifest shape:
      columns:
        unit_type: {column: B, required: true}
        unit_count: {column: C, required: true}

    Also tolerates the older/reversed shape:
      columns:
        B: unit_type
        C: unit_count

    Returns (normalized_columns, warnings).
    """
    normalized: dict = {}
    warnings: list[str] = []

    if not isinstance(columns, dict):
        return normalized, ["table columns is not a mapping"]

    for key, spec in columns.items():
        # Preferred shape: field_name: {column: B}
        if isinstance(spec, dict):
            col = spec.get("column")
            if not col:
                warnings.append(f"column spec for field {key!r} is missing 'column'")
                continue
            normalized[key] = {
                "column": str(col),
                "required": bool(spec.get("required", False)),
                "source": spec.get("source"),
                "write_class": spec.get("write_class"),
            }
            continue

        # Tolerated legacy/reversed shape: B: unit_type
        if isinstance(spec, str) and isinstance(key, str) and re.fullmatch(r"[A-Z]{1,3}", key):
            warnings.append(
                f"table columns use reversed shape {key}: {spec}; "
                "prefer field_name: {column: A}"
            )
            normalized[spec] = {
                "column": key,
                "required": False,
                "source": None,
                "write_class": None,
            }
            continue

        # Simple shape: field_name: B
        if isinstance(spec, str) and re.fullmatch(r"[A-Z]{1,3}", spec):
            normalized[key] = {
                "column": spec,
                "required": False,
                "source": None,
                "write_class": None,
            }
            continue

        warnings.append(f"unsupported column spec for {key!r}: {type(spec).__name__}")

    return normalized, warnings


def _copy_style_from_template_row(ws, source_row: int, target_row: int, columns: dict) -> None:
    """Preserve formatting when writing rows beyond the prepared row footprint."""
    from copy import copy

    if target_row <= source_row:
        return

    for spec in columns.values():
        col = spec.get("column")
        if not col:
            continue
        src = ws[f"{col}{source_row}"]
        dst = ws[f"{col}{target_row}"]

        if src.has_style:
            dst._style = copy(src._style)
        if src.number_format:
            dst.number_format = src.number_format
        if src.font:
            dst.font = copy(src.font)
        if src.fill:
            dst.fill = copy(src.fill)
        if src.border:
            dst.border = copy(src.border)
        if src.alignment:
            dst.alignment = copy(src.alignment)
        if src.protection:
            dst.protection = copy(src.protection)

def _unwrap_sourced_value(value: Any) -> Any:
    if isinstance(value, dict) and "value" in value:
        return value["value"]
    return value




def write_tables(wb, manifest: dict, payload: dict) -> dict:
    result = {
        "written_rows": [],
        "written_cells": [],
        "missing_required": [],
        "errors": [],
        "warnings": [],
        "skipped_fields": [],
    }

    for table_name, spec in (manifest.get("tables") or {}).items():
        if not isinstance(spec, dict):
            result["errors"].append({"table": table_name, "error": "table spec is not a mapping"})
            continue

        payload_path = spec.get("payload_path") or f"tables.{table_name}"
        rows = get_path(payload, payload_path)

        if rows is None:
            # Backward compatibility: try table_name at root.
            rows = get_path(payload, table_name)

        is_required = bool(spec.get("required") or spec.get("required_runtime_input"))
        if rows is None:
            if is_required:
                result["missing_required"].append(payload_path)
            continue

        if not isinstance(rows, list):
            result["errors"].append({
                "table": table_name,
                "payload_path": payload_path,
                "error": "payload table value is not a list",
            })
            continue

        try:
            ws = wb[spec["sheet"]]
        except Exception as exc:
            result["errors"].append({"table": table_name, "error": f"sheet not found: {exc}"})
            continue

        start_row = int(spec.get("first_data_row", 2))
        last_data_row = int(spec.get("last_data_row", start_row + len(rows) - 1))
        raw_columns = spec.get("columns", {}) or {}
        columns, warnings = _normalize_table_columns(raw_columns)
        for warning in warnings:
            result["warnings"].append({"table": table_name, "warning": warning})

        if not columns:
            result["errors"].append({"table": table_name, "error": "no usable table columns mapped"})
            continue

        template_style_row = start_row

        for offset, row_data in enumerate(rows):
            excel_row = start_row + offset

            if excel_row > last_data_row:
                if spec.get("overflow_behavior", "copy_template_row") == "block":
                    result["errors"].append({
                        "table": table_name,
                        "excel_row": excel_row,
                        "error": f"payload has more rows than mapped table footprint ending at row {last_data_row}",
                    })
                    continue
                _copy_style_from_template_row(ws, template_style_row, excel_row, columns)

            if not isinstance(row_data, dict):
                result["errors"].append({
                    "table": table_name,
                    "excel_row": excel_row,
                    "error": "table row payload is not a mapping",
                })
                continue

            row_written = 0
            for field, col_spec in columns.items():
                col = col_spec.get("column")
                if not col:
                    continue

                cell_value = _unwrap_sourced_value(row_data.get(field))

                if cell_value in (None, ""):
                    if col_spec.get("required"):
                        result["missing_required"].append(f"{payload_path}[{offset}].{field}")
                    else:
                        result["skipped_fields"].append({
                            "table": table_name,
                            "excel_row": excel_row,
                            "field": field,
                            "reason": "blank_or_missing_optional",
                        })
                    continue

                ws[f"{col}{excel_row}"].value = cell_value
                row_written += 1
                result["written_cells"].append({
                    "table": table_name,
                    "field": field,
                    "cell": f"{ws.title}!{col}{excel_row}",
                })

            result["written_rows"].append({
                "table": table_name,
                "excel_row": excel_row,
                "written_cell_count": row_written,
            })

        if is_required and not any(r["table"] == table_name and r["written_cell_count"] > 0 for r in result["written_rows"]):
            result["errors"].append({
                "table": table_name,
                "payload_path": payload_path,
                "error": "required runtime table received no written cells",
            })

    return result

def run(input_file: str, manifest_file: str, payload_file: str | None, out_file: str) -> dict:
    manifest = load_yaml_or_md(manifest_file)
    payload = load_payload(payload_file) if payload_file else synthesize_payload(manifest)
    wb = openpyxl.load_workbook(input_file, data_only=False, keep_links=False)
    cell_result = write_cells(wb, manifest, payload)
    table_result = write_tables(wb, manifest, payload)
    wb.save(out_file)
    return {
        "status": "passed" if not cell_result["errors"] and not table_result["errors"] and not cell_result["missing_required"] and not table_result["missing_required"] else "failed",
        "verification_level": "L1_write_only_preflight",
        "production_ready": False,
        "output_file": out_file,
        "cells": cell_result,
        "tables": table_result,
        "note": "Write-only preflight does not validate formulas or economics.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_file")
    parser.add_argument("manifest_file")
    parser.add_argument("--payload")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = run(args.input_file, args.manifest_file, args.payload, args.out)
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# END verify_write_preflight.py
~~~

## `xlsm_triage_convert.py`

~~~python
#!/usr/bin/env python3
"""xlsm triage gate: analyze the VBA project, scan it for deal-data leakage,
and — when deterministic proof obligations hold — emit a macro-stripped .xlsx
that the rest of the template-preparation pipeline consumes unchanged.

Stdlib only (zipfile + a minimal MS-CFB walker + MS-OVBA decompressor). No
macro is ever EXECUTED; the VBA project is read as data.

Verdicts
--------
  strippable      All proof obligations hold. With --convert-out, the script
                  writes the stripped .xlsx (openpyxl round-trip WITHOUT
                  keep_vba, which drops vbaProject.bin, the macro content
                  type, and legacy form-control buttons). Continue the normal
                  pipeline on the converted file; record the removed-macro
                  inventory in _PreparationAudit.

  needs_review    VBA contains Function procedures (potential UDFs) that are
                  NOT referenced by any sheet formula, or event handlers that
                  do not write cell values on inspection. A human (or the LLM
                  with user approval) must confirm the macros are cosmetic
                  before conversion. Re-run with --approve-strip after
                  approval.

  not_strippable  Sheet formulas call VBA Functions (the model's math depends
                  on macro code the converted workbook cannot execute), or
                  auto-exec code mutates cell values. The template cannot be
                  prepared from this file; the user must supply a formula-only
                  version or accept loss of the macro-computed outputs.

Proof obligations for `strippable`
----------------------------------
  P1  No Function procedures anywhere in the VBA project
      (Sub procedures cannot be called from formulas).
  P2  No formula in any sheet references any VBA Function name.
      (Vacuously true under P1; checked independently so P1 relaxation via
      --approve-strip still gets formula protection.)
  P3  No auto-exec entry points: Workbook_Open, Auto_Open/Auto_Close,
      Workbook_BeforeClose/BeforeSave, Worksheet_Change,
      Worksheet_Calculate, Application.OnTime, Application.Run.
  P4  No external-effect calls: Shell, CreateObject, GetObject,
      URLDownloadToFile, Environ, FileSystemObject, Declare (Win32).
      These don't block stripping (the code is removed either way) but they
      are reported — their presence usually means the model has behavior the
      owner should know is being dropped.

VBA leak scan
-------------
Deal strings (pass --decisions-json with a deal_strings array, same file the
post-clean leak scan consumes) are searched in the decompressed VBA source.
A hit is a blocking finding: the macro code itself carries prior-deal data
and must not ship in any form (stripping removes it, but the finding is
recorded in the report and must land in _PreparationAudit).

Usage
-----
  python tp_scripts/xlsm_triage_convert.py model.xlsm \
      --out xlsm_report.json \
      [--decisions-json decisions.json] \
      [--convert-out model_converted.xlsx] \
      [--approve-strip]

Exit codes: 0 strippable (and converted if requested), 3 needs_review,
2 not_strippable or error.
"""
from __future__ import annotations

import argparse
import json
import re
import struct
import sys
import zipfile
from pathlib import Path


# ── MS-CFB (minimal) ────────────────────────────────────────────────────────

CFB_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
FREESECT = {0xFFFFFFFE, 0xFFFFFFFF}


class CFB:
    def __init__(self, data: bytes):
        if data[:8] != CFB_MAGIC:
            raise ValueError("vbaProject.bin is not a CFB container")
        self.data = data
        self.sector_size = 1 << struct.unpack_from("<H", data, 30)[0]
        self.mini_sector_size = 1 << struct.unpack_from("<H", data, 32)[0]
        self.first_dir_sector = struct.unpack_from("<I", data, 48)[0]
        self.mini_stream_cutoff = struct.unpack_from("<I", data, 56)[0]
        self.first_minifat_sector = struct.unpack_from("<I", data, 60)[0]
        self.num_minifat_sectors = struct.unpack_from("<I", data, 64)[0]
        self.first_difat_sector = struct.unpack_from("<I", data, 68)[0]
        self.num_difat_sectors = struct.unpack_from("<I", data, 72)[0]

        difat = list(struct.unpack_from("<109I", data, 76))
        sec = self.first_difat_sector
        for _ in range(self.num_difat_sectors):
            if sec in FREESECT:
                break
            raw = self._sector(sec)
            entries = struct.unpack(f"<{self.sector_size // 4}I", raw)
            difat.extend(entries[:-1])
            sec = entries[-1]
        self.fat: list[int] = []
        for s in difat:
            if s in FREESECT:
                continue
            self.fat.extend(struct.unpack(f"<{self.sector_size // 4}I", self._sector(s)))

        dir_data = self._read_chain(self.first_dir_sector)
        self.entries: list[dict] = []
        for off in range(0, len(dir_data), 128):
            ent = dir_data[off:off + 128]
            if len(ent) < 128:
                break
            name_len = struct.unpack_from("<H", ent, 64)[0]
            if name_len == 0:
                continue
            self.entries.append({
                "name": ent[: max(0, name_len - 2)].decode("utf-16-le", errors="replace"),
                "type": ent[66],
                "start": struct.unpack_from("<I", ent, 116)[0],
                "size": struct.unpack_from("<Q", ent, 120)[0],
            })

        self.minifat: list[int] = []
        if self.num_minifat_sectors:
            mf = self._read_chain(self.first_minifat_sector)
            self.minifat = list(struct.unpack(f"<{len(mf) // 4}I", mf))
        root = next(e for e in self.entries if e["type"] == 5)
        self.mini_stream = self._read_chain(root["start"])[: root["size"]]

    def _sector(self, n: int) -> bytes:
        off = 512 + n * self.sector_size
        return self.data[off: off + self.sector_size]

    def _read_chain(self, start: int) -> bytes:
        out, sec, seen = [], start, set()
        while sec not in FREESECT and sec not in seen:
            seen.add(sec)
            out.append(self._sector(sec))
            if sec >= len(self.fat):
                break
            sec = self.fat[sec]
        return b"".join(out)

    def _read_mini_chain(self, start: int, size: int) -> bytes:
        out, sec, seen = [], start, set()
        while sec not in FREESECT and sec not in seen:
            seen.add(sec)
            off = sec * self.mini_sector_size
            out.append(self.mini_stream[off: off + self.mini_sector_size])
            if sec >= len(self.minifat):
                break
            sec = self.minifat[sec]
        return b"".join(out)[:size]

    def read_stream(self, name: str) -> bytes | None:
        for e in self.entries:
            if e["name"].lower() == name.lower() and e["type"] == 2:
                if e["size"] < self.mini_stream_cutoff:
                    return self._read_mini_chain(e["start"], e["size"])
                return self._read_chain(e["start"])[: e["size"]]
        return None


# ── MS-OVBA decompression ───────────────────────────────────────────────────

def ovba_decompress(data: bytes) -> bytes:
    if not data or data[0] != 0x01:
        raise ValueError("bad compressed container signature")
    out = bytearray()
    i = 1
    while i < len(data):
        header = struct.unpack_from("<H", data, i)[0]
        i += 2
        chunk_size = (header & 0x0FFF) + 3
        compressed = bool(header & 0x8000)
        chunk_end = i + chunk_size - 2
        chunk_start_out = len(out)
        if not compressed:
            out.extend(data[i: i + 4096])
            i += 4096
            continue
        while i < chunk_end and i < len(data):
            flags = data[i]
            i += 1
            for bit in range(8):
                if i >= chunk_end or i >= len(data):
                    break
                if not (flags >> bit) & 1:
                    out.append(data[i])
                    i += 1
                else:
                    token = struct.unpack_from("<H", data, i)[0]
                    i += 2
                    pos = len(out) - chunk_start_out
                    bits = 4
                    while (1 << (16 - bits)) > 4096 or (pos - 1) >> bits:
                        bits += 1
                        if bits >= 12:
                            break
                    bits = max(4, min(12, bits))
                    length = (token & ((1 << (16 - bits)) - 1)) + 3
                    offset = (token >> (16 - bits)) + 1
                    for _ in range(length):
                        out.append(out[-offset])
    return bytes(out)


# ── dir stream → module list ────────────────────────────────────────────────

def parse_dir_stream(decompressed: bytes) -> list[dict]:
    mods, i, cur = [], 0, {}
    while i + 6 <= len(decompressed):
        rec_id, size = struct.unpack_from("<HI", decompressed, i)
        i += 6
        if rec_id == 0x0009:  # PROJECTVERSION: declared size is bogus; fixed 6
            size = 6
        payload = decompressed[i: i + size]
        if rec_id == 0x0019:
            if cur.get("name"):
                mods.append(cur)
                cur = {}
            cur["name"] = payload.decode("latin-1", errors="replace")
        elif rec_id == 0x001A:
            cur["stream"] = payload.decode("latin-1", errors="replace")
        elif rec_id == 0x0031:
            cur["offset"] = struct.unpack("<I", payload)[0]
        elif rec_id == 0x0021:
            cur["type"] = "standard"
        elif rec_id == 0x0022:
            cur["type"] = "document_or_class"
        i += size
    if cur.get("name"):
        mods.append(cur)
    return mods


# ── analysis ────────────────────────────────────────────────────────────────

PROC_RE = re.compile(r"^\s*(?:Public\s+|Private\s+|Friend\s+)?(Sub|Function|Property\s+(?:Get|Let|Set))\s+(\w+)", re.M | re.I)
AUTOEXEC_RE = re.compile(
    r"\b(Workbook_Open|Auto_Open|Auto_Close|Workbook_BeforeClose|Workbook_BeforeSave|"
    r"Worksheet_Change|Worksheet_Calculate|Worksheet_Activate|Application\.OnTime|Application\.Run)\b",
    re.I,
)
EXTERNAL_RE = re.compile(
    r"\b(Shell|CreateObject|GetObject|URLDownloadToFile|Environ|FileSystemObject|"
    r"Declare\s+(?:PtrSafe\s+)?(?:Sub|Function))\b",
    re.I,
)
CELL_WRITE_RE = re.compile(r"\.(Value|Formula|FormulaR1C1)\s*=", re.I)


def extract_vba_modules(xlsm_path: Path) -> tuple[list[dict], dict[str, str]]:
    """Return (module_metadata, {module_name: source_text})."""
    z = zipfile.ZipFile(xlsm_path)
    try:
        blob = z.read("xl/vbaProject.bin")
    except KeyError:
        return [], {}
    cfb = CFB(blob)
    dir_raw = cfb.read_stream("dir")
    if dir_raw is None:
        raise ValueError("vbaProject.bin has no dir stream")
    modules = parse_dir_stream(ovba_decompress(dir_raw))
    sources: dict[str, str] = {}
    for m in modules:
        raw = cfb.read_stream(m.get("stream") or m["name"])
        if raw is None:
            continue
        try:
            sources[m["name"]] = ovba_decompress(raw[m.get("offset", 0):]).decode("latin-1", errors="replace")
        except Exception:
            sources[m["name"]] = ""
    return modules, sources


def formulas_reference(z: zipfile.ZipFile, func_names: set[str]) -> list[dict]:
    """P2: scan every worksheet XML for formula calls to VBA Function names."""
    hits = []
    if not func_names:
        return hits
    pats = {fn: re.compile(rf"\b{re.escape(fn)}\s*\(", re.I) for fn in func_names}
    for n in z.namelist():
        if n.startswith("xl/worksheets/sheet") and n.endswith(".xml"):
            xml = z.read(n).decode("utf-8", errors="replace")
            for fm in re.finditer(r"<f[ >]([^<]*)</f>", xml):
                t = fm.group(1)
                for fn, pat in pats.items():
                    if pat.search(t):
                        hits.append({"part": n, "function": fn})
    return hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("xlsm")
    ap.add_argument("--out", required=True)
    ap.add_argument("--decisions-json", help="decisions.json with deal_strings for the VBA leak scan")
    ap.add_argument("--convert-out", help="Write the macro-stripped .xlsx here when verdict permits")
    ap.add_argument("--approve-strip", action="store_true",
                    help="User approved stripping a needs_review project (P2 formula check still enforced)")
    args = ap.parse_args()

    path = Path(args.xlsm)
    report: dict = {"file": str(path), "verdict": None, "proof_obligations": {}, "modules": [],
                    "vba_leak_findings": [], "removed_macro_inventory": [], "conversion": None}

    z = zipfile.ZipFile(path)
    has_vba = any(n.lower() == "xl/vbaproject.bin" for n in z.namelist())
    if not has_vba:
        report["verdict"] = "strippable"
        report["proof_obligations"] = {"P1_no_functions": True, "P2_no_udf_in_formulas": True,
                                       "P3_no_autoexec": True, "P4_no_external_calls": True,
                                       "note": "no vbaProject.bin — xlsm in extension only"}
    else:
        modules, sources = extract_vba_modules(path)
        funcs: set[str] = set()
        subs: set[str] = set()
        autoexec: list[dict] = []
        external: list[dict] = []
        cell_writes: list[dict] = []
        for name, src in sources.items():
            procs = PROC_RE.findall(src)
            mod_funcs = sorted({p[1] for p in procs if p[0].lower().startswith("function")})
            mod_subs = sorted({p[1] for p in procs if p[0].lower() == "sub"})
            funcs.update(mod_funcs)
            subs.update(mod_subs)
            for m in AUTOEXEC_RE.finditer(src):
                autoexec.append({"module": name, "symbol": m.group(1)})
            for m in EXTERNAL_RE.finditer(src):
                external.append({"module": name, "symbol": m.group(1)})
            if CELL_WRITE_RE.search(src):
                cell_writes.append({"module": name})
            report["modules"].append({
                "module": name, "lines": len(src.splitlines()),
                "functions": mod_funcs, "subs": mod_subs,
            })

        udf_hits = formulas_reference(z, funcs)

        # VBA leak scan
        deal_strings: list[str] = []
        if args.decisions_json:
            try:
                deal_strings = json.loads(Path(args.decisions_json).read_text(encoding="utf-8")).get("deal_strings") or []
            except Exception:
                pass
        for name, src in sources.items():
            low = src.lower()
            for ds in deal_strings:
                if ds and ds.lower() in low:
                    report["vba_leak_findings"].append({
                        "module": name, "finding": "deal_string_in_vba_source",
                        "matched_deal_string": ds, "severity": "blocking",
                    })

        p1 = not funcs
        p2 = not udf_hits
        p3 = not autoexec or not cell_writes  # events that never write cells are cosmetic-leaning
        p3_strict = not autoexec
        p4 = not external
        report["proof_obligations"] = {
            "P1_no_functions": p1,
            "P2_no_udf_in_formulas": p2,
            "P2_udf_hits": udf_hits,
            "P3_no_autoexec": p3_strict,
            "P3_autoexec_symbols": autoexec,
            "P3_modules_writing_cells": cell_writes,
            "P4_no_external_calls": p4,
            "P4_external_symbols": external,
        }
        report["removed_macro_inventory"] = sorted(subs | funcs)

        if not p2:
            report["verdict"] = "not_strippable"
            report["reason"] = ("Sheet formulas call VBA Functions — the model's math depends on macro "
                                "code a converted workbook cannot execute. Request a formula-only version.")
        elif p1 and p3_strict:
            report["verdict"] = "strippable"
        elif args.approve_strip:
            report["verdict"] = "strippable"
            report["reason"] = "needs_review conditions present but stripping approved by user (P2 verified)."
        else:
            report["verdict"] = "needs_review"
            report["reason"] = ("VBA contains Function procedures or event handlers not provably cosmetic. "
                                "Confirm with the user, then re-run with --approve-strip.")

    if report["verdict"] == "strippable" and args.convert_out:
        import openpyxl
        wb = openpyxl.load_workbook(path)  # NO keep_vba: drops vbaProject + macro content type
        out = Path(args.convert_out)
        if out.suffix.lower() != ".xlsx":
            out = out.with_suffix(".xlsx")
        wb.save(out)
        # belt-and-braces: confirm no vba part survived
        residual = [n for n in zipfile.ZipFile(out).namelist() if "vba" in n.lower()]
        report["conversion"] = {
            "converted_to": str(out),
            "vba_parts_in_output": residual,
            "note": ("openpyxl round-trip without keep_vba removes vbaProject.bin, the macroEnabled "
                     "content type, and legacy form-control buttons wired to the removed Subs. Record "
                     "removed_macro_inventory in _PreparationAudit during Phase 2."),
        }
        if residual:
            report["verdict"] = "not_strippable"
            report["reason"] = "conversion left VBA parts in the output package"

    Path(args.out).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"verdict": report["verdict"],
                      "modules": len(report["modules"]),
                      "vba_leak_findings": len(report["vba_leak_findings"]),
                      "converted": bool(report.get("conversion")),
                      "out": args.out}, indent=2))
    return 0 if report["verdict"] == "strippable" else (3 if report["verdict"] == "needs_review" else 2)


if __name__ == "__main__":
    raise SystemExit(main())
# END xlsm_triage_convert.py
~~~

## `initial_triage.py`

~~~python
#!/usr/bin/env python3
"""Initial workbook triage for template preparation.

Outputs JSON with file type, workbook size, unsupported features, external links,
and the formula-reevaluation handoff. This script does not modify the workbook.
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

import openpyxl


def zip_parts(path: Path) -> list[str]:
    try:
        with zipfile.ZipFile(path) as zf:
            return zf.namelist()
    except zipfile.BadZipFile:
        return []


def find_external_parts(parts: list[str]) -> list[str]:
    markers = []
    for name in parts:
        lower = name.lower()
        if lower.startswith("xl/externallinks/"):
            markers.append(name)
        if lower in {"xl/connections.xml", "xl/querytables.xml"}:
            markers.append(name)
        if lower.startswith("xl/querytables/") or lower.startswith("xl/connections/"):
            markers.append(name)
    return sorted(set(markers))


def workbook_counts(path: Path) -> dict:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=False, keep_links=True)
    sheets = []
    total_cells = 0
    total_visible_cells = 0
    for ws in wb.worksheets:
        cells = int((ws.max_row or 0) * (ws.max_column or 0))
        total_cells += cells
        if ws.sheet_state == "visible":
            total_visible_cells += cells
        sheets.append(
            {
                "name": ws.title,
                "state": ws.sheet_state,
                "max_row": ws.max_row,
                "max_column": ws.max_column,
                "cell_area": cells,
            }
        )
    return {
        "sheet_count": len(wb.worksheets),
        "visible_sheet_count": sum(1 for s in sheets if s["state"] == "visible"),
        "total_cell_area": total_cells,
        "visible_cell_area": total_visible_cells,
        "sheets": sheets,
        "defined_name_count": len(list(wb.defined_names.items())) if hasattr(wb.defined_names, "items") else 0,
        "properties": {
            "creator_present": bool(getattr(wb.properties, "creator", None)),
            "last_modified_by_present": bool(getattr(wb.properties, "lastModifiedBy", None)),
            "title_present": bool(getattr(wb.properties, "title", None)),
            "subject_present": bool(getattr(wb.properties, "subject", None)),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_file")
    parser.add_argument("--out")
    args = parser.parse_args()

    path = Path(args.input_file)
    result: dict = {
        "file": str(path),
        "extension": path.suffix.lower(),
        "supported_extension": path.suffix.lower() == ".xlsx",
        "issues": [],
        "refusal_reasons": [],
        "formula_recalc": {
            "method": "excel_skill_scripts_recalc_py",
            "command": "cd <excel_skill_root> && python scripts/recalc.py <absolute_workbook> [timeout_seconds]",
            "note": "Phase 3 must run sniff_test.py, which invokes the Excel skill recalc.py after the sniff payload is written.",
        },
    }

    parts = zip_parts(path)
    result["zip_parts_checked"] = bool(parts)
    result["has_vba_project"] = "xl/vbaproject.bin" in {p.lower() for p in parts}
    result["external_connection_parts"] = find_external_parts(parts)

    if path.suffix.lower() == ".xlsm" or result["has_vba_project"]:
        # v1.3: macro-enabled workbooks are no longer flat-refused. They route
        # through the xlsm gate, which analyzes the VBA project (never executes
        # it), scans it for deal-data leakage, and emits a macro-stripped .xlsx
        # when the proof obligations hold. The pipeline then continues on the
        # converted file.
        result["requires_xlsm_gate"] = True
        result["xlsm_gate"] = {
            "script": "tp_scripts/xlsm_triage_convert.py",
            "command": ("python tp_scripts/xlsm_triage_convert.py <model.xlsm> "
                        "--out xlsm_report.json --convert-out model_converted.xlsx "
                        "[--decisions-json decisions.json]"),
            "note": ("Run the gate BEFORE any other Phase 1 script. verdict=strippable: "
                     "continue the pipeline on the converted .xlsx and carry "
                     "removed_macro_inventory into _PreparationAudit. verdict=needs_review: "
                     "present the Function/event inventory to the user; re-run with "
                     "--approve-strip after approval. verdict=not_strippable: refuse with "
                     "the report's reason (formulas depend on VBA)."),
        }
    elif path.suffix.lower() != ".xlsx":
        result["refusal_reasons"].append("Only macro-free .xlsx workbooks are supported in v1.")

    try:
        counts = workbook_counts(path)
        result.update(counts)
        if counts["visible_sheet_count"] > 25 and counts["visible_cell_area"] > 500_000:
            result["refusal_reasons"].append(
                f"Workbook has {counts['visible_sheet_count']} visible sheets and {counts['visible_cell_area']} visible cell area; this exceeds the safe automated-mapping threshold."
            )
    except Exception as exc:  # noqa: BLE001
        result["refusal_reasons"].append(f"Workbook could not be opened cleanly: {type(exc).__name__}: {exc}")

    if result["external_connection_parts"]:
        result["issues"].append(
            {
                "severity": "critical_review",
                "issue": "External data connection parts found",
                "parts": result["external_connection_parts"],
                "recommended_action": "Proceed only if the user approves static conversion or confirms the links are not required.",
            }
        )

    if result.get("requires_xlsm_gate") and not result["refusal_reasons"]:
        result["status"] = "xlsm_gate_required"
    else:
        result["status"] = "not_compatible" if result["refusal_reasons"] else "triage_passed"

    text = json.dumps(result, indent=2, default=str)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# END initial_triage.py
~~~

## `extract_surface.py`

~~~python
#!/usr/bin/env python3
"""Extract sheet roles, regions, candidate scalar inputs, output reads, and table schemas."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any

import openpyxl
from openpyxl.utils import get_column_letter

DATA_TABLE_NAMES = re.compile(r"(t-?12|trailing|rent\s*roll|unit\s*mix|comps|budget|draw|import)", re.I)
INPUT_SURFACE_NAMES = re.compile(r"(assumptions?|inputs?|pro\s*forma|proforma|key\s*terms?|deal\s*overview)", re.I)
OUTPUT_NAMES = re.compile(r"(returns?|summary|waterfall|one\s*pager|dashboard|metrics)", re.I)
DEAD_NAMES = re.compile(r"^(sheet\d+|old|scratch|backup|copy\s*of|v\d+)", re.I)

OUTPUT_VOCAB = re.compile(
    r"(irr|equity\s*multiple|moic|noi|net\s*operating\s*income|cap\s*rate|dscr|debt\s*yield|cash\s*on\s*cash|exit\s*value|sale\s*proceeds|yield\s*on\s*cost)",
    re.I,
)

INPUT_LABEL_HINTS = re.compile(
    r"(price|cost|rent|growth|cap\s*rate|rate|ltv|loan|debt|vacancy|occupancy|expense|tax|insurance|payroll|management|fee|units?|sq\.?\s*ft|sf|hold|term|amort|exit|noi|capex|renovation|premium|preferred|promote|split|hurdle)",
    re.I,
)

FORMULA_SHEET_REF = re.compile(r"(?:'([^']+)'|([A-Za-z_][A-Za-z0-9_ .&-]*))!")


def classify_value(value: Any) -> str:
    if value is None:
        return "blank"
    if isinstance(value, str) and value.startswith("="):
        return "formula"
    if isinstance(value, str):
        return "text"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, (datetime, date)):
        return "date"
    return "other"


def value_class(value: Any) -> str:
    cls = classify_value(value)
    if cls == "number":
        v = abs(float(value))
        if v >= 1_000_000:
            return "large_number"
        if v >= 1_000:
            return "medium_number"
        if 0 <= v <= 1:
            return "rate_or_ratio"
    if cls == "text":
        return "text"
    return cls


def census(ws) -> Counter:
    counts: Counter = Counter()
    for row in ws.iter_rows():
        for cell in row:
            counts[classify_value(cell.value)] += 1
    return counts


def referenced_sheets(wb) -> set[str]:
    out: set[str] = set()
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if isinstance(cell.value, str) and cell.value.startswith("="):
                    for m in FORMULA_SHEET_REF.finditer(cell.value):
                        out.add((m.group(1) or m.group(2) or "").strip())
    return out


def detect_regions(ws, row_step: int = 8) -> list[dict]:
    regions: list[dict] = []
    current: dict | None = None
    for start in range(1, (ws.max_row or 0) + 1, row_step):
        end = min(start + row_step - 1, ws.max_row or start)
        counts = Counter()
        for row in ws.iter_rows(min_row=start, max_row=end):
            for cell in row:
                counts[classify_value(cell.value)] += 1
        nonblank = sum(counts[k] for k in ["formula", "number", "text", "date", "boolean", "other"])
        if nonblank < 4:
            role = "empty"
        else:
            formula_ratio = counts["formula"] / nonblank
            numeric_ratio = (counts["number"] + counts["date"] + counts["boolean"]) / nonblank
            if formula_ratio > 0.7:
                role = "calculation"
            elif numeric_ratio > 0.25 and counts["formula"] < counts["number"] + counts["text"]:
                role = "input_like"
            else:
                role = "mixed"
        if current and current["role"] == role:
            current["rows"][1] = end
        else:
            if current:
                regions.append(current)
            current = {"rows": [start, end], "role": role}
    if current:
        regions.append(current)
    return regions


def classify_sheet(ws, counts: Counter, referenced_by_others: bool) -> tuple[str, str, list[str]]:
    name = ws.title
    nonblank = sum(counts[k] for k in counts if k != "blank")
    formula_ratio = counts["formula"] / nonblank if nonblank else 0
    number_ratio = counts["number"] / nonblank if nonblank else 0
    reasons: list[str] = []
    if nonblank == 0:
        return "dead", "high", ["empty sheet"]
    if DATA_TABLE_NAMES.search(name):
        return "data_table", "high", ["sheet name indicates data table"]
    if DEAD_NAMES.search(name) and not referenced_by_others:
        return "dead", "medium", ["sheet name suggests legacy/scratch and no inbound references"]
    if INPUT_SURFACE_NAMES.search(name):
        reasons.append("sheet name indicates input/pro forma surface")
        if formula_ratio > 0.35:
            return "mixed", "high", reasons + ["contains both formulas and hardcoded values"]
        return "input_surface", "high", reasons
    if OUTPUT_NAMES.search(name) and formula_ratio > 0.25:
        return "output", "medium", ["sheet name indicates output/summary"]
    if (ws.max_row or 0) > 80 and number_ratio > 0.45 and formula_ratio < 0.25:
        return "data_table", "medium", ["large numeric table signature"]
    if formula_ratio > 0.7:
        return "calculation", "medium", ["high formula density"]
    if formula_ratio > 0.2 and number_ratio > 0.1:
        return "mixed", "medium", ["mixed formula and numeric density"]
    return "support", "low", ["fallback classification"]


def nearest_label(ws, row: int, col: int, left: int = 4, up: int = 2) -> dict | None:
    labels: list[tuple[int, str, str, str]] = []
    for dc in range(1, left + 1):
        c = col - dc
        if c < 1:
            break
        v = ws.cell(row=row, column=c).value
        if isinstance(v, str) and v and not v.startswith("="):
            labels.append((dc, v.strip(), f"{get_column_letter(c)}{row}", "left"))
            break
    for dr in range(1, up + 1):
        r = row - dr
        if r < 1:
            break
        v = ws.cell(row=r, column=col).value
        if isinstance(v, str) and v and not v.startswith("="):
            labels.append((dr + 2, v.strip(), f"{get_column_letter(col)}{r}", "above"))
            break
    if not labels:
        return None
    labels.sort(key=lambda x: x[0])
    _, text, coord, direction = labels[0]
    return {"text": text[:200], "cell": coord, "direction": direction}


def in_any_table(ws, coord: str) -> bool:
    for table in ws.tables.values():
        if coord in ws[table.ref]:
            return True
    return False


def table_schemas(ws) -> list[dict]:
    out = []
    for name, table in ws.tables.items():
        out.append({"name": name, "sheet": ws.title, "ref": table.ref, "displayName": table.displayName})
    return out


def extract_candidates(ws, sheet_role: str, max_candidates: int) -> tuple[list[dict], list[dict]]:
    inputs: list[dict] = []
    outputs: list[dict] = []
    skip_scalar = sheet_role == "data_table"
    for row in ws.iter_rows():
        for cell in row:
            cls = classify_value(cell.value)
            if cls == "blank":
                continue
            label = nearest_label(ws, cell.row, cell.column)
            if label and cls in {"number", "text", "date", "boolean"}:
                if OUTPUT_VOCAB.search(label["text"]):
                    outputs.append(
                        {
                            "cell": f"{ws.title}!{cell.coordinate}",
                            "label": label,
                            "value_class": value_class(cell.value),
                            "source": "adjacent_label",
                        }
                    )
                elif not skip_scalar and INPUT_LABEL_HINTS.search(label["text"]):
                    inputs.append(
                        {
                            "cell": f"{ws.title}!{cell.coordinate}",
                            "label": label,
                            "value_class": value_class(cell.value),
                            "in_excel_table": in_any_table(ws, cell.coordinate),
                            "source": "adjacent_label",
                        }
                    )
        if len(inputs) >= max_candidates and len(outputs) >= max_candidates:
            break
    return inputs[:max_candidates], outputs[:max_candidates]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_file")
    parser.add_argument("--out")
    parser.add_argument("--max-candidates-per-sheet", type=int, default=250)
    args = parser.parse_args()

    wb = openpyxl.load_workbook(args.input_file, data_only=False, read_only=False, keep_links=True)
    refs = referenced_sheets(wb)
    result = {"file": args.input_file, "sheets": [], "candidate_inputs": [], "candidate_outputs": [], "tables": []}
    for ws in wb.worksheets:
        counts = census(ws)
        role, confidence, reasons = classify_sheet(ws, counts, ws.title in refs)
        regions = detect_regions(ws) if role in {"mixed", "input_surface", "support"} else []
        sheet_info = {
            "name": ws.title,
            "state": ws.sheet_state,
            "role": role,
            "confidence": confidence,
            "reasons": reasons,
            "census": dict(counts),
            "regions": regions,
        }
        result["sheets"].append(sheet_info)
        result["tables"].extend(table_schemas(ws))
        if ws.sheet_state == "visible":
            inputs, outputs = extract_candidates(ws, role, args.max_candidates_per_sheet)
            result["candidate_inputs"].extend(inputs)
            result["candidate_outputs"].extend(outputs)
    text = json.dumps(result, indent=2, default=str)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# END extract_surface.py
~~~

## `build_dependency_graph.py`

~~~python
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
~~~

## `detect_conventions.py`

~~~python
#!/usr/bin/env python3
"""Detect workbook conventions: unit scale, time axes, signs, and iterative calc."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any

import openpyxl

UNIT_MARKERS = [
    (re.compile(r"\$\s*000|\$\s*in\s*000|dollars?\s*in\s*thousands|in\s*thousands", re.I), "$000"),
    (re.compile(r"\$\s*mm|\$\s*m\b|in\s*millions|dollars?\s*in\s*millions", re.I), "$M"),
    (re.compile(r"whole\s*dollars|actual\s*dollars|in\s*dollars", re.I), "$"),
]
ANCHOR_LABELS = re.compile(
    r"(offer\s*price|purchase\s*price|acquisition\s*price|contract\s*price|total\s*capitalization|loan\s*amount|debt\s*proceeds|total\s*equity|total\s*sources|total\s*uses|stabilized\s*noi|year\s*1\s*noi)",
    re.I,
)
EXPENSE_LABELS = re.compile(r"(tax|insurance|utilities|repairs?|maintenance|payroll|admin|management\s*fee|operating\s*expense|opex)", re.I)
MONTH_TEXT = re.compile(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\b", re.I)
YEAR_TEXT = re.compile(r"\b(20\d{2}|19\d{2}|year\s*[1-9][0-9]?)\b", re.I)


def nearest_label(ws, row: int, col: int) -> str | None:
    for dc in range(1, 5):
        c = col - dc
        if c < 1:
            break
        v = ws.cell(row=row, column=c).value
        if isinstance(v, str) and v and not v.startswith("="):
            return v.strip()
    for dr in range(1, 3):
        r = row - dr
        if r < 1:
            break
        v = ws.cell(row=r, column=col).value
        if isinstance(v, str) and v and not v.startswith("="):
            return v.strip()
    return None


def marker_scan(wb) -> list[dict]:
    hits = []
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if isinstance(cell.value, str):
                    for pattern, scale in UNIT_MARKERS:
                        if pattern.search(cell.value):
                            hits.append({"sheet": ws.title, "cell": cell.coordinate, "scale": scale, "text": cell.value[:120]})
    return hits


def anchor_amounts(wb) -> list[dict]:
    anchors = []
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if isinstance(cell.value, (int, float)) and not isinstance(cell.value, bool):
                    label = nearest_label(ws, cell.row, cell.column)
                    if label and ANCHOR_LABELS.search(label):
                        v = float(cell.value)
                        abs_v = abs(v)
                        if abs_v >= 1_000_000:
                            inferred = "$"
                        elif 1_000 <= abs_v < 1_000_000:
                            inferred = "$000"
                        elif 10 <= abs_v < 1_000:
                            inferred = "$M"
                        else:
                            inferred = "unknown"
                        anchors.append(
                            {
                                "sheet": ws.title,
                                "cell": cell.coordinate,
                                "label": label[:120],
                                "value_class": "redacted_numeric_anchor",
                                "inferred_scale": inferred,
                            }
                        )
    return anchors


def detect_unit_scale(wb) -> dict:
    markers = marker_scan(wb)
    if markers:
        counts = Counter(m["scale"] for m in markers)
        scale, count = counts.most_common(1)[0]
        return {"scale": scale, "confidence": "high", "source": "explicit_marker", "evidence": markers[:20]}
    anchors = anchor_amounts(wb)
    usable = [a["inferred_scale"] for a in anchors if a["inferred_scale"] != "unknown"]
    if usable:
        scale, count = Counter(usable).most_common(1)[0]
        confidence = "high" if count >= 2 else "medium"
        return {"scale": scale, "confidence": confidence, "source": "anchor_amount_magnitude", "evidence": anchors[:20]}
    return {"scale": "unknown", "confidence": "low", "source": "not_detected", "evidence": []}


def period_kind(values: list[Any]) -> str | None:
    if len(values) < 3:
        return None
    text = " ".join(str(v) for v in values if v is not None)
    if MONTH_TEXT.search(text):
        return "monthly"
    if sum(1 for v in values if isinstance(v, (datetime, date))) >= 3:
        # Use count rather than spacing: Excel models often store dates with formulas.
        return "monthly_or_date_based"
    if len(YEAR_TEXT.findall(text)) >= 3:
        return "annual"
    nums = [v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if len(nums) >= 3 and all(1900 <= float(v) <= 2100 for v in nums[: min(len(nums), 10)]):
        return "annual"
    return None


def detect_time_axes(wb) -> list[dict]:
    candidates = []
    for ws in wb.worksheets:
        for row_idx in range(1, (ws.max_row or 0) + 1):
            row_vals = [ws.cell(row=row_idx, column=c).value for c in range(1, (ws.max_column or 0) + 1)]
            nonblank_positions = [(i + 1, v) for i, v in enumerate(row_vals) if v not in (None, "")]
            if len(nonblank_positions) < 3:
                continue
            kind = period_kind([v for _, v in nonblank_positions])
            if kind:
                candidates.append(
                    {
                        "sheet": ws.title,
                        "row": row_idx,
                        "granularity": "monthly" if kind == "monthly_or_date_based" and len(nonblank_positions) >= 12 else kind,
                        "period_count": len(nonblank_positions),
                        "first_column": nonblank_positions[0][0],
                        "last_column": nonblank_positions[-1][0],
                        "role_guess": "historical_source_data" if re.search(r"t-?12|trailing", ws.title, re.I) else "projection_or_output",
                    }
                )
    # Prefer compact output.
    candidates.sort(key=lambda x: (0 if x["role_guess"] == "projection_or_output" else 1, -x["period_count"]))
    return candidates[:30]


def detect_expense_sign(wb_values) -> dict:
    signs = Counter()
    evidence = []
    for ws in wb_values.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if isinstance(cell.value, (int, float)) and not isinstance(cell.value, bool):
                    label = nearest_label(ws, cell.row, cell.column)
                    if label and EXPENSE_LABELS.search(label):
                        sign = "negative" if cell.value < 0 else "positive"
                        signs[sign] += 1
                        if len(evidence) < 20:
                            evidence.append({"sheet": ws.title, "cell": cell.coordinate, "label": label[:120], "sign": sign})
    if not signs:
        return {"expense_sign": "unknown", "confidence": "low", "evidence": []}
    sign, count = signs.most_common(1)[0]
    confidence = "high" if count >= 5 else "medium"
    return {"expense_sign": sign, "confidence": confidence, "evidence": evidence}


def iterative_calc(wb) -> dict:
    calc = getattr(wb, "calculation", None) or getattr(wb, "calculation_properties", None)
    iterate = bool(getattr(calc, "iterate", False)) if calc else False
    return {"iterative_calc_enabled": iterate}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_file")
    parser.add_argument("--out")
    args = parser.parse_args()

    wb = openpyxl.load_workbook(args.input_file, data_only=False, read_only=False, keep_links=True)
    wb_values = openpyxl.load_workbook(args.input_file, data_only=True, read_only=False, keep_links=True)
    result = {
        "file": args.input_file,
        "unit_scale": detect_unit_scale(wb),
        "time_axis_candidates": detect_time_axes(wb),
        "expense_sign": detect_expense_sign(wb_values),
        "iterative_calc": iterative_calc(wb),
        "note": "If multiple time axes exist, choose the primary underwriting projection axis in Phase 1 judgment log.",
    }
    text = json.dumps(result, indent=2, default=str)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# END detect_conventions.py
~~~

## `diagnose_workbook.py`

~~~python
#!/usr/bin/env python3
"""Workbook diagnostics: errors, external refs, named ranges, hidden data, and formula smells."""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import openpyxl

ERROR_VALUES = {"#DIV/0!", "#N/A", "#NAME?", "#NULL!", "#NUM!", "#REF!", "#VALUE!", "#GETTING_DATA"}
EXTERNAL_RE = re.compile(r"\[[^\]]+\.(?:xlsx|xlsm|xlsb|xls)\]", re.I)
CELL_REF_RE = re.compile(r"(?:'[^']+'|[A-Za-z_][A-Za-z0-9_ .&-]*!)?\$?[A-Z]{1,3}\$?\d+(?::\$?[A-Z]{1,3}\$?\d+)?")
NUMERIC_LITERAL_RE = re.compile(r"(?<![A-Z0-9])[-+]?\d+(?:\.\d+)?%?(?![A-Z0-9])", re.I)
TODO_RE = re.compile(r"\b(todo|fixme|xxx|check this|plug|placeholder)\b", re.I)


def formula_signature(formula: str) -> str:
    s = CELL_REF_RE.sub("REF", formula or "")
    s = re.sub(r"\s+", "", s).upper()
    return s


def count_errors(path: Path) -> dict:
    wb = openpyxl.load_workbook(path, data_only=True, read_only=False, keep_links=True)
    by_sheet = Counter()
    by_type = Counter()
    samples = []
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if isinstance(cell.value, str) and cell.value in ERROR_VALUES:
                    by_sheet[ws.title] += 1
                    by_type[cell.value] += 1
                    if len(samples) < 50:
                        samples.append({"sheet": ws.title, "cell": cell.coordinate, "error": cell.value})
    return {"total": sum(by_type.values()), "by_sheet": dict(by_sheet), "by_type": dict(by_type), "samples": samples}


def scan_formulas(path: Path) -> dict:
    wb = openpyxl.load_workbook(path, data_only=False, read_only=False, keep_links=True)
    external_refs = []
    formula_patterns = []
    magic_numbers = []
    todos = []
    for ws in wb.worksheets:
        for row_idx in range(1, (ws.max_row or 0) + 1):
            row_formulas = []
            for col_idx in range(1, (ws.max_column or 0) + 1):
                cell = ws.cell(row=row_idx, column=col_idx)
                v = cell.value
                if isinstance(v, str):
                    if TODO_RE.search(v):
                        todos.append({"sheet": ws.title, "cell": cell.coordinate, "text": v[:160]})
                    if v.startswith("="):
                        if EXTERNAL_RE.search(v):
                            external_refs.append({"sheet": ws.title, "cell": cell.coordinate, "formula": v[:240]})
                        row_formulas.append((cell.coordinate, formula_signature(v), v))
                        nums = [n for n in NUMERIC_LITERAL_RE.findall(v) if n not in {"0", "1", "-1", "12", "4", "365", "100"}]
                        if nums and len(magic_numbers) < 100:
                            magic_numbers.append({"sheet": ws.title, "cell": cell.coordinate, "numbers": nums[:8], "formula": v[:180]})
            if len(row_formulas) >= 4:
                counts = Counter(sig for _, sig, _ in row_formulas)
                if len(counts) > 1:
                    main_sig, main_count = counts.most_common(1)[0]
                    outliers = [coord for coord, sig, _ in row_formulas if sig != main_sig]
                    if main_count >= 3 and len(outliers) <= max(3, len(row_formulas) // 4):
                        formula_patterns.append({"sheet": ws.title, "row": row_idx, "outlier_cells": outliers[:20], "pattern_count": len(counts)})
    return {
        "external_formula_refs": external_refs,
        "formula_pattern_warnings": formula_patterns[:100],
        "hardcoded_formula_constants": magic_numbers,
        "todo_markers": todos[:100],
    }


def broken_names(path: Path) -> list[dict]:
    wb = openpyxl.load_workbook(path, data_only=False, read_only=False, keep_links=True)
    out = []
    for name, defined_name in wb.defined_names.items():
        try:
            destinations = list(defined_name.destinations)
            if not destinations:
                continue
            for sheet, ref in destinations:
                if sheet not in wb.sheetnames:
                    out.append({"name": name, "issue": "missing_sheet", "target": f"{sheet}!{ref}"})
        except Exception as exc:  # noqa: BLE001
            out.append({"name": name, "issue": "cannot_resolve", "error": str(exc)})
    return out


def package_findings(path: Path) -> dict:
    findings = {"external_parts": [], "vba_project": False, "custom_xml_parts": []}
    try:
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
            findings["vba_project"] = any(n.lower() == "xl/vbaproject.bin" for n in names)
            findings["external_parts"] = [n for n in names if n.lower().startswith("xl/externallinks/") or n.lower().startswith("xl/connections")]
            findings["custom_xml_parts"] = [n for n in names if n.lower().startswith("customxml/")][:50]
    except zipfile.BadZipFile:
        pass
    return findings


def hidden_sheets(path: Path) -> list[dict]:
    wb = openpyxl.load_workbook(path, data_only=False, read_only=False, keep_links=True)
    return [{"sheet": ws.title, "state": ws.sheet_state, "max_row": ws.max_row, "max_column": ws.max_column} for ws in wb.worksheets if ws.sheet_state != "visible"]


def issue_list(result: dict) -> list[dict]:
    issues = []
    if result["errors"]["total"]:
        issues.append({"id": "C.1", "severity": "critical", "issue": "Formula/value errors present", "count": result["errors"]["total"]})
    if result["formula_scan"]["external_formula_refs"] or result["package"]["external_parts"]:
        issues.append({"id": "C.3", "severity": "critical", "issue": "External references or connection parts present"})
    if result["broken_named_ranges"]:
        issues.append({"id": "C.4", "severity": "critical", "issue": "Broken or unresolved named ranges", "count": len(result["broken_named_ranges"])})
    if result["package"]["vba_project"]:
        issues.append({"id": "C.5", "severity": "critical", "issue": "VBA project present; .xlsm/macros unsupported in v1"})
    for key, issue_id, label in [
        ("formula_pattern_warnings", "W.1", "Inconsistent formula patterns"),
        ("hardcoded_formula_constants", "W.2", "Hardcoded constants inside formulas"),
        ("todo_markers", "W.8", "TODO/FIXME markers"),
    ]:
        count = len(result["formula_scan"].get(key, []))
        if count:
            issues.append({"id": issue_id, "severity": "warning", "issue": label, "count": count})
    if result["hidden_sheets"]:
        issues.append({"id": "I.2", "severity": "info", "issue": "Hidden sheets present", "count": len(result["hidden_sheets"])})
    return issues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_file")
    parser.add_argument("--out")
    args = parser.parse_args()
    path = Path(args.input_file)
    result = {
        "file": str(path),
        "errors": count_errors(path),
        "formula_scan": scan_formulas(path),
        "broken_named_ranges": broken_names(path),
        "hidden_sheets": hidden_sheets(path),
        "package": package_findings(path),
    }
    result["issues"] = issue_list(result)
    text = json.dumps(result, indent=2, default=str)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# END diagnose_workbook.py
~~~

## `classify_architecture.py`

~~~python
#!/usr/bin/env python3
"""Extract real estate model architecture signals and suggest supported modes."""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

import openpyxl

SIGNALS = {
    "acquisition": [r"purchase\s*price", r"offer\s*price", r"exit\s*cap", r"hold\s*period", r"loan\s*amount", r"ltv", r"noi"],
    "value_add": [r"value\s*add", r"renovation", r"cap\s*ex|capex", r"post\s*reno", r"market\s*rent", r"unit\s*turn"],
    "development": [r"hard\s*cost", r"soft\s*cost", r"land\s*cost", r"draw\s*schedule", r"construction", r"lease\s*up"],
    "waterfall": [r"waterfall", r"preferred\s*return", r"promote", r"gp\s*/?\s*lp", r"hurdle", r"catch\s*up"],
    "mixed_use": [r"retail", r"commercial", r"office", r"industrial", r"rent\s*/\s*sf", r"sf\s*rent"],
}


def scan_text(path: str) -> list[dict]:
    wb = openpyxl.load_workbook(path, data_only=False, read_only=False, keep_links=True)
    hits = []
    for ws in wb.worksheets:
        # Sheet names count as signals.
        for arch, patterns in SIGNALS.items():
            for pat in patterns:
                if re.search(pat, ws.title, re.I):
                    hits.append({"architecture": arch, "sheet": ws.title, "cell": None, "text": ws.title[:120], "source": "sheet_name"})
        for row in ws.iter_rows():
            for cell in row:
                if isinstance(cell.value, str) and cell.value and not cell.value.startswith("="):
                    text = cell.value[:240]
                    for arch, patterns in SIGNALS.items():
                        for pat in patterns:
                            if re.search(pat, text, re.I):
                                hits.append({"architecture": arch, "sheet": ws.title, "cell": cell.coordinate, "text": text, "source": "cell_text"})
                                break
    return hits


def classify(hits: list[dict]) -> dict:
    counts = defaultdict(int)
    examples = defaultdict(list)
    for hit in hits:
        counts[hit["architecture"]] += 1
        if len(examples[hit["architecture"]]) < 10:
            examples[hit["architecture"]].append(hit)
    acquisition = counts["acquisition"] >= 3
    primary = "acquisition" if acquisition else "unknown"
    if counts["development"] >= 4:
        primary = "development"
    elif counts["value_add"] >= 3 and acquisition:
        primary = "value_add"
    extensions = []
    if counts["waterfall"] >= 2:
        extensions.append("jv_waterfall")
    if counts["mixed_use"] >= 2:
        extensions.append("mixed_use")
    supported = []
    if primary in {"acquisition", "value_add", "development"}:
        supported.append(primary)
    if primary == "value_add":
        supported.append("acquisition")
    confidence = "high" if primary != "unknown" and counts[primary if primary != "value_add" else "value_add"] >= 4 else "medium" if primary != "unknown" else "low"
    return {
        "primary": primary,
        "extensions": extensions,
        "supported_payload_modes": sorted(set(supported)),
        "signal_counts": dict(counts),
        "evidence": {k: v for k, v in examples.items()},
        "confidence": confidence,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_file")
    parser.add_argument("--out")
    args = parser.parse_args()
    hits = scan_text(args.input_file)
    result = {"file": args.input_file, "architecture": classify(hits), "raw_signal_count": len(hits)}
    text = json.dumps(result, indent=2, default=str)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# END classify_architecture.py
~~~
