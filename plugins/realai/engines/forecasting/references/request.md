# Request Assembly

## Contents

- Metric Specification
- Family Parameter Options
- Common Use Cases
- Request Schema
- Assembling History and Peers from the Datamart
- Assembling Context Signals (sourced or omitted, never estimated)
- Example A: market rent (trend mode)
- Example B: office cap rate (directional mode)

## Metric Specification

The caller specifies the metric and which behavior family it belongs to, rather than choosing from a fixed list, so the engine stays extensible as datamart topics and asset classes broaden. **The family field is supplied by the caller; there is no internal lookup mapping a metric name to a family.** The caller is responsible for tagging correctly; the engine guarantees only that each mode emits its own shape (see Two Modes in SKILL.md).

### Required Metric Fields

| Field | Description |
|-------|-------------|
| `name` | What is being forecast in plain language (e.g., "asking rent for 2BR units in Charlotte MSA," "office cap rate for Atlanta," "population for Mecklenburg County") |
| `units` | Denomination ($, $/SF, %, bps, count, index) |
| `family` | Selects the mode and the overlays/signals; see below |

## Family Parameter Options

| Value | Mode | Definition |
|-------|------|------------|
| `rent_or_occupancy` | Trend | compounding; supply and demand signals evaluated and emitted |
| `demographic` | Trend | compounding; migration and employment signals emitted |
| `operating` | Trend | compounding; anchored to inflation floor; no supply/demand signal |
| `generic` | Trend | compounding; no signals, pure dampened trend with reversion |
| `capital_markets` | **Directional** | **oscillating; NO projection.** Reports band position + rate signal |

## Common Use Cases

**Trend:** asking and in-place rent (any asset class, any segment), occupancy, home value, expense growth, NOI growth, population, job growth by sector, median household income, household formation, building permit pace.

**Directional:** cap rate by asset class (multifamily, office, industrial, retail), and any other metric that oscillates around a structural level rather than compounding.

## Request Schema

**Illustrative payload, not a template of defaults.** The structure below is the universal envelope for every metric and family. Read the notation literally:

- `<...>` marks a value supplied per call. Nothing inside angle brackets is a default.
- `a | b | c` marks an enumeration: choose exactly one.
- The two examples at the end fill the identical structure with different metrics and different modes, to make clear the envelope is metric-agnostic.

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
    "years": "<integer, 1-10; used by trend mode, ignored by directional mode>",
    "intervals": "annual | quarterly | 12_24_36_months"
  },
  "as_of": "<YYYY-MM-DD, optional - the analysis date; enables the last-observation recency check>",
  "requested_lookback_years": "<float, optional - the lookback the user asked for; a shortfall vs. available history becomes a structured flag>",
  "caller_disclosures": {
    "peer_selection_basis": "<why this peer: parent-geography default or custom basket, plus a one-line comparability claim>",
    "peer_omitted_reason": "<when a family that supports a peer has none: no comparable peer at grain | not gathered>",
    "excluded_periods": [ { "period": "<YYYY-MM-DD>", "reason": "<e.g. source break>" } ],
    "signals_omitted": [ { "signal": "<name>", "reason": "<no source exists | not gathered>" } ],
    "sibling_series_note": "<sibling checked and result, or why not applicable>",
    "sibling_divergence_pct": "<float - the computed trailing-12-month growth gap between siblings, a number not prose>",
    "lookback_note": "<e.g. full available history, or the regime-break justification for truncating>",
    "rate_instrument": "<the instrument both rate figures come from, e.g. fed_funds>"
  },
  "history": [
    { "period": "<YYYY-MM-DD>", "value": "<number>", "source": "datamart | user_roll | zillow | peer_proxy" }
  ],
  "history_check": { "count": "<int>", "sum": "<number>", "first_value": "<number>", "last_value": "<number>" },
  "peer_history": [
    { "period": "<YYYY-MM-DD>", "value": "<number>", "source": "datamart | user_roll | zillow" }
  ],
  "peer_history_check": { "count": "<int>", "last_value": "<number>" },
  "context_signals": {
    "supply_pipeline": {
      "existing_stock": "<integer>",
      "under_construction_t12": "<integer>",
      "permitted_units_t13_t24": "<integer>"
    },
    "migration": {
      "inbound_income": "<number - raw inbound cohort income; the engine computes the ratio>",
      "outbound_income": "<number - raw outbound cohort income, SAME basis (both medians or both averages)>",
      "inbound_income_vs_outbound_pct": "<float - precomputed ratio, accepted only when the raw figures are unavailable>"
    },
    "employment": {
      "job_growth_1_year_pct": "<float, e.g. 0.032 = 3.2% YoY job growth>"
    },
    "rate_environment": {
      "current_rate": "<float, percent, e.g. 3.8 - preferred numeric form>",
      "projected_rate": "<float, percent - with current_rate, the engine classifies the direction itself>",
      "projected_as_of": "<YYYY (or a date) - the year the projected_rate refers to; with as_of, the engine flags a projection that falls short of the analysis horizon>",
      "direction": "tightening | easing | stable - free-text fallback when no rate figures exist",
      "note": "<free text, optional>"
    },
    "structural_ceiling": {
      "ratio_current": "<float - the family-relevant ceiling ratio today, e.g. rent-to-income 0.31>",
      "ratio_ceiling": "<float - the defended ceiling for that ratio, e.g. 0.33>"
    }
  },
  "scenarios": ["base"]
}
```

`context_signals` is informational and may be partially populated or omitted. Include only the sub-blocks relevant to the family. **No value inside `context_signals` is ever multiplied into a number; these drive directional flags only.** `horizon` and `scenarios` are used by trend mode; directional mode ignores both (it does not project). Sourcing rules for every signal live in **Assembling Context Signals** below - the short version is: sourced or omitted, never estimated.

`history_check` / `peer_history_check` are the mechanical backstop for the assemble-programmatically rule (see SKILL.md): declare the count plus any of sum / first_value / last_value from the source data, and the script validates the array it actually received against them, erroring loudly on a mismatch. Values are compared after date-sorting. Include a check on every payload; an array assembled in code produces a matching check for free, so only a transcription slip ever trips it.

**The check must be independent of the array.** Compute the check with code operating directly on the retained raw tool result - never derive it from a hand-assembled array, which makes the check decorative (it validates the transcription against itself and passes regardless). Persist the raw tool result first (to a file or held object), then parse both the array and the check from that artifact. If the array and the check share a single manual-transcription step, treat the payload as defective and re-derive from source.

`caller_disclosures` is the free-form block where every assembly decision gets written down: the engine echoes it verbatim into the response, so a disclosure lands in the logged tool result whether or not the narrative remembers to mention it. All keys are optional and the block itself is optional, with one nudge: supplying `peer_history` without a `peer_selection_basis` draws an advisory flag. "Disclose it in the narrative" throughout these docs means: write it here first, then the narrative repeats it.

`requested_lookback_years` disambiguates the user's "last N years": declare the lookback they asked for, and the engine compares it against the available span - a shortfall becomes a structured flag and two methodology fields (`lookback_requested_years` / `lookback_available_years`) instead of a courtesy sentence the caller may skip. The projection horizon stays in `horizon.years`; the two are different questions and a user's phrase can mean either - confirm which before defaulting.

## Assembling History and Peers from the Datamart

The engine does not fetch. These rules govern what the caller hands it, so a trend is not poisoned before the script ever runs:

- **Rent and occupancy** (`rent_or_occupancy`): histories come from the time-series topics: `mf_rent_ts` (aggregate), `mf_rent_ts_by_beds` / `mf_rent_ts_by_beds_baths` (segment-level), `sfr_rent_ts`, `sfr_rent_ts_by_unit_category`. Never use the snapshot or detail siblings, which carry only the current state. Every rent time-series topic requires a `period_type` filter and the accepted values differ by topic: `mf_rent_ts` and its `_by_beds*` variants take `Month` or `Week`; `sfr_rent_ts` takes `Quarter`; `sfr_rent_ts_by_unit_category` takes `Month` or `Week`. Use `Month` where available for forecast histories (weekly cadence adds noise, not signal, at a 1-10 year horizon) and hold one `period_type` constant across a history array; never mix cadences in a single series.
- **Home values**: `home_sales_and_values_ts` (monthly; `period_type` is `MONTH`).
- **Cap rates** (`capital_markets`): `caprate_ts`, a quarterly series (`period_type` is `QUARTERLY`), market grain only, one field per property type (`multifamily`, `office`, `industrial`, `single_family_rental`, `self_storage`, `senior_housing`, `retail_strip_center`, `retail_neighborhood_center`, `retail_power_center`). For a finer-grain subject the caller passes the parent market's series and labels the subject accordingly.
- **Permit pace**: `permit_ts` (monthly; census place, county, market, and state grains). Single-family, multifamily, and total units are separate fields (`sfr_units_permitted`, `mf_units_permitted`, `total_units_permitted`); pick the segment that matches the metric, never blend them.
- **Demographic, income, and operating series**: the datamart carries no geographic time series for population, income, or household formation (those topics are snapshots with trailing-change fields) and no NOI or expense time series. Histories for the `demographic` and `operating` families come from the caller's own sources (e.g., owner operating statements as `user_roll`); tag `source` honestly.
- **Peer history**: the same field at the same `period_type` from the parent or benchmark geography (submarket or zipcode to parent market, market or state to nation, property to its surrounding market), aligned period-for-period with the subject series. **The parent-geography default is a floor, not a ceiling**: where the natural parent is a poor comparison (a fast-growing metro benchmarked against a much larger, heterogeneous state), substitute a custom peer basket built from a small set of comparable geographies, provided the same field and `period_type` are used and the substitution is disclosed in the narrative.
- **Peer comparability is a separate judgment from the anomaly scan**: a peer series can be perfectly clean data and still be the wrong peer. Before defaulting to the parent, confirm it sits in a broadly similar price band and cycle position as the subject (a national aggregate dominated by a different price tier is a poor reversion target for a fast-moving secondary metro). The engine flags a growth deviation beyond 3 sigma ("peer mismatch suspected"), but that is a backstop - the comparability call is the caller's, made before submission. **The stated basis must contain numbers, not adjectives**: `caller_disclosures.peer_selection_basis` states the level comparison (e.g., "level ratio 0.89") and the trailing trend direction of both series - "parent-geography default" alone is boilerplate, and if you cannot state the comparison because you did not check, that is itself the signal to build a custom basket.
- **Grain-locked topics still get the basket test**: when a topic has no natural parent grain (e.g., `caprate_ts` is market grain only), "no comparable peer at grain" is not automatically true. Before writing that as `peer_omitted_reason`, check whether a custom basket of 2-4 comparably positioned peer entities (same field, same `period_type`, averaged) is constructable. Feasible-but-not-built is `not gathered`, not `no source exists` - the same triage that governs signals governs peer selection.
- **Sibling series that can diverge**: many metrics have a close sibling in the same dataset (asking vs. in-place rent, list vs. sale price, gross vs. net absorption). **When the sibling field sits in the same already-fetched result, checking it is mandatory** - "did not check" is a defect when the check was free, versus a legitimate disclosure when it genuinely required a separate fetch. Compute the trailing-12-month growth gap and record it as a number in `caller_disclosures.sibling_divergence_pct` alongside the `sibling_series_note`. **Materiality threshold: a gap over 100 bps of trailing-12-month growth makes running both series through the engine mandatory**, not disclose-or-run; below it, the note plus the computed number suffice. Never present the more flattering (or first-fetched) series as representative of the broader concept.
- **Parallel calls stay consistent**: when one session runs several related calls (a sibling pair, multiple bedroom cuts, several submarkets of one metro), hold peer sourcing, `context_signals`, `as_of`, and horizon constant across them unless a divergence is deliberate - and if deliberate, disclose it. The documented failure mode is building a peer array for one call and forgetting it on the near-identical second; the engine's thin-peer flag catches the omission, but parity is the caller's job.
- **Depth**: target 24+ months (the high-confidence bar) and ideally more than 30 (past the cyclical-drawdown guard's short-window trigger); below 6 valid points the engine errors, with one exception - the `operating` family degrades to a structural-terminal-rate fallback at 1-5 points (a single T12 is the normal case for expense series; see the methodology reference). Before accepting that fallback, check for cheap additional points (prior-year T12s, prior tax bills, trailing-quarter run rates) that could reach the 6-point minimum and unlock a real trend fit; below 6 the fallback applies regardless of whether you have 1 point or 5. When the user's requested lookback exceeds the available history, state the shortfall before presenting results, not as a footnote after.
- **Nulls and gaps**: drop null or missing periods; never zero-fill or interpolate. If gaps are material, treat the series as shorter than its calendar span and report the effective depth used, not the calendar span.
- **Integrity scan before submission**: scan every `history` and `peer_history` array for period-over-period jumps too large to be market movement (a source break or methodology change) and for a peer whose level sits several multiples off the subject's current level. Truncate to the clean window and disclose the exclusion, or do not submit the array; never let an unexplained discontinuity flow into the trend or reversion math unflagged.
- **Thin subject, thick parent (`peer_proxy`)**: when the subject has fewer than 6 valid points but the parent geography has a full series, rescale the parent series multiplicatively so its final value equals the subject's current level and submit that as `history` with `source: "peer_proxy"` on every row. The engine detects the tag, caps confidence at medium, and flags the substitution; disclose it in the narrative. This keeps the math in the script (the projection carries the parent's trajectory applied at the subject's level) instead of forcing an off-engine workaround.
- **Directional lookback**: pass the FULL available history. Band position is only meaningful relative to the deepest available window - a caller-selected recent window silently defines the band and produces a self-fulfilling "at the top of my chosen range" read (a post-2020 window can miss that the current level is a 20-year high, not a cycle high). The multi-regime concern is already handled mechanically: past 10 years the engine reports a trailing-10-year band alongside the full-history band, and flags when the two disagree - surface both reads. Truncating the input window requires a specific regime-break justification recorded in `caller_disclosures.lookback_note`.

## Assembling Context Signals (sourced or omitted, never estimated)

The sourcing discipline that governs history arrays applies to every leaf of `context_signals`. **Sourced-and-cited, or omitted - never estimated.** A plausible placeholder is a fabrication regardless of how directionally reasonable it looks, and it is worse than an honest `unknown`: it produces a confident-looking signal instead of a visible gap. The zero-fill prohibition applies here exactly as it does to history arrays - never populate a sub-block with 0, null-as-zero, or a guessed value to satisfy the schema shape. Omit it; every signal degrades to `unknown` (or is simply absent) by design, and that degradation is the intended safe behavior, not a failure to route around by guessing.

**Provenance triage before running the script - now engine-enforced.** For every sub-block relevant to the metric's family, account for it as exactly one of: **sourced** (the value traces to a specific tool result), **no source exists** (log it in `caller_disclosures.signals_omitted` - the gap is the data's), or **not gathered** (the gap is yours: go gather it, or log the omission with that reason). The engine knows each family's relevant blocks and flags any that are neither populated nor logged ("signals not triaged") - a silently absent block and a considered-and-omitted block must not look identical in the payload.

| Family | Triage-enforced blocks |
|--------|------------------------|
| `rent_or_occupancy` | `supply_pipeline`, `migration`, `employment` |
| `demographic` | `migration`, `employment` |
| `capital_markets` | `rate_environment` |
| `operating`, `generic` | none (inflation anchor is automatic; `structural_ceiling` is optional everywhere) |

**Signal sourcing map.** Where each leaf typically already lives - scan tool results already gathered this session for these fields BEFORE declaring a signal `not gathered`:

| Signal leaf | Typical source |
|-------------|----------------|
| `supply_pipeline.existing_stock` / `under_construction_t12` | the market rent topic's unit count; the supply snapshot's under-construction field |
| `supply_pipeline.permitted_units_t13_t24` | `permit_ts` at the market or county grain |
| `migration.inbound_income` / `outbound_income` | the migration snapshot's cohort income fields (one consistent basis) |
| `employment.job_growth_1_year_pct` | the demographic/employment snapshot's one-year job-growth field |
| `rate_environment.current_rate` / `projected_rate` / `projected_as_of` | national metrics actuals (fed funds, SOFR) + the FOMC projection or forward curve, with the projection's reference year |
| `structural_ceiling.ratio_current` | rent-to-income or value-to-income on the rent-and-occupancy or home-values snapshot |

Per-field sourcing:

- **`supply_pipeline.existing_stock`**: only from a real total-inventory field at the required grain (e.g., the unit count carried on the market's rent topic). If no inventory field exists at that grain, omit it and let `supply_pressure` read `unknown` - never estimate a market's total stock from general knowledge.
- **`migration.inbound_income` / `outbound_income`**: raw cohort incomes from the migration snapshot, on ONE consistent basis (both medians or both averages - never mixed). The engine computes the ratio; do not do the algebra by hand. The precomputed ratio field is accepted only when the raw figures are unavailable.
- **`employment.job_growth_1_year_pct`**: the snapshot job-growth field at the subject or parent grain.
- **`rate_environment.current_rate` / `projected_rate`**: real benchmark-rate figures from the national metrics topics - an actual (fed funds or SOFR) for current; an FOMC projection or market-implied forward curve for projected - never approximated from general knowledge. Pull the ACTUAL current reading first, then the projection: a projection cited without its current anchor can get the direction right and the magnitude unchecked. Both figures must come from the same instrument (fed funds vs. fed funds dot-plot, SOFR vs. SOFR forward - name it in `caller_disclosures.rate_instrument`); if only mixed-instrument sources exist, use the free-text `direction` fallback instead of a numeric pair the engine will treat as comparable. Horizon-match rule: compute the target year (`as_of` year + `horizon.years`; capital_markets calls read against a 3-year window) and select the forward data point covering it - if the projection series stops short, use the furthest available point and declare its year in `projected_as_of`, which lets the engine flag the gap ("rate projection horizon shortfall") instead of a nearer year getting silently substituted. When two credible sources (a dot-plot median, a forward curve) diverge, surface both in the narrative rather than quietly picking one.
- **`structural_ceiling`**: a real ratio field (rent-to-income, value-to-income) for `ratio_current`, and a defended ceiling for `ratio_ceiling` - benchmark the ceiling against the percentile fields, and state the basis. An invented pair is worse than no block.

## Example A: market rent (`rent_or_occupancy`, trend mode)

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
  "history_check": { "count": 6, "sum": 10442.00, "last_value": 1905.00 },
  "peer_history_check": { "count": 6, "last_value": 1898.00 },
  "caller_disclosures": {
    "peer_selection_basis": "parent market default; level ratio 1.00, both series trending up at a similar pace",
    "sibling_series_note": "in-place rent checked in the same fetch; tracks asking",
    "sibling_divergence_pct": 0.004
  },
  "context_signals": {
    "supply_pipeline": { "existing_stock": 142000, "under_construction_t12": 9800, "permitted_units_t13_t24": 5400 },
    "migration": { "inbound_income": 168000, "outbound_income": 150000 },
    "employment": { "job_growth_1_year_pct": 0.032 }
  },
  "scenarios": ["base", "upside", "downside"]
}
```

## Example B: office cap rate (`capital_markets`, directional mode)

Same envelope, different metric and mode. `units` in `%`, only the `rate_environment` signal is relevant, and `horizon` / `scenarios` will be ignored; directional mode does not project (supplying scenarios here produces the "scenarios ignored" warning in the example response).

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
  },
  "scenarios": ["base", "upside", "downside"]
}
```
