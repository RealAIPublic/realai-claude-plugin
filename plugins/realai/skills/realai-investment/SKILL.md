---
name: realai-investment
description: "Capital-deployment verdict (GO / NO-GO / CONDITIONAL) on a real estate acquisition, value-add play, ground-up development, or conversion. Internally invokes realai-pro-forma to populate the underwriting workbook, then wraps outputs in an analytical writeup (verdict + thesis + comps + market context + risks + bottom line). Returns BOTH the populated .xlsx AND the writeup. Activate on: 'underwrite this deal', 'underwrite this acquisition', 'should I buy', 'screen this deal', 'run the numbers on', 'evaluate this development site', 'is this conversion feasible', 'investment thesis', 'go/no-go on this'. NOT for refi, partner buyouts, or disposition pricing (use realai-valuation). NOT for document verification without a pro forma run (use realai-underwriting Branch B). NOT for assets the user already owns and wants to diagnose (use realai-property-analysis)."
license: Proprietary
---

# RealAI Investment

## Scope and branches

This skill consolidates four kinds of capital-deployment verdict, each with a distinct response shape and benchmark set. Resolve the branch from user intake, then run the matching flow.

| Branch | Source agent | When to run | Verdict shape |
|---|---|---|---|
| A — Screening | Investment Screening | "Quick read." 60–90s triage on a multifamily property. No T12 attached or only basic identification. | Snapshot + standout findings + bottom line. NOT a full GO/NO-GO. |
| B — Acquisitions | Acquisitions Analysis | "Full screen." User has return hurdles, T12/OM, or named target price. Stabilized OR value-add. | GO / NO-GO / CONDITIONAL with pro forma summary, comps, sensitivity. |
| C — Development | Development Feasibility | Ground-up new construction on a named site. | HIGH / MEDIUM / LOW feasibility verdict. |
| D — Conversion | Conversion Evaluation | Adaptive reuse of an existing building (e.g., office-to-MF). | HIGH / MEDIUM / LOW feasibility verdict. |

## Branch resolution

Run a single intake form, then infer the branch from signal:

| Signal | Branch |
|---|---|
| User names existing operating asset + no renovation language | A or B |
| User mentions LOI, target price, return hurdles, T12/OM uploaded, renovation/value-add language | B |
| User describes a "site" + planned product (e.g., "240-unit Class A multifamily wrap") + land cost | C |
| User describes an existing building + a target use that differs from existing use | D |
| Triage vs. full screen ambiguity in A vs. B | Default to B if any pro-forma input was supplied; default to A if identification only |

Confirm the resolved branch + asset class to the user in one line before the intake form (load-bearing because the form's contents depend on the branch). This is the single visible confirmation for the whole skill — sub-resolutions inside a branch (e.g., Stabilized vs. Value-add inside Branch B) stay internal. Follow the router's output discipline: no other interim narration.

## Phase boundary on data retrieval (critical)

Data retrieval is split into two phases. **Respect the phase boundary in branches B, C, and D.** Branch A is light enough that the boundary doesn't apply.

**Phase A** (intake / sufficiency / assumptions confirmation): permitted to resolve property identity from the datamart and parse user-uploaded documents. NOT permitted: rental comps, sale comps, submarket benchmarks, cap rate data, demographics, supply pipeline, web search.

**Phase B** (execution): all remaining retrieval.

This prevents wasteful research on deals that fail sufficiency.

 **Datamart grain and benchmark grounding (all branches).**

 - Cap rate (`caprate_ts`) and commercial conditions (`commercial_market`) exist at market grain only; trailing permits (`permit_ts`) stop at census_place. For any finer subject, pull the parent market (or census_place/county for permits) and label the read accordingly — do not request these at zip, submarket, or neighborhood.
- OpEx benchmarking: the rent/occupancy snapshot already carries headline NOI- and total-OpEx-as-%-of-EGI plus `_msa`/`_natl` indicators — use those for a quick variance flag with no second pull. For a line-item peer split (payroll, R&M, insurance, management, taxes as % of EGI), pull `mf_pnl_benchmarks` at county or market. Neither comes from the subject's own `mf_property_financials`.
- Pin exact catalog topic names when querying (they are opaque tool arguments and cannot be inferred from prose), but read fields and enum values from the catalog at runtime rather than memorizing them — field and enum sets evolve.

**Execute silently from here to the header.** Once intake is resolved, every step below — retrieval, document reconciliation, engine dispatch, math, synthesis — runs inside the thinking block. The user does NOT see "now pulling comps," "running the workbook," "let me calculate," source-class bookkeeping, methodology selection, or any "now I'll…" transition. After the single load-bearing branch-confirmation line in intake, the very next thing that appears in chat is the bold response header. This reminder is repeated at each Research and Calculations section below — that is where the urge to narrate actually strikes, so it is restated where it bites.

---

## Universal calculation pattern — every branch dispatches to realai-pro-forma

This skill is the **analytical narrative layer**. The math authority is the Excel workbook, populated and recalculated by `realai-pro-forma`. Every branch (A, B, C, D) follows the same compute pattern:

1. **Resolve which template + manifest pair to use — consult the template library first.**
   The **template library** is the registry of prepared template + manifest pairs available to this workspace (see "Template library" below). Resolve via this ladder; first match wins:

   - **(a) Best-fit library entry.** An entry whose `asset_class` matches the deal's asset class AND whose `supported_modes` includes the resolved mode AND whose `manifest_status` is `ready` or `ready_with_limitations`. Tiebreak in order: most specific asset_class match → newest `version` → most recently `deposited_at`. This is the customer's own underwriting model, tailored to how they actually underwrite — prefer it.
   - **(b) Bundled generic template** in `realai-pro-forma/assets/`. Its manifest's `supported_modes` covers stabilized acquisition, value-add, development, and conversion for MF. Use when the library is empty/absent or no entry fits.
   - **(c) No fit** (non-MF asset class with no library or bundled coverage, or an unusual mode) → fall back to the Excel skill directly for the calculation phase. The narrative still wraps the workbook outputs.

2. **Build a payload per the manifest.** Use research outputs, comp results, and assumptions resolved in intake. Payload conforms to manifest paths exactly. Source-class every entry (`datamart`, `document_upload`, `user_input`, `template_default`, `ai_estimate`).

3. **Invoke `realai-pro-forma`.** It writes the payload into the workbook, recalculates with the standard recalc helper, reads back mapped outputs (NOI, cap rate, yield on cost, DSCR, debt yield, IRR, equity multiple, multi-year projection, sensitivity outputs).

4. **Read the outputs back into your narrative.** Do NOT recompute these figures in Python or in prose — the workbook is the math authority. Quote outputs directly from the engine's response.

5. **Cross-check the workbook's headline figures (advisory only).** After the engine returns, dispatch `realai-mf-operating-engine` in `cross_check` role with the same base-year inputs and the workbook's headline NOI / EGI / going-in cap. See "MF operating math — authority and cross-check" below. The workbook remains binding; the cross-check only flags a headline divergence as a diligence note.

6. **Wrap in analytical narrative.** Verdict, thesis, comps, market context, risks, bottom line — see each branch's Response section below.

7. **Return BOTH artifacts.** Present the populated `.xlsx` via `mcp__cowork__present_files` AND deliver the analytical writeup in chat. The user gets the workbook to open and the read to act on.

8. **Offer to deposit a newly-used template into the library.** If this run used a template the workspace doesn't yet have registered — the user uploaded a cleaned template + manifest pair for this deal, or just emitted one via `realai-prepare-template` — make the one-line deposit offer described in "Deposit-to-library" below. Never let it block the deliverable.

9. **Final step: brand the writeup.** Call `realai-brand` on any docx deliverable before returning. (The workbook is NOT branded — the xlsx applicator is a stub and must not mutate populated workbooks; see `realai-brand/applicators/xlsx.md`.)

### When to NOT dispatch to the engine

- **Branch A (Investment Screening) intentionally runs lightweight.** The 60–90s triage one-pager doesn't need a full workbook populate; the operating engine in `authority` role supplies the snapshot math (it is the math authority on this no-workbook path — see below). BUT — if the user's Branch A request implicitly needs deeper math (e.g., they ask "should I underwrite this further" + return hurdles + T12 attached), upgrade to Branch B before dispatching to the engine.
- **Manifest fails or returns `needs_review` / `not_compatible`.** Engine refuses to populate. The analytical narrative still runs on whatever data is available, but flag the missing workbook outputs explicitly in the bottom-line section. Recommend `realai-prepare-template` if customer template needs rework.
- **Non-MF asset class with no template coverage.** Hand to the Excel skill directly with the inputs from Step 5 of intake. Narrative pattern unchanged. (The MF operating engine does not apply to non-MF asset classes.)

---

## Template library

The template library is a workspace-local registry of prepared template + manifest pairs, so a customer's own underwriting model is reused across deals without re-uploading it each time. It is the first rung of the resolution ladder in Step 1 above.

**Location.** The directory at the path in the `REALAI_TEMPLATE_LIBRARY` environment variable, if set; otherwise `realai-template-library/` under the workspace/outputs folder (it must live in a user-persistent folder so it survives across sessions — not the ephemeral scratchpad). The directory holds the template + manifest files plus an index file `library_index.json`.

**Index shape.** `library_index.json` is a JSON object with a `version` and an `entries` array. Each entry records:

```json
{
  "id": "acmerealestate-mf-valueadd",
  "label": "Acme RE — MF value-add model",
  "source_org": "Acme Real Estate",
  "asset_class": "multifamily",
  "supported_modes": ["stabilized", "value_add"],
  "manifest_status": "ready",
  "manifest_version": 4,
  "template_path": "templates/acmerealestate-mf-valueadd_cleaned.xlsx",
  "manifest_path": "templates/acmerealestate-mf-valueadd_manifest.md",
  "version": "1.1.0",
  "deposited_at": "2026-06-01T14:22:00Z"
}
```

**Reading the library (resolution).** Read `library_index.json`, filter to entries matching the deal's asset class + resolved mode with usable `manifest_status`, apply the tiebreak (most specific asset_class → newest `version` → newest `deposited_at`), and resolve that entry's `template_path` + `manifest_path`. If the file is absent or the array is empty, skip rung (a) and use the bundled generic (rung b). Never treat a `needs_review` / `not_compatible` entry as a match.

**Do not invent entries.** The library is read at runtime; never assume its contents. A malformed index is treated as empty (fall back to the bundled generic), not repaired inline.

### Deposit-to-library

When a deal run uses a template the workspace doesn't yet have registered, offer to deposit it so future deals reuse it:

- **Triggers.** The user uploaded a cleaned template + manifest pair for this deal, OR they just emitted one via `realai-prepare-template`. (A run that used the bundled generic or an already-registered library entry needs no deposit.)
- **What deposit does.** Copy the template + manifest into the library directory (`templates/` subfolder) and append or update the entry in `library_index.json` — `id`, `label`, `source_org`, `asset_class`, `supported_modes` (read from the manifest), `manifest_status`, `manifest_version`, `version`, `deposited_at`. Re-depositing an existing `id` bumps its `version` rather than creating a duplicate (mirrors `realai-prepare-template`'s versioned re-emission).
- **Guardrails.** Never deposit a manifest whose status is `needs_review` or `not_compatible`. The deposit is a one-line offer (`Add this model to your template library for next time?`) acted on only when the user confirms; it never blocks the deliverable and never gates the writeup. Do not deposit prior-deal data — only the cleaned template + manifest are stored, exactly as `realai-prepare-template` produced them.

---

## MF operating math — authority and cross-check

Two compute authorities exist for multifamily operating figures. **Which one is binding depends on whether Step 1 resolved a workbook.** They never both claim authority over the same number.

- **Template present (ladder rung a or b resolved a workbook).** `realai-pro-forma` is the math authority — its workbook outputs (NOI, EGI, cap, DSCR, debt yield, IRR, equity multiple, projection, sensitivity) are binding and are what you quote. As a guardrail only, dispatch `realai-mf-operating-engine` in `cross_check` role with the same base-year inputs and the workbook's headline NOI / EGI / going-in cap (`workbook_outputs`). It returns a **bounded advisory** variance on those three headline figures only — it does NOT recompute returns, projection, or sensitivity, and it is never binding. If it flags a headline divergence beyond tolerance (NOI / EGI ±2%, cap ±15 bps → `review_recommended: true`), surface it in the bottom-line / risks section as a diligence note ("an independent recompute of NOI differs from the workbook by X% — reconcile the inputs before relying on the model"); do NOT change the workbook figures. If everything is within tolerance, say nothing.

- **No template (ladder rung c, or Branch A screening).** `realai-mf-operating-engine` in `authority` role is the math authority for the MF operating statement, projection, direct-cap, DCF, levered returns, and yield-on-cost. It owns the canonical MF operating-statement contract and implements it via its bundled `scripts/operating.py`. Quote its outputs directly; do not compute these figures in Python or prose yourself. (This applies to MF only — for non-MF asset classes on rung c, hand to the Excel skill directly.)

Never run both as the authority. The workbook's presence selects the binding authority; the engine's `cross_check` role is advisory by construction (it is structurally incapable of returning binding returns or a projection).

---

## Branch A — Investment Screening

### Intake

Single `ask_user` form:
- Property — entity picker (one)
- Documents — file upload (optional): T12, rent roll, OM, or appraisal
- What you want to know — multi-line text (optional)

If documents were uploaded, follow Document Reconciliation protocol — see `references/document_reconciliation.md`.

### Research (parallel)

> _Silent execution: pull and reconcile everything below in the thinking block — no progress narration, no source-by-source play-by-play, no "now I'll…". The next thing in chat is the response header._

- Subject property: NOI, EGI, OpEx, CapEx; rent and occupancy snapshot + 12 month time series; property attributes; ownership/management; sales history.
- Submarket benchmarks: rent by bedroom, occupancy, cap rate context at zip/census place; fall back to county if local data is thin.
- Supply context: only if new supply is a known concern in the market. Directional permit count over T12–T24 is sufficient.
- Rental comps: call comp logic from `references/comps.md` for a comp-validated achievable rent range. Plot subject and comps on a map.

Skip sale comps unless the user specifically asks about pricing. Skip web search unless other tools lack needed context.

### Calculations

Branch A is the lightweight exception to the universal pattern. **No workbook populate for the one-pager** — and because no workbook is in scope, `realai-mf-operating-engine` in `authority` role is the math authority for the snapshot (run it `base_year_only`, and `direct_cap` if a last-sale price supports an implied-cap line). Quote its NOI/EGI/OpEx-ratio/implied-cap outputs directly; do not hand-compute them in prose. State inputs so the user can audit. Round dollars to nearest thousand, percentages to one decimal, cap rates to two decimals.

**Upgrade trigger.** If during Branch A you detect that the user actually wants depth (T12 attached, return hurdles named, explicit ask for a model or projections, or any mention of multi-year cash flow / IRR / DSCR), abort the one-pager and switch to Branch B — which resolves a template via the library, dispatches to the engine, and returns the workbook.

### Response

Open with the response-header convention (router output discipline): a horizontal rule and a bold deliverable header on its own line, then the body. Header text: **`Investment Screening — [Property name]`**.

Lead with verdict; reader spends 60–90 seconds.

1. **Headline** — one sentence capturing the read.
2. **Snapshot at a glance** — compact key-value: units, year built, location, owner/manager, T12 NOI/EGI/OpEx ratio, in-place rent / asking rent / occupancy, most recent sale + $/unit + implied cap rate.
3. **What stands out** — 3–5 bullets. Each pairs observation with implication. Flag only items with material variance from benchmarks.
4. **Market context** — 2–3 sentences on submarket fundamentals (supply pressure, rent trajectory, demand drivers).
5. **Comp positioning** — brief framing + table (Property | Distance | Units | Year Built | Asking Rent | In-Place Rent | Occupancy). Where does subject sit?
6. **Bottom line** — 2–4 sentences: whether performance and basis warrant further diligence; the single most important next question; one or two specific follow-ups.

---

## Branch B — Acquisitions Analysis

### Intake (Phase A only)

**Step 1 — Combined form:**
- Property — entity picker (one)
- Documents — file upload (optional): OM, T12, rent roll, appraisal, broker package
- Mode — radio (optional): Stabilized / Value-add / Not sure
- Opportunity description — multi-line text (optional)
- Return hurdles & deal terms — multi-line text (optional)

**Step 2 — Resolve mode and asset class (internal).** Value-add if description/OM mentions renovation, rehab, capex program, rent lift, unit upgrades, repositioning, lease-up, or operational improvement. Stabilized otherwise. Resolution stays in the thinking block — the branch confirmation line above already gave the user a chance to correct; the mode is reflected implicitly in the gap-fill form that follows.

**Step 3 — Sufficiency check.**

| Mode | Required minimum |
|---|---|
| Stabilized | Property identity, target price OR return hurdle |
| Value-add | Stabilized inputs PLUS renovation scope (cosmetic / classic / heavy / gut) AND renovation budget or $/unit |
| Non-MF (any mode) | Stabilized minimums PLUS in-place rents or rent roll, stabilized occupancy assumption, **WALT and 24-month rollover concentration as % of NOI** |

**Step 4 — Targeted gap-fill** if inputs insufficient. Single form with exactly the missing items. Skip if sufficient.

**Step 5 — Show assumptions (materiality-filtered).**

High-materiality (always surface):
- Entry price / total basis
- Exit cap rate
- Annual rent / income growth
- Financing terms (LTV + rate)— pre-fill from `mortgage_rate_snapshot` (current rates, spreads, LTV by loan program) when the user gives none.
- Value-add only: renovation cost/unit, achieved rent lift, unit turn pace, stabilized occupancy post-reno

Invoke the `realai-forecasting-engine` for baseline assumptions. The engine's contract splits along compounding vs. oscillating metrics — handle each correctly:

- **Rent growth** (family `rent_or_occupancy`) and **expense growth** (family `operating`) → trend mode. Request scenario envelope `[base, upside, downside]`. If user-supplied growth-rate parameters fall outside the returned ±1σ scenario boundary, flag as material underwriting risk.
- **Exit cap rate** (family `capital_markets`) → directional mode. The engine does NOT project a future cap rate value — it returns `band_position` (historical_band min/structural_mean/max, current_level, position_in_band 0–1, position_label rich/mid/cheap) plus the `rate_environment` signal. Your job is to synthesize the exit assumption from those two facts. If user-supplied exit cap falls OUTSIDE the historical band, flag it. If it sits in a "rich" band-position with a stable or tightening rate environment, that's a soft signal that the exit assumption needs justification beyond historical extrapolation.

Do not ask the engine for a base/upside/downside on cap rate — the directional mode is structurally incapable of producing those and will return a warning. Wrap the band position + rate signal in your own narrative judgment about exit cap rate, do not invent a number the engine refuses to produce.

Silent defaults: 94% stabilized occupancy (MF) / 95% industrial / 90% office / 88% retail; $50/unit/month other income (MF); OpEx ratio from area peer benchmark (`mf_pnl_benchmarks`); post-sale property tax reassessed toward entry price at the jurisdiction's assessed-to-price ratio where reassessment-on-sale applies (surface this one when the reset delta is material — it changes stabilized NOI); 2.5% closing costs; 5-year hold.

Present defaults as a markdown table above the form. Emit `ask_user` with only the 4–7 high-materiality fields, pre-filled and source-labeled.

### Research (Phase B)

> _Silent execution: pull and reconcile everything below in the thinking block — no progress narration, no source-by-source play-by-play, no "now I'll…". The next thing in chat is the response header._

**Multifamily:** Property operational data (rent/occupancy snapshot + 12+ months, rent roll, retention, tradeout, T12), submarket rent/occupancy benchmarks, the line-item OpEx peer benchmark (`mf_pnl_benchmarks`, county/market) for the "OpEx vs peers" read, cap rate context (market grain — fall back to parent market), current financing terms (`mortgage_rate_snapshot`), T12 MF permits, demographics, rental comps (`references/comps.md`), sale comps (`references/comps.md`).

- **Reassessment-on-sale exposure (`mf_tax_and_assessment`).** In-place property tax reflects the *seller's* assessed basis; in reassessment-on-sale jurisdictions the tax resets toward the transaction price at close. Pull current assessed value and tax, derive the jurisdiction's effective assessed-to-price relationship (assessed value ÷ implied market value, or the local statutory ratio), apply it to the deal's entry price to estimate post-sale tax, and carry the delta versus in-place tax as an explicit stabilized-expense underwriting line — not a footnote. A deal that pencils on the seller's frozen assessment can fail on the buyer's reset basis. Confirm field names live via `explore_data`.
- **Tenant credit/income quality (`mf_tenant_profile_detail`).** Use as a screening differentiator between otherwise-comparable deals: the tenant base's credit tier mix and income-to-rent posture feed the bad-debt and turnover assumptions that flow into stabilized NOI. A weaker credit/affordability profile argues for higher bad-debt and turn-cost assumptions (structural, tied to the resident base, not operator-driven); a stronger one supports tighter assumptions. Feed the read into the assumptions rather than treating it as color. (This is the same property-grain topic the property-analysis skill uses; there is no `_snapshot` variant at property grain.)

**Non-multifamily:** Property operational data from uploaded documents. Cap rate context at MSA. Demographics where relevant. Web search: lease comps, submarket vacancy/absorption, recent sale comps, supply pipeline, major tenant moves, capital markets context. Replacement cost benchmark via web research.

**All:** Document Reconciliation protocol (`references/document_reconciliation.md`) when conflicts arise. Flag when NOI relies on broker materials without T12 corroboration. For value-add, prioritize comp evidence for *post-renovation* rent levels.

### Calculations

Follow the **universal calculation pattern** above — resolve the template via the library ladder (Step 1), then dispatch to `realai-pro-forma`. The engine handles MF NOI/projection/direct-cap/DCF/levered-returns via the workbook math; the methodology contract is owned by `realai-mf-operating-engine`. For non-MF asset classes the resolved template doesn't cover, fall back to the Excel skill directly.

When the engine ran (a workbook is the authority), dispatch `realai-mf-operating-engine` in `cross_check` role on the workbook's headline NOI/EGI/cap as the advisory guardrail (see "MF operating math — authority and cross-check"). Do NOT compute pro forma math, IRR, equity multiple, DSCR, debt yield, or sensitivity in Python or narrative — those come from the workbook.

### Screening benchmarks (narrative context only)

- **Entry basis vs market cap:** >25 bps above market cap = favorable basis; >25 bps below = above market (requires justification); within 25 bps = market pricing.
- **Value-add renovation yield:** (stabilized NOI − current NOI) / renovation cost. Target 100–200 bps above market cap to justify execution risk.
- **DSCR lender-floor check:** below 1.25x for stabilized → flag as potentially unfundable and report entry-price reduction to clear the floor.

### Internal synthesis (work through; do not output verbatim)

- What is the single most important factor in whether this deal works?
- What kills this deal if it goes wrong?
- Where do data points contradict each other?
- Which assumption, if off by 10%, changes the verdict?
- Go, no-go, or conditional — and what conditions?

### Response (2–3 minute read)

Open with the response-header convention (router output discipline): a horizontal rule and a bold deliverable header on its own line, then the body. Header text: **`Acquisitions Analysis — [Property name]`** (append `(value-add)` when mode is value-add).

1. **Recommendation** — Line 1: **[GO / NO-GO / CONDITIONAL]** — [Property] at $[Price] ($[X]/unit) generates $[NOI] at [X%] entry cap vs [Y%] market cap. Lines 2–3: investment thesis. Lines 4–6: top three risks (each pairs risk with mitigant/watch item). Line 7: what most affects conviction.
2. **What the comps say** — brief framing + comp table (rental for MF; non-MF source-labeled). State where subject sits in the distribution.
3. **How it's operating** — 2–3 bullets. MF: rents vs comps by unit type, occupancy/retention trajectory, OpEx vs peers. Non-MF: lease structure (WAULT, rollover, top-tenant concentration), in-place vs market rent gap, OpEx from T12. Value-add: spread between current and post-renovation comp-supported rents. One chart only if a clear story.
4. **Market context** — 2–4 sentences on submarket. Include supply pipeline if material. Value-add: whether renovation thesis is supported by submarket trajectory.
5. **How it underwrites** — compact pro forma summary table from model output. Stabilized: single column. Value-add: current vs stabilized. Plus renovation summary (budget, $/unit, scope, renovation yield). Then 2–3 interpretive sentences.
6. **Sensitivity** — Conditional only. Name 1–2 variables most sensitive and where they break the deal. Two sentences + optional compact 3-row table or chart.
7. **Bottom line** — 2–3 sentences. Restate verdict. Conditions to upgrade Conditional to Go; for Value-add, achievability of rent lift from comp evidence and highest-ROI scope items. If the cross-check flagged a headline divergence, name the reconciliation as a diligence item here.

No closing recap table. Round aggressively. Max 2–3 focused charts.

---

## Branch C — Development Feasibility

### Intake (Phase A)

**Step 1 — Combined form:**
- Site or address — entity picker (one)
- Planned product — plain text (required): e.g., "240-unit Class A multifamily, 4-story wrap"
- Documents — file upload (optional): site plan, feasibility study, zoning analysis, pro forma draft
- Opportunity description — multi-line text (optional)
- Return hurdles & deal terms — multi-line text (optional)

**Step 2 — Confirm + sufficiency check.** Cannot run without: site resolved, planned product described, land cost assumption, hard cost estimate or benchmark default indication, construction timeline or benchmark default indication.

**Step 3 — Targeted gap-fill** if insufficient.

**Step 4 — Benchmark research (narrow pass).** Pull benchmark ranges for: land cost ($/unit, $/SF, $/buildable SF), hard cost $/SF, stabilized rent/ADR/sale price, lease-up/absorption pace, exit cap rate, OpEx ratio, stabilized occupancy, soft cost % of hard, construction timeline. Use smallest geographic grain available; tag each: range, midpoint, source, confidence.

**Step 5 — Pre-fill + challenge.** Challenge thresholds:
- Land cost: ±25% of comp midpoint, OR land basis >25% of TDC
- Hard cost $/SF: ±20% of benchmark midpoint, OR below benchmark floor (any amount)
- Stabilized rent: ±15% of comp range midpoint (vintage-adjusted)
- Lease-up pace: faster than fastest comparable recent delivery, OR ±40% of typical
- Exit cap rate: ±75 bps of benchmark midpoint
- OpEx ratio: ±5 pp of benchmark midpoint
- Stabilized occupancy: ±3 pp of benchmark midpoint
- Soft cost % of hard: outside 12–28% range
- Construction timeline: ±25% of typical for product type and scale
- Construction loan rate: ±150 bps of current market rate

**Step 6 — Conditional challenge form** if challenges exist. For each: show pre-filled value + source, benchmark range + source, directional implication. Free-text rationale field.

**Step 7 — Show assumptions and confirm.** High-materiality always surfaced. Conditional surface (promote if flagged): entitlement timeline, site work/horizontal cost, development incentive value, impact fees and exactions. Silent defaults match Branch B's plus 5% hard-cost contingency (10% unusual). Two-part presentation (defaults table in message + minimal form).

### Research (Phase B) — three parallel tracks

> _Silent execution: run all three tracks in the thinking block — no progress narration, no track-by-track play-by-play, no "now I'll…". The next thing in chat is the response header._

**Site and constraints:** Zoning, density, height, FAR, parking. Jurisdiction entitlement timeline (by-right vs. conditional). Development incentives (opportunity zone, tax abatements, density bonuses, LIHTC, impact fee waivers). Impact fees and affordable housing requirements. Prioritize uploaded zoning/entitlement memos over web summaries.

**Demand for the product:**
- MF: demographics, rent/occupancy benchmarks, rental comps, cap rate context, supply pipeline (T12 MF permits — **load-bearing for ground-up; flag if pipeline large or recent deliveries still in lease-up**).
- Non-MF: cap rate context at MSA; web search for demand fundamentals, lease comp evidence, supply pipeline.

**Construction cost reasonableness:** Hard cost benchmarks for similar product in geography; current labor and materials trends. Prioritize contractor GMP or detailed cost estimate over web benchmarks.

Document Reconciliation when multiple documents. Broker/developer cost estimates from pitch materials are user-provided context — flag when hard or land cost relies on pitch without architect or contractor pricing.

### Calculations

Follow the **universal calculation pattern** above — resolve the template via the library ladder (Step 1; prefer a customer development-mode library entry), then dispatch to `realai-pro-forma` if the resolved manifest's `supported_modes` includes `development`. The engine produces the development budget + stabilized pro forma + yield on cost + sensitivity. For asset classes the resolved template doesn't cover, fall back to the Excel skill directly. When the engine ran, the `cross_check` guardrail on headline stabilized NOI/EGI applies (cap cross-check only when a stabilized value basis exists). Do NOT compute YoC, IRR, or DSCR in narrative.

### Screening benchmarks

- **Yield on cost vs. market cap:** target 100–150 bps above stabilized market cap; ground-up often needs 125–175 bps. Below 75 bps = generally insufficient.
- **Total cost vs. replacement cost:** ground-up IS replacement cost — if all-in basis is materially above typical replacement cost, pressure-test the cost stack.
- **DSCR lender-floor check:** flag if stabilized DSCR < 1.25x at assumed take-out financing.
- **Land basis vs. residual:** meaningfully high land basis (>20% of TDC for MF) signals over-valuation relative to the rent stack.
- **Lease-up pace:** compare to recent comparable deliveries in submarket.

### Response (2–3 min)

Open with the response-header convention (router output discipline): a horizontal rule and a bold deliverable header on its own line, then the body. Header text: **`Development Feasibility — [Site or address]`**.

1. **Recommendation** — **[FEASIBILITY: HIGH / MEDIUM / LOW]** — Build [product] at [site] at $[Total Cost] ($[X]/unit), generating $[NOI] at [X%] yield on cost vs. [Y%] market cap. Thesis (2 sentences). Top three risks. Line 7: what most affects conviction.
2. **Site & entitlements** — 2–3 narrative bullets on parcel, zoning, as-of-right vs. discretionary, entitlement timeline, incentives or affordability requirements.
3. **Demand & comp positioning** — 2–3 bullets on demand. Comp table. Where projected rents sit; vintage premium explicit.
4. **Market context & supply pipeline** — 2–4 sentences: T12 permit volume, recent deliveries still leasing up, timing of competing supply relative to delivery.
5. **Whether it pencils** — compact development budget + proforma table from model (Land / Hard / Soft / Contingency / Financing / TDC / Stabilized NOI / YoC / Market cap / Development spread). Then 2–3 sentences.
6. **Sensitivity** (Medium only) — name 1–2 most sensitive variables and break-evens.
7. **Bottom line** — feasibility read, critical path items, what would move feasibility up.

---

## Branch D — Conversion Evaluation

### Intake (Phase A)

**Step 1 — Combined form:**
- Property or address — entity picker (one)
- Existing use — plain text (required): e.g., "Class B office, 14 floors"
- Target use — plain text (required): e.g., "market-rate multifamily, ~250 units"
- Documents — file upload (optional): feasibility study, architect's plans, condition report, OM
- Opportunity description — multi-line text (optional)
- Return hurdles & deal terms — multi-line text (optional)

**Step 2 — Confirm + sufficiency.** Cannot run without: property resolved, existing use described with directional size, target use described with directional program, acquisition cost or target hurdle, hard cost estimate or benchmark default.

**Step 3 — Targeted gap-fill** if insufficient.

**Step 4 — Benchmark research.** Pull ranges for: hard cost $/SF for conversion type, stabilized rent/ADR/sale price, exit cap rate, OpEx ratio, stabilized occupancy, soft cost % of hard.

**Step 5 — Pre-fill + challenge.** Challenge thresholds:
- Hard cost $/SF: ±30% of benchmark midpoint, OR below benchmark floor
- Stabilized rent/ADR/sale price: ±15% of comp range midpoint
- Exit cap rate: ±75 bps of benchmark midpoint
- OpEx ratio: ±5 pp of benchmark midpoint
- Stabilized occupancy: ±3 pp of benchmark midpoint
- Soft cost % of hard: outside 15–35% range (broader than Branch C — conversions carry more soft cost)
- Construction loan rate: ±150 bps of current market rate
- Construction timeline: ±50% of typical (broader than Branch C — conversions are harder to time)

**Step 6 — Conditional challenge form.**

**Step 7 — Show assumptions and confirm.** Conditional surface (promote if flagged): demolition/stripout cost, structural retrofit cost, adaptive reuse incentive value, RE tax reassessment. Silent defaults match Branch C plus 10% hard-cost contingency, 2.5% closing costs.

### Research (Phase B) — two parallel tracks

> _Silent execution: run both tracks in the thinking block — no progress narration, no track-by-track play-by-play, no "now I'll…". The next thing in chat is the response header._

**Demand for the target use:**
- MF target: demographics, rent/occupancy benchmarks, rental comps, cap rate context, supply pipeline (flag if pipeline large).
- Non-MF target: cap rate context at MSA; web search for demand, lease/sale comps, supply pipeline.

**Feasibility of the conversion:**
- Web search for existing building condition, prior listings, vacancy history, current owner statements.
- Jurisdiction adaptive reuse policy — zoning by-right paths, incentive programs (tax abatements, density bonuses, fee waivers), historic preservation overlays, affordability requirements.
- Entitlement timelines — recent comparable conversions and how long they took.
- Hard cost benchmarks for similar conversions — office-to-MF has a wide range ($150–$400+/SF depending on building era and MEP condition).
- Prioritize contractor pricing or architect concept plans over web benchmarks.

Document Reconciliation when multiple documents. Broker-stated cost estimates are user-provided context — flag when hard cost relies on broker materials without architect/contractor pricing.

### Calculations

Follow the **universal calculation pattern** above — resolve the template via the library ladder (Step 1; prefer a customer conversion-mode library entry), then dispatch to `realai-pro-forma` if the resolved manifest's `supported_modes` includes `conversion`. The engine produces the development budget + stabilized pro forma + yield on cost + sensitivity. For asset classes the resolved template doesn't cover, fall back to the Excel skill directly. When the engine ran, the `cross_check` guardrail on headline stabilized NOI/EGI applies. Do NOT compute YoC, IRR, or DSCR in narrative.

### Screening benchmarks

- **Yield on cost vs. market cap:** target 100–150 bps above stabilized market cap; conversions with execution risk often need 150+ bps. Below 75 bps generally insufficient.
- **Total cost vs. replacement cost:** if all-in basis approaches new-construction replacement cost for target use, conversion economics are weak — the existing structure should provide a basis advantage.
- **DSCR lender-floor check:** flag if stabilized DSCR < 1.25x.
- **Hard cost reasonableness:** if user-provided hard cost is materially below web benchmarks, flag as key assumption to pressure-test.

### Response (2–3 min)

Open with the response-header convention (router output discipline): a horizontal rule and a bold deliverable header on its own line, then the body. Header text: **`Conversion Evaluation — [Property] ([existing use] → [target use])`**.

When a challenged assumption was confirmed in Step 6, surface in two places: (1) in the assumption disclosure/budget table with the user's rationale; (2) in the recommendation's risk section as a load-bearing assumption to validate.

1. **Recommendation** — **[FEASIBILITY: HIGH / MEDIUM / LOW]** — Convert [Property] from [existing use] to [target use] at $[Total Cost] ($[X]/unit), generating $[NOI] at [X%] YoC vs. [Y%] market cap. Thesis. Top three risks. Conviction note.
2. **Building & site** — 2–3 narrative bullets on existing building size, era, condition, structural/MEP factors. For office-to-MF: floorplate depth, column grid, window line.
3. **Demand & feasibility for the target use** — 2–3 bullets. Comp table. Where projected rents sit.
4. **Market context** — 2–4 sentences on supply pipeline, demand trajectory, jurisdiction's adaptive reuse policy environment.
5. **Whether it pencils** — compact development budget table (Acquisition / Hard / Soft / Contingency / TDC / Stabilized NOI / YoC / Market cap / Development spread). 2–3 sentences.
6. **Sensitivity** (Medium only) — 1–2 most sensitive variables, break-evens.
7. **Bottom line** — feasibility read, critical path items (feasibility study, zoning pre-application, cost validation, demand study), what would move feasibility up or keep it Low.

---

## Voice (all branches)

Reader is a sophisticated institutional investor — fund principal, head of acquisitions, or strategy lead. Lead with the conclusion, then support it. Use figures in service of judgment, not as substitutes for it. When a metric is at parity and doesn't change the story, leave it out. Never restate a figure that already appears in a scorecard table or chart. Section names should sound like an analyst speaking ("What stands out," "What the comps say," "How it underwrites"), not like a methodology doc ("Triangulation," "Convergence").

## When to call out to other skills

- Need a value figure for entry-vs-market basis or refi/buyout/disposition pricing → call `realai-valuation`.
- Need rental or sale comps → use `references/comps.md` (comp logic mirrors what lives canonically in `realai-valuation/references/`).
- Need MF operating-statement math (NOI/EGI/OpEx, projection, direct-cap, DCF, levered returns, yield-on-cost) → invoke `realai-mf-operating-engine`. `authority` role when no workbook is in scope (Branch A screening, or the no-template fallback); `cross_check` role (bounded advisory on headline NOI/EGI/cap) when a `realai-pro-forma` workbook is the authority. Do not compute these inline.
- Need a multi-year projection or DCF → that is the operating engine's `authority` role on the no-template path; on the template path it is the workbook's. The methodology contract is owned by `realai-mf-operating-engine`. Hand non-MF to the Excel skill.
- Need a forecast for rent / expenses → invoke `realai-forecasting-engine` in trend mode. Need a directional read on cap rate → same engine in directional mode (no projection — band position + rate signal only).
- Comparing 5+ deals or markets → also load `methodology/multi-entity.md`.
- Final deliverable formatting → call `realai-brand` as the last step.

## References

- `references/document_reconciliation.md` — Document Reconciliation Protocol (rules for picking document vs. datamart per field).
- `references/comps.md` — MF sale + rental comp methodology (mirrored from `realai-valuation/references/`).
- `realai-mf-operating-engine` — sibling skill; owns the canonical MF operating-statement contract (bundled in the skill as `realai-mf-operating-engine/references/methodology/mf-operating-statement.md` and `.../scripts/operating.py`). The MF operating-statement math authority on the no-template path (`authority` role) and the bounded advisory cross-check on headline NOI/EGI/cap when a workbook is present (`cross_check` role).
- `realai-forecasting-engine` — sibling skill, dispatched for all forward-looking reads (rent / expense growth in trend mode; cap rate in directional mode — no projection).
- `references/methodology/multi-entity.md` — process spine for 5+ entity comparisons.
- Template library — workspace-local registry of prepared template + manifest pairs (`REALAI_TEMPLATE_LIBRARY` env var or `realai-template-library/` under the workspace folder); first rung of the Step 1 resolution ladder, populated by Deposit-to-library.
