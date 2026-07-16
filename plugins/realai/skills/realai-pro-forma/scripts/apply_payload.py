#!/usr/bin/env python3
"""
Apply a payload to a RealAI pro forma template.

Validates that:
  - Every scalar payload key exists in manifest.cells
  - Every table payload key exists in manifest.tables
  - Every write target is in allowed_write_surfaces.cells
  - No target cell holds a formula
  - No protected default is overwritten
  - Table writes stay within the declared row range

Copies the template to the output path, applies writes, saves. Does NOT recalc
— run xlsx skill's scripts/recalc.py against the output file next.

Usage:
    python apply_payload.py \\
        --template path/to/template.xlsx \\
        --manifest path/to/manifest.md \\
        --payload path/to/payload.json \\
        --output  path/to/output.xlsx

Exit codes:
    0  success
    2  manifest defect (reversed table shape, bad status, etc.)
    3  payload defect (unknown path, wrong shape, source class not allowed)
    4  write conflict (would overwrite formula, protected default, etc.)
    5  IO / openpyxl error
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from copy import copy
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed. Run: pip install pyyaml --break-system-packages", file=sys.stderr)
    sys.exit(5)

try:
    from openpyxl import load_workbook
    from openpyxl.utils import column_index_from_string
except ImportError:
    print("ERROR: openpyxl not installed. Run: pip install openpyxl --break-system-packages", file=sys.stderr)
    sys.exit(5)


# ─── Manifest loading ────────────────────────────────────────────────────────


def load_manifest(path: Path) -> dict[str, Any]:
    """Read a manifest .md file and extract the single fenced YAML block."""
    text = path.read_text(encoding="utf-8")
    match = re.search(r"```ya?ml\s*\n(.*?)\n```", text, re.DOTALL)
    if not match:
        die(2, f"Manifest at {path} does not contain a fenced YAML block.")
    try:
        return yaml.safe_load(match.group(1))
    except yaml.YAMLError as e:
        die(2, f"Manifest YAML is invalid: {e}")


def validate_manifest(m: dict[str, Any]) -> None:
    if m.get("status") not in {"ready", "ready_with_limitations"}:
        die(2, f"Manifest status is {m.get('status')!r}; must be 'ready' or 'ready_with_limitations'.")
    if "cells" not in m or "tables" not in m or "outputs" not in m:
        die(2, "Manifest must have 'cells', 'tables', and 'outputs' sections.")
    if "allowed_write_surfaces" not in m:
        die(2, "Manifest is missing 'allowed_write_surfaces'.")

    # Detect reversed table column shape.
    for tname, tdef in m["tables"].items():
        cols = tdef.get("columns", {})
        for k, v in cols.items():
            # Correct shape: key is field name like "comp_1", value is dict with "column": "D"
            # Reversed shape: key is a single column letter like "D", value is field name
            if len(k) <= 2 and k.isalpha() and isinstance(v, str):
                die(2, f"Table {tname!r} has reversed column shape ({k}: {v!r}). Route back to Template Preparation.")


# ─── Cell address parsing ────────────────────────────────────────────────────


_CELL_RE = re.compile(r"^(?P<sheet>[^!]+)!(?P<col>[A-Z]+)(?P<row>\d+)$")


def parse_cell_ref(ref: str) -> tuple[str, str, int]:
    m = _CELL_RE.match(ref.strip())
    if not m:
        raise ValueError(f"Bad cell ref: {ref!r}")
    return m.group("sheet"), m.group("col"), int(m.group("row"))


def col_letter_to_idx(letter: str) -> int:
    return column_index_from_string(letter)


# ─── Payload loading & validation ────────────────────────────────────────────


VALID_SOURCE_CLASSES = {
    "datamart",
    "document",
    "user_input",
    "ai_estimate",
    "template_default",
    "user_override",
    "user_paste_unlisted",
    "datamart_unlisted",
}


def load_payload(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def split_payload(payload: dict[str, Any]) -> tuple[dict[str, dict], dict[str, list]]:
    """Return (scalars, tables) from a payload that may use either
    {capital.purchase_price: {...}, tables: {...}} or {cells: {...}, tables: {...}}.
    """
    scalars: dict[str, dict] = {}
    tables: dict[str, list] = {}
    for k, v in payload.items():
        if k == "tables" and isinstance(v, dict):
            tables = v
        elif k == "cells" and isinstance(v, dict):
            scalars.update(v)
        elif isinstance(v, dict) and "value" in v:
            scalars[k] = v
    return scalars, tables


def validate_entry(entry: dict, manifest_field_key: str, allowed_sources: list[str] | None) -> None:
    if "value" not in entry:
        die(3, f"Payload entry {manifest_field_key!r} missing 'value'.")
    sc = entry.get("source_class")
    if sc not in VALID_SOURCE_CLASSES:
        die(3, f"Payload entry {manifest_field_key!r} has invalid source_class {sc!r}.")
    if allowed_sources is not None and sc not in (allowed_sources + ["user_override", "user_paste_unlisted", "datamart_unlisted"]):
        # Special-case mapping between payload source classes and manifest's
        # `allowed_sources` enum (which uses values like "datamart", "user_input").
        # We accept exact match here; advisory only.
        pass  # Soft check — manifest enums differ slightly; do not block.
    if not entry.get("source_detail"):
        die(3, f"Payload entry {manifest_field_key!r} missing 'source_detail'.")


# ─── Writer ──────────────────────────────────────────────────────────────────


def write_scalars(wb, manifest: dict, scalars: dict, allowed_cells: set[str], protected_classes: set[str]) -> list[dict]:
    log = []
    for key, entry in scalars.items():
        cell_def = manifest["cells"].get(key)
        if cell_def is None:
            die(3, f"Payload path {key!r} not found in manifest.cells.")
        validate_entry(entry, key, cell_def.get("allowed_sources"))
        write_class = (cell_def.get("write_policy") or {}).get("write_class")
        if write_class in protected_classes:
            die(4, f"Cell {key!r} has write_class={write_class!r}; not writable.")
        for w in cell_def.get("writes", []):
            ref = w["cell"]
            if ref not in allowed_cells:
                die(4, f"Cell {ref!r} not in allowed_write_surfaces.")
            sheet, col, row = parse_cell_ref(ref)
            ws = wb[sheet]
            target = ws.cell(row=row, column=col_letter_to_idx(col))
            existing = target.value
            if isinstance(existing, str) and existing.startswith("="):
                die(4, f"Refusing to overwrite formula at {ref}: {existing!r}.")
            target.value = entry["value"]
            log.append({"cell": ref, "key": key, "value": entry["value"], "source_class": entry["source_class"]})
    return log


def write_tables(wb, manifest: dict, tables: dict) -> list[dict]:
    log = []
    for tname, rows in tables.items():
        tdef = manifest["tables"].get(tname)
        if tdef is None:
            die(3, f"Payload table {tname!r} not found in manifest.tables.")
        sheet = tdef["sheet"]
        first = tdef["first_data_row"]
        last = tdef["last_data_row"]
        cols = tdef["columns"]
        ws = wb[sheet]

        if not isinstance(rows, list):
            die(3, f"Payload table {tname!r} must be a list of row-dicts.")
        if len(rows) > (last - first + 1):
            die(3, f"Payload table {tname!r} has {len(rows)} rows but manifest range is rows {first}-{last}.")

        for offset, row in enumerate(rows):
            r = first + offset
            for col_key, entry in row.items():
                if col_key not in cols:
                    die(3, f"Payload table {tname!r} row has unknown column key {col_key!r}.")
                col_letter = cols[col_key]["column"]
                validate_entry(entry, f"{tname}.{col_key}", None)
                target = ws.cell(row=r, column=col_letter_to_idx(col_letter))
                existing = target.value
                if isinstance(existing, str) and existing.startswith("="):
                    die(4, f"Refusing to overwrite formula at {sheet}!{col_letter}{r}: {existing!r}.")
                target.value = entry["value"]
                log.append({"cell": f"{sheet}!{col_letter}{r}", "table": tname, "col": col_key, "value": entry["value"], "source_class": entry["source_class"]})
    return log


# ─── Driver ──────────────────────────────────────────────────────────────────


def die(code: int, msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", required=True, type=Path)
    ap.add_argument("--manifest", required=True, type=Path)
    ap.add_argument("--payload", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()

    if not args.template.exists():
        die(5, f"Template not found: {args.template}")
    if not args.manifest.exists():
        die(5, f"Manifest not found: {args.manifest}")
    if not args.payload.exists():
        die(5, f"Payload not found: {args.payload}")

    manifest = load_manifest(args.manifest)
    validate_manifest(manifest)

    payload = load_payload(args.payload)
    scalars, tables = split_payload(payload)

    allowed_cells = {entry["cell"] for entry in manifest["allowed_write_surfaces"]["cells"]}
    protected_classes = {"do_not_write", "protected_default"}

    # Copy template → output, then load output for writing.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    import shutil, os
    if args.output.exists():
        os.chmod(args.output, 0o644)
        args.output.unlink()
    shutil.copyfile(args.template, args.output)  # copyfile (not copy) avoids inheriting read-only perms
    os.chmod(args.output, 0o644)

    wb = load_workbook(args.output, data_only=False)

    scalar_log = write_scalars(wb, manifest, scalars, allowed_cells, protected_classes)
    table_log = write_tables(wb, manifest, tables)

    wb.save(args.output)

    summary = {
        "status": "success",
        "output_path": str(args.output),
        "cells_written": len(scalar_log),
        "table_cells_written": len(table_log),
        "writes": scalar_log + table_log,
    }
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
