# Interpreting household tiers, cohorts, and confidence

This reference owns household field semantics. Use the relevant section when those
fields matter; it is not a profile template. Tier descriptions were checked against live
`explore_data` fields for `household_financials_detail` on 2026-09-18. Schema descriptions
are definitions, not evidence of a particular household's finances.

## Contents

- [Tier scales and dollar bands](#tier-scales-and-dollar-bands)
- [Benchmarks and distributions](#benchmarks-and-distributions)
- [Confidence and sample evidence](#confidence-and-sample-evidence)
- [Migration cohorts](#migration-cohorts)
- [Generational cohorts](#generational-cohorts)

## Tier scales and dollar bands

These are proprietary ordinal buckets, not dollar values or interchangeable scores.
The table records the manifest's stated scale endpoints; use the returned range companion
for a subject's dollar band rather than constructing a complete numeric lookup from them.

| Field family | Stated scale | Low endpoint | High endpoint | Meaning |
|---|---|---|---|---|
| `net_worth_tier_*` | 0–11 | Under $25K or negative | $2M–$3M | Assets minus liabilities |
| `liquid_resources_tier_*` | 1–14 | Under approximately $500 | Over $75K | Cash, checking, savings |
| `investment_resources_tier_*` | 1–13 | Under approximately $5K | Over $500K | Stocks, bonds, funds, retirement assets |
| `wealth_resources_tier_*` | 1–9 | Under approximately $25K | $500K–$750K+ | Composite of liquid, investable, and property wealth |
| `short_term_liability_tier_*` | 1–8 | Under approximately $2,500 | $30K–$50K+ | Near-term debt; higher means greater burden |

Higher resource tiers mean more resources; a higher liability tier means more debt.
Reverse the latter's direction when a financial-strength composite requires higher to be
better. Never average raw tiers across families. A tier 9 on a 1–9 scale differs from a
tier 9 on a 1–14 scale. Percentile companions can support a consistently directed
comparison, with weights and computation handled under
`${CLAUDE_PLUGIN_ROOT}/shared/multi-entity-analysis.md`.

Prefer `*_tier_median_range` when supplied: it translates the median tier into its
supported dollar band. Do not interpolate dollars from an average tier such as 6.4;
bucket widths differ and the within-bucket distribution is unknown. A two-tier change
is not a constant dollar change. If a range and description conflict, retain the returned
band as labeled evidence and flag the definition issue only if it affects the answer.

The median describes a typical sampled household; the average tier summarizes the
ordinal distribution. Compare like statistics across populations. An average/median
gap can suggest skew, but inspect brackets before inferring concentrated wealth or a
specific distribution. It does not reveal the dollar magnitude of high-wealth outliers.

## Benchmarks and distributions

Use a benchmark when relative position helps the question; a direct factual lookup may
need only the level and date. Confirm the field's reference population and direction.

- `_natl_pctile` / `_msa_pctile`: percentile position in the documented national or metro
  comparison set. A percentile ranks areas or properties as defined; it is not the
  percent of individual households below that value.
- `_natl_zscore` / `_msa_zscore`: standardized distance from the benchmark mean.
- `_natl_indicator` / `_msa_indicator`: qualitative comparison, not the size of a gap.
  Above-average liabilities mean more debt, not stronger finances.

Income and wealth bracket shares describe composition that a median can hide. Read the
actual scale before converting a fraction to a percentage. Check whether bands are
exhaustive, non-overlapping, and share a denominator; do not silently normalize an
incomplete set to 100%. NULL bands are unknown, not zero. Compare matching brackets and
periods. Distribution charts are useful when their shape changes the interpretation.

## Confidence and sample evidence

A `*_conf` field may be a JSON object encoded as a string. The inspected historical
format includes `avg_ci_lower_97`, `avg_ci_upper_97`, `avg_std_error`,
`median_ci_lower_97`, `median_ci_upper_97`, `median_std_error`, `sample_size`, and `stddev`.
Parse the returned value and check which keys actually exist; some values contain only
`sample_size`. Do not sort or average the raw string or assume every confidence field
has this schema. A numeric model-confidence score is a different quantity.

Match the interval to the estimate: average bounds for an average, median bounds for a
median. For example, `fico_score` is described as an average in current credit fields;
do not call it a median because a median interval is also present. The `_97` keys denote
97% intervals. A wide interval or one crossing a decision threshold calls for a qualified
conclusion; the point estimate alone does not establish a clear threshold crossing.

Inspect confidence internally whenever it supports a consequential estimate. Report the
interval, sample count, or a plain-language qualification when uncertainty affects the
answer or the user requests it. Do not require every factual answer to print diagnostics.
Absent intervals do not establish high confidence, and `sample_size: 1` cannot support a
broad population conclusion.

Keep these field families distinct:

| Family | What it tells you |
|---|---|
| `sample_size`, `*_sample_size`, `num_adults_in_sample` | Count of observations, households, or adults as the field defines |
| `*_sample_coverage_pct` | Coverage share of the defined population, not a count or confidence interval |
| `*_sample_confidence` | Separate confidence marker; follow its live definition |
| `sample_completeness` | Whether a period is complete; partial recent periods can distort trends |
| `confidence_score_*`, `*_r_squared`, `*_trend_strength` | Model confidence or fit, not household sample coverage |

SuperCensus metadata describes ZIP+4 anonymization and possible insufficient-sample
coverage. That is a possible limitation, not an explanation for every NULL or empty row.
Use the recovery rules in `shared/data-retrieval/data-access.md`. Do not claim suppression without
supporting metadata or replace an unavailable property value with a geography's value.

## Migration cohorts

Match inbound and outbound definitions, periods, and units. Net migration answers how
much the population changed through movement; cohort profiles answer who moved. Let the
question determine which leads. Pair income, education, and comparable wealth families
when composition matters. Lower inbound liability tiers indicate less near-term debt
on that scale, but do not by themselves establish better overall financial health.

Higher inbound income alongside flat net movement can suggest changing demand composition.
It does not prove rent growth, greater total purchasing power, or a strengthening market.
Counts multiplied by medians are not total income, and ordinal wealth tiers cannot be
summed into dollar capital flows. Resolve origin/destination IDs when locations matter.

## Generational cohorts

`home_price_mortgage_ts_by_gen` is a housing topic, not a SuperCensus-sourced topic. It
returns a panel with generation and date. Keep generations separate when plotting or
aggregating; interleaving Gen Z, Millennial, Gen X, and Boomer rows is not one time series.
Purchase shares, prices, down payments, and sample sizes can show participation and terms,
using comparable periods. They do not measure all households' ability to buy a home.
