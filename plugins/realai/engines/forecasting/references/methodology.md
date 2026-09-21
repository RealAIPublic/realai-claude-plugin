# Methodology

## Contents

- Trend Methodology: three computed operations
  - 1. Dampened Trend Extrapolation with Structural Terminal Anchor
  - 2. Mean Reversion Toward Peer Median (spatial)
  - 3. Scenario Envelope
- Cyclical-Drawdown Guard
- Boom-Extrapolation Guard
- Stale-Series and Recency Guards (both modes)
- Where the Override Lives When a Guard Fires
- Operating Short-History Fallback
- Parameters and Terminal Rates
- Directional Methodology: band position, no projection
- Signals: qualitative, not arithmetic

## Trend Methodology: three computed operations

For trend families, the script executes these three steps in order on the `history` (and `peer_history`) arrays. This is the complete arithmetic: the only anchors are the series long-run mean and the documented structural terminal rate, and there are no signal-derived basis-point overlays.

### 1. Dampened Trend Extrapolation with Structural Terminal Anchor

Compute the annualized growth rate from a log-linear regression on the historical series. Project it forward, but pull the projected growth rate toward two anchors as the horizon extends: the series' own long-run mean growth, and a **family-level structural terminal rate**. Near-term years stay close to recent momentum; later years decay toward a defensible structural rate.

The blend has three terms:

`projected_growth_t = recent_growth * (1 - d_t) * (1 - w_t) + long_run_mean_growth * d_t * (1 - w_t) + terminal_rate * w_t`

- `d_t` is the recent-to-mean dampening weight, ramping linearly from a year-1 weight (`0.20`) to a cap (`0.50`).
- `w_t` is the recent/mean-to-terminal weight, ramping from 0 at year 1 to a cap (`0.60`, or `0.85` when the boom guard fires) at the final year.

**Why the terminal term exists.** The original two-term blend dampened recent momentum toward the series' own long-run mean. When the entire history window sits inside a single regime (e.g. a history that is entirely post-2020), that mean IS the regime, so dampening toward it is a no-op and the forecast never levels off. Example A demonstrated exactly this: recent growth 4.04%, long-run mean 4.08%, dampening moved a 4.04% projection toward 4.08% and accomplished nothing. The structural terminal rate is a documented, window-independent house-view anchor (the DCF terminal-growth convention institutional readers already trust), so late years converge toward a defensible structural rate regardless of what regime the input window captured. The terminal rate for each family lives in the script's `PARAMS` block (see Parameters and Terminal Rates below); it is reported in the response as `terminal_rate_applied`. **It is an anchor, not a signal: a fixed methodology parameter, never multiplied by anything in `context_signals`, so it does not violate the "no smuggled basis points" principle.**

R-squared is computed and reported as a diagnostic. **It does not gate execution and is not a quality threshold.** Rent and price series are autocorrelated and clear high R-squared even when a trend is about to break.

### 2. Mean Reversion Toward Peer Median (spatial)

**Trigger:** applied when `peer_history` is supplied and the subject's historical growth deviates from the peer cohort by more than one standard deviation (the sigma > 1.0 trigger).

**Compute:** blend the subject trajectory toward the peer-cohort growth rate, at a cumulative `0.30`/year rate over the horizon, capped at full reversion. This is the single most load-bearing adjustment for the domain: it prevents a hot submarket from extrapolating to the moon. The realized weight and pre-adjustment deviation are recorded in the methodology block.

**Peer-mismatch flag:** a deviation beyond `3.0` sigma gets a loud `data_quality_flags` entry ("peer mismatch suspected") in addition to the silent methodology field. A gap that large usually means the peer itself is a poor reversion target (different price tier, different cycle position), not that the subject is an outlier - the flag tells the caller to consider a custom peer basket rather than letting the blend quietly pull toward a structurally different geography. The math is unchanged; the disclosure is mandatory.

**Peer level ratio (ex-ante):** the sigma check is ex-post - it fires only after the trend fit. The engine also reports `peer_level_ratio` (peer's latest level over the subject's) and flags beyond `1.5x` either way ("peer level mismatch"). Reversion blends growth, not level, so a level gap does not poison the math directly - but a peer trading at a multiple of the subject is usually a different price tier whose cycle the subject does not share, and this catches it legibly before the sigma number has to. A normal parent premium sits well inside the bound. Neither flag replaces the caller's comparability judgment (see the request reference); they are backstops.

### 3. Scenario Envelope

**Trigger:** generated when `scenarios` includes `upside` and/or `downside`.

**Compute:** plot +/- sigma bands around the base case, where the band half-width is the **larger of** (a) the historical residual volatility of period-over-period growth and (b) a per-family structural floor, widening at each interval (x`1.15`/year on the half-width) to reflect compounding uncertainty.

**Why the floor.** Residual volatility of a smooth, autocorrelated series measures noise around the trend, not regime-change risk. Without a floor the band can be cosmetically narrow: Example A's original downside case was +3.3% in year 1 and never left positive territory, while the actual outcome was roughly flat-to-negative. A band that cannot contain a regime shift is not an honest deliverable. The per-family floors (rent +/-200bps year 1, operating +/-150bps, demographic +/-100bps, generic +/-150bps) ensure the band is wide enough to span a boom-to-flat transition. The floor is reported as `scenario_halfwidth_floor_applied`.

**For 5-year real estate forecasts, the band is the deliverable; the point estimate is decoration.** Narrative should foreground the range.

## Cyclical-Drawdown Guard

A short history sitting inside a correction is the engine's hardest case, and the one most likely to mislead. When the window is short (30 months or less) the recent growth AND the long-run mean computed off it can both be negative, so dampening pulls toward a negative anchor and the engine extrapolates the correction forward. That is the wrong frame for a multi-year hold: the window is too short to contain a full cycle, so the engine cannot distinguish a cyclical trough from a structural decline.

**Trigger:** history depth 30 months or less AND trailing annualized growth below -0.5%.

**Behavior when triggered:** the engine does NOT project the decline forward. It holds the honest trailing rate for year 1 (the correction has not cleared) and goes flat (0%) thereafter. It explicitly does NOT invent a recovery curve, because that is a judgment the engine cannot make from a short window. It forces confidence to `low`, sets `cyclical_drawdown_suspected: true` in the methodology block, and leads the warnings with an instruction to the caller: supply a longer history that spans a full cycle, or apply structural context and a defended recovery path before using the output as a multi-year assumption.

This is deliberate division of labor. The engine's job is to stop confidently extrapolating a correction and to flag that judgment is required, not to replicate the analyst's cycle-bridge reasoning. That reasoning (e.g., "the pipeline is decelerating, employment base is intact, recovery by year 3") belongs in the consuming analysis, which sees the low-confidence flag and the warning and supplies the structural view. A confident wrong number is worse than a flagged hold.

## Boom-Extrapolation Guard

The **symmetric mirror** of the cyclical-drawdown guard. The drawdown guard stops the engine extrapolating a correction off a short window; this guard stops it extrapolating a boom. Without it, the engine carries a regime-high growth rate forward at high confidence: the exact Sun Belt failure of 2023-2025, where 4%-flat rent trajectories shipped while the forward market delivered 0.5-1%. The original engine protected against extrapolating a correction but not against extrapolating a bubble.

**Trigger:** trailing annualized growth is positive AND either (a) it exceeds the family terminal rate by more than a multiple (`1.75x`), or (b) the entire history window sits inside a single known-hot regime (starting on or after 2020-01-01), where the series' own long-run mean is itself inflated and cannot serve as a leveling anchor.

**Behavior when triggered:** unlike a drawdown, a boom does NOT hold flat; booms decay, they don't stop. The engine accelerates convergence toward the structural terminal rate (a higher terminal-weight cap, `0.85` vs `0.60`), caps confidence at `medium`, sets `boom_extrapolation_suspected: true`, and leads the warnings with an instruction to the caller to supply a longer history spanning a full cycle, or apply structural context (supply pipeline, rent-to-income ceiling) before using the near-term years as a multi-year assumption.

Boom and drawdown are mutually exclusive (a window is either running hot or correcting, never both), and the drawdown check takes precedence if somehow both matched.

**The flag names its trigger.** The warning text is composed from whichever condition(s) actually fired, and the methodology block carries `boom_trigger` (`above_terminal` and/or `single_regime`). A post-2020 window with modest growth is told about the regime problem, not handed a claim that its growth "exceeds the terminal rate" when the numbers show otherwise - the flag never asserts a comparison its own cited figures contradict.

## Stale-Series and Recency Guards (both modes)

A metric that has not moved in several consecutive periods is a data-quality question independent of what the metric is: appraisal-based series are known to lag and carry the last print forward when transaction volume dries up, so a genuinely stale series and a genuinely stable market would otherwise look identical in the output.

**Trigger:** the trailing 4 periods are identical (within a de minimis tolerance). Applies to trend and directional histories alike.

**Behavior when triggered:** the computation runs normally, but the engine appends a data-quality flag naming the possible reporting lag and caps confidence at medium regardless of lookback depth. A flatlined series never silently reads as "stable" or earns high confidence without disclosure.

**Recency check (opt-in via `as_of`).** The identical-values pattern cannot see a series whose last print is simply old. When the caller declares the analysis date in the request's `as_of` field, the engine compares the most recent observation against it: a gap exceeding `2x` the series' native cadence (median period spacing) draws a flag and caps confidence at medium. The check keys off the declared `as_of`, never the wall clock, so the same payload always produces the same output. Omit `as_of` and no recency check runs.

## Where the Override Lives When a Guard Fires

Both trend guards instruct the caller to apply structural judgment (a defended recovery path, a ceiling argument) before using the output as a multi-year assumption. That judgment belongs in the consuming analysis's narrative, explicitly labeled as judgment, sitting alongside the engine's numbers. It must never take the form of a resubmitted or synthetic history array designed to move the engine's output: the engine's numbers stand, and the analyst's view is layered on top where the reader can see the seam. The `structural_ceiling` signal block (see the request reference) is the structured input for ceiling arguments; everything else is prose.

## Operating Short-History Fallback

Nearly every acquisition carries a single T12, not a 6+ point expense series, so for the `operating` family the sub-minimum case is the norm, not an edge case. Erroring would push callers to exactly the off-engine hand-picked default this engine exists to prevent.

**Trigger:** family `operating` with 1-5 history points (0 points still errors; all other families error below 6 points).

**Behavior:** the engine returns the family's structural terminal rate as a flat growth path with no trend fit, `confidence: low`, `primary_method: "Structural terminal rate fallback (insufficient history; no trend fit)"`, and a flag explaining the substitution. Scenario bands, if requested, use the family floor alone (`scenario_sigma_source: "structural_floor_only"`). The terminal rate, not the lower inflation anchor, is the fallback because the family's documented basis is that expense risk is UNDER-forecasting; falling back to the lower number would contradict that rationale.

## Parameters and Terminal Rates

The structural terminal rates are house-view parameters in the script's `PARAMS` block, keyed by family:

| Family | Terminal rate | Basis (sourced 2026-07) |
|--------|--------------|-------------------------|
| `rent_or_occupancy` | 2.8% | 21st-century CPI rent-of-primary-residence CAGR ~3.5%, trimmed for the rent-to-income ceiling and near-term supply overhang; near the Yardi Matrix forward curve (0.5%/1%/2.3% for 2026-28) blended toward the long-run rate |
| `operating` | 3.5% | ~CPI + 100bps; Trepp 2015-2024 multifamily OpEx CAGR 4.15% (insurance ~11.8%, taxes ~5.4%), floored because expense risk is UNDER-forecasting |
| `demographic` | 0.4% national + bounded market spread (cap +60bps) | CBO Sept-2025 Demographic Outlook: 0.4%/yr national 2025-2035, slowing to 0.1%/yr thereafter, vs the 0.9% 1984-2024 historical average; net immigration now carries essentially all growth |
| `generic` | 2.5% | CPI |

**These rates are versioned, not live-sourced per call.** Determinism across the agent suite (the guarantee that two analyses draw identical baselines for the same metric) requires that the same payload produce the same numbers. A terminal rate fetched live on each call would break that silently. Instead the `PARAMS` block carries a `PARAMS_VERSION` and `PARAMS_VERSION_DATE`, both stamped into every trend response's methodology block, and the rates are refreshed on a deliberate cadence (target: quarterly). The refresh is a sourcing task (pull current Yardi/CBO/Trepp figures, propose updated rates, bump the version, stamp the date and sources), but the engine never sources inline. This gives bounded-staleness freshness WITH determinism WITH auditability.

**Staleness is the caller's check:** if `params_version_date` is more than one quarter old at call time, note that in the narrative as a staleness caveat rather than treating the terminal rate as current.

**Docs move in lockstep with the code:** every `PARAMS_VERSION` bump gets a corresponding diff pass over the request and response schema blocks in these references, not just the tunables table - a caller reading only the prose spec must not build an incomplete model of what the engine checks. Verify the running file with `--version` (see SKILL.md).

## Directional Methodology: band position, no projection

For `capital_markets`, the script computes **no trend, no growth, and no future values.** It reports two observed facts:

1. **The historical band**: min, structural mean, and max of the observed series. A factual description of the past.
2. **Current position in that band**: `position_in_band` is `(current - min) / (max - min)`, from `0` (at the historical low) to `1` (at the historical high), plus a coarse `position_label`: `rich` (top third, >= 0.66), `mid`, or `cheap` (bottom third, <= 0.34). These describe where the level sits in its own past range. **They do not predict.**

Alongside, the `rate_environment` signal is reported. **The engine emits no outlook and performs no synthesis**: it does not say "firmer" or "softer." The caller combines the band position and the rate signal into its own view and decides its own assumption. This keeps the engine purely descriptive for oscillating metrics, with all forward judgment residing in the consuming analysis.

**Multi-regime windows get a second band.** When the observed history exceeds 10 years, the engine also computes the band over the trailing 10 years and returns it as `band_position_trailing_10y`. A two-decade window mixes distinct rate regimes (GFC spike, ZIRP lows, hiking cycle) into one min/mean/max, and the full-history band alone can misstate where the level sits relative to the regime that matters for the hold. When the two labels disagree the engine flags it; the caller reports both reads rather than silently picking one - the discrepancy is itself informative.

`peer_history` is accepted by the schema but currently unused in directional mode; it is reserved for a future peer-spread read.

## Signals: qualitative, not arithmetic

After computing, the engine inspects `context_signals` per family and emits directional flags. **These flags never modify a computed number.** They are passed up so the consuming analysis folds them into its written read, where economic judgment belongs, rather than smuggled into a number as fabricated basis points.

| Signal | Families | Emitted values |
|--------|----------|----------------|
| `supply_pressure` | `rent_or_occupancy` | `elevated` (under-construction >= 5% of stock), `moderate` (>= 2.5%), `low`, `unknown` |
| `migration_signal` | `rent_or_occupancy`, `demographic` | `positive` (inbound income >= 10% over outbound), `neutral`, `negative` (<= -10%), `unknown` - the engine computes the ratio from raw `inbound_income` / `outbound_income` when supplied (one consistent basis); the precomputed ratio is a fallback |
| `employment_signal` | `rent_or_occupancy`, `demographic` | `positive` (>= 2% YoY), `neutral`, `negative` (< 0%), `unknown` |
| `rate_environment` | `capital_markets` | `tightening`, `easing`, `stable`, `unknown` - classified by the engine from `current_rate` / `projected_rate` when supplied (threshold 25 bps of projected minus current); the free-text `direction` is a fallback |
| `inflation_anchor` | `operating` | the inflation floor the trend was sanity-checked against (`0.025` default) |
| `ceiling_proximity` | any trend family, when `structural_ceiling` is supplied | `at_ceiling` (ratio at or above ceiling), `approaching` (>= 90% of ceiling), `room`; omitted when the block is absent |

The thresholds mapping raw inputs to a flag are deliberately coarse and documented as heuristics, not precision arithmetic. Their job is to set a direction, not a magnitude.

**Triage is enforced.** Each family's relevant blocks (see the table in the request reference) must be populated or logged in `caller_disclosures.signals_omitted`; the engine flags any block that is neither ("signals not triaged"). An `unknown` that means "no source exists" and an `unknown` that means "nobody looked" are different findings, and the payload must distinguish them.
