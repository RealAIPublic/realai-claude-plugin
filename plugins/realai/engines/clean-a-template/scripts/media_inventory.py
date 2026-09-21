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
