# Diagnostic Catalog

## Contents

- Severity rules
- **Critical** — C.1 formula/value errors · C.2 circular references · C.3 external
  references · C.4 broken named ranges · C.5 macros/VBA · C.6 normalization recalc
  unavailable · C.8 runtime deal facts retained · **C.9 residual unaccounted value**
  · C.10 unit mix / program row labels retained · C.11 media leakage or drawing
  repair risk · C.12 unsafe sheet deletion · C.13 post-clean leak scan failed ·
  C.15 workbook package repair risk · **C.16 array-formula output cell proposed for
  clearing** · **C.17 unresolved manual-review / cleared-by-default cells** ·
  **C.18 toggle-gated region preserved or toggle control cleared** ·
  **C.19 structural surface carries a prior-deal name** ·
  **C.20 formula-baked deal amount** ·
  **W.3 unit-mix metric header**
- **Warning** — W.1 inconsistent formula patterns · W.2 hardcoded constants inside
  formulas · W.3 convention mismatch · W.4 multiple time axes · W.5 formula override
  cells · W.6 dead inputs · W.7 formatting/content mismatch · W.8
  TODO/FIXME/placeholders · W.9 table schema uncertainty · W.11 preserved default
  ambiguity · W.12 formula cache leakage
- **Info** — I.1 document metadata · I.2 reviewer comments · I.3 hidden sheets ·
  I.4 print areas, filters, custom views · I.5 reusable defaults · I.6 table
  surfaces · I.7 template owner logo candidates
- Detection preference (script role vs LLM role)
- Retired codes (C.7, C.9b, C.14, W.10, W.13, W.14)

Use this catalog during Phase 1. Diagnostics inform readiness and cleanup recommendations. They are not a license to auto-fix formulas or mutate model logic.

Codes are kept at their original numbers for traceability. Six codes retired with the mapping/verification phase and are listed under **Retired codes** at the end — the gaps in the sequence are deliberate, not omissions. C.18–C.20 were added in v4.8 from a real staging run on a user's own model.

## Severity rules

- Critical issues block `ready` and `ready_with_limitations` until resolved, isolated, or explicitly recorded as unsupported by the cleaned template.
- Warning issues require judgment and may block readiness when material.
- Info items are recorded but usually do not block preparation.

## Critical

### C.1 Formula/value errors

Detect cached or formula errors such as `#REF!`, `#NAME?`, `#VALUE!`, `#DIV/0!`, and `#N/A`.

Action:

- Critical if the error affects retained outputs, retained support logic, or core calculation sections **in the uploaded workbook**.
- Repair only when intent is high-confidence from labels, neighboring formulas, row/column patterns, named ranges, tables, and dependents.
- If intent cannot be determined, remove the broken formula and trace dependents.
- Do not mark `ready` if a retained output depends on an unfixable formula.
- Note the asymmetry: an error that appears *after* cleanup because its input chain was emptied is the expected post-clean state, not a defect. Judge C.1 against the pre-clean workbook.

### C.2 Circular references / iterative calculation

Detect circular logic from the dependency graph and workbook calculation settings.

Action:

- If intentional and iterative calculation is enabled, record it in the audit and preserve the setting.
- If not enabled or unexplained, block readiness.

### C.3 External references and connections

Detect formulas referencing external workbooks and package parts such as external links, Power Query, or connection XML.

Action:

- Block unless the user approves static conversion and cached values are available, or unless the external link is proven irrelevant to retained outputs.
- Remove external links only when retained formulas and outputs do not depend on them.

### C.4 Broken or invalid named ranges

Detect defined names that cannot resolve to existing sheets/ranges, point to `#REF!`, reference external workbooks, or use invalid names.

Action:

- Block if used by retained formulas or retained outputs.
- Repair only when target is high-confidence.
- Otherwise remove and audit.
- A workbook that triggers Excel repair due to named ranges is not `ready`.

### C.5 Macros/VBA

Detect `.xlsm` or `xl/vbaProject.bin`.

Action:

- Refuse. Ask for a macro-free `.xlsx` copy. Never execute VBA.
- When a calling agent has already run a macro gate, the input to this skill is the converted macro-free `.xlsx` and C.5 does not fire on it.

### C.6 Normalization recalc unavailable or not executed

Detect when the workbook integrity gate's no-op recalc normalization (via the xlsx skill's `recalc.py`) was not attempted, was skipped, or failed.

Action:

- Status mapping:
  - normalization ran and reported success → gate satisfied.
  - `skipped_no_skill_root`, or `--skip-normalization` used → the integrity gate degrades from preventive to detective. Cap readiness at `ready_with_limitations` and state the reason; set `REALAI_XLSX_SKILL_ROOT=skills/xlsx` and re-run to clear it.
  - the recalc helper failed to execute → `needs_review` with limitation `recalc_execution_failed`.
- Do not inspect the underlying formula engine directly. Do not copy, recreate, or edit the xlsx skill's `recalc.py`.
- A `#NAME?` on a dynamic-array function is an engine coverage gap, not a preparation defect (see `phase2_remediation.md`).

### C.8 Runtime deal facts retained

Detect retained deal-specific facts in the cleaned workbook, including units, unit mix, unit type labels, rentable square footage, in-place rents, rent roll values, parking counts, purchase price, development budget, hard costs, soft costs, loan amounts, and capital-stack values.

Action:

- Block `ready` and return to remediation unless the user explicitly approved the value as a true reusable template default.
- Existing-property facts should be datamart first with user fallback — never a template default.
- Development/conversion program facts should be user-required unless a reliable datamart source exists.
- A cell inside a detected runtime-input table region cannot be a reusable default. The Phase 2 force-clear must run with `--table-regions table_regions.json`.

### C.9 Residual unaccounted value

Detect non-formula numeric values remaining in the cleaned workbook that are NOT accounted for as evidenced preserved defaults. This is the inverse of the coverage gate: where `coverage_verify.py` confirms the cleanup cleared what it intended to clear, this check confirms everything that REMAINS is something the preparation can defend.

Action:

- Enforced by the **residual-value pass**: re-run `comprehensive_input_inventory.py` against the cleaned workbook with the same `--table-regions` and `--preserved-defaults` inputs. Anything landing in `clear_cells` or `cleared_by_default_needs_decision` on that second pass is residual.
- Block `ready` and `ready_with_limitations` if any residual value remains unresolved.
- Either clear the cell in Phase 2, or move it into `preserved_defaults.json` with real evidence and re-run.
- Zeros are not silently skipped. A remaining `0` under a label is a cleared-to-zero input, not a structural blank — in an underwriting model a bare zero under a deal label is exactly the leak this check exists for. Label-less spacer zeros are ignored.
- A preserved-defaults entry only accounts for a value when it carries evidence of being reusable policy (`approved_default: true`, OR `rationale` + `semantic_role`, OR `parallel_siblings`/`sibling_cells`). Do NOT resolve a leftover deal fact by declaring it a default — that is laundering, not classification.
- Array-formula (CSE/spill) output cells are excluded — they are derived logic, not retained values.
- ⚠️ The automatic `default_without_evidence` warning was emitted by `manifest_lint.py` and left with the manifest. The evidence half of this check is currently enforced by review. Absence of a warning is not a pass.

### C.10 Unit mix or program row labels retained

Detect row labels such as Studio, 1BR, 2BR, TH, Retail, Garage, named unit plans, parking types, budget line-item labels, comp-table property names or addresses, or other prior deal rows in runtime tables.

Action:

- Block readiness unless labels are true structural headers approved by the user.
- Clear row labels and values while preserving headers, formulas, validation, formatting, and table shape.
- For wide-region tables (rent comps, sales comps): the data rectangle is force-cleared, but the row-label column is preserved as structural scaffolding. Property names, addresses, and city/state strings inside the data rectangle are runtime input and must be cleared.

### C.11 Media leakage or drawing repair risk

Detect photos, renderings, maps, aerials, partner logos, lender logos, broker logos, developer logos, consultant logos, unknown logos, orphaned media files, or malformed drawing relationships.

Action:

- Preserve only template-owner logos.
- Remove all other media unless the user explicitly approves.
- Rebuild or validate drawing relationships.
- A workbook that triggers Excel drawing repair is not `ready`.

### C.12 Unsafe sheet deletion or unresolved support sheets

Detect hidden/very-hidden sheets proposed for deletion without full transitive dependency trace.

Action:

- Block deletion until no retained visible output, input surface, hidden support sheet, defined name, chart, table, validation rule, conditional format, pivot source, or supported mode depends on the sheet.
- If uncertain, retain as a support sheet and clear deal-specific values.

### C.13 Post-clean leak scan failed

Detect a failed `post_clean_leak_scan.py` result (`blocking_count > 0`).

Action:

- Block `ready` and `ready_with_limitations` until resolved.

### C.15 Workbook package repair risk

Detect workbooks that trigger or are likely to trigger Excel repair due to invalid defined names, drawing parts, relationships, workbook XML, or orphaned media.

Action:

- Not deliverable as `ready` until repaired and revalidated.
- Sanitize defined names and drawing/media relationships deterministically via the integrity gate's package surgery.
- If unresolved, mark `needs_review`.

### C.16 Array-formula output cell proposed for clearing

Detect a cell that is part of an array-formula (CSE / spill) output range but has been proposed for clearing (appears in `clear_cells`, or its value class routed it to the scalar clear path). openpyxl reports a spilled cell's *cached scalar result*, so an array output is easily mistaken for an ordinary hardcoded number.

Action:

- Treat every cell in an `ws.array_formulae` range as `derived_formula` / `do_not_write`. It must NOT be cleared.
- Clearing is not merely wrong but futile: the post-clean normalization recalc re-spills the array formula and writes the value back into the "cleared" cell, silently restoring the prior-deal figure. This is the defect that shipped stale per-unit cost values in an early template.
- `comprehensive_input_inventory.py` detects spill-range membership and classifies these cells `do_not_write` automatically (`array_formula_output_cells_protected` in the scan summary). If hand-authoring decisions, never target an array-range cell for clearing.
- This is a Phase 1/Phase 2 classification defect; resolve it before remediation rather than discovering it as residual leakage.

### C.17 Unresolved manual-review / cleared-by-default cells at Phase 2 entry

Detect cells classified `manual_review` — or surfaced in the inventory draft's `cleared_by_default_needs_decision` list — that have not been explicitly resolved (cleared, or allowlisted as an evidenced preserved default) before `prepare_clean_template_v2.py` runs.

Action:

- Block. `manual_review` is not a resting state and `cleared_by_default_needs_decision` is not advisory. In prior versions these buckets were produced but never consumed, so the cells survived into the cleaned workbook carrying prior-deal values — the primary leak mode.
- Each such cell must be routed to exactly one of: `clear_cells` (the safe default), or `preserved_defaults.json` as an **evidenced** default.
- A formula-anchor constant (clearing would orphan a fill cascade) legitimately stays in `manual_review` through cleanup, but it must be resolved before the Phase 2B exit gate and will be caught by the residual-value pass (C.9) if left as an unaccounted value.
- Do NOT empty these buckets by deleting entries or by declaring leftovers as unevidenced defaults.

### C.18 Toggle-gated region preserved, or toggle control cleared

Two failures of the same rule, in opposite directions.

**Preserved gated region.** A cell behind a binary mode toggle (`Use Staged Inputs = No`, `Co-Invest / Promote Structure = No`) still holds a value after cleanup, because the toggle's position was read as evidence that the block is inert. Leak-scan code: `value_in_toggle_gated_region`.

**Cleared toggle control.** The toggle cell itself was cleared, leaving a template whose mode switch is gone and whose gating formulas read a blank. Leak-scan code: `toggle_control_cleared`.

Action:

- Block, both directions. The values in a gated block are one cell-flip from going live, and they are the previous deal's.
- Gated cells are force-cleared by `comprehensive_input_inventory.py` (`force_cleared_reason: in_toggle_gated_region`) and are deliberately not surfaced in `cleared_by_default_needs_decision`.
- `parallel_siblings` is **refused** as evidence inside a gated region: a gated block is uniformly filled across periods or tiers by construction, so the shape distinguishes nothing there. Only `"approved_region_exception": true`, after explicit user approval in the Phase 1 form, holds a cell.
- The toggle control is `template_default` and is preserved in the position the template's author left it. Do not normalize it, reset it, or clear it.

### C.19 Structural surface carries a prior-deal name

A sheet tab name, banner/title cell, label cell, or checklist row still names the prior deal. Clearing does not reach these — they hold no value, and blanking them would delete the template's own scaffolding. Leak-scan codes: `deal_string_in_sheet_name`, `deal_token_in_sheet_name`, `deal_token_in_structural_text`, and `deal_string_retained` carrying a `structural_surface` field.

Action:

- Block. This is the most visible leak in a delivered file and the one a user notices first.
- Resolve by redaction to a generic equivalent through `structural_text_surgery.py --plan` → `decisions.json` (`structural_redactions`, `sheet_renames`), each applied with a `_PreparationAudit` row. Never by blanking.
- Match on the approved deal strings **and their distinctive tokens**: `Modera Walsh` does not contain `Walsh Ranch`, so whole-string matching misses a checklist row naming the prior deal's submarket. Generic CRE vocabulary is excluded from tokenization.
- A sheet rename happens only when it is dependency-safe — formula, defined-name, validation, and conditional-format references are rewritten in the same pass. A chart or pivot cache holding its own copy of the reference makes it unsafe; that becomes an ask_user blocker, not a rename.

### C.20 Formula-baked deal amount

A formula carrying cell references **and** a large hardcoded dollar figure in its body: `=C6/91327500`, `=MAX(0,B32-57915000)`. Live model logic computing off the prior deal's number. Leak-scan code: `formula_baked_deal_amount`.

Action:

- Block, and do **not** repair. Extracting the constant into an input cell changes the model's logic; approving it as a template constant is a claim about the user's intent. Both are the user's decision.
- Surface each as an ask_user finding with the recommendation: extract to an input cell and reference it, or approve as a genuine template constant.
- **Readiness cannot be `ready` while an unresolved one remains** — the template still computes off the previous deal, so it is not reusable and no population agent can be built on it.
- Distinct from W.2's arithmetic-only disguised constant (`=168227*2`), which carries no references, is not model logic, and is force-cleared by the existing rule. The scan separates them: `formula_baked_deal_amount` (blocking) vs `formula_embedded_hardcoded_numeric` (review).
- **Also distinct from a normalization scale (v4.9).** Two or more **distinct** literals inside a clamp function (`MIN` / `MAX` / `MEDIAN` / `PERCENTILE`) are range bounds, not a deal amount: `=MIN(100,MAX(0,(C7-30000)/(150000-30000)*100))` indexes household income onto 0–100. The scan classifies those `formula_scale_constant`, severity **info** — reported so a genuinely odd one stays visible, never blocking. The rule keys off the **literal count, not the function name**, so `=MAX(0,B32-57915000)` is still C.20: one distinct large literal against a reference is a subtraction from a deal figure, whatever wraps it.
- Why it matters that this is not blocking: on our own house template the old rule fired **10 times, all false positives**, so the skill could never certify the RealAI template — and a staging run handed 10 unresolvable blockers responded by **rewriting two of the formulas** to extract the constants, which is precisely the model-logic change the "never repair" rule above exists to prevent. An unresolvable blocker invites an invented remedy.

## Warning

### W.1 Inconsistent formula patterns

A row/column of formulas has outliers.

Action: flag. Do not auto-fix working formulas; overrides may be intentional.

### W.2 Hardcoded constants inside formulas

Formulas include numeric literals that may encode business assumptions or prior-deal facts.

Action:

- Flag.
- If the hardcode is a prior-deal fact inside a formula, classify as formula-embedded leakage.
- Repair only when high-confidence and non-structural.
- An arithmetic-only formula inside an input range or detected region is a disguised constant and is force-cleared, not flagged (see `phase2_remediation.md`).
- A formula that carries cell references AND a large hardcoded amount is not this code — it is **C.20**, and it blocks. W.2 covers the review-severity remainder.
- A clamp carrying two or more distinct literals is neither: it is a normalization scale, reported `formula_scale_constant` at info severity. See C.20.

### W.3 Unit-mix metric header (v4.9)

A label that names a unit type **and** a measure — `Studio — In-Place Rent`, `1 BR Occupancy`, `2 BR SF`. Leak-scan code: `unit_mix_metric_header`, severity **info**.

This is the template's own scaffolding, not a unit-mix row label: it is identical in every copy of the workbook, carries no deal data, and blanking it deletes the row's meaning. Distinguished from the real thing by the presence of a measure word — a genuine unit-mix row label names the unit type and nothing else (`Studio`, `2 BR / 2 BA`, `A1`), and that remains **blocking** as `unit_mix_or_program_row_label_retained`.

Action:

- Report, do not clear, do not block. Preserve the header.
- On our own house template this rule turned five fixed Rent Comps headers from blockers into info findings; the non-negotiable *"unit mix row labels are deal-specific, delete both labels and values"* still applies in full to actual row labels.

Related: the bare plan-code pattern (`possible_plan_code_label`) no longer fires on `T12` / `T-12` / `T-3` / `T-6`, which are universal CRE vocabulary the pattern read as plan "T" number 12.

### W.3 Convention mismatch

Template conventions are unusual or internally inconsistent: currency scale, expense sign, percentage format, or time axis.

Action: record the convention explicitly in the audit so it is not lost. If a section's convention cannot be determined, mark `needs_review` for that section rather than guessing what is a deal fact.

### W.4 Multiple time axes

The workbook has historical monthly data, annual projections, monthly debt schedules, etc.

Action: record all candidates and select the primary underwriting projection axis with evidence.

### W.5 Formula override cells

A hardcoded cell appears inside a formula-driven projection range.

Action: flag. Do not clear or rewrite unless the user approves — unless it is a disguised constant inside a declared input range, which clears.

### W.6 Dead inputs

Input-looking cells have no direct or range-based dependents.

Action: clear if deal-specific; preserve only if reusable default or structural control.

### W.7 Formatting/content mismatch

Input-styled cells contain formulas, or calculation-styled cells contain hardcodes.

Action: flag for review.

### W.8 TODO/FIXME/placeholders

Cells or comments indicate unfinished work.

Action: flag in Phase 1.

### W.9 Table schema uncertainty

A detected table region has unclear header row, first data row, or columns.

Action: ask for review before clearing. The detection itself is mechanical; only schema interpretation requires LLM/user judgment.

### W.11 Preserved default ambiguity

A scalar value could be either reusable model policy or a stale deal-specific assumption.

Action: classify conservatively as `user_required` unless evidence supports preservation. Under the clear-by-default rule the ambiguous cell clears; preserving it requires an evidenced `preserved_defaults.json` entry.

### W.12 Formula cache leakage

Formula cells may retain cached prior-deal outputs until recalculation.

Action: the integrity gate's normalization recalc refreshes these. When normalization is skipped, record cached-value staleness as a limitation.

## Info

### I.1 Document metadata

Author, company, last modified by, or similar metadata exists.

Action: strip silently in Phase 2.

### I.2 Reviewer comments

Comments include reviewer identity or stale review notes.

Action: strip identity; remove comments containing deal-specific strings; preserve substantive model documentation when feasible.

### I.3 Hidden sheets

Hidden or very-hidden sheets exist.

Action: trace dependencies. Retain support sheets that feed retained logic and clear deal-specific values.

### I.4 Print areas, filters, and custom views

Prior layout artifacts exist.

Action: record; clean only if safe and approved.

### I.5 Reusable defaults

Default rent growth, vacancy, reserves, fees, exit cap, or similar assumptions are present.

Action: preserve only when classified as `template_default` AND the cell is NOT inside a detected table region AND the `preserved_defaults.json` entry carries evidence. Protect from silent mutation.

### I.6 Table surfaces

Rent roll, T12, unit mix, capex, debt, waterfall, and development-budget table regions detected.

Action: treat as table candidates, not scalar clutter. Clear prior rows and row labels unless structural.

### I.7 Template owner logo candidates

Images may include reusable template-owner logos.

Action: preserve only confirmed template-owner logos. Remove other logos and photos.

## Detection preference

Use scripts for mechanical facts and the LLM for business interpretation.

| Area | Script role | LLM role |
|---|---|---|
| Workbook size and compatibility | detect | summarize |
| Candidate inputs | `candidate_mapping.py` emits per-cell label inventory | classify runtime source from labels + section headers |
| Table regions | `candidate_mapping.py` detects mechanically (label col + value col + sum confirmation) | confirm category (unit mix vs budget vs rent roll); approve any region as defaults if appropriate |
| Dependency graph | detect direct and range-based dependencies | interpret business relevance |
| Sheet deletion | compute transitive dependencies | recommend delete/retain/review |
| Unit scale | detect markers and anchors | choose final scale if ambiguous |
| Time axes | list candidates | choose primary projection axis |
| Architecture | extract signals | classify the model type that governs what is a deal fact |
| Errors | count and locate | explain likely business impact |
| Named ranges | detect invalid/broken/external names | decide repair/remove/preserve |
| Media | inventory images and drawings | classify template-owner logos vs leakage |
| Post-clean leak scan | execute deterministically | triage `review`-tier findings; decide remediation if failed |
| Coverage gate | `coverage_verify.py` compares intent to result | explain any uncleared residue |
| Residual value | second inventory pass on the cleaned workbook | route each residual cell to clear or evidenced default |
| Array-formula outputs | `comprehensive_input_inventory.py` reads `ws.array_formulae` and protects spill cells | confirm none were force-mapped for clearing |
| Manual-review / cleared-by-default resolution | inventory emits the buckets | route each cell to clear or evidenced default |
| Default legitimacy | *(no script — see C.9)* | supply sign-off, rationale + role, or sibling evidence — or clear the cell |
| Package integrity | integrity gate substeps execute deterministically | explain failures and set the limitation |

## Retired codes

| Code | Was | Why retired |
|---|---|---|
| C.7 | Output coverage insufficient | Measured whether a manifest exposed enough outputs to validate a write mapping. No manifest, no write mapping. |
| C.9b | Allowed-write-surfaces / cells asymmetry | Purely a manifest-schema defect. The equivalent check now lives in the consuming flow's own mapping audit. |
| C.14 | Script extraction failure | Existed because scripts were markdown-embedded and had to be extracted with a `# END` sentinel check. Scripts are now real files in `scripts/`; the replacement rule is in SKILL.md § Execution Mandate — run the bundled file, never retype it, and stop with `needs_review` if one is missing. |
| W.10 | Low-confidence mapping | Mapping is out of scope. An unresolvable cell clears; it is not mapped with low confidence. |
| W.13 | Source policy missing or weak | A manifest-completeness check. |
| W.14 | Detected table region not mapped | A manifest-completeness check. Cleaning is unaffected: an unmapped detected region is still force-cleared, which is the conservative action. |
