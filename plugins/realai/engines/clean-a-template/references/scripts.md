# Scripts index

One row per bundled script. The code lives in `scripts/<name>.py` — real files,
seeded into the workspace at `skills/clean-a-template/scripts/`. No code is
embedded in this index.

Invoke as:

```bash
python skills/clean-a-template/scripts/<name>.py ...
```

**Integrity rule.** Run the bundled file and only the bundled file. Never retype,
trim, port, or "fix" a script, however it reached you — a partial replica runs,
emits well-formed JSON, and silently drops guard paths. If a script is missing
from the seeded skill files, stop with `needs_review` and name the missing file.
See SKILL.md § Execution Mandate.

**Dependencies.** Python with `openpyxl`, plus `PyYAML` for `tp_common.py`. Set
`REALAI_XLSX_SKILL_ROOT=skills/xlsx` once per run so the steps that call the xlsx
skill's helpers can find them.

## Shared

| Script | Phase | Purpose | Key flags | In → Out |
|---|---|---|---|---|
| `tp_common.py` | — | Shared primitives (manifest-style loaders, cell-ref parsing, xlsx-skill-root resolver, value helpers). Imported by the other scripts through a `sys.path` shim. **Never invoked directly.** Must sit beside them in `scripts/`. | — | — |

## Phase 1 — analysis

| Script | Purpose | Key flags | In → Out |
|---|---|---|---|
| `initial_triage.py` | Compatibility gate. Size, zip parts, macro detection, calculation settings, recalc method record. Fails fast on an unsupportable workbook. | `--out` | `model.xlsx` → `triage.json` |
| `extract_surface.py` | Per-sheet input-candidate surface: cells, value classes, styles, number formats, validation. | `--out`, `--max-candidates-per-sheet` (250) | `model.xlsx` → `surface.json` |
| `build_dependency_graph.py` | Direct and range-based dependency edges across sheets. | `--surface-json`, `--out` | `model.xlsx` (+ `surface.json`) → `graph.json` |
| `dependency_trace_report.py` | Transitive sheet-level trace. The evidence a sheet-deletion proposal requires. | `--out` (required) | `model.xlsx` → `dependency_trace.json` |
| `detect_conventions.py` | Currency scale, expense sign, iterative-calc requirement, time-axis candidates, primary projection axis. | `--out` | `model.xlsx` → `conventions.json` |
| `diagnose_workbook.py` | Diagnostic sweep against the catalog: formula/value errors, circular refs, external refs, broken names, placeholders. | `--out` | `model.xlsx` → `diagnostics.json` |
| `media_inventory.py` | Inventory of `xl/media/*`, drawings, and their relationships, for owner-logo classification. | `--out` (required) | `model.xlsx` → `media.json` |
| `classify_architecture.py` | Model-type signals → acquisition / value-add / development / conversion / waterfall / mixed-use. | `--out` | `model.xlsx` → `architecture.json` |
| `candidate_mapping.py` | **Three detectors in one run.** Tall regions (label col + value col, SUM-confirmed), wide regions (label col + data rectangle, for comp tables), and toggle-gated regions (a binary mode toggle plus the input block it gates, emitted under `gated_regions` / `toggle_cells`). Also emits the per-cell label surface. `table_regions.json` is the Phase 2 force-clear mask — gated blocks included. | `--out-tables` (required), `--out-candidates` (required), `--include-hidden`, `--min-rows`, `--max-gap` | `model.xlsx` → `table_regions.json`, `cell_candidates.json` |

## Phase 1/2 — inventory and clear list

| Script | Purpose | Key flags | In → Out |
|---|---|---|---|
| `comprehensive_input_inventory.py` | The decision engine. Classifies every candidate cell, force-clears inside detected regions, protects array-formula spill cells (`do_not_write`), clears un-allowlisted scalars by default, and emits the `clear_cells` draft plus the mandatory `cleared_by_default_needs_decision` triage list. **Always pass `--table-regions`.** Iterate with `--preserved-defaults` until the draft holds only deal facts. Run a **second time against the cleaned workbook** for the residual-value pass. | `--table-regions`, `--preserved-defaults`, `--out` (required), `--emit-decisions`, `--include-hidden`, `--max-rows-per-sheet` (8000), `--max-cols-per-sheet` (250) | `model.xlsx` + `table_regions.json` [+ `preserved_defaults.json`] → `input_inventory.json`, `decisions_clear_cells_draft.json` |

## Phase 2 — cleanup

| Script | Purpose | Key flags | In → Out |
|---|---|---|---|
| `structural_text_surgery.py` | **Plans only — writes nothing to the workbook.** Proposes the resolution of structural prior-deal leakage that clearing cannot reach: sheet tab names, banner/title cells, label cells, checklist rows. Emits `structural_redactions` (per-cell `before` → `replacement`) and `sheet_renames` (each with a `dependency_safe` verdict — unsafe when a chart or pivot cache holds its own copy of the sheet reference). Also lists **formula-baked deal amounts** as `blockers`: a formula with cell references *and* a large hardcoded amount is never rewritten, because extracting the constant changes the model. With `--leak-scan`, reconciles the plan against the scan so no structural finding is silently unaddressed. | `--decisions-json` (required, supplies `deal_strings`), `--leak-scan`, `--out` (required) | `model.xlsx` + `decisions.json` → `structural_surgery_plan.json` |
| `prepare_clean_template_v2.py` | Executes the approved decisions: clears cells, table rows and row labels, disguised constants; strips metadata and media; repairs or removes formulas; redacts structural text (`structural_redactions`) and performs dependency-safe sheet renames (`sheet_renames`, requires `dependency_safe: true`, rewriting formula / defined-name / validation / conditional-format references in the same pass); deletes traced sheets; writes the hidden `_PreparationAudit`. Then runs the three-substep integrity gate — Excel-Table `ref` reset, OOXML package surgery (`office/unpack.py` → `office/pack.py` → `office/validate.py`), and no-op recalc normalization (`recalc.py`). **`decisions.json` must contain a populated `clear_cells` array** — a missing key clears nothing, silently. | `--skip-package-surgery`, `--skip-normalization`, `--normalization-timeout` (90), `--out` (required) | `model.xlsx` + `decisions.json` → `model_cleaned.xlsx` + result JSON |
| `repair_broken_named_ranges.py` | Deterministic defined-name sanitation: removes `#REF!` names, repairs high-confidence ranges, preserves print areas and names retained formulas use. Run `--dry-run` first. | `--out`, `--dry-run` | `model_cleaned.xlsx` → repaired xlsx / findings |

## Phase 2B — proof

| Script | Purpose | Key flags | In → Out |
|---|---|---|---|
| `coverage_verify.py` | Intent-vs-result gate: compares the pre-clean inventory against the cleaned workbook and reports which `clear`-disposition cells still hold values. Catches the orchestrator-missed-cells failure mode. Exit 2 above `--max-uncleared`. | `--inventory` (required), `--out` (required), `--max-uncleared` (20) | `model_cleaned.xlsx` + `input_inventory.json` → `coverage_report.json` |
| `post_clean_leak_scan.py` | The leak scan. Walks visible and hidden sheets, defined names, formula text and embedded hardcodes, comments and threaded comments, document properties, headers/footers, text boxes and alt text, chart text, pivot caches, validation lists, conditional formatting, customXml, external links, and media relationships — plus **sheet tab names**, distinctive deal TOKENS on structural surfaces (banner titles, label cells, checklist rows), and toggle-gated regions in both directions (residue left in a gated block, and a toggle control that was cleared). **Always pass `--table-regions`** so table-region and gated-region residue are both caught. Findings are redacted — coordinate, code, hash, value class only. Severity tiers: `blocking` / `review` / `info`. Exit 2 on any blocking finding. | `--decisions-json`, `--table-regions`, `--preserved-defaults`, `--cross-check`, `--out` (required) | `model_cleaned.xlsx` (+ decisions, regions, defaults) → `leak_scan.json` |

The residual-value pass uses `comprehensive_input_inventory.py` a second time — see its row above and `phase2_remediation.md` § Residual-value pass.

## Caller-facing utility — not a phase of this workflow

| Script | Purpose | Key flags | In → Out |
|---|---|---|---|
| `xlsm_triage_convert.py` | **Macro gate.** Analyzes an `.xlsm`'s VBA project **without executing it**, scans the VBA source for deal-string leakage, inventories functions and auto-exec events, and emits a macro-stripped `.xlsx` when the proof obligations hold (no UDFs referenced by formulas, no auto-exec or calculation-driving events). Verdict routing: `strippable` → continue on the converted file and carry `removed_macro_inventory` into the audit; `needs_review` → present the function/event inventory via `ask_user`, then re-run with `--approve-strip`; `not_strippable` → refuse with the report's reason. | `--out` (required), `--decisions-json`, `--convert-out`, `--approve-strip` | `model.xlsm` → `xlsm_report.json`, `model_converted.xlsx` |

| `predelivery_check.py` | **Pre-delivery gate.** Caller-facing. Fails a run that is about to hand over a bad workbook: filename pattern on disk, the source not delivered as itself, placeholders or Excel errors **this run introduced**, and a full-recalc flag on the final file. Checks C and D are diffs against `--source`, not absolute scans — the pristine house template holds 209 em-dashes, 5 hyphens and 4 literal `N/A` cells as formatting, so an absolute scan flags 218 and blocks everything, while the diff finds the 102 that staging run 3 actually wrote. Without `--source` both degrade to advisory and say so. Exit 2 = do not deliver. | `--subject`, `--source`, `--text`, `--date`, `--allow-placeholder`, `--json` | `delivered.xlsx` → stdout + optional JSON |

**Why `predelivery_check.py` is bundled here.** Same reason as the macro gate
below: a caller needs it, and this is the skill with a `scripts/` directory. **The
cleaning workflow never runs it** — it checks a *populated* workbook, and cleaning
never populates anything. Run it on the final path, after any copy or rename: one
staging run recalculated, then `cp`-ed the result to the delivered name, and
shipped 61 `#DIV/0!` cells the earlier recalc had already reported.

**Why it is bundled here.** A caller that meets an `.xlsm` needs a real macro gate
and the calling agents have no scripts directory of their own; every file in a skill
directory is seeded into the sandbox independently of whether the skill was
loaded, so a caller can run this one directly. **The cleaning workflow never runs
it** — this skill's own intake refuses `.xlsm` and asks for a macro-free copy.
Never execute VBA under any verdict.

## Retired with the mapping phase — not in this bundle

| Script | Was | Where its job went |
|---|---|---|
| `manifest_lint.py` | Static manifest lint + the C.9 leakage check and defaults-evidence gate | Manifest lint is gone with the manifest. The leakage check is reproduced by the residual-value pass; the automatic `default_without_evidence` warning has no replacement and is a known gap (see C.9). |
| `verify_write_preflight.py` | Wrote placeholder values to every mapped input on a scratch copy | The consuming flow's own write preflight. This skill never populates a template. |
| `sniff_test.py` | Wrote a payload, recalculated, read mapped outputs, returned production readiness | The consuming flow's recalc + economic sniff. The cleaning-side equivalent is the quiet economic check, which reads output cells without writing anything. |
