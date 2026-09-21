#!/usr/bin/env python3
"""Multifamily operating statement & projection engine.

Pure compute. Reads a request JSON on stdin, writes a response JSON on stdout.
No network, no tool calls, no state between invocations. Contract is defined in
../references/schema.md and ../references/methodology.md.

This is a faithful reference implementation of the sub-agent spec. If the RealAI
application already ships its own engine, replace this file with it and keep the
same stdin-JSON / stdout-JSON contract so SKILL.md stays valid.
"""
import json
import sys

MODES = {"base_year_only", "projection", "direct_cap", "dcf",
         "levered_returns", "yield_on_cost"}
DEFAULTS = {"rent_growth": 0.03, "expense_growth": 0.025, "other_income_growth": 0.03,
            "target_vacancy": 0.06, "horizon_years": 5}


def g(d, *path, default=None):
    for k in path:
        if not isinstance(d, dict) or d.get(k) is None:
            return default
        d = d[k]
    return d


def err(failures):
    return {"status": "error",
            "validation": {"checks_passed": False, "blocking_failures": failures,
                           "data_quality_flags": []}}


# ---------------------------------------------------------------- scenario ----
def resolve_scenario(fin, ctx, comps):
    have = lambda k: fin.get(k) is not None
    if all(have(k) for k in ("gpr", "vacancy_loss", "other_income", "egi", "opex", "noi")):
        return 1
    if have("gpr") and have("vacancy_loss") and have("opex_ratio") \
            and fin.get("opex") is None and fin.get("other_income") is None:
        return 2
    if not any(have(k) for k in fin) and ctx.get("in_place_rent") is not None \
            and ctx.get("occupancy") is not None:
        return 3
    if not any(have(k) for k in fin) and ctx.get("in_place_rent") is None \
            and g(comps, "comp_rent_per_unit_month") is not None:
        return 4
    return None


def build_base(scenario, fin, ctx, bench, comps):
    """Return (statement dict, other_income_present, blocking list)."""
    blocking = []
    units = ctx.get("units")
    if scenario == 1:
        s = {"gpr": fin["gpr"], "vacancy_loss": fin["vacancy_loss"],
             "net_rent": fin["gpr"] + fin["vacancy_loss"],
             "other_income": fin["other_income"], "egi": fin["egi"],
             "opex": fin["opex"], "noi": fin["noi"]}
        oi_present = True
        if abs(fin["egi"] - fin["opex"] - fin["noi"]) > 1:
            blocking.append("scenario 1 identity failed: EGI - OpEx != NOI")
    else:
        if scenario == 2:
            gpr, vac = fin["gpr"], fin["vacancy_loss"]
            opex_ratio = fin["opex_ratio"]
        elif scenario == 3:
            gpr = units * ctx["in_place_rent"] * 12
            vac = -(gpr * (1 - ctx["occupancy"]))
            opex_ratio = g(bench, "opex_ratio")
        else:  # 4
            gpr = units * comps["comp_rent_per_unit_month"] * 12
            vac = -(gpr * g(bench, "vacancy_rate", default=0))
            opex_ratio = g(bench, "opex_ratio")
        if opex_ratio is None:
            blocking.append(f"scenario {scenario} requires an opex_ratio benchmark")
            return None, False, blocking
        net_rent = gpr + vac
        egi = net_rent
        opex = egi * opex_ratio
        s = {"gpr": gpr, "vacancy_loss": vac, "net_rent": net_rent,
             "other_income": 0, "egi": egi, "opex": opex, "noi": egi - opex}
        oi_present = False
        if opex > egi:
            blocking.append(f"scenario {scenario}: OpEx exceeds EGI")

    if s["vacancy_loss"] > 0:
        blocking.append("vacancy_loss must be stored as a negative number")
    if s["noi"] < 0:
        blocking.append("computed NOI is negative")
    s["vacancy_rate"] = abs(s["vacancy_loss"]) / s["gpr"] if s["gpr"] else 0
    s["opex_ratio"] = s["opex"] / s["egi"] if s["egi"] else 0
    return s, oi_present, blocking


def base_flags(scenario, s, oi_present, status):
    flags = []
    if not (0.35 <= s["opex_ratio"] <= 0.55):
        flags.append(f"OpEx ratio {s['opex_ratio']:.1%} outside 35-55% of EGI")
    if scenario == 1 and oi_present and s["net_rent"]:
        oi_pct = s["other_income"] / s["net_rent"]
        if not (0.02 <= oi_pct <= 0.12):
            flags.append(f"Other Income {oi_pct:.1%} outside 2-12% of Net Rent")
    hi = 0.08 if status == "stabilized" else 0.30
    if not (0.02 <= s["vacancy_rate"] <= hi):
        flags.append(f"vacancy rate {s['vacancy_rate']:.1%} unusual for {status}")
    if scenario == 1 and abs(s["gpr"] + s["vacancy_loss"] + s["other_income"] - s["egi"]) > 1:
        flags.append("scenario 1 revenue lines do not foot to EGI")
    return flags


# ------------------------------------------------------------ stabilization ----
def resolve_status(ctx, scenario):
    ov = ctx.get("stabilization_status_override")
    if ov:
        return ov, "user_override", "caller-provided override"
    occ, ip, mkt = ctx.get("occupancy"), ctx.get("in_place_rent"), ctx.get("market_rent")
    if occ is not None and ip is not None and mkt:
        gap = abs(ip - mkt) / mkt
        if occ >= 0.90 and gap <= 0.10:
            return "stabilized", "inferred", f"occupancy {occ:.0%}, rent within {gap:.0%} of market"
        if (mkt - ip) / mkt > 0.10 and ctx.get("repositioning_flag"):
            return "value-add", "inferred", "in-place rent >10% below market with repositioning flagged"
    if occ is not None and occ < 0.85 and ctx.get("recent_delivery_flag"):
        return "lease-up", "inferred", f"occupancy {occ:.0%} with recent delivery"
    if scenario == 4 and ctx.get("recent_delivery_flag"):
        return "lease-up", "default", "scenario 4 recent delivery default"
    return "unknown", "unresolved", "insufficient signals to infer status"


# ------------------------------------------------------------------ project ----
def project(base, oi_present, status, pin, ctx):
    """Return (projection dict, data_quality_flags list)."""
    hy = int(g(pin, "horizon_years", default=DEFAULTS["horizon_years"]))
    rg = g(pin, "rent_growth", default=DEFAULTS["rent_growth"])
    eg = g(pin, "expense_growth", default=DEFAULTS["expense_growth"])
    oig = g(pin, "other_income_growth", default=DEFAULTS["other_income_growth"])
    tv = g(pin, "target_vacancy", default=DEFAULTS["target_vacancy"])
    mts = g(pin, "months_to_stabilization",
            default=18 if status == "lease-up" else 24)
    base_vac_rate = base["vacancy_rate"]
    years = []
    flags = []

    if status == "value-add":
        # Caller has already validated units/in_place_rent/post_renovation_rent
        # are present (see main()) before this branch is reached.
        units = ctx["units"]
        ip = ctx["in_place_rent"]
        pr = g(pin, "post_renovation_rent")
        cap_total = g(pin, "renovation_capex", default=0) or 0
        market_rent = ctx.get("market_rent")
        prev_frac = 0.0
        for yr in range(1, hy + 1):
            frac = min(1.0, (yr * 12) / mts) if mts else 1.0
            if frac < 1.0:
                # Ramping: in-place rent moves linearly toward post-reno rent.
                current_rent = ip + (pr - ip) * frac
                vr = base_vac_rate
            else:
                # Renovation complete: rent grows off post-reno rent from here.
                years_past_complete = yr - (mts / 12 if mts else 0)
                current_rent = pr * (1 + rg) ** max(years_past_complete, 0)
                vr = tv
            capex = cap_total * (frac - prev_frac)
            prev_frac = frac
            if market_rent and current_rent > market_rent:
                flags.append(f"year {yr} value-add rent {current_rent:.0f} "
                             f"exceeds market_rent {market_rent:.0f}")
            gpr = units * current_rent * 12
            vac = -(gpr * vr)
            net_rent = gpr + vac
            oi = base["other_income"] * (1 + oig) ** yr if oi_present else 0
            egi = net_rent + oi
            opex = base["opex"] * (1 + eg) ** yr
            years.append({"year": yr, "gpr": gpr, "vacancy_loss": vac, "vacancy_rate": vr,
                          "net_rent": net_rent, "other_income": oi, "egi": egi,
                          "opex": opex, "noi": egi - opex, "capex": capex})
    else:
        for yr in range(1, hy + 1):
            gpr = base["gpr"] * (1 + rg) ** yr
            if status == "lease-up":
                frac = min(1.0, (yr * 12) / mts) if mts else 1.0
                vr = base_vac_rate + (tv - base_vac_rate) * frac
            else:  # stabilized
                vr = base_vac_rate
            vac = -(gpr * vr)
            net_rent = gpr + vac
            oi = base["other_income"] * (1 + oig) ** yr if oi_present else 0
            egi = net_rent + oi
            opex = base["opex"] * (1 + eg) ** yr
            years.append({"year": yr, "gpr": gpr, "vacancy_loss": vac, "vacancy_rate": vr,
                          "net_rent": net_rent, "other_income": oi, "egi": egi,
                          "opex": opex, "noi": egi - opex, "capex": 0})

    for y in years:
        ratio = y["opex"] / y["egi"] if y["egi"] else 0
        if not (0.35 <= ratio <= 0.55):
            flags.append(f"year {y['year']} OpEx ratio {ratio:.1%} outside 35-55% of EGI")
    if status in ("lease-up", "value-add") and years:
        ramp_years = (mts / 12) if mts else 0
        if hy >= ramp_years:
            final_vr = years[-1]["vacancy_rate"]
            if abs(final_vr - tv) > 1e-6:
                flags.append(f"vacancy rate {final_vr:.1%} has not converged to "
                             f"target {tv:.1%} by year {hy}")

    assumptions = {
        "rent_growth": {"value": rg, "source": "provided" if g(pin, "rent_growth") is not None else "default"},
        "expense_growth": {"value": eg, "source": "provided" if g(pin, "expense_growth") is not None else "default"},
        "target_vacancy": {"value": tv, "source": "provided" if g(pin, "target_vacancy") is not None else "default"},
    }
    return {"horizon_years": hy, "assumptions": assumptions, "years": years}, flags


# --------------------------------------------------------------------- math ----
def irr(cashflows, lo=-0.99, hi=5.0):
    def npv(r):
        return sum(cf / (1 + r) ** t for t, cf in enumerate(cashflows))
    if npv(lo) * npv(hi) > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        v = npv(mid)
        if abs(v) < 1:
            return mid
        if npv(lo) * v < 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def amort_payment(principal, rate, years):
    r = rate / 12
    n = years * 12
    if r == 0:
        return principal / n
    return principal * r / (1 - (1 + r) ** -n)


def balance_after(principal, rate, amort_years, elapsed_years):
    r = rate / 12
    pay = amort_payment(principal, rate, amort_years)
    bal = principal
    for _ in range(int(elapsed_years * 12)):
        bal = bal * (1 + r) - pay
    return bal


# ------------------------------------------------------------------- driver ----
def main():
    try:
        req = json.load(sys.stdin)
    except Exception as e:
        json.dump(err([f"invalid request JSON: {e}"]), sys.stdout)
        return

    mode = req.get("mode")
    if mode not in MODES:
        json.dump(err([f"unknown mode: {mode!r}"]), sys.stdout); return

    ctx = req.get("property_context") or {}
    fin = req.get("mf_property_financials") or {}
    bench = req.get("benchmarks") or {}
    comps = req.get("rent_comps") or {}

    scenario = resolve_scenario(fin, ctx, comps)
    if scenario is None:
        json.dump(err(["no scenario satisfied by mf_property_financials/property_context"]),
                  sys.stdout); return

    s, oi_present, blocking = build_base(scenario, fin, ctx, bench, comps)
    if blocking:
        json.dump(err(blocking), sys.stdout); return

    status, src, why = resolve_status(ctx, scenario)
    flags = base_flags(scenario, s, oi_present, status)

    base_year = {
        "scenario": scenario, "stabilization_status": status,
        "stabilization_status_source": src, "stabilization_status_explanation": why,
        "other_income_present": oi_present,
        "statement": {k: round(v, 4) if isinstance(v, float) else v for k, v in s.items()},
        "data_quality_flags": flags,
    }

    resp = {"status": "ok", "base_year": base_year,
            "validation": {"checks_passed": True, "blocking_failures": [],
                           "data_quality_flags": flags}}

    if mode == "base_year_only":
        if status == "unknown":
            resp["unknown_resolution"] = {
                "missing_fields": ["market_rent"] if not ctx.get("market_rent") else [],
                "reason": "stabilization status unresolved",
                "suggested_resolution": "provide market_rent or set stabilization_status_override, then re-invoke"}
        json.dump(resp, sys.stdout); return

    # projection modes require resolved status
    if status == "unknown":
        resp["status"] = "unknown"
        resp["unknown_resolution"] = {
            "missing_fields": ["market_rent"] if not ctx.get("market_rent") else [],
            "reason": "cannot run projection without resolved stabilization status",
            "suggested_resolution": "resolve status (pull market_rent or prompt user) and re-invoke with stabilization_status_override"}
        json.dump(resp, sys.stdout); return

    pin = req.get("projection_inputs") or {}

    if status == "value-add":
        missing = [name for name, val in (
            ("property_context.units", ctx.get("units")),
            ("property_context.in_place_rent", ctx.get("in_place_rent")),
            ("projection_inputs.post_renovation_rent", g(pin, "post_renovation_rent")),
        ) if val is None]
        if missing:
            resp["status"] = "error"
            resp["validation"]["blocking_failures"].append(
                f"value-add projection requires: {', '.join(missing)}")
            json.dump(resp, sys.stdout); return

    proj, projection_flags = project(s, oi_present, status, pin, ctx)
    resp["validation"]["data_quality_flags"] = flags + projection_flags
    for y in proj["years"]:
        for k, v in list(y.items()):
            if isinstance(v, float):
                y[k] = round(v, 4)
    resp["projection"] = proj

    val = req.get("valuation_inputs") or {}
    noi_year1 = proj["years"][0]["noi"]

    if mode == "direct_cap":
        cap = val.get("going_in_cap")
        price = val.get("purchase_price")
        value = noi_year1 / cap if cap else None
        dc = {"capitalized_noi_year": 1, "capitalized_noi": round(noi_year1, 2),
              "going_in_cap": cap, "value": round(value, 2) if value else None,
              "value_per_unit": round(value / ctx["units"], 2) if value and ctx.get("units") else None,
              "implied_cap_rate": round(noi_year1 / price, 4) if price else None,
              "implied_cap_basis": "purchase_price" if price else None}
        resp["valuation"] = {"direct_cap": dc}

    elif mode == "dcf":
        exit_cap = val.get("exit_cap"); dr = val.get("discount_rate")
        scp = val.get("sale_costs_pct", 0)
        price = val.get("purchase_price")
        noi_np1 = s["noi"] * (1 + g(pin, "rent_growth", default=DEFAULTS["rent_growth"])) ** (proj["horizon_years"] + 1)
        tv = (noi_np1 / exit_cap) * (1 - scp) if exit_cap else 0
        year_cfs = [y["noi"] - y["capex"] for y in proj["years"]]
        year_cfs[-1] += tv
        # "npv" is the DCF asset value (no cost basis netted out) — it feeds
        # value_per_unit, mirroring direct_cap's price-agnostic valuation.
        npv = sum(cf / (1 + dr) ** t for t, cf in enumerate([0] + year_cfs)) if dr else None
        # unlevered_irr needs a cost basis (an entry outlay) to solve for a
        # rate; without a purchase price there is nothing to enter against,
        # so it is null rather than a meaningless/undefined rate.
        unlevered_irr = irr([-price] + year_cfs) if price is not None else None
        resp["valuation"] = {"dcf": {
            "npv": round(npv, 2) if npv is not None else None,
            "unlevered_irr": round(unlevered_irr, 4) if unlevered_irr is not None else None,
            "value_per_unit": round(npv / ctx["units"], 2) if npv and ctx.get("units") else None,
            "terminal_value": round(tv, 2)}}

    elif mode == "levered_returns":
        cap_stack = req.get("capital_stack") or {}
        price = val.get("purchase_price")
        if price is None:
            resp["status"] = "error"
            resp["validation"]["blocking_failures"].append("levered_returns requires valuation_inputs.purchase_price")
            json.dump(resp, sys.stdout); return
        loan = cap_stack.get("loan_amount") or (cap_stack.get("ltv", 0) * price)
        rate = cap_stack.get("interest_rate", 0)
        amort = cap_stack.get("amortization_years", 30)
        init_eq = price - loan
        ds = amort_payment(loan, rate, amort) * 12
        exit_cap = val.get("exit_cap"); scp = val.get("sale_costs_pct", 0)
        hy = proj["horizon_years"]
        noi_np1 = s["noi"] * (1 + g(pin, "rent_growth", default=DEFAULTS["rent_growth"])) ** (hy + 1)
        sale_price = noi_np1 / exit_cap if exit_cap else 0
        bal_exit = balance_after(loan, rate, amort, hy)
        exit_eq = sale_price * (1 - scp) - bal_exit
        lev = [y["noi"] - y["capex"] - ds for y in proj["years"]]
        cfs = [-init_eq] + lev
        cfs[-1] += exit_eq
        total_dist = sum(lev) + exit_eq
        em = total_dist / init_eq if init_eq else None
        avg_coc = (sum(lev) / hy) / init_eq if init_eq else None
        exit_noi = proj["years"][-1]["noi"]
        resp["levered_returns"] = {
            "initial_equity": round(init_eq, 2), "peak_equity": round(init_eq, 2),
            "levered_irr": round(irr(cfs), 4) if irr(cfs) is not None else None,
            "equity_multiple": round(em, 3) if em else None,
            "equity_multiple_basis": "initial_equity",
            "average_cash_on_cash": round(avg_coc, 4) if avg_coc else None,
            "cash_on_cash_denominator": "initial_equity",
            "loan_balance_at_exit": round(bal_exit, 2),
            "exit_year_dscr": round(exit_noi / ds, 3) if ds else None}
        if bal_exit >= loan:
            resp["validation"]["data_quality_flags"].append("loan balance at exit not below original — check amortization inputs")

    elif mode == "yield_on_cost":
        dev = req.get("development_inputs") or {}
        tdc = dev.get("total_development_cost")
        if not tdc:
            resp["status"] = "error"
            resp["validation"]["blocking_failures"].append("yield_on_cost requires development_inputs.total_development_cost")
            json.dump(resp, sys.stdout); return
        untrended = noi_year1 / tdc
        trended = proj["years"][-1]["noi"] / tdc
        gic = val.get("going_in_cap")
        resp["yield_on_cost"] = {
            "untrended_yoc": round(untrended, 4), "trended_yoc": round(trended, 4),
            "spread_to_market_cap_bps": round((trended - gic) * 10000) if gic else None}

    json.dump(resp, sys.stdout)


if __name__ == "__main__":
    main()
