# Rental conditions, demand, and market fit

Use the parts relevant to the question. Rental dynamics, demand drivers, and investment
fit are related lines of inquiry; they are not response modes or mandatory report sections.
Topic names are starting points for the shared catalog; live schema controls field meaning.

## Rental conditions

Read asking versus in-place rents alongside achieved new-lease tradeouts. An asking premium
supported by tradeouts differs from the same premium when signed leases clear near existing
rents. Occupancy, days on market, retention, and concessions can explain the difference.
A geographic asking premium is not a building's recoverable loss-to-lease.

`mf_rent_and_occupancy_detail` is useful for this relationship. Add `mf_rent_ts` for history,
and bedroom-level series when an aggregate may hide unit-type divergence. Use SFR rent
snapshot/history for SFR questions; compare segments explicitly when both are relevant.
Retrieve household credit or liquidity evidence when affordability is consequential,
rather than adding it to every rent answer.

Compute derived measures in code from sourced values, with compatible units and periods:

| Measure | Interpretation and calculation |
|---|---|
| Asking versus in-place spread | `(asking - in_place) / in_place`; denominator must be positive and both rents comparable |
| Trailing rent change | Latest rent divided by the matching earlier period, minus one; distinguish this from tradeout growth |
| Occupancy change | Difference in percentage points, not percent growth; align periods |
| Leasing velocity | Days on market and tradeouts alongside their lease counts; fewer than 30 signed leases is a cautionary screen, not proof of statistical reliability |
| MF affordability | Use the supplied rent-to-income measure after checking its population and definition |
| SFR affordability proxy | Monthly rent × 12 / annual household income; identify whether household income represents renters, owners, or all households |

Rent-to-income near 30% or 40% can prompt closer scrutiny, but these are screening
heuristics, not hard rent ceilings. Combine affordability with DTI direction and liquid
resources when those inputs support the question. Do not manufacture a tenant-ceiling
rating from missing inputs or impose a numeric score on an ordinary rent question.

## Competing supply

Where available, `supply_snapshot` distinguishes under-construction units, deliveries,
absorption, vacancy, and permit counts. Compare under-construction units with matching
existing stock; read absorption and deliveries on compatible period bases. Do not infer
months of remaining supply until the absorption period is established. A cumulative YTD
figure cannot be treated as a monthly flow.

When direct pipeline evidence is unavailable, `permit_ts` can indicate pressure. T12 MF
permits divided by matching MF stock is a useful intensity measure; above 3% merits
attention and above 5% merits closer scrutiny as historical screening heuristics. The
same intensity can mean different things in a growing market and a shrinking one. Compare
T12 with the prior T12, and never treat permits as completed units or guaranteed deliveries.
The unit count in an MF rent series is usable as stock only if its definition measures
the relevant stock rather than a lease or property sample.

Keep SF and MF supply separate. SF permits are not automatically BTR; a material BTR
component needs supporting public evidence. At finer grains, parent-market supply is
context, not a local measurement. Resolve coverage through the shared catalog and schema.

## Demand drivers

Migration volume and cohort differences answer different questions. Compare inbound and
outbound income, wealth, education, and age on the same basis; an income difference is
not itself a forecast of future rent growth. Link migration to household formation,
employment, and incumbent household resources when evidence supports the relationship.

Useful topic families are migration, demographic basics, employment, education, and
household financials. Credit detail adds resilience context when relevant. Translate
wealth tiers with the SuperCensus cohort guidance linked from SKILL.md; ordinal tier
averages are not dollar averages.

Industry concentration of roughly 15–20% in one sector can warrant investigation, but
job stability and local employers matter more than a universal concentration label.
Historical review heuristics flag fewer than 500 migration observations or 10,000 local
households for closer inspection; fewer than 300 observations on either side can weaken
a cohort comparison. These are review triggers, not statistical significance tests.
Check definitions and parent comparisons before treating a large divergence as a finding.

## Market fit and outlook

Use strategy-calibration.md when acquisition, value-add, development, SFR, or BTR changes
which evidence matters. Apply a common strategy and compatible dates across named places.
Do not convert a comparison into a ranked scorecard based on the number of places.

For numerical forecasts, use the forecasting contract linked from SKILL.md: rents and
occupancy use `rent_or_occupancy`; population or employment counts use `demographic`;
dollar-valued income or home-value series use `generic`; capital-market band analysis uses
`capital_markets` and projects no cap-rate value. Supply real history and required context
signals; never manufacture a series from snapshot change fields. Without sufficient
history, distinguish a supported qualitative outlook from an unavailable computed forecast.

A chart of asking, in-place, and signed-lease evidence can clarify a rent story. Supply
bars or aligned inbound/outbound comparisons can expose the relevant driver. Use the
shared output guidance to show uncertainty and material limitations without empty metrics.
