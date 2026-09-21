#!/usr/bin/env python3
"""
Forecasting engine - reference computation for the forecasting skill.

This is the SOLE math authority for the forecasting skill. The caller
assembles the request payload (history arrays, peer arrays, context
signals) and invokes this script. The script performs the three computed
operations - dampened trend extrapolation with a structural terminal
anchor, peer mean reversion, scenario envelope - entirely in deterministic
Python, applies the cyclical-drawdown and boom-extrapolation guards,
evaluates the qualitative signals, and returns the response object.

The caller MUST NOT estimate, adjust, or recompute any forecast value in
prose. Its job is: assemble payload -> call this -> read result -> narrate
-> done.

Usage:
    python forecast.py '<request_json>'
    python forecast.py --file path/to/request.json
    echo '<request_json>' | python forecast.py -
    python forecast.py --version   (params version, date, sha256 of this file)

Output: a single JSON object (the response schema) printed to stdout.

Dependencies: numpy only. (No network, no file fetching, no document parsing.)
"""

import sys
import json
import math
from datetime import datetime

import numpy as np


# --------------------------------------------------------------------------
# Tunable parameters. These are the ONLY magic numbers in the methodology,
# and they are deliberately few. Tune against real series; do not multiply.
#
# The terminal rates are versioned house-view parameters, refreshed on a
# deliberate cadence (target quarterly), never live-sourced per call:
# determinism across the agent suite requires the same payload to produce
# the same numbers. Bump PARAMS_VERSION and PARAMS_VERSION_DATE on refresh.
# --------------------------------------------------------------------------
PARAMS_VERSION = "2026Q3.5"
PARAMS_VERSION_DATE = "2026-07-22"

PARAMS = {
    # Dampening: blend recent growth toward the series long-run mean as the
    # horizon extends. d_t ramps linearly from DAMPEN_YEAR1 up to DAMPEN_CAP.
    "DAMPEN_YEAR1": 0.20,        # year-1 blend weight toward long-run mean
    "DAMPEN_CAP": 0.50,          # far-out years are at most a 50/50 blend
    # Structural terminal anchor: the third blend term. w_t ramps from 0 at
    # year 1 to the cap at the final year, pulling late years toward a
    # window-independent house-view rate. This is what makes the forecast
    # level off when the entire history window sits inside a single regime
    # (where the series own long-run mean IS the regime and cannot anchor).
    # It is an anchor, not a signal: a fixed methodology parameter, never
    # multiplied by anything in context_signals.
    "TERMINAL_WEIGHT_CAP": 0.60,
    "TERMINAL_WEIGHT_CAP_BOOM": 0.85,   # accelerated convergence when boom fires
    # Structural terminal rates by trend family (see methodology reference
    # for the sourcing basis; sourced 2026-07).
    "TERMINAL_RATES": {
        "rent_or_occupancy": 0.028,
        "operating": 0.035,
        "demographic": 0.004,   # national; bounded market spread added at runtime
        "generic": 0.025,
    },
    "TERMINAL_RATE_BASIS": {
        "rent_or_occupancy": "family terminal 0.0280",
        "operating": "family terminal 0.0350",
        "demographic": "national 0.0040 plus bounded market spread "
                       "(subject long-run growth vs national, capped at 60bps)",
        "generic": "family terminal 0.0250",
    },
    # Demographic terminal = national rate + market spread, spread bounded
    # to +/- this cap so a hot or shrinking market cannot drag the anchor.
    "DEMOGRAPHIC_SPREAD_CAP": 0.006,
    # Mean reversion: trigger when subject deviates from peer cohort by > this
    # many standard deviations; then blend toward peer median at this rate/yr.
    "REVERSION_SIGMA_TRIGGER": 1.0,
    "REVERSION_WEIGHT_PER_YEAR": 0.30,
    # Scenario bands: +/- this many sigma at year 1, widening by the per-year
    # factor (multiplicative on the half-width) for each subsequent year.
    # The year-1 half-width is the LARGER of residual volatility and the
    # per-family structural floor: residual volatility of a smooth series
    # measures noise around the trend, not regime-change risk, and a band
    # that cannot contain a regime shift is not an honest deliverable.
    "SCENARIO_SIGMA": 1.0,
    "SCENARIO_WIDEN_PER_YEAR": 1.15,
    "SCENARIO_HALFWIDTH_FLOOR": {
        "rent_or_occupancy": 0.02,
        "operating": 0.015,
        "demographic": 0.01,
        "generic": 0.015,
    },
    # Signal thresholds - COARSE BY DESIGN. They set direction, not magnitude,
    # and are never multiplied into a number.
    "SUPPLY_ELEVATED_SHARE": 0.05,   # under-construction / existing stock
    "SUPPLY_MODERATE_SHARE": 0.025,
    "MIGRATION_POSITIVE_PCT": 0.10,  # inbound income vs outbound
    "MIGRATION_NEGATIVE_PCT": -0.10,
    "EMPLOYMENT_POSITIVE_PCT": 0.02,
    "EMPLOYMENT_NEGATIVE_PCT": 0.0,
    "INFLATION_FLOOR_DEFAULT": 0.025,  # operating-family sanity floor
    # Rate-environment classification (capital_markets). Numeric form: the
    # caller passes current and projected benchmark rates in percent (e.g.
    # 3.8) and the engine classifies the direction itself, with the same
    # coarse documented treatment the other signals get. A move smaller than
    # the threshold (in pct-points) is noise, not a direction. Free-text
    # "direction" remains accepted as a fallback.
    "RATE_DIRECTION_THRESHOLD": 0.25,
    # Structural-ceiling proximity (trend families, optional). The caller
    # supplies the family-relevant ratio (rent-to-income, price-to-income,
    # expense-to-EGI) and its defended ceiling; the engine labels proximity.
    # Like every signal, it is directional only - never multiplied into a
    # number.
    "CEILING_APPROACHING_SHARE": 0.90,
    # Directional mode (capital_markets) - band-position labels. Position is
    # (current - min) / (max - min) over the observed history. COARSE BY DESIGN:
    # these label where current sits in its OWN past range; they describe the
    # past, they do not predict.
    "BAND_RICH_ABOVE": 0.66,   # current in top third of its historical range
    "BAND_CHEAP_BELOW": 0.34,  # current in bottom third
    # Cyclical-drawdown guard (trend mode). Short histories sitting in a
    # correction extrapolate the correction, because both recent growth and
    # the long-run mean computed off that window are negative. The engine
    # cannot see a full cycle in a short window, so it must NOT confidently
    # project a negative trend far out. When triggered: hold flat after year 1
    # instead of extrapolating the decline, force low confidence, and warn the
    # caller to supply a longer history or structural context. The engine does
    # NOT invent a recovery curve - that judgment belongs to the calling agent.
    "DRAWDOWN_MAX_HISTORY_MONTHS": 30,   # "short" history threshold
    "DRAWDOWN_NEGATIVE_GROWTH": -0.005,  # trailing growth below this = drawdown
    # Boom-extrapolation guard (trend mode) - the symmetric mirror of the
    # drawdown guard. Fires when trailing growth is positive AND either it
    # exceeds the family terminal by more than the multiple below, or the
    # entire history window starts inside a single known-hot regime (on or
    # after BOOM_REGIME_START), where the series own long-run mean is itself
    # inflated and cannot serve as a leveling anchor. Booms decay, they do
    # not stop: the engine accelerates convergence toward the terminal rate
    # (TERMINAL_WEIGHT_CAP_BOOM) and caps confidence at medium.
    "BOOM_TERMINAL_MULTIPLE": 1.75,
    "BOOM_REGIME_START": "2020-01-01",
    # Stale-series guard (both modes). N trailing identical values reads as a
    # possibly non-refreshed source (appraisal-lagged series carry the last
    # print forward when transaction volume dries up), not as genuine
    # stability. A flatlined series must never silently read as "stable" or
    # earn high confidence without disclosure.
    "STALE_SERIES_RUN": 4,
    # Directional dual band: when the observed window exceeds this many
    # months, a trailing sub-window band is reported alongside the full
    # history band so a multi-regime window (GFC spike, ZIRP lows, hiking
    # cycle) cannot silently dominate the read.
    "DIRECTIONAL_TRAILING_BAND_MONTHS": 120,
    # Peer-mismatch flag: the reversion trigger is 1 sigma, but a deviation
    # this many sigma out is a different animal - it usually means the peer
    # itself is a poor reversion target (wrong price tier, wrong cycle
    # position), not that the subject is wildly hot. Loud flag, no math
    # change; the caller decides whether to swap in a custom peer basket.
    "PEER_MISMATCH_SIGMA": 3.0,
    # Recency check (opt-in via the request's as_of date): flag when the
    # last observation is more than this many native-cadence intervals older
    # than as_of. Catches a single old print the stale-series guard's
    # identical-values pattern cannot see. Keyed to the caller-declared
    # as_of, never the wall clock, so the same payload always produces the
    # same output.
    "RECENCY_STALE_MULTIPLE": 2.0,
    # Peer level ratio: an ex-ante price-tier check, distinct from the
    # ex-post growth-sigma mismatch flag. Reversion blends growth rates, so
    # a level gap does not poison the math directly - but a peer trading at
    # more than this multiple (or less than its inverse) of the subject's
    # level is usually a different price tier whose cycle the subject does
    # not share. A normal parent premium (nation vs a secondary metro) sits
    # well inside this bound; only a genuine tier mismatch trips it.
    "PEER_LEVEL_RATIO_MAX": 1.5,
    # Lookback shortfall: when the caller declares the lookback the user
    # asked for, flag when the available span covers less than this share
    # of it, so "asked for 4 years, had 2" is a structured response field
    # rather than a narrative courtesy.
    "LOOKBACK_SHORTFALL_SHARE": 0.95,
    # Rate-projection horizon check: when the caller declares as_of and the
    # year the projected_rate refers to, a projection that falls short of
    # the analysis horizon draws a flag instead of a silently substituted
    # nearer year. Directional (capital_markets) calls have no horizon, so
    # they read against this default forward window.
    "RATE_PROJECTION_DEFAULT_YEARS": 3,
}

# Family-relevant context_signals blocks, enforced by the triage check: each
# must be populated from a real source or logged in
# caller_disclosures.signals_omitted with a reason. A silently absent block
# and a considered-and-omitted block must not look identical in the payload.
# structural_ceiling stays optional everywhere by design (an overlay, not a
# family-fixed signal).
FAMILY_SIGNAL_BLOCKS = {
    "rent_or_occupancy": ("supply_pipeline", "migration", "employment"),
    "demographic": ("migration", "employment"),
    "capital_markets": ("rate_environment",),
    "operating": (),
    "generic": (),
}

VALID_FAMILIES = {
    "rent_or_occupancy", "capital_markets", "demographic", "operating", "generic"
}
HORIZON_MIN_YEARS = 1
HORIZON_MAX_YEARS = 10
MIN_DATA_POINTS = 6


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _parse_period(p):
    return datetime.strptime(p, "%Y-%m-%d")


def _sorted_series(history):
    """Return (periods_as_years_from_start, values) sorted by date."""
    rows = sorted(history, key=lambda r: _parse_period(r["period"]))
    t0 = _parse_period(rows[0]["period"])
    years = np.array(
        [(_parse_period(r["period"]) - t0).days / 365.25 for r in rows],
        dtype=float,
    )
    vals = np.array([float(r["value"]) for r in rows], dtype=float)
    return years, vals, rows


def _annualized_growth_from_regression(years, vals):
    """
    Fit log(value) ~ a + b*year via least squares. Return (annual_growth, r2).
    Log-linear so the slope is a compounding rate, which is what rent/price/
    population series actually do. Falls back gracefully on non-positive values.
    """
    if np.any(vals <= 0):
        # Cap rates can't go negative in practice, but guard anyway: use a
        # linear fit on raw values and express growth relative to the mean.
        b, a = np.polyfit(years, vals, 1)
        pred = a + b * years
        ss_res = np.sum((vals - pred) ** 2)
        ss_tot = np.sum((vals - vals.mean()) ** 2)
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
        mean_v = vals.mean()
        growth = b / mean_v if mean_v != 0 else 0.0
        return float(growth), float(max(0.0, min(1.0, r2)))

    logv = np.log(vals)
    b, a = np.polyfit(years, logv, 1)
    pred = a + b * years
    ss_res = np.sum((logv - pred) ** 2)
    ss_tot = np.sum((logv - logv.mean()) ** 2)
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    annual_growth = math.exp(b) - 1.0  # convert log-slope to compounding rate
    return float(annual_growth), float(max(0.0, min(1.0, r2)))


def _long_run_mean_growth(years, vals):
    """
    Long-run mean growth = the average period-over-period growth across the
    full window. This is the anchor the dampening pulls toward.
    """
    if len(vals) < 2:
        return 0.0
    # period-over-period compounding rates, then geometric mean
    ratios = vals[1:] / vals[:-1]
    ratios = ratios[np.isfinite(ratios) & (ratios > 0)]
    if len(ratios) == 0:
        return 0.0
    span_years = years[-1] - years[0]
    if span_years <= 0:
        return 0.0
    total_growth = vals[-1] / vals[0]
    if total_growth <= 0:
        return 0.0
    return float(total_growth ** (1.0 / span_years) - 1.0)


def _residual_volatility(years, vals):
    """Std dev of period-over-period growth - drives scenario band width."""
    if len(vals) < 2:
        return 0.0
    ratios = vals[1:] / vals[:-1] - 1.0
    ratios = ratios[np.isfinite(ratios)]
    if len(ratios) < 2:
        return 0.0
    return float(np.std(ratios, ddof=1))


def _dampening_weight(year_index, n_years):
    """
    d_t ramps linearly from DAMPEN_YEAR1 at year 1 up to DAMPEN_CAP, then holds.
    year_index is 1-based.
    """
    d1 = PARAMS["DAMPEN_YEAR1"]
    cap = PARAMS["DAMPEN_CAP"]
    if n_years <= 1:
        return min(d1, cap)
    # linear ramp from d1 (year 1) to cap (reached by the final year), capped
    frac = (year_index - 1) / max(1, (n_years - 1))
    d = d1 + (cap - d1) * frac
    return float(min(d, cap))


def _terminal_weight(year_index, n_years, w_cap):
    """
    w_t ramps linearly from 0 at year 1 to w_cap at the final year. Year 1
    stays pure recent/mean momentum; the final year is pulled hardest toward
    the structural terminal rate.
    """
    if n_years <= 1:
        return 0.0
    frac = (year_index - 1) / max(1, (n_years - 1))
    return float(min(w_cap * frac, w_cap))


def _resolve_terminal_rate(family, lr_mean):
    """
    Return (terminal_rate, basis_string) for a trend family. Demographic is
    the one runtime-composed rate: national base plus a market spread derived
    from the subject's own long-run growth, bounded to +/- the spread cap so
    an outlier market cannot drag the anchor.
    """
    base = PARAMS["TERMINAL_RATES"][family]
    basis = PARAMS["TERMINAL_RATE_BASIS"][family]
    if family == "demographic":
        cap = PARAMS["DEMOGRAPHIC_SPREAD_CAP"]
        spread = max(-cap, min(cap, lr_mean - base))
        return float(base + spread), basis
    return float(base), basis


def _history_depth_months(rows):
    span = _parse_period(rows[-1]["period"]) - _parse_period(rows[0]["period"])
    return int(round(span.days / 30.44))


def _stale_series_suspected(vals):
    """
    True when the trailing STALE_SERIES_RUN periods are identical (within a
    de minimis tolerance). That pattern reads as a possibly non-refreshed
    source, not genuine stability, and must be disclosed rather than scored
    as high confidence.
    """
    n = PARAMS["STALE_SERIES_RUN"]
    if len(vals) < n:
        return False
    tail = np.asarray(vals[-n:], dtype=float)
    tol = 1e-9 * max(1.0, abs(float(tail[0])))
    return bool(np.all(np.abs(tail - tail[0]) <= tol))


def _validate_source_check(check, rows, label):
    """
    Validate a caller-declared source check against the (date-sorted) array
    the script actually received. The check is the mechanical backstop for
    the assemble-programmatically rule: an array built in code produces a
    matching count/sum for free, while a hand-transcription slip surfaces as
    a loud blocking error instead of silently poisoning the trend. Returns
    an error string, or None when every declared key matches.
    """
    if not check:
        return None
    vals = [float(r["value"]) for r in rows]

    def close(a, b):
        return abs(a - b) <= 1e-6 * max(1.0, abs(b))

    if check.get("count") is not None and int(check["count"]) != len(vals):
        return (f"{label}_check count mismatch: payload declares "
                f"{check['count']}, array has {len(vals)}")
    if check.get("sum") is not None and not close(sum(vals), float(check["sum"])):
        return (f"{label}_check sum mismatch: payload declares "
                f"{check['sum']}, array sums to {sum(vals)}")
    if check.get("first_value") is not None and not close(vals[0], float(check["first_value"])):
        return (f"{label}_check first_value mismatch: payload declares "
                f"{check['first_value']}, earliest value is {vals[0]}")
    if check.get("last_value") is not None and not close(vals[-1], float(check["last_value"])):
        return (f"{label}_check last_value mismatch: payload declares "
                f"{check['last_value']}, latest value is {vals[-1]}")
    return None


def _untriaged_signals(family, ctx, disclosures):
    """
    Names of family-relevant signal blocks that are neither populated in
    context_signals nor accounted for in caller_disclosures.signals_omitted.
    Entries in signals_omitted may be objects with a "signal" key or plain
    strings.
    """
    omitted = set()
    for entry in ((disclosures or {}).get("signals_omitted") or []):
        name = entry.get("signal") if isinstance(entry, dict) else entry
        if name:
            omitted.add(str(name))
    return [b for b in FAMILY_SIGNAL_BLOCKS.get(family, ())
            if not (ctx or {}).get(b) and b not in omitted]


def _rate_projection_shortfall(ctx, as_of, horizon_years):
    """
    Returns (projection_year, target_year) when the declared projected_as_of
    falls short of the analysis horizon (as_of year + horizon), else None.
    Runs only when the caller declared both as_of and projected_as_of, so it
    stays deterministic and opt-in.
    """
    r = (ctx or {}).get("rate_environment") or {}
    proj_asof = r.get("projected_as_of")
    if not as_of or proj_asof is None or horizon_years is None:
        return None
    try:
        proj_year = int(str(proj_asof)[:4])
        target_year = _parse_period(as_of).year + int(horizon_years)
    except (ValueError, TypeError):
        return None
    if proj_year < target_year:
        return (proj_year, target_year)
    return None


def _last_observation_stale(rows, as_of):
    """
    True when the caller declared an as_of date and the most recent
    observation is more than RECENCY_STALE_MULTIPLE native-cadence intervals
    older than it. Distinct from the stale-series guard: this catches a
    series whose last print is simply old, without identical trailing
    values. Deterministic - keyed to the declared as_of, not the wall clock.
    """
    if not as_of or len(rows) < 2:
        return False
    dts = [_parse_period(r["period"]) for r in rows]
    diffs = sorted((dts[i + 1] - dts[i]).days for i in range(len(dts) - 1))
    spacing = diffs[len(diffs) // 2]  # median native cadence, in days
    if spacing <= 0:
        return False
    gap = (_parse_period(as_of) - dts[-1]).days
    return gap > PARAMS["RECENCY_STALE_MULTIPLE"] * spacing


# --------------------------------------------------------------------------
# The three computed operations
# --------------------------------------------------------------------------
def compute_base_trajectory(years, vals, n_years, terminal_rate, w_cap):
    """
    Operation 1: dampened trend extrapolation with structural terminal anchor.
    Three-term blend per year t:
      g_t = recent*(1-d_t)*(1-w_t) + lr_mean*d_t*(1-w_t) + terminal*w_t
    Near-term years stay close to recent momentum; later years converge toward
    the window-independent structural terminal rate.
    Returns (per_year_growth_rates, last_value, recent_growth, lr_mean, r2).
    """
    recent_growth, r2 = _annualized_growth_from_regression(years, vals)
    lr_mean = _long_run_mean_growth(years, vals)
    growth_path = []
    for t in range(1, n_years + 1):
        d = _dampening_weight(t, n_years)
        w = _terminal_weight(t, n_years, w_cap)
        momentum = recent_growth * (1.0 - d) + lr_mean * d
        g_t = momentum * (1.0 - w) + terminal_rate * w
        growth_path.append(g_t)
    return growth_path, float(vals[-1]), recent_growth, lr_mean, r2


def apply_mean_reversion(growth_path, years, vals, peer_history, n_years):
    """
    Operation 2: peer mean reversion.
    If the subject's growth deviates from the peer cohort by more than the
    sigma trigger, blend each year's growth toward the peer median growth.
    Returns (adjusted_growth_path, applied: bool, sigma_pre: float|None,
             weight: float|None).
    """
    if not peer_history or len(peer_history) < 2:
        return growth_path, False, None, None

    p_years, p_vals, _ = _sorted_series(peer_history)
    peer_growth, _ = _annualized_growth_from_regression(p_years, p_vals)
    subject_growth, _ = _annualized_growth_from_regression(years, vals)

    # sigma of subject's period-over-period growth, used to scale the deviation
    subj_vol = _residual_volatility(years, vals)
    if subj_vol <= 0:
        # can't measure deviation in sigma; do not force reversion
        return growth_path, False, None, None

    sigma_pre = abs(subject_growth - peer_growth) / subj_vol
    if sigma_pre <= PARAMS["REVERSION_SIGMA_TRIGGER"]:
        return growth_path, False, float(sigma_pre), None

    w_per_year = PARAMS["REVERSION_WEIGHT_PER_YEAR"]
    adjusted = []
    for t, g_t in enumerate(growth_path, start=1):
        # cumulative blend toward peer median, capped at 1.0
        w = min(1.0, w_per_year * t)
        adjusted.append(g_t * (1.0 - w) + peer_growth * w)
    return adjusted, True, float(sigma_pre), float(w_per_year)


def detect_cyclical_drawdown(depth_months, recent_growth):
    """
    True when the engine is being asked to project a correction off a window
    too short to contain a full cycle. In that case extrapolating the trend
    means extrapolating the drawdown, which is the wrong frame for a multi-year
    hold. Returns a bool.
    """
    short = depth_months <= PARAMS["DRAWDOWN_MAX_HISTORY_MONTHS"]
    declining = recent_growth < PARAMS["DRAWDOWN_NEGATIVE_GROWTH"]
    return bool(short and declining)


def detect_boom_extrapolation(recent_growth, terminal_rate, first_period):
    """
    The symmetric mirror of the drawdown guard: fires when the engine is
    being asked to carry a regime-high growth rate forward. Trailing growth
    must be positive AND either (a) it exceeds the family terminal by more
    than BOOM_TERMINAL_MULTIPLE, or (b) the entire history window sits inside
    a single known-hot regime (starts on or after BOOM_REGIME_START), where
    the series own long-run mean is itself inflated and cannot level the
    forecast. Returns (fired, reasons) where reasons names the specific
    trigger(s) - the warning text is composed from what actually fired, so
    the flag never asserts a comparison its own numbers contradict. Mutually
    exclusive with the drawdown guard; the caller checks drawdown first.
    """
    if recent_growth <= 0:
        return False, []
    reasons = []
    if recent_growth > PARAMS["BOOM_TERMINAL_MULTIPLE"] * terminal_rate:
        reasons.append("above_terminal")
    regime_start = _parse_period(PARAMS["BOOM_REGIME_START"])
    if _parse_period(first_period) >= regime_start:
        reasons.append("single_regime")
    return bool(reasons), reasons


def apply_drawdown_hold(growth_path):
    """
    When a cyclical drawdown is suspected on short history, do not project the
    decline forward. Hold the year-1 trailing rate for year 1 (acknowledging
    the correction hasn't cleared), then flat (0% growth) thereafter. The
    engine deliberately does NOT invent a recovery - it stops misleading and
    defers the cycle-bridge judgment to the calling agent via a low-confidence
    flag and a warning.
    """
    if not growth_path:
        return growth_path
    held = [growth_path[0]]  # keep the honest trailing signal for year 1
    held += [0.0] * (len(growth_path) - 1)  # flat thereafter, not declining
    return held


def build_cases(growth_path, last_value, n_years, scenarios, halfwidth):
    """
    Operation 3: scenario envelope.
    Compound the base growth path forward, then widen +/- bands that grow
    with horizon. halfwidth is the year-1 band half-width: the larger of
    residual volatility and the per-family structural floor.
    Returns (base_case, upside_case, downside_case).
    """
    base, upside, downside = [], [], []
    v_base = last_value
    for t, g_t in enumerate(growth_path, start=1):
        v_base = v_base * (1.0 + g_t)
        base.append({"period": f"Year {t}", "value": round(v_base, 2),
                     "pct_change": round(g_t, 4)})

    want_bands = ("upside" in scenarios) or ("downside" in scenarios)
    if not want_bands:
        return base, [], []

    s = PARAMS["SCENARIO_SIGMA"] * halfwidth
    widen = PARAMS["SCENARIO_WIDEN_PER_YEAR"]
    v_up = last_value
    v_dn = last_value
    for t, g_t in enumerate(growth_path, start=1):
        half = s * (widen ** (t - 1))
        g_up = g_t + half
        g_dn = g_t - half
        v_up = v_up * (1.0 + g_up)
        v_dn = v_dn * (1.0 + g_dn)
        upside.append({"period": f"Year {t}", "value": round(v_up, 2),
                       "pct_change": round(g_up, 4)})
        downside.append({"period": f"Year {t}", "value": round(v_dn, 2),
                         "pct_change": round(g_dn, 4)})

    if "upside" not in scenarios:
        upside = []
    if "downside" not in scenarios:
        downside = []
    return base, upside, downside


# --------------------------------------------------------------------------
# Directional mode (capital_markets) - NO projection, NO growth, NO values
# --------------------------------------------------------------------------
def compute_band_position(years, vals):
    """
    For oscillating series (cap rates), a forward trend is a category error:
    the series sits in a structural band and moves on conditions, it does not
    compound. So we project NOTHING. We report two observed facts only:
      - the historical band (min / structural-mean / max), and
      - where the current level sits within that band.

    These describe the PAST. They do not predict. The calling agent combines
    this with the rate_environment signal to form its own view; this engine
    deliberately emits no outlook, no firmer/softer call, no future value.
    """
    lo = float(np.min(vals))
    hi = float(np.max(vals))
    mean = float(np.mean(vals))
    current = float(vals[-1])

    if hi > lo:
        position = (current - lo) / (hi - lo)
    else:
        position = 0.5  # flat history; current is the band

    if position >= PARAMS["BAND_RICH_ABOVE"]:
        label = "rich"      # current near the top of its own historical range
    elif position <= PARAMS["BAND_CHEAP_BELOW"]:
        label = "cheap"     # current near the bottom of its own historical range
    else:
        label = "mid"

    return {
        "historical_band": {
            "min": round(lo, 4),
            "structural_mean": round(mean, 4),
            "max": round(hi, 4),
        },
        "current_level": round(current, 4),
        "position_in_band": round(position, 4),   # 0 = at min, 1 = at max
        "position_label": label,                  # describes the past, not a forecast
    }


# --------------------------------------------------------------------------
# Signals - qualitative flags, never multiplied into numbers
# --------------------------------------------------------------------------
def evaluate_signals(family, ctx):
    """Return the signals block, including only keys relevant to the family."""
    sig = {}
    ctx = ctx or {}

    def supply():
        sp = ctx.get("supply_pipeline")
        if not sp or not sp.get("existing_stock"):
            return "unknown"
        stock = sp.get("existing_stock") or 0
        uc = sp.get("under_construction_t12") or 0
        if stock <= 0:
            return "unknown"
        share = uc / stock
        if share >= PARAMS["SUPPLY_ELEVATED_SHARE"]:
            return "elevated"
        if share >= PARAMS["SUPPLY_MODERATE_SHARE"]:
            return "moderate"
        return "low"

    def migration():
        m = ctx.get("migration")
        if not m:
            return "unknown"
        # Raw incomes first: the engine does the ratio arithmetic, not the
        # caller. Both figures must be on one consistent basis (both medians
        # or both averages). The precomputed ratio remains accepted.
        inc_in = m.get("inbound_income")
        inc_out = m.get("outbound_income")
        if inc_in is not None and inc_out is not None and float(inc_out) > 0:
            d = (float(inc_in) - float(inc_out)) / float(inc_out)
        else:
            d = m.get("inbound_income_vs_outbound_pct")
        if d is None:
            return "unknown"
        if d >= PARAMS["MIGRATION_POSITIVE_PCT"]:
            return "positive"
        if d <= PARAMS["MIGRATION_NEGATIVE_PCT"]:
            return "negative"
        return "neutral"

    def employment():
        e = ctx.get("employment")
        if not e or e.get("job_growth_1_year_pct") is None:
            return "unknown"
        j = e["job_growth_1_year_pct"]
        if j >= PARAMS["EMPLOYMENT_POSITIVE_PCT"]:
            return "positive"
        if j < PARAMS["EMPLOYMENT_NEGATIVE_PCT"]:
            return "negative"
        return "neutral"

    def rate_env():
        r = ctx.get("rate_environment")
        if not r:
            return "unknown"
        # Numeric form first: the engine classifies, the caller does not
        # assert. Matches the documented-threshold treatment every other
        # signal already gets.
        cur = r.get("current_rate")
        proj = r.get("projected_rate")
        if cur is not None and proj is not None:
            delta = float(proj) - float(cur)
            thr = PARAMS["RATE_DIRECTION_THRESHOLD"]
            if delta >= thr:
                return "tightening"
            if delta <= -thr:
                return "easing"
            return "stable"
        d = r.get("direction")
        return d if d in ("tightening", "easing", "stable") else "unknown"

    def ceiling():
        c = ctx.get("structural_ceiling")
        if not c or c.get("ratio_current") is None or c.get("ratio_ceiling") is None:
            return None
        cur = float(c["ratio_current"])
        cap = float(c["ratio_ceiling"])
        if cap <= 0:
            return None
        share = cur / cap
        if share >= 1.0:
            return "at_ceiling"
        if share >= PARAMS["CEILING_APPROACHING_SHARE"]:
            return "approaching"
        return "room"

    if family == "rent_or_occupancy":
        sig["supply_pressure"] = supply()
        sig["migration_signal"] = migration()
        sig["employment_signal"] = employment()
    elif family == "demographic":
        sig["migration_signal"] = migration()
        sig["employment_signal"] = employment()
    elif family == "capital_markets":
        sig["rate_environment"] = rate_env()
    elif family == "operating":
        sig["inflation_anchor"] = PARAMS["INFLATION_FLOOR_DEFAULT"]
    # generic: no family-fixed signals

    # Structural-ceiling proximity is optional and family-generic across the
    # trend families: emitted only when the caller supplied the block.
    if family != "capital_markets":
        lbl = ceiling()
        if lbl is not None:
            sig["ceiling_proximity"] = lbl
    return sig


# --------------------------------------------------------------------------
# Confidence + warnings
# --------------------------------------------------------------------------
def assess_confidence(depth_months, n_years, reversion_applied, sigma_pre, signals):
    if depth_months < 12 or n_years > 5:
        return "low"
    # signal conflict check
    conflict = (
        signals.get("supply_pressure") == "elevated"
        and signals.get("migration_signal") == "positive"
    )
    if depth_months < 24 or (reversion_applied and (sigma_pre or 0) > 1.0) or conflict:
        return "medium"
    return "high"


def collect_warnings(depth_months, growth_path, n_years, reversion_applied,
                     peer_history, base, upside, downside):
    warns = []
    # dampening cap hit early (n_years small enough that cap reached fast)
    if n_years >= 3 and _dampening_weight(3, n_years) >= PARAMS["DAMPEN_CAP"] - 1e-9:
        warns.append("dampening cap reached by year 3; far-out years weakly informative")
    if not peer_history or len(peer_history) < 2:
        warns.append("thin or absent peer cohort; mean reversion not applied")
    if upside and base:
        last_band = abs(upside[-1]["value"] - downside[-1]["value"]) if downside else 0
        if base[-1]["value"] and last_band / base[-1]["value"] > 0.4:
            warns.append("wide scenario divergence relative to point estimate")
    return warns


def _operating_short_history_fallback(request, metric, horizon, n_years,
                                      history, scenarios, ctx):
    """
    Operating family only. Nearly every acquisition carries a single T12, not
    a 6+ point expense series, so below the minimum the engine returns the
    family's structural terminal rate as a flat growth path with no trend fit
    - deterministic and versioned - rather than erroring and pushing the
    caller to an off-engine hand-picked default (the exact failure mode this
    engine exists to prevent). The terminal rate, not the lower inflation
    anchor, is the fallback because the family's documented basis is that
    expense risk is UNDER-forecasting. Confidence is low by construction and
    the trend-fit diagnostics are null.
    """
    years, vals, rows = _sorted_series(history)
    depth_months = _history_depth_months(rows)
    terminal_rate, terminal_basis = _resolve_terminal_rate("operating", 0.0)
    growth_path = [terminal_rate] * n_years
    halfwidth_floor = PARAMS["SCENARIO_HALFWIDTH_FLOOR"]["operating"]
    base, upside, downside = build_cases(
        growth_path, float(vals[-1]), n_years, scenarios, halfwidth_floor)
    signals = evaluate_signals("operating", ctx)
    warnings = [
        f"insufficient history for a trend fit ({len(history)} point(s), "
        f"minimum {MIN_DATA_POINTS}): the structural terminal rate "
        f"({terminal_rate:.4f}) was applied as a flat growth path with no "
        "trend component. This is the expected case for operating series (a "
        "single T12), not an error, but the path carries no subject-specific "
        "signal - confidence is low."
    ]
    return {
        "status": "warning",
        "mode": "trend",
        "metric": {
            "name": metric.get("name"),
            "units": metric.get("units"),
            "family": "operating",
        },
        "subject": request.get("subject", {}).get("entity_id"),
        "horizon": f"{n_years}_years_{horizon.get('intervals', 'annual')}",
        "base_case": base,
        "upside_case": upside,
        "downside_case": downside,
        "methodology": {
            "primary_method": "Structural terminal rate fallback "
                              "(insufficient history; no trend fit)",
            "history_depth_months": depth_months,
            "history_point_count": len(rows),
            "lookback_requested_years": (
                float(request["requested_lookback_years"])
                if request.get("requested_lookback_years") is not None else None),
            "lookback_available_years": round(depth_months / 12.0, 2),
            "trend_r2": None,
            "recent_annualized_growth": None,
            "long_run_mean_growth": None,
            "dampening_cap_applied": None,
            "terminal_rate_applied": round(terminal_rate, 4),
            "terminal_rate_basis": terminal_basis,
            "terminal_weight_cap_applied": 1.0,
            "mean_reversion_applied": False,
            "peer_deviation_sigma_pre": None,
            "reversion_weight_per_year": None,
            "cyclical_drawdown_suspected": False,
            "boom_extrapolation_suspected": False,
            "boom_trigger": [],
            "stale_series_suspected": False,
            "peer_proxy_substituted": False,
            "scenario_sigma_source": "structural_floor_only",
            "scenario_halfwidth_floor_applied": halfwidth_floor,
            "params_version": PARAMS_VERSION,
            "params_version_date": PARAMS_VERSION_DATE,
            "computed_in_sandbox": True,
        },
        "signals": signals,
        "confidence": "low",
        "data_quality_flags": warnings,
        "caller_disclosures": request.get("caller_disclosures") or None,
        "narrative": None,
    }


# --------------------------------------------------------------------------
# Main entry
# --------------------------------------------------------------------------
def run(request):
    # ---- validation / blocking failures ----
    metric = request.get("metric", {})
    family = metric.get("family")
    if family not in VALID_FAMILIES:
        return {"status": "error",
                "error": f"family omitted or invalid: {family!r}"}

    horizon = request.get("horizon", {}) or {}

    history = request.get("history") or []
    # Operating is the one family where a short history is the norm (a single
    # T12), so it degrades to a structural-terminal-rate fallback instead of
    # erroring; every other family errors below the minimum.
    operating_fallback = (family == "operating"
                          and 1 <= len(history) < MIN_DATA_POINTS)
    if len(history) < MIN_DATA_POINTS and not operating_fallback:
        return {"status": "error",
                "error": f"history has {len(history)} points; minimum is {MIN_DATA_POINTS}"}

    peer_history = request.get("peer_history") or []
    scenarios = request.get("scenarios") or ["base"]
    ctx = request.get("context_signals") or {}

    # ---- input integrity (before any computation) ----
    as_of = request.get("as_of")
    if as_of:
        try:
            _parse_period(as_of)
        except (ValueError, TypeError):
            return {"status": "error",
                    "error": f"as_of must be YYYY-MM-DD, got: {as_of!r}"}

    years, vals, rows = _sorted_series(history)
    depth_months = _history_depth_months(rows)

    err = _validate_source_check(request.get("history_check"), rows, "history")
    if err:
        return {"status": "error", "error": err}
    peer_check = request.get("peer_history_check")
    if peer_check:
        if not peer_history:
            return {"status": "error",
                    "error": "peer_history_check supplied but peer_history is empty"}
        p_rows = sorted(peer_history, key=lambda r: _parse_period(r["period"]))
        err = _validate_source_check(peer_check, p_rows, "peer_history")
        if err:
            return {"status": "error", "error": err}

    recency_stale = _last_observation_stale(rows, as_of)

    # Caller disclosures ride through verbatim so every assembly decision
    # (peer basis, excluded periods, omitted signals, lookback and sibling
    # notes) lands in the logged tool result, not only in prose the caller
    # may or may not write.
    disclosures = request.get("caller_disclosures") or None

    requested_lookback = request.get("requested_lookback_years")
    available_lookback = round(depth_months / 12.0, 2)
    lookback_short = (
        requested_lookback is not None
        and available_lookback < PARAMS["LOOKBACK_SHORTFALL_SHARE"]
        * float(requested_lookback))

    # ---- computation ----

    # ============================================================
    # DIRECTIONAL MODE - capital_markets only.
    # Oscillating series (cap rates) do NOT compound, so applying a
    # trend/growth is a category error. This path projects NOTHING.
    # It reports observed band position + the rate-environment signal,
    # and the calling agent synthesizes its own view. This path is
    # STRUCTURALLY incapable of emitting a base_case - that is the
    # contract guarantee that a mistagged family fails loudly rather
    # than producing a fake cap-rate trajectory.
    # ============================================================
    if family == "capital_markets":
        band = compute_band_position(years, vals)
        signals = evaluate_signals(family, ctx)  # -> {"rate_environment": ...}
        stale_suspected = _stale_series_suspected(vals)

        # A window spanning multiple rate regimes should not silently
        # dominate the read: report a trailing sub-window band alongside the
        # full-history band and surface any disagreement between the two.
        trailing_band = None
        if depth_months > PARAMS["DIRECTIONAL_TRAILING_BAND_MONTHS"]:
            cutoff = years[-1] - PARAMS["DIRECTIONAL_TRAILING_BAND_MONTHS"] / 12.0
            mask = years >= cutoff
            if 2 <= int(mask.sum()) < len(vals):
                trailing_band = compute_band_position(years[mask], vals[mask])

        warnings = []
        if scenarios and scenarios != ["base"]:
            warnings.append("scenarios ignored: capital_markets is directional, "
                            "not projected; no scenario envelope is produced")
        if depth_months < 24:
            warnings.append("under 24 months of history; band position is "
                            "weakly characterized")
        if stale_suspected:
            warnings.append(
                f"stale series suspected: the trailing "
                f"{PARAMS['STALE_SERIES_RUN']} periods are identical, which "
                "reads as a possibly non-refreshed source (appraisal-lagged "
                "series carry the last print forward) rather than genuine "
                "stability; confidence capped at medium")
        if recency_stale:
            warnings.append(
                "last observation is stale relative to the declared as_of "
                "date: the gap exceeds "
                f"{PARAMS['RECENCY_STALE_MULTIPLE']:g}x the series' native "
                "cadence, so the current level may be outdated; confidence "
                "capped at medium")
        if trailing_band and trailing_band["position_label"] != band["position_label"]:
            warnings.append(
                "band position differs between the full history "
                f"({band['position_label']}) and the trailing 10 years "
                f"({trailing_band['position_label']}): the window spans "
                "multiple regimes - report both reads, do not silently "
                "pick one")
        if lookback_short:
            warnings.append(
                f"lookback shortfall: the caller requested "
                f"{float(requested_lookback):g} years of history but only "
                f"{available_lookback:g} years are available; state the "
                "shortfall before presenting results")
        untriaged = _untriaged_signals(family, ctx, disclosures)
        if untriaged:
            warnings.append(
                f"signals not triaged: [{', '.join(untriaged)}] - each "
                "family-relevant signal must be populated from a real source "
                "or logged in caller_disclosures.signals_omitted with a "
                "reason; a silent absence is indistinguishable from a signal "
                "never considered")
        rate_short = _rate_projection_shortfall(
            ctx, as_of, PARAMS["RATE_PROJECTION_DEFAULT_YEARS"])
        if rate_short:
            warnings.append(
                f"rate projection horizon shortfall: projected_rate "
                f"references {rate_short[0]} while the analysis window "
                f"reaches {rate_short[1]}; use the furthest available "
                "projection and disclose the gap rather than substituting a "
                "nearer, more convenient year")

        confidence = "high" if depth_months >= 24 else (
            "medium" if depth_months >= 12 else "low")
        if (stale_suspected or recency_stale) and confidence == "high":
            confidence = "medium"

        return {
            "status": "warning" if warnings else "ok",
            "mode": "directional",
            "metric": {
                "name": metric.get("name"),
                "units": metric.get("units"),
                "family": family,
            },
            "subject": request.get("subject", {}).get("entity_id"),
            "lookback": f"{depth_months}_months_observed",
            # No base_case / upside_case / downside_case - by design.
            "band_position": band,
            "band_position_trailing_10y": trailing_band,
            "signals": signals,
            "methodology": {
                "primary_method": "Directional band-position read (no projection)",
                "history_depth_months": depth_months,
                "history_point_count": len(rows),
                "lookback_requested_years": (float(requested_lookback)
                                             if requested_lookback is not None else None),
                "lookback_available_years": available_lookback,
                "stale_series_suspected": stale_suspected,
                "params_version": PARAMS_VERSION,
                "params_version_date": PARAMS_VERSION_DATE,
                "note": "Oscillating metric: structural band from observed "
                        "history; no growth applied, no future values produced. "
                        "Caller synthesizes outlook from band position and "
                        "rate-environment signal.",
                "computed_in_sandbox": True,
            },
            "confidence": confidence,
            "data_quality_flags": warnings,
            "caller_disclosures": disclosures,
            "narrative": None,  # caller writes this from band + signal
        }

    # ============================================================
    # TREND MODE - rent_or_occupancy, demographic, operating, generic.
    # These genuinely compound; the three computed operations apply.
    # ============================================================
    try:
        n_years = int(horizon.get("years"))
    except (TypeError, ValueError):
        return {"status": "error", "error": "horizon.years missing or non-integer"}
    if not (HORIZON_MIN_YEARS <= n_years <= HORIZON_MAX_YEARS):
        return {"status": "error",
                "error": f"horizon {n_years}y outside {HORIZON_MIN_YEARS}-{HORIZON_MAX_YEARS}y envelope"}

    if operating_fallback:
        return _operating_short_history_fallback(
            request, metric, horizon, n_years, history, scenarios, ctx)

    # A trend basis substituted from a parent geography (source peer_proxy,
    # see the request reference) carries the parent's trajectory, not the
    # subject's - it computes normally but cannot support high confidence.
    proxy_substituted = any(r.get("source") == "peer_proxy" for r in rows)
    stale_suspected = _stale_series_suspected(vals)

    # Ex-ante price-tier check on the peer, distinct from the ex-post
    # growth-sigma mismatch flag: reversion blends growth rates, but a peer
    # trading at a multiple of the subject's level is usually a different
    # tier whose cycle the subject does not share.
    peer_level_ratio = None
    if peer_history and float(vals[-1]) != 0:
        p_last = sorted(peer_history,
                        key=lambda r: _parse_period(r["period"]))[-1]
        peer_level_ratio = float(p_last["value"]) / float(vals[-1])

    # Regression stats first: the guards and the terminal anchor need them
    # before the growth path is built.
    recent_growth, r2 = _annualized_growth_from_regression(years, vals)
    lr_mean = _long_run_mean_growth(years, vals)
    terminal_rate, terminal_basis = _resolve_terminal_rate(family, lr_mean)

    # Guards are mutually exclusive: a window is either correcting or running
    # hot, never both, and the drawdown check takes precedence.
    drawdown_suspected = detect_cyclical_drawdown(depth_months, recent_growth)
    boom_suspected, boom_reasons = (False, []) if drawdown_suspected else \
        detect_boom_extrapolation(recent_growth, terminal_rate, rows[0]["period"])

    w_cap = (PARAMS["TERMINAL_WEIGHT_CAP_BOOM"] if boom_suspected
             else PARAMS["TERMINAL_WEIGHT_CAP"])

    growth_path, last_value, recent_growth, lr_mean, r2 = compute_base_trajectory(
        years, vals, n_years, terminal_rate, w_cap)

    growth_path, reversion_applied, sigma_pre, rev_weight = apply_mean_reversion(
        growth_path, years, vals, peer_history, n_years)

    if drawdown_suspected:
        growth_path = apply_drawdown_hold(growth_path)

    # Scenario half-width: the larger of residual volatility and the
    # per-family structural floor (regime-change risk, not just trend noise).
    halfwidth_floor = PARAMS["SCENARIO_HALFWIDTH_FLOOR"][family]
    halfwidth = max(_residual_volatility(years, vals), halfwidth_floor)
    base, upside, downside = build_cases(
        growth_path, last_value, n_years, scenarios, halfwidth)

    signals = evaluate_signals(family, ctx)

    confidence = assess_confidence(
        depth_months, n_years, reversion_applied, sigma_pre, signals)
    if confidence == "high" and (boom_suspected or stale_suspected
                                 or proxy_substituted or recency_stale):
        confidence = "medium"  # none of these windows support high confidence
    if drawdown_suspected:
        confidence = "low"  # short window in a correction cannot be projected

    warnings = collect_warnings(
        depth_months, growth_path, n_years, reversion_applied,
        peer_history, base, upside, downside)
    if proxy_substituted:
        warnings.append(
            "trend basis substituted from a parent geography (source "
            "peer_proxy): subject-level history was insufficient, so the "
            "projection carries the parent's trajectory applied at the "
            "subject's level; confidence capped at medium")
    if stale_suspected:
        warnings.append(
            f"stale series suspected: the trailing "
            f"{PARAMS['STALE_SERIES_RUN']} periods are identical, which "
            "reads as a possibly non-refreshed source rather than genuine "
            "stability; confidence capped at medium")
    if recency_stale:
        warnings.append(
            "last observation is stale relative to the declared as_of date: "
            f"the gap exceeds {PARAMS['RECENCY_STALE_MULTIPLE']:g}x the "
            "series' native cadence, so the current level may be outdated; "
            "confidence capped at medium")
    if sigma_pre is not None and sigma_pre > PARAMS["PEER_MISMATCH_SIGMA"]:
        warnings.append(
            f"peer mismatch suspected: the subject's growth deviates "
            f"{sigma_pre:.1f} sigma from the peer cohort (threshold "
            f"{PARAMS['PEER_MISMATCH_SIGMA']:g}). A deviation this large "
            "usually means the peer is a poor reversion target (different "
            "price tier or cycle position), not that the subject is an "
            "outlier; consider a custom peer basket of comparable "
            "geographies and disclose the peer choice either way")
    if peer_level_ratio is not None and (
            peer_level_ratio > PARAMS["PEER_LEVEL_RATIO_MAX"]
            or peer_level_ratio < 1.0 / PARAMS["PEER_LEVEL_RATIO_MAX"]):
        warnings.append(
            f"peer level mismatch: the peer's current level is "
            f"{peer_level_ratio:.2f}x the subject's (bound "
            f"{PARAMS['PEER_LEVEL_RATIO_MAX']:g}x either way). The peer "
            "likely sits in a different price tier whose cycle the subject "
            "does not share; consider a custom peer basket")
    if peer_history and not (disclosures or {}).get("peer_selection_basis"):
        warnings.append(
            "peer selection basis not disclosed: state why this peer was "
            "chosen (parent-geography default or custom basket) and its "
            "comparability in caller_disclosures.peer_selection_basis")
    if lookback_short:
        warnings.append(
            f"lookback shortfall: the caller requested "
            f"{float(requested_lookback):g} years of history but only "
            f"{available_lookback:g} years are available; state the "
            "shortfall before presenting results")
    untriaged = _untriaged_signals(family, ctx, disclosures)
    if untriaged:
        warnings.append(
            f"signals not triaged: [{', '.join(untriaged)}] - each "
            "family-relevant signal must be populated from a real source or "
            "logged in caller_disclosures.signals_omitted with a reason; a "
            "silent absence is indistinguishable from a signal never "
            "considered")
    if boom_suspected:
        # Compose the flag from the trigger(s) that actually fired so the
        # text never asserts a comparison its own numbers contradict.
        parts = []
        if "above_terminal" in boom_reasons:
            parts.append(
                f"recent growth ({recent_growth:.4f}) exceeds the structural "
                f"terminal rate ({terminal_rate:.4f}) by more than "
                f"{PARAMS['BOOM_TERMINAL_MULTIPLE']:g}x")
        if "single_regime" in boom_reasons:
            parts.append(
                "the entire history sits inside a single post-2020 regime, "
                "so the series' own long-run mean cannot serve as a leveling "
                "anchor")
        warnings.insert(0,
            "boom extrapolation suspected: " + "; ".join(parts) + ". "
            "The engine accelerated convergence toward the terminal rate rather "
            "than carrying the boom forward, and capped confidence at medium. "
            "Supply a longer history that spans a full cycle, or have the "
            "calling agent apply structural context (supply pipeline, "
            "rent-to-income ceiling) before using the near-term years as a "
            "multi-year assumption.")
    if drawdown_suspected:
        warnings.insert(0,
            "cyclical drawdown suspected: history is short (<= "
            f"{PARAMS['DRAWDOWN_MAX_HISTORY_MONTHS']}mo) and trailing trend is "
            "negative. The engine held flat after year 1 rather than "
            "extrapolating the correction. Supply a longer history that spans "
            "a full cycle, or have the calling agent apply structural context "
            "and a defended recovery path. Do NOT use this base case as a "
            "multi-year assumption without that judgment.")

    status = "warning" if warnings else "ok"

    response = {
        "status": status,
        "mode": "trend",
        "metric": {
            "name": metric.get("name"),
            "units": metric.get("units"),
            "family": family,
        },
        "subject": request.get("subject", {}).get("entity_id"),
        "horizon": f"{n_years}_years_{horizon.get('intervals', 'annual')}",
        "base_case": base,
        "upside_case": upside,
        "downside_case": downside,
        "methodology": {
            "primary_method": "Dampened trend extrapolation with structural "
                              "terminal anchor and peer mean reversion",
            "history_depth_months": depth_months,
            "history_point_count": len(rows),
            "lookback_requested_years": (float(requested_lookback)
                                         if requested_lookback is not None else None),
            "lookback_available_years": available_lookback,
            "trend_r2": round(r2, 4),
            "recent_annualized_growth": round(recent_growth, 4),
            "long_run_mean_growth": round(lr_mean, 4),
            "dampening_cap_applied": PARAMS["DAMPEN_CAP"],
            "terminal_rate_applied": round(terminal_rate, 4),
            "terminal_rate_basis": terminal_basis,
            "terminal_weight_cap_applied": w_cap,
            "mean_reversion_applied": reversion_applied,
            "peer_deviation_sigma_pre": round(sigma_pre, 4) if sigma_pre is not None else None,
            "peer_level_ratio": (round(peer_level_ratio, 4)
                                 if peer_level_ratio is not None else None),
            "reversion_weight_per_year": rev_weight,
            "cyclical_drawdown_suspected": drawdown_suspected,
            "boom_extrapolation_suspected": boom_suspected,
            "boom_trigger": boom_reasons,
            "stale_series_suspected": stale_suspected,
            "peer_proxy_substituted": proxy_substituted,
            "scenario_sigma_source": "residual_volatility_floored",
            "scenario_halfwidth_floor_applied": halfwidth_floor,
            "params_version": PARAMS_VERSION,
            "params_version_date": PARAMS_VERSION_DATE,
            "computed_in_sandbox": True,
        },
        "signals": signals,
        "confidence": confidence,
        "data_quality_flags": warnings,
        "caller_disclosures": disclosures,
        "narrative": None,  # the calling agent writes this from the values above
    }
    return response


def _load_request(argv):
    if len(argv) >= 2 and argv[1] == "--file":
        with open(argv[2]) as f:
            return json.load(f)
    if len(argv) >= 2 and argv[1] == "-":
        return json.load(sys.stdin)
    if len(argv) >= 2:
        return json.loads(argv[1])
    return json.load(sys.stdin)


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "--version":
        # Canonical-file verification: a caller confirms it is running the
        # bundled script (not a retyped or trimmed copy) by checking this
        # output before first use in a session. The sha256 is computed over
        # the file's own bytes, so any port, trim, or paraphrase - however
        # plausible its output looks - produces a different digest.
        import hashlib
        with open(__file__, "rb") as f:
            digest = hashlib.sha256(f.read()).hexdigest()
        print(json.dumps({"params_version": PARAMS_VERSION,
                          "params_version_date": PARAMS_VERSION_DATE,
                          "sha256": digest}))
        sys.exit(0)
    try:
        req = _load_request(sys.argv)
    except Exception as e:
        print(json.dumps({"status": "error",
                          "error": f"could not parse request: {e}"}))
        sys.exit(0)
    # The contract is a JSON response on stdout in every case: a malformed
    # payload (bad date, non-numeric value, missing key) returns a structured
    # error the caller passes upward, never a traceback.
    try:
        response = run(req)
    except Exception as e:
        response = {"status": "error",
                    "error": f"computation failed on malformed payload: {e}"}
    print(json.dumps(response, indent=2))
