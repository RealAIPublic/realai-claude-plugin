#!/usr/bin/env python3
"""
Forecasting Engine — reference computation engine.

This is the SOLE math authority for the Forecasting Engine. The calling
agent assembles the request payload (history arrays, peer arrays, context
signals) and invokes this script. The script performs the three computed
operations — dampened trend extrapolation, peer mean reversion, scenario
envelope — entirely in deterministic Python, evaluates the qualitative
signals, and returns the response object.

The agent MUST NOT estimate, adjust, or recompute any forecast value in prose.
Its job is: assemble payload -> call this -> read result -> narrate -> done.

Usage:
    python forecast.py '<request_json>'
    python forecast.py --file path/to/request.json
    echo '<request_json>' | python forecast.py -

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
# --------------------------------------------------------------------------
PARAMS = {
    # Dampening: blend recent growth toward the series long-run mean as the
    # horizon extends. d_t ramps linearly from DAMPEN_YEAR1 up to DAMPEN_CAP.
    "DAMPEN_YEAR1": 0.20,        # year-1 blend weight toward long-run mean
    "DAMPEN_CAP": 0.50,          # far-out years are at most a 50/50 blend
    # Mean reversion: trigger when subject deviates from peer cohort by > this
    # many standard deviations; then blend toward peer median at this rate/yr.
    "REVERSION_SIGMA_TRIGGER": 1.0,
    "REVERSION_WEIGHT_PER_YEAR": 0.30,
    # Scenario bands: +/- this many sigma at year 1, widening by the per-year
    # factor (multiplicative on the half-width) for each subsequent year.
    "SCENARIO_SIGMA": 1.0,
    "SCENARIO_WIDEN_PER_YEAR": 1.15,
    # Signal thresholds — COARSE BY DESIGN. They set direction, not magnitude,
    # and are never multiplied into a number.
    "SUPPLY_ELEVATED_SHARE": 0.05,   # under-construction / existing stock
    "SUPPLY_MODERATE_SHARE": 0.025,
    "MIGRATION_POSITIVE_PCT": 0.10,  # inbound income vs outbound
    "MIGRATION_NEGATIVE_PCT": -0.10,
    "EMPLOYMENT_POSITIVE_PCT": 0.02,
    "EMPLOYMENT_NEGATIVE_PCT": 0.0,
    "INFLATION_FLOOR_DEFAULT": 0.025,  # operating-family sanity floor
    # Directional mode (capital_markets) — band-position labels. Position is
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
    # NOT invent a recovery curve — that judgment belongs to the calling agent.
    "DRAWDOWN_MAX_HISTORY_MONTHS": 30,   # "short" history threshold
    "DRAWDOWN_NEGATIVE_GROWTH": -0.005,  # trailing growth below this = drawdown
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
    """Std dev of period-over-period growth — drives scenario band width."""
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


def _history_depth_months(rows):
    span = _parse_period(rows[-1]["period"]) - _parse_period(rows[0]["period"])
    return int(round(span.days / 30.44))


# --------------------------------------------------------------------------
# The three computed operations
# --------------------------------------------------------------------------
def compute_base_trajectory(years, vals, n_years):
    """
    Operation 1: dampened trend extrapolation.
    Returns (per_year_growth_rates, last_value, recent_growth, lr_mean, r2).
    """
    recent_growth, r2 = _annualized_growth_from_regression(years, vals)
    lr_mean = _long_run_mean_growth(years, vals)
    growth_path = []
    for t in range(1, n_years + 1):
        d = _dampening_weight(t, n_years)
        g_t = recent_growth * (1.0 - d) + lr_mean * d
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


def detect_cyclical_drawdown(growth_path, depth_months, recent_growth):
    """
    True when the engine is being asked to project a correction off a window
    too short to contain a full cycle. In that case extrapolating the trend
    means extrapolating the drawdown, which is the wrong frame for a multi-year
    hold (see Charlotte rent case). Returns a bool.
    """
    short = depth_months <= PARAMS["DRAWDOWN_MAX_HISTORY_MONTHS"]
    declining = recent_growth < PARAMS["DRAWDOWN_NEGATIVE_GROWTH"]
    return bool(short and declining)


def apply_drawdown_hold(growth_path):
    """
    When a cyclical drawdown is suspected on short history, do not project the
    decline forward. Hold the year-1 trailing rate for year 1 (acknowledging
    the correction hasn't cleared), then flat (0% growth) thereafter. The
    engine deliberately does NOT invent a recovery — it stops misleading and
    defers the cycle-bridge judgment to the calling agent via a low-confidence
    flag and a warning.
    """
    if not growth_path:
        return growth_path
    held = [growth_path[0]]  # keep the honest trailing signal for year 1
    held += [0.0] * (len(growth_path) - 1)  # flat thereafter, not declining
    return held


def build_cases(growth_path, last_value, n_years, scenarios, sigma):
    """
    Operation 3: scenario envelope.
    Compound the base growth path forward, then widen +/- sigma bands that
    grow with horizon. Returns (base_case, upside_case, downside_case).
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

    s = PARAMS["SCENARIO_SIGMA"] * sigma
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
# Directional mode (capital_markets) — NO projection, NO growth, NO values
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
# Signals — qualitative flags, never multiplied into numbers
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
        if not m or m.get("inbound_income_vs_outbound_pct") is None:
            return "unknown"
        d = m["inbound_income_vs_outbound_pct"]
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
        if not r or not r.get("direction"):
            return "unknown"
        d = r["direction"]
        return d if d in ("tightening", "easing", "stable") else "unknown"

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
    # generic: no signals
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
    if len(history) < MIN_DATA_POINTS:
        return {"status": "error",
                "error": f"history has {len(history)} points; minimum is {MIN_DATA_POINTS}"}

    peer_history = request.get("peer_history") or []
    scenarios = request.get("scenarios") or ["base"]
    ctx = request.get("context_signals") or {}

    # ---- computation ----
    years, vals, rows = _sorted_series(history)
    depth_months = _history_depth_months(rows)

    # ============================================================
    # DIRECTIONAL MODE — capital_markets only.
    # Oscillating series (cap rates) do NOT compound, so applying a
    # trend/growth is a category error. This path projects NOTHING.
    # It reports observed band position + the rate-environment signal,
    # and the calling agent synthesizes its own view. This path is
    # STRUCTURALLY incapable of emitting a base_case — that is the
    # contract guarantee that a mistagged family fails loudly rather
    # than producing a fake cap-rate trajectory.
    # ============================================================
    if family == "capital_markets":
        band = compute_band_position(years, vals)
        signals = evaluate_signals(family, ctx)  # -> {"rate_environment": ...}

        warnings = []
        if scenarios and scenarios != ["base"]:
            warnings.append("scenarios ignored: capital_markets is directional, "
                            "not projected — no scenario envelope is produced")
        if depth_months < 24:
            warnings.append("under 24 months of history; band position is "
                            "weakly characterized")

        confidence = "high" if depth_months >= 24 else (
            "medium" if depth_months >= 12 else "low")

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
            # No base_case / upside_case / downside_case — by design.
            "band_position": band,
            "signals": signals,
            "methodology": {
                "primary_method": "Directional band-position read (no projection)",
                "history_depth_months": depth_months,
                "note": "Oscillating metric: structural band reported from "
                        "observed history; no growth applied, no future values "
                        "produced. Caller synthesizes outlook from band position "
                        "and rate-environment signal.",
                "computed_in_sandbox": True,
            },
            "confidence": confidence,
            "data_quality_flags": warnings,
            "narrative": None,  # caller writes this from band + signal
        }

    # ============================================================
    # TREND MODE — rent_or_occupancy, demographic, operating, generic.
    # These genuinely compound; the three computed operations apply.
    # ============================================================
    try:
        n_years = int(horizon.get("years"))
    except (TypeError, ValueError):
        return {"status": "error", "error": "horizon.years missing or non-integer"}
    if not (HORIZON_MIN_YEARS <= n_years <= HORIZON_MAX_YEARS):
        return {"status": "error",
                "error": f"horizon {n_years}y outside {HORIZON_MIN_YEARS}-{HORIZON_MAX_YEARS}y envelope"}

    growth_path, last_value, recent_growth, lr_mean, r2 = compute_base_trajectory(
        years, vals, n_years)

    growth_path, reversion_applied, sigma_pre, rev_weight = apply_mean_reversion(
        growth_path, years, vals, peer_history, n_years)

    drawdown_suspected = detect_cyclical_drawdown(
        growth_path, depth_months, recent_growth)
    if drawdown_suspected:
        growth_path = apply_drawdown_hold(growth_path)

    sigma = _residual_volatility(years, vals)
    base, upside, downside = build_cases(
        growth_path, last_value, n_years, scenarios, sigma)

    signals = evaluate_signals(family, ctx)

    confidence = assess_confidence(
        depth_months, n_years, reversion_applied, sigma_pre, signals)
    if drawdown_suspected:
        confidence = "low"  # short window in a correction cannot be projected

    warnings = collect_warnings(
        depth_months, growth_path, n_years, reversion_applied,
        peer_history, base, upside, downside)
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
            "primary_method": "Dampened trend extrapolation with peer mean reversion",
            "history_depth_months": depth_months,
            "trend_r2": round(r2, 4),
            "recent_annualized_growth": round(recent_growth, 4),
            "long_run_mean_growth": round(lr_mean, 4),
            "dampening_cap_applied": PARAMS["DAMPEN_CAP"],
            "mean_reversion_applied": reversion_applied,
            "peer_deviation_sigma_pre": round(sigma_pre, 4) if sigma_pre is not None else None,
            "reversion_weight_per_year": rev_weight,
            "cyclical_drawdown_suspected": drawdown_suspected,
            "scenario_sigma_source": "residual_volatility",
            "computed_in_sandbox": True,
        },
        "signals": signals,
        "confidence": confidence,
        "data_quality_flags": warnings,
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
    try:
        req = _load_request(sys.argv)
    except Exception as e:
        print(json.dumps({"status": "error",
                          "error": f"could not parse request: {e}"}))
        sys.exit(0)
    print(json.dumps(run(req), indent=2))
