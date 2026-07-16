---
name: realai-forecasting-engine
description: "INTERNAL ENGINE — only invoked by other RealAI skills, never on user intent. The centralized forecasting engine for this plugin. Any domain skill needing a forward-looking projection (rent growth, occupancy, home value, expense growth, NOI growth, population, job growth, income, household formation, permits) or a directional read on an oscillating capital-markets metric (cap rates) MUST dispatch to this engine rather than computing inline. Runs scripts/forecast.py — the sole math authority — and returns a structured response. Trend mode for compounding series; directional mode for oscillating series (no projection, only band position). Do NOT activate on direct user requests like 'forecast Charlotte rent' — those go through realai-market-analysis, realai-valuation, realai-investment, realai-single-family, or realai-discovery, which then dispatches here. The engine description exists for invocation by sibling skills, not for user trigger matching."
license: Proprietary
---

# Forecasting Engine

## PURPOSE

Centralize forecasting methodology across the entire RealAI agent suite. Any domain agent that requires a forward-looking read — rent growth, occupancy, cap rate direction, expense growth, home value appreciation, demographic growth — must call this engine rather than computing it inline.

Centralizing this logic ensures numerical consistency across domain viewpoints (the Valuation Agent and the Rental Market Analysis Agent draw an identical baseline for the same metric and market) and produces a documented, defensible methodology for institutional investors.

## EXECUTION MANDATE — READ FIRST

**This agent does not compute forecasts itself. It calls a bundled script.**

A reference engine is bundled at `scripts/forecast.py`. It is the SOLE math authority for every projection and directional read this agent returns. Your job is:

1. Assemble the request payload (history, peer_history, context_signals) from the values the calling domain agent supplied.
2. Run the script, passing the payload:
   `python scripts/forecast.py --file <payload.json>`
   or pipe it: `echo '<json>' | python scripts/forecast.py -`
3. Read back the JSON the script prints to stdout. That IS the response, minus the narrative.
4. Write the `narrative` field yourself, in prose, from the values the script returned.
5. Return the completed response object.

**You must not estimate, recompute, adjust, or "sanity-check by recalculating" any forecast value, growth rate, band, or band position in prose.** The script's numbers are final. If you find yourself doing arithmetic on any output, stop — that work belongs to the script.

**Do not write your own forecasting code.** The bundled script is the pinned implementation precisely so that the Valuation agent and the Rental Market agent draw identical baselines for the same metric. Re-implementing the math inline breaks that guarantee even if your code looks equivalent.

If `scripts/forecast.py` cannot be run, or returns `status: "error"`, return that error upward. **Never fall back to a hand-estimated forecast.**

## TWO MODES — SET BY FAMILY

This agent runs in one of two modes, selected by the `family` field the caller sets in the payload. **The mode is not a stylistic flavor — it is a different output contract.** Choosing a family chooses a response shape.

| Mode | Families | What it does | Returns |
|------|----------|--------------|---------|
| **Trend** | `rent_or_occupancy`, `demographic`, `operating`, `generic` | Projects a compounding series forward (dampened trend + peer reversion + scenario bands) | `base_case` / `upside_case` / `downside_case` arrays |
| **Directional** | `capital_markets` | Reports where an oscillating metric sits in its own historical band, plus the rate signal. **Projects nothing.** | `band_position` + `signals`; **no projected values** |

**Why two modes.** Compounding series (rent, population, home value) have a genuine forward trajectory; projecting them is appropriate. Oscillating series (cap rates) sit in a structural band and move on conditions — they do not compound. Fitting a growth rate to a cap rate and projecting it forward is a category error that produces runaway nonsense (a cap rate climbing indefinitely). For those metrics the honest output is a directional read — where the level sits relative to its own history, plus the rate environment — which the calling agent synthesizes into its own view. This agent emits no outlook, no firmer/softer call, and no future cap-rate value.

**The mode is enforced structurally.** The directional code path is incapable of emitting a `base_case`. So a metric mistagged into the wrong family fails *loudly* — a cap rate accidentally tagged `generic` falls into trend mode and produces a visibly absurd projection an eval or reviewer catches — rather than silently emitting a plausible-looking fake trajectory. Every response carries a `mode` field (`trend` | `directional`) as a one-field assertion target.

## BOUNDARY

### Pure Compute Primitive

A calculation engine only. Zero external data fetching, zero document parsing, zero underwriting or recommendations.

### Rates, Trajectories, and Band Reads Only

Outputs market-level or property-level rates, trajectories, or band positions. It does not generate pro formas, cash flow waterfalls, or returns — those belong to domain agents (e.g., the Multifamily Operating Statement Agent), which consume this engine's output as an upstream input.

## INVOCATION

Each call is stateless. The calling agent assembles and passes all required history arrays, peer arrays, and context in a single payload. One metric per call.

## METRIC SPECIFICATION

The caller specifies the metric and which behavior family it belongs to, rather than choosing from a fixed list, so the agent stays extensible as datamart topics and asset classes broaden. **The family field is supplied by the caller — there is no internal lookup mapping a metric name to a family.** The calling agent is responsible for tagging correctly; the engine guarantees only that each mode emits its own shape (see TWO MODES).

### Required Metric Fields

| Field | Description |
|-------|-------------|
| `name` | What's being forecast in plain language (e.g., "asking rent for 2BR units in Charlotte MSA," "office cap rate for Atlanta," "population for Mecklenburg County") |
| `units` | Denomination ($, $/SF, %, bps, count, index) |
| `family` | Selects the mode and the overlays/signals — see below |

### Family Parameter Options

| Value | Mode | Definition |
|-------|------|------------|
| `rent_or_occupancy` | Trend | compounding; supply and demand signals evaluated and emitted |
| `demographic` | Trend | compounding; migration and employment signals emitted |
| `operating` | Trend | compounding; anchored to inflation floor; no supply/demand signal |
| `generic` | Trend | compounding; no signals, pure dampened trend with reversion |
| `capital_markets` | **Directional** | **oscillating; NO projection.** Reports band position + rate signal |

### Common Use Cases

**Trend:** asking and in-place rent (any asset class, any segment), occupancy, home value, expense growth, NOI growth, population, job growth by sector, median household income, household formation, building permit pace.

**Directional:** cap rate by asset class (multifamily, office, industrial, retail), and any other metric that oscillates around a structural level rather than compounding.

## REQUEST SCHEMA

**Illustrative payload, not a template of defaults.** The structure below is the universal envelope for *every* metric and family. Read the notation literally:

- `<...>` marks a value you supply per call. Nothing inside angle brackets is a default.
- `a | b | c` marks an enumeration — choose exactly one.
- The two examples that follow fill the *identical* structure with different metrics and different modes, to make clear the envelope is metric-agnostic.

```json
{
  "metric": {
    "name": "<datamart field or plain-language metric, e.g. mf_rent_ts.asking_rent_latest>",
    "units": "$ | $/SF | % | bps | count | index",
    "family": "rent_or_occupancy | capital_markets | demographic | operating | generic"
  },
  "subject": {
    "entity_type": "nation | state | market | submarket | county | census_place | neighborhood | zipcode | centum | property",
    "entity_id": "<UUID or string>",
    "label": "<human-readable name>"
  },
  "horizon": {
    "years": "<integer, 1–10 — used by trend mode; ignored by directional mode>",
    "intervals": "annual | quarterly | 12_24_36_months"
  },
  "history": [
    { "period": "<YYYY-MM-DD>", "value": "<number>", "source": "datamart | user_roll | zillow" }
  ],
  "peer_history": [
    { "period": "<YYYY-MM-DD>", "value": "<number>", "source": "datamart | user_roll | zillow" }
  ],
  "context_signals": {
    "supply_pipeline": {
      "existing_stock": "<integer>",
      "under_construction_t12": "<integer>",
      "permitted_units_t13_t24": "<integer>"
    },
    "migration": {
      "inbound_income_vs_outbound_pct": "<float, e.g. 0.12 = inbound cohort income 12% above outbound>"
    },
    "employment": {
      "job_growth_1_year_pct": "<float, e.g. 0.032 = 3.2% YoY job growth>"
    },
    "rate_environment": {
      "direction": "tightening | easing | stable",
      "note": "<free text, optional>"
    }
  },
  "scenarios": ["base"]
}
```

`context_signals` is informational and may be partially populated or omitted. Include only the sub-blocks relevant to the family. **No value inside `context_signals` is ever multiplied into a number — these drive directional flags only.** `horizon` and `scenarios` are used by trend mode; directional mode ignores both (it does not project).

### Assembling History and Peers from the Datamart

The engine does not fetch — these rules govern what the caller hands it, so a trend is not poisoned before the script ever runs:
 
- **Rent and occupancy** (`rent_or_occupancy`): histories come from the time-series topics — `mf_rent_ts` (aggregate), `mf_rent_ts_by_beds` / `mf_rent_ts_by_beds_baths` (segment-level), `sfr_rent_ts`, `sfr_rent_ts_by_unit_category` — never from the snapshot or detail siblings, which carry only the current state. Every rent time-series topic requires a `period_type` filter and the accepted values differ by topic: `mf_rent_ts` and its `_by_beds*` variants take `Month` or `Week`; `sfr_rent_ts` takes `Quarter`; `sfr_rent_ts_by_unit_category` takes `Month` or `Week`. Use `Month` where available for forecast histories (weekly cadence adds noise, not signal, at a 1–10 year horizon) and hold one `period_type` constant across a history array — never mix cadences in a single series.
- **Home values**: `home_sales_and_values_ts` (monthly; `period_type` is `MONTH`). 
- **Cap rates** (`capital_markets`): `caprate_ts` — a quarterly series (`period_type` is `QUARTERLY`), market grain only, one field per property type (`multifamily`, `office`, `industrial`, `single_family_rental`, `self_storage`, `senior_housing`, `retail_strip_center`, `retail_neighborhood_center`, `retail_power_center`). For a finer-grain subject the caller passes the parent market's series and labels the subject accordingly.
- **Permit pace**: `permit_ts` (monthly; census place, county, market, and state grains). Single-family, multifamily, and total units are separate fields (`sfr_units_permitted`, `mf_units_permitted`, `total_units_permitted`) — pick the segment that matches the metric, never blend them.
- **Demographic, income, and operating series**: the datamart carries no geographic time series for population, income, or household formation (those topics are snapshots with trailing-change fields) and no NOI or expense time series. Histories for the `demographic` and `operating` families come from the caller's own sources (e.g., owner operating statements as `user_roll`) — tag `source` honestly.
- **Peer history**: the same field at the same `period_type` from the parent or benchmark geography — submarket or zipcode → parent market, market or state → nation, property → its surrounding market — aligned period-for-period with the subject series.
- **Depth**: target 24+ months (the high-confidence bar) and ideally more than 30 (past the cyclical-drawdown guard's short-window trigger); below 6 valid points the engine errors.

### Example A — market rent (`rent_or_occupancy`, trend mode)

```json
{
  "metric": { "name": "mf_rent_ts.asking_rent_latest", "units": "$", "family": "rent_or_occupancy" },
  "subject": { "entity_type": "market", "entity_id": "msa_charlotte_nc", "label": "Charlotte MSA" },
  "horizon": { "years": 5, "intervals": "annual" },
  "history": [
    { "period": "2020-01-01", "value": 1560.00, "source": "datamart" },
    { "period": "2021-01-01", "value": 1640.00, "source": "datamart" },
    { "period": "2022-01-01", "value": 1715.00, "source": "datamart" },
    { "period": "2023-01-01", "value": 1780.00, "source": "datamart" },
    { "period": "2024-01-01", "value": 1842.00, "source": "datamart" },
    { "period": "2025-01-01", "value": 1905.00, "source": "datamart" }
  ],
  "peer_history": [
    { "period": "2020-01-01", "value": 1610.00, "source": "datamart" },
    { "period": "2021-01-01", "value": 1660.00, "source": "datamart" },
    { "period": "2022-01-01", "value": 1730.00, "source": "datamart" },
    { "period": "2023-01-01", "value": 1810.00, "source": "datamart" },
    { "period": "2024-01-01", "value": 1855.00, "source": "datamart" },
    { "period": "2025-01-01", "value": 1898.00, "source": "datamart" }
  ],
  "context_signals": {
    "supply_pipeline": { "existing_stock": 142000, "under_construction_t12": 9800, "permitted_units_t13_t24": 5400 },
    "migration": { "inbound_income_vs_outbound_pct": 0.12 }
  },
  "scenarios": ["base", "upside", "downside"]
}
```

### Example B — office cap rate (`capital_markets`, directional mode)

Same envelope, different metric and mode. `units` in `%`, only the `rate_environment` signal is relevant, and `horizon` / `scenarios` will be ignored — directional mode does not project.

```json
{
  "metric": { "name": "caprate_ts.office", "units": "%", "family": "capital_markets" },
  "subject": { "entity_type": "market", "entity_id": "msa_atlanta_ga", "label": "Atlanta MSA" },
  "horizon": { "years": 5, "intervals": "annual" },
  "history": [
    { "period": "2020-01-01", "value": 6.0, "source": "datamart" },
    { "period": "2021-01-01", "value": 6.2, "source": "datamart" },
    { "period": "2022-01-01", "value": 6.5, "source": "datamart" },
    { "period": "2023-01-01", "value": 6.8, "source": "datamart" },
    { "period": "2024-01-01", "value": 7.4, "source": "datamart" },
    { "period": "2025-01-01", "value": 7.9, "source": "datamart" }
  ],
  "context_signals": {
    "rate_environment": { "direction": "stable", "note": "policy rate expected flat over hold" }
  }
}
```

## TREND METHODOLOGY — THREE COMPUTED OPERATIONS

For trend families, the sandbox executes these three steps in order on the `history` (and `peer_history`) arrays. This is the complete arithmetic — there are no basis-point overlays.

### 1. Dampened Trend Extrapolation

Compute the annualized growth rate from a log-linear regression on the historical series. Project it forward, but pull the projected growth rate toward the series' own long-run mean growth as the horizon extends, so near-term years stay close to recent momentum and later years decay toward the long-run average.

A single horizon-scaled dampening weight is used rather than fixed per-year breakpoints: `projected_growth_t = recent_growth * (1 - d_t) + long_run_mean_growth * d_t`, where `d_t` ramps linearly from a year-1 weight (`0.20`) up to a cap (`0.50`), so far-out years are at most a 50/50 blend of recent momentum and long-run mean. The ramp and cap are single tunable parameters in the script's `PARAMS` block.

R² is computed and reported as a diagnostic. **It does not gate execution and is not a quality threshold** — rent and price series are autocorrelated and clear high R² even when a trend is about to break.

### 2. Mean Reversion Toward Peer Median (spatial)

**Trigger:** Applied when `peer_history` is supplied and the subject's historical growth deviates from the peer cohort by more than one standard deviation (the `σ > 1.0` trigger).

**Compute:** Blend the subject trajectory toward the peer-cohort growth rate, at a cumulative `0.30`/year rate over the horizon, capped at full reversion. This is the single most load-bearing adjustment for the domain — it prevents a hot submarket from extrapolating to the moon. The realized weight and pre-adjustment deviation are recorded in the methodology block.

### 3. Scenario Envelope

**Trigger:** Generated when `scenarios` includes `upside` and/or `downside`.

**Compute:** Plot ±1σ bands (σ from the historical series' residual volatility of period-over-period growth) around the base case, widening at each interval (×`1.15`/year on the half-width) to reflect compounding uncertainty.

**For 5-year real estate forecasts, the band is the deliverable; the point estimate is decoration.** Narrative should foreground the range.

### Cyclical-Drawdown Guard

A short history sitting inside a correction is the engine's hardest case, and the one most likely to mislead. When the window is short (≤ 30 months) the recent growth *and* the long-run mean computed off it can both be negative — so dampening pulls toward a negative anchor and the engine extrapolates the correction forward. That is the wrong frame for a multi-year hold: the window is too short to contain a full cycle, so the engine cannot distinguish a cyclical trough from a structural decline.

**Trigger:** history depth ≤ 30 months AND trailing annualized growth below −0.5%.

**Behavior when triggered:** the engine does **not** project the decline forward. It holds the honest trailing rate for year 1 (the correction has not cleared) and goes flat (0%) thereafter — it explicitly does **not** invent a recovery curve, because that is a judgment the engine cannot make from a short window. It forces confidence to `low`, sets `cyclical_drawdown_suspected: true` in the methodology block, and leads the warnings with an instruction to the calling agent: supply a longer history that spans a full cycle, or apply structural context and a defended recovery path before using the output as a multi-year assumption.

This is deliberate division of labor. The engine's job is to stop confidently extrapolating a correction and to *flag that judgment is required* — not to replicate the analyst's cycle-bridge reasoning. That reasoning (e.g., "the pipeline is decelerating, employment base is intact, recovery by year 3") belongs in the consuming domain agent, which sees the low-confidence flag and the warning and supplies the structural view. A confident wrong number is worse than a flagged hold.

## DIRECTIONAL METHODOLOGY — BAND POSITION, NO PROJECTION

For `capital_markets`, the sandbox computes **no trend, no growth, and no future values.** It reports two observed facts:

1. **The historical band** — min, structural mean, and max of the observed series. This is a factual description of the past.
2. **Current position in that band** — `position_in_band` is `(current − min) / (max − min)`, from `0` (at the historical low) to `1` (at the historical high), plus a coarse `position_label`: `rich` (top third, ≥ 0.66), `mid`, or `cheap` (bottom third, ≤ 0.34). These describe where the level sits in its own past range — **they do not predict.**

Alongside, the `rate_environment` signal is echoed through. **The engine emits no outlook and performs no synthesis** — it does not say "firmer" or "softer." The calling agent combines the band position and the rate signal into its own view and decides its own assumption. This keeps the engine purely descriptive for oscillating metrics, with all forward judgment residing in the consuming domain agent.

## SIGNALS — QUALITATIVE, NOT ARITHMETIC

After computing, the agent inspects `context_signals` per family and emits directional flags. **These flags never modify a computed number.** They are passed up so the consuming domain agent folds them into its written read — where economic judgment belongs, rather than smuggled into a number as fabricated basis points.

| Signal | Families | Emitted values |
|--------|----------|----------------|
| `supply_pressure` | `rent_or_occupancy` | `elevated` (under-construction ≥ 5% of stock), `moderate` (≥ 2.5%), `low`, `unknown` |
| `migration_signal` | `rent_or_occupancy`, `demographic` | `positive` (inbound income ≥ 10% over outbound), `neutral`, `negative` (≤ −10%), `unknown` |
| `employment_signal` | `rent_or_occupancy`, `demographic` | `positive` (≥ 2% YoY), `neutral`, `negative` (< 0%), `unknown` |
| `rate_environment` | `capital_markets` | `tightening`, `easing`, `stable`, `unknown` (echoed from the request) |
| `inflation_anchor` | `operating` | the inflation floor the trend was sanity-checked against (`0.025` default) |

The thresholds mapping raw inputs to a flag are deliberately coarse and documented as heuristics, not precision arithmetic. Their job is to set a direction, not a magnitude.

## RESPONSE SCHEMA — TREND MODE

Same notation: `<...>` is a value the sandbox produced, `a | b | c` is an enumeration. Every `methodology` field is sourced from an executed value; `computed_in_sandbox` is set only by the code path that ran the computation, never written by the model.

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
    "primary_method": "Dampened trend extrapolation with peer mean reversion",
    "history_depth_months": "<integer>",
    "trend_r2": "<float, diagnostic only — not a gate>",
    "recent_annualized_growth": "<float>",
    "long_run_mean_growth": "<float>",
    "dampening_cap_applied": "<float>",
    "mean_reversion_applied": "<bool>",
    "peer_deviation_sigma_pre": "<float, or null if no peer cohort>",
    "reversion_weight_per_year": "<float, or null>",
    "cyclical_drawdown_suspected": "<bool — true forces low confidence and a flat-hold projection>",
    "scenario_sigma_source": "residual_volatility",
    "computed_in_sandbox": true
  },
  "signals": {
    "supply_pressure": "elevated | moderate | low | unknown",
    "migration_signal": "positive | neutral | negative | unknown",
    "employment_signal": "positive | neutral | negative | unknown",
    "inflation_anchor": "<float, when family = operating>"
  },
  "confidence": "high | medium | low",
  "data_quality_flags": [],
  "narrative": "<caller writes this — foreground the band, name any reversion, state which signals were flagged without applying them>"
}
```

The `signals` block includes only keys relevant to the family.

### Example A response — Charlotte rent (trend)

```json
{
  "status": "ok",
  "mode": "trend",
  "metric": { "name": "mf_rent_ts.asking_rent_latest", "units": "$", "family": "rent_or_occupancy" },
  "subject": "msa_charlotte_nc",
  "horizon": "5_years_annual",
  "base_case": [
    { "period": "Year 1", "value": 1982.02, "pct_change": 0.0404 },
    { "period": "Year 2", "value": 2062.21, "pct_change": 0.0405 }
  ],
  "upside_case": [
    { "period": "Year 1", "value": 1996.20, "pct_change": 0.0479 },
    { "period": "Year 2", "value": 2094.07, "pct_change": 0.0490 }
  ],
  "downside_case": [
    { "period": "Year 1", "value": 1967.84, "pct_change": 0.0330 },
    { "period": "Year 2", "value": 2030.61, "pct_change": 0.0319 }
  ],
  "methodology": {
    "primary_method": "Dampened trend extrapolation with peer mean reversion",
    "history_depth_months": 60,
    "trend_r2": 0.9931,
    "recent_annualized_growth": 0.0404,
    "long_run_mean_growth": 0.0408,
    "dampening_cap_applied": 0.50,
    "mean_reversion_applied": false,
    "peer_deviation_sigma_pre": 0.7304,
    "reversion_weight_per_year": null,
    "scenario_sigma_source": "residual_volatility",
    "computed_in_sandbox": true
  },
  "signals": { "supply_pressure": "elevated", "migration_signal": "positive" },
  "confidence": "medium",
  "data_quality_flags": [],
  "narrative": "Base case carries recent ~4% growth forward, lightly dampened toward a near-identical long-run mean; the subject tracked its peer cohort closely (0.73σ, under the 1.0 trigger), so no reversion blend was applied. Elevated supply and a positive inbound-migration signal are flagged for the consuming agent to weigh — neither was applied to the computed figures. The band, not the central line, is the read for a 5-year horizon."
}
```

## RESPONSE SCHEMA — DIRECTIONAL MODE

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
  "signals": { "rate_environment": "tightening | easing | stable | unknown" },
  "methodology": {
    "primary_method": "Directional band-position read (no projection)",
    "history_depth_months": "<integer>",
    "note": "Oscillating metric: structural band from observed history; no growth applied, no future values produced. Caller synthesizes outlook from band position and rate-environment signal.",
    "computed_in_sandbox": true
  },
  "confidence": "high | medium | low",
  "data_quality_flags": [],
  "narrative": "<caller writes this — state band position and rate signal as the two facts, then the caller's own synthesized lean>"
}
```

### Example B response — Atlanta office cap rate (directional)

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
  "signals": { "rate_environment": "stable" },
  "methodology": {
    "primary_method": "Directional band-position read (no projection)",
    "history_depth_months": 60,
    "note": "Oscillating metric: structural band from observed history; no growth applied, no future values produced. Caller synthesizes outlook from band position and rate-environment signal.",
    "computed_in_sandbox": true
  },
  "confidence": "high",
  "data_quality_flags": [
    "scenarios ignored: capital_markets is directional, not projected — no scenario envelope is produced"
  ],
  "narrative": "The office cap rate sits at the very top of its observed five-year range (6.0–7.9%, current 7.9%), having expanded steadily off the 2020 low. The rate environment is flagged stable. These two facts are reported without synthesis; the consuming agent decides whether a band-top level plus a stable rate environment implies further expansion, a plateau, or compression for its own assumption set."
}
```

## CONFIDENCE CALIBRATION

### Trend mode

Keyed to data sufficiency and how much the trajectory had to be corrected — not to R² (see Trend Methodology §1).

- **High:** ≥ 24 months of clean history, horizon ≤ 5 years, the reversion blend did not materially move the trajectory (subject near its peer cohort), and any present signals are mutually consistent.
- **Medium:** history 12–24 months, OR the reversion blend materially altered the trajectory (subject far from cohort), OR emitted signals conflict (e.g. positive migration but elevated supply).
- **Low:** history < 12 months, OR horizon > 5 years, OR local history directly contradicts the peer-cohort direction.

### Directional mode

Keyed to lookback depth, since no projection is made: **High** ≥ 24 months, **Medium** 12–24 months, **Low** < 12 months.

## ERROR HANDLING

### Blocking Failures (status: "error")

- Fewer than 6 valid historical data points
- `family` omitted or invalid
- Trend mode only: horizon outside the 1-to-10-year envelope, or `horizon.years` missing/non-integer (directional mode does not require a horizon)
- Sandbox computation did not execute or returned an incomplete result. The agent must not fall back to estimating numbers in prose; it returns an error.

### Warning Triggers (status: "warning")

Output is computed but appended with alerts:

- Trend: dampening cap reached early (far-out years weakly informative); thin or absent peer cohort (reversion not applied); wide scenario divergence relative to the point estimate; emitted signals conflict with the computed direction; cyclical drawdown suspected (short history in a correction — held flat after year 1, confidence forced low, structural context required from the caller).
- Directional: scenarios were supplied (ignored — directional mode does not project); under 24 months of history (band position weakly characterized).

## WHAT THIS AGENT DOES NOT DO

### Do NOT Estimate Numbers in Prose
All projections and band reads come from `scripts/forecast.py`. If the sandbox is unavailable, return `status: "error"` — never a hand-estimated result.

### Do NOT Fetch Data Inline
The calling agent assembles all history arrays using its own tools before invoking this engine  — per "Assembling History and Peers from the Datamart" in the Request Schema.

### Do NOT Execute Multi-Metric Requests
Strict one-metric-per-call. Parallel forecasts are split into distinct invocations by the router.

### Do NOT Apply Signals as Arithmetic
`context_signals` are reported as directional flags only. They never multiply, discount, or modify a computed value.

### Do NOT Project Oscillating Metrics
`capital_markets` metrics receive a band-position read only. The engine never assigns them a growth rate or a future value.

### Do NOT Formulate Investment Opinions
Objective numerical and methodological output only. Never recommends buying, selling, financing, or rejecting an asset.
