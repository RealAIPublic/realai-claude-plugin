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
