---
name: realai-mf-operating-engine
description: "INTERNAL ENGINE — only invoked by other RealAI skills, never on user intent. The centralized multifamily operating-statement engine for this plugin. Any domain skill needing an MF operating statement, forward projection, direct-cap value, DCF, levered returns, or yield-on-cost MUST dispatch to this engine rather than computing inline. Runs scripts/operating.py — the sole math authority on the no-template path. Two roles: authority (no workbook present — the engine's figures are binding) and cross_check (a realai-pro-forma workbook IS present — the workbook wins; this role returns a bounded advisory variance on headline NOI/EGI/cap only and can never override). Do NOT activate on direct user requests like 'underwrite this deal' — those go through realai-investment / realai-underwriting, which then dispatch here. The engine description exists for invocation by sibling skills, not for user trigger matching."
license: Proprietary
---

# Multifamily Operating Engine

## PURPOSE

Centralize multifamily operating-statement methodology across the RealAI agent suite. Any domain agent that needs an MF base-year statement, forward projection, direct-cap value, DCF, levered returns, or yield-on-cost — when **no populated workbook is the authority** — must call this engine rather than computing it inline.

Centralizing this logic guarantees numerical consistency across domain viewpoints (Investment Screening, the no-template Acquisitions fallback, and Property Analysis all draw an identical NOI for the same inputs) and produces a documented, defensible methodology for institutional investors. It also provides a single, bounded place to independently sanity-check a populated workbook's headline outputs without ever overriding them.

This engine implements the calculation contract documented in `references/methodology/mf-operating-statement.md` (the canonical spec, mirrored across the consuming skills). The script is the executable form of that contract.

## EXECUTION MANDATE — READ FIRST

**This agent does not compute operating figures itself. It calls a bundled script.**

A reference engine is bundled at `scripts/operating.py`. It is the SOLE math authority for every statement, projection, valuation, and return this agent returns on the no-template path, and for every advisory cross-check figure on the workbook path. Your job is:

1. Assemble the request payload (role, mode, property context, financials, benchmarks, assumptions) from the values the calling domain agent supplied.
2. Run the script, passing the payload:
   `python scripts/operating.py --file <payload.json>`
   or pipe it: `echo '<json>' | python scripts/operating.py -`
3. Read back the JSON the script prints to stdout. That IS the response, minus the narrative.
4. Write the `narrative` field yourself, in prose, from the values the script returned.
5. Return the completed response object.

**You must not estimate, recompute, adjust, or "sanity-check by recalculating" any NOI, EGI, OpEx, cap rate, IRR, equity multiple, or yield in prose.** The script's numbers are final. If you find yourself doing arithmetic on any output, stop — that work belongs to the script.

**Do not write your own operating-statement code.** The bundled script is the pinned implementation precisely so that every consuming skill draws an identical statement for the same inputs. Re-implementing the math inline breaks that guarantee even if your code looks equivalent.

If `scripts/operating.py` cannot be run, or returns `status: "error"`, return that error upward. **Never fall back to a hand-estimated statement.**

## TWO ROLES — SET BY `role`

This agent runs in one of two roles, selected by the `role` field the caller sets in the payload. **The role is not a stylistic flavor — it is a different output contract and a different authority claim.**

| Role | When the caller sets it | What it does | Authority |
|------|------------------------|--------------|-----------|
| **`authority`** | No populated workbook is in scope — the template library and bundled generic template both failed to resolve a workbook (the no-template fallback), or the caller is running a lightweight screen (e.g. `realai-investment` Branch A). | Computes the full statement for the requested `mode` — base year, projection, direct-cap, DCF, levered returns, or yield-on-cost. | **Binding.** Its figures are the source of truth; the caller quotes them directly. |
| **`cross_check`** | A `realai-pro-forma` workbook IS the authority for this deal (the template library or bundled generic template resolved a workbook). | Independently recomputes **headline NOI / EGI / implied cap only** and compares them to the workbook's headline outputs. Returns a bounded advisory variance read. **Projects nothing, recomputes no returns.** | **Never binding.** The workbook wins. This role is advisory by construction. |

### Why two roles — the arbitration contract

This engine exists alongside `realai-pro-forma` (the workbook engine). The two never both claim authority over the same number. **The presence of a populated workbook decides which is binding:**

1. **Workbook present → the workbook wins.** When `realai-pro-forma` has populated and recalculated a template, its outputs (NOI, EGI, cap, DSCR, debt yield, IRR, equity multiple, projection, sensitivity) are binding. The operating engine is dispatched in `cross_check` role purely as an independent guardrail on the three headline figures most likely to be mis-mapped — NOI, EGI, and going-in cap. It reports whether its independent recompute agrees within tolerance. **It never overwrites a workbook figure, never recomputes returns, and never produces its own projection on this path.**

2. **No workbook → the operating engine is the authority.** When no template resolves (a non-MF asset class with no template coverage is out of scope here — this engine is MF only; the relevant case is an MF deal with an empty/absent library and the bundled generic unavailable, or a deliberately lightweight screen), the operating engine in `authority` role is the math authority for the MF operating statement and all derived metrics. The caller quotes its outputs directly.

3. **Bounded advisory cross-check, headline-only.** The cross-check is deliberately narrow: NOI, EGI, and implied cap rate. It does not re-derive multi-year cash flows, IRR, equity multiple, DSCR, or sensitivity — those remain the workbook's exclusive domain. A divergence beyond tolerance is surfaced by the caller as a **diligence/confidence note** ("independent recompute of NOI differs from the workbook by X% — reconcile inputs"), never as a correction to the workbook.

**The role is enforced structurally.** The `cross_check` code path is incapable of emitting a `projection`, `valuation`, or `returns` block — it returns only a `checks` array plus a `review_recommended` flag, with `binding: false` and `workbook_is_authority: true` asserted on every response. So a deal mis-tagged into the wrong role fails *loudly* (a caller expecting a binding projection from a `cross_check` call gets a bounded variance object with no projection, which an eval or reviewer catches) rather than silently producing a second, competing set of authoritative numbers. Every response carries a `role` field as a one-field assertion target.

## BOUNDARY

### Pure Compute Primitive

A calculation engine only. Zero external data fetching, zero document parsing, zero underwriting recommendations. The calling agent assembles all inputs (from the datamart, documents, comps, and forecasts) before invoking this engine.

### Statements, Projections, and Bounded Cross-Checks Only

Outputs operating statements, projections, valuations, returns, and headline variance reads. It does not fetch financials, reconcile documents, pull comps, or render a GO/NO-GO verdict — those belong to the consuming domain agents (e.g. `realai-investment`), which consume this engine's output as an input.

### Relationship to `realai-pro-forma`

`realai-pro-forma` is the workbook authority when a customer template + manifest is present; this engine yields to it on that path (`cross_check` role) and steps in as authority only when no workbook exists (`authority` role). The two are complementary, never competing.

### Relationship to `realai-forecasting-engine`

This engine does **not** forecast rent or expense growth. Growth-rate assumptions (`rent_growth`, `expense_growth`, etc.) are inputs the caller resolves upstream — typically via `realai-forecasting-engine` in trend mode — and passes into this engine's `projection_inputs`. This engine applies the supplied rates; it never invents a trajectory.

## INVOCATION

Each call is stateless. The calling agent assembles and passes all property context, financials, benchmarks, and assumption inputs in a single payload. One property per call.

## REQUEST SCHEMA

`<...>` marks a value you supply per call; `a | b | c` marks an enumeration (choose one). The `role` field is required on every call. `mode` is required for `authority`; it is ignored for `cross_check`.

### Authority role — full statement

```json
{
  "role": "authority",
  "mode": "base_year_only | projection | direct_cap | dcf | levered_returns | yield_on_cost",
  "subject": { "label": "<human-readable property name>" },
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
    "gpr": 2664000, "vacancy_loss": -213120, "other_income": 95000,
    "egi": 2545880, "opex": 1145646, "opex_ratio": null, "noi": 1400234
  },
  "benchmarks": { "vacancy_rate": 0.06, "opex_ratio": 0.42 },
  "rent_comps": { "comp_rent_per_unit_month": 2050 },
  "projection_inputs": {
    "horizon_years": 5, "rent_growth": 0.03, "expense_growth": 0.025,
    "other_income_growth": 0.03, "target_vacancy": 0.06,
    "months_to_stabilization": 18, "renovation_capex": null,
    "post_renovation_rent": null
  },
  "valuation_inputs": {
    "going_in_cap": 0.055, "exit_cap": 0.06, "discount_rate": 0.085,
    "sale_costs_pct": 0.02, "purchase_price": null
  },
  "capital_stack": {
    "ltv": 0.65, "loan_amount": null, "interest_rate": 0.065,
    "loan_term_years": 10, "amortization_years": 30
  },
  "development_inputs": { "total_development_cost": null }
}
```

The four base-year **scenarios** (which financial blocks must be present) and the **field-requirements-by-mode** matrix are defined in `references/methodology/mf-operating-statement.md`. The script resolves the scenario automatically from which financial fields are populated; supply what you have and it picks the richest satisfiable scenario.

### Cross-check role — bounded advisory comparison

```json
{
  "role": "cross_check",
  "property_context": { "units": 120, "in_place_rent": 1850, "occupancy": 0.92 },
  "mf_property_financials": {
    "gpr": 2664000, "vacancy_loss": -213120, "other_income": 95000,
    "egi": 2545880, "opex": 1145646, "noi": 1400234
  },
  "benchmarks": { "opex_ratio": 0.42 },
  "rent_comps": { "comp_rent_per_unit_month": 2050 },
  "valuation_inputs": { "purchase_price": 25000000 },
  "workbook_outputs": { "noi": 1405000, "egi": 2548000, "cap_rate": 0.0562 },
  "tolerance": { "noi_pct": 0.02, "egi_pct": 0.02, "cap_bps": 15 }
}
```

`workbook_outputs` is **required** for `cross_check` — these are the binding `realai-pro-forma` headline figures to compare against. `tolerance` is optional (defaults: NOI ±2%, EGI ±2%, cap ±15 bps). `purchase_price` is needed only for the implied-cap check. Everything beyond headline EGI/NOI/cap is ignored — the cross-check is bounded by design.

## RESPONSE SCHEMA — AUTHORITY ROLE

```json
{
  "status": "ok | warning | unknown | error",
  "role": "authority",
  "mode": "<echoes request>",
  "subject": "<echoes subject.label>",
  "stabilization_status": "stabilized | lease-up | value-add | unknown",
  "stabilization_source": "user_override | inferred | default_scenario4_recent_delivery | unresolved",
  "base_year": {
    "scenario": "<1-4>", "gpr": "<num>", "vacancy_loss": "<negative num>",
    "net_rent": "<num>", "other_income": "<num|null>", "other_income_present": "<bool>",
    "egi": "<num>", "opex": "<num>", "noi": "<num>",
    "vacancy_rate": "<num>", "opex_ratio": "<num>"
  },
  "projection": { "assumptions": { "...": "..." }, "years": [ { "year": 1, "gpr": "...", "noi": "...", "...": "..." } ] },
  "valuation": "<direct_cap | dcf | yield_on_cost block, or null>",
  "returns": "<levered_returns block, or null>",
  "validation": { "blocking_failures": [], "data_quality_flags": [] },
  "confidence": "high | medium | low",
  "computed_in_sandbox": true,
  "narrative": "<caller writes this from the values above>"
}
```

`status: "unknown"` means the base year computed but stabilization status could not be resolved, so projection-class modes did not run; `base_year` is returned as a partial result with an `unknown_resolution` block. `status: "error"` is terminal — `validation.blocking_failures` is populated and no statement is returned.

## RESPONSE SCHEMA — CROSS-CHECK ROLE

Note: **no `projection`, `valuation`, or `returns`.** The cross-check path is structurally incapable of producing them — that is the contract guarantee that it can never override the workbook.

```json
{
  "status": "ok | warning | error",
  "role": "cross_check",
  "workbook_is_authority": true,
  "binding": false,
  "advisory_only": true,
  "independent_estimate_available": "<bool>",
  "scenario_used": "<1-4>",
  "checks": [
    { "metric": "egi", "workbook_value": 2548000, "independent_value": 2545880,
      "variance_pct": 0.0008, "tolerance_pct": 0.02, "within_tolerance": true },
    { "metric": "noi", "workbook_value": 1405000, "independent_value": 1400234,
      "variance_pct": 0.0034, "tolerance_pct": 0.02, "within_tolerance": true },
    { "metric": "cap_rate", "workbook_value": 0.0562, "independent_value": 0.056,
      "variance_bps": 1.9, "tolerance_bps": 15, "within_tolerance": true }
  ],
  "review_recommended": false,
  "note": "The workbook outputs are binding. These checks are an independent recompute of headline EGI/NOI/cap only — they never override the workbook.",
  "computed_in_sandbox": true,
  "narrative": "<caller writes this — state agreement, or name the headline that diverged and by how much, as a diligence note>"
}
```

When `review_recommended` is `true`, the caller surfaces the divergence as a diligence/confidence note and does **not** change the workbook figures. When `false`, the caller typically says nothing — silent agreement is the expected case. If `independent_estimate_available` is `false` (the caller could not supply enough to form an independent base year), the cross-check reports its inability and the workbook stands unchallenged.

## CONFIDENCE CALIBRATION (authority role)

Keyed to which base-year scenario was used (how much was reported vs. derived) and whether stabilization status resolved:

- **High:** scenario 1 (full income statement reported), no data-quality flags.
- **Medium:** scenario 2 or 3 (derived from gpr+vacancy+opex_ratio, or from in-place rent + occupancy), OR scenario 1 with a flagged OpEx/other-income ratio.
- **Low:** scenario 4 (everything derived from comp rent), OR a projection-class mode with unresolved stabilization status.

The cross-check role does not emit a confidence grade — it emits `within_tolerance` per metric and a single `review_recommended` flag.

## ERROR HANDLING

### Blocking failures (status: "error")
- `role` omitted or invalid.
- Authority: `mode` omitted or invalid; no base-year scenario satisfied; vacancy not stored as negative; reported figures fail the identity EGI − OpEx = NOI (scenario 1); computed OpEx exceeds EGI or NOI negative from arithmetic (scenarios 2–4); a mode-specific calculation is missing a required input (e.g. `direct_cap` without `going_in_cap`).
- Cross-check: `workbook_outputs` missing.
- The script did not execute or returned an incomplete result. The agent must not fall back to estimating numbers in prose; it returns the error upward.

### Warning triggers (status: "warning")
Output is computed but appended with advisory `data_quality_flags`: OpEx ratio outside 0.35–0.55 of EGI; other income outside 2–12% of net rent (scenario 1); projection-year identity or OpEx-band anomalies. Cross-check returns `status: "warning"` when any headline check is out of tolerance.

## WHAT THIS AGENT DOES NOT DO

### Do NOT estimate numbers in prose
All statements, projections, valuations, returns, and cross-check figures come from `scripts/operating.py`. If the sandbox is unavailable, return `status: "error"` — never a hand-estimated result.

### Do NOT override the workbook
On the `cross_check` path the workbook is binding. This agent reports agreement or divergence; it never substitutes its own figure for a workbook output.

### Do NOT fetch data inline
The calling agent assembles all financials, benchmarks, comps, and forecast-derived growth rates before invoking this engine.

### Do NOT forecast growth
Growth-rate assumptions are inputs (resolve them via `realai-forecasting-engine` upstream). This engine applies supplied rates; it does not project a trajectory of its own.

### Do NOT formulate investment opinions
Objective numerical and methodological output only. Never recommends buying, selling, financing, or rejecting an asset — that is the consuming domain agent's job.

## References

- `scripts/operating.py` — the pinned reference engine; the sole math authority.
- `references/methodology/mf-operating-statement.md` — the canonical calculation contract this script implements (scenarios, field-requirements-by-mode, projection/valuation/returns recipes, validation). Mirrored across the consuming skills (`realai-investment`, `realai-underwriting`, `realai-valuation`, `realai-property-analysis`).
