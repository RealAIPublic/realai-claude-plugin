---
name: realai-pro-forma
description: "INTERNAL ENGINE — do NOT activate on general underwriting requests. This skill is the workbook-populating engine called BY other skills (realai-investment dispatches here for every branch's pro forma math; realai-underwriting Branch A dispatches here for engine-only output). It should fire as a standalone trigger ONLY when the user has uploaded their own cleaned template + manifest pair AND explicitly asks to populate that specific workbook ('populate this template with my deal,' 'run my manifest with these numbers'). General intent like 'underwrite this deal' goes to realai-investment — which internally invokes this engine and wraps the outputs in an analytical writeup. The Excel model is the sole authority for NOI, cap rate, yield on cost, DSCR, debt yield, IRR, equity multiple, waterfall, multi-year projections, and sensitivity."
license: Proprietary
---

# RealAI Pro Forma (Engine)

## Purpose

Take a cleaned RealAI template and its manifest, populate the template with sourced data for a real opportunity, recalculate the workbook, and deliver the populated file with a short receipt.

The populated workbook is the product. The chat-side narrative is a summary of those results — it confirms what ran, surfaces the headline outputs, and flags gaps. The user can open the file for everything else, and ask follow-up questions if they want a fuller read.

You do not build a new pro forma, infer workbook structure, write to unmapped cells, or calculate model-derived metrics outside the workbook. The Excel model is the sole authority for NOI, cap rate, yield on cost, DSCR, debt yield, IRR, equity multiple, waterfall distributions, multi-year projections, and sensitivity outputs.

## Scope boundary (important for trigger discipline)

This skill is the engine. It fires only when a cleaned `.xlsx` template and a matching manifest are already in scope. Three valid invocation paths:

1. **`realai-underwriting` Branch A** dispatches here when the user provides a template + manifest pair.
2. **`realai-prepare-template`** emits a personalized clone of this skill (with the customer's template + manifest bundled) — that clone fires on the same narrow conditions.
3. **Direct invocation** by a power user who knows they have the right artifacts.

Do NOT fire on bare "underwrite this deal" — that goes to `realai-underwriting`, which decides whether to come back here.

## Required inputs

You already have:

1. A cleaned `.xlsx` template
2. A matching machine-readable manifest (single fenced YAML block with `cells`, `tables`, and `outputs` sections; `manifest_version` 3 or 4). It may also carry an optional `validation_rules` section (plausibility bounds executed in Step 5a); its absence is not a defect.

The manifest must have status `ready` or `ready_with_limitations`. Do not present manifest status to the user. However, stop and return if the template/manifest pair is not usable when:
- Either file is missing
- The manifest is not a fenced YAML block with cells/tables/outputs
- The manifest's status is `needs_review` or `not_compatible`
- The user requested a mode the manifest does not list under `supported_modes`

When stopping, name the specific blocker in one sentence and recommend regenerating through `realai-prepare-template`. Do not try to repair a broken manifest in this workflow.

## Mode selection

Use the manifest's `supported_modes`. If exactly one mode is listed, use it and say so briefly (`The attached manifest supports development; running as a development analysis.`). If multiple modes are listed and the user's intent is ambiguous, ask once.

Required inputs, optional inputs, source priorities, writable fields, required tables, and outputs come from the manifest, not from your training.

## The flow

**Identify → resolve sources → fill remaining gaps → emit payload → run model → deliver file + receipt.**

### 1. Identify the opportunity

One intake step. Emit an `ask_user` form for the property, site, parcel, or location plus anything the user already has. Keep the form light. The free-text paste field is the workhorse.

Intake form always includes:
- Property/site selector (entity picker for existing properties; address/parcel for new sites)
- Free-text paste field: *"Paste any deal information you have — pricing, unit mix, rents, budget, financing, schedule, return targets. I'll parse it, check the datamart for the rest, and only ask follow-ups for items the manifest still requires."*
- File uploads (optional)
- Mode selector if the manifest supports more than one mode
- User notes (optional)

Add structured fields ONLY when the manifest specifically requires a structured input the user is unlikely to paste correctly (e.g. a typed rent roll uploader). Default is paste + parse.

Do not require cell-by-cell data entry. Do not expose workbook cell addresses in intake. Do not ask the user to confirm global policies (preserve formulas, don't overwrite defaults, etc.) — those are your job.

### 2. Resolve sources

For every required input the manifest declares, determine the source.

**When user-uploaded documents are present.** Apply the **Document Reconciliation Protocol** (`references/document_reconciliation.md`) to decide whether the document or the datamart wins for each field. Two workflow-specific rules layer on top:

- **Projection-class fields** that the protocol flags rather than adopts (Rule 3) are surfaced as a conflict in the gap-filling form (Step 3). The user picks which value to use before the payload is emitted. Do not silently write the document's projection value.
- **`source_detail` must record the protocol rule applied** and, for current-operations fields, the document's date — e.g. `"rent roll dated 2026-03-15, Rule 2"`.

**When no user-uploaded documents are present.** Use the manifest's declared source priority. The default ordering is:

1. User's free-text paste, parsed for the field.
2. Datamart, if the manifest permits or prefers it.
3. Approved AI estimate, only if the manifest permits and the value is not a hard deal fact.
4. Ask the user.

This ordering matters. *"Underwrite 1234 Main St for $25M, 5.5 cap exit"* should not trigger a question about unit count — that's a datamart query.

The datamart segments rent and occupancy by bedroom count and exposes total unit count and average unit SF — it has no per-unit-type counts. When the template's unit-mix table is keyed by unit type (bath/SF/renovated tiers, not just bedrooms): if the Document Reconciliation Protocol has already sourced the mix from an uploaded rent roll, use that. Otherwise resolve total count, average SF, and per-bedroom rent/occupancy from the rent-and-occupancy snapshot, and derive per-type counts/SF by aggregating the datamart's latest rent-roll topic (bedroom, bath, and SF per unit) only where its sample coverage supports it; if coverage is thin, treat per-type counts as missing_required rather than estimating. The datamart rent roll is listings-derived, not the operator's.

**In either path.** User free-text paste fills any field the prior sources did not resolve. Approved AI estimates apply only where the manifest permits and the field is not a hard deal fact. The user is asked only for fields that nothing earlier in the chain resolved.

**Property disambiguation.** If the datamart returns multiple property matches for the user's identification, ask the user to disambiguate before resolving any hard deal facts. Do not pick a match for the user.

**Classify and record.** For each manifest input, classify what the resolution produced:
- `resolved_datamart`
- `resolved_document`
- `resolved_user_paste`
- `resolved_ai_estimate`
- `resolved_runtime_skill`
- `preserved_default`
- `missing_required`
- `missing_optional`
- `conflict`

### 3. Fill remaining gaps

After datamart + documents + paste are exhausted, you should have a list of `missing_required` and `conflict` items. Show a brief grouped summary:

| Input group | Status | Source |
|---|---|---|
| Property identity | Resolved | Datamart |
| Unit mix | Partially resolved | Datamart + 2 fields missing |
| Financing terms | Not in datamart | User input needed |
| Exit assumptions | Resolved | Template default + user override |

Then emit ONE follow-up `ask_user` form covering only:
- Required hard facts that nothing has supplied
- Conflicts between sources where the user must decide
- Approval for AI estimates the manifest permits but you'd rather confirm
- Material defaults the user might want to override

Do not re-ask anything that's already resolved. Do not ask for things that are not required and have no harm if blank.

**Strictness rule.** Block on missing required hard facts (price, units, loan amount, unit mix, hard cost budget, etc.). Do not block on missing assumption-class inputs (cap rates, growth rates, vacancy) when the manifest permits AI estimates or template defaults — use them and flag in the receipt.

### 4. Emit the payload

The payload conforms to the manifest exactly. Use manifest paths as payload paths. Do not invent paths. Do not emit Excel cell addresses, sheet names, or row numbers in the payload.

Scalar entry shape:

```json
{
  "capital.entry_price": {
    "value": 25000000,
    "source_class": "user_input",
    "source_detail": "User intake: paste field",
    "confidence": "high"
  }
}
```

Table entry shape — row keys must match the manifest's table column field names, NOT Excel column letters:

```json
{
  "tables": {
    "unit_mix": [
      {
        "unit_type":           {"value": "1BR", "source_class": "datamart", "source_detail": "Property datamart unit mix table", "confidence": "high"},
        "unit_count":          {"value": 120,   "source_class": "datamart", "source_detail": "Property datamart", "confidence": "high"},
        "sf_per_unit":         {"value": 760,   "source_class": "datamart", "source_detail": "Property datamart", "confidence": "high"},
        "monthly_market_rent": {"value": 1850,  "source_class": "user_input", "source_detail": "User intake: paste field", "confidence": "medium"}
      }
    ]
  }
}
```

If the manifest's table column shape is `B: unit_type` (reversed) instead of `unit_type: {column: B}` (correct), stop and route the user back to `realai-prepare-template`. The reversed shape is a manifest defect.

### 5. Run the model

You are the runner. Write the payload values into the workbook, recalculate, and read back the mapped outputs. Apply these rules without exception:

- Write to cells listed in `cells.<key>.writes[].cell` or to the table regions declared in `tables.<key>`.
- After writing all `cells.<key>` entries, enumerate every cell in `allowed_write_surfaces.cells` that was not written in the previous step. For each unwritten cell: sample the workbook to read its row label (A-column or nearest label), attempt to match it against available user-paste or datamart data by label, and write any match that is in the payload or can be derived from it. Apply the same formula-check and source-class rules as declared `cells` entries. Log each write in the source audit as `source_class: user_paste_unlisted` or `source_class: datamart_unlisted`. If no match is found, leave the cell blank and note it as `missing_optional` or `missing_required` per the manifest's limitations block.
- **Never overwrite a formula cell.** If a manifest entry's write target holds a formula, stop and report the mismatch — do not write through it.
- **Never modify defaults whose `write_class` is `do_not_write` or `protected_default`.** User-overridable defaults may be changed only when the manifest permits override AND the payload supplies a sourced override value.
- **Apply transforms exactly as the manifest declares them.** If `dollars_to_model_currency: divide by 1000` is declared on a write, divide. Do not invent transforms; do not skip declared ones.
- **Preserve all other workbook content.** Do not modify formulas, charts, named ranges, validations, hidden sheets, support sheets, conditional formatting, or table structure. Do not add rows or columns unless the manifest's table entry explicitly allows expansion.
- **Read outputs only from `outputs.<key>.cell`.** Do not compute returns or metrics outside the workbook.
- **Recalculate with the standard Excel skill recalc helper.** If recalc fails to execute, stop and report. Do not proceed with stale cached values.
- **Workbook integrity — post-recalc error diff.** Before writing the payload, capture a baseline set of error cells (`#REF!`, `#VALUE!`, `#DIV/0!`, `#NAME?`, etc.) from the post-clearing template — the errors already present before this run. After recalc, diff the error set against that baseline and branch:
  - **Pre-existing errors outside every mapped output's dependency chain** (e.g. an IFERROR-wrapped `#REF!` in a comps sheet the manifest's `outputs` never reads, or a documented `limitations` entry): note them in the receipt's gaps section and proceed. Do not fail the run for errors the template shipped with and that no mapped output depends on.
  - **Any new error introduced by this run, OR any error — new or pre-existing — that sits in the dependency chain of a mapped output cell:** stop and report. A mapped output resting on an error is not a deliverable result. Name the output and the erroring cell.
  If a mapped output cell itself holds an error after recalc, that is the in-chain case — stop; do not paper over it with an estimate.

If any of these fail, stop and produce a one-line technical error naming the specific issue (`payload path tables.unit_mix.row[3].sf_per_unit not in manifest`, `cells.financing.senior.loan_proceeds_total writes to formula cell at Assumptions!F29`, etc.). Do not produce a receipt or narrative when execution fails.

#### 5a. Plausibility checks — execute the manifest's `validation_rules`

Plausibility bounds are declared **in the manifest, not here.** Do not hardcode cell references, expected ranges, or which lines to sanity-check in this skill — a customer's template geometry differs from the bundled one, and a cell address baked into the engine breaks the moment their model puts occupancy somewhere else. The manifest is per-template and already maps every output cell semantically; validation rules live alongside them.

After recalc and the integrity diff pass, execute whatever the manifest declares under `validation_rules` — and nothing more. If the section is absent or empty, skip this step silently (older manifests won't carry it; that is not an error). For each rule:

- Read the value at the rule's `cell` (or the mapped output/semantic role it names).
- Compare against the rule's declared `bounds`.
- If within bounds, record nothing.
- If out of bounds and `severity: advisory` → surface it in the receipt's gaps-and-diligence section as a plausibility flag (e.g. "modeled going-in cap of 3.1% sits below the 4–8% sanity band — confirm entry price and NOI inputs"). Proceed with delivery.
- If out of bounds and `severity: blocking` → stop and report, naming the rule and the observed value. A blocking-rule breach means the populated workbook is not trustworthy enough to hand over.

`validation_rules` schema (each entry):

```yaml
validation_rules:
  - name: opex_ratio_band          # human-readable rule id
    cell: "Assumptions!H60"        # or: output_key / semantic_role the rule tests
    bounds: {min: 0.30, max: 0.60} # numeric bounds; omit a side for one-sided
    severity: advisory             # advisory (flag, proceed) | blocking (stop)
    message: "OpEx ratio outside typical 30–60% of EGI"  # optional override text
```

Bounds and severity are the manifest author's calls, not the engine's. The engine runs the declared rules literally; it does not invent bounds for a template that declares none, and it does not second-guess a rule the manifest set.

#### 5b. Goal-seek — Target-Input solving (only on explicit request)

Run this **only** when the caller explicitly asks to solve for an input that hits a target output (e.g. "what entry price gets me to a 15% levered IRR," "solve for the rent bump that clears a 1.25x DSCR"). It is never automatic.

The protocol is bounded entirely by the manifest — it cannot write anywhere the normal payload couldn't:

1. **Identify the target metric and the solve-for input.** Both must be manifest-mapped: the target must be an `outputs.<key>` (or a mapped semantic role), and the solve-for input must be a writable `cells.<key>` on an approved write surface. If either is unmapped, **refuse with a one-line explanation** ("the model doesn't expose exit cap rate as a writable input in this template") — do not improvise a write to an unmapped cell.
2. **Vary only through the manifest write location.** Each iteration writes the candidate input value via the same approved write path the payload uses — same formula-check, same transform, same protected-default rules. Never poke a formula cell or an unmapped cell to force convergence.
3. **Read the target only from its mapped output cell,** after a full recalc each iteration. No out-of-workbook estimation of the target.
4. **Iterate at most 10 times.** Use a bounded search (bisection or secant) within any range the manifest or caller specifies.
5. **Convergence tolerances:** IRR ±0.10 percentage points; DSCR ±0.01x; equity multiple ±0.01x. (For a target without a listed tolerance, state the one you used.)
6. **On non-convergence within 10 iterations,** stop and report the closest-tested input and the output it produced — do not present an un-converged value as the answer, and do not exceed the iteration cap.

Report the solved input, the achieved target, and the iteration count in the receipt's **Brief read** (this does not add a fourth receipt section — it is one or two sentences inside the existing brief read). If the solve touched a protected default or hit a manifest limitation, say so.

### 6. Deliver the file with a short receipt

Present the populated workbook. The receipt that accompanies it is brief — three sections only:

**Headline outputs** — a small table of the manifest's mapped outputs that calculated. Include only outputs the workbook produced; omit unmapped or errored ones.

| Metric | Value |
|---|---|
| Stabilized NOI | $X |
| Yield on Cost | X% |
| Levered IRR | X% |
| Equity Multiple | X.Xx |
| DSCR | X.Xx |

**Gaps and diligence** — a short list of items that affect confidence in the result. Each item names the gap, why it matters, and what to do next. Do not include generic acquisitions diligence unrelated to this run.

| Gap | Why it matters | Next step |
|---|---|---|
| GMP not finalized | Hard costs drive yield on cost | Obtain signed GMP |
| Rent roll not uploaded | In-place rent support is comp-based | Upload rent roll |

**Brief read** — one to three sentences interpreting what the model output suggests. Name the assumption the result is most sensitive to and the diligence priority. Don't reach for a recommendation unless the outputs and inputs support one. If they do, use one of: `GO`, `NO-GO`, `CONDITIONAL`, `INSUFFICIENT DATA`.

End with a collapsed/expandable **Source audit** section showing each populated input group, its source class, and source detail.

```
<details>
<summary>Source audit</summary>

| Input group | Source class | Detail |
|---|---|---|
| Property facts | datamart | Property datamart |
| Unit mix | datamart + user_fallback | Datamart found 8 of 10 plans; 2 plans from paste |
| Budget | document_upload | Uploaded GMP letter |
| Financing | user_input | User intake |
| Exit assumptions | template_default + user_override | Cap from template; cost of sale from user |

</details>
```

The receipt should not refer to workbook cell locations. The user opens the file for that.

## What this workflow does NOT do

- It does not run generic acquisitions research. Run external research (rental comps, sales comps, demographic, debt market) only when the manifest requires or permits it for a specific input or section.
- It does not write a full investment memo. The receipt is short by design.
- It does not edit the workbook beyond manifest writes. No formula repair, no structural changes, no "I noticed this and fixed it" surprises.
- It does not retry around manifest defects. A bad manifest goes back to `realai-prepare-template`.

## Guardrails

- Do not infer workbook structure.
- Do not write to unmapped cells.
- Do not overwrite formulas.
- Do not modify protected defaults without a manifest-permitted, sourced override.
- Do not calculate model-derived metrics outside the workbook.
- Do not use stale cached values; require successful recalc.
- Do not hardcode plausibility bounds or cell references for sanity-checks — execute the manifest's `validation_rules`, or skip if absent.
- Do not goal-seek unless explicitly asked, and never solve by writing to an unmapped or formula cell; refuse when the target or input isn't manifest-mapped.
- Do not treat the user's paste as a substitute for a datamart query.
- Do not run unsupported analysis modes.
- Do not produce a receipt when model execution failed.

## References

- `assets/manifest.md` — the bundled manifest. Read at runtime; never assume its contents.
- `assets/RealAI_Pro_Forma_template.xlsx` — the bundled template. Do not edit in place.
- `references/document_reconciliation.md` — the Document Reconciliation Protocol.
- `references/comps.md` — instructions for finding multifamily sales comps and rent comps via the RealAI datamart. Read when the manifest or workflow requires comp sourcing.
- `scripts/apply_payload.py` — applies a payload to the template; validates writes.
- `scripts/read_outputs.py` — reads mapped outputs from the recalculated workbook.
