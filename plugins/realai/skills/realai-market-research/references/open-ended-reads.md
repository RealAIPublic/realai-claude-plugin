# Understanding a place

Use for an open-ended question about a market, neighborhood, ZIP code, or other geography.
Identify what distinguishes the place and why it matters to the user's question. A bare
place name can receive a useful overview without asking the user to choose a report type.

## Find the useful starting point

Start with a small amount of evidence that can answer the question. Expand when it exposes
an important relationship, contradiction, or follow-up. Topic names below are hints for
the canonical catalog and live schema, not a fixed retrieval bundle.

| Question | Evidence that helps |
|---|---|
| What is this area like? | `demographic_basics`, relevant household-income context, and housing or rent conditions |
| Are rents strengthening? | `mf_rent_and_occupancy_detail` for spread, tradeouts, and occupancy; `mf_rent_ts` when direction over time matters |
| What is happening to home values? | `home_sales_and_values_snapshot` for recent changes; its time series when the shape matters |
| Could this area fit a rental strategy? | Segment-specific rents, household purchasing power, and competing supply |
| What explains a change? | The relevant demand, supply, or employment evidence; public sources for specific events |

Household profiles as the answer belong to realai-supercensus. Household evidence can
still explain a market finding. Building overviews, including buildings the user does
not own, belong to realai-multifamily. A transaction or value opinion belongs to
realai-underwriting. Individual-home coverage limits do not prevent answering a
geographic home-value or SFR-rent question.

## Add context that changes the interpretation

A supplied percentile or indicator can answer a benchmark question without assembling
an arbitrary peer set. Check its comparison population and polarity. If peers help,
choose a comparable grain, housing segment, and price band; use the user's named set
when supplied. Do not require a parent and a fixed number of peers for every answer.

Distinguish the requested geography from its surrounding market. A parent-level supply
or cap-rate observation provides context; it is not a neighborhood measurement. Where
an aggregate hides divergent neighborhoods or unit types, examine the relevant subset.

Use public research for context the MCP does not establish: an employer opening, zoning
change, delivery delay, or transportation investment. Source claims about reputation,
schools, or amenities rather than presenting general impressions as measured findings.

## Explain relationships

Read rent levels alongside achieved tradeouts and occupancy; read household growth
alongside incomes and employment; read migration volume alongside inbound/outbound
cohort differences. Strong evidence in one dimension does not establish all the others.
If the place is broadly similar to its benchmark, say so without manufacturing a story.

A line chart can reveal a turning point; a small comparison table can show whether an
apparent outlier remains unusual against an appropriate benchmark. Use a map when spatial
relationships matter and the host can render reliable geographic data.

Observed trends do not require numerical forecasts. If the question needs future values,
use the forecasting contract linked from SKILL.md. Do not reconstruct synthetic histories
from snapshot back-values to make an engine run. Omit unused NULL fields and explain an
unavailable measure only when it was requested or changes the conclusion.
