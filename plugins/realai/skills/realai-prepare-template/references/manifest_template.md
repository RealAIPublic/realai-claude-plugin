# RealAI Prepared Template Manifest

```yaml
template_id: "{slug}_v1"
template_file: "{cleaned_filename}"
manifest_version: 4
skill_contract:
  skill_name: template-preparation
  skill_file_controls_execution: true
  durable_outputs_only: true
  no_refill_step: true
  # Recalc rules live in SKILL.md §recalc — do not restate here.

# Status enum (collapsed from prior 8-state version):
#   ready                  — all checks passed
#   ready_with_limitations — recalc passed for listed supported modes only,
#                            or remaining failures are documented missing-runtime-input
#   needs_review           — manifest decisions, leakage, recalc execution, or sniff outcomes
#                            require user attention. Sub-reason in `limitations`.
#   not_compatible         — workbook cannot be safely prepared.
status: "needs_review"
supported_modes: []
limitations: []   # free-form sub-reason strings — see Phase 3 §verification

preparation_metadata:
  generated_by: "template-preparation skill"
  generated_at: "{iso_timestamp}"
  source_file: "{source_filename}"
  raw_prior_values_stored: false
  template_prep_scope: cleaned_template_and_manifest_only_no_refill
  approved_standing_policies:
    unit_mix_row_labels_deleted: true
    existing_property_source_policy: datamart_first_user_fallback_no_template_fallback
    development_source_policy: user_required_for_program_inputs_no_template_fallback
    media_policy: template_owner_logos_only
    sheet_deletion_requires_transitive_dependency_trace: true
    broken_formula_policy: repair_high_confidence_else_remove_and_trace
    table_region_cells_force_cleared: true
  architecture:
    primary: null
    extensions: []
    confidence: null
  model_judgment_log: []

conventions:
  currency_scale: null
  output_currency_scale: null
  percentage_format: null
  expense_sign: null
  primary_projection_axis:
    sheet: null
    granularity: null
    period_count: null
  time_axis_candidates: []
  iterative_calc_required: null

datamart_requirements:
  existing_property:
    required: []
    preferred: []
    missing_required_behavior: "allow_user_fallback_then_block"
    template_fallback_allowed: false
  development:
    required: []
    user_required: []
    template_fallback_allowed: false
  conversion:
    required: []
    user_required: []
    preferred: []
    template_fallback_allowed: false

ai_estimate_policy:
  allowed_for: []
  not_allowed_for: []
  provenance_required: true
  override_audit_required: true

# ── CELLS ────────────────────────────────────────────────────────────────────
# Single section unifying the prior runtime_source_plan + cells + write-policy
# information. Each entry carries source policy, write target, mapping evidence,
# and (for protected defaults) the value that legitimately remains in the
# cleaned workbook.
#
# write_policy.write_class values:
#   - scalar_input        : runtime input; cell is BLANK in cleaned template
#   - protected_default   : reusable default; cell HOLDS value in cleaned template
#   - user_overridable    : reusable default that user may override at runtime
#   - do_not_write        : structural/output cell; runner cannot write
cells:
  # property.total_units:
  #   semantic_role: total_units
  #   required: true
  #   runtime_source_class: datamart_preferred_user_fallback
  #   write_policy:
  #     write_class: scalar_input
  #     provenance_required: true
  #   allowed_sources: [datamart, user_input]
  #   missing_behavior: block_population
  #   writes:
  #     - cell: "Assumptions!C10"
  #   mapping_evidence:
  #     left_labels: ["Total Units"]
  #     section_header_above: "PROJECT OVERVIEW"
  #     in_named_range: null
  #
  # assumptions.market_vacancy:
  #   semantic_role: vacancy_loss_rate
  #   required: false
  #   runtime_source_class: template_default
  #   write_policy:
  #     write_class: user_overridable
  #     override_requires_provenance: true
  #   allowed_sources: [template_default, user_override, approved_ai_estimate]
  #   missing_behavior: use_template_default_if_missing
  #   default_value: 0.05
  #   writes:
  #     - cell: "Assumptions!C25"
  #   mapping_evidence:
  #     left_labels: ["Market Vacancy"]
  #     section_header_above: "OPERATING ASSUMPTIONS"

# ── DEFAULTS (alternate location for protected defaults) ────────────────────
# Either place protected defaults inline as cells with write_class: protected_default,
# or list them here with their preserved value. Both forms are accepted by
# manifest_lint's leakage check. Use this section for defaults that are not
# also user-overridable at runtime.
defaults:
  # financing.senior.sofr_floor:
  #   cell: "Assumptions!F48"
  #   value: 0
  #   semantic_role: interest_rate_floor
  #   rationale: "Zero floor is valid structural default"

# ── TABLES ───────────────────────────────────────────────────────────────────
tables:
  # unit_mix:
  #   payload_path: tables.unit_mix
  #   semantic_role: unit_mix
  #   sheet: "Operating Assumptions"
  #   header_row: 9
  #   first_data_row: 10
  #   last_data_row: 25
  #   clear_policy: clear_rows_and_labels_preserve_schema
  #   prior_rows_removed: true
  #   prior_row_labels_removed: true
  #   required_runtime_input: true
  #   required_for_full_economic_verification: true
  #   source_policy_by_mode:
  #     existing_property:
  #       source_priority: [datamart.rent_roll, datamart.unit_mix, user_fallback]
  #       missing_behavior: block_population
  #     development:
  #       source_priority: [user_input]
  #       missing_behavior: block_population
  #     conversion:
  #       source_priority: [user_input, datamart]
  #       missing_behavior: block_population
  #   template_default_allowed: false
  #   ai_estimate_allowed: false
  #   confidence: high
  #   columns:
  #     unit_type:    {column: A, required: true,  source: datamart_or_user}
  #     unit_count:   {column: B, required: true,  source: datamart_or_user}
  #     avg_sqft:     {column: C, required: true,  source: datamart_or_user}
  #     in_place_rent:{column: D, required: false, source: datamart_or_user}
  #
  # construction_budget:
  #   payload_path: tables.construction_budget
  #   sheet: "Cons. Budget & Sch."
  #   header_row: 8
  #   first_data_row: 9
  #   last_data_row: 71
  #   clear_policy: clear_rows_and_labels_preserve_schema
  #   prior_rows_removed: true
  #   prior_row_labels_removed: false  # column-E line-item labels are structural
  #   required_runtime_input: true     # MUST be true on dev/conversion templates
  #   required_for_full_economic_verification: true
  #   source_policy_by_mode:
  #     development:
  #       source_priority: [user_input]
  #       missing_behavior: block_population
  #   columns:
  #     line_item_label: {column: E, required: true, source: user_input}
  #     total_amount:    {column: D, required: true, source: user_input}

# ── COMP REQUIREMENTS ────────────────────────────────────────────────────────
# Wide-region tables that hold rent or sales comps. The cleaned template's data
# rectangle is empty by force-clear; row labels (Property, Address, etc.) remain
# as structural scaffolding. At population time, the runner reads this section
# and invokes the named sandbox skill to source comps for the subject property.
#
# Each entry names the runtime skill (`rental-comps` or `sales-comps`), the
# rectangle to populate, and the row-label expectations the runner can use to
# align the skill's output rows with the template's row labels.
#
# This section is populated by Phase 3 whenever Phase 1 detected a wide region
# whose row labels match a comp-table signature. If no comp tables are detected,
# the section is omitted (an empty `comp_requirements: {}` is also acceptable).
comp_requirements:
  # rent_comps:
  #   runtime_skill: rental-comps                  # sandbox_skills("rental-comps")
  #   semantic_role: rent_comp_table
  #   sheet: "Rent Comps"
  #   label_col: B
  #   first_data_col: D
  #   last_data_col: K
  #   first_row: 6
  #   last_row: 14
  #   row_labels:                                  # ordered, read from label_col
  #     - "Property"
  #     - "Address"
  #     - "City, State"
  #     - "Year Built"
  #     - "Units"
  #     - "Avg Rent"
  #     - "Occupancy"
  #     - "Distance from Subject"
  #   max_comps: 8                                 # number of data columns
  #   required_runtime_input: false                # falsey: comps enrich but don't gate underwriting
  #   missing_behavior: leave_empty_and_flag       # runner notes absence in source audit
  #   mapping_evidence:
  #     wide_region_id: 3                          # index into table_regions.json
  #     section_header_above: "RENT COMPARABLES"
  #
  # sales_comps:
  #   runtime_skill: sales-comps                   # sandbox_skills("sales-comps")
  #   semantic_role: sales_comp_table
  #   sheet: "Sales Comps"
  #   label_col: B
  #   first_data_col: D
  #   last_data_col: K
  #   first_row: 6
  #   last_row: 18
  #   row_labels:
  #     - "Property"
  #     - "Address"
  #     - "City, State"
  #     - "Sale Date"
  #     - "Sale Price"
  #     - "Price/Unit"
  #     - "Cap Rate"
  #     - "Year Built"
  #     - "Units"
  #   max_comps: 8
  #   required_runtime_input: false
  #   missing_behavior: leave_empty_and_flag
  #   mapping_evidence:
  #     wide_region_id: 5
  #     section_header_above: "SALES COMPARABLES"

# ── OUTPUTS ──────────────────────────────────────────────────────────────────
outputs:
  # year1_noi:
  #   cell: "Returns!E20"
  #   semantic_role: net_operating_income_year_1
  #   currency_scale: "$"
  #   format: dollar_whole

# ── TRANSFORMS ──────────────────────────────────────────────────────────────
transforms:
  # dollars_to_model_currency:
  #   operation: divide
  #   factor: 1000
  #   applies_to: write
  #   rationale: "Payload uses dollars; model uses $000s."

# ── ALLOWED WRITE SURFACES ───────────────────────────────────────────────────
allowed_write_surfaces:
  formulas_editable: false
  cells: []          # populated automatically from cells.<key>.writes[].cell
  tables: []
  formula_override_cells: []

# ── PROTECTED FORMULA FINGERPRINTS ──────────────────────────────────────────
formula_fingerprints:
  formulas_editable: false
  formula_cell_count: null
  formula_hash: null
  sheet_hashes: {}
  generated_at: null
  critical_protected_cells: []

# ── FORMULA EDIT POLICY ─────────────────────────────────────────────────────
formula_edit_policy:
  allow_repair: true
  allowed_repair_types:
    - broken_reference
    - missing_named_range
    - external_link_removal
    - table_range_repair
    - adjacent_formula_pattern_repair
  require_audit_log: true
  require_high_confidence_for_repair: true
  allow_structural_rewrites: false
  unrepairable_formula_action: "remove_and_trace_dependents"
  block_ready_if_supported_output_depends_on_unrepairable_formula: true

# ── SHEET & MEDIA POLICY ─────────────────────────────────────────────────────
sheet_policy:
  visible_sheets: []
  hidden_sheets: []
  deletion_candidates: []

media_policy:
  template_owner: null
  retained: []
  removed: []

# ── CLEANUP SUMMARY ─────────────────────────────────────────────────────────
cleanup_summary:
  raw_prior_values_stored: false
  unit_mix_row_labels_deleted: null
  non_template_owner_media_removed: null
  hidden_sheet_dependency_trace_completed: null
  sheets_deleted: []
  support_sheets_retained: []
  defined_names_removed_or_repaired: []
  broken_formulas_repaired: []
  broken_formulas_removed: []
  table_regions_force_cleared_count: 0
  allowlist_overrides_due_to_table_regions: 0

# ── LEAK SCAN ───────────────────────────────────────────────────────────────
leak_scan:
  passed: false
  scanned_surfaces:
    visible_sheets: false
    hidden_sheets: false
    defined_names: false
    formulas: false
    comments_notes: false
    document_properties: false
    headers_footers: false
    drawings_media: false
    charts_pivots: false
    validation_conditional_formats: false
    external_links: false
  remaining_findings: []

# ── VERIFICATION ────────────────────────────────────────────────────────────
verification:
  level: "L0_static_parse"
  production_ready: false
  workbook_opens_without_repair: null
  manifest_lint_passed: false
  manifest_lint_leakage_passed: false   # NEW — manifest_lint --cleaned-workbook
  leak_scan_passed: false
  workbook_integrity_passed: false
  write_preflight_passed: false
  formula_recalc_passed: false
  economic_sniff_passed: false
  recalc_method: "excel_skill_scripts_recalc_py"
  recalc_invoked_by: "tp_scripts/sniff_test.py"
  # Recalc execution rules: see SKILL.md §recalc
  recalc_attempted: false
  recalc_status: null              # one of: success | errors_found | failed_invocation | not_attempted
  execution_blocker: null
  new_error_count: null
  verified_workbook: null
  runtime_input_limitations: []
  notes: []
```

## Limitation strings (for the `limitations` field)

The `status` field collapses what was previously eight states. Sub-reasons live in `limitations`. Conventional strings:

- `unit_mix_table_required_at_runtime`
- `construction_budget_required_at_runtime`
- `permanent_loan_inputs_required_at_runtime`
- `recalc_execution_failed`
- `economic_sniff_failed_listed_outputs`
- `manifest_leakage_unaccounted_values`
- `script_extraction_failure`
- `external_links_pending_user_decision`

Add deal-specific strings as needed; keep them short and grep-able.
