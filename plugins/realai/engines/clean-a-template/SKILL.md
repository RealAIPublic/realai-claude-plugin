---
name: clean-a-template
description: "Strips prior-deal data out of a populated Excel underwriting model and returns a clean, reusable template: clears deal facts, table rows and row labels, disguised constants, media, and metadata leakage, then runs a deterministic post-clean leak and workbook-integrity scan. Use when the user wants an existing model cleaned, reset, or made reusable — \"clean my model\", \"prepare this template\", \"strip the old deal out of this workbook\", \"make this reusable\", \"remove the property data from my workbook\" — or when another agent's cleanliness gate needs a populated template cleaned before it can proceed. Takes one macro-free .xlsx; returns the cleaned .xlsx, a cleared/preserved/needs-review report, and a hidden _PreparationAudit sheet. It produces no field mapping and no manifest. Do NOT use to populate or underwrite a template (Proforma via Template), to build a pro forma or value a property (the analysis agents), or to turn a template into a population agent — that flow is not currently offered."
license: Proprietary
---

# Clean a Template

# Contents

- Purpose and boundary
- Execution Mandate: read this first
- Governing principle — runtime source classification
- Non-negotiable decisions
- Intake
- Workflow: Phase 1 → Phase 2 → Phase 2B
- Final delivery format
- Guardrails
- Reference files

# Purpose and boundary

Turn a populated, macro-free Excel underwriting model into a clean, reusable
template. Nothing is underwritten here and nothing is analyzed — this is workbook
hygiene: prior-deal facts out, reusable model logic in.

**What goes in.** One macro-free `.xlsx` workbook, plus optional user notes on
anything to preserve.

**What comes out.**

1. `{name}_cleaned.xlsx` — the cleaned template. Safe to share externally, opens
   without Excel repair, reusable model logic and formatting intact.
2. A short cleanliness report — cleared / preserved / needs-review **counts**,
   the readiness status, and one blocking reason if not `ready`.
3. The hidden `_PreparationAudit` sheet inside the cleaned workbook.

**What is never done.** No field mapping — no semantic roles, no write surfaces,
no payload paths, and **no manifest of any kind**. This skill detects that a
region is a table; it never decides what the table *means*. It does not generate
an agent, populate or refill a template (not even a scratch copy), underwrite,
value, or project anything. It does not package or emit a downloadable skill.

Field mapping and agent generation are out of scope here, and no flow currently
offers them. Populating a prepared template belongs to **Proforma via Template**.

# Execution Mandate: read this first

**This skill does not clean workbooks in prose. It runs bundled scripts.**

Python does detection, inventory, cleanup, and scanning. The LLM applies real
estate judgment on top of that mechanical evidence and logs material decisions
with evidence and confidence. Excel is the math authority — never re-derive model
logic by hand when the formula graph can be read.

**Script integrity.** Every script is a real file seeded into the workspace at
`skills/clean-a-template/scripts/<name>.py`. Run the bundled file and only the
bundled file:

- Never retype, trim, paraphrase, port, or "fix" a bundled script, regardless of
  how it reached you. A plausible-looking partial replica runs, emits well-formed
  JSON, and silently omits entire guard paths — including the spill-range and
  clear-by-default protections that exist because they each shipped a real leak.
- Never write new cleanup code alongside the bundle. The scripts are the pinned
  implementation so that two runs on the same workbook clear the same cells.
- `tp_common.py` holds the shared primitives every other script imports through a
  `sys.path` shim; it must sit beside them in `scripts/` and is never invoked
  directly.
- If a script is missing from the seeded skill files, **stop with `needs_review`**
  and report which file is absent. Do not reconstruct it.

**Packages.** The scripts need `openpyxl` and nothing else — no network access, no
runtime installs. (`tp_common.py` imports `PyYAML` behind a `try/except`, but only
its unused manifest loader needs it, so its absence is harmless.) If `openpyxl` is
unavailable, stop with `needs_review` rather than substituting another library.

**xlsx-skill dependency.** Three steps call the `xlsx` skill's helpers:
`prepare_clean_template_v2.py` (package surgery via `office/unpack.py` →
`office/pack.py` → `office/validate.py`, and normalization via `recalc.py`) and
`post_clean_leak_scan.py --cross-check` (`workbook_search.py`). The xlsx skill is
seeded at `skills/xlsx/`. Point the pipeline at it once, at the start of the run:

```bash
export REALAI_XLSX_SKILL_ROOT=skills/xlsx
```

The scripts also carry a filesystem-walk fallback that finds
`<dir>/skills/xlsx/scripts/recalc.py` by walking up from the working directory,
which resolves correctly in this sandbox — **but set the variable explicitly
anyway.** When neither path resolves, the affected substeps emit
`skipped_no_skill_root`, the cleaned file is still produced, and the workbook
integrity gate degrades from preventive to detective: readiness is capped at
`ready_with_limitations` and drops to `needs_review` if anything else is
unresolved. Never copy an xlsx helper into this bundle.

# Governing principle — runtime source classification

For every input-like value, table, row label, hardcoded assumption, image,
defined name, and support sheet, classify it into one of these runtime source
classes. The class is what makes the clear-or-preserve call correct: it names
where the value will come from the next time this template is used.

| Class | Meaning | Default cleanup action |
|---|---|---|
| `datamart_required` | Must come from the datamart; a user-supplied value is not enough | Clear |
| `datamart_preferred_user_fallback` | Datamart when available; the user may supply it if missing | Clear |
| `user_required` | Deal-specific input the user must supply | Clear |
| `approved_ai_estimate_allowed` | AI may estimate it only with explicit provenance and audit | Clear unless also a reusable default |
| `template_default` | Reusable model assumption or policy | Preserve and protect |
| `derived_formula` | Formula-driven model logic | Preserve unless broken and unfixable |
| `do_not_write` | Structural, output, or protected logic | Preserve or clear by type; nothing downstream may write here |

**Only `template_default` and `derived_formula` values may remain populated in
the cleaned workbook.** Everything else is cleared.

# Non-negotiable decisions

Apply without asking, unless new evidence directly contradicts them.

- **Unit mix row labels are deal-specific. Delete both labels and values.**
- **Existing-property facts have no template fallback.** Units, rentable SF,
  in-place rent, rent roll, parking, costs, property facts, and capital-stack
  facts may never survive as a template default.
- **Only template-owner logos may remain.** Remove photos, property images, maps,
  and unknown logos unless the user explicitly approves them.
- **Delete worksheets only after a full transitive dependency trace.**
- **Repair broken formulas only when context gives high confidence**; otherwise
  remove and trace dependents. Do not mark the template `ready` if a retained
  output depends on removed logic.
- **Cells inside detected runtime-input table regions are runtime input, not
  reusable defaults.** They are force-cleared regardless of any allowlist.
- **A region behind a binary mode toggle is runtime input whatever the toggle
  currently reads.** Toggle state is a user choice, not evidence about what the
  region holds. The toggle control itself is `template_default` and survives.
- **Structural text is redacted, not cleared.** A prior deal's name in a sheet
  tab, a banner title, a label, or a checklist row is replaced with a generic
  equivalent — blanking it would delete the template's own scaffolding.
- **A formula that carries references AND a hardcoded deal amount is never
  rewritten.** It goes to the user as a blocking decision. **Two or more distinct
  literals inside a clamp (`MIN`/`MAX`/`MEDIAN`/`PERCENTILE`) are a normalization
  scale, not a deal amount** — reported `formula_scale_constant` at info severity
  and left alone. The rule keys off the literal count, not the function name.
- **A label naming a unit type *and* a measure is a template header, not a
  unit-mix row label.** `Studio — In-Place Rent` is scaffolding; `Studio` is deal
  data. Headers are preserved and reported `unit_mix_metric_header` (info).

# Intake

Ask for one `.xlsx` model file and optional notes about anything to preserve.

**Refuse `.xlsm` and workbooks containing VBA** (diagnostic C.5): explain in one
sentence and ask for a macro-free `.xlsx` copy. Never execute VBA.

> When a calling agent has already run a macro gate and converted the workbook,
> the converted `.xlsx` is the input — clean that file, never the original
> `.xlsm`. See the note on `xlsm_triage_convert.py` in
> [references/scripts.md](references/scripts.md); it is a caller-facing utility,
> not a phase of this workflow.

If the workbook contains images or logos and the template owner is unknown, ask
which organization's logo may remain. Remove ambiguous media by default.

**Output discipline throughout.** Be concise and decision-oriented. Do not narrate
cell-by-cell detail unless asked. Emit `ask_user` forms only for material
judgment calls, recommendation-first; once the user decides, it is settled — do
not repeat the caveat in later summaries. **Never expose raw prior-deal values**
in chat, in the report, or in the audit sheet.

# Workflow

Phase 1 detects. Phase 2 cleans. Phase 2B proves it. Flag-don't-fix throughout.

Copy this checklist and check items off as you go. Steps 4 and 5 are the two that
silently ruin a run when skipped — a missing `clear_cells` key clears nothing, and
an untriaged bucket leaks every value in it.

```
Cleaning progress:
- [ ] 1. Triage the file (initial_triage.py) — stop here if not compatible
- [ ] 2. Phase 1 analysis scripts + candidate_mapping.py (table_regions.json)
- [ ] 3. Readiness card + one ask_user form for material decisions only
- [ ] 4. Inventory with --table-regions, emitting the clear-list draft
- [ ] 5. TRIAGE cleared_by_default_needs_decision → clear or evidenced default
- [ ] 6. Structural surgery plan (structural_text_surgery.py) — resolve blockers
- [ ] 7. Merge clear_cells + redactions + renames into decisions.json  ← verify keys
- [ ] 8. Clean (prepare_clean_template_v2.py) + repair named ranges
- [ ] 9. Coverage gate (coverage_verify.py)
- [ ] 10. Leak scan (post_clean_leak_scan.py, --table-regions)
- [ ] 11. Residual-value pass (second inventory on the cleaned file)
- [ ] 12. Exit gate — all nine rows pass
- [ ] 13. Deliver file + counts + status
```

Any failure at 9, 10, 11, or 12 returns to step 5 or 6, not to step 8 — the fix
is almost always a triage, allowlist, or structural-plan decision, not a re-run
of the cleaner.

## Phase 1 — Analysis and source-of-truth classification

Inspect without modifying. Run the deterministic scripts, then classify.

```bash
python skills/clean-a-template/scripts/initial_triage.py model.xlsx --out triage.json
python skills/clean-a-template/scripts/extract_surface.py model.xlsx --out surface.json
python skills/clean-a-template/scripts/build_dependency_graph.py model.xlsx --surface-json surface.json --out graph.json
python skills/clean-a-template/scripts/dependency_trace_report.py model.xlsx --out dependency_trace.json
python skills/clean-a-template/scripts/detect_conventions.py model.xlsx --out conventions.json
python skills/clean-a-template/scripts/diagnose_workbook.py model.xlsx --out diagnostics.json
python skills/clean-a-template/scripts/media_inventory.py model.xlsx --out media.json
python skills/clean-a-template/scripts/classify_architecture.py model.xlsx --out architecture.json
```

If `initial_triage.py` reports the file incompatible, stop and explain the
blocker in one short paragraph.

Then detect table regions and the per-cell label surface:

```bash
python skills/clean-a-template/scripts/candidate_mapping.py model.xlsx \
    --out-tables table_regions.json \
    --out-candidates cell_candidates.json
```

Phase 1 produces:

- **`table_regions.json`** — every detected runtime-input table region, tall and
  wide. This is the Phase 2 **force-clear mask**. Non-negotiable. The same file
  carries `gated_regions` and `toggle_cells`: binary mode toggles ("Use Staged
  Inputs = No") and the input blocks they gate. **A gated block is part of the
  force-clear mask.** Read the toggle-gated-region rule below before triaging
  anything inside one.
- **`cell_candidates.json`** — a per-cell label inventory (left labels, above
  labels, section header, named-range membership, value class, in-region flag).
  Emitted as evidence and left on disk for a caller. **This skill never consumes
  it to assign meaning to a cell** — that is mapping, and mapping is out of scope.
- **Diagnostics** per [references/diagnostic_catalog.md](references/diagnostic_catalog.md).

Produce a readiness card:

```
Status: [proceed / needs_review / not_compatible]
Model type: [acquisition / value_add / development / conversion / waterfall / mixed_use / unknown]
Projection basis: [annual / monthly / quarterly / mixed / unknown]
Currency scale: [$ / $000 / $M / mixed / unknown]
Detected table regions: <count> (<high-confidence count> with SUM confirmation)
Key finding: [one sentence]
```

Model type, basis, and currency scale are not decoration: they change what counts
as a deal fact and what a suspicious number looks like.

Identify only the decisions that matter, and emit an `ask_user` form **only** for
unresolved material ones:

| Decision group | When it applies |
|---|---|
| Template owner identity and logos to preserve | Workbook contains images and the owner is unknown |
| Ambiguous reusable defaults (scalar cells only) | A scalar could be model policy or a stale deal assumption |
| Sheets proposed for deletion | Dependency trace came back clean but the sheet's purpose is unclear |
| Broken formulas that cannot be confidently repaired | Intent not inferable from context |
| Unsupported modes or features | A section cannot be cleaned safely |
| External links or named ranges requiring cleanup | Removal would change retained logic |

**Do not ask whether table-region cells should be cleared — they always are.** Do
not re-ask anything already settled by the non-negotiables. Do not include raw
prior-deal values in the form.

### Toggle-gated regions — read before triaging anything inside one

A binary mode toggle gates a block of inputs the model ignores while the toggle
is off: *"Use Staged Inputs = No"* over a year-by-year override grid, *"Co-Invest
/ Promote Structure = No"* over a promote waterfall. Those inputs are still
runtime input. The next person to flip the toggle activates whatever is sitting
there, silently, and it will be the previous deal's numbers.

`candidate_mapping.py` marks these deterministically and the inventory
force-clears them. **Do not reason your way out of it.** Two things make that
tempting, and both are traps:

- **The template documents the region as optional.** Real templates explain
  themselves in the rows beside the toggle — *'"No" = uses the single rates
  above'*, *'If "No", waterfall is bypassed'*. That text describes the model's
  behavior, not the provenance of the values.
- **The block looks exactly like a policy default.** Gated blocks are filled
  uniformly across periods or tiers, which is the `parallel_siblings` shape the
  evidenced-defaults rule accepts as proof of a reusable default. Inside a gated
  region that shape proves nothing: a uniform 3% across ten years is what a
  staged-input grid looks like *and* what a growth policy looks like.

So `parallel_siblings` is not accepted inside a gated region. The only way a
cell there survives is `"approved_region_exception": true` on its
`preserved_defaults.json` entry, set after explicit user approval in the Phase 1
form — the same narrow escape the table-region path uses.

The toggle cell itself is preserved, in the position the template's author left
it. Clearing the control is its own defect (`toggle_control_cleared` in the leak
scan): it hands the user a template whose mode switch is gone.

A multi-way **mode selector** ("Interest Only / IO Then Amortizing / Fully
Amortizing") is not a gate — it picks between branches that are all live — and
is left to the ordinary path.

Full detail: [references/phase1_analysis.md](references/phase1_analysis.md).

## Phase 2 — Cleanup / remediation

### The pre-flight gate — do not skip this

Build the inventory and the clear list before touching the workbook. **`decisions.json`
MUST contain a populated `clear_cells` array.** A missing key silently passes an
empty list: nothing is cleared, the workbook looks processed, and every
prior-deal value survives.

```bash
python skills/clean-a-template/scripts/comprehensive_input_inventory.py model.xlsx \
    --table-regions table_regions.json \
    --out input_inventory.json \
    --emit-decisions decisions_clear_cells_draft.json
```

Always pass `--table-regions`. Without it the force-clear mask is silently
skipped and table cells fall back to allowlist-trusting behavior.

Then, in order:

1. Review `decisions_clear_cells_draft.json`.
2. **Triage `cleared_by_default_needs_decision`.** Every entry is routed to
   exactly one of: left in `clear_cells` (the safe default), or moved to
   `preserved_defaults.json` **with evidence** that it is reusable policy. Never
   empty this list by deleting entries.
3. Re-run with `--preserved-defaults preserved_defaults.json` until the draft
   contains only deal facts.
4. Merge the draft's `clear_cells` into `decisions.json` under the `clear_cells`
   key.
5. Plan the structural surgery (below) and merge its output.
6. Only then run the cleanup.

### Structural surgery — the surfaces clearing cannot reach

Clearing handles values. A prior deal's name also lives in surfaces that hold no
value and therefore survive every clearing pass: **sheet tab names**, **banner
and title cells**, **label cells**, **checklist rows**. On our own house template
these are clean. On a real user model they are the norm — and they are not
clearable, because blanking `'MODERA WALSH - DEBT STRUCTURE'` deletes the
sheet's title. The fix is redaction to a generic equivalent.

```bash
python skills/clean-a-template/scripts/structural_text_surgery.py model.xlsx \
    --decisions-json decisions.json \
    --leak-scan leak_scan.json \
    --out structural_surgery_plan.json
```

The script writes nothing to the workbook. It emits a plan:

- **`structural_redactions`** — per-cell `before` → `replacement`. Review each,
  then merge into `decisions.json` under the same key.
- **`sheet_renames`** — per-tab, each with a `dependency_safe` verdict. Merge the
  safe ones. openpyxl does not rewrite formula references when a sheet is
  renamed, so the applier rewrites formulas, defined names, validation and
  conditional-format references in the same pass; a rename is refused when a
  chart or pivot cache holds its own copy of the reference, because those are
  not rewritten. Refused renames arrive as blockers.
- **`blockers`** — findings that need the user, each with the recommendation to
  put in front of them. Every one is resolved before delivery.
- **`reconciliation.unaddressed_structural_findings`** — structural findings the
  leak scan raised that the plan does not cover. A non-empty list means the plan
  is incomplete; do not proceed with it.

**Formula-baked deal amounts are blockers, never edits.** A formula that carries
cell references *and* a large hardcoded dollar figure in its body — `=C6/91327500`
— is live model logic computing off the previous deal's number. Do not rewrite
it: extracting the constant into an input cell changes the model's logic, and
that is the user's call. Surface each one with the recommendation (extract to an
input cell, or approve it as a genuine template constant) and let them decide.
**Readiness cannot be `ready` while an unresolved formula-baked deal amount
remains** — the template still computes off the prior deal. This is distinct
from the arithmetic-only disguised constant (`=168227*2`), which has no
references, is not model logic, and is cleared by the existing rule.

```bash
python skills/clean-a-template/scripts/prepare_clean_template_v2.py model.xlsx decisions.json --out model_cleaned.xlsx
```

Required cleanup rules: clear all runtime deal facts; preserve only true reusable
scalar defaults and valid formulas; clear table data to schema (headers,
formatting, validation, and formulas preserved); remove photos and
non-template-owner logos; sanitize defined names and external references; repair
broken formulas only on high-confidence context; delete only sheets that pass a
full dependency trace; add or update the hidden `_PreparationAudit` sheet with no
raw prior-deal values.

Defined-name repair, when needed:

```bash
python skills/clean-a-template/scripts/repair_broken_named_ranges.py model_cleaned.xlsx --dry-run
```

Then the coverage gate — did the cleanup actually clear what the inventory said
it would?

```bash
python skills/clean-a-template/scripts/coverage_verify.py model_cleaned.xlsx \
    --inventory input_inventory.json \
    --out coverage_report.json \
    --max-uncleared 0
```

`--max-uncleared 0` because a correctly executed sequence leaves **zero**
uncleared inventory cells; any residue means the clear list was pruned or cleanup
introduced new values. The flag's default is 20, a tolerance for partial runs — do
not rely on it here.

Full detail, including the disguised-constant rule, the media and sheet-deletion
policies, the `_PreparationAudit` schema, and the workbook integrity gate:
[references/phase2_remediation.md](references/phase2_remediation.md).

## Phase 2B — Post-clean leak and integrity scan

```bash
python skills/clean-a-template/scripts/post_clean_leak_scan.py model_cleaned.xlsx \
    --decisions-json decisions.json \
    --table-regions table_regions.json \
    --preserved-defaults preserved_defaults.json \
    --out leak_scan.json
```

Always pass `--table-regions` so residue inside a region the force-clear should
have emptied is caught — this is what catches text leakage like a property name
that the numeric heuristics miss. Add `--cross-check` for a second opinion via
the xlsx skill's `workbook_search.py`.

The scan covers visible and hidden sheets; **sheet tab names**; defined names;
formula text and formula-embedded hardcodes; comments, notes, and document
properties; headers and footers; text boxes and drawing alt text; chart and pivot
references and caches; validation lists; conditional formatting formulas; media
relationships; and external links.

It also runs two checks that exist to catch this pipeline failing:

- **Structural surfaces** are matched against the approved deal strings *and*
  their distinctive tokens. A deal string of `Modera Walsh` does not contain
  `Walsh Ranch`, so whole-string matching misses the checklist row that names the
  prior deal's submarket; token matching on structural surfaces catches it.
  Generic CRE vocabulary is excluded, so a deal named "Midtown Apartments" does
  not make the word "apartments" a finding.
- **Toggle-gated regions**, both ways: `value_in_toggle_gated_region` when a
  gated cell still holds a value (the clearing pass believed the toggle instead
  of the rule) and `toggle_control_cleared` when the control itself is gone.

**Residual-value pass.** A blocking-clean leak scan is necessary but not
sufficient: it asks "is anything recognizably deal-shaped still here", not "is
everything that remains defensible". Run the inventory a second time, against the
**cleaned** workbook, with the same inputs:

```bash
python skills/clean-a-template/scripts/comprehensive_input_inventory.py model_cleaned.xlsx \
    --table-regions table_regions.json \
    --preserved-defaults preserved_defaults.json \
    --out residual_inventory.json \
    --emit-decisions residual_draft.json
```

Any cell that lands in `clear_cells` or `cleared_by_default_needs_decision` on
this second pass is a **residual unaccounted value** — including a bare zero
sitting under a deal label, which in an underwriting model is a cleared-to-zero
input, not a structural blank. Either clear it or move it into
`preserved_defaults.json` with evidence and re-run Phase 2. Array-formula spill
cells are already excluded (the inventory classifies them `do_not_write`), and
label-less spacer zeros are not the target.

### Exit gate

The workbook may be delivered as `ready` only when all of the following hold:

| Check | Requirement |
|---|---|
| Leak scan | `blocking_count == 0` |
| Coverage gate | zero uncleared inventory cells |
| Residual-value pass | no unaccounted remaining value |
| Triage | `cleared_by_default_needs_decision` fully resolved; no cell left in `manual_review` |
| Toggle-gated regions | every gated cell blank; every toggle control still present |
| Structural surfaces | no deal string or distinctive token left in a sheet name, banner title, label, or checklist row; every plan blocker resolved |
| Formula-baked deal amounts | zero unresolved — each either extracted to an input cell by the user or explicitly approved as a template constant |
| Integrity gate | Excel-Table ref reset, package surgery, and normalization recalc all ran (no `skipped_no_skill_root`) |
| Excel repair | workbook opens without repair of defined names, drawings, relationships, or workbook XML |
| Quiet economic check | identified output cells no longer show meaningful prior-deal results |

If material leakage remains, return to remediation. Do not deliver as `ready`.

# Final delivery format

```
Files:
1. {name}_cleaned.xlsx          (the cleaned template)

Cleared: <n>   Preserved: <n>   Needs review: <n>

Status: [ready / ready_with_limitations / needs_review / not_compatible]
Blocking reason: [one sentence only; omit if ready]
```

| Status | Meaning |
|---|---|
| `ready` | Every exit-gate row above passed. |
| `ready_with_limitations` | Cleaned and scans passed, but the integrity gate degraded (`skipped_no_skill_root`, or `--skip-package-surgery` / `--skip-normalization` with documented justification), or a named surface could not be cleaned. State the limitation. |
| `needs_review` | Unresolved triage entries, coverage residue, unaccounted residual value, blocking leak findings, or Excel-repair risk. |
| `not_compatible` | Cannot be safely cleaned — macros, or structure the workflow does not support. |

No narrative after the readiness line. Do not repeat phase summaries after
presenting the file. Never put a prior-deal value in the report.

# Guardrails

- Do not perform acquisitions analysis, valuation, or any economic opinion in
  this workflow.
- Do not populate or refill the template — including on scratch copies.
- Do not infer what a cell *means*. Mapping is out of scope; a cell whose role is
  unresolvable is cleared, not interpreted.
- Do not upgrade low confidence to high confidence.
- Do not preserve prior-deal values as preserved defaults.
- Do not preserve any cell inside a detected table region as a default.
- **Do not accept a toggle's current position as evidence about the region it
  gates**, and do not accept `parallel_siblings` as evidence inside a gated
  region — a gated block satisfies that shape by construction.
- **Do not clear a toggle or selector control.** It is the template's mode
  switch; clearing it delivers a template the user cannot drive.
- **Do not rewrite a formula to remove a baked-in deal amount.** Extracting the
  constant changes the model's logic, which is the user's decision. Surface it
  and hold at `needs_review`.
- **Do not blank a structural surface to remove a deal name.** A blank sheet
  title, label, or checklist row is a different defect. Redact to a generic
  equivalent through the planned surgery, or ask.
- **Do not rename a sheet without rewriting its references in the same pass.**
  openpyxl leaves every `'Old Name'!A1` pointing at a sheet that no longer
  exists, which is #REF! on open — an Excel-repair failure, not a cleaning win.
- **Do not resolve a `manual_review` or `cleared_by_default_needs_decision` cell
  by declaring it a default.** Routing a leftover value into
  `preserved_defaults.json` to silence the residual-value pass is laundering, not
  classification — clear it, or resolve it as a genuine, evidenced policy value.
- **Do not declare a default without evidence it is reusable policy.** Every
  `preserved_defaults.json` entry carries `approved_default: true`, OR both
  `rationale` and `semantic_role`, OR `parallel_siblings` / `sibling_cells`. An
  entry with none of these is not a default; it is an uncleared deal fact.
- **Do not clear an array-formula (CSE/spill) output cell.** These are
  `derived_formula`. openpyxl reports a spilled cell's *cached scalar result*, so
  an array output looks like an ordinary number — but clearing is futile as well
  as wrong: the post-clean normalization recalc re-spills the formula and writes
  the prior-deal value straight back. `comprehensive_input_inventory.py` reads
  `ws.array_formulae` and classifies every spill-range cell `do_not_write`; never
  hand-author a clear decision against one.
- **`manual_review` is not a resting state.** Every such cell is resolved before
  the Phase 2B exit gate — cleared, or evidenced as a preserved default. A
  formula-anchor constant whose clearing would orphan a fill cascade is the one
  legitimate reason to hold a cell in `manual_review` through cleanup, and it
  still has to be resolved before delivery.
- Do not use template fallback for existing-property or development program facts.
- Do not preserve unit mix row labels — but a label pairing a unit type with a
  measure (`1 BR Occupancy`) is a template header, and deleting it is its own
  defect.
- Do not delete sheets before dependency tracing.
- Do not preserve broken formulas merely because they are formulas.
- Do not target a formula cell for clearing, and treat a derived roll-up as
  `derived_formula` — its upstream input sheet is the real input surface.
- Do not retype, port, or rewrite a bundled script; if one is missing, stop with
  `needs_review`.
- Do not deliver `ready_with_limitations` when the normalization recalc could not
  execute at all and nothing else is known about package validity — that is
  `needs_review`.
- Do not expose raw prior-deal values in chat, the cleanliness report, or the
  audit sheet.

# Reference files

Read on demand for the task at hand. Each is one level deep from this file.

- [references/phase1_analysis.md](references/phase1_analysis.md): the full Phase 1
  contract — required analysis outputs, runtime-source-class rules by deal type,
  tall/wide table-region detection, dependency and broken-formula analysis, media
  classification, the judgment log, and the ask-user decision package.
- [references/phase2_remediation.md](references/phase2_remediation.md): cleanup
  policy, deal-fact clearing rules, table and unit-mix cleanup, disguised
  constants, defined names and media, sheet deletion, the `_PreparationAudit`
  schema, the pre-flight gate and triage sequence, the Phase 2B leak scan and
  residual-value pass, and the workbook integrity gate.
- [references/diagnostic_catalog.md](references/diagnostic_catalog.md): the
  diagnostic taxonomy (critical / warning / info) and the script-vs-LLM detection
  preference table.
- [references/scripts.md](references/scripts.md): one-row-per-script index —
  phase, purpose, key flags, inputs and outputs.
