# Phase 1 — Analysis and Source-of-Truth Classification

## Contents

- Required scripts (the nine Phase 1 commands)
- Phase 1 objectives
- Required analysis outputs (the `phase1_summary` schema)
- Runtime source classes
- Default source-of-truth rules — existing properties, development/conversion, reusable defaults
- Detected table regions — tall and wide detectors, and the force-clear mask
- Cell candidates — evidence, not interpretation (the mapping boundary)
- Business classification guidance
- Unit mix, rent roll, comp tables, and program-table analysis
- Sheet dependency analysis
- Broken formula analysis
- Media analysis
- Judgment log
- Ask-user decision package

Phase 1 inspects the uploaded workbook without modifying it. Its main deliverables are:

1. a **runtime source plan** — what should remain as reusable template logic/defaults, what must be cleared, and where future values should come from;
2. **table_regions.json** — every detected runtime-input table region, plus every toggle-gated region and toggle control (the force-clear mask used by Phase 2);
3. **cell_candidates.json** — per-input-cell label inventory (a structured evidence surface, emitted and left on disk; this skill does not consume it).

## Required scripts

Run the relevant deterministic scripts:

```bash
python skills/clean-a-template/scripts/initial_triage.py model.xlsx --out triage.json
python skills/clean-a-template/scripts/extract_surface.py model.xlsx --out surface.json
python skills/clean-a-template/scripts/build_dependency_graph.py model.xlsx --surface-json surface.json --out graph.json
python skills/clean-a-template/scripts/detect_conventions.py model.xlsx --out conventions.json
python skills/clean-a-template/scripts/diagnose_workbook.py model.xlsx --out diagnostics.json
python skills/clean-a-template/scripts/classify_architecture.py model.xlsx --out architecture.json
python skills/clean-a-template/scripts/dependency_trace_report.py model.xlsx --out dependency_trace.json
python skills/clean-a-template/scripts/media_inventory.py model.xlsx --out media.json
python skills/clean-a-template/scripts/candidate_mapping.py model.xlsx --out-tables table_regions.json --out-candidates cell_candidates.json
```

Run the bundled files only. If a script is absent from the seeded skill files, stop with `needs_review` and name the missing file; never retype, port, or reconstruct one. See SKILL.md § Execution Mandate.

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
| `datamart_required` | Must come from datamart; user fallback insufficient | Clear |
| `datamart_preferred_user_fallback` | Datamart when available; user may supply if missing | Clear |
| `user_required` | Deal-specific input the user must supply | Clear |
| `approved_ai_estimate_allowed` | AI may estimate only with explicit provenance and audit | Clear unless also a reusable default |
| `template_default` | Reusable model assumption or policy | Preserve and protect |
| `derived_formula` | Formula-driven model logic | Preserve unless broken and unfixable |
| `do_not_write` | Structural, output, or protected logic | Preserve or clear by type; nothing downstream may write here |

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

The construction budget table on a development or conversion template is runtime input by definition. A development model whose budget is treated as a reusable default is structurally incoherent — the whole budget clears.

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

The four toggle/selector entries mean the **control** — the cell the user sets to
`Yes`/`No` or picks a mode from. They do not extend to the block of inputs a
toggle gates. That block is runtime input; see *Toggle-gated regions* below.

If uncertain whether a value is a prior-deal fact or a reusable default, classify it as `user_required` (conservative), not `template_default`.

A scalar cell that sits inside a detected table region is never a `template_default`. Tables are runtime input by structure. Neither is a cell inside a toggle-gated region.

## Detected table regions

`candidate_mapping.py` runs three detectors and emits all of them into `table_regions.json`:

**Tall regions** are single-value-column tables: budgets, T12s, capex schedules. Each region looks like:

```json
{
  "sheet": "Cons. Budget & Sch.",
  "region_kind": "tall",
  "label_col": "E",
  "value_col": "D",
  "first_row": 9,
  "last_row": 73,
  "belong_rows": [9, 10, 11],
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
  "belong_rows": [6, 7, 8, 14],
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

## Toggle-gated regions

**Gated regions** are input blocks a binary mode toggle switches off. They are emitted under their own key, `gated_regions`, plus a `toggle_cells` list — not merged into `regions`, because their shape is a cell list rather than a label/value run and every existing consumer of `regions` assumes the run shape.

```json
{
  "sheet": "Assumptions",
  "region_kind": "gated",
  "toggle_cell": "Assumptions!H33",
  "toggle_label": "Use Staged Inputs",
  "first_row": 36,
  "last_row": 41,
  "gated_cells": ["Assumptions!H37", "Assumptions!I37", "..."],
  "gated_cell_count": 40,
  "evidence": ["binary_list_validation", "explainer_row_quotes_options"],
  "confidence": "high"
}
```

**Why this detector exists.** A toggle reading `No` makes its block look inert. It is not: the block still holds values, and the next person to flip the toggle activates them. In a template handed on from a prior deal, those are the prior deal's numbers, and nothing announces the change.

**What counts as a toggle.** Only **binary on/off** vocabularies — Yes/No, True/False, On/Off, Enabled/Disabled, Include/Exclude, 1/0 — either as an explicit list data-validation or as a bare value in that vocabulary with a label beside it. A multi-way **mode selector** (`Interest Only / IO Then Amortizing / Fully Amortizing`) is deliberately excluded: it picks between branches that are all live, so it creates no inert region, and treating it as a gate would sweep ordinary deal inputs into the mask for no benefit.

**Corroboration.** A toggle emits a gated region only with at least one of:

| Evidence | What it means |
|---|---|
| `binary_list_validation` | the cell carries an explicit two-option list validation |
| `explainer_row_quotes_options` | a row within three of the toggle quotes its own options — `'"No" = uses the single rates above'` |
| `formula_branches_on_toggle` | a formula elsewhere on the sheet branches on the cell — `=IF(C83="Yes",C75*C85,0)` |

Two or more signals give `confidence: high`; one gives `medium`. Phase 2 force-clears either way.

**What is gated, and what is not.** The block runs from the row after the toggle (skipping its explainer rows) to the row before the next section banner. Inside it, only **numeric** non-formula values are gated. Text cells in the block are scaffolding — period headers like `Year 1 … Year 10` — and are left to the ordinary path, as are formulas. The **toggle cell itself is preserved**, in the position the template's author left it.

**Do not reverse this in triage.** Two features of a gated block make preservation feel justified, and the phase2 reference covers both at length: the template documents the region as optional in the rows beside the toggle, and the block is uniformly filled across periods or tiers, which satisfies the `parallel_siblings` evidence rule by construction. `parallel_siblings` is therefore refused inside a gated region; the only escape is `"approved_region_exception": true` after explicit user approval in the ask_user form.

## Cell candidates — evidence, not interpretation

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

The record carries labels and a value **class** — never a value — so it is safe to leave on disk beside the cleaned workbook.

**Boundary.** This skill uses the file for exactly two things: (a) the `in_table_region_id` flag, which corroborates region membership, and (b) label context when deciding whether a scalar is a deal fact or a reusable policy value. It does **not** assign semantic roles, payload paths, or write surfaces to cells, and it records no mapping evidence anywhere. Deciding what a cell *means* is field mapping, which belongs to whatever downstream flow consumes the cleaned template — for RealAI, whichever flow consumes the cleaned template. A calling agent may read this file as one input to its own mapping, and still owes its own per-coordinate verification.

When a cell has no label and no section header, it is low-evidence. Under the clear-by-default rule that is exactly the cell that clears; do not talk yourself into preserving it.

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
- record the table's sheet, header row, first data row, and column footprint in `_PreparationAudit` so a downstream flow can find the surface without re-deriving it.

Tables detected by `candidate_mapping.py` should be cross-referenced with these expected categories. A detected region (tall or wide) that does not match any expected category is flagged for the user.

A rent or sales comp table is recognized by a wide-region detection where the row-label column holds labels like "Property", "Address", "City, State", "Year Built", "Units", "Avg Rent", "Sale Price", "Cap Rate", "Price/Unit". Recognizing one changes nothing about the cleaning action — the data rectangle is force-cleared and the label column preserved, exactly as for any wide region. It is worth noting in the audit because the emptied rectangle is a surface a downstream flow will want to fill from comp data.

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
4. if a retained output depends on the unfixable formula, mark `needs_review` or record the affected mode as one the cleaned template does not support.

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
      - "Row labels are deal-specific plan codes"
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
