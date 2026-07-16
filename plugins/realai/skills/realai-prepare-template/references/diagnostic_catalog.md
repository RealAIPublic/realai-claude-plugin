# Diagnostic Catalog

Use this catalog during Phase 1. Diagnostics inform readiness and cleanup recommendations. They are not a license to auto-fix formulas or mutate model logic.

## Severity rules

- Critical issues block `ready` and `ready_with_limitations` until resolved, isolated, or explicitly excluded from supported modes.
- Warning issues require judgment and may block readiness when material.
- Info items are recorded but usually do not block preparation.

## Critical

### C.1 Formula/value errors

Detect cached or formula errors such as `#REF!`, `#NAME?`, `#VALUE!`, `#DIV/0!`, and `#N/A`.

Action:

- Critical if the error affects mapped outputs, retained support logic, or core calculation sections.
- Repair only when intent is high-confidence from labels, neighboring formulas, row/column patterns, named ranges, tables, and dependents.
- If intent cannot be determined, remove the broken formula and trace dependents.
- Do not mark `ready` if a supported output depends on an unfixable formula.

### C.2 Circular references / iterative calculation

Detect circular logic from the dependency graph and workbook calculation settings.

Action:

- If intentional and iterative calculation is enabled, record in the manifest.
- If not enabled or unexplained, block readiness.

### C.3 External references and connections

Detect formulas referencing external workbooks and package parts such as external links, Power Query, or connection XML.

Action:

- Block unless the user approves static conversion and cached values are available, or unless the external link is proven irrelevant to supported outputs.
- Remove external links only when retained formulas and outputs do not depend on them.

### C.4 Broken or invalid named ranges

Detect defined names that cannot resolve to existing sheets/ranges, point to `#REF!`, reference external workbooks, or use invalid names.

Action:

- Block if used by retained formulas or mapped outputs.
- Repair only when target is high-confidence.
- Otherwise remove and audit.
- A workbook that triggers Excel repair due to named ranges is not `ready`.

### C.5 Macros/VBA

Detect `.xlsm` or `xl/vbaProject.bin`.

Action:

- Refuse in v1. Ask for a macro-free `.xlsx` copy.

### C.6 Recalculation unavailable or not executed

Detect when formula reevaluation through the Excel skill recalc helper was not attempted, failed, or was replaced by write-only verification.

Action:

- See SKILL.md §recalc for the canonical command and execution rules. The diagnostic catalog does not restate them.
- Status mapping:
  - recalc helper executed and reported `status: "success"` → recalc passed; proceed to economic sniff.
  - recalc helper executed and reported `status: "errors_found"` → recalc executed but produced cell errors. The economic sniff layer decides whether the errors are explained by missing runtime inputs (→ `ready_with_limitations`) or are structural defects (→ `needs_review`).
  - recalc helper failed to execute → `needs_review` with limitation `recalc_execution_failed`.
- Do not inspect the underlying formula engine directly.
- Do not mark production-ready until recalc and economic sniff pass, except for documented `ready_with_limitations` runtime-input cases.

### C.7 Output coverage insufficient

Detect when the manifest has no usable economic outputs for verification.

Action:

- Block production readiness. A template must expose enough outputs to validate the write mapping.

### C.8 Runtime deal facts retained

Detect retained deal-specific facts in the cleaned workbook, including units, unit mix, unit type labels, rentable square footage, in-place rents, rent roll values, parking counts, purchase price, development budget, hard costs, soft costs, loan amounts, and capital-stack values.

Action:

- Block `ready` and return to remediation unless the user explicitly approved the value as a true reusable template default.
- Existing-property facts should be datamart first with user fallback.
- Development/conversion program facts should be user-required unless a reliable datamart source exists.
- A cell inside a detected runtime-input table region cannot be a reusable default. The Phase 2 force-clear must run with `--table-regions table_regions.json`.

### C.9 Manifest unaccounted-value leakage

Detect non-formula numeric values remaining in the cleaned workbook that are NOT accounted for in the manifest as protected defaults. This is the inverse of coverage_verify: where coverage_verify confirms the LLM cleared what it intended to clear, the leakage check confirms everything that REMAINS is something the manifest can defend.

Action:

- `manifest_lint.py --cleaned-workbook` enforces this automatically.
- Block `ready` and `ready_with_limitations` if the leakage check reports any unaccounted value.
- Either clear the leaked cells in Phase 2 or add a manifest entry classifying them as `protected_default`/`do_not_write` with a real rationale.

### C.9b Allowed-write-surfaces / cells asymmetry

Detect cells listed in `allowed_write_surfaces.cells` that have no corresponding `cells.<key>.writes[].cell` entry (forward direction) OR cells listed in `cells.<key>.writes[]` that are absent from `allowed_write_surfaces.cells` (reverse direction).

Action:

- `manifest_lint.py` enforces both directions automatically.
- Forward asymmetry (`unmapped_writable_cells`) is a silent-data-loss defect: the manifest claims a cell is writable but provides no semantic mapping for it, so a runtime value intended for that cell has nowhere to go. Block status to `needs_review`.
- Reverse asymmetry (`allowed_write_surfaces_missing_cells`) is a write-refused defect: the runner will reject the write because it's outside the allowed surface. Block status to `needs_review`.
- Drive both lists from the same source in Phase 3: `cells` is canonical, `allowed_write_surfaces.cells` should be generated as the union of every `writes[].cell` plus any `protected_default` / `do_not_write` cells.

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
- Remove all other media unless user explicitly approves.
- Rebuild or validate drawing relationships.
- A workbook that triggers Excel drawing repair is not `ready`.

### C.12 Unsafe sheet deletion or unresolved support sheets

Detect hidden/very-hidden sheets proposed for deletion without full transitive dependency trace.

Action:

- Block deletion until no retained visible output, input surface, hidden support sheet, defined name, chart, table, validation rule, conditional format, pivot source, or supported mode depends on the sheet.
- If uncertain, retain as a support sheet and clear deal-specific values.

### C.13 Post-clean leak scan failed

Detect a failed `post_clean_leak_scan.py` result.

Action:

- Block `ready` and `ready_with_limitations` until resolved.

### C.14 Script extraction failure

Detect when a required script block is incomplete, missing, or missing its `# END <filename>` sentinel.

Action:

- Stop with status `needs_review` and limitation `script_extraction_failure`.
- Do not recreate the script from memory.

### C.15 Workbook package repair risk

Detect workbooks that trigger or are likely to trigger Excel repair due to invalid defined names, drawing parts, relationships, workbook XML, or orphaned media.

Action:

- Not production-ready until repaired and revalidated.
- Sanitize defined names and drawing/media relationships deterministically.
- If unresolved, mark `needs_review` or worse.

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

### W.3 Convention mismatch

Template conventions differ from RealAI's default payload conventions: currency scale, sign, percentage format, or time axis.

Action: generate explicit transforms when safe. If structural, mark `needs_review` or `not_compatible`.

### W.4 Multiple time axes

The workbook has historical monthly data, annual projections, monthly debt schedules, etc.

Action: record all candidates and select the primary underwriting projection axis with evidence.

### W.5 Formula override cells

A hardcoded cell appears inside a formula-driven projection range.

Action: flag. Do not clear or rewrite unless user approves.

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

Action: ask for review before clearing or mapping. The detection itself is mechanical; only schema interpretation requires LLM/user judgment.

### W.10 Low-confidence mapping

A manifest mapping relies on context rather than a clear label/direct dependency.

Action: include in the confidence summary and mark the manifest `needs_review` if material. Always record `mapping_evidence` (left labels, section header) on the manifest entry.

### W.11 Preserved default ambiguity

A scalar value could be either reusable model policy or stale deal-specific assumption.

Action: classify conservatively as `user_required` unless evidence supports preservation.

### W.12 Formula cache leakage

Formula cells may retain cached prior-deal outputs until recalculation.

Action: clear or refresh caches where supported and require recalc-backed verification.

### W.13 Source policy missing or weak

Mapped cells/tables lack source priority, missing-data behavior, or provenance requirements.

Action: block manifest lint until source policy is complete.

### W.14 Detected table region not mapped

`candidate_mapping.py` flagged a table region (tall or wide) but the manifest contains no `tables.<key>` or `comp_requirements.<key>` entry covering it.

Action: either map the region as a table in the manifest, or map it as a comp requirement (`runtime_skill: rental-comps` or `sales-comps`), or document why it should not be a runtime input. Unmapped table regions are usually a sign of incomplete Phase-3 mapping.

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

Action: preserve only when classified as `template_default` AND the cell is NOT inside a detected table region. Protect from silent downstream mutation.

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
| Candidate inputs | `candidate_mapping.py` emits per-cell label inventory | classify intent and runtime source from labels + section headers |
| Table regions | `candidate_mapping.py` detects mechanically (label col + value col + sum confirmation) | confirm category (unit mix vs budget vs rent roll); approve any region as defaults if appropriate |
| Dependency graph | detect direct and range-based dependencies | interpret business relevance |
| Sheet deletion | compute transitive dependencies | recommend delete/retain/review |
| Unit scale | detect markers and anchors | choose final scale if ambiguous |
| Time axes | list candidates | choose primary projection axis |
| Architecture | extract signals | classify supported modes |
| Errors | count and locate | explain likely business impact |
| Named ranges | detect invalid/broken/external names | decide repair/remove/preserve |
| Media | inventory images and drawings | classify template-owner logos vs leakage |
| Manifest mapping | `cell_candidates.json` provides structured surface | map business concepts with confidence; record evidence |
| Source policy | provide candidates | finalize datamart/user/template/AI source plan |
| Post-clean leak scan | execute deterministically | decide remediation if failed |
| Manifest leakage check | `manifest_lint.py --cleaned-workbook` enforces | review unaccounted values |
| Recalculation/sniff | execute deterministically | explain failures |
