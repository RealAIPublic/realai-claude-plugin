# Rates, financing, and capital markets

Use for rates, the financing environment, or how macro conditions affect real estate.
Answer the question at its natural scale: a latest-rate question needs a dated observation;
an explanation of transmission may need several related series.

## Match the evidence to the question

These are topic and field hints, not a stored schema. Use the shared catalog and live
schema for current availability, definitions, dates, and query construction.

| Evidence family | Useful questions |
|---|---|
| `national_metrics_daily` | Treasury and SOFR levels, market indexes, inflation breakevens |
| `national_metrics_monthly` | Inflation, unemployment, Fed funds, consumer mortgage rates, housing activity |
| `national_metrics_quarterly` | GDP, homeownership, rental vacancy, CRE loan delinquency |
| `national_metrics_annual_projection` | The Fed projection path, identified as that source's outlook |
| `national_metrics_monthly_projection` | Forward SOFR curve and its vintage |
| `mortgage_rate_snapshot` on `mortgage_rates` | Commercial/MF lending programs, rates, spreads, LTV, and DSCR terms |
| `caprate_ts` at market grain | Observed cap-rate history by covered asset class |

Consumer 30-year and 15-year mortgage quotes differ from institutional lending programs.
Program indications are not commitments for a particular borrower or property. Match the
asset, term, and loan type before comparing terms.

A sample of major markets is not a national cap-rate series. Name the markets and weighting
if constructing a summary. Missing class-specific cap rates do not justify substituting
multifamily rates for another asset class. Public market reports may provide supplemental
context, labeled by source, period, and retrieval date.

## Read levels and changes together

For rate direction, choose the historical window that answers the question. Compare
compatible observation dates rather than juxtaposing a stale quarterly cap rate and a
current daily Treasury quote as if simultaneous.

Use an available non-code calculator for spreads and changes, preserving units. A cap-rate minus Treasury spread
is a simple relative-yield indicator; it is not a complete measure of property risk or a
property valuation. Nominal Treasury yield minus the matching inflation breakeven is an
approximate real-yield proxy, not an observed TIPS yield.

A historical range describes the observed window, not a predicted cap rate. Use source
statistics or an available non-code calculator for derived comparisons. Do not label an
observed range as a probability band or an implied future path.

## Connect macro conditions to the user's subject

Rates affect financing cost and valuation assumptions; inflation affects expense and
rent context; employment affects demand; starts and permits inform future supply.
Explain only the links supported by the evidence. National conditions supply context
for local performance and do not replace local observations.

For a transaction's financing assumptions or supplied model results, use
realai-underwriting. Do not turn indicative program terms into a computed deal result
without the necessary inputs and a supported calculation tool.

Published projection topics carry their source's outlook, not a new RealAI forecast.
Keep the projection vintage visible. This edition interprets those sourced outlooks;
it does not generate an additional statistical forecast or fill unavailable history.

A dated rate comparison table or aligned time-series chart can clarify a spread or
turning point. Use public research for breaking policy, central-bank commentary, or
context absent from the MCP; keep the source distinction visible where it matters.
