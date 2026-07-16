# Phase 1 — Analysis and Source-of-Truth Classification

Phase 1 inspects the uploaded workbook without modifying it. Its main deliverables are:

1. a **runtime source plan** — what should remain as reusable template logic/defaults, what must be cleared, and where future values should come from;
2. **table_regions.json** — every detected runtime-input table region (force-clear mask used by Phase 2);
3. **cell_candidates.json** — per-input-cell label inventory (structured surface used in Phase 3 for confident mapping).

## Required scripts

Run the relevant deterministic scripts:

1. `initial_triage.py`
2. `extract_surface.py`
3. `build_dependency_graph.py`
4. `detect_conventions.py`
5. `diagnose_workbook.py`
6. `classify_architecture.py`
7. `dependency_trace_report.py`
8. `media_inventory.py`
9. `candidate_mapping.py` *(replaces the older `source_plan_inventory.py`)*

Before running any script, confirm the script block was extracted completely and contains its `# END <filename>` sentinel. If not, stop with `needs_review` and a `script_extraction_failure` limitation; do not reconstruct from memory.

The scripts provide mechanical evidence. The LLM applies real estate judgment, but material decisions are logged with evidence and confidence. The SKILL file controls execution order and readiness definitions.

## Phase 1 objectives

Phase 1 must answer four questions before cleanup:

1. What model architecture and workbook conventions are present?
2. Which cells, tables, formulas, names, media objects, and sheets carry reusable template logic?
3. Which cells, tables, formulas, names, media objects, and sheets carry prior-deal data or stale artifacts?
4. For every future input, should the runtime source be datamart, user, approved AI estimate, preserved template default, or derived formula?

## Required analysis outputs

```yaml
phase1_summary:
  workbook_status: triage_passed | needs_review | not_compatible
  architecture:
    primary: acquisition | value_add | development | conversion | mixed_use | waterfall | unknown
    extensions: []
    confidence: high | medium | low
  conventions:
    currency_scale: "$" | "$000" | "$M" | mixed | unknown
    output_currency_scale: "$" | "$000" | "$M" | mixed | unknown
    expense_sign: positive | negative | mixed | unknown
    iterative_calc_required: true | false | unknown
    time_axis_candidates: []
    primary_projection_axis: {}
  workbook_inventory:
    visible_sheets: []
    hidden_sheets: []
    very_hidden_sheets: []
    tables_detected: []           # from candidate_mapping
    high_confidence_tables: []    # subset with SUM confirmation
    defined_names_summary: {}
    media_summary: {}
    external_link_summary: {}
  runtime_source_classification:
    datamart_required: []
    datamart_preferred_user_fallback: []
    user_required: []
    approved_ai_estimate_allowed: []
    template_defaults: []
    derived_formula: []
    do_not_write: []
  dependency_plan:
    retained_visible_sheets: []
    retained_hidden_support_sheets: []
    proposed_delete_sheets: []
    uncertain_dependency_sheets: []
  media_plan:
    preserve_template_owner_logos: []
    remove_non_owner_logos: []
    remove_photos_or_renderings: []
    review_unknown_media: []
  broken_formula_plan:
    repair_high_confidence: []
    remove_after_dependency_trace: []
    unsupported_mode_candidates: []
    requires_user_review: []
  diagnostics:
    critical: []
    warnings: []
    info: []
  model_judgment_log: []
```

## Runtime source classes

This is the single classification system. The earlier `input_intent_classification` (prior_deal_specific / reusable_defaults / user_controls / data_tables / formula_overrides / dead_or_legacy) is no longer used — runtime source class plus `prep_action` carries all the same semantics.

| Runtime source class | Meaning | Default cleanup action |
|---|---|---|
| `datamart_required` | Must come from datamart; user fallback insufficient | Clear; block future population if missing |
| `datamart_preferred_user_fallback` | Datamart when available; user may supply if missing | Clear; manifest allows user fallback |
| `user_required` | Deal-specific input the user must supply | Clear; block future population if missing |
| `approved_ai_estimate_allowed` | AI may estimate only with explicit provenance and audit | Clear unless also a reusable default |
| `template_default` | Reusable model assumption or policy | Preserve and protect |
| `derived_formula` | Formula-driven model logic | Preserve unless broken and unfixable |
| `do_not_write` | Structural, output, or protected logic | Preserve or clear by type; downstream cannot write |

## Default source-of-truth rules

### Existing properties

Classify these as `datamart_preferred_user_fallback` unless the user requires datamart only:

- property name and address;
- total units;
- rentable square footage;
- unit mix;
- unit type row labels;
- in-place rents;
- rent roll;
- occupancy;
- parking spaces;
- acreage;
- taxes and insurance when property-specific;
- trailing financials;
- operating history;
- existing debt or capital stack when applicable.

Do not allow template fallback for these fields.

### Development and conversion deals

Classify these as `user_required` unless a reliable datamart source is identified:

- unit mix and unit type row labels;
- square footage program;
- parking program;
- development schedule;
- hard cost budget;
- soft cost budget;
- land cost;
- financing terms and capital stack amounts;
- construction loan assumptions;
- lease-up plan.

The construction budget table on a development or conversion template must be marked `required_runtime_input: true` in the manifest. A development model whose budget is not a required runtime input is structurally incoherent.

### Reusable template defaults

These may be `template_default` when evidence supports that they reflect reusable model policy:

- market rent growth;
- expense growth;
- vacancy default;
- credit loss default;
- management fee percentage;
- replacement reserves per unit;
- selling cost percentage;
- exit cap default;
- debt-sizing toggles;
- refinance toggles;
- waterfall toggles;
- scenario selectors.

If uncertain whether a value is a prior-deal fact or a reusable default, classify it as `user_required` (conservative), not `template_default`.

A scalar cell that sits inside a detected table region is never a `template_default`. Tables are runtime input by structure.

## Detected table regions

`candidate_mapping.py` runs two detectors and emits both into `table_regions.json`:

**Tall regions** are single-value-column tables: budgets, T12s, capex schedules. Each region looks like:

```json
{
  "sheet": "Cons. Budget & Sch.",
  "region_kind": "tall",
  "label_col": "E",
  "value_col": "D",
  "first_row": 9,
  "last_row": 73,
  "belong_rows": [9, 10, 11, ...],
  "row_count": 51,
  "has_sum_confirmation": true,
  "aggregator_cell": "D73",
  "confidence": "high"
}
```

**Wide regions** are multi-data-column tables with a row-label column on the side: rent comps, sales comps, unit-mix-by-type matrices. Each region looks like:

```json
{
  "sheet": "Rent Comps",
  "region_kind": "wide",
  "label_col": "B",
  "first_data_col": "D",
  "last_data_col": "K",
  "first_row": 6,
  "last_row": 14,
  "belong_rows": [6, 7, 8, ..., 14],
  "data_col_count": 8,
  "row_count": 9,
  "confidence": "medium"
}
```

The wide detector exists because comp tables are text-heavy. A rent-comp column holds property names, addresses, "City, State" strings, year-built integers, unit counts, and occupancy rates — a mix of text and numeric values. The tall detector requires every belonging row to have a numeric or formula value in the value column and therefore misses comp-style structures. Without the wide detector, a prior deal's comp property names and addresses survive Phase 2 cleanup because the cells were never inside any detected region.

Phase 2 passes the combined file to `comprehensive_input_inventory.py` as `--table-regions`. Cells in any detected region (tall or wide) are force-cleared regardless of preserved-defaults allowlist. The audit log marks each override with `force_cleared_reason: in_detected_table_region_overrides_allowlist`.

For wide regions, the **label column is excluded** from force-clear. Row labels like "Property", "Address", "Sale Price" are structural template scaffolding. Only the rectangle of data cells (first_data_col through last_data_col, across belong_rows) gets cleared.

Tall regions are confidence=high when SUM-confirmed. Wide regions are always confidence=medium — no aggregator pattern fits a heterogeneous-content table — but Phase 2 force-clears either way. A wide region can only be overridden by explicit user approval in the Phase 1 ask_user form.

The LLM may approve specific regions for review (e.g. a region the LLM believes is genuinely structural defaults), but the default action is force-clear.

## Cell candidates for confident Phase-3 mapping

`candidate_mapping.py` also emits `cell_candidates.json` with one entry per non-blank, non-formula cell:

```json
{
  "cell": "Assumptions & Dashboard!F29",
  "value_class": "large_number",
  "left_labels": ["Total Proceeds"],
  "above_labels": [],
  "section_header_above": "$ Amount",
  "in_named_range": null,
  "in_table_region_id": 0
}
```

In Phase 3, the LLM uses this structured surface to assign semantic roles and `payload_path` keys with high confidence. The mapping evidence (left labels + section header) is recorded under each manifest entry's `mapping_evidence` field so the choice is auditable.

The LLM should never map a cell to a semantic role without checking its candidate record. A cell with no label and no section header is low-evidence; in that case ask the user before mapping it.

## Business classification guidance

| Concept | Default class |
|---|---|
| property name, address, offer price, loan amount | `user_required` or `datamart_preferred_user_fallback` per mode |
| rent growth, tax growth, reserves/unit, exit cap default, management fee | `template_default` (only if not in a table region) |
| refi toggle, waterfall toggle, scenario selector | `template_default` |
| rent roll, T12, unit mix, sales comps, capex schedule, construction budget | `user_required` or `datamart_preferred_user_fallback` (table) |
| hardcoded value in an otherwise formula-driven row | `derived_formula` if structural; `user_required` if deal-specific |
| unused scratch assumption | clear after dependency trace |

## Unit mix, rent roll, comp tables, and program-table analysis

For unit mix, rent roll, square footage schedules, parking schedules, development program tables, cost schedules, rent comp tables, and sales comp tables:

- identify headers, first data row, formulas, validation, formatting, and downstream dependents;
- treat row labels as prior-deal data unless they are structural headers;
- plan to delete row labels and row values during cleanup (for wide-region tables, only the data rectangle is force-cleared — row labels in the label column are preserved as structural scaffolding);
- map the table in the manifest so future labels and values can come from datamart, user input, or — for rent and sales comp tables — the runtime comp skills (`sandbox_skills("rental-comps")` and `sandbox_skills("sales-comps")`); see `phase3_manifest.md` for the `comp_requirements` schema.

Tables detected by `candidate_mapping.py` should be cross-referenced with these expected categories. A detected region (tall or wide) that does not match any expected category is flagged for the user.

A rent or sales comp table is recognized by a wide-region detection where the row-label column holds labels like "Property", "Address", "City, State", "Year Built", "Units", "Avg Rent", "Sale Price", "Cap Rate", "Price/Unit". When recognized, Phase 3 must record the table under `comp_requirements` so the runner knows to invoke the appropriate comp skill.

## Sheet dependency analysis

Do not propose deletion of any sheet until a full transitive dependency trace is complete.

A sheet may be proposed for deletion only when all are true:

1. no retained visible output depends on it;
2. no retained input surface depends on it;
3. no retained hidden sheet depends on it;
4. no retained defined name depends on it;
5. no retained chart, table, validation rule, conditional formatting rule, or pivot source depends on it;
6. no supported analysis mode depends on it.

If dependency status is uncertain, retain the sheet as `support_sheet_retained_for_formula_dependencies` and clear deal-specific values according to the runtime source plan.

## Broken formula analysis

For formulas containing `#REF!`, `#NAME?`, broken external references, missing named ranges, or invalid structured references:

1. infer intent from labels, surrounding formulas, formulas above/below, row/column patterns, named ranges, tables, and dependents;
2. propose minimal repair only when confidence is high;
3. if intent cannot be determined, propose removal and dependency trace;
4. if a supported output depends on the unfixable formula, mark `needs_review` or exclude that mode from `supported_modes`.

Do not preserve broken formulas merely because they are formulas.

## Media analysis

Extract and classify media assets as:

- `template_owner_logo`;
- `non_owner_logo`;
- `photo_or_rendering`;
- `chart_or_model_graphic`;
- `unknown`.

Only template-owner logos may remain. Partner, lender, broker, developer, consultant, property, and unknown logos should be removed unless the user explicitly approves them.

## Judgment log

Use a short judgment log when script evidence is not enough:

```yaml
model_judgment_log:
  - decision: runtime_source_for_unit_mix
    script_result: table_detected_high_confidence
    final_result: datamart_preferred_user_fallback_for_existing_property_user_required_for_development
    evidence:
      - "Unit mix table detected at Operating Assumptions B-C, rows 8-26 (sum confirmed)"
      - "Row labels (A1, A1A, etc.) are deal-specific plan codes"
    confidence: high
    requires_user_review: false
```

## Ask-user decision package

End Phase 1 with one of:

- proceed with recommended cleanup;
- proceed after the listed user review items;
- stop because the workbook is not compatible.

When user input is needed, emit a decision-group form:

| Decision | Recommendation | Reason | Options | Default if accepted |
|---|---|---|---|---|
| Existing-property facts | Datamart first, user fallback, no template fallback | Prevents stale deal facts | Accept / datamart only / review fields | Accept |
| Unit mix and row labels | Delete labels and values | Labels are runtime deal data | Accept / review tables | Accept |
| Detected table regions | Force-clear all values; no allowlist override | Tables are runtime input by structure | Accept / mark specific region as defaults / review | Accept |
| Template owner logos | Keep only template-owner logos | Prevents non-owner branding leakage | Accept / keep selected / remove all | Accept |
| Hidden support sheets | Delete only when dependency trace proves safe | Hidden chains may support outputs | Accept / keep all / review | Accept |
| Broken formulas | Repair if high confidence; otherwise remove and trace | Broken logic should not survive | Accept / review formulas / stop | Accept |

Do not include raw prior-deal values in the form.
