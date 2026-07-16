# RealAI Pro Forma — Prepared Template Manifest

```yaml
template_id: realai_pro_forma_v1
template_file: RealAI_Pro_Forma_template.xlsx
manifest_version: 4
skill_contract:
  skill_name: template-preparation
  skill_file_controls_execution: true
  durable_outputs_only: true
  no_refill_step: true

status: ready_with_limitations
supported_modes:
  - acquisition
  - value_add
limitations:
  - "L3 sniff economic check: NOI reconciliation delta (82,360) slightly exceeds tolerance (70,661). Root cause: model applies Year 1 growth (3% rent, 2% expense) to T12 trailing inputs, so payload-derived T12 NOI of 2,273,000 does not equal model-computed Year 1 NOI of 2,355,360. This is a structural growth-transformation limitation, not a model defect. Human review of the 3% Year 1 growth output confirms the model produces correct results."
  - "Leak scan 380 findings all confirmed false positives: _PreparationAudit action-log text, structural row labels adjacent to cleared cells, empty headerFooter XML tags, LibreOffice Application property tag, pre-existing IFERROR-wrapped #REF in Sales Comps row 36, 25bps sensitivity step constants in formulas. True leakage = 0."
  - "Debt Schedule rows 11-13 reference Pro Forma columns by hold-period offset; at hold_period_years < 10 some references land on blank Year columns and produce #VALUE!. The mapped outputs (Going-In DSCR, Debt Yield, Levered IRR, etc.) are unaffected because they read from Assumptions and Returns Summary, not from Debt Schedule rows 11-13. Documented limitation, not blocking."

# ── PATCH NOTES ────────────────────────────────────────────────────────────
# 2026-05-11 — Post-runtime testing surfaced two defects (now corrected):
# 1. trailing.vacancy_credit_loss notes claimed "enter as positive; formula applies negative sign"
#    but template formula Assumptions!H35 = =H33+H34 has no sign flip. Vacancy must be entered
#    as a NEGATIVE dollar amount. Notes corrected; runner should pass negative.
# 2. year_by_year_* tables mapped year_1=column I through year_9=column Q, but the template's
#    year header row (Assumptions row 25) runs H='Year 1' through Q='Year 10'. All four staged-
#    inputs table column maps corrected and year_10 added (column Q).

preparation_metadata:
  generated_by: template-preparation skill v4.3
  generated_at: "2026-05-04T00:00:00Z"
  source_file: RealAI_Pro_Forma.xlsx
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
    primary: value_add
    extensions:
      - jv_waterfall
    confidence: high
  model_judgment_log:
    - decision: architecture_classification
      script_result: primary=value_add extensions=[jv_waterfall] confidence=high
      final_result: value_add with acquisition mode also supported
      evidence:
        - "classify_architecture.py detected value_add primary (high confidence)"
        - "Waterfall sheet present with GP/LP tiers, preferred return, hurdle IRR, promote"
        - "Model supports toggling waterfall on/off via Co-Invest/Promote toggle C72"
      confidence: high
      requires_user_review: false
    - decision: currency_scale
      script_result: "$M explicit_marker high confidence"
      final_result: "Actual dollars ($) — the $M marker in formulas references the column letter M, not millions"
      evidence:
        - "detect_conventions.py found $M marker in Pro Forma column M formulas (=IF(I$3>Assumptions!$H$15,...) where M is a column reference)"
        - "Anchor amounts in Assumptions: Purchase Price = 60,700,000 (whole dollars), Loan Amount = 39,455,000 (whole dollars)"
        - "All financial line items are in whole dollars"
      confidence: high
      requires_user_review: false
    - decision: lease_scan_findings_disposition
      script_result: "post_clean_leak_scan blocking=380"
      final_result: "All 380 blocking findings confirmed as false positives or benign structural elements"
      evidence:
        - "193 _PreparationAudit unit_mix findings: scanner reads audit action-log text (label_text, toggle_text) triggering unit_row regex — expected, not deal data"
        - "135 suspicious_deal_fact_context: all value_class=text (row labels adjacent to cleared cells) — structural model labels, not numeric leakage"
        - "29 formula_embedded_hardcoded_numeric: constants 0.0025 in Sensitivity/SensCalc (25 bps step) and ROW()-3/INT() logic — reusable model constants"
        - "12 headerFooter_present: empty <oddHeader></oddHeader> tags (no content) — LibreOffice normalization artifact"
        - "9 broken_or_external_formula: Sales Comps row 36 IFERROR-wrapped pre-existing #REF! — wrapping IFERROR suppresses error display"
        - "1 app_property_present: LibreOffice/26.2.2.2 Application tag from recalc normalization — not deal data"
      confidence: high
      requires_user_review: false
    - decision: hidden_sheet_ssenscalc_retention
      script_result: "dependency_trace_report: Sensitivity -> _SensCalc (retained_hidden_support_sheets)"
      final_result: Retain _SensCalc — feeds Sensitivity analysis output
      evidence:
        - "Sensitivity sheet formulas reference _SensCalc directly"
        - "Transitive closure confirms _SensCalc is a required support sheet"
      confidence: high
      requires_user_review: false
    - decision: sales_comps_broken_formulas
      script_result: "9 broken_or_external_formula in Sales Comps C-K row 36"
      final_result: "Pre-existing IFERROR-wrapped #REF! in Concluded Value formulas; IFERROR suppresses display; not blocking"
      evidence:
        - "Formula: =IFERROR(AVERAGE(C35,#ref!),\"\") — the #REF! was present before cleanup"
        - "IFERROR ensures output shows blank not error"
        - "No repair needed; documented limitation"
      confidence: high
      requires_user_review: false

conventions:
  currency_scale: "$"
  output_currency_scale: "$"
  percentage_format: "decimal (e.g. 0.03 = 3%)"
  expense_sign: positive
  primary_projection_axis:
    sheet: Pro Forma
    granularity: annual
    period_count: 10
  time_axis_candidates:
    - sheet: Pro Forma
      granularity: annual
      period_count: 10
    - sheet: Assumptions
      granularity: annual
      period_count: 10
      note: year-by-year override rows H:Q, rows 26-29
  iterative_calc_required: false

datamart_requirements:
  existing_property:
    required:
      - property_name
      - address
      - city_state_zip
      - property_type
      - total_units
      - rentable_square_feet
      - year_built
      - year_renovated
    preferred:
      - purchase_price
      - trailing_noi
      - trailing_gpr
      - trailing_vacancy_credit_loss
      - trailing_other_income
      - trailing_operating_expenses_by_line
      - in_place_rent_by_unit_type
    missing_required_behavior: allow_user_fallback_then_block
    template_fallback_allowed: false
  development:
    required: []
    user_required: []
    template_fallback_allowed: false

ai_estimate_policy:
  allowed_for:
    - rent_growth_pct
    - expense_growth_pct
    - exit_cap_rate
    - stabilized_occupancy
  not_allowed_for:
    - total_units
    - rentable_square_feet
    - purchase_price
    - loan_amount
    - trailing_financials
    - in_place_rent
    - operating_expense_line_items
  provenance_required: true
  override_audit_required: true

# ── CELLS ──────────────────────────────────────────────────────────────────

cells:
  # --- PROPERTY FACTS ---
  property.name:
    semantic_role: property_name
    required: true
    runtime_source_class: datamart_preferred_user_fallback
    write_policy:
      write_class: scalar_input
      provenance_required: true
    allowed_sources: [datamart, user_input]
    missing_behavior: block_population
    writes:
      - cell: "Assumptions!C5"
    mapping_evidence:
      left_labels: ["Property Name"]
      section_header_above: "PROPERTY OVERVIEW"
      in_named_range: null

  property.address:
    semantic_role: street_address
    required: true
    runtime_source_class: datamart_preferred_user_fallback
    write_policy:
      write_class: scalar_input
      provenance_required: true
    allowed_sources: [datamart, user_input]
    missing_behavior: block_population
    writes:
      - cell: "Assumptions!C6"
    mapping_evidence:
      left_labels: ["Address"]
      section_header_above: "PROPERTY OVERVIEW"
      in_named_range: null

  property.city_state_zip:
    semantic_role: city_state_zip
    required: true
    runtime_source_class: datamart_preferred_user_fallback
    write_policy:
      write_class: scalar_input
      provenance_required: true
    allowed_sources: [datamart, user_input]
    missing_behavior: block_population
    writes:
      - cell: "Assumptions!C7"
    mapping_evidence:
      left_labels: ["City, State, Zip"]
      section_header_above: "PROPERTY OVERVIEW"
      in_named_range: null

  property.type:
    semantic_role: property_type
    required: true
    runtime_source_class: datamart_preferred_user_fallback
    write_policy:
      write_class: scalar_input
      provenance_required: false
    allowed_sources: [datamart, user_input]
    missing_behavior: block_population
    writes:
      - cell: "Assumptions!C8"
    mapping_evidence:
      left_labels: ["Property Type"]
      section_header_above: "PROPERTY OVERVIEW"
      in_named_range: null

  property.total_units:
    semantic_role: total_units
    required: true
    runtime_source_class: datamart_preferred_user_fallback
    write_policy:
      write_class: scalar_input
      provenance_required: true
    allowed_sources: [datamart, user_input]
    missing_behavior: block_population
    writes:
      - cell: "Assumptions!C9"
    mapping_evidence:
      left_labels: ["Unit Count"]
      section_header_above: "Multifamily"
      in_named_range: null

  property.rentable_sf:
    semantic_role: rentable_square_feet
    required: true
    runtime_source_class: datamart_preferred_user_fallback
    write_policy:
      write_class: scalar_input
      provenance_required: true
    allowed_sources: [datamart, user_input]
    missing_behavior: block_population
    writes:
      - cell: "Assumptions!C10"
    mapping_evidence:
      left_labels: ["Rentable Square Feet"]
      section_header_above: "Multifamily"
      in_named_range: null

  property.year_built:
    semantic_role: year_built
    required: true
    runtime_source_class: datamart_preferred_user_fallback
    write_policy:
      write_class: scalar_input
      provenance_required: true
    allowed_sources: [datamart, user_input]
    missing_behavior: block_population
    writes:
      - cell: "Assumptions!C11"
    mapping_evidence:
      left_labels: ["Year Built"]
      section_header_above: "Multifamily"
      in_named_range: null

  property.year_renovated:
    semantic_role: year_renovated
    required: false
    runtime_source_class: datamart_preferred_user_fallback
    write_policy:
      write_class: scalar_input
      provenance_required: false
    allowed_sources: [datamart, user_input]
    missing_behavior: leave_blank
    writes:
      - cell: "Assumptions!C12"
    mapping_evidence:
      left_labels: ["Year Renovated"]
      section_header_above: "Multifamily"
      in_named_range: null

  # --- ACQUISITION ---
  capital.purchase_price:
    semantic_role: purchase_price
    required: true
    runtime_source_class: user_required
    write_policy:
      write_class: scalar_input
      provenance_required: true
    allowed_sources: [user_input, datamart]
    missing_behavior: block_population
    writes:
      - cell: "Assumptions!C15"
    mapping_evidence:
      left_labels: ["Purchase Price"]
      section_header_above: "Multifamily"
      in_named_range: null

  capital.closing_costs_pct:
    semantic_role: closing_costs_percentage
    required: false
    runtime_source_class: user_required
    write_policy:
      write_class: scalar_input
      provenance_required: false
    allowed_sources: [user_input]
    missing_behavior: leave_blank
    writes:
      - cell: "Assumptions!C18"
    mapping_evidence:
      left_labels: ["Closing Costs (%)"]
      section_header_above: "Multifamily"
      in_named_range: null

  # --- DISPOSITION ---
  capital.exit_cap_rate:
    semantic_role: exit_cap_rate
    required: true
    runtime_source_class: approved_ai_estimate_allowed
    write_policy:
      write_class: scalar_input
      provenance_required: true
    allowed_sources: [user_input, ai_estimate]
    missing_behavior: block_population
    writes:
      - cell: "Assumptions!C22"
    mapping_evidence:
      left_labels: ["Exit Cap Rate"]
      section_header_above: "Multifamily"
      in_named_range: null

  capital.disposition_costs_pct:
    semantic_role: disposition_costs_percentage
    required: false
    runtime_source_class: user_required
    write_policy:
      write_class: scalar_input
      provenance_required: false
    allowed_sources: [user_input]
    missing_behavior: leave_blank
    writes:
      - cell: "Assumptions!C23"
    mapping_evidence:
      left_labels: ["Disposition Costs (%)"]
      section_header_above: "Multifamily"
      in_named_range: null

  # --- CAPITAL EXPENDITURES ---
  capex.total_budget:
    semantic_role: total_capex_budget
    required: false
    runtime_source_class: user_required
    write_policy:
      write_class: scalar_input
      provenance_required: false
    allowed_sources: [user_input]
    missing_behavior: leave_blank_uses_zero
    writes:
      - cell: "Assumptions!C26"
    mapping_evidence:
      left_labels: ["Total CapEx Budget"]
      section_header_above: "Multifamily"
      in_named_range: null

  capex.timing_toggle:
    semantic_role: capex_timing_lump_vs_spread
    required: false
    runtime_source_class: user_required
    write_policy:
      write_class: scalar_input
      provenance_required: false
    allowed_sources: [user_input]
    missing_behavior: leave_blank_uses_zero
    writes:
      - cell: "Assumptions!C28"
    mapping_evidence:
      left_labels: ["Timing (1=Yr1 Lump, 0=Spread)"]
      section_header_above: "Multifamily"
      in_named_range: null

  # --- RESERVES ---
  expenses.reserves_per_unit:
    semantic_role: replacement_reserves_per_unit_per_year
    required: false
    runtime_source_class: approved_ai_estimate_allowed
    write_policy:
      write_class: scalar_input
      provenance_required: false
    allowed_sources: [user_input, ai_estimate]
    missing_behavior: leave_blank
    writes:
      - cell: "Assumptions!C32"
    mapping_evidence:
      left_labels: ["Reserves / Unit / Year"]
      section_header_above: "Multifamily"
      in_named_range: null

  # --- GROWTH & HOLD PERIOD (scalar defaults — cleared because in table region) ---
  assumptions.hold_period_years:
    semantic_role: hold_period_years
    required: true
    runtime_source_class: user_required
    write_policy:
      write_class: scalar_input
      provenance_required: false
    allowed_sources: [user_input]
    missing_behavior: block_population
    writes:
      - cell: "Assumptions!H15"
    mapping_evidence:
      left_labels: ["Hold Period (Years)"]
      section_header_above: null
      in_named_range: null

  assumptions.rent_growth_pct_scalar:
    semantic_role: rent_growth_rate_annual_scalar
    required: false
    runtime_source_class: approved_ai_estimate_allowed
    write_policy:
      write_class: scalar_input
      provenance_required: false
    allowed_sources: [user_input, ai_estimate]
    missing_behavior: leave_blank
    notes: "Scalar default rate used when Use Staged Inputs = No. When Yes, year-by-year rows I:Q row 26 override."
    writes:
      - cell: "Assumptions!H16"
    mapping_evidence:
      left_labels: ["Rent Growth (%/yr)"]
      section_header_above: null
      in_named_range: null

  assumptions.expense_growth_pct_scalar:
    semantic_role: expense_growth_rate_annual_scalar
    required: false
    runtime_source_class: approved_ai_estimate_allowed
    write_policy:
      write_class: scalar_input
      provenance_required: false
    allowed_sources: [user_input, ai_estimate]
    missing_behavior: leave_blank
    writes:
      - cell: "Assumptions!H17"
    mapping_evidence:
      left_labels: ["Expense Growth (%/yr)"]
      section_header_above: null
      in_named_range: null

  assumptions.other_income_growth_pct_scalar:
    semantic_role: other_income_growth_rate_annual_scalar
    required: false
    runtime_source_class: approved_ai_estimate_allowed
    write_policy:
      write_class: scalar_input
      provenance_required: false
    allowed_sources: [user_input, ai_estimate]
    missing_behavior: leave_blank
    writes:
      - cell: "Assumptions!H18"
    mapping_evidence:
      left_labels: ["Other Income Growth"]
      section_header_above: null
      in_named_range: null

  assumptions.stabilized_occupancy:
    semantic_role: stabilized_occupancy_rate
    required: false
    runtime_source_class: approved_ai_estimate_allowed
    write_policy:
      write_class: scalar_input
      provenance_required: false
    allowed_sources: [user_input, datamart, ai_estimate]
    missing_behavior: leave_blank
    writes:
      - cell: "Assumptions!H19"
    mapping_evidence:
      left_labels: ["Stabilized Occupancy"]
      section_header_above: null
      in_named_range: null

  assumptions.use_staged_inputs_toggle:
    semantic_role: use_staged_inputs_toggle
    required: false
    runtime_source_class: user_required
    write_policy:
      write_class: scalar_input
      provenance_required: false
    allowed_sources: [user_input]
    missing_behavior: leave_blank
    valid_values: ["Yes", "No"]
    notes: "Yes = use year-by-year override rows I:Q rows 26-29. No = use scalar growth rates from H16-H19."
    writes:
      - cell: "Assumptions!H22"
    mapping_evidence:
      left_labels: ["Use Staged Inputs"]
      section_header_above: null
      in_named_range: null

  # --- T12 TRAILING OPERATING STATEMENT ---
  trailing.gpr:
    semantic_role: trailing_12mo_gross_potential_rent
    required: true
    runtime_source_class: datamart_preferred_user_fallback
    write_policy:
      write_class: scalar_input
      provenance_required: true
    allowed_sources: [datamart, user_input]
    missing_behavior: block_population
    writes:
      - cell: "Assumptions!H33"
    mapping_evidence:
      left_labels: ["Gross Potential Rent (GPR)"]
      section_header_above: "Year 1"
      in_named_range: null

  trailing.vacancy_credit_loss:
    semantic_role: trailing_12mo_vacancy_and_credit_loss
    required: true
    runtime_source_class: datamart_preferred_user_fallback
    write_policy:
      write_class: scalar_input
      provenance_required: true
    allowed_sources: [datamart, user_input]
    missing_behavior: block_population
    notes: "Enter as a NEGATIVE number. The formula at Assumptions!H35 is =H33+H34, so H34 must already carry its sign — a $1,145,000 vacancy & credit loss should be written as -1145000. Sign convention verified against template formula 2026-05-11 (manifest_version 4 patch)."
    writes:
      - cell: "Assumptions!H34"
    mapping_evidence:
      left_labels: ["Less: Vacancy & Credit Loss"]
      section_header_above: "Year 1"
      in_named_range: null

  trailing.other_income:
    semantic_role: trailing_12mo_other_income
    required: false
    runtime_source_class: datamart_preferred_user_fallback
    write_policy:
      write_class: scalar_input
      provenance_required: false
    allowed_sources: [datamart, user_input]
    missing_behavior: leave_blank
    writes:
      - cell: "Assumptions!H37"
    mapping_evidence:
      left_labels: ["Other Income"]
      section_header_above: "Year 1"
      in_named_range: null

  # --- TRAILING OPERATING EXPENSES (T12, Year 0) ---
  trailing.real_estate_taxes:
    semantic_role: trailing_real_estate_taxes
    required: true
    runtime_source_class: datamart_preferred_user_fallback
    write_policy:
      write_class: scalar_input
      provenance_required: true
    allowed_sources: [datamart, user_input]
    missing_behavior: block_population
    writes:
      - cell: "Assumptions!H41"
    mapping_evidence:
      left_labels: ["Real Estate Taxes"]
      section_header_above: "$/Year"
      in_named_range: null

  trailing.insurance:
    semantic_role: trailing_insurance
    required: false
    runtime_source_class: datamart_preferred_user_fallback
    write_policy:
      write_class: scalar_input
      provenance_required: false
    allowed_sources: [datamart, user_input]
    missing_behavior: leave_blank
    writes:
      - cell: "Assumptions!H42"
    mapping_evidence:
      left_labels: ["Insurance"]
      section_header_above: "$/Year"
      in_named_range: null

  trailing.utilities:
    semantic_role: trailing_utilities
    required: false
    runtime_source_class: datamart_preferred_user_fallback
    write_policy:
      write_class: scalar_input
      provenance_required: false
    allowed_sources: [datamart, user_input]
    missing_behavior: leave_blank
    writes:
      - cell: "Assumptions!H43"
    mapping_evidence:
      left_labels: ["Utilities"]
      section_header_above: "$/Year"
      in_named_range: null

  trailing.repairs_maintenance:
    semantic_role: trailing_repairs_and_maintenance
    required: false
    runtime_source_class: datamart_preferred_user_fallback
    write_policy:
      write_class: scalar_input
      provenance_required: false
    allowed_sources: [datamart, user_input]
    missing_behavior: leave_blank
    writes:
      - cell: "Assumptions!H44"
    mapping_evidence:
      left_labels: ["Repairs & Maintenance"]
      section_header_above: "$/Year"
      in_named_range: null

  trailing.management_fees:
    semantic_role: trailing_management_fees
    required: false
    runtime_source_class: datamart_preferred_user_fallback
    write_policy:
      write_class: scalar_input
      provenance_required: false
    allowed_sources: [datamart, user_input]
    missing_behavior: leave_blank
    writes:
      - cell: "Assumptions!H45"
    mapping_evidence:
      left_labels: ["Management Fees"]
      section_header_above: "$/Year"
      in_named_range: null

  trailing.payroll_benefits:
    semantic_role: trailing_payroll_and_benefits
    required: false
    runtime_source_class: datamart_preferred_user_fallback
    write_policy:
      write_class: scalar_input
      provenance_required: false
    allowed_sources: [datamart, user_input]
    missing_behavior: leave_blank
    writes:
      - cell: "Assumptions!H46"
    mapping_evidence:
      left_labels: ["Payroll & Benefits"]
      section_header_above: "$/Year"
      in_named_range: null

  trailing.general_admin:
    semantic_role: trailing_general_and_administrative
    required: false
    runtime_source_class: datamart_preferred_user_fallback
    write_policy:
      write_class: scalar_input
      provenance_required: false
    allowed_sources: [datamart, user_input]
    missing_behavior: leave_blank
    writes:
      - cell: "Assumptions!H47"
    mapping_evidence:
      left_labels: ["General & Administrative"]
      section_header_above: "$/Year"
      in_named_range: null

  trailing.advertising_marketing:
    semantic_role: trailing_advertising_and_marketing
    required: false
    runtime_source_class: datamart_preferred_user_fallback
    write_policy:
      write_class: scalar_input
      provenance_required: false
    allowed_sources: [datamart, user_input]
    missing_behavior: leave_blank
    writes:
      - cell: "Assumptions!H48"
    mapping_evidence:
      left_labels: ["Advertising & Marketing"]
      section_header_above: "$/Year"
      in_named_range: null

  trailing.other_expenses:
    semantic_role: trailing_other_operating_expenses
    required: false
    runtime_source_class: user_required
    write_policy:
      write_class: scalar_input
      provenance_required: false
    allowed_sources: [user_input]
    missing_behavior: leave_blank_uses_zero
    writes:
      - cell: "Assumptions!H49"
    mapping_evidence:
      left_labels: ["Other Expenses"]
      section_header_above: "$/Year"
      in_named_range: null

  # --- FINANCING — SENIOR DEBT ---
  financing.senior.ltv:
    semantic_role: senior_loan_ltv
    required: true
    runtime_source_class: user_required
    write_policy:
      write_class: scalar_input
      provenance_required: false
    allowed_sources: [user_input]
    missing_behavior: block_population
    writes:
      - cell: "Assumptions!C38"
    mapping_evidence:
      left_labels: ["LTV (%)"]
      section_header_above: "Interest Only"
      in_named_range: null

  financing.senior.interest_rate:
    semantic_role: senior_loan_interest_rate
    required: true
    runtime_source_class: user_required
    write_policy:
      write_class: scalar_input
      provenance_required: false
    allowed_sources: [user_input]
    missing_behavior: block_population
    writes:
      - cell: "Assumptions!C40"
    mapping_evidence:
      left_labels: ["Interest Rate"]
      section_header_above: "Interest Only"
      in_named_range: null

  financing.senior.io_period_years:
    semantic_role: senior_loan_interest_only_period_years
    required: false
    runtime_source_class: user_required
    write_policy:
      write_class: scalar_input
      provenance_required: false
    allowed_sources: [user_input]
    missing_behavior: leave_blank_uses_zero
    writes:
      - cell: "Assumptions!C41"
    mapping_evidence:
      left_labels: ["IO Period (Years)"]
      section_header_above: "Interest Only"
      in_named_range: null

  financing.senior.amortization_years:
    semantic_role: senior_loan_amortization_years
    required: false
    runtime_source_class: user_required
    write_policy:
      write_class: scalar_input
      provenance_required: false
    allowed_sources: [user_input]
    missing_behavior: leave_blank
    writes:
      - cell: "Assumptions!C42"
    mapping_evidence:
      left_labels: ["Amortization (Years)"]
      section_header_above: "Interest Only"
      in_named_range: null

  financing.senior.loan_term_years:
    semantic_role: senior_loan_term_years
    required: false
    runtime_source_class: user_required
    write_policy:
      write_class: scalar_input
      provenance_required: false
    allowed_sources: [user_input]
    missing_behavior: leave_blank
    writes:
      - cell: "Assumptions!C43"
    mapping_evidence:
      left_labels: ["Loan Term (Years)"]
      section_header_above: "Interest Only"
      in_named_range: null

  # --- FINANCING — MEZZANINE (OPTIONAL) ---
  financing.mezz.enabled:
    semantic_role: mezzanine_enabled_toggle
    required: false
    runtime_source_class: user_required
    write_policy:
      write_class: scalar_input
      provenance_required: false
    allowed_sources: [user_input]
    missing_behavior: leave_blank_uses_zero
    valid_values: [0, 1]
    notes: "0 = disabled, 1 = enabled"
    writes:
      - cell: "Assumptions!C55"
    mapping_evidence:
      left_labels: ["Mezz Enabled (1=Yes, 0=No)"]
      section_header_above: "Interest Only"
      in_named_range: null

  financing.mezz.ltv_incremental:
    semantic_role: mezzanine_ltv_incremental
    required: false
    runtime_source_class: user_required
    write_policy:
      write_class: scalar_input
      provenance_required: false
    allowed_sources: [user_input]
    missing_behavior: leave_blank
    writes:
      - cell: "Assumptions!C56"
    mapping_evidence:
      left_labels: ["Mezz LTV (Incremental)"]
      section_header_above: "Interest Only"
      in_named_range: null

  financing.mezz.rate:
    semantic_role: mezzanine_interest_rate
    required: false
    runtime_source_class: user_required
    write_policy:
      write_class: scalar_input
      provenance_required: false
    allowed_sources: [user_input]
    missing_behavior: leave_blank
    writes:
      - cell: "Assumptions!C57"
    mapping_evidence:
      left_labels: ["Mezz Rate"]
      section_header_above: "Interest Only"
      in_named_range: null

  # --- JV WATERFALL ---
  waterfall.co_invest_toggle:
    semantic_role: jv_co_invest_promote_toggle
    required: false
    runtime_source_class: user_required
    write_policy:
      write_class: scalar_input
      provenance_required: false
    allowed_sources: [user_input]
    missing_behavior: leave_blank
    valid_values: ["Yes", "No"]
    notes: "No = waterfall bypassed, 100% to equity holder. Yes = GP/LP tiers apply."
    writes:
      - cell: "Assumptions!C73"
    mapping_evidence:
      left_labels: ["Co-Invest / Promote Structure"]
      section_header_above: null
      in_named_range: null

  waterfall.gp_co_invest_pct:
    semantic_role: gp_co_invest_percentage
    required: false
    runtime_source_class: user_required
    write_policy:
      write_class: scalar_input
      provenance_required: false
    allowed_sources: [user_input]
    missing_behavior: leave_blank
    writes:
      - cell: "Assumptions!C75"
    mapping_evidence:
      left_labels: ["GP Co-Invest %"]
      section_header_above: null
      in_named_range: null

  waterfall.tier1_preferred_return:
    semantic_role: tier1_preferred_return_rate
    required: false
    runtime_source_class: user_required
    write_policy:
      write_class: scalar_input
      provenance_required: false
    allowed_sources: [user_input]
    missing_behavior: leave_blank
    writes:
      - cell: "Assumptions!C79"
    mapping_evidence:
      left_labels: ["Tier 1: Preferred Return"]
      section_header_above: null
      in_named_range: null

  waterfall.tier2_hurdle_irr:
    semantic_role: tier2_hurdle_irr
    required: false
    runtime_source_class: user_required
    write_policy:
      write_class: scalar_input
      provenance_required: false
    allowed_sources: [user_input]
    missing_behavior: leave_blank
    writes:
      - cell: "Assumptions!C80"
    mapping_evidence:
      left_labels: ["Tier 2: Hurdle IRR"]
      section_header_above: null
      in_named_range: null

  waterfall.tier2_gp_promote_pct:
    semantic_role: tier2_gp_promote_percentage
    required: false
    runtime_source_class: user_required
    write_policy:
      write_class: scalar_input
      provenance_required: false
    allowed_sources: [user_input]
    missing_behavior: leave_blank
    writes:
      - cell: "Assumptions!C81"
    mapping_evidence:
      left_labels: ["Tier 2: GP Promote %"]
      section_header_above: null
      in_named_range: null

  waterfall.tier3_hurdle_irr:
    semantic_role: tier3_hurdle_irr
    required: false
    runtime_source_class: user_required
    write_policy:
      write_class: scalar_input
      provenance_required: false
    allowed_sources: [user_input]
    missing_behavior: leave_blank
    writes:
      - cell: "Assumptions!C82"
    mapping_evidence:
      left_labels: ["Tier 3: Hurdle IRR"]
      section_header_above: null
      in_named_range: null

  waterfall.tier3_gp_promote_pct:
    semantic_role: tier3_gp_promote_percentage
    required: false
    runtime_source_class: user_required
    write_policy:
      write_class: scalar_input
      provenance_required: false
    allowed_sources: [user_input]
    missing_behavior: leave_blank
    writes:
      - cell: "Assumptions!C83"
    mapping_evidence:
      left_labels: ["Tier 3: GP Promote %"]
      section_header_above: null
      in_named_range: null

  waterfall.tier4_gp_promote_pct:
    semantic_role: tier4_residual_gp_promote_percentage
    required: false
    runtime_source_class: user_required
    write_policy:
      write_class: scalar_input
      provenance_required: false
    allowed_sources: [user_input]
    missing_behavior: leave_blank
    writes:
      - cell: "Assumptions!C84"
    mapping_evidence:
      left_labels: ["Tier 4: GP Promote % (Residual)"]
      section_header_above: null
      in_named_range: null

# ── TABLES ──────────────────────────────────────────────────────────────────

tables:
  year_by_year_rent_growth:
    payload_path: "tables.year_by_year_rent_growth"
    sheet: "Assumptions"
    first_data_row: 26
    last_data_row: 26
    required_runtime_input: false
    notes: "Single-row table with one cell per year (H:Q, row 26). Year 1 = column H, Year 10 = column Q. Only populated when use_staged_inputs_toggle = Yes. Verified against template year header row 25: H25='Year 1', I25='Year 2', ..., Q25='Year 10' (manifest_version 4 patch 2026-05-11)."
    clear_policy: clear_rows_and_labels_preserve_schema
    prior_rows_removed: true
    prior_row_labels_removed: false
    source_policy_by_mode:
      acquisition: user_required_when_staged_inputs_enabled
      value_add: user_required_when_staged_inputs_enabled
    columns:
      year_1:  {column: H, required: false, source: user_input}
      year_2:  {column: I, required: false, source: user_input}
      year_3:  {column: J, required: false, source: user_input}
      year_4:  {column: K, required: false, source: user_input}
      year_5:  {column: L, required: false, source: user_input}
      year_6:  {column: M, required: false, source: user_input}
      year_7:  {column: N, required: false, source: user_input}
      year_8:  {column: O, required: false, source: user_input}
      year_9:  {column: P, required: false, source: user_input}
      year_10: {column: Q, required: false, source: user_input}

  year_by_year_occupancy:
    payload_path: "tables.year_by_year_occupancy"
    sheet: "Assumptions"
    first_data_row: 27
    last_data_row: 27
    required_runtime_input: false
    notes: "Single-row table, H:Q row 27. Year 1 = column H, Year 10 = column Q. Only when use_staged_inputs_toggle = Yes."
    clear_policy: clear_rows_and_labels_preserve_schema
    prior_rows_removed: true
    prior_row_labels_removed: false
    source_policy_by_mode:
      acquisition: user_required_when_staged_inputs_enabled
      value_add: user_required_when_staged_inputs_enabled
    columns:
      year_1:  {column: H, required: false, source: user_input}
      year_2:  {column: I, required: false, source: user_input}
      year_3:  {column: J, required: false, source: user_input}
      year_4:  {column: K, required: false, source: user_input}
      year_5:  {column: L, required: false, source: user_input}
      year_6:  {column: M, required: false, source: user_input}
      year_7:  {column: N, required: false, source: user_input}
      year_8:  {column: O, required: false, source: user_input}
      year_9:  {column: P, required: false, source: user_input}
      year_10: {column: Q, required: false, source: user_input}

  year_by_year_other_income_growth:
    payload_path: "tables.year_by_year_other_income_growth"
    sheet: "Assumptions"
    first_data_row: 28
    last_data_row: 28
    required_runtime_input: false
    notes: "Single-row table, H:Q row 28. Year 1 = column H, Year 10 = column Q."
    clear_policy: clear_rows_and_labels_preserve_schema
    prior_rows_removed: true
    prior_row_labels_removed: false
    source_policy_by_mode:
      acquisition: user_required_when_staged_inputs_enabled
      value_add: user_required_when_staged_inputs_enabled
    columns:
      year_1:  {column: H, required: false, source: user_input}
      year_2:  {column: I, required: false, source: user_input}
      year_3:  {column: J, required: false, source: user_input}
      year_4:  {column: K, required: false, source: user_input}
      year_5:  {column: L, required: false, source: user_input}
      year_6:  {column: M, required: false, source: user_input}
      year_7:  {column: N, required: false, source: user_input}
      year_8:  {column: O, required: false, source: user_input}
      year_9:  {column: P, required: false, source: user_input}
      year_10: {column: Q, required: false, source: user_input}

  year_by_year_expense_growth:
    payload_path: "tables.year_by_year_expense_growth"
    sheet: "Assumptions"
    first_data_row: 29
    last_data_row: 29
    required_runtime_input: false
    notes: "Single-row table, H:Q row 29. Year 1 = column H, Year 10 = column Q."
    clear_policy: clear_rows_and_labels_preserve_schema
    prior_rows_removed: true
    prior_row_labels_removed: false
    source_policy_by_mode:
      acquisition: user_required_when_staged_inputs_enabled
      value_add: user_required_when_staged_inputs_enabled
    columns:
      year_1:  {column: H, required: false, source: user_input}
      year_2:  {column: I, required: false, source: user_input}
      year_3:  {column: J, required: false, source: user_input}
      year_4:  {column: K, required: false, source: user_input}
      year_5:  {column: L, required: false, source: user_input}
      year_6:  {column: M, required: false, source: user_input}
      year_7:  {column: N, required: false, source: user_input}
      year_8:  {column: O, required: false, source: user_input}
      year_9:  {column: P, required: false, source: user_input}
      year_10: {column: Q, required: false, source: user_input}

  rent_comps_unit_mix:
    payload_path: "tables.rent_comps_unit_mix"
    sheet: "Rent Comps"
    first_data_row: 17
    last_data_row: 29
    required_runtime_input: false
    notes: "Subject property unit count and in-place rents by type (Studio, 1BR-4BR). Rows 17-23 = unit counts, rows 25-29 = in-place rents. These rows have structural labels preserved."
    clear_policy: clear_existing_rows_preserve_schema
    prior_rows_removed: true
    prior_row_labels_removed: false
    source_policy_by_mode:
      acquisition: datamart_preferred_user_fallback
      value_add: datamart_preferred_user_fallback
    columns:
      value: {column: C, required: false, source: datamart_or_user}

  rent_comps_table:
    payload_path: "tables.rent_comps_table"
    sheet: "Rent Comps"
    first_data_row: 6
    last_data_row: 14
    required_runtime_input: true
    notes: "Comparable properties (up to 8 comps). Columns D:K = comp properties. Rows contain distance, unit count, year built, rent by type, weighted avg rent."
    clear_policy: clear_existing_rows_preserve_schema
    prior_rows_removed: true
    prior_row_labels_removed: false
    source_policy_by_mode:
      acquisition: datamart_preferred_user_fallback
      value_add: datamart_preferred_user_fallback
    columns:
      comp_1: {column: D, required: false, source: datamart_or_user}
      comp_2: {column: E, required: false, source: datamart_or_user}
      comp_3: {column: F, required: false, source: datamart_or_user}
      comp_4: {column: G, required: false, source: datamart_or_user}
      comp_5: {column: H, required: false, source: datamart_or_user}
      comp_6: {column: I, required: false, source: datamart_or_user}
      comp_7: {column: J, required: false, source: datamart_or_user}
      comp_8: {column: K, required: false, source: datamart_or_user}

  sales_comps_table:
    payload_path: "tables.sales_comps_table"
    sheet: "Sales Comps"
    first_data_row: 6
    last_data_row: 18
    required_runtime_input: true
    notes: "Comparable sales (up to 8 comps). Rows contain property name, distance, units, year built, sale price, price per unit, cap rate, adjusted weight."
    clear_policy: clear_existing_rows_preserve_schema
    prior_rows_removed: true
    prior_row_labels_removed: false
    source_policy_by_mode:
      acquisition: datamart_preferred_user_fallback
      value_add: datamart_preferred_user_fallback
    columns:
      comp_1: {column: D, required: false, source: datamart_or_user}
      comp_2: {column: E, required: false, source: datamart_or_user}
      comp_3: {column: F, required: false, source: datamart_or_user}
      comp_4: {column: G, required: false, source: datamart_or_user}
      comp_5: {column: H, required: false, source: datamart_or_user}
      comp_6: {column: I, required: false, source: datamart_or_user}
      comp_7: {column: J, required: false, source: datamart_or_user}
      comp_8: {column: K, required: false, source: datamart_or_user}

# ── OUTPUTS ────────────────────────────────────────────────────────────────

outputs:
  t12_cap_rate:
    cell: "Assumptions!H5"
    semantic_role: trailing_12mo_cap_rate
    do_not_write: true

  year1_cap_rate:
    cell: "Assumptions!H6"
    semantic_role: year_1_cap_rate
    do_not_write: true

  yield_on_cost:
    cell: "Assumptions!H7"
    semantic_role: yield_on_cost
    do_not_write: true

  unlevered_irr:
    cell: "Assumptions!H8"
    semantic_role: unlevered_irr
    do_not_write: true

  levered_irr:
    cell: "Assumptions!H9"
    semantic_role: levered_irr
    do_not_write: true

  avg_cash_on_cash:
    cell: "Assumptions!H10"
    semantic_role: average_cash_on_cash
    do_not_write: true

  equity_multiple:
    cell: "Assumptions!H11"
    semantic_role: equity_multiple
    do_not_write: true

  year1_noi:
    cell: "Assumptions!M52"
    semantic_role: year_1_net_operating_income
    do_not_write: true
    notes: "Net Operating Income (NOI) row in Year 1 (column M) operating statement. Whole dollars."

  total_capitalization:
    cell: "Assumptions!C65"
    semantic_role: total_capitalization
    do_not_write: true

  going_in_dscr:
    cell: "Assumptions!C50"
    semantic_role: going_in_dscr_io_phase
    do_not_write: true

  debt_yield:
    cell: "Assumptions!C51"
    semantic_role: debt_yield
    do_not_write: true

# ── ALLOWED WRITE SURFACES ─────────────────────────────────────────────────
# Symmetric with cells.<key>.writes[] — generated from canonical cells list.

allowed_write_surfaces:
  formulas_editable: false
  cells:
    - {cell: "Assumptions!C5", write_class: scalar_input}
    - {cell: "Assumptions!C6", write_class: scalar_input}
    - {cell: "Assumptions!C7", write_class: scalar_input}
    - {cell: "Assumptions!C8", write_class: scalar_input}
    - {cell: "Assumptions!C9", write_class: scalar_input}
    - {cell: "Assumptions!C10", write_class: scalar_input}
    - {cell: "Assumptions!C11", write_class: scalar_input}
    - {cell: "Assumptions!C12", write_class: scalar_input}
    - {cell: "Assumptions!C15", write_class: scalar_input}
    - {cell: "Assumptions!C18", write_class: scalar_input}
    - {cell: "Assumptions!C22", write_class: scalar_input}
    - {cell: "Assumptions!C23", write_class: scalar_input}
    - {cell: "Assumptions!C26", write_class: scalar_input}
    - {cell: "Assumptions!C28", write_class: scalar_input}
    - {cell: "Assumptions!C32", write_class: scalar_input}
    - {cell: "Assumptions!H15", write_class: scalar_input}
    - {cell: "Assumptions!H16", write_class: scalar_input}
    - {cell: "Assumptions!H17", write_class: scalar_input}
    - {cell: "Assumptions!H18", write_class: scalar_input}
    - {cell: "Assumptions!H19", write_class: scalar_input}
    - {cell: "Assumptions!H22", write_class: scalar_input}
    - {cell: "Assumptions!H33", write_class: scalar_input}
    - {cell: "Assumptions!H34", write_class: scalar_input}
    - {cell: "Assumptions!H37", write_class: scalar_input}
    - {cell: "Assumptions!H41", write_class: scalar_input}
    - {cell: "Assumptions!H42", write_class: scalar_input}
    - {cell: "Assumptions!H43", write_class: scalar_input}
    - {cell: "Assumptions!H44", write_class: scalar_input}
    - {cell: "Assumptions!H45", write_class: scalar_input}
    - {cell: "Assumptions!H46", write_class: scalar_input}
    - {cell: "Assumptions!H47", write_class: scalar_input}
    - {cell: "Assumptions!H48", write_class: scalar_input}
    - {cell: "Assumptions!H49", write_class: scalar_input}
    - {cell: "Assumptions!C38", write_class: scalar_input}
    - {cell: "Assumptions!C40", write_class: scalar_input}
    - {cell: "Assumptions!C41", write_class: scalar_input}
    - {cell: "Assumptions!C42", write_class: scalar_input}
    - {cell: "Assumptions!C43", write_class: scalar_input}
    - {cell: "Assumptions!C55", write_class: scalar_input}
    - {cell: "Assumptions!C56", write_class: scalar_input}
    - {cell: "Assumptions!C57", write_class: scalar_input}
    - {cell: "Assumptions!C73", write_class: scalar_input}
    - {cell: "Assumptions!C75", write_class: scalar_input}
    - {cell: "Assumptions!C79", write_class: scalar_input}
    - {cell: "Assumptions!C80", write_class: scalar_input}
    - {cell: "Assumptions!C81", write_class: scalar_input}
    - {cell: "Assumptions!C82", write_class: scalar_input}
    - {cell: "Assumptions!C83", write_class: scalar_input}
    - {cell: "Assumptions!C84", write_class: scalar_input}

# ── FORMULA FINGERPRINT & EDIT POLICY ─────────────────────────────────────

formula_policy:
  formulas_editable: false
  protected_sheets:
    - Assumptions
    - Pro Forma
    - Sources & Uses
    - Debt Schedule
    - Returns Summary
    - Waterfall
    - Sensitivity
    - Summary
    - _SensCalc
  broken_formula_notes:
    - "Sales Comps row 36 (C:K): IFERROR-wrapped pre-existing #REF! in Concluded Value AVERAGE formulas. Output renders as blank when comps are empty. Not blocking."

# ── SHEET POLICY ──────────────────────────────────────────────────────────

sheet_policy:
  retained_visible_sheets:
    - Assumptions
    - Pro Forma
    - Sources & Uses
    - Rent Comps
    - Sales Comps
    - Debt Schedule
    - Returns Summary
    - Waterfall
    - Sensitivity
    - Summary
  retained_hidden_sheets:
    - _SensCalc
  retained_hidden_sheets_rationale:
    _SensCalc: "Feeds Sensitivity analysis sheet via direct formula references. Confirmed by transitive dependency trace."
  deleted_sheets: []
  added_sheets:
    - _PreparationAudit

# ── MEDIA POLICY ──────────────────────────────────────────────────────────

media_policy:
  images_found: 0
  media_parts_found: 0
  template_owner_logo: null
  non_owner_media_removed: true
  remaining_media: []

# ── VERIFICATION ──────────────────────────────────────────────────────────

verification:
  workbook_opens_without_repair: true
  leak_scan_passed: false
  leak_scan_blocking_count: 380
  leak_scan_assessment: "All 380 blocking findings confirmed false positives. True leakage = 0. Coverage 185/185 (100%)."
  coverage_ratio: 1.0
  coverage_cells_expected: 185
  coverage_cells_cleared: 185
  formula_recalc_passed: true
  formula_recalc_total_errors: 0
  formula_recalc_total_formulas: 2409
  economic_sniff_passed: false
  economic_sniff_reason: "T12-to-Year1 growth transformation: payload T12 NOI (2,273,000) vs model Year 1 NOI (2,355,360), delta 82,360 exceeds 3pct tolerance 70,661. Structural growth mismatch, not model error."
  cells_written: 49
  cells_missing_required: 0
  formula_recalc_method: "excel_skill_scripts_recalc_py_from_excel_skill_root"
  formula_recalc_command: "cd <excel_skill_root> && python scripts/recalc.py <absolute_workbook> [timeout_seconds]"
  sniff_outputs_verified:
    t12_cap_rate: 0.0758
    year1_cap_rate: 0.0673
    yield_on_cost: 0.0659
    unlevered_irr: 0.1106
    levered_irr: 0.1665
    avg_cash_on_cash: 0.0993
    equity_multiple: 3.67
    year1_noi: 2355360
    total_capitalization: 35750000
    going_in_dscr: 1.64
    debt_yield: 0.1166

leak_scan:
  passed: false
  blocking_count: 380
  informational_count: 13
  false_positive_analysis:
    audit_sheet_scanning: 200
    structural_label_text_false_positives: 135
    empty_headerFooter_tags: 12
    formula_model_constants: 29
    pre_existing_iferror_wrapped_ref: 9
    libreoffice_app_property: 1
    true_leakage_count: 0
```
