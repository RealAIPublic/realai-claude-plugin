#!/usr/bin/env python3
"""Fail a run that is about to deliver a bad workbook. Caller-facing.

Every check here was a prose rule first, and every one of them was broken anyway
in a staging run while the rule sat in the prompt being ignored. The project's
own lesson, from HANDOVER §5, is mechanical gates over prose — but a paragraph
telling a model to check itself is still prose. This is the gate.

    python3 predelivery_check.py delivered.xlsx --subject "Griffis Edgemoor" \
        --source RealAI_Pro_Forma_Template_v4.xlsx \
        --text briefing.md agent.md

Exit 0 = deliver.  Exit 2 = do not deliver; fix what is named and re-run.
Exit 1 = the check could not run (missing file, unreadable workbook). Also do
not deliver: an unverified file is not a verified one.

**Run it on the final path, after any copy or rename.** That is the point of
check E — one staging run recalculated, then `cp`-ed the result to the delivered
name, and shipped 61 `#DIV/0!` cells the earlier recalc had already reported.
Verifying an ancestor of the file you hand over verifies nothing.

Checks, all deterministic:

  A  filename         {Subject}_underwriting_{YYYY-MM-DD}.xlsx on disk   (R06)
  B  source untouched delivered path != source path                      (R18)
  C  placeholders     no placeholder THIS RUN introduced                 (R07)
  D  error cells      no error cell THIS RUN introduced                  (R17)
  E  freshness        the workbook carries a full-recalc flag            (R16)

C and D are DIFFS against --source, not absolute scans, and that is not a
refinement — an absolute scan is unusable. Measured on the pristine RealAI house
template, before any run touches it: 209 cells holding an em-dash, 5 holding a
hyphen, and 4 holding the literal string "N/A". All of it is the template's own
formatting convention. Scanning absolutely flags 218 cells and blocks every
delivery; diffing against the source flags the 102 "N/A" cells staging run 3
actually wrote, which is exactly the number in that run's answer key.

Without --source, C and D degrade to advisory and say so. A blocking check with
a 218-cell false-positive floor is worse than no check: it gets switched off,
and then the real 102 ship.

Advisory, because it needs judgment and a false positive must not block a
delivery: currency figures found in --text deliverables (R03). A briefing shipped
the prior deal's NOI, exit value, and loan amount while the rule scored a pass,
because the rule only covered chat. The script lists candidates; a human or an
agent decides which came from the prior deal.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

try:
    import openpyxl
except ImportError:                                    # pragma: no cover
    print("predelivery_check: openpyxl unavailable", file=sys.stderr)
    raise SystemExit(1)

# Exactly the strings observed written into model cells across staging runs,
# plus the obvious neighbours. A bare hyphen and "Not disclosed" are here
# because a run wrote both into comp rectangles.
PLACEHOLDERS = {
    "n/a", "n.a.", "na", "-", "--", "—", "–", "tbd", "tba", "not available",
    "unavailable", "not disclosed", "undisclosed", "unfindable",
    "not in datamart", "not populated", "unknown", "none available",
    "no data", "n/m", "nm", "not applicable", "?", "???",
}
ERRORS = {"#DIV/0!", "#VALUE!", "#REF!", "#NAME?", "#N/A", "#NULL!", "#NUM!", "#SPILL!", "#CALC!"}

CURRENCY = re.compile(r"\$\s?\d[\d,]*(?:\.\d+)?\s*(?:[MmKkBb]\b|million|billion|thousand)?")

INTERNAL_SHEETS = {"_PreparationAudit", "_Data", "_SensCalc"}


def slug(s: str) -> str:
    """'Griffis Edgemoor' -> 'griffisedgemoor'. Comparison only, never output."""
    return re.sub(r"[^a-z0-9]", "", s.lower())


def check_filename(path: Path, subject: str, run_date: str) -> list[str]:
    m = re.fullmatch(r"(.+)_underwriting_(\d{4}-\d{2}-\d{2})\.xlsx", path.name)
    if not m:
        return [f"A filename: {path.name!r} is not "
                f"{{SubjectProperty}}_underwriting_{{YYYY-MM-DD}}.xlsx"]
    got_subject, got_date = m.group(1), m.group(2)
    out = []
    if slug(subject) and slug(got_subject) != slug(subject):
        out.append(f"A filename: names {got_subject!r}, but the subject of this run "
                   f"is {subject!r}")
    if got_date != run_date:
        out.append(f"A filename: dated {got_date}, expected {run_date}")
    return out


def check_source(delivered: Path, source: Path | None) -> list[str]:
    if source is None:
        return []
    if not source.exists():
        return [f"B source: {source} does not exist — cannot prove it was untouched"]
    if delivered.resolve() == source.resolve():
        return [f"B source: delivering the source file itself ({source.name}). "
                f"Write to a copy"]
    return []


def cell_map(path: Path) -> dict[str, str]:
    """{'Sheet!A1': 'stripped string value'} for every string cell.

    data_only=True so cached results are visible: an Excel error is a cached
    value, never a formula, so a formulas-only read cannot see one.
    """
    wb = openpyxl.load_workbook(path, data_only=True)
    out: dict[str, str] = {}
    try:
        for ws in wb.worksheets:
            if ws.title in INTERNAL_SHEETS:
                continue
            for row in ws.iter_rows():
                for c in row:
                    if isinstance(c.value, str):
                        s = c.value.strip()
                        if s:
                            out[f"{ws.title}!{c.coordinate}"] = s
    finally:
        wb.close()
    return out


def classify(cells: dict[str, str]) -> tuple[dict[str, str], dict[str, str]]:
    """Split a cell map into (placeholders, error cells)."""
    ph = {k: v for k, v in cells.items() if v.lower() in PLACEHOLDERS}
    er = {k: v for k, v in cells.items() if v in ERRORS}
    return ph, er


def introduced(delivered: dict[str, str], source: dict[str, str] | None
               ) -> tuple[dict[str, str], dict[str, str], bool]:
    """What this run added. Returns (placeholders, errors, was_diffed).

    A cell counts as introduced when it now holds a placeholder or an error and
    did not hold that same value in the source. A cell the template always had
    is the template's business.
    """
    ph, er = classify(delivered)
    if source is None:
        return ph, er, False
    sph, ser = classify(source)
    return ({k: v for k, v in ph.items() if source.get(k) != v},
            {k: v for k, v in er.items() if source.get(k) != v},
            True)


def check_freshness(path: Path) -> list[str]:
    """Did anything ask Excel to recalculate this file on open?

    Detective, not preventive: we cannot recalc here. If the workbook neither
    carries fullCalcOnLoad nor has cached values, the outputs a run read back
    were stale or absent.
    """
    wb = openpyxl.load_workbook(path)
    props = getattr(wb, "calculation", None)
    full = bool(getattr(props, "fullCalcOnLoad", False)) if props else False
    wb.close()
    if full:
        return []
    return ["E freshness: workbook does not carry fullCalcOnLoad. Confirm the "
            "delivered file was recalculated AFTER its last copy or rename"]


def check_text(paths: list[Path], subject: str) -> list[str]:
    """Advisory. Currency in a delivered text file, minus the subject's own."""
    out = []
    for p in paths:
        if not p.exists():
            out.append(f"  {p}: not found")
            continue
        found = sorted(set(CURRENCY.findall(p.read_text(errors="replace"))))
        if found:
            out.append(f"  {p.name}: {', '.join(found[:12])}"
                       + (f" … +{len(found)-12} more" if len(found) > 12 else ""))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Pre-delivery gate for a populated workbook.")
    ap.add_argument("workbook", type=Path, help="the file you are about to deliver")
    ap.add_argument("--subject", default="", help="subject property name")
    ap.add_argument("--source", type=Path, help="the template or upload this came from")
    ap.add_argument("--text", type=Path, nargs="*", default=[],
                    help="delivered text files to scan for prior-deal figures (advisory)")
    ap.add_argument("--date", default=date.today().isoformat(), help="run date, YYYY-MM-DD")
    ap.add_argument("--allow-placeholder", action="append", default=[],
                    help="a cell coordinate that may legitimately hold one, e.g. 'Notes!B4'")
    ap.add_argument("--json", type=Path, help="also write the result here")
    a = ap.parse_args()

    if not a.workbook.exists():
        print(f"predelivery_check: {a.workbook} does not exist", file=sys.stderr)
        return 1

    failures: list[str] = []
    failures += check_filename(a.workbook, a.subject, a.date) if a.subject else []
    failures += check_source(a.workbook, a.source)

    try:
        delivered = cell_map(a.workbook)
        source = cell_map(a.source) if (a.source and a.source.exists()) else None
    except Exception as e:
        print(f"predelivery_check: cannot read a workbook: {type(e).__name__}: {e}",
              file=sys.stderr)
        return 1

    ph, er, diffed = introduced(delivered, source)
    allowed = set(a.allow_placeholder)
    ph = {k: v for k, v in ph.items() if k not in allowed}

    notes: list[str] = []
    if not diffed:
        notes.append(
            "C/D ran WITHOUT a baseline, so they are ADVISORY. Pass --source to make "
            "them blocking. Absolute scanning flags the template's own dashes and "
            "N/A cells — 218 of them on the house template — so a hit here is not "
            "evidence this run wrote anything.")

    def fmt(d: dict[str, str], limit: int = 25) -> list[str]:
        items = [f"    {k}  {v!r}" for k, v in list(d.items())[:limit]]
        if len(d) > limit:
            items.append(f"    … and {len(d)-limit} more")
        return items

    verb = "introduced" if diffed else "present"
    if ph:
        line = f"C placeholders: {len(ph)} cell(s) {verb} holding narration of an absence"
        (failures if diffed else notes).append(line)
        (failures if diffed else notes).extend(fmt(ph))
    if er:
        line = f"D error cells: {len(er)} cell(s) {verb} carrying an Excel error"
        (failures if diffed else notes).append(line)
        (failures if diffed else notes).extend(fmt(er))

    failures += check_freshness(a.workbook)

    advisory = check_text(a.text, a.subject) if a.text else []

    print(f"predelivery_check: {a.workbook.name}"
          + (f"   (baseline: {a.source.name})" if diffed else "   (NO BASELINE)"))
    if failures:
        print(f"\nRESULT: DO NOT DELIVER — {sum(1 for f in failures if f[:2].strip() and f[0].isalpha() and f[1] == ' ')} check(s) failed\n")
        for f in failures:
            print(f"  {f}" if not f.startswith("    ") else f)
    else:
        print("\nRESULT: OK — all checks passed")

    if notes:
        print("\nNOTES")
        for n in notes:
            print(f"  {n}" if not n.startswith("    ") else n)

    if advisory:
        print("\nADVISORY — currency in delivered text (R03). Confirm none of these "
              "came from the PRIOR deal:")
        for line in advisory:
            print(line)

    if a.json:
        a.json.write_text(json.dumps({
            "workbook": str(a.workbook),
            "passed": not failures,
            "failures": failures,
            "advisory_currency": advisory,
            "baseline_used": diffed,
            "placeholder_cells": ph,
            "error_cells": er,
            "notes": notes,
        }, indent=1))

    return 2 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
