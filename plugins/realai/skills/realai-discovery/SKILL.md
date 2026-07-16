---
name: realai-discovery
description: "Search and rank a POPULATION (multifamily properties or markets) against criteria; return a ranked candidate list. Two branches: Find Properties — multifamily only via the RealAI semantic datamart; Find & Rank Markets — markets, counties, neighborhoods, zip codes within a larger parent area that best match concrete or fuzzy criteria. Activate on phrasings like: 'find me MF properties that', 'search for multifamily over 300 units', 'where should I buy for cashflow', 'rank the fastest-growing suburbs', 'screen markets for', 'top zip codes for', 'which neighborhoods are emerging'. Returns a candidate list, NOT analysis of one named thing. Single-family and commercial property search is NOT available in this skill — no Zillow integration. Do NOT use to PROFILE a single named market (route to realai-market-analysis), to underwrite a specific property (route to realai-investment), or to value a property (route to realai-valuation). Always invokes multi-entity discipline."
license: Proprietary
---

# RealAI Discovery

## Scope and branches

| Branch | Source agent | What it does |
|---|---|---|
| A — Find Properties | Find Properties | Search for **multifamily properties only** within a geography matching user-defined criteria. Uses the RealAI semantic datamart (`property_mfr`). |
| B — Find & Rank Markets | Find and Rank Markets | Identify and rank places within a larger parent area matching concrete or fuzzy criteria |

**Always invoke `references/methodology/multi-entity.md`** — discovery is inherently multi-entity (batched pulls, code-based composite scoring, threshold labels, superlative verification).

 **Execute silently from here to the header.** All querying, pool-percentiling, composite scoring, forecasting calls, and synthesis run inside the thinking block — no "now querying," no "scoring the candidates," no field-by-field or candidate-by-candidate play-by-play, no "now I'll…". The ONLY things visible in chat before the bold response header are the intake/grain forms and the criteria table that the multi-criteria workflow explicitly requires you to surface before scoring. Everything else is internal. This reminder is repeated at the retrieval sections below because that is where the urge to narrate strikes.

## What this skill CANNOT search

- **Single-family for-sale or sold listings** — no Zillow tools are connected. If the user asks for residential search, tell them this skill is multifamily-only and that single-family valuation is available via `realai-single-family` (which does have Zillow access for individual property lookup, but does not do population-level search).
- **Commercial properties** (office, industrial, retail, hotel, self-storage) — not currently supported. The semantic datamart's property search is scoped to multifamily.
- **Property listings status** (active / sold / off-market) — not exposed in the datamart for multifamily either. Do not imply or surface listing status.

## Branch resolution

Resolve from the user's primary noun:

| User asks for | Branch |
|---|---|
| "MF properties that..." / "Multifamily buildings 300+ units" / "Apartment communities with..." / "Value-add MF in..." | A |
| "Markets where..." / "Suburbs that..." / "Counties with..." / "Zip codes for..." / "Neighborhoods that..." | B |
| Single-family or commercial property search | OUT OF SCOPE — explain the limitation; do not route |

If genuinely ambiguous, ask once.

---

## Branch A — Find MF Properties

This branch searches multifamily properties only via the RealAI semantic datamart (`property_mfr` entity). If the user asks for single-family, condo, or commercial property search, explain that this skill is MF-only and stop — do not attempt to invent a workaround.

### Step 1 — Collect search criteria

Single intake form:

| Field | Input | Required | Description |
|---|---|---|---|
| Search location | Entity picker (one or many) | Yes | Area in which to search — market, county, census place, zip, neighborhood, or submarket |
| Specific question or context | Multi-line text | No | Narrows scope or surfaces the actual investment question. Examples: "Value-add opportunities in Fairfax County," "300+ unit buildings in Austin, TX," "Class A garden-style MF in suburban Charlotte," "Distressed MF with elevated bad debt in DFW" |
| Documents | File upload | No | Research reports, brochures, forecasts |

Helper: *"Multifamily search only. Tell me where to look and what you're looking for — I'll tailor the analysis to what you actually need."*

### Data retrieval

Silent execution: query, evaluate, and shortlist in the thinking block — no "now querying," no result-by-result narration, no "now I'll…". The next thing in chat is the response header.

1. Query `property_mfr` with the user's geography filter and criteria. Apply a logical sort relevant to the question (rent trajectory, unit count, vintage, occupancy gap, etc.).
2. **If more than 50 results return, STOP.** Inform the user of the result count and ask them to narrow before continuing.
3. Evaluate results using retrieved data and general knowledge to determine which best answer the question. If results are inadequate, retry with adjusted filters or sort logic BEFORE surfacing.
4. Once an adequate set is identified, pull additional detail (financials, tenant profile, surrounding area) on the shortlist as warranted.

### Response structure

Open with the response-header convention (router output discipline): a horizontal rule and a bold deliverable header on its own line, then the body. Header text: **`Property Discovery — [Search geography] ([N] MF properties)`** — e.g., `**Property Discovery — Fairfax County (12 MF properties)**`.

- Lead with narrative insights — text tells the story, visualizations express the data
- Include benchmark comparisons where warranted
- Highlight what makes individual properties unique or noteworthy
- Include at least one data visualization per major section (H3)

**Visualization guidance:**
- Components of a whole → **pie chart**
- Rental, housing, or demographic metric correlation → **scatterplot** (all properties or permits, two variables)
- Income, wealth, age, or other population distributions → **histogram**
- Other comparisons → **time series or bar chart** with subject properties, comparable properties, and a geographic benchmark together

---

## Branch B — Find & Rank Markets

### Typical questions

"Where should I buy for cashflow in [state]," "rank the fastest-growing suburbs near [metro]," "find affordable counties with strong job growth," "which neighborhoods are emerging before they peak."

Criteria are often fuzzy — translate them into datamart fields using the multi-criteria workflow below.

### Step 1 — Select parent geography

- Parent geography — entity picker (one or many)
- Specific question or context — multi-line text (optional)
- Documents — file upload (optional)

Helper: *"Fill in as much as you can, or write your question in free-form — I'll tailor the analysis to what you actually need."*

### Step 2 — Populate grain picker

Immediately after Step 1, call `explore_data` silently. Scan `identity_fields` of every entity — any entity that carries a `foreign_key` whose `references_entity` matches the parent's entity type is a valid grain. Emit a single-question follow-up with only those options. Do not hardcode options — derive them fresh from the schema each time. Do not explain this step to the user.

### Research

Silent execution: gather context and run the scoring workflow in the thinking block — no narration, no candidate-by-candidate play-by-play. The only thing surfaced before the response header is the required criteria table (see the multi-criteria workflow).

Pull together everything known about the subject area(s): overall reputation, community type (commuter, tourism, family-oriented), dominant geography (ocean, lake, mountain, urban, suburb, rural), transportation, major industries and employers and their growth prospects, amenities (retail, dining, schools, walkability).

Distinguish datamart-grounded claims from general-knowledge context. Figures sourced from the datamart can be stated plainly; world-knowledge color (reputation, employers, school quality) should be framed as context, not presented with the same confidence as queried data. A professional user must be able to tell which is which.

### Data retrieval rules

- For census places, zip codes, and counties: filter to `population` over 500 unless the question targets small areas. Use `population` for these grains; `total_population_est` is a fallback only where `population` is null.
- **Do not filter or sort neighborhoods or centums on population** — they don't carry that field. Use `households` or a topic-specific sample-size field for sufficiency.
- Before composing any query, map intended fields against the selected grain using the coverage matrix. If a field is unavailable at that grain, substitute the nearest available proxy AND disclose the substitution — never silently drop part of the thesis.

### Multi-criteria filtering workflow

Vague or compound criteria ("best cashflow markets," "cashflow with high tenant quality," "affordable and growing") require combining several fields and, often, more than one query. Internal knowledge helps sort, but the ranking must be grounded in datamart fields and reconstructable from the criteria table alone.

#### 1. Translate the goal into a criteria table

Decompose the user's question into 3–6 named criteria. Each row binds one criterion to one datamart field and a ranking direction:

| Column | Meaning |
|---|---|
| `criterion_name` | Plain-language thesis component (e.g., "rent growth momentum," "tenant credit quality") |
| `datamart_field` | The single field expressing it — prefer a percentile/z-score variant if one exists (see step 2) |
| `direction` | `higher_better` or `lower_better` — **declare explicitly for every row** |
| `scaling_source` | `natl_pctile` / `msa_pctile` / `pool_computed` — how the field is made comparable (step 2) |
| `weight` | Fractional weight; row weights sum to 1 |
| `origin` | `user` or `model-added` (step 5) |

**Surface this table to the user before scoring** — it is the audit trail.

#### 2. Bind each criterion to a comparable score, in this priority order

Not every field carries a pre-computed cross-geography variant. The wealth, income, affordability, education, and migration-quality families are well-covered, but most operational real-estate fields (rents, occupancy, tradeout, retention, permits, cap rates, job growth, FICO bucket shares) are **raw value only.** For each criterion's field:

**Two demographic families are available for criteria but easy to overlook.** `cultural_identity` (ethnicity/ancestry, primary language, religion mix) supports cohort-composition and cultural-shift theses; it is a snapshot — freely combinable and sortable in the wide query like any other snapshot field. `home_personas` (housing-stock characteristics and personas by property type and decade built) supports housing-vintage / stock-mix theses; it carries a required `id` filter and is a **separate data source**, so — like the `[TS]` fields — it cannot be sorted in the wide net and must be pulled per-candidate during the scoring pass, then pool-percentiled after retrieval. Both are available across the geographic grains this branch uses (confirm the specific grain via `explore_data`). Neither ships pre-computed cross-geography percentiles, so expect `pool_computed` scaling for their fields.

For each criterion's field:

1. **If a `_natl_pctile` / `_msa_pctile` / `_zscore` variant exists, use it.** Already comparable across geographies. Use `_msa_*` when the parent is a single metro, `_natl_*` for multi-metro or national scope. Set `scaling_source = natl_pctile` or `msa_pctile`.
2. **Otherwise, compute a percentile within the candidate pool in the sandbox.** Since you've pulled 25–50 candidates (step 3), rank-normalize the raw field across that set. This is a relative-to-pool percentile, a weaker claim than relative-to-nation — set `scaling_source = pool_computed` so the user can see which criteria rest on national scaffolding and which are only pool-relative.

**Direction is applied after scaling, not before.** For `lower_better` fields, invert the percentile (`100 − pctile`) or flip the z-score sign. Watch the inverted families — affordability ratios (`*_to_income_ratio*`), short-term liability tiers, and days-on-market all read "high = worse." Some fields are reverse-coded against their name (e.g. mobility/stability scores), so read each field's live description before assigning direction rather than inferring from the name. Declaring direction per row in the table is what prevents the silent ranking bug where "rank high on this" does the wrong thing on a ratio.

#### 3. Cast a wide net on the lead criterion

Pick the highest-weight criterion's field as the primary sort, retrieve a candidate pool of **25–50**, and apply only hard constraints — geographic containment and data sufficiency (`*_sample_confidence`, sample-size, or `population` / `households` per the grain rules).

#### 4. Score the composite in the sandbox

Pass the per-criterion scaled values to the sandbox and compute the weighted sum using the table's weights. Do not eyeball it. Output each candidate's **per-criterion contribution**, not just the total, so a place ranking #15 on the lead criterion but winning overall is explainable. Flag any candidate that scores high on the lead criterion but fails two or more others.

#### 5. Handle user-supplied criteria

When the user names criteria explicitly ("cashflow with high tenant quality"), those become the **high-weight rows** (`origin = user`). You may add **at most one or two low-weight guardrail rows** — a sufficiency, affordability, or supply sanity-check — to stop a user-named thesis from surfacing a place that ranks #1 on the stated criteria but has a collapsing tenant base or an unaffordable entry price. Guardrail rows must be labeled `origin = model-added` in the table and carry small weights; user intent stays dominant.

#### 6. Narrow to holistic winners

Present places that score well across the criteria, not just the lead. If too few multi-criterion winners emerge, widen the net or relax one threshold and say so.

**Time-series note.** Fields marked **[TS]** (tradeout, occupancy trend, rent growth, cap-rate trend — see Standing Rules) do not exist in the wide candidate query and cannot be pool-percentiled up front. Pull the series per candidate during the scoring pass, then compute the `pool_computed` percentile across those gathered per-candidate values — the rank-normalization happens after retrieval, not in the initial net.

### Worked walkthrough — methodology in action

The abstract workflow is easier to apply when you've seen it on one concrete question. This is what the criteria table should look like end-to-end. The methodology itself is the contract — the specific weights and fields below are illustrative.

**User question:** *"Best cashflow markets in New Jersey."* Parent geography = New Jersey (state); selected grain = county.

> **This is an illustration of the criteria-decomposition method at county grain with pool-percentiling — not a template to copy literally.** The field choices below are grain-specific: at county grain, several operational fields have no pre-computed cross-geography companion, so they're scaled `pool_computed`. Before reusing any row, check whether a `_natl_pctile` / `_msa_pctile` variant exists for that field *at your chosen grain* (prefer it when it does), and re-derive the available topics for your grain from the coverage matrix in Standing Rules — a different grain will expose a different field set. Adapt criteria to the grain; do not transplant this table.

**Step 1 — decompose into criteria.** "Cashflow" decomposes into: room to push rents (today's rents not maxed against incomes), affordable entry basis, healthy demand (occupancy holding), demonstrated rent momentum, and supply discipline (so rents don't soften). The user-named thesis is cashflow, so all five user rows carry the bulk of the weight; one model-added guardrail on supply prevents a place with a flood of new construction from winning on current cashflow but failing on durability.

| `criterion_name` | `datamart_field` | `direction` | `scaling_source` | `weight` | `origin` |
|---|---|---|---|---|---|
| Rent push headroom | `rent_to_income_ratio` **[SNAP]** | `lower_better` | `pool_computed` | 0.25 | `user` |
| Entry affordability | `value_to_income_ratio_natl_pctile` | `lower_better` | `natl_pctile` | 0.25 | `user` |
| Demand strength | `occupancy_latest` **[SNAP]** | `higher_better` | `pool_computed` | 0.20 | `user` |
| Rent growth momentum | `in_place_rent_t12_pct_chg` **[SNAP]** | `higher_better` | `pool_computed` | 0.20 | `user` |
| Supply discipline | `mf_units_permitted_t12` **[TS]** ÷ `households` | `lower_better` | `pool_computed` | 0.10 | `model-added` |

Weights sum to 1.00. User rows = 0.90, model-added guardrail = 0.10. Hard filter (not weighted): `population ≥ 500` for sufficiency.

**Step 2 — surface the table to the user before scoring.** This is the audit trail. The user can see that the cashflow thesis is being scored on five fields with explicit directions, and that the only thing the model added on its own is a small supply-side guardrail. If they push back ("I don't care about supply, just rank by yield"), drop the guardrail and reweight.

**Step 3 — direction notes (the inverted-ratio trap).** Three of the five fields read "high = worse" or work on an inverted scale:

- `rent_to_income_ratio_natl_pctile` — a *high* percentile means rents are already eating a large share of income for that geography vs. the nation. That means *less* push headroom, not more. So `lower_better`. After scaling, invert the percentile (`100 − pctile`) before adding to the composite.
- `value_to_income_ratio_natl_pctile` — same logic. High = unaffordable entry. `lower_better`.
- `mf_units_permitted_t12 ÷ households` — high = lots of new supply incoming. `lower_better`.

Declaring `direction` per row in the table makes these inversions explicit and prevents the silent ranking bug.

**Step 4 — scaling source notes.** Only the entry-affordability row (`value_to_income_ratio_natl_pctile`) has a pre-computed `_natl_pctile` companion — the strong claim, comparable to all counties nationally. The other four rows have no national percentile: rent-to-income, occupancy, in-place rent change, and permit pace are raw values for ranking. Retrieve those across the candidate pool, then rank-normalize within that pool in the sandbox — that's `pool_computed`. Note this is a separate axis from `[TS]`/`[SNAP]`: rent-to-income, occupancy, and in-place-rent change are pool_computed **and** snapshot-resident (pulled in the wide query), while only permit pace is `[TS]` (enriched per candidate in Step 6).


**Step 5 — cast the wide net.** Pick the highest-weight field that exists in the snapshot — here it's a tie at 0.25 between `rent_to_income_ratio_natl_pctile` and `value_to_income_ratio_natl_pctile` (both **[SNAP]**). Sort on whichever; retrieve 25–50 NJ counties with `population ≥ 500`. (NJ only has 21 counties, so you get the full set — but the pattern matters for larger parents.) This is the candidate pool.

**Step 6 — enrich [TS] fields per candidate.** For each of the candidates, pull the three time-series fields (`occupancy_latest`, `in_place_rent_t12_pct_chg`, `mf_units_permitted_t12`). These were impossible to filter in Step 5 because they don't live in the snapshot. After retrieval, compute pool-percentile rank for each [TS] field across the gathered candidate values.

**Step 7 — composite in the sandbox.** For each candidate, compute the five scaled scores (invert the three `lower_better` rows), multiply each by its weight, sum. Output per-candidate **per-criterion contribution** alongside the total, so a county ranking #15 on rent push headroom but winning overall is explainable.

**Step 8 — flag and present.** Flag any candidate that scores in the top quartile on a user-named criterion but fails the model-added guardrail (e.g., wins on rent momentum but has a heavy pipeline) — that's where the user judgment lives, not the composite score. Present the top 4–6 holistic winners with a map and a per-criterion contribution table; if fewer than 4 multi-criterion winners emerge, widen the net or relax one threshold and say so.

**What this teaches.** The methodology's three load-bearing moves — surfacing the criteria table, declaring direction per row to handle inverted ratios, and labeling pool_computed vs. natl_pctile scaling — all appear above. The abstract worked-examples table that follows lists field compositions for other goals; translate them into criteria tables using the same five-column shape.

### Standing rules

1. **Snapshot vs. time-series.** Fields marked **[TS]** live only in time-series topics (`mf_rent_ts`, `sfr_rent_ts`, `permit_ts`, `caprate_ts`, `home_sales_and_values_ts`) and cannot be sorted in a single candidate query — pull the series per candidate during scoring. Fields marked **[SNAP]** are directly sortable in the wide query.
2. **Grain coverage gaps to watch** (confirm live via `explore_data` scope `"topics"` for the selected grain before composing — coverage shifts as the catalog evolves):
   - `caprate_ts` — market only
   - `permit_ts` — market, county, census_place only
   - `top_consumer_behaviors` — carried at census_place, zipcode, neighborhood, centum, market, and property_mfr; **not** at submarket, county, state, or nation. Requires an `id` filter and is a separate data source (own call, per-candidate — cannot go in the wide net). If the selected grain is submarket or county, this topic is unavailable — drop to census_place/zip or substitute a different signal, and disclose the substitution.
   - Rent time-series — not at centum

### Worked examples

**Illustrations of the criteria-decomposition method, not a fixed menu.** Most real questions will not match a row; compose your own criteria the same way. Each cell lists the fields that express the thesis — bind each to a direction and a scaling source per the workflow above.

| Goal | Field composition (criteria) | What it teaches |
|---|---|---|
| `best_rental_investment_markets` | `tradeout_new_lease_pct_avg` **[TS]**, `occupancy_latest` **[TS]**, `mf_units_permitted_t12` **[TS]** vs `_t13_t24`, `days_on_market` **[TS]**, `job_growth_1_year`, `rent_to_income_ratio_msa_pctile` **[SNAP]** (low = room to push rents) | Rent fundamentals live in time-series, not snapshot — pull series per candidate and pool-percentile them after retrieval. |
| `cap_rate_opportunity_markets` *(market grain only)* | `caprate_ts.multifamily` trend **[TS]**, `mf_units_permitted_t12` **[TS]**, `population_growth_t12_pct_chg`, `median_t6_pct_chg` (cap-rate direction **[TS]**: expansion = entry, compression = momentum) | The catalog's most investment-relevant asset exists at one grain only; respect that. |
| `supply_constrained_rent_growth` *(mkt/county/census_place)* | `tradeout_new_lease_pct_avg` **[TS]**, `population_growth_t12_pct_chg`, **low** `total_units_permitted_t12` **[TS]** vs `households`, `occupancy_latest` **[TS]**, `days_on_market` **[TS]**, `value_to_income_ratio_natl_pctile` **[SNAP]** | Demand and supply are read together — strong demand with heavy pipeline is not the same deal. |
| `migration_quality_inflow_markets` | `net_pct_msa_pctile`, `total_units_permitted_t12` **[TS]**, `household_income_median_diff_natl_pctile` (in vs out), `net_worth_tiers_avg_in`, `education_score_avg_in`, `age_avg_in`, `value_to_income_ratio_msa_pctile` **[SNAP]** | *Who* is arriving matters more than how many — use inbound (`_in`) and differential fields, not raw net. |
| `most_affordable_markets` | `households`, `population` (sufficiency), `poverty_level`, `median_natl_pctile` (income), `value_to_income_ratio_natl_pctile` **[SNAP]**, `rent_to_income_ratio_natl_pctile` **[SNAP]** | Affordability is inherently relative — the percentile scaffolding *is* the metric, and these ratios are `lower_better`. |
| `distressed_undervalued_opportunity` | `est_value_median_t12_pct_chg` **[SNAP]** (weak/negative), `total_units_permitted_t12` **[TS]** (low), `job_growth_1_year` turning, `population_growth_t12_pct_chg`, `est_value_median_natl_pctile` **[SNAP]** (low), `fico_score_below_579_pct` | Some theses invert the signal — a *weak* trailing number is the entry point, gated on a turn. |
| `where_young_people_are_moving_to` (migration flow) | Sort on low `age_avg_in` + positive `net_pct_msa_pctile`. **Do not use `age_avg_out`** (that measures who is *leaving*). `top_destination_area_*_id` are foreign-key IDs for tracing a flow to a named place — resolve to names only on request, never as a ranking score. | Migration fields are directional; IDs are not rankable metrics. |
| `cohort_or_cultural_shift_markets` | `migration` inbound cohort fields + `cultural_identity` composition fields (language, ancestry, religion mix) as a snapshot criterion **[SNAP]**, gated on demand (`occupancy_latest` **[TS]**) | Cultural composition is a sortable snapshot — combine it in the wide query; pair it with a demand gate so a shift alone doesn't win. |
| `aging_housing_stock_value_add` | `home_personas` **[separate source, id-filtered]** decade-built / property-type mix (older stock = renovation runway), `est_value_median_natl_pctile` **[SNAP]** (low), `total_units_permitted_t12` **[TS]** (low = little new competition) | `home_personas` is id-filtered and separate-source — pull per candidate and pool-percentile after retrieval, never in the wide net. |

### Forecasting

When the goal is inherently forward-looking (emerging markets, fastest-growing, home value appreciation, best rental investment, supply-constrained rent growth, migration quality inflow, or any custom question with forward intent) — invoke `realai-forecasting-engine` during the scoring pass.

**For compounding metrics** (rent, home value, population, jobs, income): trend mode. Pass metric, candidate geography, history, peer context, and `scenarios: ["base", "upside", "downside"]`. Use the base case as the forward component of the weighted ranking; flag candidates with wide scenario bands.

**For oscillating metrics (cap rates)** — e.g. the `cap_rate_opportunity_markets` goal: directional mode. The skill (engine) returns `band_position` (rich/mid/cheap) and the `rate_environment` signal — it does NOT project a future cap rate. Score on band position (markets at "cheap" band position with stable or easing rate environment rank higher; "rich" markets rank lower). Do NOT use a projected cap rate value — the engine refuses to produce one.

When scoring more than a handful of candidates, parallelize the forecasting calls — one metric per call but issued together, not sequenced.

Present-tense and distress/screening goals (affordable, blue-chip, luxury, distressed/undervalued, recession-resistant, first-time-buyer, build-to-rent) do not require forecasts.

### When N > 5 (always for this skill)

This skill always invokes `references/methodology/multi-entity.md` — batched pulls, sandbox composite scoring, threshold labeling, superlative verification. See that file for the five rules; they're not optional here.

### Response structure

Open with the response-header convention (router output discipline): a horizontal rule and a bold deliverable header on its own line, then the body. Header text: **`Market Discovery — [Parent geography] ([grain], [N] candidates)`** — e.g., `**Market Discovery — New Jersey (counties, 6 candidates)**`.

- Lead with narrative insights, not raw data dumps
- Include benchmark comparisons if warranted
- Highlight what makes the area(s) unique or noteworthy
- Keep text focused on narrative; let visualizations express data
- Visualize when the data has shape worth seeing — distribution, trend, correlation, or ranking. Use prose for everything else; do not add charts to satisfy a quota.
- Once geographies are identified, **generate a new map** containing the geographies to discuss
- For income, wealth, age, or other demographic distributions → histogram
- For other inquiries → time series or bar chart, plotting subject geography, comparable geographies, and a benchmark alongside each other

---

## When to call out to other skills

- Profile a single named market that emerged from discovery → hand off to `realai-market-analysis`.
- Underwrite a specific property that emerged from discovery → hand off to `realai-investment`.
- Final deliverable formatting → call `realai-brand` as the last step.

## References

- `references/methodology/multi-entity.md` — process spine. ALWAYS invoked for this skill.
- `realai-forecasting-engine` — sibling skill. Trend mode for compounding metrics; directional mode for cap rates.
