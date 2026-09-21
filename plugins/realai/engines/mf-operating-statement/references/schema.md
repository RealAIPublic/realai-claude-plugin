# Schema

The script reads a request JSON on stdin and writes a response JSON on stdout. Blocks not
relevant to the requested mode are omitted from the response.

## Contents

- [Request](#request)
- [Field requirements by mode](#field-requirements-by-mode)
- [Scenario resolution from `mf_property_financials`](#scenario-resolution-from-mf_property_financials)
- [Response](#response)

## Request

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

  "benchmarks": { "vacancy_rate": 0.06, "opex_ratio": 0.42 },

  "rent_comps": { "comp_rent_per_unit_month": 2050 },

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

  "development_inputs": { "total_development_cost": null }
}
```

## Field requirements by mode

| Block | base_year_only | projection | direct_cap | dcf | levered_returns | yield_on_cost |
|---|---|---|---|---|---|---|
| `property_context` | required | required | required | required | required | required |
| `mf_property_financials` | required (one scenario) | required | required | required | required | required |
| `benchmarks` | required for scenarios 2,3,4 | same | same | same | same | same |
| `rent_comps` | required for scenario 4 | same | same | same | same | same |
| `projection_inputs` | — | optional (defaults) | optional | optional | optional | optional |
| `valuation_inputs` | — | — | required | required | required for sale | — |
| `capital_stack` | — | — | — | — | required | — |
| `development_inputs` | — | — | — | — | — | required |

## Scenario resolution from `mf_property_financials`

| Scenario | Trigger |
|---|---|
| 1 | `gpr`, `vacancy_loss`, `other_income`, `egi`, `opex`, `noi` all present |
| 2 | `gpr`, `vacancy_loss`, `opex_ratio` present; `opex` and `other_income` absent/null |
| 3 | Financials null, but `property_context.in_place_rent` and `occupancy` present |
| 4 | Financials null, `in_place_rent` null, `rent_comps.comp_rent_per_unit_month` present |

If none is satisfied → validation error.

## Additional requirements not captured by the table

- **`dcf`** — `unlevered_irr` is only computed when `valuation_inputs.purchase_price` is
  supplied (it's the entry outlay the IRR solves against); omit it and `unlevered_irr` comes
  back `null` while `npv`/`value_per_unit`/`terminal_value` still compute normally.
- **value-add projections** (any mode beyond `base_year_only` when stabilization status is
  `value-add`) — `property_context.units`, `property_context.in_place_rent`, and
  `projection_inputs.post_renovation_rent` are all required; missing any of them is a blocking
  error (`status: "error"`), since the value-add rent ramp can't be defaulted.

## Response

```json
{
  "status": "ok | unknown | error",
  "base_year": {
    "scenario": 1,
    "stabilization_status": "stabilized | lease-up | value-add | unknown",
    "stabilization_status_source": "user_override | inferred | default | unresolved",
    "stabilization_status_explanation": "plain-language reason",
    "other_income_present": true,
    "statement": {
      "gpr": 0, "vacancy_loss": 0, "vacancy_rate": 0, "net_rent": 0,
      "other_income": 0, "egi": 0, "opex": 0, "opex_ratio": 0, "noi": 0
    },
    "data_quality_flags": []
  },
  "projection": {
    "horizon_years": 5,
    "assumptions": { "rent_growth": {"value": 0.03, "source": "default"} },
    "years": [ { "year": 1, "gpr": 0, "vacancy_loss": 0, "vacancy_rate": 0,
                 "net_rent": 0, "other_income": 0, "egi": 0, "opex": 0,
                 "noi": 0, "capex": 0 } ]
  },
  "valuation": {
    "direct_cap": { "capitalized_noi_year": 1, "capitalized_noi": 0, "going_in_cap": 0,
                    "value": 0, "value_per_unit": 0, "implied_cap_rate": null,
                    "implied_cap_basis": null },
    "dcf": { "npv": 0, "unlevered_irr": 0, "value_per_unit": 0, "terminal_value": 0 }
  },
  "levered_returns": {
    "initial_equity": 0, "peak_equity": 0, "levered_irr": 0, "equity_multiple": 0,
    "equity_multiple_basis": "peak_equity", "average_cash_on_cash": 0,
    "cash_on_cash_denominator": "initial_equity", "loan_balance_at_exit": 0,
    "exit_year_dscr": 0
  },
  "yield_on_cost": { "untrended_yoc": 0, "trended_yoc": 0, "spread_to_market_cap_bps": 0 },
  "unknown_resolution": {
    "missing_fields": ["market_rent"],
    "reason": "why status is unknown",
    "suggested_resolution": "how to resolve and re-invoke"
  },
  "validation": { "checks_passed": true, "blocking_failures": [], "data_quality_flags": [] }
}
```

Sign convention: `vacancy_loss` is negative; `vacancy_rate` in the response is positive
(`abs(vacancy_loss) / gpr`). Where a source exposes both a vacancy-only loss and a combined
vacancy-and-collection loss, the caller chooses; default to vacancy-only.
