# Topic availability by entity grain (canonical — do not restate in other skills)

| Topic | nation | state | market | submarket | county | census_place | zipcode | neighborhood | centum | property_mfr |
|---|---|---|---|---|---|---|---|---|---|---|
| demographic_basics / employment / education / cultural_identity | Y | Y | Y | Y | Y | Y | Y | Y | Y | education only |
| credit_profile_snapshot / _detail | Y | Y | Y | Y | Y | Y | Y | Y | Y | — |
| household_financials_snapshot / _detail | Y | Y | Y | Y | Y | Y | Y | Y | Y | — |
| migration | Y | Y | Y | Y | Y | Y | Y | Y | Y | — |
| home_sales_and_values_snapshot / _ts | Y | Y | Y | Y | Y | Y | Y | Y | Y | — |
| home_personas (id req.) | — | Y | Y | Y | Y | Y | Y | Y | Y | — |
| top_consumer_behaviors (id req.) | — | — | Y | — | — | Y | Y | Y | Y | Y |
| mf_rent_and_occupancy_snapshot / _detail | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y |
| mf_rent_ts / _by_beds / _by_beds_baths (period_type req.) | Y | Y | Y | Y | Y | Y | Y | Y | ts only | Y |
| mf_pnl_benchmarks | — | — | Y | — | Y | — | — | — | — | Y |
| sfr_rent_snapshot (id req.) / sfr_rent_ts (period_type req.) | Y | Y | Y | Y | Y | Y | Y | Y | — | — |
| permit_ts (id req.) | — | Y | Y | — | Y | Y | — | — | — | — |
| caprate_ts (id req.) | — | — | Y | — | — | — | — | — | — | — |
| supply_snapshot / commercial_market | — | — | Y | — | — | — | — | — | — | — |
| mf_rent_roll_ts / rent_roll_latest (period_type req.) | — | — | — | — | — | — | — | — | — | Y |
| mf_property_* , mf_tenant_profile_* , mf_amenities, mf_ownership_and_management, mf_sales_history, mf_tax_and_assessment | — | — | — | — | — | — | — | — | — | Y |

## Required filters (query fails without them)
- `period_type` IN [DAY, MONTH, WEEK]: mf_rent_ts, mf_rent_ts_by_beds, mf_rent_ts_by_beds_baths, mf_rent_roll_ts, rent_roll_latest
- `period_type` IN [Month, Week]: sfr_rent_ts, sfr_rent_ts_by_unit_category
- `id`: caprate_ts, permit_ts, home_personas, sfr_rent_snapshot, top_consumer_behaviors
- Topics marked separate_data_source must be queried alone (own call): caprate_ts, permit_ts, mf_rent_ts family, rent roll topics.

Re-run `explore_data` before relying on an exact field list; this matrix covers topic-level availability only
