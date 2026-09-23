# RealAI Grain Coverage & Required Filters

Derived directly from `entities/*.ts` topic registrations (manifests @ origin/main
2026-07-22), with topic registrations rechecked at local origin/main `f03a27d` on
2026-09-18. Field enum values retain their original verification date; live discovery
controls current calls. ★ marks `separate_data_source: true`; query construction follows
`data-access.md`. Blank means not registered at that grain.

## Contents

- [Geographic entity x topic matrix](#geographic-entity-x-topic-matrix)
- [Required filters](#required-filters-exact-values-and-casing-from-manifests--column-stats)
- [Entity primary keys and identity notes](#entity-primary-keys--identity-notes)

## Geographic entity x topic matrix

cen=centum zip=zipcode nbhd=neighborhood cp=census_place sub=submarket cty=county
mkt=market sta=state nat=nation

| Topic | cen | zip | nbhd | cp | sub | cty | mkt | sta | nat |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| demographic_basics | x | x | x | x | x | x | x | x | x |
| household_financials_snapshot | x | x | x | x | x | x | x | x | x |
| household_financials_detail | x | x | x | x | x | x | x | x | x |
| credit_profile_snapshot | x | x | x | x | x | x | x | x | x |
| credit_profile_detail | x | x | x | x | x | x | x | x | x |
| credit_ts ★ | x | x | x | x | x | x | x | x | x |
| household_income_ts ★ | x | x | x | x | x | x | x | x | x |
| home_price_mortgage_ts_by_gen ★ | | | | | | | x | | x |
| education | x | x | x | x | x | x | x | x | x |
| employment | x | x | x | x | x | x | x | x | x |
| cultural_identity | x | x | x | x | x | x | x | x | x |
| migration (0 rows cen/nat) | x | x | x | x | x | x | x | x | x |
| home_sales_and_values_snapshot | x | x | x | x | x | x | x | x | x |
| home_sales_and_values_ts ★ | x | x | x | x | x | x | x | x | x |
| home_personas ★ | x | x | x | x | x | x | x | x | |
| mf_rent_and_occupancy_snapshot | | x | x | x | x | x | x | x | x |
| mf_rent_and_occupancy_detail | | x | x | x | x | x | x | x | x |
| mf_rent_ts ★ | | x | x | x | x | x | x | x | x |
| mf_rent_ts_by_beds ★ | | x | x | x | x | x | x | x | x |
| mf_rent_ts_by_beds_baths ★ | | x | x | x | x | x | x | x | x |
| sfr_rent_snapshot ★ | | x | x | x | x | x | x | x | x |
| sfr_rent_ts ★ | | x | x | x | x | x | x | x | x |
| sfr_rent_ts_by_unit_category ★ | | x | x | x | x | x | x | x | x |
| permit_ts ★ | | | | x | | x | x | x | |
| mf_pnl_benchmarks | | | | | | x | x | | |
| supply_snapshot | | | | | | | x | | |
| commercial_market | | | | | | | x | | |
| caprate_ts ★ (~42 covered markets) | | | | | | | x | | |
| top_consumer_behaviors ★ | x | x | x | x | | | x | | |
| demographic_samples ★ (hidden) | x | x | x | x | x | x | x | x | x |

Property entities: `property` = top_consumer_behaviors ★ only. `property_mfr` =
mf_tenant_profile_snapshot/detail, education, mf_rent_and_occupancy_snapshot/detail,
mf_property_attributes, mf_property_financials, mf_pnl_benchmarks, mf_tax_and_assessment,
mf_sales_history, mf_ownership_and_management, mf_amenities (inherited) + mf_rent_roll_ts ★,
rent_roll_latest ★, mf_rent_ts ★, mf_rent_ts_by_beds ★, mf_rent_ts_by_beds_baths ★,
top_consumer_behaviors ★, demographic_samples ★, **credit_ts ★, household_income_ts ★**
(hidden: demographic_samples). Note `credit_ts` and `household_income_ts` at
`property_mfr` read as tenant credit and income trajectories for that specific building. Tenant-profile
snapshots remain useful for current levels; use history when direction matters. `property_residential` =
res_property_attributes, res_property_area, res_sales_history, res_tax_and_assessment,
res_home_valuation (all inherited). National entities carry one same-named topic each:
`national_metrics_daily`, `national_metrics_monthly`, `national_metrics_quarterly`,
`national_metrics_annual_projection`, `national_metrics_monthly_projection`;
`mortgage_rates` = mortgage_rate_snapshot.

## Required filters (exact values and casing, from manifests + column stats)

The table distinguishes schema-required filters from useful subject constraints. Topics
not listed have no registered required filters in the verified manifests. That does not
make an unconstrained scan appropriate: use the bounds in `data-access.md`. Table field
names are shorthand; live discovery supplies the exact query paths and current values.

| Topic | Required filter field | Recorded value(s) or constraint note |
|---|---|---|
| mf_rent_ts | period_type | `"MONTH"` \| `"WEEK"` \| `"DAY"` (ALL-CAPS) |
| mf_rent_ts_by_beds | period_type | `"MONTH"` \| `"WEEK"` \| `"DAY"` |
| mf_rent_ts_by_beds_baths | period_type | `"MONTH"` \| `"WEEK"` \| `"DAY"` |
| mf_rent_roll_ts | period_type | `"MONTH"` \| `"WEEK"` \| `"DAY"` |
| rent_roll_latest | period_type | `"MONTH"` \| `"WEEK"` \| `"DAY"` |
| sfr_rent_ts | period_type | `"Month"` \| `"Week"` (Title Case; old `"Quarter"` is stale) |
| sfr_rent_ts_by_unit_category | period_type | `"Month"` \| `"Week"` |
| permit_ts | id | — (`id` only; NEVER filter period_type — data is single-valued `"MONTHLY"`) |
| caprate_ts | id | — (`id` only; period_type not required — single-valued `"QUARTERLY"`) |
| home_personas | id | — |
| credit_ts | (none) | No registered required filters at any supported grain; constrain subject `id` and relevant dates. No period_type. |
| household_income_ts | (none) | No registered required filters at any supported grain; constrain subject `id` and relevant dates. No period_type. |
| home_price_mortgage_ts_by_gen | (none) | No registered required filters at market or nation; constrain subject `id` and dates. One row per generation per date. |
| top_consumer_behaviors | id | — |
| sfr_rent_snapshot | id | — (exception: nation registration has no required filter) |
| demographic_samples (hidden) | id | — (exception: nation has no required filter) |
| home_sales_and_values_ts | (none) | no required filter on any entity; data is monthly-only — do not filter period_type |

Casing errors fail two ways: a value outside the manifest switch list → 400; a value
with wrong case that passes validation → zero rows. Copy values verbatim.

## Entity primary keys & identity notes

- Geographic entities and all property entities use `id` as the filter field. Under
  the hood: market id = `msa_cbsa_fips_code` (CBSA FIPS, e.g. Atlanta = "12060"),
  state id = state FIPS, zipcode id = 5-digit ZIP (ZCTA), county id = `county_geo_id`,
  centum id = `full_centum_id`, property/property_mfr/property_residential id =
  `property_id`. The AI always sends `"id"` — never the SQL column name.
- Market names are stored as "City, ST" (e.g. "Chicago, IL"), not full CBSA titles;
  resolve names to ids via entity_search rather than name filters. Market has no
  state dimension.
- Use the foreign keys actually exposed for an entity (`market_id`, `county_id`,
  `state_id`, ...) for parent-based screens. Geographic grains do not form a universal
  nesting ladder; do not infer a parent relationship from grain names alone.
- National entities (`national_metrics_daily/monthly/quarterly/annual_projection/`
  `monthly_projection`) are keyed by `period_start_date` — there is no `id`; filter
  by date (all default-sort period_start_date desc).
- `mortgage_rates` is keyed by `loan_name` (e.g. "Fannie Mae - Conventional");
  `loan_type` and `property_type` are the other identity fields. No `id`.
- Grain fallbacks: caprate_ts / supply_snapshot / commercial_market → market only;
  permit_ts → census_place/county/market/state; top_consumer_behaviors → not at
  submarket/county/state/nation; centum has no MF/SFR rent topics (rent starts at
  zipcode); home_personas not at nation. Use a verified broader relationship only when
  it helps answer the question, and label the geography actually measured.
