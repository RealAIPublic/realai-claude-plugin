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


# --- v4.9 -------------------------------------------------------------------
# Normalization scale bounds vs. a prior deal's amount. Both look like "a big
# number welded into a live formula", and only one of them is a defect.
#
#   =MIN(100,MAX(0,(C7-30000)/(150000-30000)*100))   income indexed 0-100
#   =MAX(0,B32-57915000)                             the prior deal's balance
#
# The discriminator is TWO OR MORE DISTINCT literals inside a clamp function,
# because that is what a range needs: a floor and a ceiling. One literal against
# a reference is a subtraction from a deal figure, whatever function wraps it —
# so this keys off the literal COUNT, not the presence of MIN/MAX. Verified
# 21/21 across both project fixtures with no cross-contamination.
CLAMP_FN_RE = re.compile(r"\b(?:MIN|MAX|MEDIAN|PERCENTILE(?:\.[A-Z]+)?)\s*\(", re.I)


def is_normalization_scale(formula: str, baked_literals) -> bool:
    """True when a formula's large literals are range bounds, not a deal amount.

    `baked_literals` is the already-filtered list of suspicious literals from the
    formula body (references stripped). Callers keep their own magnitude floor;
    this decides only what the construct *is*.
    """
    if not formula or not CLAMP_FN_RE.search(formula):
        return False
    distinct = {str(n).lstrip("+") for n in baked_literals}
    return len(distinct) >= 2


# Back-compat alias: sniff_test.py referenced this name.
infer_excel_skill_root = find_excel_skill_root

# END tp_common.py
