# Phase 2 — Remediation, and Phase 2B — Post-clean scan

## Contents

**Phase 2 — cleanup**

- Required inputs
- Cleanup policy — silent, approved, preserve-by-default, do-not-preserve
- Runtime source cleanup rules (+ array-formula / spill protection)
- Deal-fact clearing rules
- Data table cleanup
- Unit mix cleanup
- Formula preservation and broken-formula policy
- Formula-embedded hardcodes → **arithmetic-only formulas (disguised constants)**
- Defined names and external links
- Media cleanup
- Sheet deletion policy
- Audit log — the `_PreparationAudit` column schema
- **Pre-flight gate — `decisions.json` must contain `clear_cells`** (the five-step
  required sequence; skipping it cleans nothing, silently)
- Resolve `cleared_by_default_needs_decision` before merging
- Preserved defaults must be evidenced — do not launder leftovers

**Phase 2B — proof**

- Leak scan
- Coverage gate
- Residual-value pass
- Quiet economic check
- Workbook integrity gate (Excel-Table ref reset, OOXML package surgery, recalc
  normalization) + the dynamic-array engine limitation
- Output

Phase 2 creates the cleaned template. It applies the approved source-of-truth classification while preserving reusable workbook logic. Phase 2B proves the result. Use the SKILL file as the execution authority.

## Required inputs

Phase 2 must use the Phase 1 outputs:

- `runtime_source_classification`;
- `table_cleanup_plan`;
- `sheet_dependency_trace`;
- `media_plan`;
- `broken_formula_plan`;
- approved ask_user decisions;
- deterministic script evidence.

Do not clean from intuition alone. The source-of-truth plan drives remediation.

## Cleanup policy

### Silent cleanup

Allowed without further user approval:

- strip author/company/lastModifiedBy metadata;
- strip deal-specific document properties;
- remove reviewer identity from comments while preserving substantive template documentation when feasible;
- remove stale custom views or print artifacts only when they do not affect workbook logic;
- remove orphaned media relationships after approved media deletion.

### Approved cleanup

Apply after Phase 1 approval or when already covered by standing policy:

- clear scalar cells classified as prior-deal runtime inputs;
- clear prior-deal table rows;
- clear prior-deal row labels in unit mix, rent roll, parking, square-footage, development program, and similar tables;
- clear prior capital-stack, cost, schedule, rent, operating, tax, insurance, and budget data;
- remove photos and non-template-owner logos;
- remove or repair broken defined names;
- remove external links or convert to approved static template defaults only when safe;
- delete sheets proven unused by full dependency trace;
- repair high-confidence broken formulas;
- remove unrepairable broken formulas and trace impact.

### Preserve by default

Preserve only when not deal-specific:

- valid formulas;
- formula structure and dependent calculation logic;
- reusable template defaults;
- toggles and controls;
- generic table headers;
- generic labels needed to understand the template;
- formatting, validation, and number formats;
- template-owner logos.

Do not preserve:

- unit mix row labels;
- deal-specific table row labels;
- deal facts;
- prior budget/cost/capital-stack values;
- photos or non-template-owner logos;
- invalid named ranges;
- broken formulas with unknowable intent.

## Runtime source cleanup rules

| Runtime source class | Workbook action |
|---|---|
| `datamart_required` | Clear value/rows/labels |
| `datamart_preferred_user_fallback` | Clear value/rows/labels |
| `user_required` | Clear value/rows/labels |
| `approved_ai_estimate_allowed` | Preserve only if also a reusable template default; otherwise clear |
| `template_default` | Preserve; protect from silent mutation |
| `derived_formula` | Preserve if valid; repair/remove if broken per formula policy |
| `do_not_write` | Preserve unless leakage |
| `manual_review` | Do not modify until resolved — and resolve it before the Phase 2B exit gate |

**Array-formula (CSE / spill) output cells are `derived_formula`, never inputs.** openpyxl reports a spilled cell's *cached scalar result*, so an array output looks like an ordinary number and the naive scalar path would clear it — but the post-clean normalization recalc re-spills the value straight back, silently restoring a stale deal figure. `comprehensive_input_inventory.py` reads `ws.array_formulae` and classifies every spill-range cell as `do_not_write`; these cells must never appear in `clear_cells`. If you are hand-authoring a clear decision, do not target a cell that is part of an array-formula range.

## Deal-fact clearing rules

The following must be cleared from the workbook and cannot survive as template defaults:

- property name and address;
- unit count;
- rentable square footage;
- acreage;
- parking spaces;
- unit mix row labels and values;
- rent roll rows;
- in-place rent;
- prior-deal market rent by unit type;
- development program rows;
- hard costs, soft costs, fees, contingencies, and financing cost line items;
- purchase price, land cost, closing costs, and sale price;
- prior loan amounts, mezzanine/preferred equity amounts, and equity contributions;
- prior taxes, insurance, payroll, operating expense values, and trailing financials;
- partner, lender, broker, consultant, developer, or prior-owner names.

Existing-property runtime source: datamart first, user fallback, no template fallback.

Development/conversion runtime source: user input unless a reliable datamart source is identified. No template fallback.

## Data table cleanup

For rent rolls, T12s, unit mix, capex schedules, hard-cost schedules, soft-cost schedules, square-footage schedules, parking schedules, development programs, debt schedules, and similar row-based inputs:

1. Preserve generic headers.
2. Preserve formulas.
3. Preserve formatting and data validation.
4. Clear prior-deal hardcoded row values.
5. Clear prior-deal row labels.
6. Preserve table shape only when useful for future population.
7. Record the table's sheet, header row, first data row, and column footprint in `_PreparationAudit`.

If the first data row, structural header row, or table boundaries are uncertain, stop for review rather than guessing.

## Unit mix cleanup

Unit mix is always runtime deal data unless explicitly proven to be a generic placeholder.

Required action:

- delete row labels such as Studio, 1BR, 2BR, 3BR, TH, Retail, Garage, etc. when they are prior-deal row entries;
- delete unit counts;
- delete unit square-footage values;
- delete rent values;
- preserve only generic column headers, formulas, formatting, validation, and table footprint.

## Formula preservation and broken-formula policy

Valid formulas are preserved by default and fingerprinted.

Broken formulas are not preserved by default. For formulas containing `#REF!`, `#NAME?`, broken external links, missing named ranges, invalid structured references, or similar defects:

1. Use context clues to infer intent:
   - labels;
   - surrounding formulas;
   - adjacent time periods;
   - row/column patterns;
   - named ranges;
   - comparable sheets;
   - dependent formulas.
2. Repair only when the inferred formula is high confidence and minimal.
3. Record every repair in `_PreparationAudit`.
4. If intent cannot be determined, remove the formula and trace all dependents.
5. If a retained output depends on the removed formula, status cannot be `ready` until the dependency is fixed or the affected output is recorded as unsupported by the cleaned template.

Do not structurally redesign economics to repair a formula.

## Formula-embedded hardcodes

Detect formulas with embedded numeric constants that appear deal-specific. Examples include formulas that hardcode units, rentable square footage, costs, rents, purchase price, or debt proceeds.

Default action:

- preserve if clearly a generic formula constant or mathematical constant;
- repair/rewrite only if the constant is clearly a broken reference replacement and a blank input cell exists to reference instead;
- otherwise flag for manual review;
- do not silently preserve deal-specific formula hardcodes as protected logic.

### Arithmetic-only formulas (disguised constants)

A formula whose body contains **no cell or range references** — only numeric literals and the
operators `+ - * / ( )` and whitespace — is not model logic. It is a prior-deal constant typed as arithmetic. Examples: `=168227*2`, `=9245040-46225`, `=59250+98750+167875+98750+71000`.

Because the value begins with `=`, openpyxl and every formula-aware guard treat it as a
protected formula. The consequence is twofold: (a) it survives the value-clear pass and leaks
prior-deal figures, and (b) it blocks any future write under the no-overwrite-formula rule, so the cell can never be repopulated.

Rule: inside any declared input range or detected table region, detect cells whose value matches `^=[\d\s.,+\-*/()]+$` (no letters, no `!`, no defined-name token) and **clear them to blank**.
Log as `clear_disguised_constant` in `_PreparationAudit` with `prior_value_redacted: true`. Do not preserve them as `derived_formula`.

Outside declared input ranges, flag such cells for manual review rather than auto-clearing — a standalone constant like `=365/12` may be intentional model scaffolding.

## Defined names and external links

Sanitize defined names before final save:

- remove names resolving to `#REF!` when unused or unrepairable;
- repair missing named ranges only when the intended range is high confidence;
- remove external workbook references unless explicitly approved as supported runtime links;
- preserve print areas/titles and valid names used by retained formulas;
- remove deal-specific names that are unused and do not support retained logic.

`repair_broken_named_ranges.py` does the deterministic pass; run it `--dry-run` first.

```bash
python skills/clean-a-template/scripts/repair_broken_named_ranges.py model_cleaned.xlsx --dry-run
python skills/clean-a-template/scripts/repair_broken_named_ranges.py model_cleaned.xlsx --out model_cleaned_repaired.xlsx
```

The workbook cannot be marked `ready` if Excel repairs named ranges on open.

## Media cleanup

Extract and classify workbook media.

Allowed to remain:

- template-owner logos only.

Remove:

- property photos;
- renderings;
- aerials;
- maps;
- broker photos;
- partner logos;
- lender logos;
- developer logos;
- consultant logos;
- unknown images unless the user explicitly approves preservation.

After deleting media, rebuild or validate drawing relationships. The workbook cannot be marked `ready` if Excel repairs drawings on open.

## Sheet deletion policy

Do not delete worksheets until after a full transitive dependency trace.

A worksheet may be deleted only if all are true:

1. no retained visible output depends on it;
2. no retained visible input surface depends on it;
3. no retained hidden support sheet depends on it;
4. no retained defined name depends on it;
5. no retained chart, table, validation rule, conditional format, or pivot source depends on it;
6. no supported analysis mode depends on it.

Hidden sheets may feed other hidden sheets, which may feed user-facing outputs. Trace those chains.

If a sheet supports retained model logic, keep it and clear deal-specific values within it according to the source-of-truth classification.

If dependency status is uncertain, keep the sheet and document it as `support_sheet_retained_for_formula_dependencies`.

## Audit log

The cleaned workbook includes a hidden `_PreparationAudit` sheet. It must not contain raw prior-deal values.

Columns:

| Column | Purpose |
|---|---|
| timestamp_utc | When action occurred |
| location | Sheet/cell/range/property/media/name |
| action | clear_value, clear_table_values, clear_row_labels, strip_metadata, remove_media, remove_name, repair_formula, remove_formula, delete_sheet, etc. |
| value_class_before | text, large_number, rate_or_ratio, formula, media, defined_name, sheet, etc. |
| prior_value_redacted | true/false |
| before_hash | SHA-256 hash of prior value or object descriptor |
| after_state | blank, preserved, removed, repaired, unchanged, etc. |
| category | Diagnostic/category code |
| runtime_source_class | datamart_preferred_user_fallback, user_required, template_default, etc. |
| rationale | Short reason |
| approved_by_user | true/false |
| confidence | high/medium/low |

## Pre-flight gate — decisions.json must contain clear_cells

Before invoking `prepare_clean_template_v2.py`, confirm that `decisions.json` contains a `clear_cells` array populated from `comprehensive_input_inventory.py --emit-decisions`. This is not optional.

The script does:
```python
clear_cells(wb, audit_ws, decisions.get("clear_cells", []))
```

A missing `clear_cells` key silently passes an empty list — no cells are cleared, the workbook retains all prior-deal values, and the leak scan will fail with hundreds of findings.

Required sequence:

1. Run `python skills/clean-a-template/scripts/comprehensive_input_inventory.py model.xlsx --table-regions table_regions.json --out input_inventory.json --emit-decisions decisions_clear_cells_draft.json`
2. Review `decisions_clear_cells_draft.json`. Move any cells that are true reusable defaults into `preserved_defaults.json`.
3. Re-run with `--preserved-defaults preserved_defaults.json` until the draft contains only deal facts.
4. Merge `decisions_clear_cells_draft.json["clear_cells"]` into `decisions.json` as the `"clear_cells"` key.
5. Only then call `python skills/clean-a-template/scripts/prepare_clean_template_v2.py model.xlsx decisions.json --out model_cleaned.xlsx`.

Always pass `--table-regions` to the inventory. Without it the force-clear mask is silently skipped and table cells fall back to allowlist-trusting behavior — and the toggle-gated mask in the same file goes with it, so gated blocks revert to allowlist-trusting too. Defaults trapped inside a detected (non-sum-confirmed) region, or inside a toggle-gated region, need `"approved_region_exception": true` on their `preserved_defaults` entry — set ONLY after explicit user approval in the Phase 1 form.

### Structural surgery — redaction, not clearing (v4.8)

Between the triage (step 2 above) and the merge, plan the structural surgery.
Clearing empties value cells; a prior deal's name also sits in surfaces that hold
no value and so pass through untouched:

| Surface | Example | Why clearing does not reach it |
|---|---|---|
| Sheet tab name | `Modera Walsh DD Checklist` | not a cell; the openpyxl cell walk never sees it |
| Banner / title cell | `MODERA WALSH - DEBT STRUCTURE` | a title, not an input; blanking it deletes the title |
| Label cell | a prior lender's name under a `Lender` label | text scaffolding by position |
| Checklist row | `☐ Market study on Walsh Ranch absorption` | prose; and the deal name is mid-sentence |

```bash
python skills/clean-a-template/scripts/structural_text_surgery.py model.xlsx \
    --decisions-json decisions.json \
    --leak-scan leak_scan.json \
    --out structural_surgery_plan.json
```

Review the plan, then merge `structural_redactions` and the `dependency_safe`
entries of `sheet_renames` into `decisions.json` under those same keys.
`prepare_clean_template_v2.py` applies them and writes a `_PreparationAudit` row
for each (`redact_structural_text`, `rename_sheet`), so the substitution is
auditable and reversible by inspection.

**Sheet renames are dependency-safe or they do not happen.** openpyxl does not
rewrite formula references when a worksheet is renamed — every `'Old Name'!A1`
silently points at a sheet that no longer exists, which Excel reports as #REF! on
open. `apply_sheet_renames` rewrites cell formulas, defined names, data-validation
formulas, and conditional-format formulas in the same pass as the rename, and
records the count in the audit row (`renamed_refs_rewritten:3f/1n`). Charts and
pivot caches carry their own copies of sheet-qualified refs and are **not**
rewritten, so the planner marks a rename unsafe when either is present and it
becomes an `ask_user` blocker instead — the recommendation is for the user to
rename the tab in Excel, which updates those references, and re-run.

**Formula-baked deal amounts are blockers, not edits.** A formula carrying cell
references *and* a large hardcoded dollar figure — `=C6/91327500`, the prior
deal's total cost welded into an LTC calculation — is live model logic computing
off the previous deal's number. Two reasons it is not repaired here: extracting
the constant into an input cell changes the model's logic, and approving it as a
constant is a claim about the user's intent. Both are the user's call. Surface
each with the recommendation the planner supplies and hold. **Readiness cannot be
`ready` while an unresolved one remains.**

This is a different defect from the arithmetic-only disguised constant
(`=168227*2`), which has no references, is not model logic, and the existing
disguised-constant rule clears. The leak scan separates them:
`formula_baked_deal_amount` (blocking) vs `formula_embedded_hardcoded_numeric`
(review).

### Resolve `cleared_by_default_needs_decision` before merging

The draft emitted by `comprehensive_input_inventory.py` contains a
`cleared_by_default_needs_decision` list alongside `clear_cells`. These are
un-allowlisted scalars, zeros, and toggles that the inventory **cleared by
default** because, in an underwriting model, an un-allowlisted scalar is runtime
input — not a reusable assumption.

This list exists because of a real failure mode: in prior versions these cells
returned `manual_review`, and **nothing in the sequence consumed
`manual_review`**, so every one of them silently survived into the "cleaned"
workbook carrying its prior-deal value (zeros under `Free Months` /
`Contingency` / `Rate Floor`, phasing constants, per-unit cost figures, etc.).

You MUST triage `cleared_by_default_needs_decision` before step 4:

- If a cell is a **genuine reusable template default** (a policy rate that should
  ship with the template, e.g. a standard 3%-of-EGI management fee), move it to
  `preserved_defaults.json` with a rationale and re-run. It will then be
  preserved, and the entry must carry evidence (see below).
- Otherwise, leave it in `clear_cells`. The safe default is clear.

Do NOT empty this list by deleting entries; either preserve-via-allowlist or
clear. An unresolved entry that is neither is exactly the leak this step exists
to prevent.

**`manual_review` is not a resting state.** Any cell still classified
`manual_review` at the end of Phase 2 (e.g. a formula-anchor constant that
cannot be cleared without orphaning a fill cascade) must be explicitly resolved
before the Phase 2B exit gate — cleared, or declared an evidenced preserved
default. It must not be left to survive silently. The residual-value pass below
will report any such remaining numeric value, including a zero under a label, so
an unresolved `manual_review` cell cannot reach `ready`.

### Preserved defaults must be evidenced — do not launder leftovers

**Do not resolve a leftover value by declaring it a default.** Routing an
un-cleared deal fact into `preserved_defaults.json` purely to silence the
residual-value pass is laundering, not classification.

A `preserved_defaults.json` entry is legitimate only when the value is reusable
model policy, and the entry must carry affirmative evidence of that — one of:

- `approved_default: true` — the user explicitly signed off on this cell in the
  Phase 1 form; or
- both `rationale` and `semantic_role` — a stated reason plus what the value *is*
  in the model's economics; or
- `parallel_siblings` / `sibling_cells` — the same policy value appears across
  parallel cells (all unit types, all periods), which is what a policy rate looks
  like and a deal fact does not.

An entry with none of these is not a default; it is an uncleared deal fact.
Clear it.

**`parallel_siblings` is refused inside a toggle-gated region (v4.8).** This is
the one place the rule above inverts, and it is worth stating plainly because the
evidence looks textbook-valid. A block behind a binary mode toggle — a
year-by-year override grid under `Use Staged Inputs = No`, a promote waterfall
under `Co-Invest / Promote Structure = No` — is filled uniformly across periods
or tiers *by construction*. So "the same value appears across all periods" is
satisfied by every gated block, whether it holds a growth policy or the last
deal's assumptions, and it therefore distinguishes nothing there.

That is exactly the path a real staging run took: the toggle read `No`, the rows
beside it documented the block as optional, the values were uniform across ten
years, and the block was preserved as a reusable default. It was the previous
deal's numbers, one cell-flip from going live.

`comprehensive_input_inventory.py` enforces this mechanically — gated cells are
force-cleared with `force_cleared_reason: in_toggle_gated_region` (or
`in_gated_region_overrides_allowlist` when an allowlist entry was overridden),
and they are deliberately **not** surfaced in
`cleared_by_default_needs_decision`, because surfacing them is what invited the
reasoning in the first place. The only escape is `"approved_region_exception":
true` after explicit user approval in the Phase 1 form.

The toggle control itself is classified `preserve_default` and survives in the
position the template's author left it. Do not clear it: `toggle_control_cleared`
is a blocking leak-scan finding, and a template whose mode switch is missing is
not a working template.

> **Known gap.** In the production bundle this evidence rule was machine-enforced
> by `manifest_lint.py`, which emitted a `default_without_evidence` warning. That
> script was manifest-coupled and left the bundle with the manifest. The rule is
> currently enforced by review, not by a script. Do not treat the absence of a
> warning as a pass.

## Phase 2B — Post-clean leak and integrity scan

### Leak scan

After cleanup, run the post-clean leak scan.

```bash
python skills/clean-a-template/scripts/post_clean_leak_scan.py model_cleaned.xlsx \
    --decisions-json decisions.json \
    --table-regions table_regions.json \
    --preserved-defaults preserved_defaults.json \
    --out leak_scan.json
```

Always pass `--table-regions` so the scan can flag any non-blank value remaining inside a region the force-clear should have emptied — this catches text leakage like a property name that the heuristic deal-fact scans miss.

Coverage surfaces (all implemented in the deterministic scan):

- visible sheets and hidden sheets (openpyxl cell walk);
- defined names (broken refs, external refs, deal-string in name);
- formula text including embedded numeric hardcodes (magic-number leakage like `=12000000*0.65` where the constant was a prior loan amount);
- comments and threaded comments (text bodies + author identity + person displayName);
- document properties (creator, lastModifiedBy, title, subject, description, company, manager);
- worksheet headers and footers;
- text boxes and drawing alt text;
- conditional formatting formulas (broken refs + embedded numeric hardcodes);
- data validation list formulas;
- chart titles and embedded chart text;
- pivot cache definitions (cached field data);
- customXml parts;
- external link parts and external relationships in `xl/_rels/workbook.xml.rels`;
- media relationships (orphan and unapproved `xl/media/*`);
- detected table regions (with `--table-regions`);
- **sheet tab names** (v4.8 — they live in `xl/workbook.xml`, so neither the cell walk nor the package-parts scan reached them before);
- **structural surfaces** — banner/title cells, label cells, checklist rows — matched against the approved deal strings AND their distinctive tokens (v4.8);
- **toggle-gated regions and toggle controls** (v4.8, with `--table-regions`).

Specifically flag retained:

- property names and addresses (matched via approved `decisions.deal_strings`);
- units, SF, parking, acreage (matched via suspicious-deal-fact-context heuristic — label keyword + numeric value);
- unit mix row labels (broadened pattern catches Studio/Penthouse/PH/Loft/townhome/retail/garage AND alphanumeric plan codes);
- rents and rent roll rows (deal_string match + suspicious_deal_fact_context);
- in-place rent;
- development budget, hard costs, soft costs;
- loan amounts and capital-stack values (formula-embedded numeric scan catches these even when the source cell was cleared);
- partner/vendor names (deal_string match);
- photos and non-template-owner logos;
- a prior deal's name in a tab title, banner, label, or checklist row (`deal_string_in_sheet_name`, `deal_token_in_sheet_name`, `deal_token_in_structural_text`, and `deal_string_retained` with a `structural_surface` field — resolved by redaction, see C.19);
- a value left in a toggle-gated region, or a toggle control that was cleared (`value_in_toggle_gated_region`, `toggle_control_cleared` — see C.18);
- a prior-deal dollar amount welded into a live formula (`formula_baked_deal_amount` — blocking and never auto-repaired, see C.20).

The scan emits a structured result with `blocking_count` and `informational_count`. Severity tiers: `blocking` findings fail the scan; `review` findings are heuristic hits the LLM verifies against the workbook (`label_context` and `text` fields are included in clear text for exactly that triage); `info` is FYI. Any blocking finding fails the scan; informational findings (e.g. the bare presence of a customXml part, a document property whose value doesn't match a deal string) are reported but do not block readiness on their own. **The cleaned workbook must produce zero blocking findings.**

The optional `--cross-check` flag delegates a second-opinion pass to the xlsx skill's `workbook_search.py` for the deal strings and broken-formula tokens, surfacing any discrepancies between the scan and the helper. Requires `REALAI_XLSX_SKILL_ROOT` to be set; degrades to `skipped_no_skill_root` otherwise.

If material leakage remains, return to remediation. Do not deliver as `ready`.

### Coverage gate

The leak scan asks "is anything recognizably deal-shaped still here". The coverage gate asks the different question "did the cleanup clear what the inventory said it would" — it catches the orchestrator-missed-cells failure mode.

```bash
python skills/clean-a-template/scripts/coverage_verify.py model_cleaned.xlsx \
    --inventory input_inventory.json \
    --out coverage_report.json \
    --max-uncleared 0
```

A non-zero uncleared count means either the clear list was pruned when it should not have been, or cleanup introduced newly populated cells. Both are `needs_review`. Pass `--max-uncleared 0`: a correctly executed sequence leaves zero, and the flag's built-in default of 20 is a tolerance for partial runs that would let real residue pass this gate.

### Residual-value pass

Neither scan above answers the inverse question: **is everything that remains defensible?** Run the inventory a second time, against the cleaned workbook, with the same inputs:

```bash
python skills/clean-a-template/scripts/comprehensive_input_inventory.py model_cleaned.xlsx \
    --table-regions table_regions.json \
    --preserved-defaults preserved_defaults.json \
    --out residual_inventory.json \
    --emit-decisions residual_draft.json
```

Any cell that lands in `clear_cells` or `cleared_by_default_needs_decision` on this second pass is a residual unaccounted value. Because the inventory clears un-allowlisted scalars by default, this surfaces the cleared-to-zero case: a bare `0` under a deal label is a cleared-to-zero input, not a structural blank. Label-less spacer zeros are not the target, and array-formula spill cells are already excluded — the inventory classifies them `do_not_write`.

For each residual cell: clear it, or move it into `preserved_defaults.json` with evidence (see the evidenced-defaults rule above) and re-run Phase 2. Nothing is resolved by leaving it.

### Quiet economic check

After cleanup, check whether identified output cells still show meaningful prior-deal results because drivers were missed. If they do, trace the likely missed inputs and stop for review.

This is a sanity check on incomplete clearing, not an economic verification of the model. A blank-input template showing `#DIV/0!` or `0` on its outputs is the expected post-clean state; a template still showing a plausible prior-deal IRR is not.

## Workbook integrity gate

After remediation and the post-clean scan, the workbook package must be structurally valid. A workbook that would trigger Excel repair for defined names, drawings, relationships, or workbook XML cannot be marked `ready`. Repair by sanitizing package parts, defined names, and drawing/media relationships; if still unresolved, mark `needs_review`.

`prepare_clean_template_v2.py` enforces this gate via three explicit substeps run after the openpyxl save and before result emission:

1. **Excel Table ref reset.** Each `ListObject` (Excel Table) has its `ref` attribute shrunk to the smallest rectangle that contains its header plus any non-empty data row. Without this step, a table whose data rows were cleared retains its prior row count, and downstream structured references (`Tablename[Column]`) average over stale blank rows. The reset is recorded in the audit log as `shrink_table_ref`.

2. **OOXML package surgery.** The cleaned file is round-tripped through the xlsx skill's `office/unpack.py` → surgical edits → `office/pack.py` (which auto-validates with `office/validate.py --auto-repair`). Surgery covers:

   - Deletion of orphan `xl/media/*` parts that no remaining relationship points to (openpyxl saves can leave these behind even after `ws._images` removal).
   - Comment author scrubbing: `xl/comments*.xml`, `xl/threadedComments/*.xml`, and `xl/persons/*.xml` have author identity replaced with "Anonymous".
   - Drop of `customXml/*` parts unless explicitly retained via `decisions.retain_custom_xml` (these frequently carry deal-data caches embedded by Excel add-ins).
   - Optional header/footer strip from worksheet XML (`decisions.strip_headers_footers`).
   - Inline redaction of approved deal strings inside `<t>...</t>` runs in worksheet XML and `xl/sharedStrings.xml`, catching deal-name leakage in header rows that survived cell-level cleanup.
   - Final `office/validate.py --auto-repair` pass on the packed file (defense in depth).

3. **No-op recalc normalization.** A single recalc pass via the xlsx skill's `recalc.py` is run on the cleaned file with no payload writes. LibreOffice's `RecalculateAndSave` macro rewrites the OOXML, normalizing namespace ordering and any minor structural differences openpyxl produces. This means the delivered `{name}_cleaned.xlsx` is byte-identical to what any downstream recalc will produce, eliminating the openpyxl-vs-LibreOffice serialization drift that could cause Excel-repair-on-first-open or subtle differences between the delivered template and a later populated workbook.

All three substeps require the xlsx skill root to be discoverable (set `REALAI_XLSX_SKILL_ROOT=skills/xlsx`). When the env var is unset and the filesystem-walk fallback returns None, each substep emits a `skipped_no_skill_root` status in the result JSON; the cleaned file is still produced, but the integrity gate degrades from preventive to detective and readiness caps at `ready_with_limitations`.

CLI flags `--skip-package-surgery` and `--skip-normalization` exist for emergency degraded modes (e.g. when LibreOffice is provably unavailable in the current environment). Using either flag without documented justification disqualifies the workbook from `ready`.

### Known recalc-engine limitation: dynamic-array functions

LibreOffice may return `#NAME?` for modern Excel dynamic-array functions (`_xlfn._xlws.SORT`, `FILTER`, `XLOOKUP`, `LAMBDA`, …). This applies to any workbook and is an engine coverage gap, NOT a preparation defect. Do not chase it; record it as a `ready_with_limitations` sub-reason if it affects the normalization pass.

## Output

Produce `{name}_cleaned.xlsx`.

The workbook should:

- be safe to share externally;
- preserve reusable model logic;
- open without Excel repair;
- contain no prior-deal data leakage except explicitly approved, evidenced reusable defaults;
- contain no photos or non-template-owner logos;
- contain no invalid defined names or unrepairable broken formulas in retained paths.
