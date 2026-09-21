# Response Contract

## Contents

- Response Schema: trend mode
- Example A response: Charlotte rent (trend)
- Response Schema: directional mode
- Reading position_label correctly
- Example B response: Atlanta office cap rate (directional)
- Consuming the Output
- Confidence Calibration
- Error Handling
- What This Engine Does NOT Do

## Response Schema: trend mode

Same notation as the request reference: `<...>` is a value the script produced, `a | b | c` is an enumeration. Every `methodology` field is sourced from an executed value; `computed_in_sandbox` is set only by the code path that ran the computation, never written by the model.

```json
{
  "status": "ok | warning | error",
  "mode": "trend",
  "metric": { "name": "<echoes request>", "units": "...", "family": "..." },
  "subject": "<echoes request subject.entity_id>",
  "horizon": "<e.g. 5_years_annual>",
  "base_case": [ { "period": "<label>", "value": "<number>", "pct_change": "<float>" } ],
  "upside_case": [],
  "downside_case": [],
  "methodology": {
    "primary_method": "Dampened trend extrapolation with structural terminal anchor and peer mean reversion",
    "history_depth_months": "<integer - calendar span, last minus first observation>",
    "history_point_count": "<integer - observations submitted; differs from the span when the cadence is coarser than monthly or gaps exist>",
    "lookback_requested_years": "<float or null - echoes requested_lookback_years>",
    "lookback_available_years": "<float - the span actually available>",
    "trend_r2": "<float, diagnostic only, not a gate>",
    "recent_annualized_growth": "<float>",
    "long_run_mean_growth": "<float>",
    "dampening_cap_applied": "<float>",
    "terminal_rate_applied": "<float, the structural anchor late years converge toward>",
    "terminal_rate_basis": "<string, how the terminal was derived>",
    "terminal_weight_cap_applied": "<float, 0.60 normally, 0.85 when boom guard fires>",
    "mean_reversion_applied": "<bool>",
    "peer_deviation_sigma_pre": "<float, or null if no peer cohort>",
    "peer_level_ratio": "<float, peer latest level / subject latest level; flagged beyond 1.5x either way; null without a peer>",
    "reversion_weight_per_year": "<float, or null>",
    "cyclical_drawdown_suspected": "<bool, true forces low confidence and a flat-hold projection>",
    "boom_extrapolation_suspected": "<bool, true caps confidence at medium and accelerates terminal convergence>",
    "boom_trigger": "<list - which condition(s) fired: above_terminal and/or single_regime; empty when the guard did not fire>",
    "stale_series_suspected": "<bool, true caps confidence at medium - trailing periods identical, possible non-refreshed source>",
    "peer_proxy_substituted": "<bool, true caps confidence at medium - trend basis came from a parent geography, not the subject>",
    "scenario_sigma_source": "residual_volatility_floored | structural_floor_only (operating short-history fallback)",
    "scenario_halfwidth_floor_applied": "<float, per-family band floor>",
    "params_version": "<string, terminal-rate table version>",
    "params_version_date": "<YYYY-MM-DD>",
    "computed_in_sandbox": true
  },
  "signals": {
    "supply_pressure": "elevated | moderate | low | unknown",
    "migration_signal": "positive | neutral | negative | unknown",
    "employment_signal": "positive | neutral | negative | unknown",
    "inflation_anchor": "<float, when family = operating>",
    "ceiling_proximity": "at_ceiling | approaching | room - only when structural_ceiling was supplied"
  },
  "confidence": "high | medium | low",
  "data_quality_flags": [],
  "caller_disclosures": "<verbatim echo of the request's caller_disclosures block, or null - assembly decisions land in the logged result whether or not the narrative repeats them>",
  "narrative": "<caller writes this; foreground the band, name any reversion, state which signals were flagged without applying them>"
}
```

The `signals` block includes only keys relevant to the family.

## Example A response: Charlotte rent (trend)

```json
{
  "status": "warning",
  "mode": "trend",
  "metric": { "name": "mf_rent_ts.asking_rent_latest", "units": "$", "family": "rent_or_occupancy" },
  "subject": "msa_charlotte_nc",
  "horizon": "5_years_annual",
  "base_case": [
    { "period": "Year 1", "value": 1982.02, "pct_change": 0.0404 },
    { "period": "Year 2", "value": 2056.97, "pct_change": 0.0378 }
  ],
  "upside_case": [
    { "period": "Year 1", "value": 2020.12, "pct_change": 0.0604 },
    { "period": "Year 2", "value": 2142.97, "pct_change": 0.0608 }
  ],
  "downside_case": [
    { "period": "Year 1", "value": 1943.92, "pct_change": 0.0204 },
    { "period": "Year 2", "value": 1972.72, "pct_change": 0.0148 }
  ],
  "methodology": {
    "primary_method": "Dampened trend extrapolation with structural terminal anchor and peer mean reversion",
    "history_depth_months": 60,
    "history_point_count": 6,
    "lookback_requested_years": null,
    "lookback_available_years": 5.0,
    "trend_r2": 0.9931,
    "recent_annualized_growth": 0.0404,
    "long_run_mean_growth": 0.0408,
    "dampening_cap_applied": 0.50,
    "terminal_rate_applied": 0.028,
    "terminal_rate_basis": "family terminal 0.0280",
    "terminal_weight_cap_applied": 0.85,
    "mean_reversion_applied": false,
    "peer_deviation_sigma_pre": 0.7304,
    "peer_level_ratio": 0.9963,
    "reversion_weight_per_year": null,
    "cyclical_drawdown_suspected": false,
    "boom_extrapolation_suspected": true,
    "boom_trigger": ["single_regime"],
    "stale_series_suspected": false,
    "peer_proxy_substituted": false,
    "scenario_sigma_source": "residual_volatility_floored",
    "scenario_halfwidth_floor_applied": 0.02,
    "params_version": "2026Q3.5",
    "params_version_date": "2026-07-22",
    "computed_in_sandbox": true
  },
  "signals": { "supply_pressure": "elevated", "migration_signal": "positive", "employment_signal": "positive" },
  "confidence": "medium",
  "data_quality_flags": [
    "boom extrapolation suspected: the entire history sits inside a single post-2020 regime, so the series' own long-run mean cannot serve as a leveling anchor. The engine accelerated convergence toward the terminal rate rather than carrying the boom forward, and capped confidence at medium. Supply a longer history that spans a full cycle, or have the calling agent apply structural context (supply pipeline, rent-to-income ceiling) before using the near-term years as a multi-year assumption."
  ],
  "caller_disclosures": {
    "peer_selection_basis": "parent market default; level ratio 1.00, both series trending up at a similar pace",
    "sibling_series_note": "in-place rent checked in the same fetch; tracks asking",
    "sibling_divergence_pct": 0.004
  },
  "narrative": "Base case starts at recent ~4% growth but decays toward a 2.8% structural terminal rate over the hold, because the entire history sits in the post-2020 regime: the boom-extrapolation guard fired, accelerating that convergence and capping confidence at medium. The subject tracked its peer cohort closely (0.73 sigma, under the 1.0 trigger), so no reversion blend was applied. Elevated supply and a positive inbound-migration signal are flagged for the consuming agent to weigh; neither was applied to the computed figures. The band spans roughly +6% to 0% by the back years; that range, not the central line, is the read for a 5-year horizon."
}
```

## Response Schema: directional mode

Note: **no `base_case`, `upside_case`, `downside_case`, or `horizon`.** The directional path is structurally incapable of producing projected values. It carries `band_position` instead.

```json
{
  "status": "ok | warning",
  "mode": "directional",
  "metric": { "name": "<echoes request>", "units": "...", "family": "capital_markets" },
  "subject": "<echoes request subject.entity_id>",
  "lookback": "<e.g. 60_months_observed>",
  "band_position": {
    "historical_band": { "min": "<number>", "structural_mean": "<number>", "max": "<number>" },
    "current_level": "<number>",
    "position_in_band": "<float, 0 = at min, 1 = at max>",
    "position_label": "rich | mid | cheap"
  },
  "band_position_trailing_10y": "<same shape as band_position, computed over the trailing 10 years - present only when the observed window exceeds 10 years, else null>",
  "signals": { "rate_environment": "tightening | easing | stable | unknown" },
  "methodology": {
    "primary_method": "Directional band-position read (no projection)",
    "history_depth_months": "<integer - calendar span>",
    "history_point_count": "<integer - observations submitted>",
    "lookback_requested_years": "<float or null>",
    "lookback_available_years": "<float>",
    "stale_series_suspected": "<bool, true caps confidence at medium>",
    "params_version": "<string>",
    "params_version_date": "<YYYY-MM-DD>",
    "note": "Oscillating metric: structural band from observed history; no growth applied, no future values produced. Caller synthesizes outlook from band position and rate-environment signal.",
    "computed_in_sandbox": true
  },
  "confidence": "high | medium | low",
  "data_quality_flags": [],
  "caller_disclosures": "<verbatim echo of the request's caller_disclosures block, or null>",
  "narrative": "<caller writes this; state band position and rate signal as the two facts, then the caller's own synthesized lean>"
}
```

## Reading position_label correctly

`position_label` describes where the metric's current LEVEL sits in its own observed range: `rich` = near the historical maximum of the metric itself, `cheap` = near the minimum. It is a statement about the metric's level, never about asset pricing. Worked example: an office cap rate at the top of its 20-year band is `rich` (the metric is high) even though the assets it prices are historically cheap on that basis; getting this backwards in a memo reverses the compression/expansion read. For cap rates the inversion is always confusing ("rich" reads backwards from normal broker usage), so for `capital_markets` the convention statement is mandatory, not conditional: spell out, in the same sentence the label is used, that rich/cheap describe the metric's own level (high cap rate = wide yield = cheap asset). Avoiding the label instead of explaining it is a workaround, not compliance.

## Example B response: Atlanta office cap rate (directional)

```json
{
  "status": "warning",
  "mode": "directional",
  "metric": { "name": "caprate_ts.office", "units": "%", "family": "capital_markets" },
  "subject": "msa_atlanta_ga",
  "lookback": "60_months_observed",
  "band_position": {
    "historical_band": { "min": 6.0, "structural_mean": 6.8, "max": 7.9 },
    "current_level": 7.9,
    "position_in_band": 1.0,
    "position_label": "rich"
  },
  "band_position_trailing_10y": null,
  "signals": { "rate_environment": "stable" },
  "methodology": {
    "primary_method": "Directional band-position read (no projection)",
    "history_depth_months": 60,
    "history_point_count": 6,
    "lookback_requested_years": null,
    "lookback_available_years": 5.0,
    "stale_series_suspected": false,
    "params_version": "2026Q3.5",
    "params_version_date": "2026-07-22",
    "note": "Oscillating metric: structural band from observed history; no growth applied, no future values produced. Caller synthesizes outlook from band position and rate-environment signal.",
    "computed_in_sandbox": true
  },
  "confidence": "high",
  "data_quality_flags": [
    "scenarios ignored: capital_markets is directional, not projected; no scenario envelope is produced"
  ],
  "caller_disclosures": null,
  "narrative": "The office cap rate sits at the very top of its observed five-year range (6.0-7.9%, current 7.9%), having expanded steadily off the 2020 low. The rate environment is flagged stable. These two facts are reported without synthesis; the consuming agent decides whether a band-top level plus a stable rate environment implies further expansion, a plateau, or compression for its own assumption set."
}
```

This example's window is under 10 years, so `band_position_trailing_10y` is null. A deeper series (say a 2005-to-present cap-rate history) returns BOTH bands populated - full-history and trailing-10-year - and the narrative reports both, especially when their labels disagree. Passing the full available history is the rule (see the request reference); the dual band exists so a multi-regime window is handled mechanically rather than by truncating the input.

## Consuming the Output

- **Surface confidence and flags verbatim.** State the returned `confidence` tier and reproduce every `data_quality_flags` entry near the figures they qualify. Paraphrasing a guard warning into vague prose is a defect; the flag text is written for the end reader. Before finalizing any deliverable that cites this engine's output, confirm each cited figure carries (a) its confidence tier and (b) the name of any fired guard, inline or in an adjacent note - if you cannot point to where that appears in your own draft, it is missing; go back and add it.
- **Verbatim does not mean uncritical.** If a flag's stated figures look internally inconsistent, still quote the flag as-is, then append an explicit caller note surfacing the inconsistency for the reader (and report it as a possible engine bug). Never quietly reword a flag into something that resolves the inconsistency for the reader.
- **Disclosures are distinct labeled items, not caveat-paragraph filler.** Each required disclosure (peer substitution or omission, lookback truncation or shortfall, signal omission, sibling scope) appears as its own labeled line adjacent to the figure it qualifies - never folded into a general caveats paragraph where it reads as soft prose and gets under-weighted.
- **Reconcile signals against what you separately know.** If a returned signal contradicts a fact you hold from other sourced data (the engine says supply is low while your own pull shows deliveries outrunning absorption), do not write around it: trace the signal back to the input that drove it, fix or omit that input if it was wrong, and only then write the narrative. An unreconciled contradiction between an engine signal and your own prose means an input was never checked - a defect of the same severity as a hand-estimated number.
- **Flattening a multi-year path to one scalar.** When a downstream consumer (an operating-statement model, a pro forma cell) needs a single growth rate from the year-by-year `base_case` path, use the CAGR over the horizon (compound the path, annualize), not a simple average, and state which years it compresses - including where the approximation error concentrates (e.g., "the flat 1.2% understates Year 1, which the base case put near 0%, and understates Year 5, near 2.4%"). Two callers flattening the same forecast must converge on the same number.
- **Directional reads stay directional.** Turning a band position plus a rate signal into a point estimate (e.g., an exit cap) is the consuming analysis's documented judgment, made in narrative with the reasoning shown. The engine deliberately provides no formula for it; hard-coding one would relocate the projecting-an-oscillating-metric error one level up.

## Confidence Calibration

### Trend mode

Keyed to data sufficiency and how much the trajectory had to be corrected, not to R-squared (see the methodology reference).

- **High:** 24+ months of clean history, horizon 5 years or less, the reversion blend did not materially move the trajectory (subject near its peer cohort), no boom-extrapolation guard fired, and any present signals are mutually consistent.
- **Medium:** history 12-24 months, OR the reversion blend materially altered the trajectory (subject far from cohort), OR the boom-extrapolation guard fired (recent growth well above terminal, or window entirely post-2020), OR emitted signals conflict (e.g. positive migration but elevated supply).
- **Low:** history under 12 months, OR horizon over 5 years, OR local history directly contradicts the peer-cohort direction.

### Directional mode

Keyed to lookback depth, since no projection is made: **High** 24+ months, **Medium** 12-24 months, **Low** under 12 months.

## Error Handling

### Blocking Failures (status: "error")

- Fewer than 6 valid historical data points, except the `operating` family with 1-5 points, which degrades to the structural-terminal-rate fallback (status `warning`, confidence `low`) instead of erroring
- `family` omitted or invalid
- A `history_check` / `peer_history_check` mismatch (declared count, sum, first_value, or last_value does not match the submitted array) - loud by design; it means the array was corrupted between source and payload
- `as_of` supplied but not parseable as YYYY-MM-DD; `peer_history_check` supplied without a `peer_history`
- Trend mode only: horizon outside the 1-to-10-year envelope, or `horizon.years` missing/non-integer (directional mode does not require a horizon)
- Script computation did not execute or returned an incomplete result. Never fall back to estimating numbers in prose; return the error.

### Warning Triggers (status: "warning")

Output is computed but appended with alerts:

- Trend: dampening cap reached early (far-out years weakly informative); thin or absent peer cohort (reversion not applied); wide scenario divergence relative to the point estimate; emitted signals conflict with the computed direction; cyclical drawdown suspected (short history in a correction: held flat after year 1, confidence forced low, structural context required from the caller); boom extrapolation suspected (the flag names its actual trigger(s): growth above 1.75x terminal and/or a window entirely post-2020 - accelerated convergence to terminal, confidence capped at medium, structural context required from the caller); stale series suspected (trailing periods identical: confidence capped at medium); last observation stale relative to the declared `as_of` (confidence capped at medium); peer mismatch suspected (subject deviates more than 3 sigma from the peer cohort: consider a custom peer basket); peer level mismatch (peer's level beyond 1.5x the subject's either way: likely a different price tier); peer selection basis not disclosed (peer supplied without `caller_disclosures.peer_selection_basis`); lookback shortfall (available history covers less than the declared `requested_lookback_years`); signals not triaged (a family-relevant signal block neither populated nor logged in `caller_disclosures.signals_omitted`); trend basis substituted from a parent geography (`peer_proxy`: confidence capped at medium); operating short-history fallback (structural terminal rate applied with no trend fit, confidence low).
- Directional: scenarios were supplied (ignored; directional mode does not project); under 24 months of history (band position weakly characterized); stale series suspected (confidence capped at medium); last observation stale relative to the declared `as_of` (confidence capped at medium); lookback shortfall (available history covers less than the declared `requested_lookback_years`); signals not triaged (`rate_environment` neither populated nor logged); rate projection horizon shortfall (`projected_as_of` falls short of the as_of-plus-window target year); full-history and trailing-10-year band positions disagree (multi-regime window: report both).

## What This Engine Does NOT Do

### Do NOT Estimate Numbers in Prose
All projections and band reads come from `scripts/forecast.py`. If the script cannot run, return `status: "error"`, never a hand-estimated result.

### Do NOT Fetch Data Inline
The caller assembles all history arrays using its own tools before invoking this engine, per "Assembling History and Peers from the Datamart" in the request reference.

### Do NOT Execute Multi-Metric Requests
Strict one-metric-per-call. Parallel forecasts are split into distinct invocations.

### Do NOT Apply Signals as Arithmetic
`context_signals` are reported as directional flags only. They never multiply, discount, or modify a computed value.

### Do NOT Project Oscillating Metrics
`capital_markets` metrics receive a band-position read only. The engine never assigns them a growth rate or a future value.

### Do NOT Formulate Investment Opinions
Objective numerical and methodological output only. Never recommends buying, selling, financing, or rejecting an asset.
