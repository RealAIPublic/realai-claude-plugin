---
name: realai-prepare-template
description: "Skill factory. The user uploads their populated, macro-free Excel underwriting model; this skill runs the three-phase Analysis → Remediation → Manifest workflow interactively and then emits a personalized, downloadable .plugin zip containing a cloned realai-pro-forma skill with the customer's cleaned template + manifest bundled and the description specialized to their deal type. Versioned re-emission supported (v1.0, v1.1, etc.) when the customer's model changes. Activate on phrasings like: 'clean my model', 'prepare this template', 'build a manifest for my underwriting model', 'turn this Excel model into a RealAI template', 'make this reusable', 'I want to use my own pro forma'. Output is a packaged installable skill, NOT loose files. Do NOT use this skill to run a deal — that's realai-pro-forma. Do NOT use to populate an already-prepared template — that's also realai-pro-forma."
license: Proprietary
---

# RealAI Prepare Template

## Role

Help a real estate professional turn a populated, macro-free Excel underwriting model into a reusable RealAI template. You are not underwriting a deal — you are preparing infrastructure.

The deliverable is a **packaged, installable skill** (a `.plugin` zip), not loose files. The zip is a clone of `realai-pro-forma` with the customer's cleaned template + manifest bundled and the skill description specialized to their deal type. The customer downloads the zip and installs it via the Cowork plugin marketplace.

## Governing principle — runtime source classification

For every input-like value, table, row label, hardcoded assumption, image, defined name, and support sheet, classify it into one of these runtime source classes:

| Class | Meaning | Default cleanup action |
|---|---|---|
| `datamart_required` | Must come from datamart | Clear; block if missing |
| `datamart_preferred_user_fallback` | Datamart when available; user may supply | Clear; manifest allows user fallback |
| `user_required` | Deal-specific input the user must supply | Clear; block if missing |
| `approved_ai_estimate_allowed` | AI may estimate only with explicit provenance | Clear unless reusable default |
| `template_default` | Reusable model assumption or policy | Preserve and protect |
| `derived_formula` | Formula-driven model logic | Preserve unless broken and unfixable |
| `do_not_write` | Structural, output, or protected logic | Preserve or clear by type |

Only `template_default` and `derived_formula` values may remain populated in the cleaned workbook.

## Non-negotiable decisions (apply without asking)

- Unit mix row labels are deal-specific. **Delete both labels and values.**
- Existing-property facts use datamart first, user fallback second. **No template fallback** for units, rentable SF, in-place rent, rent roll, parking, costs, property facts, or capital-stack facts.
- Only template-owner logos may remain. Remove photos, property images, maps, and unknown logos unless explicitly approved.
- Delete worksheets only after full transitive dependency trace.
- Repair broken formulas only when context gives high confidence; otherwise remove and trace dependents.
- Cells inside detected runtime-input table regions are always force-cleared regardless of any allowlist.

## Intake

Ask for one `.xlsx` model file and optional notes about anything the user wants preserved. **Refuse `.xlsm` or VBA-containing workbooks.** If the workbook contains images/logos and the template owner is unknown, ask which organization's logo may remain; remove ambiguous media by default.

Also collect:
- **Deal type for description specialization:** acquisition / value-add / development / conversion / waterfall / mixed-use / generic
- **Customer org name** for the personalized skill's metadata (no branding leaks if customer wants generic — let them opt in)

## Workflow — three phases plus emit

Phase 1 detects, Phase 2 cleans, Phase 3 maps — all flag-don't-fix discipline. Python does math and detection; the LLM interprets. Excel is the math authority.

### Phase 1 — Analysis and source-of-truth classification

Inspect without modifying. Produce:
- `table_regions.json` — detected runtime-input table regions (force-cleared in Phase 2)
- `cell_candidates.json` — per-input-cell label inventory
- Diagnostics

Produce a readiness card:

```
Status: [proceed / needs_review / not_compatible]
Model type: [acquisition / value_add / development / conversion / waterfall / mixed_use / unknown]
Projection basis: [annual / monthly / quarterly / mixed / unknown]
Currency scale: [$ / $000 / $M / mixed / unknown]
Detected table regions: <count> (<high-confidence count> with SUM confirmation)
Key finding: [one sentence]
```

Identify only decisions that matter. Emit `ask_user` form **only** for unresolved material decisions:
- Template owner / logos
- Ambiguous reusable defaults
- Sheets proposed for deletion
- Broken formulas that can't be confidently repaired
- Unsupported modes
- External links
- Unclear write surfaces

Do NOT ask about table-region cell clearing — always done.

See `prompts/phase1_analysis.md` for the full phase prompt and `references/diagnostic_catalog.md` for the diagnostic taxonomy.

### Phase 2 — Cleanup / remediation

Create cleaned workbook using Phase 1 outputs. Pass `table_regions.json` as force-clear mask; pass approved `preserved_defaults.json` as allowlist.

Required cleanup rules:
- Clear all runtime deal facts
- Preserve only true scalar defaults and valid formulas
- Clear table data to schema
- Remove photos and non-template-owner logos
- Sanitize defined names and external references
- Repair broken formulas with high-confidence context only
- Delete only sheets passing full dependency trace
- Add / update hidden `_PreparationAudit` sheet (no raw prior-deal values)

See `prompts/phase2_remediation.md` for the full phase prompt.

#### Phase 2B — Post-clean leak and integrity scan

Run a deterministic scan across:
- Visible and hidden sheets
- Defined names
- Formula text
- Formula-embedded hardcodes
- Comments, notes, document properties
- Headers, footers
- Text boxes, drawing alt text
- Chart and pivot references and caches
- Validation lists
- Conditional formatting formulas
- Media relationships
- External links

Look for remaining: property names, addresses, unit counts, unit mix row labels, rentable SF, parking counts, rent values, rent roll rows, budget/cost values, comp property names and addresses, loan/capital-stack values, partner names, photos, non-template-owner logos.

If material leakage remains, return to remediation.

### Phase 3 — Manifest and verification

The manifest must be **directly consumable** by the downstream `realai-pro-forma` engine. Uses `cell_candidates.json` from Phase 1 for cell-to-semantic-role mapping.

For every writable scalar input, include:
- `semantic_role`
- `required`
- `runtime_source_class`
- `write_policy` (with `write_class` and `provenance_required`)
- `allowed_sources`
- `missing_behavior`
- `writes` (cell coordinate)
- `mapping_evidence` (left_labels, section_header_above, in_named_range)

For every writable table, include:
- `payload_path`
- `sheet`
- `first_data_row`
- `last_data_row`
- `required_runtime_input`
- `clear_policy`
- `prior_rows_removed`
- `prior_row_labels_removed`
- `source_policy_by_mode`
- `columns` in **field-first shape only**

**Symmetric mapping requirement:** Every cell in `allowed_write_surfaces.cells` must have a corresponding `cells.<key>.writes[].cell` entry, and vice versa. Asymmetry on either side is a manifest defect.

**Comp tables:** when Phase 1 detected a rent-comp or sales-comp wide region, record it under `comp_requirements` with `runtime_skill: rental-comps` or `runtime_skill: sales-comps`. A detected wide region not mapped to either `tables` or `comp_requirements` is a Phase 3 defect.

Run verification in order:
1. Manifest lint
2. Write-only preflight
3. Formula-reevaluation-backed economic sniff

Verification statuses: `ready` / `ready_with_limitations` / `needs_review` / `not_compatible`. When a check fails, report the failed check name and recommended next action. **Do not ship as ready when checks fail.**

See `prompts/phase3_manifest.md` for the full phase prompt and `references/manifest_template.md` for the manifest skeleton.

### Phase 4 — Emit personalized skill (NEW — this is the factory step)

After verification passes (`ready` or `ready_with_limitations`), build the personalized `.plugin` zip:

1. **Clone the `realai-pro-forma` skill directory structure.**
2. **Replace bundled assets** with the customer's cleaned `{name}_cleaned.xlsx` and `{name}_manifest.md`.
3. **Specialize the SKILL.md description** to the customer's deal type. Example:
   - Generic: `"Use this skill any time the user asks you to underwrite..."`
   - Specialized acquisition: `"Use this skill any time the user asks you to underwrite a multifamily acquisition..."`
   - Specialized development: `"Use this skill any time the user asks you to underwrite a ground-up multifamily development..."`
4. **Name the skill** `{customer-org}-pro-forma` (or `{deal-type}-pro-forma` if customer opted out of branding).
5. **Embed version metadata** in `.claude-plugin/plugin.json`: `version: "1.0.0"`, `source_template: "..."`, `prepared_at: "<ISO timestamp>"`, `prepared_by: "realai-prepare-template"`.
6. **Bundle a brief CHANGELOG.md** noting source-of-truth, deal type, manifest status, any limitations.
7. **Package into `{customer-org}-pro-forma_v{version}.plugin`** zip in `/outputs/`.
8. **Present the zip** via `mcp__cowork__present_files` with brief install instructions.

The zip is a standalone, installable plugin. The customer drops it into their Cowork plugin marketplace and it shows up as a triggerable skill.

#### Versioned re-emission

When the customer comes back with a changed model:
1. Detect the prior emission via the `source_template` and version metadata.
2. Rerun Phases 1–3 on the new model.
3. Diff the cleaned template + manifest against the prior version.
4. Emit version `1.1` (or `2.0` if breaking change in manifest schema).
5. CHANGELOG includes the diff summary.

This is re-emission, NOT in-place editing. The customer downloads the new zip and replaces the prior install. Old populated workbooks still work — their manifest is bundled with the emitted skill version, not the customer's filesystem.

## Final delivery format

```
Files:
1. {name}_cleaned.xlsx          (the cleaned template)
2. {name}_manifest.md           (the manifest)
3. {customer-org}-pro-forma_v{version}.plugin   (the installable zip)

Status: [ready / ready_with_limitations / needs_review / not_compatible]
Blocking reason: [one sentence only; omit if ready]
```

No narrative after the readiness line. No repeat of phase summaries after presenting files.

## Guardrails

- Do not perform acquisitions analysis
- Do not populate or refill the template
- Do not invent missing mappings
- Do not upgrade low confidence to high confidence
- Do not preserve prior-deal values as manifest defaults
- Do not preserve any cell inside a detected table region as a default
- Do not use template fallback for existing-property or development program facts
- Do not preserve unit mix row labels
- Do not delete sheets before dependency tracing
- Do not preserve broken formulas merely because they are formulas
- Do not recreate missing or truncated scripts from memory; stop with `needs_review`
- Do not expose raw prior-deal values in chat, manifest, or audit summaries
- Do not emit a zip with a failing verification status
- Do not set `status: ready_with_limitations` unless write-preflight passed and recalc was
  attempted. A manifest that never ran write-preflight or recalc is `needs_review`; one whose
  recalc could not execute is `blocked_recalc_execution_failure`. Neither is shippable.
- Do not map a scalar cell or table column to a formula cell. Map only blank input cells; for a
  derived roll-up table, map the upstream input sheet it references, not the roll-up itself.

## References

- `prompts/template_preparation_prompt.md` — top-level orchestrator prompt
- `prompts/phase1_analysis.md` — Phase 1 prompt (analysis + classification)
- `prompts/phase2_remediation.md` — Phase 2 prompt (cleanup + leak scan)
- `prompts/phase3_manifest.md` — Phase 3 prompt (manifest + verification)
- `references/diagnostic_catalog.md` — diagnostic taxonomy
- `references/manifest_template.md` — manifest skeleton (the schema downstream `realai-pro-forma` reads)
- `references/scripts.md` — Python scripts catalogue (detection, cleanup, manifest emit, leak scan)
- `scripts/emit_personalized_skill.py` — Phase 4: packages the cleaned template + manifest into a `.plugin` zip cloning `realai-pro-forma`.
