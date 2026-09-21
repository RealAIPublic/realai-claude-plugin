---
name: forecasting
description: "Centralized forecasting engine for every forward-looking read in a RealAI analysis. Use whenever an analysis needs a projection of a compounding series (asking or in-place rent growth, occupancy, home value appreciation, expense growth, NOI growth, population, job growth, median income, household formation, permit pace) or a directional band-position read on an oscillating capital-markets metric (cap rates by asset class). Runs scripts/forecast.py, the sole math authority; never compute a forecast inline, estimate a projection in prose, or fit a trend by hand. Do NOT use for pro formas, cash flow waterfalls, returns, or investment recommendations; those belong to the domain analysis that consumes this engine's output."
---

# Contents

- Purpose
- Execution Mandate: read this first
- Two Modes, Set by Family
- Boundary and Invocation
- Pre-Flight Checklist
- Running the Script
- Reference files

# Purpose

Centralize forecasting methodology across the entire RealAI agent suite. Any analysis that requires a forward-looking read (rent growth, occupancy, cap rate direction, expense growth, home value appreciation, demographic growth) must run through this engine rather than computing it inline.

Centralizing this logic ensures numerical consistency across domain viewpoints (a valuation analysis and a rental market analysis draw an identical baseline for the same metric and market) and produces a documented, defensible methodology for institutional investors.

# Execution Mandate: read this first

**This skill does not compute forecasts in prose. It calls a bundled script.**

The reference engine is `scripts/forecast.py`. It is the SOLE math authority for every projection and directional read this skill returns. The job is:

1. Assemble the request payload (history, peer_history, context_signals) from values already gathered by the calling analysis. See [references/request.md](references/request.md).
2. Run the script, passing the payload:
   `python skills/forecasting/scripts/forecast.py --file payload.json`
   or pipe it: `echo '<json>' | python skills/forecasting/scripts/forecast.py -`
3. Read back the JSON the script prints to stdout. That IS the response, minus the narrative.
4. Write the `narrative` field in prose, from the values the script returned.
5. Return the completed response object.

**Never estimate, recompute, adjust, or "sanity-check by recalculating" any forecast value, growth rate, band, or band position in prose.** The script's numbers are final. Doing arithmetic on any output is a defect; that work belongs to the script.

**Do not write new forecasting code.** The bundled script is the pinned implementation precisely so that two analyses draw identical baselines for the same metric. Re-implementing the math inline breaks that guarantee even if the code looks equivalent.

**Delivering a forecast: the returned series is an input, never a formula to rebuild.** A bare forecast request - what rents will do, where a metric is headed, with no valuation or returns question attached - is answered in the response itself: the scenarios as a chart or table, the confidence tier and every fired flag, and a one-line offer of the workbook. Do not build one unasked, and do not let three scenario columns bootstrap it into workbook territory. The reason is this engine's own rule below: it owns every driver, and a growth rate typed into a cell cannot re-run it, so a workbook holding only engine output has no lever for the user to move and manufactures an editability that is not real. A directional response returns no series and likewise stays in prose. Build the workbook when the user asks for it, or when the projection feeds a build with drivers of its own - a pro forma, a valuation, a returns or yield-on-cost model. That downstream build is the workbook: load the `xlsx` skill, write the projected values this engine returned into labeled input cells, and reference them from there. Everything the analysis derives on top of that series (an NOI line, a value, a return) is a formula, per the `xlsx` skill's rule that raw data may be hardcoded while the analysis built on it may not. The derived layer includes the reads the narrative states (cumulative change, the spread between cases, a terminal level against today): build them as formulas referencing the series cells, so a workbook the user asked for is a live model rather than a pasted grid that fails the `xlsx` skill's integrity gate. What you must never do is rebuild the projection itself in Excel - taking a returned growth rate and compounding it across periods in cell formulas is re-implementing the engine, which is the same defect as porting the script, and it will drift from the engine's dampening and guard logic. If the user wants to flex a growth rate, that is a new engine run with a new payload, not an editable cell.

**The engine's logic exists in exactly one place: the bundled file.** Never retype, trim, paraphrase, or port `scripts/forecast.py` into a new file, regardless of how it reached you (skill materialization, an attachment, prior conversation text) - a plausible-looking partial replica runs, returns well-formed JSON, and silently omits entire guard paths. If the script is only reachable as text, copy it byte-for-byte. Verify before first use in a session: `python skills/forecasting/scripts/forecast.py --version` prints the params version, date, and a sha256 of the file's own bytes - any port or trim produces a different digest.

If `scripts/forecast.py` cannot be run, or returns `status: "error"`, return that error upward. **Never fall back to a hand-estimated forecast.**

**Surface confidence and flags verbatim.** Any analysis consuming this engine's output must state the returned `confidence` tier and reproduce every `data_quality_flags` entry near the figures they qualify. Paraphrasing a guard warning into vague prose is a defect: the flag text is written for the end reader. Self-check before finalizing: for each figure sourced from this engine, point to where in the draft its confidence tier and any fired guard name appear; if you cannot, they are missing.

**Every input is sourced or omitted, never estimated.** The no-fabrication standard covers the whole payload, not just the arrays: every `context_signals` leaf must trace to a specific tool result, or the sub-block is omitted (signals degrade to `unknown` by design - that is the honest state, and a plausible placeholder is a fabrication that is worse than a visible gap). See Assembling Context Signals in the request reference.

**Where the override lives when a guard fires.** The drawdown and boom guards instruct the caller to apply structural judgment before using the output. That judgment belongs in the consuming analysis's narrative, explicitly labeled as judgment, sitting alongside the engine's numbers. It never takes the form of a resubmitted or synthetic history array designed to move the engine's output; the engine's numbers stand.

# Two Modes, Set by Family

The engine runs in one of two modes, selected by the `family` field in the payload. **The mode is not a stylistic flavor; it is a different output contract.** Choosing a family chooses a response shape.

| Mode | Families | What it does | Returns |
|------|----------|--------------|---------|
| **Trend** | `rent_or_occupancy`, `demographic`, `operating`, `generic` | Projects a compounding series forward (dampened trend + structural terminal anchor + peer reversion + scenario bands) | `base_case` / `upside_case` / `downside_case` arrays |
| **Directional** | `capital_markets` | Reports where an oscillating metric sits in its own historical band, plus the rate signal. **Projects nothing.** | `band_position` + `signals`; **no projected values** |

**Why two modes.** Compounding series (rent, population, home value) have a genuine forward trajectory; projecting them is appropriate. Oscillating series (cap rates) sit in a structural band and move on conditions; they do not compound. Fitting a growth rate to a cap rate and projecting it forward is a category error that produces runaway nonsense (a cap rate climbing indefinitely). For those metrics the honest output is a directional read: where the level sits relative to its own history, plus the rate environment, which the consuming analysis synthesizes into its own view. The engine emits no outlook, no firmer/softer call, and no future cap-rate value.

**The mode is enforced structurally.** The directional code path is incapable of emitting a `base_case`. So a metric mistagged into the wrong family fails loudly (a cap rate accidentally tagged `generic` falls into trend mode and produces a visibly absurd projection a reviewer catches) rather than silently emitting a plausible-looking fake trajectory. Every response carries a `mode` field (`trend` | `directional`) as a one-field assertion target.

# Boundary and Invocation

**Pure compute primitive.** A calculation engine only: zero external data fetching, zero document parsing, zero underwriting or recommendations.

**Rates, trajectories, and band reads only.** Outputs market-level or property-level rates, trajectories, or band positions. It does not generate pro formas, cash flow waterfalls, or returns; those belong to the consuming domain analysis, which takes this engine's output as an upstream input.

**Stateless, one metric per call.** Each call passes all required history arrays, peer arrays, and context in a single payload. Parallel forecasts are split into distinct invocations.

**Signals are qualitative, never arithmetic.** `context_signals` values drive directional flags only; no signal is ever multiplied into a computed number. The flags are passed up so the consuming analysis folds them into its written read, where economic judgment belongs, rather than smuggled into a number as fabricated basis points.

# Pre-Flight Checklist

Walk this before assembling any payload. Every item maps to a documented failure mode; the request reference has the detail.

1. **Canonical script verified?** Run `--version` once per session; never a retyped or trimmed copy.
2. **Arrays traced to source?** Every numeric array parsed by code from a retained raw tool result, zero hand-typed literals - and the `history_check` computed from that raw result, never from the assembled array (a check sharing a manual-transcription step with its array validates nothing).
3. **Sibling series checked?** If the sibling field is in the same fetched result, checking it is mandatory; compute `sibling_divergence_pct`, and over 100 bps of trailing-12-month divergence run both series.
4. **Peer actually comparable?** Price band and cycle position stated as numbers in `caller_disclosures.peer_selection_basis`, not adjectives. Grain-locked topic with no parent: test a custom basket before claiming no peer exists.
5. **Lookback vs. horizon disambiguated?** "The last N years" is usually a lookback instruction, not a projection horizon. Declare it in `requested_lookback_years` so a shortfall becomes a structured flag.
6. **Signals triaged?** Every family-relevant `context_signals` sub-block populated or logged in `caller_disclosures.signals_omitted` - the engine flags silent absences ("signals not triaged"). Scan this session's existing tool results against the sourcing map first.
7. **Parallel calls consistent?** Sibling or multi-cut calls in one session hold peer sourcing, signals, and horizon constant unless a divergence is deliberate and disclosed.
8. **Checks declared?** `history_check` (and `peer_history_check`) in every payload; `as_of` when the analysis date matters; `projected_as_of` on any rate projection.

# Running the Script

```bash
python skills/forecasting/scripts/forecast.py --file payload.json
```

Dependencies: numpy only. No network, no file fetching. Output is a single JSON object (the response schema) printed to stdout. Blocking failures return `status: "error"` with an `error` string; computed-with-alerts responses return `status: "warning"` with `data_quality_flags` populated.

**Assemble arrays programmatically, and declare the check.** Build `history` and `peer_history` in code from the raw query result (parse the JSON, emit the array); never retype values by hand. Include `history_check` (count plus sum or last_value, taken from the source data) - and `peer_history_check` when a peer is supplied - in every payload: the script mechanically validates the array it received against the declaration and errors loudly on a mismatch. An array assembled in code produces a matching check for free; only a transcription slip ever trips it. Hand-transcription of more than a handful of periods is a defect even when it happens to produce correct numbers.

# Reference files

Read on demand for the task at hand. Each is one level deep from this file.

- [references/request.md](references/request.md): the metric specification and family options, the full request schema, the rules for assembling history and peer arrays from the datamart, and two worked example payloads (trend and directional).
- [references/methodology.md](references/methodology.md): the trend-mode arithmetic (dampened trend with structural terminal anchor, peer mean reversion, scenario envelope), the cyclical-drawdown and boom-extrapolation guards, the parameter and terminal-rate table, the directional-mode band read, and the signal thresholds.
- [references/response.md](references/response.md): both response schemas (trend and directional) with worked example responses, confidence calibration, error handling, and the list of things this engine must never do.
