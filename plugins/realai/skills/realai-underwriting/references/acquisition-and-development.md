# Acquisition, development, and conversion

Use the user's question to decide how much underwriting is useful. A question about
rent upside needs evidence for achievable rents; a priced acquisition recommendation
also needs basis, costs, financing where relevant, and the user's decision criteria.
Do not turn either into a prescribed report or a sequence of intake confirmations.

## Establish the economic question

Use the property, documents, proposed program, and assumptions already supplied. Resolve
material ambiguity about the asset or transaction. For an initial screen, disclosed
ranges can support useful conclusions while unresolved inputs remain conditional.

- **Acquisition:** distinguish current operations from the proposed stabilized result.
  For value-add, identify renovation scope, cost, achievable rent lift, turn pace,
  downtime, and whether the current operator already captures the opportunity.
- **Development:** establish site, product, scale, land basis, construction and lease-up
  timing. Investigate entitlement or site constraints that could change what can be built.
- **Conversion:** establish existing building dimensions and condition, target use,
  acquisition basis, conversion scope, and usable area after conversion.

Price is needed to judge a specific price; an unknown price need not prevent a supported
value range or operating assessment. Missing debt terms constrain levered returns, not
an unlevered read. Do not invent the user's return hurdle or require one for every task.

## Evidence for the economics

Choose evidence that tests the proposed economics, using the shared retrieval workflow.

| Question | Evidence and interpretation |
|---|---|
| What cash flow exists today? | Current rent roll and operating records; reconcile concessions, vacancy, collections, recurring expenses, and period differences. RealAI financials may be modeled annual values, not a verified T12. |
| Is the rent assumption achievable? | Comparable product and unit mix, effective rents and concessions, renovation scope, recent leasing results, and competing deliveries. Asking rent alone does not establish achievable rent. |
| Does the basis make sense? | Relevant sale transactions and income evidence; adjust for date, condition, terms, and stabilization. A market cap rate is context, not a property valuation. |
| What supports future demand? | Relevant rent history, household economics, employment, migration cohorts, and supply. Use these when they test the thesis, not as a standard demographic appendix. |
| Could supply disrupt the plan? | Actual construction and deliveries relative to absorption and the delivery date; permits are authorizations, not committed completions. |

For commercial assets outside multifamily, operating evidence comes from documents and
public sources. Review lease terms, reimbursements, concessions, tenant concentration,
weighted remaining lease term, rollover, downtime, and tenant-improvement/leasing costs
when relevant to the asset. Do not apply office lease tests to hotel rooms, or multifamily
occupancy and expense defaults to unrelated uses. For mixed-use, test material components
separately; aggregating them must preserve their different economics.

## Development and conversion judgment

For development, distinguish by-right capacity from approvals still needed. Check zoning,
allowable use, density, height, parking, site work, utilities, impact fees, and conditions
attached to incentives when they affect feasibility. Site-specific documents and current
jurisdictional sources carry more weight than generic policy summaries.

For conversion, investigate floorplate depth, window access, column grid, ceiling heights,
structure, building systems, life safety, and rentable efficiency as applicable. An
attractive purchase basis cannot establish physical or regulatory feasibility.

Test major costs and timing using `benchmark-challenge.md`. Prefer contractor pricing,
comparable completed projects, and local evidence over generic ranges. Keep land or
acquisition, hard costs, soft costs, contingency, financing carry, and lease-up costs
separate so the total does not double-count an allowance or omit carrying costs.
Compare conversion basis with a relevant new-build alternative; a structural constraint
or cost overrun may remove the apparent advantage of reusing the building.

## Calculations and assumptions

Apply the host mapping in `${CLAUDE_PLUGIN_ROOT}/shared/infrastructure.md`.

Use `${CLAUDE_PLUGIN_ROOT}/engines/mf-operating-statement/SKILL.md` for supported multifamily
NOI, direct-cap value, DCF, returns, and yield-on-cost calculations. Map source inputs
and their units; read results from the engine. Select only the requested calculation.
A commercial model must represent its actual lease and cost structure; the multifamily
engine does not establish support for another asset class merely because fields fit.
For a requested commercial workbook, follow
`${CLAUDE_PLUGIN_ROOT}/engines/xlsx/SKILL.md` and validate formulas.
If no supported calculation path exists, limit the numerical conclusion accordingly.

Use `${CLAUDE_PLUGIN_ROOT}/engines/forecasting/SKILL.md` for new numerical forecasts.
A user-specified growth path
is a scenario assumption, not a statistical forecast. Historical cap-rate bands do not
predict the exit cap: choose and disclose a supported exit assumption or show scenarios.
Never silently default financing, occupancy, taxes, other income, or growth.

Compare modeled economics with the user's hurdle and applicable lender terms when
available. Debt coverage depends on amortization and interest-only periods, not merely a
headline rate. Yield-on-cost spread compensates for execution and timing risk; no fixed
spread proves a development is attractive. Tax changes need jurisdiction-specific support.

## Explain what changes the decision

Connect the strongest evidence to the requested conclusion. Test the assumptions most
likely to change it: achieved rents, renovation cost, lease-up pace, total basis,
financing, or exit pricing. Sensitivities are useful even when the base case looks strong.
Use a cost comparison, cash-flow waterfall, or sensitivity visual when it clarifies the
tradeoff. Distinguish conditions supported by evidence from matters needing diligence;
keep an unresolved assumption beside the conclusion that depends on it.
