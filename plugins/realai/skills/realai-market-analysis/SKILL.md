---
name: realai-market-analysis
description: "Profile or characterize a NAMED real estate market (or 2–4 named peer markets). Three frames: Rental Market Analysis (where rents are headed — asking-vs-in-place spread, tradeouts, supply pipeline, tenant ceiling), Market Demand Drivers (migration cohort delta, employment, household formation), Market Entry Scorecard (strategy-weighted go/no-go for stabilized MF, value-add MF, ground-up MF, SFR aggregation, BTR, or mixed). Activate on phrasings like: 'rental market read', 'where are rents going', 'demand drivers', 'who's moving to', 'market entry scorecard', 'should we enter Charlotte', 'is Austin still good for value-add'. Do NOT use this skill to DISCOVER markets (route to realai-discovery), to analyze a single property (route to realai-property-analysis or realai-investment), or for capital-deployment verdicts on a specific deal (route to realai-investment)."
license: Proprietary
---

# RealAI Market Analysis

## Scope and frames

This skill characterizes one or more NAMED markets across three frames. It does not discover markets — that's `realai-discovery`. It does not analyze a specific property — that's `realai-property-analysis` or `realai-investment`.

| Frame | Source agent | What it tells you |
|---|---|---|
| Rental | Rental Market Analysis | Where rents are headed — asking-vs-in-place spread + tradeouts + supply pipeline + tenant ceiling |
| Demand | Market Demand Drivers | Migration cohort delta, employer base, household formation, financial trajectory |
| Entry | Market Entry Scorecard | Strategy-weighted go/no-go for entering a market for a specific play |

## Frame resolution

Run a single intake form. Infer the frame from signal:

| Signal | Frame |
|---|---|
| "Where are rents going," "asking vs in-place," "tradeouts," "supply pipeline impact on rents" | Rental |
| "Who's moving here," "demand fundamentals," "cohort quality," "employment base," "demographic shift" | Demand |
| "Should we enter," "go/no-go on this market," "strategy fit," "what's the entry play" — includes a stated strategy | Entry |

If multiple frames implied, default to Entry when a strategy is named, otherwise ask which the user wants first.

## Hard scope boundaries

The frames have explicit boundaries — respect them or split into multiple runs:

- **Rental** does not cover property-level rent roll analysis (→ `realai-property-analysis` Mark-to-Market), home values (→ `realai-single-family`), cap rates (out of scope), or migration decomposition (→ Demand frame).
- **Demand** does not cover rent levels, home values, or cap rates. A single sentence contextualizing price or rent is permitted; a housing or rental analytical section is not. Asset-class-agnostic.
- **Entry** is for evaluating markets the user already named. Not for discovering which markets to consider. Not for deal screening on a specific property.

## Common intake

Single `ask_user`:
- Market(s) — entity picker (one to four)
- Strategy — single-select (Entry frame only): Stabilized MF / Value-add MF / Ground-up MF / SFR aggregation / BTR development / Mixed/opportunistic
- Documents — file upload (optional)
- What you want to know — multi-line text (optional)

If 5+ markets are named, route to `realai-discovery` for cross-sectional treatment instead of running this skill per market.

Helper: *"Pick the markets and tell me what you want to know. If you're weighing an investment strategy in a specific market, name the strategy."*

**Execute silently from here to the header.** Once the intake form is answered, all retrieval, peer-set resolution, metric computation, forecasting calls, and synthesis run inside the thinking block — no "now pulling," no peer-by-peer or metric-by-metric play-by-play, no "now I'll…". The next thing the user sees in chat is the bold response header. Repeated at each Research section below, where the urge to narrate strikes.

## Voice (all frames)

Sophisticated reader — institutional investor, fund principal, head of acquisitions, or strategy lead. Lead with the conclusion, then support it. Use figures in service of judgment. When a metric is at parity and doesn't change the story, leave it out. **Never restate a figure that already appears in the scorecard table or chart.**

---

## Frame 1 — Rental Market Analysis

### Signature analytical move

**Asking-vs-in-place spread plus tradeout direction.** Asking rent is theoretical until tradeouts confirm it. A widening spread with tradeouts clearing the gap means real rent growth in the market; the same spread with tradeouts at in-place levels means asking is aspirational.

### Three headline triggers

(1) asking-vs-in-place spread > 5% in either direction; (2) MF pipeline > 5% of existing stock; (3) tenant ceiling — rent-to-income > 30% AND DTI rising AND reserves thin. If multiple trigger, lead with the strongest signal.

### Research — data retrieval
Silent execution: resolve peers, pull, and compute in the thinking block — no progress narration, no peer-by-peer play-by-play. The next thing in chat is the response header._

Resolve entity set first. Identify 2–4 peer areas (same grain, same parent). Retrieve for subject, parent, and peers.

**Segment-conditional:**
- MF or Both: MF or Both: MF rent & occupancy detail, MF rent time series (overall). Pull the by-bedrooms breakdown only if a rent finding actually turns on unit mix; pull by-bedrooms-and-baths only for mixed-product comparative analyses, and only for the subject and one closest peer — never the full entity set
- SFR or Both: SFR rent snapshot by unit category, SFR rent time series (overall and by unit category).

**Always:**
- Permit time series — MF and SF permitted units, T12 and T13–T24
- Credit profile Detail — FICO, DTI level and recent direction
-  Household financials — for rent-to-income context, liquid resources for the reserves test
-  Supply conditions (market grain only) — MF units under construction, deliveries year-to-date, net absorption, and MF vacancy. For finer-grain subjects pull it at the parent market and caveat that the read is market-level
-  Demographics — population, age, mobility score, education, employment, density, housing supply growth

**Reading consumer behavior (when pulled):** the dual comparison is what makes it useful. *Vs national* shows what's distinctive about this market's cohort in absolute terms; *vs parent/peers* shows whether the cohort behaves differently from the surrounding region — usually where the more interesting findings live. Both reads matter. Treat the categories as cohort-profile material, not a list of facts: aggregate them into a sentence or two on how this market's renters actually live and spend, then feed that into the demand read. 
Translation examples: salad over fries → health-conscious; fine dining → affluence, experience-seeking; financial advisor → planning-oriented, risk-averse; takeout → time-poor, convenience-driven.

**Web search:** only for context the platform doesn't carry — major employer announcements, supply events, policy events, BTR-share confirmation.

**Peer filtering:** by population, household income, density, rent level.

**Coverage caveats:**
- Permit time series only at market / county / census_place.
- Supply conditions at market only — finer grains read the parent market and caveat.

**Thin-sample threshold:** days-on-market and tradeout from fewer than 30 leases signed in period are directional, not load-bearing.

### Core metrics

| Metric | Definition |
|---|---|
| Asking-vs-in-place spread | (Asking − In-place) / In-place, weighted across market |
| Tradeout direction | Recent new-lease tradeout % vs. trailing pattern |
| Occupancy direction | Latest vs. T12 |
| Days-on-market shift | Current days vacant vs. T12 |
| MF supply intensity | Trailing-12-month MF permits ÷ existing MF stock (existing MF stock = the unit count on the latest month of the MF rent time series); T12 vs. T13–T24 trend. >3% caution, >5% warning |
| SF supply (with BTR caveat) | T12 SF permits ÷ existing SF stock; flag BTR check when elevated |
| Rent-to-income ratio | Market MF rent-to-income for MF; derived for SFR |
| Tenant ceiling test | All three conditions: rent-to-income > 30% AND DTI trend positive (12-month DTI change from the subject's credit detail) AND liquid resources thin (liquid-resources tier below average vs. MSA or national per its built-in indicators). One or two isn't enough |
| Peer differential | Percentile gap between subject and peers |

### Response (7 sections, 4–6 min read)

Open with the response-header convention (router output discipline): a horizontal rule and a bold deliverable header on its own line, then the body. Header text: **`Rental Market Analysis — [Market(s)]`** (comma-separate up to 4 markets when comparing).

1. **Headline** — When a trigger fires, lead with the signature move. Otherwise lead with the most material finding.
2. **Scorecard at a glance** — verdict line: *Rental market posture: Accelerating / Stable / Cooling / Distressed* + table (Rent trajectory, Tradeout direction, Occupancy, Supply pipeline, Tenant ceiling, Days on market).
3. **Where rents are headed** — 3–5 sentences: (1) spread + tradeout direction; (2) occupancy + DOM; (3) tenant ceiling test. Natural chart: rent trajectory line (asking and in-place, 12–24 months).
4. **What supply is doing** — 3–4 sentences: (1) MF pipeline intensity; (2) SF supply with BTR caveat; (3) cross-reference against demand direction. Natural chart: MF/SF permit volume T12 vs. T13–T24.
5. **How it sits in context** — open with divergence. Cover up-stack (subject vs. parent) and down-stack (which child geographies are driving the picture). Peers integrated, not standalone.
6. **Where this is headed** — 12/24/36 forecast table (Horizon / Asking rent / Occupancy) via `realai-forecasting-engine` in trend mode (family `rent_or_occupancy`). Name biggest driver and variable most likely to shift the read. For 5-year horizons, foreground the scenario band over the central line.
7. **Risks and follow-ups** — 2–3 risk bullets each paired with a trigger signal. Route demand-side, capital-markets, or property-level findings as one-sentence redirects.

**Forbidden additions:** no separate "Verdict," "Bottom line," "Demand context," or "Affordability" sections.

---

## Frame 2 — Market Demand Drivers

### Core read

**Migration is not a supporting signal — it is a demand forecast.** The cohort delta (income, wealth, education, age of inbound vs. outbound migrants) is the most forward-looking signal in the data. A market gaining the right people is selecting for durable demand even when net inflows are modest; a market losing them is degrading even when headline population holds.

### Research — data retrieval
Silent execution: pull and compute in the thinking block — no progress narration, no peer-by-peer play-by-play. The next thing in chat is the response header.

Retrieve for subject, parent, and 2–4 identified peers.

**Always:**
- Migration — net migration, inbound/outbound deltas, top origin/destination areas
- Census demographics — population, density, growth, households, age structure
- Demographic basics — gender, marital status, mobility
- Household income — median, owner/renter split, recent trajectory
- Household wealth — net worth tiers, investable assets
- Employment — industry and occupation composition
- Education — score and bachelor's+ rate

**Conditional:**
- Credit profile — when financial resilience is implicit
- Top consumer behaviors — when cohort differentiation is the headline
- Cultural identity — only if intake makes it relevant
- Demographic samples — only when standard distributions don't tell the story

**Web search:** only for major employer announcements, plant closings, university capacity changes, large policy events.

**Peer filtering:** by population, household income, education score, density.

**Thin-sample threshold:** for geographies with fewer than 500 migration observations OR fewer than 10,000 housing units: (1) note constraint; (2) sanity-check any metric diverging from parent by >30%; (3) state constraint inline when citing cohort delta from fewer than 300 observations.

### Core metrics

| Metric | Definition |
|---|---|
| Net migration rate | Net migration as % of population, with national and MSA percentile context |
| Migration cohort delta | Inbound minus outbound: income, education score, net worth tier, age |
| Population growth | T12 and 5-year change |
| Employer concentration | Top 3 industry shares; flag any single industry above 15–20% |
| Income trajectory | Recent % change in median household income |
| Wealth profile | Net worth tier distribution and migrant tier delta |
| Peer differential | Percentile gap between subject and peers |

### Response (7 sections, 4–6 min read)

Open with the response-header convention (router output discipline): a horizontal rule and a bold deliverable header on its own line, then the body. Header text: **`Market Demand Drivers — [Market(s)]`**.

1. **Headline** — when migration trigger fires, lead with cohort delta. Otherwise lead with most material finding.
2. **Scorecard at a glance** — verdict: *Demand strength: Strong / Mixed / Weakening* + table: Net migration, Cohort direction, Population growth, Employer concentration, Income trajectory, Financial profile.
3. **Who's moving in (and out)** — 3–5 sentences: (1) cohort delta; (2) net flow vs peers; (3) origin/destination flows. Natural chart: horizontal bar comparing inbound vs outbound on income, wealth tier, education score.
4. **What's anchoring demand** — 3–5 sentences (integrated): employer base, household formation and age structure, financial trajectory. Skip whichever isn't material.
5. **How it sits in context** — divergence sentence. Up-stack (subject vs parent divergences only). Down-stack (which children drive the picture). Peers integrated.
6. **Where this is headed** — invoke `realai-forecasting-engine` in trend mode (family `demographic`) for population, jobs, or median income. 2–4 sentences: central case, biggest driver, variable most likely to shift the read. On explicit request: Base / Upside / Downside at 1yr / 2yr / 3yr.
7. **Risks and follow-ups** — 2–3 bullets each paired with trigger signal. Route housing or rent findings as one-sentence redirects.

---

## Frame 3 — Market Entry Scorecard

### What ties the read together

A complete market entry read combines three things:
- **Demand fundamentals** — population, migration, employment, household income and wealth, credit profile, cohort the market is selecting for
- **Supply and pricing** — rent levels and trajectory, home values, permits, cap rates, market vs. national benchmarks
- **Strategy fit** — the same market reads differently for stabilized MF vs. ground-up vs. SFR aggregation

The strongest scorecard scores the market *for the strategy the user named.*

### If documents were uploaded

Follow Document Reconciliation Protocol (`references/document_reconciliation.md`).

### Strategy calibration

| Strategy | What "good" looks like | Signals to weight heaviest | Risks to lean into |
|---|---|---|---|
| Stabilized MF acquisition | Durable rent trajectory, healthy occupancy, moderate supply pressure, cap rates priced for stability | `mf_rent_ts` trend, occupancy, `caprate_ts`, `permit_ts` MF, migration, HH income trend | Yield compression, supply waves, migration cohort weakening |
| MF value-add | Loss-to-lease headroom, stable-to-improving cohort, room between in-place and asking rents | `mf_rent_ts` asking vs in-place spread, tradeout %, HH income trajectory, credit profile, MF permit pipeline | Cohort downgrade, rent ceilings from new supply, wage stagnation |
| MF ground-up development | Strong absorption, rents that pencil for new construction, pipeline not saturated, durable demand | `mf_rent_ts` asking, days on market, `permit_ts` MF, migration, employment growth | Pipeline overhang, affordability ceiling, cap rate softening at exit |
| SFR aggregation | Affordable home values, right vintage/configuration, healthy SFR rent trajectory | `sfr_rent_ts`, home sales/values, home personas, `permit_ts` SFR, value-to-income | Home value appreciation outpacing rent, HOA/regulatory friction, low-quality stock |
| BTR development | SFR rent levels that justify new build, demand cohort preferring SFR over MF | `sfr_rent_ts`, home sales/values, `permit_ts` SFR, home personas, migration cohort age | SFR pipeline saturation, rent ceiling, exit liquidity |
| Mixed/opportunistic | Multiple plausible entry paths, durable underlying demand | Migration, employment, HH wealth, both MF and SFR rent series + permits | Read on strongest entry path; flag weaker ones |

### Research — data retrieval (parallel)

Silent execution: run the parallel pulls and scorecard math in the thinking block — no progress narration, no metric-by-metric play-by-play. The next thing in chat is the response header.

**Always:**
- Census demographics — population, density, growth, households, age structure
- Demographic basics — gender, marital, mobility score
- Migration — net migration, inbound/outbound deltas, top origins/destinations. **Single richest demand signal — weight accordingly.**
- Household income — median, owner/renter split, trajectory, national + MSA percentiles
- Household wealth — net worth tiers, investable assets
- Employment — industry and occupation composition
- Education — score and bachelor's+ rate

**Strategy-conditional:**
- MF strategies: MF rent time series, permits
- SFR/BTR strategies: SFR rent time series, home sales and values, home personas, permits
- Mixed: both MF and SFR rent series + both permit categories

**Always at MSA level:** cap rates for the relevant asset class.

**Optionally:** top consumer behaviors (cohort-sensitive strategies), cultural identity (if relevant), credit profile (value-add and SFR).

**Web search:** only for major employer announcements, regulatory events, natural disasters affecting insurance markets.

### Core metrics

Python sandbox:

| Metric | Definition |
|---|---|
| Net migration rate | `migration.net_pct`, ranked vs. national and MSA percentiles |
| Migration cohort delta | Inbound minus outbound: income, education, net worth tier |
| Population growth | T12 and 5-year |
| Employment concentration | Top 3 industry shares; flag single industry >15–20% |
| Rent trajectory | Recent asking vs. prior period; days on market; tradeout % |
| Rent vs income | `rent_to_income_ratio` for MF; derived for SFR |
| Asking-vs-in-place spread | Loss-to-lease headroom |
| Permit intensity | MF and SFR units permitted T12, normalized by population/housing stock |
| Cap rate band position | MSA cap rate via `realai-forecasting-engine` directional mode — returns historical band (min/structural_mean/max), current_level, position_in_band (0–1), position_label (rich/mid/cheap), and `rate_environment` signal. Do NOT project a future cap rate value. |
| Home value trajectory | Median est. value, trajectory, value-to-income |
| Affordability gap | Sale price-to-income and rent-to-income vs. benchmarks |

For comparative analyses, also compute percentile-rank differentials and identify the metric where markets are *most* differentiated.

### Response (max 2–3 charts)

Open with the response-header convention (router output discipline): a horizontal rule and a bold deliverable header on its own line, then the body. Header text: **`Market Entry Scorecard — [Market(s)] ([Strategy])`** — e.g., `**Market Entry Scorecard — Charlotte MSA (value-add MF)**`.

1. **Headline** — one sentence on the read for the named strategy. For comparatives, one sentence per market or a single comparative sentence.
2. **Scorecard at a glance** — compact table: Demand/migration, Cohort quality, Rent trajectory, Supply pipeline, Pricing (cap rate band position + rate environment), Affordability. Max 7 rows. The "Pricing" row reports where the cap rate sits in its historical band (rich/mid/cheap) plus rate environment — not a projected cap rate value. Comparative: markets as columns with directional verdicts, not raw numbers.
3. **Verdict** — two sentences only: (1) ranking or go/no-go for the strategy; (2) single most important follow-up. Immediately after scorecard.
4. **What stands out** — three bullets. One sentence observation + one clause stating what it means for the strategy. Hard cap: 35 words per bullet. Comparatives: bullets that *compare*.
5. **Strategy fit** — one sentence per market: does the data support entry for this strategy, and what's the swing factor?
6. **Risks** — two bullets only. One sentence each: name the risk and specific condition that triggers it. Comparatives: risks may differ across markets.

No closing summary table.

---

## When to call out to other skills

- 5+ markets named → route to `realai-discovery` instead of running this skill per market.
- Need a forecast → invoke `realai-forecasting-engine`. Trend mode for rent / population / income / occupancy (compounding); directional mode for cap rates (band position + rate signal, no projection).
- Final deliverable formatting → call `realai-brand` as the last step.

## References

- `references/document_reconciliation.md` — Document Reconciliation Protocol (Entry frame, when documents present).
- `realai-forecasting-engine` — sibling skill. Trend mode for rent / occupancy / demographic compounding series; directional mode for cap rates (band position + rate signal, no projection).
- `references/methodology/multi-entity.md` — process spine when comparing 5+ entities (this skill caps at 4; beyond that → discovery).
