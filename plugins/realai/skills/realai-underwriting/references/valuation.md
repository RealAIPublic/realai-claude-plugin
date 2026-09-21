# Value ranges and valuation judgment

Use for a commercial property's value, refinance collateral, buyout, mark-to-market, or
disposition pricing. Answer the valuation question at the depth requested. These methods
do not support individual homes, condos, or 2–4 unit residential valuations.

## Establish the basis

Identify the property, valuation date, interest being valued, and whether the question
concerns current or stabilized value. Use the purpose when supplied; do not assign an
acquisition purpose to a neutral value question. Clarify purpose only when it changes
the required basis. Property value, equity value after debt, and partner proceeds are
different quantities; ownership agreements may affect a buyout beyond asset value.

Label the income basis: documented T12, normalized actuals, pro forma, or platform-modeled.
RealAI financials are modeled annual statements unless the source establishes otherwise.
A current, internally consistent T12 usually supports current economics better than a
broker projection. Explain material normalization for nonrecurring items, taxes,
concessions, occupancy, or deferred maintenance; do not substitute stabilized NOI for
current NOI without accounting for the cost and time to reach it.

For non-multifamily commercial assets, obtain operating inputs from documents and public
sources. Supported market-grain evidence can provide context, but the MCP has no
commercial operational property entity. Scope missing evidence to the affected method:
missing lease rollover can weaken an office DCF without preventing a sale-comp discussion.

## Select methods that fit the evidence

| Method | Useful when | Important limits |
|---|---|---|
| Direct capitalization | Income and occupancy are reasonably stabilized and cap-rate evidence is relevant | Match NOI definition, period, property risk, and cap-rate basis. Market averages are not property-specific rates. |
| Discounted cash flow | Lease rollover, renovation, lease-up, or changing cash flows materially affect value | Explicitly represent timing, capital costs, terminal assumptions, and discount rate; avoid double-counting stabilization costs. |
| Sales comparison | Recent transactions describe sufficiently similar assets | Verify consideration, date, size, condition, property rights, and transaction terms. Adjust transparently or use a wider range. |
| Replacement cost | New construction, specialty property, or basis relative to construction is the question | Include land, relevant costs and entrepreneurial profit; account for depreciation and obsolescence. Cost does not guarantee market value. |

Income and sales evidence often anchor stabilized multifamily and industrial valuations.
Lease-specific cash flows matter more for office and other assets with concentrated
rollover. Hotel operations, management/franchise obligations, reserves, and appropriate
income definitions need their own treatment. Mixed-use may require component analysis.
These are considerations, not rules requiring every method or a fixed hold threshold.

Thin or stale comps reduce their weight rather than becoming a precise estimate through
averaging. Independent methods can share the same weak inputs; numerical convergence
alone does not establish confidence.

## Evidence that changes the range

- **Income:** distinguish asking, effective, contracted, and collected rents. Support
  achievable rent with comparable product and concessions. Expense ratios need matched
  accounting, service levels, reimbursements, and tax treatment.
- **Capitalization:** consider asset class, location, condition, remaining lease term,
  growth expectations, and capital needs. Label market-level context and explain any
  property adjustment. A prior sale is context whose relevance depends on changed facts.
- **Growth:** use relevant history and current supply/demand to test assumptions. Income
  or migration patterns can support a hypothesis; they do not prove future rent growth.
- **Stabilization:** include renovation, downtime, leasing costs, and carrying costs.
  Compare current and stabilized values only on clearly stated bases.
- **Refinance:** use the lender's accepted income and terms if supplied. LTV support does
  not establish proceeds by itself; DSCR, debt yield, reserves, and lending constraints
  may bind earlier. Do not assume an interest-only loan allows a lower required DSCR.
- **Taxes and transfer costs:** assess the transaction and jurisdiction. Refinance,
  ownership-interest transfers, and asset sales can have different consequences; do not
  assume any category is universally exempt from reassessment.

## Calculate using the supported authority

Apply the host mapping in `${CLAUDE_PLUGIN_ROOT}/shared/infrastructure.md`.

For multifamily, use `${CLAUDE_PLUGIN_ROOT}/engines/mf-operating-statement/SKILL.md` for NOI,
projection, direct cap, and DCF. Preserve source basis and use only its supported outputs.
Use `${CLAUDE_PLUGIN_ROOT}/engines/forecasting/SKILL.md` for numerical forecasts;
a chosen exit cap or user growth
scenario remains an assumption, not an engine prediction. Act on errors and unsupported
inputs instead of estimating engine results in prose.

For a requested commercial workbook, use `${CLAUDE_PLUGIN_ROOT}/engines/xlsx/SKILL.md`
to build or audit formulas
that reflect the property's economics. Do not force commercial inputs through multifamily
defaults. Where a method has no supported computational path, discuss its evidence and
limits without inventing a numerical output or commissioning an unrequested workbook.

## Reconcile and communicate

When evidence supports a range, explain what anchors it and why methods differ. Weight
source fitness, comp quality, income reliability, and assumption sensitivity; do not
mechanically average approaches. If the evidence supports only a directional comparison,
state that rather than manufacturing a central estimate.

Use sensitivities for the variables that matter, such as NOI, cap rate, discount rate,
rollover, or terminal value. Scenario bounds are not statistical confidence intervals.
A comparison chart or interactive sensitivity can make a range easier to understand;
use the same validated results in every form. Name the material evidence that would
narrow the range when useful. Describe the work as an analytical estimate, not a formal
appraisal; address appraisal requirements when relevant to the user's intended use.
