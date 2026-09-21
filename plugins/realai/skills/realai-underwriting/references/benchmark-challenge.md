# Testing development and conversion assumptions

Use when a cost, rent, timing, or financing assumption materially affects feasibility.
This is analytical guidance, not an intake stage or mandatory confirmation process.
Reuse evidence already available; research only the assumptions the question needs.

## Choose a relevant comparison

Match product, location, scale, condition, cost basis, and date before comparing values.
Prefer recent local evidence, but a poorly matched local project can be less useful than
a well-matched regional one. Record the source, observation period, basis, and supported
range. A midpoint is descriptive, not automatically the appropriate project assumption.

| Assumption | Useful support | Comparison traps |
|---|---|---|
| Land or acquisition basis | Comparable sales, property rights, entitlements, and site condition | Land area, buildable area, and rentable area are different denominators. |
| Hard construction or conversion costs | Contractor pricing, comparable completed projects, public cost reports | Shell versus finished space; site work, demolition, systems, labor rules, and escalation included or excluded. |
| Rent, ADR, or sale price | Comparable product, effective pricing, concessions, quality, and performance | Asking versus achieved pricing; new-build premium without comparable support. |
| Lease-up or sale absorption | Actual performance of comparable deliveries and competing inventory | Monthly pace, units available, preleasing, concessions, seasonality, and launch effects. |
| Stabilized occupancy | Comparable operating assets and product-specific demand | Hotel room occupancy and residential occupancy are different economics. |
| Operating expenses | Property records and compatible benchmarks | Net versus gross leases, reimbursements, service scope, taxes, and reserve treatment. |
| Exit capitalization | Comparable investment transactions and appropriate market context | Market averages, NOI basis, terminal asset age, and an unsupported assumed rate improvement. |
| Soft costs and contingency | Detailed project scope, contractor budget, design maturity, and known conditions | Percentages applied to different bases; allowances already included in hard costs. |
| Timeline | Entitlement status, contractor schedule, infrastructure needs, and comparable execution | Approval, construction, occupancy approval, and stabilization are different milestones. |
| Financing | Supplied terms or current public evidence for comparable risk and structure | LTC versus LTV, draw timing, interest carry, fees, reserves, amortization, and takeout conditions. |

Use freely accessible public evidence for external context and label source and retrieval
date. Do not assume access to paid construction, lodging, or senior-housing databases.
A single anecdote usually supports a tentative range. Several reports repeating the
same underlying source are not independent corroboration.

## Identify what deserves challenge

Compare the assumption with the supported range and explain its effect on the economics.
Use the size of the financial impact and the quality of the evidence to set priority;
there is no universal percentage or basis-point gap that determines acceptability.

Give particular attention to optimistic assumptions that compound:

- Costs below a relevant range may omit scope, escalation, or carrying costs. A credible
  project-specific contract can explain the difference; generic benchmarks cannot refute
  that contract without checking its exclusions and conditions.
- Faster lease-up than comparable deliveries can accelerate cash flows and reduce carry.
  Test whether preleasing, concessions, or product differences justify the pace.
- High rents combined with high occupancy and minimal concessions can overstate revenue
  even when each assumption looks plausible in isolation.
- A large land allocation can leave insufficient room for construction and return on
  total cost. Test residual economics, not a universal land-share threshold.
- A conversion budget needs explicit allowance for structure, systems, code compliance,
  usable-area loss, demolition, and surprises appropriate to the actual building.
- An incentive should affect economics only on its supported terms, including eligibility,
  timing, required approvals, affordability obligations, and possible clawbacks.

A deliberately conservative stress assumption is not a mistake. Label its role and use
it as intended. Conversely, a low-confidence benchmark cannot establish that the user's
project-specific assumption is wrong.

## Handle unresolved assumptions productively

For a preliminary question, proceed with a disclosed assumption or a useful range when
possible. Show the material difference between the proposed and evidence-supported cases.
Ask for the specific missing evidence when it would change the requested conclusion;
do not require the user to confirm every input before research or calculation.

If the user chooses an out-of-range assumption, retain it as a user scenario and record
the rationale. Confirmation does not make it independently verified. Avoid repeated
challenge loops; explain the dependency where the result is used. A revision should
update the dependent calculation without restarting unrelated work.

## Carry the judgment into the result

Use the multifamily operating engine for the financial calculations it supports and the
forecasting engine for new numerical forecasts, following the main skill's calculation
rules and `${CLAUDE_PLUGIN_ROOT}/shared/infrastructure.md`. Preserve asset-class limits.
A sensitivity uses specified alternatives; it is not a probability distribution or
forecast merely because it has upside and downside cases.

Surface the assumptions that move the decision and explain which evidence supports them.
Use a compact comparison or interactive sensitivity when useful and supported by the
host. Do not repeat every assumption in several sections or create a list of irrelevant
missing fields. Material unresolved costs, timing, and physical constraints should remain
visible beside the feasibility conclusion they affect.
