# Methodology

The exact logic the script implements. Read this when you need to explain a figure, debug
an output, or verify the compute matches intent.

## Contents

- [Base-year recipe by scenario](#base-year-recipe-by-scenario)
- [Stabilization status](#stabilization-status)
- [Projection](#projection)
- [Mode-specific calculations](#mode-specific-calculations)
- [Validation](#validation)

## Base-year recipe by scenario

| Line | Scenario 1 | Scenario 2 | Scenario 3 | Scenario 4 |
|---|---|---|---|---|
| GPR | reported | reported | units × in_place_rent × 12 | units × comp_rent × 12 |
| Vacancy | reported | reported | −(GPR × (1 − occupancy)) | −(GPR × benchmarks.vacancy_rate) |
| Net Rent | reported | reported | GPR + Vacancy | GPR + Vacancy |
| Other Income | reported | omitted | omitted | omitted |
| EGI | reported | = Net Rent | = Net Rent | = Net Rent |
| OpEx | reported $ | EGI × reported opex_ratio | EGI × benchmarks.opex_ratio | EGI × benchmarks.opex_ratio |
| NOI | reported | EGI − OpEx | EGI − OpEx | EGI − OpEx |

For scenarios 2, 3, 4: set `other_income_present: false`.

## Stabilization status

Resolution order:

1. **Override** — if `stabilization_status_override` is set, use it; source `user_override`.
2. **Inference** — source `inferred` when signals hold:
   - **stabilized**: occupancy ≥ ~0.90 AND in_place_rent within ~10% of market_rent
   - **lease-up**: occupancy materially below ~0.85 AND recent delivery flagged
   - **value-add**: in_place_rent >10% below market_rent AND repositioning flagged
3. **Default** — if inference fails:
   - Scenario 4 with recent delivery flagged → `lease-up`, source `default`
   - Otherwise → `unknown`, source `unresolved`

If status is `unknown`:
- mode `base_year_only` → return statement, `status: "ok"`, populate `unknown_resolution`.
- any other mode → `status: "unknown"`, return base-year as partial, populate
  `unknown_resolution`, **do not run projection**.

## Projection

For each year 1…`horizon_years`, compute the full waterfall. Behavior by status:

**Stabilized** — rent grows at `rent_growth`; vacancy held at base-year rate; other income
(if present) grows at `other_income_growth`; OpEx grows at `expense_growth`.

**Lease-up** — rent grows at `rent_growth`; vacancy ramps linearly from base-year to
`target_vacancy` over `months_to_stabilization`, flat thereafter; OpEx grows at
`expense_growth`.

**Value-add** — requires `property_context.units`, `property_context.in_place_rent`, and
`projection_inputs.post_renovation_rent` (blocking error if any is missing — these drive the
rent line and can't be defaulted). GPR is rebuilt each year from `units × current_rent × 12`,
not scaled off the base-year GPR:
- Renovation fraction complete by the end of year *yr* is `min(1, (yr × 12) / months_to_stabilization)`.
- While ramping (fraction < 1): `current_rent = in_place_rent + (post_renovation_rent − in_place_rent) × fraction`;
  vacancy held at the base-year rate.
- Once complete (fraction = 1): `current_rent = post_renovation_rent × (1 + rent_growth) ^ years_since_completion`;
  vacancy drops to `target_vacancy`.
- `renovation_capex` (total dollars) is drawn proportionally to the fraction of the
  renovation completed *in that year* (`capex_year = renovation_capex × (fraction_end − fraction_start)`),
  so the full amount is drawn by the year renovation completes and zero thereafter — a line
  below NOI, not netted into it.
- If `property_context.market_rent` is provided and a projected year's `current_rent` exceeds
  it, that year is flagged (rents shouldn't out-run the market indefinitely).
- There is no separate OpEx step-up input; OpEx grows at `expense_growth` in every mode,
  value-add included.

Preserve `other_income_present` from base year; if false, omit Other Income throughout.

Defaults when `projection_inputs` fields are null: rent_growth 0.03, expense_growth 0.025,
other_income_growth 0.03, target_vacancy 0.06, months_to_stabilization 18 (lease-up) / 24
(value-add), horizon_years 5. Record `provided` vs `default` per assumption.

## Mode-specific calculations

**direct_cap** — value = capitalized_noi ÷ going_in_cap (Year 1 NOI if stabilized; year of
stabilization otherwise). If a price is provided, also compute implied cap = NOI ÷ price and
label `implied_cap_basis`; else leave implied fields null.

**dcf** — unlevered CF = NOI − capex each year; terminal value = (Year N+1 NOI ÷ exit_cap) ×
(1 − sale_costs_pct); `npv` = Σ discounted CFs + discounted terminal at `discount_rate` — this
is a price-agnostic DCF asset value (no cost basis netted out), which is what `value_per_unit`
divides. `unlevered_irr` needs an entry outlay to solve a rate against: only computed when
`valuation_inputs.purchase_price` is supplied (cash flow list becomes `[-purchase_price, ...]`);
null otherwise, not a fabricated rate.

**levered_returns**
- loan proceeds = ltv × purchase_price (or `loan_amount` if given)
- initial equity = purchase_price − proceeds
- debt service = standard amortizing payment (loan_amount, interest_rate, amortization_years)
- loan balance at exit = remaining principal after `horizon_years` (amortization schedule)
- levered CF = unlevered CF − debt service, where unlevered CF already nets out that year's
  `capex` (from a value-add projection) — capex draws are funded from operating cash flow,
  reducing that year's distribution, **not** from a separate equity contribution
- exit equity CF = sale price − sale costs − loan balance at exit
- levered IRR solves −initial_equity + Σ(levered CF/(1+r)^t) + exit equity CF/(1+r)^N = 0
- **Equity multiple** = total distributions ÷ initial equity; **cash-on-cash** = average
  annual levered CF ÷ initial equity. Because capex is operating-funded rather than
  equity-funded, this implementation's `peak_equity` always equals `initial_equity` and both
  basis/denominator labels are always `"initial_equity"` — there is no equity-funded-capex-draw
  path (that would require deciding when a negative-CF year triggers a capital call, which is
  out of scope here).

**yield_on_cost** — untrended = Year 1 stabilized NOI ÷ total_development_cost; trended =
stabilization-year NOI ÷ total_development_cost; spread = trended_yoc − going_in_cap (bps).

## Validation

**Blocking** (`status: "error"`, no statement):
- required input missing for resolved scenario
- vacancy not stored negative
- scenario-1 identity EGI − OpEx ≠ NOI
- implausible computed values (negative NOI from arithmetic; OpEx > EGI in scenarios 2/3/4)

**Advisory flags** (return result, populate `data_quality_flags`) — base year:
- OpEx ratio outside 0.35–0.55 of EGI
- Other Income outside 2–12% of Net Rent (scenario 1 only)
- vacancy rate outside expected range for status (stabilized 0.05–0.08; non-stabilized higher)
- scenario-1 revenue lines do not foot (GPR + Vacancy + Other Income ≠ EGI)

**Advisory flags** — projection (any mode beyond `base_year_only`):
- OpEx ratio outside 0.35–0.55 of EGI, checked for every projected year
- lease-up/value-add: final-year vacancy rate has not converged to `target_vacancy` by the
  end of the horizon, when the horizon extends past the ramp/renovation period (in normal
  operation this only fires if the ramp math itself is wrong — it's a regression guard, not
  something a normal input combination should trigger)
- value-add: a projected year's rent exceeds `property_context.market_rent`, when provided
- levered_returns: loan balance at exit is not below the original loan amount (amortization
  sanity check)

**Not independently re-checked** — these hold by construction given how the script derives
each field, so they aren't separate runtime checks: EGI − OpEx = NOI every year (NOI is
literally defined as that difference), Year 1 NOI ties to the base year via the stated
growth/ramp formula, equity multiple × basis = total distributions (the basis *is* the
denominator used to compute the multiple), cash-on-cash's denominator matches the structure
described above, and implied cap rate is populated only when a price is supplied (an `if`
guard, not a validation pass). Treat these as documentation of the invariant, not as flags to
look for in the output.

**Projection checks** — EGI − OpEx = NOI every year; vacancy negative & Net Rent = GPR +
Vacancy every year; Year 1 NOI ties to base-year adjusted by one period; vacancy converges to
`target_vacancy` by end of stabilization; OpEx ratio stays 0.35–0.55; value-add rent ≤
market_rent if provided; levered loan balance at exit < original (proves amortization); EM ×
basis = total distributions on the named basis; CoC denominator matches structure; implied
cap populated only if a price was supplied.
