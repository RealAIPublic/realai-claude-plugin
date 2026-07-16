---
name: realai-property-analysis
description: "Characterize and diagnose a held real estate asset (typically multifamily). Use when the user owns or operates the asset and wants to understand how it's running, who the tenants are, whether expenses are reasonable, how much rent upside exists in the rent roll, or whether the property manager is doing a good job. Four diagnostic frames: Tenant Analysis, Operating Efficiency, Mark-to-Market Rent, Property Manager Assessment. Activate on phrasings like: 'how is this property performing', 'who lives here', 'are we overpaying for management', 'is the operator doing a good job', 'what's our rent upside', 'why is OpEx so high', 'mark to market', 'tenant quality', 'retention is weak', 'should we replace the property manager'. Do NOT use this skill for buy/sell verdicts (route to realai-investment or realai-valuation), for document verification (route to realai-underwriting), or for market-level reads (route to realai-market-analysis)."
license: Proprietary
---

# RealAI Property Analysis

## Scope and frames

This skill diagnoses a HELD asset across four frames. Each frame produces a different read; none produces a buy verdict.

| Frame | Source agent | What it tells you |
|---|---|---|
| Tenant | Tenant Analysis | Whether the tenant base, their spending behavior, and the operating performance agree |
| Operating | Operating Efficiency Analysis | Where OpEx diverges from peer-built benchmarks, split between operator-controllable and structural drivers; implied NOI lift |
| Mark-to-Market | Mark to Market Rent Analysis | The rent growth already locked in by the existing roll, waiting to be captured through turnover |
| Manager | Property Manager Assessment | Whether the operator's decisions are creating or destroying value vs. a competent operator with the same asset; retain/improve/replace verdict |

## Frame resolution

Run a single intake form. Infer the frame from signal:

| Signal | Frame |
|---|---|
| "Who lives here," "tenant quality," "credit profile," demographic-vs-operations alignment | Tenant |
| "Why is OpEx so high," "are we overspending," "where can we save," expense efficiency, line-item attribution | Operating |
| "Rent upside," "loss-to-lease," "achievable rents," renovation lift, turnover capture | Mark-to-Market |
| "Manager performance," "should we replace," fee rate, attribution of variance to operator | Manager |

If multiple frames are implied, ask the user which they want first and offer the others as follow-ups — running all four at once produces noise.

## Voice

Sophisticated institutional reader — owner, asset manager, fund principal. Lead with conclusion, then support it. Brief is not the same as cold; complete sentences, professional confidence. Numbers earn their place in narrative when they carry a judgment; otherwise they live in the table.

> **Execute silently from here to the header.** Once intake is answered, all retrieval, attribution, and sandbox math run inside the thinking block — no "now pulling," no line-by-line or comp-by-comp play-by-play, no "now I'll…". The next thing the user sees in chat is the bold response header. Repeated at each Research section below, where the urge to narrate strikes.

---

## Data layer (retrieval calibration)

All four frames query the `property_mfr` entity. Pin the canonical topic names given in each frame as the query targets, but do **not** hardcode field names: field and enum names evolve, so read them live with `explore_data` (scope `fields`) for each flagged topic before quoting a  metric, and prefer built-in benchmark/trend siblings (`_natl_indicator`, `_msa_indicator`, `_natl_pctile`, `_t3/_t6/_t12_pct_chg`, `_r_squared`, `_trend_strength`) over recomputing.

 Own-table topics — `rent_roll_latest`, `mf_rent_roll_ts`, the `mf_rent_ts*` family, and  `top_consumer_behaviors` — must each be a **separate** query call; `rent_roll_latest` / `mf_rent_roll_ts` / `mf_rent_ts*` require a `period_type` filter and `top_consumer_behaviors`  requires an `id` filter. These required filters are not fixed strings to memorize: read them live from `required_filters` in the `explore_data` scope `"topics"` response for each topic before every `query_data` call, and take the `period_type` value (case-sensitive) from `required_filters[].values` — a missing or mis-cased filter returns a 400. Geographic benchmark pulls (`household_financials_snapshot`,  `credit_profile_snapshot`, `cultural_identity`, `demographic_basics`, `migration`) resolve at the benchmark geography, not at the property. 

**Affordability ratio orientation (applies to every frame that touches affordability).** The datamart's `rent_to_income_ratio` field is **rent ÷ income**. Income-to-rent is its inverse: `mf_tenant_profile_detail` median income ÷ (in-place rent × 12) = `1 / rent_to_income_ratio`. The 2.5x income-to-rent floor this skill uses corresponds to `rent_to_income_ratio` above ~0.40. Confirm the field's direction live via `explore_data` scope `"fields"` before quoting either form — do not assume orientation from the field name.

## Frame 1 — Tenant Analysis

### Intake

- Property — entity picker (one)
- Documents — file upload (optional): rent roll, T12, delinquency report, maintenance log, or OM
- What you want to know — multi-line text (optional)

Helper: *"Upload a rent roll, delinquency report, or maintenance log if you want me to tie tenant quality directly to operating outcomes."* Document Reconciliation (`references/document_reconciliation.md`) if documents are present.

### Research (parallel)

> _Silent execution: run the parallel pulls and math in the thinking block — no progress narration, no source-by-source play-by-play. The next thing in chat is the response header._

**Who the tenants are (subject, property grain):** `mf_tenant_profile_detail` resolves tenant income, net worth and wealth tiers, the full credit panel with trend history, household demographics, and sample confidence in a single pull — these are not separate topics at the property grain. Add `education` (tenant attainment) and `top_consumer_behaviors` (property grain). Cultural identity is not reliably exposed at the property grain; source it from the geographic `cultural_identity` topic only if the question needs it. "Demographic samples" is not a topic — the tenant demographics live inside the profile pull.

**What the property is doing:** Rent & Occupancy (asking vs. in-place, occupancy, retention, tradeouts, leasing velocity), Property Financials (NOI, EGI, OpEx by category), Rent Roll if available.

**Submarket benchmarks (geography grain):** `household_financials_snapshot`, `credit_profile_snapshot`, and `top_consumer_behaviors` at the benchmark geography. Where the comparison is national/MSA, lean on the snapshots' built-in `_natl_indicator` / `_msa_indicator` fields rather than a second pull.

**Optional (transience):** the tenant-level `mobility_score` inside `mf_tenant_profile_detail` is the property-grain read on relocation likelihood (lower score = more likely to move); add geographic `migration` and `demographic_basics` only if area churn, not tenant churn, is the question.

Distribution shape often matters more than median. If credit data sample is INSUFFICIENT, say so plainly; do not present low-confidence figures as definitive.

### Calculations (Python sandbox, single call)

| Metric | Definition |
|---|---|
| Income variance | Subject median income vs submarket median, % delta |
| Income distribution shape | Subject vs submarket at 25th, 50th, 75th percentiles |
| Wealth variance | Subject median net worth tier and liquid resources vs submarket |
| Credit tier mix | Share in subprime / near-prime / prime / super-prime, vs submarket |
| Rent-to-income | Median in-place rent × 12 / median tenant income |
| DTI summary | Median tenant DTI vs submarket |
| Retention variance | Subject retention vs submarket benchmark |
| Tradeout direction | Net new-lease tradeout %, recent vs trailing |
| Delinquency rate | Bad debt as % of GPR, or unit-level from documents if available |
| Tenant consumer indices | Top 5–10 categories where tenants over- or under-index, vs national AND vs submarket |

Round dollars to nearest thousand, percentages to one decimal, FICO to whole numbers, indices to one decimal.

**Consumer behavior:**
- The dual comparison on consumer behavior matters. *Vs national* tells you what's distinctive about this tenant base in absolute terms. *Vs benchmark* tells you whether tenants behave differently than the surrounding area — which is where the more interesting findings tend to live. Both *Vs benchmark* and *Vs national* are very important. 
- Treat top_consumer_behaviors as persona material, not a list of facts — aggregate signals into a sentence or two about how people in this building actually live. When consumer behavior is the primary focus, go deeper: synthesize into a typed persona covering what this renter values, how they spend, and what that means for amenity expectations, lease renewal likelihood, and rent sensitivity. If the property's persona diverges sharply from its benchmark, that's signal — it's drawing a different resident type than its immediate competition.
- **Consumer behavior translation examples:** salad over fries → health-conscious; fine dining → affluence, experience-seeking; financial advisor → planning-oriented, risk-averse; takeout → time-poor, convenience-driven.
  
### Response (~90 seconds to read)

Open with the response-header convention (router output discipline): a horizontal rule and a bold deliverable header on its own line, then the body. Header text: **`Tenant Analysis — [Property name]`**.

1. **Headline** — one sentence. Aligned-positive vs. disconnected (where the analysis focuses).
2. **Tenant profile vs submarket** — compact comparison table (3–5 differentiating rows): Median household income, Bottom quartile income, Median net worth, Credit tier mix (prime+), Median DTI, Rent-to-income. "Read" column shows direction. 1–2 short narrative paragraphs.
3. **Lifestyle & spending signal** — compact behavior table (3–5 rows, most diagnostic categories): Category | Tenant behavior (vs national) | Submarket behavior (vs national) | Signal. Signal column carries the analytical weight. 1–2 paragraphs; if spending contradicts the financial profile, surface it prominently.
4. **How the property is performing** — 3–4 narrative bullets. Possible angles: rent levels/growth, retention/tradeouts, delinquency/bad debt, maintenance/OpEx. Select a chart (bar or line) on the most indicative metric.
5. **What the picture says together** — 2–3 sentences stating plainly whether snapshot, behavior, and operating data line up. If they don't, where the disconnect is and what would resolve it.
6. **Opportunities and trade-offs** — 2–3 insights pairing action with expected impact and trade-off. Tenant base / Operations / Underwriting. Stay directional.
7. **Bottom line** — 2–3 sentences. Asset or liability to the business plan? Most important question? Most valuable follow-up?

---

## Frame 2 — Operating Efficiency

### Intake

- Property — entity picker (one)
- Documents — file upload (optional): T12, OM, budget, recent appraisal, insurance binder
- What you want to know — multi-line text (optional)

Helper: *"Upload a T12 or budget if you have it — that lets me read line items directly rather than relying on benchmark averages."* Document Reconciliation if documents present.

### Research

> _Silent execution: run the pulls and math in the thinking block — no progress narration, no line-by-line play-by-play. The next thing in chat is the response header._

**Subject — cost structure and physical context:** Full operating P&L (every expense line as $ and % of EGI, plus NOI, EGI, GPR); vintage, unit count, building count/style, construction materials, roof type, exterior wall material, flood zone, acreage.

**Subject — tax and ownership:** Tax burden, assessed value (total + per unit), land/improvement split, ownership and management identity.

**Subject — revenue and tenant context:** Occupancy, retention, projected annual unit turnovers, leasing velocity. Tenant financial health: credit indicators, debt burden trend, income relative to in-place rent. If unavailable at property level, note the gap.

**Peer benchmark construction — two tiers:**
1. **First-line:** `mf_pnl_benchmarks` at county grain (fallback: market) — pre-aggregated opex/income lines as % of EGI. `mf_pnl_benchmarks` is available only at market, county, and property_mfr grains. Always pull it; it is cheap and load-bearing.
2. **Refinement:** construct a peer set from `property_mfr` — same county, vintage ±10 years, unit count 50–200% of subject, same building style. Pull `mf_property_financials` (the `mf_pnl_*_pct_of_egi` lines) and `mf_property_attributes` per peer in one batched call. Compute median and 75th percentile per line. Report peer-set size.

Use tier 2 as the quoted benchmark when ≥5 peers carry financials; otherwise quote tier 1 and say so explicitly. When both tiers exist and disagree materially, flag the divergence — that is itself a finding, not noise to reconcile away. (Confirm the `mf_pnl_*_pct_of_egi` field names live via `explore_data` scope `"fields"` before quoting; topic names above are stable, field names may evolve.)

**Named checks — retrieve, do not merely assert.** Each of the three checks below requires a data pull:
- **Tax appeal:** pull `mf_tax_and_assessment` (tax amount, tax per unit, tax as % of EGI, total/per-unit/land/improvement assessed value, tax year). Trigger when tax exceeds peer median by 100+ bps of EGI → compare assessed value/unit against implied market value/unit (NOI ÷ market cap range) and size annual savings directionally.
- **Management fee rate:** compute fees ÷ gross potential rent against unit-count bands (<100 units: 5–8%; 100–300: 4–5%; 300+: 3–4%). Flag only above the band.
- **Insurance structural:** cross-reference `fema_flood_zone`, roof type/vintage, exterior wall material, and year built from `mf_property_attributes`. Two or more structural factors present → variance is explained, not a lever; zero present on a material gap → flag an insurance-market RFP.

**Optional:** If the tax-appeal check triggers, retrieve recent sale prices per unit to pressure-test whether the assessed value/unit is supportable against actual market transactions. Web search if a market-level event (post-storm insurance reset, jurisdiction-wide reassessment) may be driving a finding.

Skip amenity data, rental comps, sale comps beyond tax check, broad demographic data.

### Calculations (Python sandbox)

Round: dollars to nearest thousand, percentages to one decimal, $/unit whole dollars, $/SF two decimals.

**Base operating statement.** Source the base-year MF operating statement (NOI / EGI / OpEx) from `realai-mf-operating-engine` in `authority` role (no workbook is in scope here) so this frame draws the same NOI as every other RealAI viewpoint for the same inputs. Compute the frame-specific diagnostics below — peer-benchmark gaps, controllable vs. structural splits, implied NOI lift — on top of that statement in the sandbox. The skill (engine) produces the statement only; it does not do benchmarking or diagnostics.

| Metric | Definition |
|---|---|
| Total OpEx ratio | Total OpEx / EGI |
| OpEx $/unit | Total OpEx / unit count |
| OpEx $/SF | Total OpEx / total rentable SF |
| Line-item ratios | Each major expense line as % of EGI |
| Line-item variance vs. peer | Delta from peer median in bps and dollars |
| Operator-controllable gap | Variance dollars on payroll, R&M, advertising, G&A, management fees — **net of any tenant-driven portion** (see Tenant credit linkage; tenant-driven cost is structural and never counts here) |
| Structural cost gap | Variance dollars on insurance, utilities, taxes |
| Implied NOI lift | NOI if controllable lines closed to peer-median |
| CapEx run rate | CapEx as % of EGI and $/unit (vs. ~$300/unit stabilized; $400–500/unit pre-1980) |
| Income-to-rent ratio | Renter median income / (in-place rent × 12) = `1 / rent_to_income_ratio`. Flag if below 2.5x. Confirm ratio orientation live (data-layer note) |
| Management fee rate | Management fees as a share of EGI (the basis the norm bands assume), vs. unit-count-adjusted norms — computing on GPR understates the rate against an EGI-based norm and can hide a genuine lever. |
| Margin trajectory | OpEx-ratio trend over 12–24 months — computable **only from uploaded documents**. The datamart P&L is single-period; never impute a trend from it. |

**Three additional checks** (data pulls specified in Research above — here are the calc-time triggers):

- **Management fee rate check:** Under 100 units → 5–8% typical; 100–300 → 4–5%; 300+ → 3–4%. Fees ÷ gross potential rent; flag as lever only if the rate exceeds the band's upper bound.
- **Tax appeal check:** If tax burden (from `mf_tax_and_assessment`) exceeds peer median by 100+ bps as share of EGI, compare assessed value/unit against implied market value/unit (NOI ÷ market cap range). Flag appeal + directional savings estimate if assessed value materially exceeds implied value.
- **Insurance structural check:** From `mf_property_attributes` — `fema_flood_zone`, roof type/vintage, exterior wall material, year built. 2+ structural factors present → variance explained, not a lever. Zero present on a material gap → flag insurance-market RFP as a genuine near-term action.

**Tenant credit linkage.** There is no standalone bad-debt field in the datamart — tenant-credit cost surfaces indirectly across operating lines. When average tenant FICO is sub-620, connect that structural pressure to:
- `mf_pnl_general_administrative` (eviction, legal, and collections cost),
- `mf_pnl_repairs_and_maintenance` (turn prep — cross-reference `retention_proj_annual_unit_turnovers` for turn frequency), and
- `mf_pnl_advertising_and_marketing` (re-leasing frequency).

Size the aggregate tenant-driven cost as the NOI-margin gap versus peers **after structural lines are set aside** — not by summing raw line variances. Use `num_collection_count_l12_mos_t12_pct_chg`, `num_trades_delinquent_ltd_t12_pct_chg`, and the FICO tier distribution as upstream signals of collection pressure (flag a deteriorating trend as forward risk even when the current P&L looks clean). Confirm these field names live via `explore_data` scope `"fields"`. **Never assign tenant-driven cost to the operator-controllable gap** — it is structural, tied to the resident base, not to management performance.

Income-to-rent below 2.5x (equivalently `rent_to_income_ratio` above ~0.40 — see the affordability-orientation note in the data layer) is a structural driver of higher turnover: estimate incremental turn cost as `retention_proj_annual_unit_turnovers` × $1,500–$3,000/unit and compare to peer R&M.

### Response

Open with the response-header convention (router output discipline): a horizontal rule and a bold deliverable header on its own line, then the body. Header text: **`Operating Efficiency Analysis — [Property name]`**.

**Output budget:** one table, three charts max — line-item variance chart, single most-material driver chart, scenario waterfall at end.

**Headline** — one sentence variant:
- Operator-controllable: "The property is running ~4 pts heavier on OpEx than peer vintage, with most of the gap in payroll and R&M — a roughly $400K margin opportunity that's largely operator-controllable, before touching structural cost lines."
- Structural pressure: "Total OpEx ratio reads elevated against peers, but nearly all of the gap sits in insurance and utilities — structurally explained by flood zone exposure and pre-1985 construction — and the operator looks well within range on the lines they actually control."
- Tenant-driven: "Expenses look manageable on controllable lines, but the tenant credit profile is structurally elevating collection losses and turn costs, and that pressure is likely to increase before it eases."
- Tight ship: "Operating efficiency is already running ahead of peer expectations across controllable lines — the NOI story here will need to come from revenue, not cost."

**Cost structure at a glance** — comparison table (max 5 rows, total OpEx then material variance lines). Peer set named below table. 1–2 short paragraphs framing overall cost structure and splitting the gap between operator-controllable and structural. Line-item variance chart: horizontal bar, distinguishing controllable from structural, max 5 lines.

**Where the gaps are** — 2–3 narrative bullets, each focused on one material line item. Angles: Payroll, R&M, Insurance, Utilities, Management fees, Bad debt/collection losses, G&A and advertising.

**What's driving it** — 2–3 sentences explaining the pattern (operator, structural, tenant-quality, or combination). Name any recent change.

**Levers and trade-offs** — 2–3 bullets. Each names a specific action, sizes directional impact (from sandbox), states the trade-off. Operator-side / Structural-side / Underwriting categories.

**Bottom line** — 2–3 sentences: investor takeaway, single most important question, most valuable follow-up. If levers identified material opportunities, follow with a scenario impact waterfall.

---

## Frame 3 — Mark-to-Market Rent

### Intake

- Property — entity picker (one)
- Documents — file upload (optional): rent roll, T12, or OM
- Value-add context — radio: None / Light renovation planned / Heavy renovation planned / Already in progress
- Notes — multi-line text (optional)

Document Reconciliation if documents present.

### Research (parallel)

> _Silent execution: run the parallel pulls and math in the thinking block — no progress narration, no comp-by-comp play-by-play. The next thing in chat is the response header._

**Subject:** latest rent roll from from `rent_roll_latest`(unit-level asking rent, in-place rent, days on market, tradeouts), rent + occupancy time series (12–24 months), property attributes, ownership/management.

**Rent benchmarks:** submarket rent levels by bedroom + beds/baths combination. Time series rent at zip or census place over 12–24 months. Occupancy + tradeout benchmarks vs subject.

**Concession environment:** web search — concession trends in submarket and at property, leasing velocity benchmarks.

Call rental comp logic (`references/comps.md`) to validate currently achievable asking rents at the property's quality level. Comp-validated rent is the benchmark for "true" market rent — published asking on the subject may be stale or aspirational. If renovations planned, consider comps with upgraded finish/amenities.

Skip sale comps and demographic data unless notes specifically require.

### Calculations (Python sandbox, single call)

| Metric | Definition |
|---|---|
| Loss-to-lease | (Asking rent − In-place rent) / Asking rent, weighted by unit count |
| Comp-validated upside | (Comp-validated market rent − In-place rent) / Comp-validated market rent |
| Annualized rent upside | (Market rent − In-place rent) × 12 × occupied units |
| NOI impact at full capture | Annualized rent upside × (1 − typical OpEx pass-through) |
| Lease expiration profile | From an uploaded rent roll, Share of units expiring in next 0–6 / 6–12 / 12+ months |

The lease expiration profile drives the *capture timeline* — even a large gap is slow to realize if leases are long-dated. Round: dollars to nearest dollar (unit-level), nearest thousand (property-level NOI), percentages to one decimal.

For phased pro formas, unit turn schedules, or full underwriting, hand off to `realai-underwriting`.

### Response

Open with the response-header convention (router output discipline): a horizontal rule and a bold deliverable header on its own line, then the body. Header text: **`Mark-to-Market Rent Analysis — [Property name]`**.

Lead with size AND realism of the opportunity. Reader wants two numbers fast: *how much* and *how soon*.

1. **Headline** — magnitude + quality. Example: *"~7% loss-to-lease across the roll translates to ~$340K of annualized rent upside, with roughly 60% capturable in the next 12 months given the lease expiration profile."*
2. **Mark-to-market summary** — compact key-value: total units / occupied, weighted avg in-place / asking / comp-validated market rent, loss-to-lease % and comp-validated upside %, annualized $ upside + NOI impact at full capture, share of units rolling in 12 months.
3. **Where the upside lives** — break gap down by unit type. Bar chart: in-place, asking, comp-validated side-by-side per unit type. Then 3–5 bullets: which units carry most absolute vs. percentage upside (often different); whether gap is consistent or concentrated (concentration signals stale pricing or mispriced renovated units); any unit types where in-place exceeds asking (market softening).
4. **Capture realism** — separates from naive loss-to-lease:
   - Lease expiration timing: share capturable in next 6 / 12 / 18 months
   - Tradeout history: are recent new leases closing the gap, or signing at in-place?
   - Concession environment: if submarket offers concessions, headline asking overstates true achievable
   - Renovation gating (if applicable): distinguish lift from renovation vs. mark-to-market alone — do not double-count
5. **Risks to the thesis** — 3–5 short bullets pairing risk with what-to-watch.
6. **Bottom line** — 2–4 sentences: defensible mark-to-market number to underwrite (net of capture friction); single biggest factor determining realization; one or two recommended follow-ups.

---

## Frame 4 — Property Manager Assessment

### Intake

- Property — entity picker (one)
- Documents — file upload (optional): rent roll, T12, management agreement
- What you want to know — multi-line text (optional)

Document Reconciliation if documents present — most common conflict: management fee rate (agreement vs. implied T12 rate).

### Research (parallel)

> _Silent execution: run the parallel pulls, attribution, and math in the thinking block — no progress narration, no metric-by-metric play-by-play. The next thing in chat is the response header._

**Subject operations:** occupancy (current + trailing), in-place/asking rents by bedroom type, leasing velocity, retention/renewal rates, NOI, EGI, total OpEx + key lines (payroll, R&M, advertising, G&A, management fees), CapEx run rate, vintage, unit count, building style.

**Tenant profile:** credit score trend, income-to-rent ratio, debt burden trend.

**Peer benchmark — two tiers (same construction as Operating Efficiency):**
1. **First-line:** `mf_pnl_benchmarks` at county (fallback: market) — pre-aggregated opex/income lines as % of EGI. Available at market, county, and property_mfr grains only. Always pull.
2. **Refinement:** peer set from `property_mfr` — same county, ±10 yrs vintage, 50–200% of subject unit count, same building style — pulling `mf_property_financials` (`mf_pnl_*_pct_of_egi`), `mf_rent_and_occupancy_snapshot`, and `mf_property_attributes` in one batched call for the occupancy, rent-per-SF, and 75th-percentile reads tier 1 does not carry. Compute median and 75th percentile; report peer-set size.

Quote tier 2 when ≥5 peers carry financials; otherwise quote tier 1 and say so. Where both exist and disagree materially, flag it.



**Submarket context:** rent growth, occupancy trend, supply pipeline.

**Manager profile:** how many properties, what geographies, whether their other assets show similar operational patterns, fee structure, realistic local alternatives.

**Tenant reviews:** Google Places reviews categorized by theme (maintenance, staff, move-in/out, security), sentiment trend, tied to measurable outcomes.

Call rental comp logic (`references/comps.md`) for a comp-validated rent range and map.

### Attribution (core analytical step)

For each of four required dimensions — occupancy, rent/SF, OpEx ratio, retention rate — allocate variance from peers across four drivers:

1. **Market conditions**
2. **Structural asset factors**
3. **Tenant quality** (credit <620 → structural bad debt, sized as the NOI-margin gap after structural lines, never charged to the manager; income-to-rent <2.5x, i.e. `rent_to_income_ratio` above ~0.40 per the data-layer orientation note → structural turnover)
4. **Manager decisions**

State attribution explicitly with numbers. Pattern-check against the firm's other assets.

### Calculations (Python sandbox)

Core metrics: occupancy delta, rent/SF delta, OpEx ratio, operator-controllable gap (net of tenant-driven cost, which is structural), structural cost gap, days vacant, trade-out quality, renewal rate delta, income-to-rent ratio (= `1 / rent_to_income_ratio`; confirm orientation live), management fee rate (vs. size-tier norms: <100 units 5–8%; 100–300 units 4–5%; 300+ units 3–4%), NOI gap to peer-average management, and value impact = NOI gap / market cap rate.

### Response (5 sections, 4-minute read)

Open with the response-header convention (router output discipline): a horizontal rule and a bold deliverable header on its own line, then the body. Header text: **`Property Manager Assessment — [Property name] ([Manager firm])`**.

1. **Recommendation** — Line 1: **[RETAIN / IMPROVE / REPLACE]** + firm grade (letter) + one-sentence characterization. Line 2: dollar-sized annual manager-attributable gap and implied value impact at market cap rate. Line 3: dominant piece of evidence. Then **dimension scorecard** (leasing efficiency 25%, expense control 25%, retention tactics 20%, occupancy vs. submarket 15%, revenue strategy 10%, tenant quality trend 5%) with raw delta, manager-attributable delta, and score. Action matched to verdict:
   - **Retain:** value creation + optimization opportunity.
   - **Improve:** one 90-day target with dollar lever, 1–2 secondary targets in 12 months, escalation trigger to Replace.
   - **Replace:** annual value of closing the gap, switching costs, 2–3 realistic alternatives, early-termination clause details.
2. **Attribution** — peer set identification, attribution table across four dimensions, 3–4 sentences, firm pattern check.
3. **Operational read** — 3–5 bullets, each tying a specific data point to a management decision and a quantified implication. At least one bullet rules out the most plausible alternative explanation. Cover: leasing efficiency, expense execution (structural lines held aside), retention, revenue strategy. Skip dimensions with nothing material. One chart maximum.
4. **Manager profile** — 3–4 sentences: firm context, implied fee rate vs. norms, management agreement provisions that constrain the owner.
5. **Bottom line** — 1–2 sentences: single most important action in next 30 days; one metric most worth monitoring next quarter.

---

## When to call out to other skills

- Comparing 5+ properties → also load `methodology/multi-entity.md`.
- Tenant Analysis frame finds disconnect between demographics and operations → consider a follow-up Manager frame run.
- Base-year MF operating statement (NOI/EGI/OpEx) underpinning any frame → source it from `realai-mf-operating-engine` in `authority` role (no workbook is in scope), then compute the frame-specific diagnostics on top. This keeps NOI identical across every RealAI viewpoint for the same inputs. The skill (engine) owns the canonical MF operating-statement contract.
- Mark-to-Market frame's NOI impact figure needed inside an underwriting pro forma → hand to `realai-underwriting`.
- Need a value figure (e.g., to size value impact at market cap) → call `realai-valuation`.
- Final deliverable formatting → call `realai-brand` as the last step.

## References

- `references/document_reconciliation.md` — Document Reconciliation Protocol.
- `references/comps.md` — rental comp methodology (used by Mark-to-Market and Manager Assessment frames).
- `references/methodology/multi-entity.md` — for cross-property comparisons.
- `realai-mf-operating-engine` — sibling skill; the base-year MF operating-statement math authority (`authority` role) for frames that rest on a normalized NOI / EGI / OpEx statement.
