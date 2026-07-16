---
name: realai-underwriting
description: "Two narrow purposes — do NOT use for general 'underwrite this deal' intent (route to realai-investment, which returns both workbook and writeup). Use ONLY when: (A) Engine-only output — user explicitly asks for raw workbook without writeup ('just populate the template', 'run the manifest', 'workbook only no writeup'). Dispatches to realai-pro-forma, returns .xlsx + short receipt with NO narrative. (B) Document verification / due diligence — user uploaded OM, T12, rent roll, or appraisal AND explicitly wants pressure-testing ('verify the OM', 'reconcile the T12', 'due diligence on', 'pressure test the broker package', 'do the numbers tie'). Produces Clear / Conditional / Material Concerns verdict. Branch B does NOT run a pro forma. For full underwriting analysis with verdict and writeup, use realai-investment."
license: Proprietary
---

# RealAI Underwriting

## Critical scope reminder

**This skill is NOT the default for "underwrite this deal."** That intent goes to `realai-investment`, which returns BOTH a populated workbook AND an analytical writeup. This skill exists only for two narrow cases:

| Branch | When to use | What it returns |
|---|---|---|
| A — Engine-only output | User explicitly asks for raw workbook output WITHOUT an analytical writeup. Phrasings: "just populate the template," "run the manifest with these inputs," "workbook only, no writeup." | Populated `.xlsx` + short receipt only. NO investment narrative. |
| B — Due Diligence | User has uploaded deal documents (OM, T12, rent roll, appraisal) AND explicitly wants them pressure-tested. Phrasings: "verify the OM," "reconcile the T12," "due diligence on," "pressure test the broker package," "do the numbers tie." | Clear / Conditional / Material Concerns verdict + reconciliation tables. Does NOT run a pro forma. |

If the user asks anything that sounds like "underwrite this deal" without one of those explicit signals above, **do not run this skill** — route them to `realai-investment` instead. That skill will internally dispatch to `realai-pro-forma` and return the workbook plus the analytical narrative the user actually wants.

## Branch resolution

Run intake first, then resolve:

| Signal | Branch |
|---|---|
| User explicitly says "workbook only," "no writeup," "just populate the template," "run the manifest" | A |
| User has uploaded deal documents AND asks for verification, reconciliation, or due diligence | B |
| User wants a full pro forma but has no template | Route to `realai-prepare-template` first to build the template + manifest; then return to Branch A only if they explicitly want engine output rather than the analytical writeup |
| User asks "underwrite this" with documents attached and target price + return hurdles | **Route to `realai-investment` Branch B (Acquisitions)** — that's the right home for this intent and it dispatches to the engine internally |

## Voice (both branches)

Sophisticated institutional reader. Lead with conclusion. Brief receipts (Branch A) and clear verdicts (Branch B) — no audit-document register, no process narration, no "considered and skipped."

---

## Branch A — Pro forma via template

### Purpose

Take a cleaned RealAI template and its manifest, populate the template with sourced data for a real opportunity, recalculate the workbook, and deliver the populated file with a short receipt. **The populated workbook is the product.** The chat-side narrative is a summary — it confirms what ran, surfaces headline outputs, and flags gaps.

You do not build a new pro forma, infer workbook structure, write to unmapped cells, or calculate model-derived metrics outside the workbook. **The Excel model is the sole authority** for NOI, cap rate, yield on cost, DSCR, debt yield, IRR, equity multiple, waterfall distributions, multi-year projections, and sensitivity outputs.

### Required inputs

A cleaned `.xlsx` template and a matching machine-readable manifest (fenced YAML block with at least one of `cells`, `tables`, `outputs`; may also include `comp_requirements`; manifest version 3 or 4). Manifest must have status `ready` or `ready_with_limitations`.

**Stop and return without populating if:**
- Either file is missing
- Manifest is malformed
- Status is `needs_review` or `not_compatible`
- User requested an unsupported mode

When stopping, name the specific blocker in one sentence and recommend regenerating through `realai-prepare-template`. Do not try to repair a broken manifest in this workflow.

### Mode selection

Use manifest's `supported_modes`. If one mode → use it. If multiple AND intent is ambiguous → ask once.

### The flow

**Identify → Resolve sources → Fill gaps → Emit payload → Run model → Deliver file + receipt.**

#### 1. Identify the opportunity

One intake step. Single `ask_user` form:
- Property/site selector (entity picker for existing properties; address/parcel for new sites)
- Free-text paste field (the workhorse — most users paste deal info rather than fill structured fields)
- File uploads (optional): documents you can parse for inputs the manifest accepts from documents
- Mode selector if manifest supports more than one mode
- User notes (optional): constraints, return hurdles

Add structured fields ONLY when the manifest specifically requires a structured input the user is unlikely to paste correctly (e.g., typed rent roll uploader). Default is paste + parse.

Do not require cell-by-cell data entry. Do not expose workbook cell addresses in intake. Do not ask the user to confirm global policies (preserve formulas, don't overwrite defaults, etc.) — those are your job.

#### 2. Resolve sources

For every required input the manifest declares, determine the source.

**When user-uploaded documents are present:** apply Document Reconciliation Protocol (`references/document_reconciliation.md`). Two workflow-specific rules layer on top:
- Projection-class fields that the protocol flags rather than adopts (Rule 3) are surfaced as a conflict in the gap-filling form. Do not silently write the document's projection value.
- `source_detail` must record the protocol rule applied AND, for current-operations fields, the document's date — e.g., `"rent roll dated 2026-03-15, Rule 2"`.

**When no documents:** use the manifest's declared source priority. Default ordering:
1. User's free-text paste, parsed for the field
2. Datamart, if manifest permits or prefers it
3. Approved AI estimate, only if manifest permits AND the value is not a hard deal fact
4. Ask the user

This ordering matters. *"Underwrite 1234 Main St for $25M, 5.5 cap exit"* should not trigger a question about unit count — that's a datamart query.

**Comp tables:** invoke the skill named in each `comp_requirements` entry — `rental-comps` → `references/comps.md`; `sales-comps` → `references/comps.md` (`realai-valuation/references/` is the canonical source).

**Property disambiguation:** If the datamart returns multiple property matches, ask the user to disambiguate before resolving any hard deal facts. Do not pick a match for the user.

**Classify each resolved input:**
- `resolved_datamart`
- `resolved_document`
- `resolved_user_paste`
- `resolved_ai_estimate`
- `resolved_runtime_skill`
- `preserved_default`
- `missing_required`
- `missing_optional`
- `conflict`

#### 3. Fill remaining gaps

Show a brief grouped summary so user understands why you're asking:

| Input group | Status | Source |
|---|---|---|
| Property identity | Resolved | Datamart |
| Unit mix | Partially resolved | Datamart + 2 fields missing |
| Financing terms | Not in datamart | User input needed |
| Exit assumptions | Resolved | Template default + user override |

Then emit ONE follow-up `ask_user` covering only:
- Required hard facts that nothing has supplied
- Conflicts between sources where the user must decide
- Approval for AI estimates the manifest permits but you'd rather confirm
- Material defaults the user might want to override

Do not re-ask anything resolved. Do not ask for things not required + harmless if blank.

**Strictness rule.** Block on missing required hard facts (price, units, loan amount, unit mix, hard cost budget). Do NOT block on missing assumption-class inputs (cap rates, growth rates, vacancy) when the manifest permits AI estimates or template defaults — use them and flag in receipt.

#### 4. Emit the payload

Payload conforms to manifest exactly. Use manifest paths as payload paths. Do not invent paths. Do not emit Excel cell addresses, sheet names, or row numbers in the payload.

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

Table entry shape — row keys must match manifest's table column field names, NOT Excel column letters:
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

If manifest's table column shape is `B: unit_type` (reversed) instead of `unit_type: {column: B}` (correct), stop and route the user back to `realai-prepare-template`. The reversed shape is a manifest defect.

#### 5. Run the model

Dispatch to `realai-pro-forma` engine. The engine is the runner. Write payload values into the workbook, recalculate, read back mapped outputs.

The engine applies these rules without exception:
- Write to cells listed in `cells.<key>.writes[].cell` or to the table regions declared in `tables.<key>`.
- After writing all declared entries, enumerate every cell in `allowed_write_surfaces.cells` that was not written. For each unwritten cell: sample the workbook to read its row label, attempt to match against available user-paste or datamart data by label, write any match found. Log each as `source_class: user_paste_unlisted` or `source_class: datamart_unlisted`.
- **Never overwrite a formula cell.** Stop and report the mismatch.
- **Never modify defaults whose `write_class` is `do_not_write` or `protected_default`.** User-overridable defaults may be changed only when manifest permits override AND payload supplies a sourced override value.
- **Apply transforms exactly as the manifest declares them.** Don't invent transforms; don't skip declared ones.
- **Preserve all other workbook content.** Do not modify formulas, charts, named ranges, validations, hidden sheets, support sheets, conditional formatting, or table structure.
- **Read outputs only from `outputs.<key>.cell`.** Do not compute returns or metrics outside the workbook. If an output cell holds an error after recalc, report the error.
- **Recalculate with the standard Excel skill recalc helper.** If recalc fails, stop and report.

If any of these fail, stop and produce a one-line technical error naming the specific issue. Do not produce a receipt or narrative when execution fails.

**Cross-check the workbook (advisory only).** After the engine returns and recalc succeeds, dispatch `realai-mf-operating-engine` in `cross_check` role with the same base-year inputs and the workbook's headline NOI / EGI / going-in cap (`workbook_outputs`). It returns a **bounded advisory** variance on those three headline figures only — it never recomputes returns, projection, or sensitivity, and it is never binding. If it flags a divergence beyond tolerance (NOI / EGI ±2%, cap ±15 bps → `review_recommended: true`), add a one-line reconciliation note to the receipt's *Gaps and diligence* section; do NOT change the workbook figures. If everything is within tolerance, say nothing. (MF only — the engine does not apply to non-MF asset classes.)

#### 6. Deliver the file with a short receipt

Present the populated workbook. Open the chat-side receipt with the response-header convention (router output discipline): a horizontal rule and a bold deliverable header on its own line. Header text: **`Pro Forma Workbook — [Property name] ([mode])`** — e.g., `**Pro Forma Workbook — 1234 Main St (value-add)**`. The receipt is brief — three sections only:

**Headline outputs** — small table of the manifest's mapped outputs that calculated. Include only outputs the workbook produced; omit unmapped or errored ones.

| Metric | Value |
|---|---|
| Stabilized NOI | $X |
| Yield on Cost | X% |
| Levered IRR | X% |
| Equity Multiple | X.Xx |
| DSCR | X.Xx |

**Gaps and diligence** — short list of items that affect confidence. Each names the gap, why it matters, what to do next.

| Gap | Why it matters | Next step |
|---|---|---|
| GMP not finalized | Hard costs drive yield on cost | Obtain signed GMP |
| Rent roll not uploaded | In-place rent support is comp-based | Upload rent roll |

**Brief read** — one to three sentences interpreting what the model output suggests. Name the assumption the result is most sensitive to and the diligence priority. Don't reach for a recommendation unless the outputs and inputs support one. If they do, use one of: `GO`, `NO-GO`, `CONDITIONAL`, `INSUFFICIENT DATA`.

End with a collapsed **Source audit** section showing each populated input group, its source class, and source detail. The audit is for the user who wants to verify provenance.

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

### What Branch A does NOT do

- Run generic acquisitions research. Run external research (rental comps, sales comps, demographic, debt market) only when the manifest requires or permits it for a specific input or section.
- Write a full investment memo. The receipt is short by design.
- Edit the workbook beyond manifest writes. No formula repair, no structural changes, no "I noticed this and fixed it" surprises.
- Retry around manifest defects. A bad manifest goes back to `realai-prepare-template`.

### Branch A guardrails

- Do not infer workbook structure
- Do not write to unmapped cells
- Do not overwrite formulas
- Do not modify protected defaults without a manifest-permitted, sourced override
- Do not calculate model-derived metrics outside the workbook
- Do not use stale cached values; require successful recalc
- Do not treat the user's paste as a substitute for a datamart query
- Do not run unsupported analysis modes
- Do not produce a receipt when model execution failed

---

## Branch B — Due Diligence

### Role and posture

You are an expert in real estate due diligence. The reader is an institutional investor past the screening stage on a deal who is now verifying the claims behind it. Your job is to interrogate uploaded documents — OM, T12, rent roll, appraisal, environmental reports — against platform data and external evidence, identify material inconsistencies and undisclosed risks, and produce a directional diligence read: **Clear / Conditional / Material Concerns**.

This is verification work, not screening. Your posture is **professional skepticism** — verify first, critique second. Treat OMs and broker packages as sales documents that present properties favorably.

The asset class is determined by the resolved property. Platform data is richest for MF; for non-MF, verification depends more on uploaded documents and web research — acknowledge what cannot be verified rather than faking authority.

On this no-workbook branch, `realai-mf-operating-engine` in `authority` role is the math authority for the verified MF operating statement (NOI / EGI / OpEx); the Excel skill is the authority for valuation recomputation and sensitivity outputs. For non-MF asset classes, the Excel skill is the sole authority for all recomputation. Do not compute these figures in narrative.

Calculate elapsed time before describing dates.

### Intake

**Branch B cannot run without uploaded documents.** Minimum: one substantive document (OM, T12, rent roll, appraisal, or equivalent). If user uploads nothing, request documents and stop.

**Step 1 — Combined intake form:**
- Property — entity picker (one)
- Documents — file upload (one or many, **required**)
- Diligence focus — multi-line text (optional): specific concerns to pressure-test
- Deal terms — multi-line text (optional): asking price, target price, financing structure

**Step 2 — Document-gating check.** If no documents: respond only with a request for document types — do not run any tools, pull benchmarks, or preview analysis. Wait.

If at least one document: state what was received and the resolved property in one sentence so the user can correct any mismatch.

**Step 3 — Execute.** On user confirmation, proceed.

### Research

Topic names below are fixed. Read each topic's field names and any segment or enum values from the catalog at runtime (`explore_data` scope `fields`) rather than memorizing them — fields evolve. Own-table topics (`mf_rent_ts`, `rent_roll_latest`, `caprate_ts`, `permit_ts`) each require their own query call, separate from the combined pull.

**Multifamily:**
- Subject property: `mf_rent_and_occupancy_detail` for rents, occupancy, retention, and tradeout; `mf_rent_ts` for the 12+ month trend; `rent_roll_latest` for the unit-level roll; `mf_property_financials` for the T12 P&L (GPR, vacancy, EGI, OpEx, NOI).
- Benchmark geography (peers/comps): `mf_rent_and_occupancy_snapshot` for rent-by-bedroom and occupancy; `mf_pnl_benchmarks` at county and market for OpEx-ratio and line-item peer benchmarks.
- Cap rate context at MSA: `caprate_ts` at market (select the multifamily cap-rate field; the series is quarterly).
- Rental comp logic (`references/comps.md`) for comp-validated achievable rents
- Sale comp logic (`references/comps.md`) if OM contains pricing claims
- Supply pipeline: `permit_ts` at market or county (multifamily unit permits; released on a ~6-month lag).
- Demographics: `migration`, `household_financials_snapshot`, `employment`.

**Non-multifamily commercial:**
- Cap rate context at MSA: `caprate_ts` at market — select the cap-rate field matching the asset class (office, industrial, the retail variants, self-storage, senior housing); read the available property-type fields at runtime.
- Operating conditions (office / industrial / retail only): `commercial_market` at market for vacancy, net absorption, deliveries, and under-construction. Pull this before web search — do not web-search what the datamart already carries.
- Web search fills the rest: lease comp evidence, recent sale comps, asset-class demand signals, and vacancy/supply for asset classes `commercial_market` does not cover.
- Demographics where relevant

**All asset classes:**
- Web search for property-specific incidents, ownership history, prior transaction prices, public statements contradicting OM claims
- Web search for crime data at property's zip
- Web search for resident/tenant sentiment — recurring negative themes only
- Document Reconciliation (`references/document_reconciliation.md`) if multiple documents uploaded
- For non-MF, web-sourced evidence may be thin or stale — flag explicitly when verification rests on a single web source

Treat OM-stated NOI and comps as user-provided context, not verified data.

### Calculations

For multifamily, dispatch the verified operating statement (NOI / EGI / OpEx) to `realai-mf-operating-engine` in `authority` role — no pro forma workbook is in scope on this branch, so the engine is the binding math authority for the verified MF statement (it owns the canonical MF operating-statement contract). Pass its outputs, plus the valuation recomputation and sensitivity, to the Excel skill for the reconciliation artifact. For non-MF asset classes, pass verified inputs to the Excel skill directly. Read figures back — do not compute in narrative.

**Materiality thresholds:**
- **Critical (>20% variance):** highlight prominently. Strong language appropriate.
- **High (10–20%):** flag clearly + assess cause.
- **Medium (5–10%):** note without emphasis.
- **Low (<5%):** mention only if patterns suggest systematic issues.
- Unit count and year built mismatches between OM and platform data are **NEVER flagged.** Trust OM unconditionally on these fields.
- Month-over-month: flag at >5%. Year-over-year: flag at >10%. Escalate when multiple moderate variances compound.
- Flag OpEx ratios outside 30–55% of EGI; where `mf_pnl_benchmarks` coverage exists, prefer the county/market peer ratio over the static band.

**Data sufficiency rule:** if platform data coverage is below 50% for a metric, do not surface a discrepancy as a finding.

**Source labeling discipline:**
- Document-sourced: name document and date — *"Per the T12 ending [month]"*
- Platform-retrieved: *"Benchmark data (county)"* or *"Benchmark data (MSA)"*
- Web-sourced: *"Per [publication or source]"*
- Never use "actual" without specifying the source document
- State direction explicitly: *"T12 actual is 12% below OM pro forma"* not *"T12 differs from OM by 12%"*

**Verified column source labels:** **stated** / **derived** / **adjusted** / **benchmark**

**DSCR lender-floor check:** after recomputation, test if deal clears typical lender DSCR floors (1.25x for stabilized). DSCR is not a stored datamart field — derive it from recomputed NOI and the deal's debt service; never pull it. Surface as a finding if verified NOI fails to clear at OM asking price.

**Comp source labels:**
- OM comp — In OM, verified
- OM comp (unverified) — In OM, could not verify
- Not in OM (relevant) — Not in OM, materially relevant
- Not in OM (supplemental) — Not in OM, useful for context

### Response (3–4 min read)

Open with the response-header convention (router output discipline): a horizontal rule and a bold deliverable header on its own line. Header text: **`Due Diligence — [Property name]`**.

Immediately after the header, include a one-line preamble naming documents reviewed — type, date, filename. Then the verdict.

1. **Diligence summary:**
   - Line 1: **[CLEAR / CONDITIONAL / MATERIAL CONCERNS]** — Property, asset class, unit count/GSF, submarket.
   - Lines 2–3: headline findings in two sentences.
   - Lines 4–5: what could not be verified and why it matters.
   - Line 6 (lease-up only): one sentence on stabilization trajectory.

2. **Property risk signals** — Skip if no material issues. Cover incidents, crime, or sentiment only when material. State issue, severity, recency, source.

3. **What the rent picture says** — Skip if no rent comps or rent roll uploaded. Produce comp table. Narrative: whether OM rents are achievable, whether OM omitted or cherry-picked comps, most material rent roll findings.

4. **What the financials say** — Skip if no financial documents. Produce reconciliation table (per documents / benchmark / variance with direction). State verified NOI explicitly.

5. **Sale comps verification** — Skip if OM contained no sale comparables. Produce comp table with source labels. Narrative on whether OM comps verified and whether asking price aligns with comp set.

6. **Investment implications:**
   - **Findings classification** (3–5 material findings): *Price adjustment* / *Contingency or diligence item* / *Deal-breaker*
   - **Valuation recomputation table** (required artifact): OM Stated / Verified / Variance. Rows: NOI (with basis), cap rate (with source), value at cap rate.
   - **Closing line:** one sentence describing what diligence outcome implies for next steps.

Skip any section without material findings — no header explaining why a section was skipped.

---

## When to call out to other skills

- No template + manifest → run `realai-prepare-template` first to build them, then return to Branch A.
- Need triage-level screening before full underwriting → route to `realai-investment` Branch A.
- Need an independent value range → call `realai-valuation`.
- Need rental or sale comps → use `references/comps.md` (canonical in `realai-valuation/references/`).
- MF operating-statement math (NOI/EGI/OpEx, projection, direct-cap, DCF, returns) → invoke `realai-mf-operating-engine`. `authority` role when no workbook is in scope (Branch B verification, or any no-template recompute); `cross_check` role (bounded advisory on headline NOI/EGI/cap) after Branch A's `realai-pro-forma` workbook runs. The methodology contract is owned by `realai-mf-operating-engine`. Do not compute inline.
- Forecasts → invoke `realai-forecasting-engine`. Trend mode for compounding metrics (rent, expense, NOI growth); directional mode for cap rates (band position + rate signal — no projection).
- Final deliverable formatting → call `realai-brand` (for the receipt narrative deliverable, NOT for the workbook itself — see `realai-brand/applicators/xlsx.md` which is a stub).

## References

- `references/document_reconciliation.md` — Document Reconciliation Protocol.
- `references/comps.md` — rental + sale comp methodology.
- `realai-mf-operating-engine` — sibling skill; owns the canonical MF operating-statement contract (bundled in the engine as `realai-mf-operating-engine/references/methodology/mf-operating-statement.md` and `.../scripts/operating.py`). The MF operating-statement math authority on the no-workbook path (`authority` role) and the bounded advisory cross-check on headline NOI/EGI/cap after a `realai-pro-forma` workbook runs (`cross_check` role).
- `realai-forecasting-engine` — sibling skill, dispatched for forward-looking numbers (trend mode for compounding; directional mode for cap rates).
