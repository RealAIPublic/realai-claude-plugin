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

