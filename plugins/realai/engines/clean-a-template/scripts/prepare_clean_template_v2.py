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


def apply_structural_redactions(wb, audit_ws, items: list[dict]):
    """Redact a prior deal's name out of STRUCTURAL text — banner titles, label
    cells, checklist rows (v4.8).

    These surfaces hold no values, so no clearing pass touches them; the deal
    name simply rides along into the next deliverable. They are also not
    clearable: blanking `'MODERA WALSH - DEBT STRUCTURE'` deletes the sheet's
    title. The fix is a text substitution to a generic equivalent, which is a
    planned, audited edit — `structural_text_surgery.py --plan` proposes each
    one, the plan is reviewed, and only reviewed items arrive here.
    """
    for item in items:
        ref = item.get("cell")
        if not ref:
            continue
        sheet, coord = split_cell(ref)
        if sheet not in wb.sheetnames:
            audit(audit_ws, ref, "skip_missing_sheet", None, "unchanged", "C.16",
                  "structural_text", "Sheet not found", False, "low")
            continue
        cell = wb[sheet][coord]
        before = cell.value
        replacement = item.get("replacement")
        if not isinstance(before, str) or isinstance(replacement, str) is False:
            audit(audit_ws, ref, "skip_structural_redaction", before, "unchanged", "C.16",
                  "structural_text", "Target is not text, or no replacement supplied", False, "low")
            continue
        if before.startswith("="):
            audit(audit_ws, ref, "skip_formula", before, "unchanged", "W.5",
                  "structural_text", "Formula cells are not redacted by text surgery", False, "medium")
            continue
        if not replacement.strip():
            audit(audit_ws, ref, "skip_empty_replacement", before, "unchanged", "C.16",
                  "structural_text",
                  "Redaction would leave the surface blank — needs a user decision, not a blank title",
                  False, "low")
            continue
        cell.value = replacement
        audit(audit_ws, ref, "redact_structural_text", before, "generic_equivalent", "C.16",
              item.get("runtime_source_class", "structural_text"),
              item.get("rationale", "Replaced prior-deal name in structural text with a generic equivalent"),
              True, item.get("confidence", "high"))


def _rewrite_sheet_refs(text: str, old: str, new: str) -> str:
    """Rewrite every sheet-qualified reference in a formula / defined-name body.

    Handles both quoted (`'Old Name'!A1`) and bare (`Old!A1`) forms, plus 3-D
    ranges (`'Old Name:Other'!A1` is not produced by Excel, but `Old:Other!A1`
    is — only the matching element is replaced).
    """
    out = text
    # Quoted form. Excel doubles internal apostrophes.
    old_q = old.replace("'", "''")
    new_q = new.replace("'", "''")
    out = out.replace(f"'{old_q}'!", f"'{new_q}'!")
    # Bare form, only valid when the name needs no quoting.
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", old):
        out = re.sub(rf"(?<![A-Za-z0-9_'!]){re.escape(old)}!", f"'{new_q}'!", out)
    return out


def apply_sheet_renames(wb, audit_ws, items: list[dict]):
    """Dependency-safe sheet rename (v4.8).

    openpyxl does NOT rewrite formula references when a worksheet is renamed —
    every `'Old Name'!A1` in the workbook silently becomes a reference to a
    sheet that no longer exists, which Excel reports as #REF! on open. So the
    rename and the reference rewrite happen together here, or not at all: a
    rename whose references cannot be rewritten deterministically is refused
    and left for `ask_user`.

    Charts and pivot caches hold their own copies of sheet-qualified refs and
    are not rewritten here — `structural_text_surgery.py --plan` marks a rename
    unsafe when either is present, so those never reach this function.
    """
    for item in items:
        old = item.get("sheet")
        new = item.get("new_name")
        if not old or not new:
            continue
        if old not in wb.sheetnames:
            audit(audit_ws, f"sheet:{old}", "skip_missing_sheet", None, "unchanged", "C.16",
                  "structural_text", "Sheet not found", False, "low")
            continue
        if old == AUDIT_SHEET:
            continue
        if new in wb.sheetnames and new != old:
            audit(audit_ws, f"sheet:{old}", "skip_sheet_rename_name_collision", old, "unchanged", "C.16",
                  "structural_text", f"Target name already in use", False, "low")
            continue
        if not item.get("dependency_safe"):
            audit(audit_ws, f"sheet:{old}", "skip_sheet_rename_not_dependency_safe", old, "unchanged", "C.16",
                  "structural_text",
                  "Rename requires dependency_safe:true from structural_text_surgery.py --plan",
                  False, "low")
            continue

        rewritten_formulas = 0
        for ws in wb.worksheets:
            max_row = min(ws.max_row or 0, 8000)
            max_col = min(ws.max_column or 0, 250)
            for row in ws.iter_rows(min_row=1, max_row=max_row, min_col=1, max_col=max_col):
                for cell in row:
                    v = cell.value
                    if not isinstance(v, str) or not v.startswith("="):
                        continue
                    nv = _rewrite_sheet_refs(v, old, new)
                    if nv != v:
                        cell.value = nv
                        rewritten_formulas += 1
            # Data-validation and conditional-formatting formulas.
            try:
                for dv in ws.data_validations.dataValidation:
                    for attr in ("formula1", "formula2"):
                        f = getattr(dv, attr, None)
                        if isinstance(f, str) and f:
                            nf = _rewrite_sheet_refs(f, old, new)
                            if nf != f:
                                setattr(dv, attr, nf)
                                rewritten_formulas += 1
            except Exception:
                pass
            try:
                for rng in ws.conditional_formatting:
                    for rule in rng.rules:
                        if getattr(rule, "formula", None):
                            rule.formula = [_rewrite_sheet_refs(f, old, new) if isinstance(f, str) else f
                                            for f in rule.formula]
            except Exception:
                pass

        rewritten_names = 0
        try:
            for name, defn in list(wb.defined_names.items()):
                if isinstance(getattr(defn, "value", None), str):
                    nv = _rewrite_sheet_refs(defn.value, old, new)
                    if nv != defn.value:
                        defn.value = nv
                        rewritten_names += 1
        except Exception:
            pass

        wb[old].title = new
        audit(audit_ws, f"sheet:{old}", "rename_sheet", old, f"renamed_refs_rewritten:"
              f"{rewritten_formulas}f/{rewritten_names}n", "C.16",
              item.get("runtime_source_class", "structural_text"),
              item.get("rationale", "Renamed prior-deal-named sheet to a generic equivalent; "
                                    "formula, defined-name, validation and conditional-format "
                                    "references rewritten in the same pass"),
              True, item.get("confidence", "high"))


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
    # Structural-text surgery (v4.8) runs before defined-name cleanup so a
    # renamed sheet's references are already rewritten when the name scrub
    # inspects them for #REF!.
    apply_structural_redactions(wb, audit_ws, decisions.get("structural_redactions", []))
    apply_sheet_renames(wb, audit_ws, decisions.get("sheet_renames", []))
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
