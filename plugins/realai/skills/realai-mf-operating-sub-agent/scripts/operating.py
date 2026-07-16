#!/usr/bin/env python3
"""
RealAI MF Operating Engine — reference computation engine.

This is the SOLE math authority for the Multifamily Operating Engine on the
NO-TEMPLATE path. The calling agent assembles the request payload (property
context, financials, benchmarks, assumptions) and invokes this script. The
script performs the multifamily operating-statement contract documented in
`references/methodology/mf-operating-statement.md` — base-year statement,
forward projection, direct-cap valuation, DCF, levered returns, yield on cost —
entirely in deterministic stdlib Python, and returns the response object.

The agent MUST NOT estimate, adjust, or recompute any operating figure in prose.
Its job is: assemble payload -> call this -> read result -> narrate -> done.

TWO ROLES, set by the top-level `role` field. The role is not a stylistic
flavor — it is a different output contract:

  - role = "authority"   (NO template / workbook present)
        The engine IS the binding math authority. It runs the full
        statement for the requested `mode` and returns binding figures.

  - role = "cross_check" (a template/workbook IS present; realai-pro-forma ran)
        The WORKBOOK WINS. This role computes ONLY headline NOI / EGI / implied
        cap independently and compares them to the workbook's headline outputs,
        returning a BOUNDED, ADVISORY variance read. It is structurally
        incapable of returning a projection, DCF, or levered return — that is
        the contract guarantee that a cross-check can never override the
        workbook or be mistaken for a binding result.

Usage:
    python operating.py '<request_json>'
    python operating.py --file path/to/request.json
    echo '<request_json>' | python operating.py -

Output: a single JSON object (the response schema) printed to stdout.

Dependencies: Python standard library only. (No network, no file fetching, no
document parsing, no third-party packages.)
"""

import sys
import json
import math


# --------------------------------------------------------------------------
# Tunable parameters. Deliberately few. These mirror the thresholds documented
# in the MF operating-statement methodology; tune against real data, do not
# multiply.
# --------------------------------------------------------------------------
PARAMS = {
    # OpEx ratio sanity band (advisory flag, never blocking on its own).
    "OPEX_RATIO_MIN": 0.35,
    "OPEX_RATIO_MAX": 0.55,
    # Other-income plausibility band as a share of net rent (scenario 1 only).
    "OTHER_INCOME_MIN_SHARE": 0.02,
    "OTHER_INCOME_MAX_SHARE": 0.12,
    # Projection defaults (used only when projection_inputs fields are null).
    "DEFAULT_RENT_GROWTH": 0.03,
    "DEFAULT_EXPENSE_GROWTH": 0.025,
    "DEFAULT_OTHER_INCOME_GROWTH": 0.03,
    "DEFAULT_TARGET_VACANCY": 0.06,
    "DEFAULT_MONTHS_TO_STAB_LEASEUP": 18,
    "DEFAULT_MONTHS_TO_STAB_VALUEADD": 24,
    "DEFAULT_HORIZON_YEARS": 5,
    # Stabilization inference thresholds.
    "STABILIZED_OCC_MIN": 0.90,
    "LEASEUP_OCC_MAX": 0.85,
    "VALUEADD_RENT_GAP": 0.10,   # in-place more than 10% below market
    "STABILIZED_RENT_GAP": 0.10,  # in-place within 10% of market
    # Cross-check tolerances. Headline divergence beyond these flags a review.
    # NOI / EGI are percentage tolerances; cap rate is a basis-point tolerance.
    "XCHECK_NOI_PCT": 0.02,
    "XCHECK_EGI_PCT": 0.02,
    "XCHECK_CAP_BPS": 15.0,
}

VALID_MODES = {
    "base_year_only", "projection", "direct_cap",
    "dcf", "levered_returns", "yield_on_cost",
}
VALID_ROLES = {"authority", "cross_check"}


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------
def _num(x):
    """Coerce to float or return None. Empty string / None -> None."""
    if x is None or x == "":
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _present(d, key):
    return d.get(key) is not None and d.get(key) != ""


def _round_money(x):
    return None if x is None else round(float(x))


def _round_pct(x, places=4):
    return None if x is None else round(float(x), places)


# --------------------------------------------------------------------------
# Base-year scenario resolution + statement
# --------------------------------------------------------------------------
def resolve_scenario(fin, ctx, rent_comps):
    """Return the integer scenario (1-4) or None if none is satisfied."""
    full = all(_present(fin, k) for k in
               ("gpr", "vacancy_loss", "other_income", "egi", "opex", "noi"))
    if full:
        return 1
    if (_present(fin, "gpr") and _present(fin, "vacancy_loss")
            and _present(fin, "opex_ratio")
            and not _present(fin, "opex") and not _present(fin, "other_income")):
        return 2
    any_fin = any(_present(fin, k) for k in
                  ("gpr", "vacancy_loss", "other_income", "egi", "opex", "noi"))
    if not any_fin and _present(ctx, "in_place_rent") and _present(ctx, "occupancy"):
        return 3
    if (not any_fin and not _present(ctx, "in_place_rent")
            and _present(rent_comps, "comp_rent_per_unit_month")):
        return 4
    return None


def build_base_year(req):
    """
    Compute the base-year operating statement. Returns (statement, blocking).
    `statement` is the dict of lines; `blocking` is a list of blocking-failure
    strings (non-empty => caller must treat status as error).
    """
    fin = req.get("mf_property_financials") or {}
    ctx = req.get("property_context") or {}
    bench = req.get("benchmarks") or {}
    rent_comps = req.get("rent_comps") or {}

    blocking = []
    scenario = resolve_scenario(fin, ctx, rent_comps)
    if scenario is None:
        return None, ["no base-year scenario satisfied: provide a full income "
                      "statement (scenario 1), gpr+vacancy+opex_ratio (2), "
                      "in_place_rent+occupancy (3), or comp rent (4)"]

    units = _num(ctx.get("units"))
    other_income_present = (scenario == 1)

    if scenario == 1:
        gpr = _num(fin.get("gpr"))
        vac = _num(fin.get("vacancy_loss"))
        oi = _num(fin.get("other_income"))
        egi = _num(fin.get("egi"))
        opex = _num(fin.get("opex"))
        noi = _num(fin.get("noi"))
        if vac is not None and vac > 0:
            blocking.append("vacancy_loss must be stored as a negative number")
        net_rent = (gpr + vac) if (gpr is not None and vac is not None) else None
        # identity check EGI - OpEx = NOI
        if egi is not None and opex is not None and noi is not None:
            if abs((egi - opex) - noi) > max(1.0, 0.005 * abs(noi)):
                blocking.append("reported figures fail identity EGI - OpEx = NOI")

    elif scenario == 2:
        gpr = _num(fin.get("gpr"))
        vac = _num(fin.get("vacancy_loss"))
        opex_ratio = _num(fin.get("opex_ratio"))
        if vac is not None and vac > 0:
            blocking.append("vacancy_loss must be stored as a negative number")
        net_rent = (gpr + vac) if (gpr is not None and vac is not None) else None
        egi = net_rent
        opex = (egi * opex_ratio) if (egi is not None and opex_ratio is not None) else None
        oi = None
        noi = (egi - opex) if (egi is not None and opex is not None) else None

    elif scenario == 3:
        in_place = _num(ctx.get("in_place_rent"))
        occ = _num(ctx.get("occupancy"))
        opex_ratio = _num(bench.get("opex_ratio"))
        if units is None or in_place is None or occ is None:
            blocking.append("scenario 3 requires units, in_place_rent, occupancy")
        gpr = units * in_place * 12 if (units is not None and in_place is not None) else None
        vac = -(gpr * (1 - occ)) if (gpr is not None and occ is not None) else None
        net_rent = (gpr + vac) if (gpr is not None and vac is not None) else None
        egi = net_rent
        if opex_ratio is None:
            blocking.append("scenario 3 requires benchmarks.opex_ratio")
        opex = (egi * opex_ratio) if (egi is not None and opex_ratio is not None) else None
        oi = None
        noi = (egi - opex) if (egi is not None and opex is not None) else None

    else:  # scenario 4
        comp_rent = _num(rent_comps.get("comp_rent_per_unit_month"))
        vac_rate = _num(bench.get("vacancy_rate"))
        opex_ratio = _num(bench.get("opex_ratio"))
        if units is None or comp_rent is None:
            blocking.append("scenario 4 requires units and comp_rent_per_unit_month")
        if vac_rate is None:
            blocking.append("scenario 4 requires benchmarks.vacancy_rate")
        if opex_ratio is None:
            blocking.append("scenario 4 requires benchmarks.opex_ratio")
        gpr = units * comp_rent * 12 if (units is not None and comp_rent is not None) else None
        vac = -(gpr * vac_rate) if (gpr is not None and vac_rate is not None) else None
        net_rent = (gpr + vac) if (gpr is not None and vac is not None) else None
        egi = net_rent
        opex = (egi * opex_ratio) if (egi is not None and opex_ratio is not None) else None
        oi = None
        noi = (egi - opex) if (egi is not None and opex is not None) else None

    # Common arithmetic-plausibility checks (scenarios 2-4 derive opex/noi)
    if not blocking:
        if scenario in (2, 3, 4) and egi is not None and opex is not None and opex > egi:
            blocking.append("computed OpEx exceeds EGI — implausible inputs")
        if noi is not None and noi < 0 and scenario != 1:
            blocking.append("computed NOI is negative from arithmetic")

    if blocking:
        return {"scenario": scenario}, blocking

    vacancy_rate = abs(vac) / gpr if (vac is not None and gpr) else None
    opex_ratio_out = (opex / egi) if (opex is not None and egi) else None

    statement = {
        "scenario": scenario,
        "gpr": _round_money(gpr),
        "vacancy_loss": _round_money(vac),
        "net_rent": _round_money(net_rent),
        "other_income": _round_money(oi) if other_income_present else None,
        "other_income_present": other_income_present,
        "egi": _round_money(egi),
        "opex": _round_money(opex),
        "noi": _round_money(noi),
        "vacancy_rate": _round_pct(vacancy_rate),
        "opex_ratio": _round_pct(opex_ratio_out),
        # in-place per-unit monthly rent retained for the value-add GPR ramp
        "_in_place_rent": _num(ctx.get("in_place_rent")),
        # raw (unrounded) values retained for downstream projection math
        "_raw": {"gpr": gpr, "vacancy_loss": vac, "net_rent": net_rent,
                 "other_income": oi if other_income_present else 0.0,
                 "egi": egi, "opex": opex, "noi": noi,
                 "vacancy_rate": vacancy_rate},
    }
    return statement, []


def base_year_flags(statement):
    """Advisory (non-blocking) data-quality flags on the base year."""
    flags = []
    opex_ratio = statement.get("opex_ratio")
    if opex_ratio is not None and not (
            PARAMS["OPEX_RATIO_MIN"] <= opex_ratio <= PARAMS["OPEX_RATIO_MAX"]):
        flags.append(f"opex_ratio {opex_ratio:.3f} outside "
                     f"{PARAMS['OPEX_RATIO_MIN']}-{PARAMS['OPEX_RATIO_MAX']} band")
    if statement.get("other_income_present"):
        nr = statement["_raw"].get("net_rent")
        oi = statement["_raw"].get("other_income")
        if nr and oi is not None:
            share = oi / nr
            if not (PARAMS["OTHER_INCOME_MIN_SHARE"] <= share <= PARAMS["OTHER_INCOME_MAX_SHARE"]):
                flags.append(f"other_income {share:.3f} of net rent outside "
                             f"{PARAMS['OTHER_INCOME_MIN_SHARE']}-{PARAMS['OTHER_INCOME_MAX_SHARE']} band")
    return flags


# --------------------------------------------------------------------------
# Stabilization status
# --------------------------------------------------------------------------
def resolve_stabilization(req):
    """Return (status, source)."""
    ctx = req.get("property_context") or {}
    override = ctx.get("stabilization_status_override")
    if override:
        return override, "user_override"

    occ = _num(ctx.get("occupancy"))
    in_place = _num(ctx.get("in_place_rent"))
    market = _num(ctx.get("market_rent"))
    recent = bool(ctx.get("recent_delivery_flag"))
    reposition = bool(ctx.get("repositioning_flag"))

    # stabilized
    if (occ is not None and occ >= PARAMS["STABILIZED_OCC_MIN"]
            and in_place is not None and market):
        if abs(in_place - market) / market <= PARAMS["STABILIZED_RENT_GAP"]:
            return "stabilized", "inferred"
    # lease-up
    if (occ is not None and occ < PARAMS["LEASEUP_OCC_MAX"] and recent):
        return "lease-up", "inferred"
    # value-add
    if (in_place is not None and market
            and (market - in_place) / market > PARAMS["VALUEADD_RENT_GAP"]
            and reposition):
        return "value-add", "inferred"

    # scenario-4 recent-delivery default
    fin = req.get("mf_property_financials") or {}
    rent_comps = req.get("rent_comps") or {}
    if resolve_scenario(fin, ctx, rent_comps) == 4 and recent:
        return "lease-up", "default_scenario4_recent_delivery"

    return "unknown", "unresolved"


# --------------------------------------------------------------------------
# Projection
# --------------------------------------------------------------------------
def projection_assumptions(req, status):
    pin = req.get("projection_inputs") or {}

    def pick(key, default):
        v = _num(pin.get(key))
        return (v, "provided") if v is not None else (default, "default")

    rent_growth, rg_src = pick("rent_growth", PARAMS["DEFAULT_RENT_GROWTH"])
    exp_growth, eg_src = pick("expense_growth", PARAMS["DEFAULT_EXPENSE_GROWTH"])
    oi_growth, oig_src = pick("other_income_growth", PARAMS["DEFAULT_OTHER_INCOME_GROWTH"])
    target_vac, tv_src = pick("target_vacancy", PARAMS["DEFAULT_TARGET_VACANCY"])
    horizon, h_src = pick("horizon_years", PARAMS["DEFAULT_HORIZON_YEARS"])
    horizon = int(horizon)

    default_months = (PARAMS["DEFAULT_MONTHS_TO_STAB_VALUEADD"] if status == "value-add"
                      else PARAMS["DEFAULT_MONTHS_TO_STAB_LEASEUP"])
    months_to_stab, mts_src = pick("months_to_stabilization", default_months)

    reno_capex = _num(pin.get("renovation_capex"))
    post_reno_rent = _num(pin.get("post_renovation_rent"))

    return {
        "rent_growth": rent_growth, "expense_growth": exp_growth,
        "other_income_growth": oi_growth, "target_vacancy": target_vac,
        "horizon_years": horizon, "months_to_stabilization": months_to_stab,
        "renovation_capex": reno_capex, "post_renovation_rent": post_reno_rent,
        "sources": {"rent_growth": rg_src, "expense_growth": eg_src,
                    "other_income_growth": oig_src, "target_vacancy": tv_src,
                    "horizon_years": h_src, "months_to_stabilization": mts_src},
    }


def run_projection(base, status, assume, market_rent=None):
    """
    Produce a year-by-year projection. Returns (rows, flags).
    Each row: year, gpr, vacancy_loss, net_rent, other_income, egi, opex, noi,
              vacancy_rate, renovation_capex.
    """
    raw = base["_raw"]
    rows = []
    flags = []

    base_gpr = raw["gpr"]
    base_vac_rate = raw["vacancy_rate"] if raw["vacancy_rate"] is not None else 0.0
    base_oi = raw["other_income"] if base["other_income_present"] else 0.0
    base_opex = raw["opex"]
    oi_present = base["other_income_present"]

    rg = assume["rent_growth"]
    eg = assume["expense_growth"]
    oig = assume["other_income_growth"]
    target_vac = assume["target_vacancy"]
    horizon = assume["horizon_years"]
    months_to_stab = assume["months_to_stabilization"]
    stab_year_frac = months_to_stab / 12.0

    # Value-add: derive the post-renovation GPR target by scaling base GPR by
    # the post-reno / in-place rent ratio (works at the GPR level without needing
    # a unit count). Ramp linearly from base to that target over the renovation
    # period, then compound at rent_growth. Capped at market_rent-implied GPR.
    post_reno_gpr = None
    if status == "value-add" and assume["post_renovation_rent"] and base_gpr:
        ip = base.get("_in_place_rent")
        if ip:
            post_reno_gpr = base_gpr * (assume["post_renovation_rent"] / ip)
        else:
            post_reno_gpr = base_gpr  # no per-unit basis; hold base

    for y in range(1, horizon + 1):
        # GPR path
        if status == "value-add" and post_reno_gpr is not None:
            if y <= stab_year_frac:
                frac = min(1.0, y / max(stab_year_frac, 1e-9))
                gpr = base_gpr + (post_reno_gpr - base_gpr) * frac
            else:
                extra_years = y - stab_year_frac
                gpr = post_reno_gpr * ((1 + rg) ** max(0.0, extra_years))
        else:
            gpr = base_gpr * ((1 + rg) ** y) if base_gpr is not None else None

        # Vacancy
        if status == "stabilized":
            vac_rate = base_vac_rate
        elif status == "lease-up":
            # ramp from base to target over months_to_stab
            if y <= stab_year_frac:
                frac = y / max(stab_year_frac, 1e-9)
                vac_rate = base_vac_rate + (target_vac - base_vac_rate) * min(1.0, frac)
            else:
                vac_rate = target_vac
        elif status == "value-add":
            # hold base vacancy during renovation, drop to target after
            vac_rate = base_vac_rate if y < stab_year_frac else target_vac
        else:
            vac_rate = base_vac_rate

        vac = -(gpr * vac_rate) if gpr is not None else None
        net_rent = (gpr + vac) if (gpr is not None and vac is not None) else None
        oi = (base_oi * ((1 + oig) ** y)) if oi_present else 0.0
        egi = (net_rent + oi) if net_rent is not None else None
        opex = base_opex * ((1 + eg) ** y) if base_opex is not None else None
        noi = (egi - opex) if (egi is not None and opex is not None) else None
        reno = assume["renovation_capex"] if (status == "value-add" and y == 1
                                              and assume["renovation_capex"]) else 0.0

        # value-add ceiling: stabilized rent should not exceed market
        if (status == "value-add" and market_rent and gpr is not None
                and base["_raw"].get("gpr")):
            pass  # ceiling enforced via post_renovation_rent input upstream

        rows.append({
            "year": y,
            "gpr": _round_money(gpr),
            "vacancy_loss": _round_money(vac),
            "net_rent": _round_money(net_rent),
            "other_income": _round_money(oi) if oi_present else None,
            "egi": _round_money(egi),
            "opex": _round_money(opex),
            "noi": _round_money(noi),
            "vacancy_rate": _round_pct(vac_rate),
            "renovation_capex": _round_money(reno) if reno else None,
            "_raw_noi": noi, "_raw_egi": egi,
        })

    # validation: EGI - OpEx = NOI each year; opex ratio band
    for r in rows:
        if r["_raw_egi"] is not None and r["opex"] is not None and r["_raw_noi"] is not None:
            if abs((r["_raw_egi"] - r["opex"]) - r["_raw_noi"]) > max(1.0, 0.005 * abs(r["_raw_noi"])):
                flags.append(f"year {r['year']}: EGI - OpEx != NOI")
        if r["_raw_egi"]:
            ratio = r["opex"] / r["_raw_egi"] if r["opex"] is not None else None
            if ratio is not None and not (PARAMS["OPEX_RATIO_MIN"] <= ratio <= PARAMS["OPEX_RATIO_MAX"]):
                flags.append(f"year {r['year']}: opex ratio {ratio:.3f} outside band")
    return rows, flags


def stabilization_year_noi(rows, status, assume):
    """NOI used for capitalization: year 1 if stabilized, else stabilization year."""
    if not rows:
        return None
    if status == "stabilized":
        return rows[0]["_raw_noi"]
    stab_year = max(1, math.ceil(assume["months_to_stabilization"] / 12.0))
    idx = min(stab_year, len(rows)) - 1
    return rows[idx]["_raw_noi"]


# --------------------------------------------------------------------------
# Returns / valuation math
# --------------------------------------------------------------------------
def _irr(cashflows, lo=-0.99, hi=2.0, tol=1e-7, maxit=200):
    """Bisection IRR. cashflows[0] is the t0 (typically negative) flow."""
    def npv(r):
        return sum(cf / ((1 + r) ** t) for t, cf in enumerate(cashflows))
    f_lo, f_hi = npv(lo), npv(hi)
    if f_lo * f_hi > 0:
        return None  # no sign change in bracket -> IRR not bracketed
    for _ in range(maxit):
        mid = (lo + hi) / 2
        f_mid = npv(mid)
        if abs(f_mid) < tol:
            return mid
        if f_lo * f_mid < 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2


def _amort_payment(principal, annual_rate, amort_years):
    r = annual_rate / 12.0
    n = amort_years * 12
    if r == 0:
        return principal / n
    return principal * r / (1 - (1 + r) ** (-n))


def _balance_after(principal, annual_rate, amort_years, years_elapsed):
    r = annual_rate / 12.0
    n = amort_years * 12
    k = int(round(years_elapsed * 12))
    if r == 0:
        return principal * (1 - k / n)
    return principal * ((1 + r) ** n - (1 + r) ** k) / ((1 + r) ** n - 1)


def compute_direct_cap(req, base, rows, status, assume):
    val = req.get("valuation_inputs") or {}
    going_in = _num(val.get("going_in_cap"))
    price = _num(val.get("purchase_price"))
    cap_noi = stabilization_year_noi(rows, status, assume) if rows else base["_raw"]["noi"]
    if cap_noi is None or not going_in:
        return {"error": "direct_cap requires going_in_cap and a capitalizable NOI"}
    value = cap_noi / going_in
    out = {
        "capitalized_noi": _round_money(cap_noi),
        "going_in_cap": going_in,
        "value": _round_money(value),
    }
    if price:
        out["implied_cap_rate"] = _round_pct(cap_noi / price)
        out["implied_cap_basis"] = "capitalized_noi / purchase_price"
    return out


def compute_dcf(req, base, rows, status, assume):
    val = req.get("valuation_inputs") or {}
    exit_cap = _num(val.get("exit_cap"))
    disc = _num(val.get("discount_rate"))
    sale_costs = _num(val.get("sale_costs_pct")) or 0.0
    price = _num(val.get("purchase_price"))
    if not exit_cap or not disc:
        return {"error": "dcf requires exit_cap and discount_rate"}
    capex_by_year = {1: (assume["renovation_capex"] or 0.0)} if status == "value-add" else {}
    unlevered = []
    for r in rows:
        cf = (r["_raw_noi"] or 0.0) - capex_by_year.get(r["year"], 0.0)
        unlevered.append(cf)
    # terminal value from year N+1 NOI
    last_noi = rows[-1]["_raw_noi"] or 0.0
    noi_np1 = last_noi * (1 + assume["rent_growth"])
    terminal = (noi_np1 / exit_cap) * (1 - sale_costs)
    npv = 0.0
    for t, cf in enumerate(unlevered, start=1):
        npv += cf / ((1 + disc) ** t)
    npv += terminal / ((1 + disc) ** len(rows))
    out = {
        "unlevered_cash_flows": [_round_money(c) for c in unlevered],
        "terminal_value": _round_money(terminal),
        "npv": _round_money(npv),
        "discount_rate": disc,
        "exit_cap": exit_cap,
    }
    if price:
        irr = _irr([-price] + unlevered[:-1] + [unlevered[-1] + terminal])
        out["unlevered_irr"] = _round_pct(irr) if irr is not None else None
    return out


def compute_levered(req, base, rows, status, assume):
    val = req.get("valuation_inputs") or {}
    stack = req.get("capital_stack") or {}
    price = _num(val.get("purchase_price"))
    exit_cap = _num(val.get("exit_cap"))
    sale_costs = _num(val.get("sale_costs_pct")) or 0.0
    ltv = _num(stack.get("ltv"))
    loan_amount = _num(stack.get("loan_amount"))
    rate = _num(stack.get("interest_rate"))
    amort = _num(stack.get("amortization_years")) or 30
    if price is None or rate is None or (ltv is None and loan_amount is None) or not exit_cap:
        return {"error": "levered_returns requires purchase_price, interest_rate, "
                         "ltv or loan_amount, and exit_cap"}
    loan = loan_amount if loan_amount is not None else ltv * price
    initial_equity = price - loan
    annual_ds = _amort_payment(loan, rate, int(amort)) * 12.0
    horizon = assume["horizon_years"]
    capex_by_year = {1: (assume["renovation_capex"] or 0.0)} if status == "value-add" else {}

    levered_cfs = []
    peak_equity = initial_equity
    post_closing_contributions = False
    for r in rows:
        unlev = (r["_raw_noi"] or 0.0)
        capex = capex_by_year.get(r["year"], 0.0)
        # equity-funded capex draw modeled as additional equity if it pushes CF negative
        op_after_ds = unlev - annual_ds
        net_lev = op_after_ds - capex
        if capex > 0:
            # treat capex as an equity draw in its year (post-closing contribution)
            post_closing_contributions = True
            peak_equity += capex
            net_lev = op_after_ds  # the draw is a separate equity contribution
            levered_cfs.append(net_lev)
        else:
            levered_cfs.append(net_lev)

    # exit
    last_noi = rows[-1]["_raw_noi"] or 0.0
    noi_np1 = last_noi * (1 + assume["rent_growth"])
    sale_price = noi_np1 / exit_cap
    balance = _balance_after(loan, rate, int(amort), horizon)
    exit_equity = sale_price * (1 - sale_costs) - balance

    # build IRR stream: t0 = -initial_equity; capex draws are negative in-year
    stream = [-initial_equity]
    for i, r in enumerate(rows):
        cf = levered_cfs[i]
        draw = capex_by_year.get(r["year"], 0.0)
        if draw > 0:
            cf = cf - draw  # equity contribution shows as negative CF in its year
        if i == len(rows) - 1:
            cf = cf + exit_equity
        stream.append(cf)

    irr = _irr(stream)
    total_distributions = sum(max(0.0, cf) for cf in stream[1:])
    equity_basis = peak_equity if post_closing_contributions else initial_equity
    equity_multiple = total_distributions / equity_basis if equity_basis else None

    coc = []
    denom = peak_equity if post_closing_contributions else initial_equity
    for i, r in enumerate(rows):
        coc.append(_round_pct((levered_cfs[i]) / denom) if denom else None)

    return {
        "loan_proceeds": _round_money(loan),
        "initial_equity": _round_money(initial_equity),
        "peak_equity": _round_money(peak_equity),
        "annual_debt_service": _round_money(annual_ds),
        "loan_balance_at_exit": _round_money(balance),
        "sale_price": _round_money(sale_price),
        "exit_equity_cf": _round_money(exit_equity),
        "levered_cash_flows": [_round_money(c) for c in levered_cfs],
        "levered_irr": _round_pct(irr) if irr is not None else None,
        "equity_multiple": round(equity_multiple, 2) if equity_multiple is not None else None,
        "equity_multiple_basis": "peak_equity" if post_closing_contributions else "initial_equity",
        "cash_on_cash": coc,
        "cash_on_cash_denominator": "peak_equity" if post_closing_contributions else "initial_equity",
    }


def compute_yoc(req, base, rows, status, assume):
    dev = req.get("development_inputs") or {}
    val = req.get("valuation_inputs") or {}
    tdc = _num(dev.get("total_development_cost"))
    going_in = _num(val.get("going_in_cap"))
    if not tdc:
        return {"error": "yield_on_cost requires development_inputs.total_development_cost"}
    year1_noi = rows[0]["_raw_noi"] if rows else base["_raw"]["noi"]
    stab_noi = stabilization_year_noi(rows, status, assume) if rows else base["_raw"]["noi"]
    untrended = year1_noi / tdc if year1_noi is not None else None
    trended = stab_noi / tdc if stab_noi is not None else None
    spread_bps = ((trended - going_in) * 10000) if (trended is not None and going_in) else None
    return {
        "total_development_cost": _round_money(tdc),
        "untrended_yoc": _round_pct(untrended),
        "trended_yoc": _round_pct(trended),
        "going_in_cap": going_in,
        "spread_to_market_cap_bps": round(spread_bps, 1) if spread_bps is not None else None,
    }


# --------------------------------------------------------------------------
# AUTHORITY ROLE — full statement per mode (binding on the no-template path)
# --------------------------------------------------------------------------
def run_authority(req):
    mode = req.get("mode")
    if mode not in VALID_MODES:
        return {"status": "error", "role": "authority",
                "error": f"mode omitted or invalid: {mode!r}"}

    base, blocking = build_base_year(req)
    if blocking:
        return {"status": "error", "role": "authority", "mode": mode,
                "validation": {"blocking_failures": blocking},
                "computed_in_sandbox": True}

    dq_flags = base_year_flags(base)
    status_stab, status_src = resolve_stabilization(req)

    # base_year_only short-circuit
    if mode == "base_year_only":
        resolution = None
        if status_stab == "unknown":
            resolution = {"reason": "stabilization status could not be inferred; "
                                    "provide stabilization_status_override or occupancy/"
                                    "rent context", "defaulted_to": "unknown"}
        return _strip_raw({
            "status": "ok",
            "role": "authority",
            "mode": mode,
            "subject": (req.get("subject") or {}).get("label"),
            "stabilization_status": status_stab,
            "stabilization_source": status_src,
            "base_year": base,
            "projection": None,
            "valuation": None,
            "returns": None,
            "unknown_resolution": resolution,
            "validation": {"blocking_failures": [], "data_quality_flags": dq_flags},
            "confidence": _authority_confidence(base, status_stab, dq_flags, mode),
            "computed_in_sandbox": True,
            "narrative": None,
        })

    # modes beyond base_year_only need a resolved stabilization status to project
    if status_stab == "unknown":
        return _strip_raw({
            "status": "unknown",
            "role": "authority",
            "mode": mode,
            "stabilization_status": "unknown",
            "stabilization_source": status_src,
            "base_year": base,
            "projection": None,
            "valuation": None,
            "returns": None,
            "unknown_resolution": {
                "reason": "stabilization status unresolved; base year returned as "
                          "partial result, projection not run",
                "defaulted_to": "unknown"},
            "validation": {"blocking_failures": [], "data_quality_flags": dq_flags},
            "confidence": "low",
            "computed_in_sandbox": True,
            "narrative": None,
        })

    assume = projection_assumptions(req, status_stab)
    market_rent = _num((req.get("property_context") or {}).get("market_rent"))
    rows, proj_flags = run_projection(base, status_stab, assume, market_rent)
    dq_flags = dq_flags + proj_flags

    valuation = None
    returns = None
    if mode == "direct_cap":
        valuation = compute_direct_cap(req, base, rows, status_stab, assume)
    elif mode == "dcf":
        valuation = compute_dcf(req, base, rows, status_stab, assume)
    elif mode == "levered_returns":
        returns = compute_levered(req, base, rows, status_stab, assume)
    elif mode == "yield_on_cost":
        valuation = compute_yoc(req, base, rows, status_stab, assume)

    # surface mode-calc errors as blocking
    for blk in (valuation, returns):
        if isinstance(blk, dict) and blk.get("error"):
            return {"status": "error", "role": "authority", "mode": mode,
                    "validation": {"blocking_failures": [blk["error"]]},
                    "base_year": _strip_raw_obj(base),
                    "computed_in_sandbox": True}

    return _strip_raw({
        "status": "warning" if dq_flags else "ok",
        "role": "authority",
        "mode": mode,
        "subject": (req.get("subject") or {}).get("label"),
        "stabilization_status": status_stab,
        "stabilization_source": status_src,
        "base_year": base,
        "projection": {"assumptions": assume, "years": rows} if mode != "base_year_only" else None,
        "valuation": valuation,
        "returns": returns,
        "validation": {"blocking_failures": [], "data_quality_flags": dq_flags},
        "confidence": _authority_confidence(base, status_stab, dq_flags, mode),
        "computed_in_sandbox": True,
        "narrative": None,
    })


def _authority_confidence(base, status, dq_flags, mode):
    scenario = base.get("scenario")
    if scenario == 1:
        c = "high"
    elif scenario in (2, 3):
        c = "medium"
    else:
        c = "low"
    # Unknown stabilization status only undermines projection-class modes; a
    # base-year-only statement stands on the reported figures alone.
    if status == "unknown" and mode != "base_year_only":
        c = "low"
    if dq_flags and c == "high":
        c = "medium"
    return c


def _strip_raw_obj(base):
    b = dict(base)
    b.pop("_raw", None)
    b.pop("_in_place_rent", None)
    return b


def _strip_raw(resp):
    """Remove internal _raw helpers before returning."""
    by = resp.get("base_year")
    if isinstance(by, dict):
        by.pop("_raw", None)
        by.pop("_in_place_rent", None)
    proj = resp.get("projection")
    if isinstance(proj, dict):
        for r in proj.get("years", []) or []:
            r.pop("_raw_noi", None)
            r.pop("_raw_egi", None)
    return resp


# --------------------------------------------------------------------------
# CROSS-CHECK ROLE — bounded advisory comparison vs. the workbook (NEVER binding)
# --------------------------------------------------------------------------
def run_cross_check(req):
    """
    The workbook (realai-pro-forma) is the authority. This role ONLY recomputes
    headline EGI / NOI / implied cap and compares them to the workbook's
    headline outputs. It returns advisory variances and a single review flag.
    It is structurally incapable of returning a projection, DCF, or levered
    returns — that guarantee is what makes a cross-check unable to override the
    workbook or be mistaken for a binding result.
    """
    wb = req.get("workbook_outputs") or {}
    if not wb:
        return {"status": "error", "role": "cross_check",
                "error": "cross_check requires workbook_outputs (the binding "
                         "realai-pro-forma headline NOI/EGI/cap to compare against)"}

    base, blocking = build_base_year(req)
    if blocking:
        # Cannot form an independent estimate; report inability WITHOUT touching
        # the workbook. The workbook remains binding regardless.
        return {
            "status": "warning",
            "role": "cross_check",
            "workbook_is_authority": True,
            "binding": False,
            "advisory_only": True,
            "independent_estimate_available": False,
            "reason": "independent base-year estimate could not be formed: "
                      + "; ".join(blocking),
            "checks": [],
            "review_recommended": False,
            "computed_in_sandbox": True,
            "narrative": None,
        }

    tol = req.get("tolerance") or {}
    noi_tol = _num(tol.get("noi_pct")) or PARAMS["XCHECK_NOI_PCT"]
    egi_tol = _num(tol.get("egi_pct")) or PARAMS["XCHECK_EGI_PCT"]
    cap_tol = _num(tol.get("cap_bps")) or PARAMS["XCHECK_CAP_BPS"]

    indep_noi = base["_raw"]["noi"]
    indep_egi = base["_raw"]["egi"]

    price = _num((req.get("valuation_inputs") or {}).get("purchase_price"))
    indep_cap = (indep_noi / price) if (indep_noi is not None and price) else None

    checks = []
    review = False

    def pct_check(name, wb_val, indep_val, tol_pct):
        nonlocal review
        wb_v = _num(wb_val)
        if wb_v is None or indep_val is None or indep_val == 0:
            return
        variance = (wb_v - indep_val) / abs(indep_val)
        within = abs(variance) <= tol_pct
        if not within:
            review = True
        checks.append({
            "metric": name,
            "workbook_value": _round_money(wb_v),
            "independent_value": _round_money(indep_val),
            "variance_pct": _round_pct(variance),
            "tolerance_pct": tol_pct,
            "within_tolerance": within,
        })

    pct_check("egi", wb.get("egi"), indep_egi, egi_tol)
    pct_check("noi", wb.get("noi"), indep_noi, noi_tol)

    wb_cap = _num(wb.get("cap_rate"))
    if wb_cap is not None and indep_cap is not None:
        bps = (wb_cap - indep_cap) * 10000.0
        within = abs(bps) <= cap_tol
        if not within:
            review = True
        checks.append({
            "metric": "cap_rate",
            "workbook_value": _round_pct(wb_cap),
            "independent_value": _round_pct(indep_cap),
            "variance_bps": round(bps, 1),
            "tolerance_bps": cap_tol,
            "within_tolerance": within,
        })

    return {
        "status": "warning" if review else "ok",
        "role": "cross_check",
        "workbook_is_authority": True,
        "binding": False,
        "advisory_only": True,
        "independent_estimate_available": True,
        "scenario_used": base.get("scenario"),
        "checks": checks,
        "review_recommended": review,
        "note": ("The workbook outputs are binding. These checks are an "
                 "independent recompute of headline EGI/NOI/cap only — they do "
                 "not recompute returns, projection, or sensitivity, and they "
                 "never override the workbook. Surface a divergence as a "
                 "diligence note; do not change the workbook figures."),
        "computed_in_sandbox": True,
        "narrative": None,
    }


# --------------------------------------------------------------------------
# Main entry
# --------------------------------------------------------------------------
def run(request):
    role = request.get("role")
    if role not in VALID_ROLES:
        return {"status": "error",
                "error": f"role omitted or invalid: {role!r} "
                         f"(expected one of {sorted(VALID_ROLES)})"}
    if role == "cross_check":
        return run_cross_check(request)
    return run_authority(request)


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
