# Phase 2 - Remediation

Phase 2 creates the cleaned template. It applies the approved source-of-truth classification while preserving reusable workbook logic. Use the SKILL file as the execution authority.

## Required inputs

Phase 2 must use the Phase 1 outputs:

- `input_intent_classification`;
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

| Runtime source class | Workbook action | Manifest action |
|---|---|---|
| `datamart_required` | Clear value/rows/labels | Map as required datamart input; block if missing |
| `datamart_preferred_user_fallback` | Clear value/rows/labels | Map datamart first, user fallback, no template fallback |
| `user_required` | Clear value/rows/labels | Map as required user input; block if missing |
| `ai_estimate_allowed` | Preserve only if also reusable template default; otherwise clear | Allow AI override/estimate only with provenance |
| `template_default` | Preserve | Protect as default; require provenance for override |
| `derived_formula` | Preserve if valid; repair/remove if broken per formula policy | Fingerprint and protect |
| `do_not_write` | Preserve unless leakage | Exclude from write surfaces |
| `manual_review` | Do not modify until resolved | Mark `needs_review` if unresolved |

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
7. Map the table in the manifest or mark it as a required manual/runtime table.

If the first data row, structural header row, or table boundaries are uncertain, stop for review rather than guessing.

## Unit mix cleanup

Unit mix is always runtime deal data unless explicitly proven to be a generic placeholder.

Required action:

- delete row labels such as Studio, 1BR, 2BR, 3BR, TH, Retail, Garage, etc. when they are prior-deal row entries;
- delete unit counts;
- delete unit square-footage values;
- delete rent values;
- preserve only generic column headers, formulas, formatting, validation, and table footprint;
- manifest source policy must use datamart first/user fallback for existing properties and user-required for development/conversion deals.

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
5. If a retained supported output depends on the removed formula, status cannot be `ready` until the dependency is fixed or the affected mode/output is excluded from supported modes.

Do not structurally redesign economics to repair a formula.

## Formula-embedded hardcodes

Detect formulas with embedded numeric constants that appear deal-specific. Examples include formulas that hardcode units, rentable square footage, costs, rents, purchase price, or debt proceeds.

Default action:

- preserve if clearly a generic formula constant or mathematical constant;
- repair/rewrite only if the constant is clearly a broken reference replacement and a mapped input exists;
- otherwise flag for manual review;
- do not silently preserve deal-specific formula hardcodes as protected logic.

### Arithmetic-only formulas (disguised constants)

A formula whose body contains **no cell or range references** — only numeric literals and the
operators `+ - * / ( )` and whitespace — is not model logic. It is a prior-deal constant typed as arithmetic. Examples: `=168227*2`, `=9245040-46225`, `=59250+98750+167875+98750+71000`.

Because the value begins with `=`, openpyxl and every formula-aware guard treat it as a
protected formula. The consequence is twofold: (a) it survives the value-clear pass and leaks
prior-deal figures, and (b) it blocks the runtime write under the no-overwrite-formula rule, so the cell can never be repopulated.

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

## Post-clean leak scan

After cleanup and before manifest generation, run the post-clean leak scan via `post_clean_leak_scan.py`.

Coverage surfaces (all implemented in the deterministic scan):

- visible sheets and hidden sheets (openpyxl cell walk);
- defined names (broken refs, external refs, deal-string in name);
- formula text including embedded numeric hardcodes (magic-number leakage like `=12000000*0.65` where the constant was a prior loan amount);
- comments and threaded comments (text bodies + author identity + person displayName);
- document properties (creator, lastModifiedBy, title, subject, description, company, manager);
- worksheet headers and footers;
- conditional formatting formulas (broken refs + embedded numeric hardcodes);
- data validation list formulas;
- chart titles and embedded chart text;
- pivot cache definitions (cached field data);
- customXml parts;
- external link parts and external relationships in `xl/_rels/workbook.xml.rels`;
- media relationships (orphan and unapproved `xl/media/*`).

Specifically flag retained:

- property names and addresses (matched via approved `decisions.deal_strings`);
- units, SF, parking, acreage (matched via suspicious-deal-fact-context heuristic — label keyword + numeric value);
- unit mix row labels (broadened pattern catches Studio/Penthouse/PH/Loft/townhome/retail/garage AND alphanumeric plan codes like A1, A1A, B2, C3);
- rents and rent roll rows (deal_string match + suspicious_deal_fact_context);
- in-place rent;
- development budget, hard costs, soft costs;
- loan amounts and capital-stack values (formula-embedded numeric scan catches these even when the source cell was cleared);
- partner/vendor names (deal_string match);
- photos and non-template-owner logos.

The scan emits a structured result with `blocking_count` and `informational_count`. Any blocking finding fails the scan; informational findings (e.g., bare presence of a customXml part, a document property whose value doesn't match a deal string) are reported but do not block readiness on their own. The cleaned workbook should produce zero blocking findings before Phase 3 manifest generation.

The optional `--cross-check` flag delegates a second-opinion pass to the xlsx skill's `workbook_search.py` for the deal strings and broken-formula tokens, surfacing any discrepancies between the scan and the helper. Requires `REALAI_XLSX_SKILL_ROOT` to be set; degrades to `skipped_no_skill_root` otherwise.

If material leakage remains, return to remediation. Do not proceed to final manifest as `ready`.

## Quiet economic check

After cleanup, check whether identified output cells still show meaningful prior-deal results because drivers were missed. If they do, trace likely missed inputs and stop for review.

The quiet check is not the final sniff test. It only catches incomplete clearing before manifest generation.

## Pre-flight gate — decisions.json must contain clear_cells

Before invoking `prepare_clean_template_v2.py`, confirm that `decisions.json` contains a `clear_cells` array populated from `comprehensive_input_inventory.py --emit-decisions`. This is not optional.

The script does:
```python
clear_cells(wb, audit_ws, decisions.get("clear_cells", []))

A missing clear_cells key silently passes an empty list — no cells are cleared, the workbook retains all prior-deal values, and the leak scan will fail with hundreds of findings.

Required sequence:

1. Run comprehensive_input_inventory.py model.xlsx --out input_inventory.json --emit-decisions decisions_clear_cells_draft.json
2. Review decisions_clear_cells_draft.json. Remove any cells that are true reusable defaults into preserved_defaults.json.
3. Re-run with --preserved-defaults preserved_defaults.json until the draft contains only deal facts.
4. Merge decisions_clear_cells_draft.json["clear_cells"] into decisions.json as the "clear_cells" key.
5. Only then call prepare_clean_template_v2.py model.xlsx decisions.json --out cleaned.xlsx.


## Workbook integrity gate

After remediation and post-clean scan, the workbook package must be structurally valid. A workbook that would trigger Excel repair for defined names, drawings, relationships, or workbook XML cannot be marked `ready`. Repair by sanitizing package parts, defined names, and drawing/media relationships; if still unresolved, mark `needs_review` or `unverified_draft` depending on impact.

`prepare_clean_template_v2.py` enforces this gate via three explicit substeps run after the openpyxl save and before result emission:

1. **Excel Table ref reset.** Each `ListObject` (Excel Table) has its `ref` attribute shrunk to the smallest rectangle that contains its header plus any non-empty data row. Without this step, a table whose data rows were cleared retains its prior row count, and downstream structured references (`Tablename[Column]`) average over stale blank rows. The reset is recorded in the audit log as `shrink_table_ref`.

2. **OOXML package surgery.** The cleaned file is round-tripped through the xlsx skill's `office/unpack.py` → surgical edits → `office/pack.py` (which auto-validates with `office/validate.py --auto-repair`). Surgery covers:

   - Deletion of orphan `xl/media/*` parts that no remaining relationship points to (openpyxl saves can leave these behind even after `ws._images` removal).
   - Comment author scrubbing: `xl/comments*.xml`, `xl/threadedComments/*.xml`, and `xl/persons/*.xml` have author identity replaced with "Anonymous".
   - Drop of `customXml/*` parts unless explicitly retained via `decisions.retain_custom_xml` (these frequently carry deal-data caches embedded by Excel add-ins).
   - Optional header/footer strip from worksheet XML (`decisions.strip_headers_footers`).
   - Inline redaction of approved deal strings inside `<t>...</t>` runs in worksheet XML and `xl/sharedStrings.xml`, catching deal-name leakage in header rows that survived cell-level cleanup.
   - Final `office/validate.py --auto-repair` pass on the packed file (defense in depth).

3. **No-op recalc normalization.** A single recalc pass via the xlsx skill's `recalc.py` is run on the cleaned file with no payload writes. LibreOffice's `RecalculateAndSave` macro rewrites the OOXML, normalizing namespace ordering and any minor structural differences openpyxl produces. This means the delivered `{name}_cleaned.xlsx` is byte-identical to what every downstream recalc will produce, eliminating the openpyxl-vs-LibreOffice serialization drift that could cause Excel-repair-on-first-open or subtle differences between the delivered template and the populated workbook.

All three substeps require the xlsx skill root to be discoverable (set `REALAI_XLSX_SKILL_ROOT`). When the env var is unset and the filesystem-walk fallback returns None, each substep emits a `skipped_no_skill_root` status in the result JSON; the cleaned file is still produced, but the integrity gate degrades from preventive to detective and the workflow should mark readiness as `needs_review` until the env var is configured.

CLI flags `--skip-package-surgery` and `--skip-normalization` exist for emergency degraded modes (e.g., when LibreOffice is provably unavailable in the current environment). Using either flag without documented justification disqualifies the workbook from `ready`.

## Output

Produce `{name}_cleaned.xlsx`.

The workbook should:

- be safe to share externally;
- preserve reusable model logic;
- open without Excel repair;
- contain no prior-deal data leakage except explicitly approved reusable defaults;
- contain no photos or non-template-owner logos;
- contain no invalid defined names or unrepairable broken formulas in supported paths.
