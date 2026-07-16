# Multifamily Operating Statement & Projection Methodology

> **Module type:** Methodology spine. Plain markdown reference file — NOT a triggerable skill. This is the canonical calculation contract for multifamily NOI, projection, direct-cap valuation, DCF, levered returns, and yield-on-cost. It is mirrored across `realai-investment`, `realai-underwriting`, `realai-valuation`, and `realai-property-analysis`, and is the contract implemented by `realai-mf-operating-engine/scripts/operating.py`. Callers route MF calculations through the engine (which runs the script) rather than computing inline.

## Purpose

Produce a multifamily income statement and optional forward projection / returns analysis. Pure compute: the caller supplies all inputs as structured data, the methodology yields structured output. No external data fetches, no tool calls, no document parsing.

## Modes

The `mode` field selects behavior:

- `base_year_only` — produce a base-year statement and stop
- `projection` — project the base-year statement forward N years
- `direct_cap` — produce direct cap valuation from stabilized NOI
- `dcf` — produce NPV and unlevered IRR from projected cash flows
- `levered_returns` — produce levered IRR, equity multiple, cash-on-cash
- `yield_on_cost` — produce untrended and trended YoC for development

Any mode other than `base_year_only` runs the Base Year module first internally, then proceeds to Projection. The caller does not need to invoke Base Year separately.

**Scope discipline.** Presence of input data beyond what the mode requires does not authorize output beyond what the mode defines. Extra inputs are ignored silently.

## Request schema

```json
{
  "mode": "base_year_only | projection | direct_cap | dcf | levered_returns | yield_on_cost",
  "property_context": {
    "units": 120,
    "in_place_rent": 1850,
    "market_rent": 2100,
    "occupancy": 0.92,
    "stabilization_status_override": null,
    "recent_delivery_flag": false,
    "repositioning_flag": false
  },
  "mf_property_financials": {
    "gpr": 2664000,
    "vacancy_loss": -213120,
    "other_income": 95000,
    "egi": 2545880,
    "opex": 1145646,
    "opex_ratio": null,
    "noi": 1400234
  },
  "benchmarks": {
    "vacancy_rate": 0.06,
    "opex_ratio": 0.42
  },
  "rent_comps": {
    "comp_rent_per_unit_month": 2050
  },
  "projection_inputs": {
    "horizon_years": 5,
    "rent_growth": 0.03,
    "expense_growth": 0.025,
    "other_income_growth": 0.03,
    "target_vacancy": 0.06,
    "months_to_stabilization": 18,
    "renovation_capex": null,
    "post_renovation_rent": null
  },
  "valuation_inputs": {
    "going_in_cap": 0.055,
    "exit_cap": 0.06,
    "discount_rate": 0.085,
    "sale_costs_pct": 0.02,
    "purchase_price": null
  },
  "capital_stack": {
    "ltv": 0.65,
    "loan_amount": null,
    "interest_rate": 0.065,
    "loan_term_years": 10,
    "amortization_years": 30
  },
  "development_inputs": {
    "total_development_cost": null
  }
}
```

Under `realai-mf-operating-engine`, this request is wrapped with a `role` field (`authority` for binding output; `cross_check` for a bounded advisory comparison against a populated workbook). The fields above are the `authority`-role body; `cross_check` adds a `workbook_outputs` block and ignores everything beyond what is needed for headline EGI/NOI/cap.

### Field requirements by mode

| Block | base_year_only | projection | direct_cap | dcf | levered_returns | yield_on_cost |
|---|---|---|---|---|---|---|
| `property_context` | required | required | required | required | required | required |
| `mf_property_financials` | required (one scenario satisfied) | required | required | required | required | required |
| `benchmarks` | required for scenarios 2, 3, 4 | same | same | same | same | same |
| `rent_comps` | required for scenario 4 | same | same | same | same | same |
| `projection_inputs` | — | optional (defaults apply) | optional | optional | optional | optional |
| `valuation_inputs` | — | — | required | required | required for sale | — |
| `capital_stack` | — | — | — | — | required | — |
| `development_inputs` | — | — | — | — | — | required |

### Scenario resolution from `mf_property_financials`

| Scenario | Trigger |
|---|---|
| 1 | `gpr`, `vacancy_loss`, `other_income`, `egi`, `opex`, `noi` all present |
| 2 | `gpr`, `vacancy_loss`, and `opex_ratio` present; opex and `other_income` absent or null |
| 3 | All financials null, but `property_context.in_place_rent` and `occupancy` present |
| 4 | All financials null, `in_place_rent` null, `rent_comps.comp_rent_per_unit_month` present |

If none of the four scenarios is satisfied, return a validation error.

## Base-year statement recipes

| Line | Scenario 1 | Scenario 2 | Scenario 3 | Scenario 4 |
|---|---|---|---|---|
| GPR | reported | reported | units × in_place_rent × 12 | units × comp_rent × 12 |
| Vacancy | reported | reported | −(GPR × (1 − occupancy)) | −(GPR × benchmarks.vacancy_rate) |
| Net Rent | reported | reported | GPR + Vacancy | GPR + Vacancy |
| Other Income | reported | omitted | omitted | omitted |
| EGI | reported | = Net Rent | = Net Rent | = Net Rent |
| OpEx | reported $ | EGI × reported opex_ratio | EGI × benchmarks.opex_ratio | EGI × benchmarks.opex_ratio |
| NOI | reported | EGI − OpEx | EGI − OpEx | EGI − OpEx |

**Sign convention:** `vacancy_loss` is stored as a negative number. `vacancy_rate` in the response is always positive (abs(vacancy_loss) ÷ gpr). For scenarios 2, 3, 4: set `other_income_present: false`. Do not use `vacancy_collection_loss` — default to `vacancy_loss`.

## Stabilization status resolution

1. If `property_context.stabilization_status_override` is provided, use it. Set source to `user_override`.
2. Otherwise, attempt inference:

| Status | Required signals |
|---|---|
| stabilized | occupancy ≥ ~0.90 AND in_place_rent within ~10% of market_rent |
| lease-up | occupancy materially below ~0.85 AND recent delivery documented in context |
| value-add | in_place_rent more than 10% below market_rent AND repositioning context flagged |

If inferred, set source to `inferred`. If inference fails and Scenario 4 is in play with recent_delivery_flag = true, default to `lease-up`. Otherwise default to `unknown`.

If `stabilization_status` resolves to `unknown` and mode is `base_year_only`: return statement with `status: "ok"`, `stabilization_status: "unknown"`, populated `unknown_resolution`. If mode is anything else: return `status: "unknown"`, include base-year as partial result, populate `unknown_resolution`, do not run projection.

## Base-year validation

**Blocking failures** (set `status: "error"`, do not return statement):
- Required input missing for resolved scenario
- Vacancy not stored as negative
- Reported figures fail the identity EGI − OpEx = NOI in scenario 1
- Computed values implausible (negative NOI from arithmetic, OpEx > EGI in scenarios 2–4)

**Flagged-but-proceeding:**
- OpEx ratio outside 0.35–0.55 of EGI
- Other Income outside 2–12% of Net Rent (scenario 1 only)
- Vacancy rate outside expected range for status
- Scenario 1 revenue lines do not foot: GPR + Vacancy + Other Income ≠ EGI

## Projection (modes beyond base_year_only)

For each year 1 through `horizon_years`, compute the full waterfall (GPR → Vacancy → Net Rent → Other Income → EGI → OpEx → NOI). Apply growth and stabilization logic based on resolved `stabilization_status`:

**Stabilized:** rent grows at `rent_growth`; vacancy held at base-year `vacancy_rate`; Other Income (if present) grows at `other_income_growth`; OpEx grows at `expense_growth`.

**Lease-up:** rent grows at `rent_growth`; vacancy rate ramps linearly from base-year to `target_vacancy` over `months_to_stabilization`; flat thereafter; OpEx grows at `expense_growth`.

**Value-add:** in-place rent ramps linearly from base-year toward `post_renovation_rent` over renovation period; grows at `rent_growth` thereafter; vacancy held at base-year rate during renovation, drops to `target_vacancy` post-renovation; OpEx grows at `expense_growth` plus any step-up; `renovation_capex` is a separate line below NOI.

Preserve `other_income_present` from base year. If false, omit Other Income across the projection.

### Defaults if `projection_inputs` fields are null

| Field | Default |
|---|---|
| `rent_growth` | 0.03 |
| `expense_growth` | 0.025 |
| `other_income_growth` | 0.03 |
| `target_vacancy` | 0.06 |
| `months_to_stabilization` | 18 (lease-up), 24 (value-add) |
| `horizon_years` | 5 |

Record source (`provided` or `default`) for each assumption.

## Mode-specific calculations

**`direct_cap`:** Value = capitalized_noi ÷ going_in_cap. Capitalized NOI is Year 1 for stabilized; year of stabilization for lease-up or value-add. If a price is provided, also compute implied cap rate = NOI ÷ price.

**`dcf`:**
- Unlevered CF each year = NOI − capex
- Terminal value = (Year N+1 NOI ÷ exit_cap) × (1 − sale_costs_pct)
- NPV = sum of discounted unlevered CFs + discounted terminal value at `discount_rate`
- Report unlevered IRR (requires a `purchase_price` as the t0 outflow; NPV is reported regardless)

**`levered_returns`:**
- Loan proceeds = ltv × purchase_price (or `loan_amount` if provided)
- Initial equity = purchase_price − loan_proceeds
- Annual debt service = standard amortizing payment from loan_amount, interest_rate, amortization_years
- Loan balance at exit = remaining principal after `horizon_years` of amortization
- Annual levered CF = unlevered CF − debt service
- If capex draws occur, present NOI, Debt Service, Operating Carry, CapEx Draw, Net Levered CF as separate lines
- Peak equity = initial equity + sum of equity-funded capex draws
- Exit equity CF = sale price − sale costs − loan balance at exit
- Levered IRR solves: −initial_equity + Σ(levered CF / (1+r)^t) + (exit equity CF / (1+r)^N) = 0
- Post-closing equity contributions enter as negative CF in the year they occur

**Equity Multiple basis:**
- EM = Total Distributions ÷ Equity Basis
- Default basis = peak_equity
- If no post-closing contributions, label `equity_multiple_basis: "initial_equity"` explicitly
- Never mix bases in one response

**Cash-on-Cash:**
- No post-closing contributions: annual CoC = annual levered CF ÷ initial equity. Denominator: `initial_equity`.
- Post-closing contributions exist: annual CoC = annual levered CF ÷ peak equity. Denominator: `peak_equity`.
- Never silently use initial equity when contributions exist post-closing.

**`yield_on_cost`:**
- Untrended YoC = Year 1 stabilized NOI ÷ total_development_cost
- Trended YoC = stabilization year NOI ÷ total_development_cost
- Spread to going-in market cap = trended_yoc − valuation_inputs.going_in_cap (in bps)

## Projection validation

Run before returning:

- EGI − OpEx = NOI every projected year
- Vacancy stored as negative every year; Net Rent = GPR + Vacancy
- Year 1 NOI ties to base-year NOI adjusted by exactly one period of growth/ramp — larger jumps indicate error
- Vacancy converges to `target_vacancy` by end of stabilization period (non-stabilized)
- OpEx ratio stays within 0.35–0.55 across all years
- Value-add: stabilized rent does not exceed `market_rent` if provided
- Levered: loan balance at exit < original loan amount (proves amortization applied)
- Levered: EM × Equity Basis = Total Distributions, using the same basis named in the response
- Levered: cash_on_cash_denominator matches deal structure (peak if post-closing contributions; initial only if none)
- Direct cap: implied cap rate populated only if a price was supplied; `implied_cap_basis` labeled

## Error handling

`status: "error"` is terminal — response includes `validation.blocking_failures`, no statement or projection. Caller fixes inputs and re-invokes.

`status: "unknown"` means base year succeeded but projection could not run due to unresolved stabilization status. Response includes base-year statement as partial result and the `unknown_resolution` block.

`status: "ok"` means all requested computations succeeded. `validation.data_quality_flags` may still be populated — advisory, not blocking.

## What this methodology does NOT do

- Fetch financials from a datamart, document store, or external system
- Parse PDFs, rent rolls, or OMs
- Resolve conflicting figures across documents (caller must reconcile upstream)
- Pull rent comps
- Persist state between calls
- Make calls to other agents

If the caller needs any of the above, the caller orchestrates them and passes results into this methodology's request.

## Implementation note

The executable form of this contract is `realai-mf-operating-engine/scripts/operating.py`. On the **no-template path** the engine runs the script in `authority` role and its outputs are binding. On the **workbook path** a populated `realai-pro-forma` workbook is the math authority; the sengine runs in `cross_check` role to independently recompute headline NOI/EGI/cap only and flag divergence, never overriding the workbook. Read outputs back from the workbook or the script — never compute model-derived metrics in narrative.
