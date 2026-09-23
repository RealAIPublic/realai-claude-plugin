# Interpreting RealAI evidence

Use the sections relevant to the question. These are analytical considerations, not
universal thresholds or a checklist every answer must fill. Query mechanics belong in
`data-retrieval/data-access.md`; household tier and confidence semantics belong in
`${CLAUDE_PLUGIN_ROOT}/skills/realai-supercensus/references/cohort-interpretation.md`.

## Compare like with like

Compare compatible geography, asset type, units, observation period, and sample. Built-in
percentiles and indicators can provide a useful benchmark without a new peer pull. Read
their reference population and direction: above average does not always mean favorable.
A small percentage gap can still be material for occupancy, cap rates, or debt coverage;
do not use one outlier threshold for every metric.

Separate level, change, and uncertainty. A low trend-fit statistic means the fitted
trend is unreliable; it does not establish that the series is flat. A recent arm's-length
sale is relevant valuation evidence, but its terms, condition, and date determine its
weight relative to today's comparable sales.

## Property operations

In-place rent describes existing leases; asking rent describes advertised new pricing.
Their spread can suggest loss-to-lease or pressure on new rents, but concessions, unit mix,
lease dates, and renovations can also explain it. Achievable rent needs comparable units
and leasing evidence. Do not equate asking rent with collected or effective rent.

Read occupancy, retention, leasing velocity, and tradeouts together. High retention with
negative tradeouts can indicate weaker new-lease pricing despite a stable resident base.
Low retention with negative tradeouts warrants investigating both demand and operations.
Neither combination proves a supply or management cause without corroboration.

A low mobility score indicates greater expected movement; a high score indicates greater
stability. Compare actual turnover with that baseline before attributing churn to an
operator. A current credit score cannot establish an improving or deteriorating tenant
base; use matching observations or the appropriate change series.

Expense comparisons need consistent denominators and accounting. Separate controllable
costs from taxes, insurance, utilities, building systems, and service differences. Compare
both dollar magnitude and per-unit or income-share measures. A modeled benchmark is not
an audit of actual expenses.

## Household economics and migration

A rent equal to 30% of gross income is a conventional burden benchmark, not a hard ceiling
on attainable rent. Keep annual income and monthly rent on compatible units, and use
renter income when considering renters. Household medians do not describe every resident.

Renter-owner income differences and distribution shape can reveal market segmentation;
they do not establish why people choose to rent. A high Gini indicates inequality, not a
specific two-group distribution. Inspect brackets before describing a barbell.

For migration, distinguish net flow from who arrives and leaves. Compare income, wealth,
age, and education using the same periods and cohort definitions. Higher inbound income
can support a stronger-demand hypothesis; it is not proof of rent growth or capital inflow.
Ordinal wealth tiers cannot be summed as dollars. Distance moved and origins/destinations
help distinguish local churn from broader relocation. Resolve geographic IDs when the
origin or destination itself is part of the question.

## Housing supply

Keep historical housing-stock growth, permits, units under construction, and deliveries
separate. Permits are authorizations, not guaranteed completions. Compare matched trailing
windows and account for reporting lag, cancellations, and construction timing. Separate
single-family and multifamily counts. Current absorption and available inventory help
interpret how much of a pipeline the market can accommodate.

Use market-level supply as context for a smaller geography, not as its measured pipeline.
An ownership-market series and a rental-market series may describe different populations.

## Consumer behavior

Use aggregate behavior indices only when they help answer the question. Explain relative
patterns using the documented baseline; an index is not automatically a probability or
percentage of residents. Group related signals cautiously and identify interpretation as
such. Food, travel, and spending signals alone do not establish someone's age, wealth,
motives, creditworthiness, or renewal likelihood.

## Data quality and synthesis

Inspect sample sizes, coverage, confidence intervals, and completeness before relying on
a surprising result. Corroboration can strengthen an inference but does not erase sample
uncertainty. Explain a material limitation near the conclusion; omit irrelevant diagnostics.
Do not invent a cause for NULL values. Exclude or clearly distinguish incomplete periods
when assessing trends; a partial recent sales month must not create a false decline.

State what the data supports even when its cause is unknown. Distinguish observation from
hypothesis, and identify conflicting signals without manufacturing a distinctive story.
For a direct factual question, the factual answer is sufficient. For interpretation,
connect the strongest relevant evidence and explain the practical implication. Broadly
peer-like performance is a valid finding when the comparison actually supports it.
