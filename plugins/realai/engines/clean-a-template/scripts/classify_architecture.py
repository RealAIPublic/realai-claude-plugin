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
