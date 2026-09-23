# RealAI Datamart Topic Catalog

Canonical topic reference, verified against the semantic-layer TypeScript manifests
(`src/semantic-layer/manifests/`). Use live MCP discovery when it differs from this stored reference; the manifests
provide offline verification, not a substitute for the connected schema.
Companion file: `grain-coverage.md` (entity x topic matrix + required-filter quick table).

**Verification state**

| | |
|---|---|
| Topic inventory + provenance | origin/main `f03a27d`, 2026-09-18 — 51 topics; strict catalog verifier passed |
| Field citations | 2026-09-18 verifier: 41 concrete citations matched; 100 wildcard/range patterns not checked. Live market credit and household fields spot-checked. |
| Coverage observations and filter values | Historical observations unless explicitly updated below; recheck live for the current question. Schema verification does not verify population or observation dates. |

Recheck topic and field definitions with live MCP discovery after a semantic-layer
release; use the definitions exposed by the current connection.

## Table of contents

1. [Conventions](#conventions)
2. [Provenance and freshness](#provenance-and-freshness) — declared sources and refresh metadata
3. [Data confidence and sample quality](#data-confidence-and-sample-quality) — `_conf`, sample fields
4. [Coverage and alternatives](#coverage-and-alternatives) — what to do when a value is thin
5. [Geographic entity topics](#geographic-entity-topics)
   - Demographics & household economics
   - Housing supply, sales & values
   - Multifamily & SFR rent (geo grain)
   - Cap rates, commercial, behaviors
6. [property_mfr topics](#property_mfr-topics-multifamily-property)
7. [property_residential topics](#property_residential-topics-single-family)
8. [property (master) topics](#property-master-entity)
9. [National / macro entities](#national--macro-entities)
10. [Disambiguation rules](#disambiguation-rules)
11. [Question-specific topic selection](#question-specific-topic-selection)
12. [Field conventions](#field-conventions)
13. [Known traps](#known-traps)
    - Topic names that do not exist
    - Field-name traps

## Conventions

- **★ = own-table topic** (`separate_data_source: true`). Retrieval grouping, filters,
  field projection, pagination, and recovery are defined only in `data-access.md`.
- `snapshot`, `detail`, and `ts` help distinguish concise comparisons, richer components,
  and history. Actual contents vary; a suffix is not a guaranteed field contract.
- Field names below are API keys, not SQL columns. Tables are a selection aid; confirm
  names and required-filter values through live discovery before constructing calls.

## Provenance and freshness

Source declarations below are from manifest metadata. The dates are stored
`meta.last_updated` values captured during earlier verification, not necessarily current
refresh dates or observation dates. Use live metadata and returned row dates for the
answer. Declared cadence does not prove a dataset refreshed on schedule. Some topics do
not declare provenance.

| Source | Declared cadence | Recorded metadata refresh | Topics |
|---|---|---|---|
| **RealAI SuperCensus™** — 250M+ US adults; credit bureau (TransUnion, Experian, Equifax), Nielsen, Census ACS, NMDB. Metadata describes ZIP+4 anonymization and possible insufficient-sample coverage; it does not explain every absent value. | Quarterly | 2026-06-30 | `credit_profile_snapshot`, `credit_profile_detail`, `credit_ts` |
| **RealAI SuperCensus™** (same dataset, faster cadence) | Every 6 weeks (8×/yr) | 2026-08-15 | `cultural_identity`, `education`, `household_financials_snapshot`, `household_financials_detail`, `household_income_ts`, `mf_tenant_profile_snapshot`, `mf_tenant_profile_detail`, `top_consumer_behaviors` |
| **RealAI SuperCensus™** — migration aggregates derived from tracking individuals address-to-address across updates | Every 6 weeks | 2026-08-15 | `migration` |
| **RealAI Rent Index** — daily tracking of 20M+ public rental listings and ILS feeds; exact source varies by property | Weekly | 2026-09-05 | `mf_rent_and_occupancy_snapshot`, `mf_rent_and_occupancy_detail`, `mf_rent_ts`, `mf_rent_ts_by_beds`, `mf_rent_ts_by_beds_baths`, `mf_rent_roll_ts`, `rent_roll_latest`, `sfr_rent_snapshot`, `sfr_rent_ts`, `sfr_rent_ts_by_unit_category` |
| **RealAI Ops Benchmarks** — MF revenue/expense benchmarks from HUD/FHA, GSE securitization disclosures, SEC EDGAR, assessor and insurance datasets; revenue from daily observation of 20M+ units | Daily | 2026-08-31 | `mf_property_financials`, `mf_pnl_benchmarks` |
| **Municipal recorder of deeds** | Monthly | 2026-08-31 | `home_sales_and_values_snapshot`, `home_sales_and_values_ts`, `res_sales_history` |
| **Municipal tax assessor** | Monthly | 2026-08-31 | `mf_tax_and_assessment`, `res_tax_and_assessment` |
| **Assessor + deed recorder** | Monthly | 2026-08-31 | `home_personas`, `res_property_area`, `res_property_attributes` |
| **Residential AVM** — 2.9% median absolute percentage error; 80%+ of valuations within 10% of actual sale price on out-of-sample testing across the past decade | Monthly | 2026-08-31 | `res_home_valuation` |
| **US Census Building Permits Survey** — released with roughly a 6-month lag from the reference period | Monthly | 2026-05-21 | `permit_ts` |
| **GreenStreet Market Cap Rates** | Monthly | 2026-07-07 | `caprate_ts` |
| **Cushman & Wakefield US MarketBeats** | Quarterly | 2026-05-20 | `commercial_market` |
| **US Census 2024 ACS** — 1-year where available, else 5-year | Annually | 2026-01-29 | `employment` |
| *(no provenance declared in the manifest)* | — | — | `demographic_basics`, `demographic_samples`, `home_price_mortgage_ts_by_gen`, `mf_amenities`, `mf_ownership_and_management`, `mf_property_attributes`, `mf_sales_history`, `mortgage_rate_snapshot`, `national_metrics_*` (5), `supply_snapshot` |

Refresh lag and observation lag differ. For permits and other delayed series, use the
reported observation period; do not subtract a presumed lag from a refresh date to invent
an as-of. Asset-specific refresh may differ from source-wide metadata. When a source is
not declared, retain the MCP attribution without inventing an upstream provider.

## Data confidence and sample quality

Confidence JSON, counts, coverage shares, completeness flags, and model-fit measures have
different meanings. Their interpretation is centralized in
`${CLAUDE_PLUGIN_ROOT}/skills/realai-supercensus/references/cohort-interpretation.md`
(Confidence and sample evidence), including use outside household topics. General
analytical judgment is in `../interpretation-guide.md`; disclosure is in
`../output-conventions.md`. Inspect quality when relying on an estimate and disclose material
uncertainty. Do not infer a NULL's cause or prohibit useful sample qualifications.

## Coverage and alternatives

Coverage is specific to the entity, topic, field, and period. `grain-coverage.md` records
topic availability; a registered topic does not guarantee a populated result. Historical
coverage notes in the tables are clues to check, not current counts or reasons to skip a
requested measure automatically. Retrieval recovery and selection of related geography
belong to `data-access.md`.

A wider geography can provide context but does not measure the original subject. A
benchmark ratio is not actual property expenses, an AVM is not an observed sale, and a
median is not a replacement mean. If an alternative helps, label the changed measure and
population. Omit irrelevant NULLs; acknowledge requested or consequential gaps near the
affected answer, following `../output-conventions.md`.

## Geographic entity topics

Grains: centum, zipcode, neighborhood, census_place, submarket, county, market, state,
nation. Availability varies per topic — see `grain-coverage.md`.

### Demographics & household economics

| Topic | Purpose / when to use | Filters | Key fields & caveats |
|---|---|---|---|
| `demographic_basics` | Population, households, age, tenure, labor force, supply growth. Baseline context for any market/site prompt. All 9 geo grains. | none | `population`, `households`, `owner_occupied_unit_pct`, `rental_occupied_unit_pct`, `population_growth`, `job_growth_1_year`, `housing_supply_growth_1_year`, `hhi_median`, `education_score_avg`, `mobility_score` |
| `household_financials_snapshot` | Income + wealth for comps/benchmarks (replaced old `household_income`/`household_wealth`). | none | `hhi_avg`, `hhi_median_acs`, `hhi_renter_median`, `hhi_pct_*` brackets, `net_worth_tier_avg`, `net_worth_tier_median`, `wealth_resources_tier_avg`, `liquid_resources_tier_avg`. Note: `hhi_median` itself lives in the detail/`demographic_basics` sets. |
| `household_financials_detail` | Single-geography income/wealth deep dive: all brackets, trend + benchmark variants, wealth tier components, short-term liability tiers. | none | `hhi_median_msa_zscore`, `hhi_median_natl_pctile`, `net_worth_pct_*` distribution, `investment_resources_tier_*`, `short_term_liability_tier_*` |
| `household_income_ts` ★ | Median household income **over time** with national and MSA benchmarks, split all households / renters / owners. All 9 geo grains **plus `property_mfr`**. The renter/owner split is the high-signal read for rent-to-income trajectory. | No schema-required filter; constrain subject `id`. **No `period_type`** | `report_date`, `hhi_median`, `hhi_renter_median`, `hhi_owner_median`, `hhi_median_natl_indicator/pctile/zscore`, `hhi_median_msa_indicator/pctile/zscore` |
| `credit_profile_snapshot` | Area credit health for comps/benchmarks: FICO, tiers, DTI, utilization, collections, delinquencies. | none | `fico_score`, `fico_score_*_pct` tiers, `debt_to_income_ratio`, `current_balance_to_limit_ltd`, `num_collection_count_l12_mos`, `num_trades_delinquent_ltd`, `trade_balance_ltd` |
| `credit_profile_detail` | Current credit levels plus 3/6/12-month changes; live market fields verified 2026-09-18. | none | `fico_score`, `fico_score_conf`, `fico_score_t3_chg`, `fico_score_t6_chg`, `fico_score_t12_chg`, `num_adults_in_sample`. FICO changes are absolute points, not percent changes. |
| `credit_ts` ★ | Credit health **over time** — FICO, balances by trade type, delinquency and utilization rates. All 9 geo grains **plus `property_mfr`**, where it reads as tenant credit trajectory for a specific building. Use for direction; a latest verified series observation can also answer a level question. At a building, tenant-profile snapshots provide another current-level source when needed. | No schema-required filter; constrain subject `id`. **No `period_type`** | `report_date`, `credit_data_sample_size`, `fico_score`, `home_equity/credit_card/installment/mortgage/total_balance_avg`, `total_balance_ex_mortgage_avg`, `total_balance_past_due_avg`, `num_accts_past_due_avg`, `num_mortgage_delinquent_avg`, `num_repossessions_avg`, `months_since_latest_delinquency_avg`, `mortgage_delinquency_rate`, `past_due_rate`, `pct_accts_50_util`, `pct_accts_75_util`. Many metrics have a `_conf` companion; interpret it under the cohort reference. Key fields, not exhaustive. |
| `education` | Attainment + composite score. Also on `property_mfr` (tenant attainment). | none | `pct_bachelors_or_higher`, `pct_high_school_or_higher`, `score_avg`, `score_avg_natl_pctile`, `score_avg_msa_indicator` |
| `employment` | Industry / occupation mix, labor-force rates. | none | `ind_*` (13 industries), `occ_*` (4 occupation groups), `in_labor_force_rate`, `job_growth_1_year`, `job_growth_5_year` |
| `cultural_identity` | Ethnicity by ancestry, language, religion for residents (or a property's tenants via `mf_tenant_profile_detail`). | none | `ethnicity_*_pct`, `language_*_pct`, `religion_*_pct` |
| `migration` | In/out flows with migrant cohort profiles and top origins/destinations. Use flows for volume and paired cohort profiles for composition. | none | `net`, `net_pct` (+`_natl/_msa` benchmarks), `household_income_median_in/out/diff`, `net_worth_tiers_avg_in/out`, `education_score_avg_in/out`, `top_origin_area_*_id`, `top_destination_area_*_id`. **Data caveat: 0 rows / all-null at centum and nation** (historical column-stat observation; recheck live). |
| `demographic_samples` ★ (**hidden/deprecated**) | Household-level sample records. Hidden/deprecated; avoid in new work and use currently discoverable aggregate topics. | `id` (nation: none) | `est_household_income`, `fico_score`, `net_worth_range`, `age`, `mobility_score` |

### Housing supply, sales & values

| Topic | Purpose / when to use | Filters | Key fields & caveats |
|---|---|---|---|
| `home_sales_and_values_snapshot` | THE ownership-market topic: values, sale prices, affordability ratios, mortgage mix, down payment, 12-mo turnover, **plus** z-scores, natl/MSA percentiles, indicator flags. Per the manifest this single topic now carries what older docs split into "snapshot" and "detail" — **`home_sales_and_values_detail` does not exist**. | none | `est_value_median` (+`_t3/t6/t12/t3yr/t5yr_pct_chg`, `_natl/_msa_zscore/indicator/pctile`), `sale_price_median` (+same variants), `value_to_income_ratio`, `sale_price_to_income_ratio`, `pct_housing_stock_sold_t12`, `downpayment_pct_est_median`, `mortgage_rate_median`, `mortgage_type_pct_conv/fha/va` |
| `home_sales_and_values_ts` ★ | Monthly value/price/volume history: trajectory, cycles, appreciation. | none required. Data is monthly-only (`period_type` = `"MONTH"` in every row); **do not filter period_type** — it adds nothing and the manifest switch value (`"Month"`) is cased differently from the stored data. | `period_start_date`, `est_value_median`, `sale_price_median`, `pct_housing_stock_sold_t12`, `sample_completeness` (recent months = PARTIAL), sample sizes. Default sort: `period_start_date` desc. |
| `home_personas` ★ | Housing-stock composition by property type x decade built (multi-row). Vintage/renovation context. Not on nation. | `id` | `decade_built`, `property_use_standardized(_desc)`, `num_homes`, `pct_of_housing_stock`, `median_sqft`, `median_lot_size_acres`, `mode_bed_count`, `mode_bath_count` |
| `supply_snapshot` | Current MF/resi supply conditions: vacancy, absorption, pipeline, trailing permits. **Market grain only.** Registered in the verified inventory. | none | `mf_vacancy_rate_pct`, `mf_net_absorption_units`, `mf_under_construction_units`, `mf_deliveries_ytd_units`, `mf/sfr/total_units_permitted_t12` and `_t13_t24`, `cap_rate_multifamily` |
| `home_price_mortgage_ts_by_gen` ★ | Home purchase price, downpayment share and mortgage rate **by generational cohort** over time. **`market` and `nation` only.** The affordability-by-generation read: who is buying, at what price, with what down payment. | No schema-required filter; constrain subject `id` and dates. | `date_of_report`, `generation` (Gen Z / Millennial / Gen X / Boomer), `purchase_sample_size`, `share_of_purchases(_t12_pct_chg)`, `purchase_price_avg/median(_t12_pct_chg)`, `downpayment_pct_avg/median(_t12_chg)`, `mortgage_sample_size`, `mortgage_rate_avg/median(_t12_chg)`. **Primary key includes `generation`, so a query returns one row per cohort per date** — a panel, not a series. Filter or pivot client-side. |
| `permit_ts` ★ | Trailing permit time series — the forward-supply leading indicator (12-24 mo out). census_place / county / market / state only; finer grains pull the parent and caveat. | `id` only. **Never filter `period_type`** (data is single-valued `"MONTHLY"`; adding the filter historically 400s — D12). | `sf_units_permitted`, `mf_units_permitted`, `total_units_permitted`, each with `_t12`, `_t13_t24`, `_t25_t36` trailing windows. **Key is `sf_units_permitted`, not `sfr_units_permitted`** (see field traps). |

### Multifamily & SFR rent (geo grain)

| Topic | Purpose / when to use | Filters | Key fields & caveats |
|---|---|---|---|
| `mf_rent_and_occupancy_snapshot` | MF comp-set/benchmark baseline: asking + in-place rents (mean, median, per-sqft, per-bedroom), occupancy, tradeouts, retention, rent-to-income. Not at centum. Also on `property_mfr`. | none | `asking_rent_latest(_median)`, `asking_rent_sqft_latest`, `asking_rent_latest_0_bed`...`_4_bed`, `in_place_rent_latest(_median)`, `occupancy_latest`, `*_t3/t6/t12_pct_chg`, `rent_to_income_ratio`, `retention_rate`, `tradeout_new_lease_pct_avg`, `sample_size` |
| `mf_rent_and_occupancy_detail` | Single-subject deep dive: all snapshot fields + 3/6/12-mo historical levels, leasing activity, benchmark pctiles. | none | `asking_rent_3mo/6mo/12mo_ago`, `occupancy_3mo/6mo/12mo_ago`, `num_leases_signed_past_30d`, `days_on_market_leases_signed_past_30d`, `tradeout_new_lease_amt/pct` + change series |
| `mf_rent_ts` ★ | MF aggregate rent/occupancy time series. The only MF rent TS with `unit_count` and `occupancy_latest`. | `period_type` = `"MONTH"` \| `"WEEK"` \| `"DAY"` (**ALL-CAPS** — manifest switch + data both uppercase; older docs' `"Month"`/`"Week"` is stale) | `asking_rent_latest(_median)`, `in_place_rent_latest(_median)`, `asking_rent_sqft_latest`, `num_vacant_units`, `num_leases_signed`, `days_on_market`, `tradeout_new_lease_amt/pct_avg`, `unit_count`, `occupancy_latest` |
| `mf_rent_ts_by_beds` ★ | Same series per bedroom count. Unit-type spread over time. | `period_type` = `"MONTH"` \| `"WEEK"` \| `"DAY"` | shared rent fields + `num_bedrooms` (no unit_count/occupancy) |
| `mf_rent_ts_by_beds_baths` ★ | Same, per bed x bath config. Floor-plan granularity; usually single-property territory. | `period_type` = `"MONTH"` \| `"WEEK"` \| `"DAY"` | shared rent fields + `num_bedrooms`, `num_full_baths` |
| `sfr_rent_snapshot` ★ | Current SFR rents by unit category (property type x bedrooms); multi-row. The SFR comp/benchmark topic. Not at centum. | `id` (nation: no required filter) | `unit_category(_label)`, `asking_rent_latest`, `asking_rent_sqft_latest`, `in_place_rent_latest`, `num_leases_signed_past_30d`, `days_on_market_leases_signed_past_30d` |
| `sfr_rent_ts` ★ | SFR aggregate rent time series. | `period_type` = `"Month"` \| `"Week"` (**Title Case** — differs from the MF family. Older docs' `"Quarter"` is stale: current manifest + data are Month/Week.) | `asking_rent_latest`, `in_place_rent_latest`, per-sqft variants, `num_vacant_units`, `days_on_market`, `tradeout_new_lease_amt/pct_avg` |
| `sfr_rent_ts_by_unit_category` ★ | SFR rent time series per unit category. | `period_type` = `"Month"` \| `"Week"` | same + `sfr_unit_category(_label)` |

### Cap rates, commercial, behaviors

| Topic | Purpose / when to use | Filters | Key fields & caveats |
|---|---|---|---|
| `caprate_ts` ★ | Quarterly cap-rate series by asset class. Valuation/exit assumptions. **Market grain only.** | `id` only per manifest. `period_type` is single-valued `"QUARTERLY"` — filtering it is unnecessary (older docs said it was required; the manifest does not). | `period_start_date`, `quarter`, `multifamily`, `industrial`, `office`, `retail_strip/neighborhood/power_center`, `self_storage`, `senior_housing`, `single_family_rental`. **Coverage: ~42 institutional markets** (3,698 rows); other market ids return `data: []`. `multifamily` ~99% populated; `single_family_rental` ~53% populated — MF is the reliable field. Topic description says "monthly" but data is quarterly. |
| `commercial_market` | Vacancy, absorption, deliveries, under-construction, cap rates for industrial/office/retail. **Market grain only.** Registered in the verified inventory. | none | `ind/off/ret_vacancy_rate_pct`, `*_net_absorption_sqft`, `*_deliveries_ytd_sqft`, `*_under_construction_sqft`, per-class cap rates |
| `top_consumer_behaviors` ★ | Ranked spending/lifestyle categories (23 pairs) + deviation vs. market. Persona building, retail siting, tenant marketing. Grains: centum, zipcode, neighborhood, census_place, market (+ `property`, `property_mfr`). NOT submarket/county/state/nation. | `id` | `<category>` label + `<category>_value` per category (e.g. `dining_style`, `travel_style`, `tech`); `<category>_deviation` at sub-market grains. Centum table now has ~2.5M rows (the old "0 rows at centum" claim appears resolved — verify live). |

---

## property_mfr topics (multifamily property)

Entity for ~200K+ MF communities; `id` = property_id. 18 visible topics.

| Topic | Purpose / when to use | Filters | Key fields & caveats |
|---|---|---|---|
| `mf_property_attributes` | Physical profile: year built, stories, units, unit mix, ratings. Anchors per-unit math in any single-property analysis. | none | `year_built`, `year_renovated`, `unit_count`, `unit_size_sqft`, `num_stories`, `bldg_count`, `total_rentable_sqft`, `property_type`, `rent_type`, `improvements_rating`, `location_rating`, `latest_sale_date/price(_per_unit)` |
| `mf_rent_and_occupancy_snapshot` / `_detail` | Same manifests as the geo versions, read at the property. Snapshot to screen/compare properties; detail for the single subject. | none | see geo table above |
| `mf_property_financials` | Property P&L dollar lines + ratios. | none | `mf_pnl_gross_potential_rent`, `mf_pnl_net_rent`, `mf_pnl_vacancy_loss`, `mf_pnl_effective_gross_income`, `mf_pnl_net_operating_income`, `mf_pnl_total_operating_expenses`, expense lines + `_pct_of_egi` ratios, `tax_amt`. **Data caveat (D7, still true):** rent lines ~51-61% populated; NOI / OpEx / CapEx ~92% null. Treat expense-side output as partial. |
| `mf_pnl_benchmarks` | P&L expense/income lines as % of EGI or net rent — benchmark ratios. Also at county and market grain for area benchmarking. **Not documented in older prose refs (newer topic).** | none | `mf_pnl_net_operating_income_pct_of_egi`, `mf_pnl_total_operating_expenses_pct_of_egi`, per-line `*_pct_of_egi`, `mf_pnl_other_income_pct_of_net_rent`, `mf_pnl_financials_sample_size` |
| `mf_tenant_profile_snapshot` | Tenant demographics + income/wealth + core credit for screening/comparing properties. Replaced old `tenant_basics` / `property_credit_profile`. | none | `hhi_median`, `hhi_pct_*`, `net_worth_pct_*`, `net_worth_tier_avg`, `fico_score`, `debt_to_income_ratio`, `rent_to_income_ratio`, `rent_to_fico`, `gender_*_pct`, `marital_*_pct`, `mobility_score` |
| `mf_tenant_profile_detail` | Single-property tenant deep dive: + credit trend series (3/6/12-mo), full wealth tiers, cultural identity breakdown. | none | credit `*_t3/t6/t12_pct_chg` series, `*_tier_median(_range)`, ethnicity/language/religion fields. Credit fields at property grain are ~63% populated in historical stats (verify current coverage). |
| `education` | Tenant educational attainment (same manifest as geo). | none | see geo table |
| `mf_amenities` | Community + in-unit amenity lists. | none | `community_amenities`, `unit_amenities` |
| `mf_tax_and_assessment` | Tax + assessed values. | none | `tax_year`, `tax_amt(_per_unit)`, `tax_amt_pct_of_egi`, `assessment_value_total/land/improvements(_per_unit)` |
| `mf_sales_history` | Prior trades. | none | `latest_sale_date`, `latest_sale_price`, `latest_sale_price_per_unit` |
| `mf_ownership_and_management` | Owner chain + manager. | none | `true_owner_name`, `fee_owners`, `property_mgr_name` |
| `rent_roll_latest` ★ | Most-recent unit-level rent roll (window-function "latest row per unit"). Start here for unit-level questions. **property_mfr only.** | `period_type` = `"MONTH"` \| `"WEEK"` \| `"DAY"` (ALL-CAPS) | `unit_number`, `num_bedrooms`, `num_full_baths`, `unit_size_sqft`, `occupancy_status`, `availability_status`, `asking_rent_latest`, `in_place_rent_latest`, `previous_in_place_rent`, `tradeout_new_lease_amt/pct`, `days_on_market`, `listed_date`, `leased_date`, `inferred_move_in_date`. (Key is `unit_number` — older docs' `unit_name`/`occupancy_indicator` are not manifest keys.) |
| `mf_rent_roll_ts` ★ | Same schema, full history per unit. High volume — prefer `rent_roll_latest` unless history is needed. **property_mfr only.** | `period_type` = `"MONTH"` \| `"WEEK"` \| `"DAY"` | same as above + `period_start_date` (default sort desc) |
| `mf_rent_ts` / `_by_beds` / `_by_beds_baths` ★ | Property-level rent time series (same manifests as geo). | `period_type` = `"MONTH"` \| `"WEEK"` \| `"DAY"` | see geo table |
| `top_consumer_behaviors` ★ | Tenant behavior profile; dual-compare against the same topic at the surrounding geography. | `id` | see geo table |
| `demographic_samples` ★ (hidden) | Deprecated; avoid. | `id` | — |

---

## property_residential topics (single-family)

All inherited (no ★, no required filters). `id` = property_id; use the shared retrieval workflow.

| Topic | Purpose | Key fields |
|---|---|---|
| `res_property_attributes` | Physical characteristics, identifiers. | `year_built`, `bedrooms_count`, `bath_count`, `stories_count`, `decade_built`, `attom_id`, `parcel_number` |
| `res_property_area` | Size measurements. | `area_building_sqft`, `area_lot_sqft`, `area_lot_acres`, `area_gross_sqft`, garage/porch/patio/deck/pool sqft |
| `res_home_valuation` | AVM value + confidence, current + prior 5 years. | `est_value_current_avg`, `confidence_score_current_avg`, `est_value_2yr_ago_avg`...`_5yr_ago_avg`, `est_value_pct_chg_from_*` |
| `res_sales_history` | Transactions. | `sale_latest_date/price_per_assessor`, `sale_latest_date/price_per_deed`, `sale_prior_date/price_per_assessor` |
| `res_tax_and_assessment` | Tax + assessed/market values. | `tax_billed_amount`, `tax_assessed_value_total/land/improvements`, `tax_market_value_*` |

## property (master entity)

126M+ properties; location + classification only. One topic: `top_consumer_behaviors` ★
(requires `id`). For anything analytic use `property_mfr` (MF) or `property_residential`
(SFR) — both join 1:1 via property_id. Useful identity fields: `address`,
`property_category` (RESIDENTIAL / MULTIFAMILY / OTHER), `latitude`, `longitude`,
plus the full geographic FK ladder.

## National / macro entities

Each is its own entity carrying exactly one topic of the same name. No geographic
filter; keyed by `period_start_date` (NOT `id`). `mortgage_rates` is keyed by
`loan_name`. Backdrop only — never the answer to a local question.

| Entity = topic | Cadence | Key fields |
|---|---|---|
| `national_metrics_daily` | daily | `sofr`, `ten_year_treasury_pct`, `sp500_index`, `nasdaq_composite_index`, `five_year_breakeven_pct`, `ten_year_break_even_rate` |
| `national_metrics_monthly` | monthly | `unemployment_rate`, `cpi_rate`, `fed_funds_rate`, `mortgage_rate_30yr_fixed`, `mortgage_rate_15yr_fixed`, `case_shiller_index`, `housing_supply_starts/permits`, `housing_inventory_existing`, `housing_affordability_index` |
| `national_metrics_quarterly` | quarterly | `gross_domestic_product`, `homeownership_pct`, `median_home_price_dollars`, `rental_vacancy_rate`, `commercial_real_estate_loan_delinquency_rate`, `all_tx_house_price_index` |
| `national_metrics_annual_projection` | yearly | `fed_funds_rate_low/median/high_projection` |
| `national_metrics_monthly_projection` | monthly fwd | `sofr_1m_projection`, `sofr_3m_projection`, `as_of_date` |
| `mortgage_rate_snapshot` (on entity `mortgage_rates` — the entity and topic names differ; see failure modes) | current | `loan_name` (PK), `loan_type`, `property_type`, `loan_term`, `interest_rate_pct_min/max/avg`, `spread_bps_*`, `loan_to_value_*`, `dscr`. Commercial/MF loan programs (Fannie, Freddie, Life Co, CMBS...), not consumer 30-yr quotes — those live in `national_metrics_monthly`. |

All five national_metrics topics default-sort `period_start_date` desc.

---

## Disambiguation rules

The recurring ambiguities that route a query to the wrong topic:

1. **Whose profile.** Geographic topics describe everyone living in the area;
   `mf_tenant_profile_*` describes one property's tenants. Subject-vs-area analyses
   need both (e.g. `mf_tenant_profile_detail` at the property + `credit_profile_snapshot`
   / `household_financials_snapshot` at the surrounding geography).
2. **Which asset class.** `mf_*` = apartments; `sfr_*` = single-family rentals;
   `home_sales_and_values_*` and `home_personas` = the for-sale / owner-occupied stock.
   "The rental market" unqualified usually means MF + SFR; "home prices" means the
   ownership topics.
3. **Which data shape.** snapshot = concise comparisons; detail = richer components;
   ts = movement over time. Deep dives: detail at the subject, snapshot at the
   benchmark. Pulling detail across a comp set wastes budget; a snapshot cannot fill
   a trend section.
4. **Supply vs. pipeline vs. commercial.** Current resi/MF conditions =
   `supply_snapshot`; trailing permits as the forward-supply signal = `permit_ts`;
   industrial/office/retail = `commercial_market`; historical supply-growth context =
   `demographic_basics`.
5. **Local vs. national.** `national_metrics_*` and `mortgage_rate_snapshot` are
   backdrop only — they never answer a local question. For apples-to-apples national
   comparison use the nation-grain geographic topics.
6. **Valuation of what.** A house = `res_home_valuation`; an MF asset =
   `mf_property_financials` + `mf_sales_history` + `caprate_ts`; an area's stock =
   `home_sales_and_values_snapshot` / `_ts`.
7. **Relevance.** Include a topic when it helps answer the question. Expand only when
   an unresolved question needs more evidence.

Family-specific splits the master rule does not cover:

- MF rent TS: `mf_rent_ts` = aggregate (only one with `occupancy_latest`/`unit_count`);
  `_by_beds` = bedroom mix; `_by_beds_baths` = floor-plan granularity.
- Rent roll: `rent_roll_latest` = current unit-level picture; `mf_rent_roll_ts` =
  unit history over time (high volume).
- SFR: `sfr_rent_snapshot` = current state by unit type; `sfr_rent_ts` = aggregate
  trend; `sfr_rent_ts_by_unit_category` = trend by unit type.
- Rent/occupancy point-in-time trend context: `mf_rent_and_occupancy_detail` carries
  3/6/12-mo lookbacks in one row — use it before spinning up a full `mf_rent_ts` pull
  when the question is merely directional.

## Question-specific topic selection

Domain references explain which evidence helps a particular question. They are not
mandatory retrieval bundles:

- Transactions: `${CLAUDE_PLUGIN_ROOT}/skills/realai-underwriting/references/`
- Buildings and operations: `${CLAUDE_PLUGIN_ROOT}/skills/realai-multifamily/references/`
- Geographies: `${CLAUDE_PLUGIN_ROOT}/skills/realai-market-research/references/`
- Household profiles: `${CLAUDE_PLUGIN_ROOT}/skills/realai-supercensus/references/topics.md`

## Field conventions

Trailing-change suffixes such as `_t3_pct_chg`, `_t6_pct_chg`, and `_t12_pct_chg` identify
windows; check units and actual definitions. Absolute `_chg` and percentage `_pct_chg`
are different. Benchmark and confidence interpretation belongs to the cohort reference.
Bedroom, bath, generation, and unit-category dimensions can create multiple rows per
entity/date; preserve those dimensions before aggregating or plotting.

## Known traps

### Topic names that do not exist (400 / null output)

| Hallucinated | Use instead |
|---|---|
| `property_summary`, `property_mfr_summary`, `mf_property_details` | `mf_property_attributes` + `mf_rent_and_occupancy_snapshot` |
| `financials` | `mf_property_financials` |
| `mf_occupancy_ts` | `mf_rent_ts` (carries `occupancy_latest` + `unit_count`) |
| `tenant_profile`, `tenant_basics`, `property_credit_profile` | `mf_tenant_profile_snapshot` / `_detail` |
| `mortgage_rates` used as a topic | topic `mortgage_rate_snapshot` on entity `mortgage_rates` |
| `mf_fundamentals`, `mf_supply`, `mf_demand`, `mf_investment_snapshot`, `mf_unit_mix_rent` | do not exist |
| `household_income`, `household_wealth` | merged into `household_financials_snapshot` / `_detail` |
| `home_sales_and_values_detail` | **documented in older prose refs but NOT in the manifest.** `home_sales_and_values_snapshot` is the complete dataset (z-scores, pctiles, indicators included). |

### Field-name traps (manifest key wins)

| Trap | Correct manifest key | Note |
|---|---|---|
| `median_household_income`, bare `median` | `hhi_median` (demographic_basics, household_financials_detail, mf_tenant_profile_*); `hhi_median_acs` / `hhi_avg` / `hhi_renter_median` in household_financials_snapshot | The old `household_income.median` key is gone with the topic rename. |
| `sfr_units_permitted` (in `permit_ts`) | `sf_units_permitted` (+`_t12`, `_t13_t24`, `_t25_t36`) | Direction flipped vs. older docs: today's permit_ts keys are `sf_/mf_/total_units_permitted`. `sfr_units_permitted_t12` is a `supply_snapshot` key — different topic. |
| `asking_rent_sqft` | `asking_rent_sqft_latest` | mf_rent_and_occupancy_*, rent TS families |
| `in_place_rent` | `in_place_rent_latest` | same families; `in_place_rent_latest_median` for the median |
| `occupancy` / `occupancy_rate` | `occupancy_latest` | snapshot + mf_rent_ts |
| `unit_name`, `occupancy_indicator` (rent roll) | `unit_number`, `occupancy_status` | rent_roll_latest / mf_rent_roll_ts |
| period_type casing | MF rent TS + rent roll = ALL-CAPS `"MONTH"`/`"WEEK"`/`"DAY"`; SFR TS = Title Case `"Month"`/`"Week"`; caprate data = `"QUARTERLY"`; permits = never filter | Casing mismatch → 400 (switch validation) or zero rows. |

