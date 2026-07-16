# Phase 3 - Manifest and Verification

Phase 3 creates the manifest and verifies that the cleaned workbook can be used safely by downstream population. It does not refill the template.

## Manifest file format - strict requirement

The manifest file (`{name}_manifest.md`) MUST be a markdown file containing **exactly one fenced YAML block** (```` ```yaml ... ``` ````) whose contents match the schema in `manifest_template.md`. The YAML block must include at least one of `cells`, `tables`, or `outputs`.

The following are NOT valid manifests and will be rejected by `manifest_lint.py` with a `manifest_not_machine_readable` error:

- Prose-style markdown with header tables and an embedded JSON sniff-output fenced block (the JSON block does not satisfy the YAML contract).
- A YAML-fenced block that contains only header/preparation_metadata sections with no `cells`/`tables`/`outputs`.
- Multiple competing YAML blocks (the lint will pick the largest, but if smaller examples shadow the real manifest the user has to fix it).
- A markdown report styled as a user guide, regardless of how thorough or well-written it is. The manifest is the machine-readable contract; user-facing documentation belongs in chat, not in the manifest file.

If the manifest is intended for human review, place prose explanations OUTSIDE the fenced YAML block, in the surrounding markdown. The lint extracts only the YAML.

A minimal valid shape:

~~~markdown
# My Template Manifest

```yaml
template_id: my_template_v1
manifest_version: 3
status: pending
allowed_write_surfaces:
  formulas_editable: false
  cells:
    - cell: "Sheet1!A1"
cells:
  capital.entry_price:
    semantic_role: acquisition_price
    writes:
      - cell: "Sheet1!A1"
outputs:
  year1_noi:
    cell: "Sheet1!B1"
```
~~~

## Manifest role

The manifest is the contract between RealAI and this workbook. The SKILL file controls readiness status and formula-reevaluation execution. It must describe:

- scalar cell writes;
- table writes;
- runtime source of truth for every input surface;
- datamart requirements;
- manual/user-required inputs;
- AI-estimate allowances and provenance requirements;
- reusable defaults;
- protected formulas and defaults;
- output reads;
- transforms;
- supported analysis modes;
- verification status.

The payload schema can flex to the manifest. Do not force weak mappings into a rigid schema.

## Top-level schema

```yaml
template_id: example_v1
template_file: example_cleaned.xlsx
manifest_version: 3
status: ready | ready_with_limitations | unverified_draft | blocked_recalc_execution_failure | needs_review | not_compatible
supported_modes: [acquisition]
limitations: []

preparation_metadata: {}
conventions: {}

runtime_source_plan: {}
datamart_requirements: {}
manual_required_inputs: {}
allowed_write_surfaces: {}
formula_edit_policy: {}
preserved_logic: {}
sheet_retention: {}
media_policy: {}
cleanup_quality_gates: {}

cells: {}
tables: {}
defaults: {}
outputs: {}
transforms: {}
extras: {}
verification: {}
```

## Required manifest sections

### Runtime source plan

The manifest must state where every mapped input or table should come from at runtime.

Allowed source classes:

- `datamart_required`
- `datamart_preferred_user_fallback`
- `user_required`
- `template_default`
- `approved_ai_estimate_allowed`
- `derived_formula`
- `do_not_write`
- `manual_review`

Example:

```yaml
runtime_source_plan:
  property.total_units:
    semantic_role: total_units
    prep_action: clear_template_value
    source_policy_by_mode:
      existing_property:
        source_priority: [datamart, user_fallback]
        missing_behavior: block_population
      development:
        source_priority: [user_input]
        missing_behavior: block_population
      conversion:
        source_priority: [user_input, datamart]
        missing_behavior: block_population
    template_default_allowed: false
    ai_estimate_allowed: false
    provenance_required: true
    writes:
      - cell: "Operating Assumptions!C26"

  unit_mix:
    semantic_role: unit_mix_table
    prep_action: clear_rows_and_labels_preserve_schema
    source_policy_by_mode:
      existing_property:
        source_priority: [datamart.rent_roll, datamart.unit_mix, user_fallback]
        missing_behavior: block_population
      development:
        source_priority: [user_input]
        missing_behavior: block_population
      conversion:
        source_priority: [user_input, datamart]
        missing_behavior: block_population
    template_default_allowed: false
    ai_estimate_allowed: false
    provenance_required: true
    table: unit_mix

  assumptions.market_vacancy:
    semantic_role: vacancy_loss_rate
    prep_action: preserve_template_default
    source_policy_by_mode:
      all:
        source_priority: [template_default, user_override, approved_ai_estimate]
        missing_behavior: preserve_template_default
    template_default_allowed: true
    ai_estimate_allowed: true
    override_requires_provenance: true
    writes:
      - cell: "Assumptions!E18"
```

### Datamart requirements

The manifest must prescribe datamart sourcing by deal mode.

```yaml
datamart_requirements:
  existing_property:
    required_or_user_fallback:
      - property.name
      - property.address
      - property.total_units
      - property.rentable_sf
      - property.parking_spaces
      - rent_roll
      - unit_mix
      - in_place_rent
      - occupancy
      - trailing_financials
    optional:
      - acreage
      - taxes
      - insurance
      - year_built
      - renovation_history
  development:
    required:
      - current_rate_curve
    user_required_not_datamart_default:
      - unit_mix
      - square_footage_program
      - parking_program
      - development_schedule
      - hard_cost_budget
      - soft_cost_budget
      - land_cost
      - financing_terms
    optional:
      - market_rent_comps
      - sale_comps
      - tax_assessment_inputs
```

Do not allow template fallback for units, square footage, unit labels, rent roll, in-place rent, parking, purchase price, costs, budgets, or capital-stack amounts.

### Manual required inputs

```yaml
manual_required_inputs:
  development:
    - unit_mix
    - square_footage_program
    - parking_program
    - development_schedule
    - hard_cost_budget
    - soft_cost_budget
    - land_cost
    - financing_terms
  conversion:
    - existing_use
    - proposed_use
    - conversion_scope
    - unit_mix
    - redevelopment_budget
```

### Allowed write surfaces

The manifest must distinguish write-allowed from write-expected.

```yaml
allowed_write_surfaces:
  cells:
    - path: property.total_units
      cell: "Operating Assumptions!C26"
      write_class: required_runtime_input
      default_owner: none
      allowed_sources: [datamart, user_fallback]
      missing_behavior: block
      formula_cell: false
      provenance_required: true

    - path: assumptions.market_vacancy
      cell: "Assumptions!E18"
      write_class: override_only
      default_owner: template
      allowed_sources: [user_override, approved_ai_estimate]
      missing_behavior: preserve_existing
      formula_cell: false
      provenance_required: true

  tables:
    - path: tables.unit_mix
      table: unit_mix
      write_class: required_runtime_table
      default_owner: none
      allowed_sources: [datamart, user_fallback, user_input]
      missing_behavior: block
      preserve_schema: true
      prior_rows_removed: true
      prior_row_labels_removed: true

  formulas_editable: false
  formula_override_cells: []
```

Write classes:

| Write class | Meaning |
|---|---|
| `required_runtime_input` | Must be populated for the applicable mode |
| `required_runtime_table` | Table rows must be populated for the applicable mode |
| `optional_runtime_input` | May be populated if provided |
| `override_only` | Existing template default remains unless explicit sourced override is provided |
| `do_not_write` | Downstream must not write |
| `formula_repair_only` | Formula may only be changed by approved repair workflow |

### Formula edit policy

Formulas are preserve-by-default only when valid.

```yaml
formula_edit_policy:
  allow_repair: true
  allowed_repair_types:
    - broken_reference
    - missing_named_range
    - external_link_removal
    - table_range_repair
    - high_confidence_context_repair
  require_audit_log: true
  allow_structural_rewrites: false
  broken_formula_policy:
    repair_if_high_confidence: true
    remove_if_unfixable: true
    trace_dependents_before_ready: true
    block_ready_if_supported_output_depends_on_unfixable_formula: true
```

Allowed repairs must be minimal, localized, non-structural, and recorded in the audit log.

Do not:

- rewrite working formulas;
- simplify or optimize formulas;
- change financial logic structure;
- preserve unfixable `#REF!` or `#NAME?` formulas as protected logic.

### Preserved logic

```yaml
preserved_logic:
  formula_fingerprint:
    formula_cell_count: 0
    formula_hash: null
    by_sheet: {}
  protected_formulas:
    - cell: "Returns!E35"
      semantic_role: levered_irr
      protection: no_downstream_write
  protected_defaults:
    - path: assumptions.market_vacancy
      cell: "Assumptions!E18"
      default_behavior: preserve_existing_unless_explicit_override
      override_requires_provenance: true
```

`protected_defaults` may include reusable assumptions only. It must not include deal facts such as units, square footage, unit labels, rents, parking, costs, or loan amounts.

### Sheet retention

```yaml
sheet_retention:
  retained_visible_sheets: []
  retained_hidden_support_sheets:
    - sheet: "Support"
      reason: feeds_visible_outputs
      dependency_trace: ["Support", "Returns"]
      cleanup_policy: clear_deal_values_preserve_logic
  deleted_sheets: []
  deletion_policy: full_transitive_dependency_trace_required
  uncertain_sheets: []
```

### Media policy

```yaml
media_policy:
  preserve_only_template_owner_logos: true
  template_owner: null
  preserved_media: []
  removed_media:
    photos: []
    non_owner_logos: []
    unknown: []
  drawing_relationships_validated: true
```

### Cleanup quality gates

```yaml
cleanup_quality_gates:
  raw_prior_values_stored: false
  unit_mix_row_labels_removed: true
  runtime_deal_facts_cleared: true
  non_owner_media_removed: true
  photos_removed: true
  defined_names_sanitized: true
  workbook_opens_without_repair: true
  post_clean_leak_scan_passed: true
  package_integrity_passed: true
```

## Scalar cells

Each scalar cell mapping must include source policy and write behavior.

```yaml
cells:
  capital.entry_price:
    semantic_role: acquisition_price
    required: true
    runtime_source_class: datamart_preferred_user_fallback
    default_behavior: no_default
    template_default_allowed: false
    confidence: high
    writes:
      - cell: "Pro Forma!E8"
        transforms: [dollars_to_model_currency]
    write_policy:
      write_class: required_runtime_input
      allowed_sources: [datamart, user_fallback]
      missing_behavior: block
      provenance_required: true
    rationale: "Adjacent label indicates offer/purchase price; prior value cleared."
```

For reusable defaults:

```yaml
cells:
  assumptions.rent_growth:
    semantic_role: market_rent_growth
    required: false
    runtime_source_class: template_default
    default_behavior: use_template_default_if_missing
    template_default_allowed: true
    override_requires_provenance: true
    confidence: high
    writes:
      - cell: "Assumptions!E14"
    write_policy:
      write_class: override_only
      allowed_sources: [user_override, approved_ai_estimate]
      missing_behavior: preserve_existing
      provenance_required: true
    rationale: "Reusable model default; preserved in cleaned template."
```

Do not include prior-deal values as defaults.

## Tables

Use tables for rent roll, T12, unit mix, capex schedules, development budgets, parking schedules, and similar row-based inputs.

```yaml
tables:
  unit_mix:
    payload_path: tables.unit_mix
    sheet: "Unit Mix"
    header_row: 4
    first_data_row: 5
    clear_policy: clear_existing_rows_and_labels_preserve_schema
    prior_rows_removed: true
    prior_row_labels_removed: true
    required: true
    required_runtime_input: true
    runtime_source_class: datamart_preferred_user_fallback
    source_policy_by_mode:
      existing_property:
        source_priority: [datamart.rent_roll, datamart.unit_mix, user_fallback]
        missing_behavior: block_population
      development:
        source_priority: [user_input]
        missing_behavior: block_population
    confidence: medium
    columns:
      unit_type: {column: B, required: true, source: datamart_or_user}
      unit_count: {column: C, required: true, source: datamart_or_user}
      avg_sqft: {column: D, required: true, source: datamart_or_user}
      current_rent: {column: E, required: false, source: datamart_or_user}
      market_rent: {column: F, required: false, source: datamart_or_user}
```

A table whose prior rows or row labels remain in the workbook cannot be marked `ready` unless those rows are true structural examples explicitly approved by the user.

## Write targets must be writable input cells (never formulas)

Every cell in `allowed_write_surfaces.cells`, and every `(column × data row)` implied by a
`tables.<t>` column mapping, must point at a **blank, non-formula** cell in the cleaned
workbook. `apply_payload.py` refuses to overwrite a formula at runtime (exit code 4), so
mapping an input onto a formula cell produces a manifest that lints clean but fails on first use.

Before mapping a scalar cell or a table column, confirm the target appears in
`cell_candidates.json`. `candidate_mapping.py` emits only non-formula, non-blank cells as
candidates — so a cell or column that is **not** in `cell_candidates.json` is almost certainly a formula or a label and must not be mapped as a writable input. Never infer a writable column from a header label alone.

`manifest_lint.py --cleaned-workbook` enforces this with the `write_target_is_formula` check.
Always run lint **with** the cleaned workbook before emitting; a formula write target is a hard
error, not a warning.

## Input tables vs. derived roll-ups

`candidate_mapping.py` detects table-shaped regions structurally; it does **not** tell you
whether a region is where the user types data (an *input table*) or a display that computes from
another sheet (a *derived roll-up*). You must distinguish them:

- If a table's value columns are formulas — especially `COUNTIF` / `AVERAGEIF` / `SUMIF` /
  lookups that reference **another sheet** — the region is a derived roll-up. Map it
  `do_not_write` and follow the references to the upstream sheet.
- The upstream sheet those formulas read from is the real input surface. Map **that** sheet as
  the writable table, with its own columns and write range.

Do NOT map a roll-up's formula columns as `datamart_or_user` inputs, and do NOT relegate the
true input sheet to `excluded_table_regions`.

Illustration: if a unit-mix summary table's count and average-rent columns are
`=COUNTIF('<rent roll sheet>'!…)` / `=AVERAGEIF('<rent roll sheet>'!…)`, that summary is a
derived roll-up — mark it `do_not_write` and map the rent-roll sheet it reads from as the
writable input table instead.

## Comp requirements

When Phase 1 detects a wide-region table whose row labels match a rent-comp or sales-comp signature, the manifest must include a `comp_requirements` section. The runner (the pro forma skill) reads this section at population time and invokes the named sandbox skill — `sandbox_skills("rental-comps")` or `sandbox_skills("sales-comps")` — to source comps for the subject property, then writes the result into the rectangle the manifest specifies.

This is what makes comp handling upstream-driven: the template-prep skill records, once, that a given template contains a rent-comp table at `Rent Comps!D6:K14` and that it should be populated by the `rental-comps` skill. Every downstream run of that template uses the same instruction. No comp-specific logic lives in the pro forma skill itself; it just reads `comp_requirements` and delegates.

```yaml
comp_requirements:
  rent_comps:
    runtime_skill: rental-comps
    semantic_role: rent_comp_table
    sheet: "Rent Comps"
    label_col: B
    first_data_col: D
    last_data_col: K
    first_row: 6
    last_row: 14
    row_labels:
      - "Property"
      - "Address"
      - "City, State"
      - "Year Built"
      - "Units"
      - "Avg Rent"
      - "Occupancy"
    max_comps: 8
    required_runtime_input: false
    missing_behavior: leave_empty_and_flag
    mapping_evidence:
      wide_region_id: 3
      section_header_above: "RENT COMPARABLES"
  sales_comps:
    runtime_skill: sales-comps
    semantic_role: sales_comp_table
    sheet: "Sales Comps"
    label_col: B
    first_data_col: D
    last_data_col: K
    first_row: 6
    last_row: 18
    row_labels:
      - "Property"
      - "Sale Date"
      - "Sale Price"
      - "Price/Unit"
      - "Cap Rate"
    max_comps: 8
    required_runtime_input: false
    missing_behavior: leave_empty_and_flag
    mapping_evidence:
      wide_region_id: 5
      section_header_above: "SALES COMPARABLES"
```

Field notes:

- `runtime_skill` is the exact string the runner passes to `sandbox_skills()`. Currently `rental-comps` and `sales-comps`; new comp-style skills can be added without changing the manifest schema.
- `row_labels` is the ordered list of labels read from `label_col` between `first_row` and `last_row`. The runner uses these to align the comp skill's output rows with the template's expected layout, so the comp skill doesn't need to know the template's specific structure.
- `required_runtime_input` defaults to `false` for comps — they enrich the underwriting narrative but don't gate the economic calculation. A template that uses comp values inside downstream formulas (e.g., a market-rent benchmarking formula that pulls from a comp average cell) may set this to `true`; in that case `missing_behavior` should be `block_population`.
- `mapping_evidence.wide_region_id` is the index into `table_regions.json`'s combined `regions` list. It lets reviewers verify the manifest's rectangle matches the Phase 1 detection.

If Phase 1 detected no comp tables, omit `comp_requirements` entirely, or include an empty `comp_requirements: {}` for clarity. Both forms pass `manifest_lint`.

A wide region detected by `candidate_mapping.py` that is NOT mapped to either `tables` or `comp_requirements` is a Phase 3 defect: `manifest_lint` flags it under W.14 (`detected table region not mapped`). Either map it or document why it should not be a runtime input.

## Outputs

```yaml
outputs:
  year1_noi:
    cell: "Returns!E20"
    semantic_role: net_operating_income_year_1
    confidence: high
    transforms: [model_currency_to_dollars]
  levered_irr:
    cell: "Returns!E35"
    semantic_role: levered_irr
    confidence: high
```

At least one economic output such as Year 1 NOI, entry cap, exit value, IRR, or equity multiple must be mapped for production readiness. Year 1 NOI is strongly preferred.

## Transforms

Transforms may apply to writes or reads.

```yaml
transforms:
  dollars_to_model_currency:
    operation: divide
    factor: 1000
    applies_to: write
    rationale: "Payload uses dollars; model uses $000s."

  model_currency_to_dollars:
    operation: multiply
    factor: 1000
    applies_to: read
    rationale: "Model outputs are in $000s."

  expense_sign_negative:
    operation: ensure_sign
    sign: negative
    applies_to: write
```

## Extras

Extras are workbook concepts that are useful but not confidently mapped.

```yaml
extras:
  acquisition_fee:
    cell: "Assumptions!E22"
    label: Acquisition Fee
    value_policy: preserved_template_default
    confidence: medium
    recommendation: "Allow explicit payload override in future if useful."
```

Do not store raw prior-deal values in extras.

## Verification

Run verification in three distinct steps.

### L0 - static manifest lint

Use `manifest_lint.py`. It checks that:

- every `cells` and `tables` entry has runtime source policy;
- every write surface is listed in `allowed_write_surfaces`;
- every allowed write has a write class;
- no deal fact uses `use_template_default_if_missing`;
- unit mix/program tables have `prior_row_labels_removed: true`;
- protected defaults do not include obvious deal facts;
- status is consistent with cleanup gates.

### L1 - write-only preflight

Use `verify_write_preflight.py`. This confirms that the manifest can write the sample payload into scalar cells and tables. It does not validate formulas.

L1 is never production-ready.

Before L3, confirm every cleared table with downstream formula dependents is either mapped and populated by the sniff payload or explicitly marked as a required runtime table.

### L2 - post-clean leak and integrity scan

Use `post_clean_leak_scan.py`. This confirms:

- required cleared cells/ranges are blank;
- runtime deal facts are not retained as template defaults;
- broken formulas and invalid names are not unresolved;
- non-owner media and photos are removed;
- defined names are valid or intentionally preserved;
- no explicit sensitive/deal strings remain.

A failed L2 blocks `ready` and `ready_with_limitations`.

### L3 - formula-reevaluation-backed economic sniff

Use `sniff_test.py`. It must:

1. write the sample payload to a temporary sniff-test workbook;
2. call the Excel skill command from the Excel skill root: `cd <excel_skill_root> && python scripts/recalc.py <absolute_sniff_workbook> [timeout_seconds]`;
3. read mapped outputs with read transforms;
4. compare error counts before and after;
5. reconcile Year 1 NOI via dual-provenance claims check (see below);
6. sanity-check entry cap and major return outputs when mapped;
7. return the recalculated sniff workbook when `--out` is supplied.

The Excel skill provides `scripts/recalc.py`. Do not copy `recalc.py` into `tp_scripts`, do not pass `tp_scripts/recalc.py`, and do not inspect the underlying formula engine directly. Invoke `recalc.py` with cwd set to the Excel skill root and pass the sniff workbook as an absolute path. If `scripts/recalc.py` cannot execute or is killed, return `blocked_recalc_execution_failure`.

**Economic reconciliation via `workbook_claims_check.py`.** The Year 1 NOI reconciliation in `sniff_test.py` delegates to the xlsx skill's `workbook_claims_check.py`, following the SKILL's anti-smoothing dual-provenance protocol:

1. The payload's economic identity (`gpr + vacancy + other_income - sum(opex_line_items)`) is computed and recorded as a derived claim's `expr`.
2. The workbook's displayed Year 1 NOI cell is read AFTER recalc and recorded both as a `fact` and as the claim's `expected` value.
3. `workbook_claims_check.py` evaluates the expression and compares to `expected` with absolute tolerance (`max(abs(workbook_noi) * 0.03, $1,000)`).
4. If the claims helpers are unreachable (skill root unset, helpers missing), `sniff_test.py` falls back to inline reconciliation using the same expression and tolerance, so the verdict is consistent regardless of helper availability.

This replaces the prior parallel-NOI calculation that frequently failed for unit-mix-driven payloads where the workbook computes NOI from `unit_count * rent * (1 - vacancy) - opex_growth_stepped`. The dual-provenance approach reconciles the payload's identity against what the workbook actually computes, so the check is meaningful regardless of how the workbook derives revenue.

**Recalc execution detection.** `sniff_test.py` distinguishes recalc execution failures (where `recalc.py` returned `{"error": "..."}` and Python exited 0) from economic-check failures. A failed recalc surfaces as `blocked_recalc_execution_failure` per the SKILL contract, NOT as `unverified_draft`. The detection requires `status in {"success", "errors_found"}` AND no top-level `error` key in the JSON output.

**Excel skill root resolution.** Set `REALAI_XLSX_SKILL_ROOT` (or `EXCEL_SKILL_ROOT` / `XLSX_SKILL_ROOT`) to the absolute path of the xlsx skill directory. `sniff_test.py`, `prepare_clean_template_v2.py`'s normalization step, and `post_clean_leak_scan.py`'s optional cross-check all use this. The filesystem-walk fallback is a courtesy but is fragile under non-standard working directories — explicit env var is preferred.

## Verification statuses

When L3 passes, update the manifest before delivery. The final manifest should not remain `unverified_draft` after a passing recalc-backed sniff test.

```yaml
verification:
  level: L3_economic_sniff_passed
  production_ready: true
  status: ready
  manifest_lint_passed: true
  post_clean_leak_scan_passed: true
  write_preflight_passed: true
  formula_recalc_command: "cd <excel_skill_root> && python scripts/recalc.py <absolute_workbook> [timeout_seconds]"
  formula_recalc_passed: true
  economic_sniff_passed: true
  new_error_count: 0
  notes: []
```

If recalculation/economic sniff does not pass after `recalc.py` is attempted:

```yaml
verification:
  level: L1_write_only_preflight
  production_ready: false
  status: unverified_draft
  manifest_lint_passed: true
  post_clean_leak_scan_passed: true
  write_preflight_passed: true
  formula_recalc_command: "cd <excel_skill_root> && python scripts/recalc.py <absolute_workbook> [timeout_seconds]"
  formula_recalc_passed: false
  economic_sniff_passed: false
  reason: "The Excel-skill recalc.py command was attempted but formula or economic checks did not pass."
```

## Final readiness

- `ready`: L3 passed, L2 passed, manifest lint passed, workbook opens without repair, and no unresolved critical issues remain.
- `ready_with_limitations`: formula reevaluation executed and either L3 passed for listed modes only, or all remaining errors are traced to intentionally cleared required runtime tables that are documented in the manifest.
- `unverified_draft`: L1 passed but formula/economic verification remains incomplete after the Excel-skill recalc command executed. Do not use this when recalc failed to execute; use `blocked_recalc_execution_failure`.
- `blocked_recalc_execution_failure`: `scripts/recalc.py` could not be executed or was killed.
- `needs_review`: important mapping, dependency, formula, logo, or source-of-truth decisions remain unresolved.
- `not_compatible`: cannot safely prepare under this workflow.

### Blocked recalculation execution

If `scripts/recalc.py` cannot be executed or is killed, do not treat the model as economically failed. Mark the run as `blocked_recalc_execution_failure`, surface the cleaned workbook separately from the unfinished manifest, and do not run direct formula-engine diagnostics.

```yaml
verification:
  level: L1_write_only_preflight
  production_ready: false
  write_preflight_passed: true
  formula_recalc_passed: false
  economic_sniff_passed: false
  status: blocked_recalc_execution_failure
  execution_blocker: recalc_py_not_executed
```

### Runtime-input errors after successful recalc

A cleaned reusable template may show formula errors immediately after prior-deal tables are cleared. This is acceptable only when the errors are traced to missing runtime inputs, not broken formulas. Mark the template `ready_with_limitations` only if:

- `recalc.py` executed successfully from the Excel skill root;
- manifest lint passed;
- post-clean leak/integrity scan passed;
- remaining errors are tied to blank required runtime tables such as T12, trailing financials, rent roll, unit mix, program data, or capex schedules;
- those tables are marked in `tables` with `required_runtime_input: true`;
- affected outputs identify the upstream table requirement;
- no structural defects remain in mapped formulas or outputs;
- no prior-deal data remains in workbook or manifest defaults.
