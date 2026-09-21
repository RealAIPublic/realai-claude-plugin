#!/usr/bin/env python3
"""
Validate derived claims from extracted workbook values.

Usage:
    python skills/xlsx/scripts/workbook_claims_check.py claims.json

Shape: every claim with an `expected` is executed automatically:
{
  "values": { "fee_old": 0.025, "fee_new": 0.03 },
  "facts":  [ ... ],
  "claims": [
    {
      "id": "claim_fee_spread_bps",
      "name": "fee_spread_bps",
      "expr": "(fee_new - fee_old) * 10000",
      "expected": 50,
      "tolerance": 0.01,
      "based_on_facts": ["fact_fee_old", "fact_fee_new"],
      "derivation": "(new fee - old fee) * 10,000"
    }
  ]
}

`tolerance` is an ABSOLUTE tolerance (math.isclose abs_tol, rel_tol=0).
Exit code is non-zero when any check fails or errors.
"""

import ast
import json
import math
import sys
from pathlib import Path


ALLOWED_BIN_OPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.Pow, ast.FloorDiv)
ALLOWED_UNARY_OPS = (ast.UAdd, ast.USub, ast.Not)
ALLOWED_BOOL_OPS = (ast.And, ast.Or)
ALLOWED_CMP_OPS = (
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
)
ALLOWED_FUNCS = {
    "abs": abs,
    "min": min,
    "max": max,
    "round": round,
}


def _eval_expr(node, env):
    if isinstance(node, ast.Expression):
        return _eval_expr(node.body, env)

    if isinstance(node, ast.Constant):
        return node.value

    if isinstance(node, ast.Name):
        if node.id not in env:
            raise ValueError(f"Unknown variable: {node.id}")
        return env[node.id]

    if isinstance(node, ast.BinOp):
        if not isinstance(node.op, ALLOWED_BIN_OPS):
            raise ValueError(f"Disallowed binary operator: {type(node.op).__name__}")
        left = _eval_expr(node.left, env)
        right = _eval_expr(node.right, env)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.Mod):
            return left % right
        if isinstance(node.op, ast.Pow):
            return left ** right
        if isinstance(node.op, ast.FloorDiv):
            return left // right

    if isinstance(node, ast.UnaryOp):
        if not isinstance(node.op, ALLOWED_UNARY_OPS):
            raise ValueError(f"Disallowed unary operator: {type(node.op).__name__}")
        value = _eval_expr(node.operand, env)
        if isinstance(node.op, ast.UAdd):
            return +value
        if isinstance(node.op, ast.USub):
            return -value
        if isinstance(node.op, ast.Not):
            return not value

    if isinstance(node, ast.BoolOp):
        if not isinstance(node.op, ALLOWED_BOOL_OPS):
            raise ValueError(f"Disallowed bool operator: {type(node.op).__name__}")
        values = [_eval_expr(v, env) for v in node.values]
        if isinstance(node.op, ast.And):
            return all(values)
        if isinstance(node.op, ast.Or):
            return any(values)

    if isinstance(node, ast.Compare):
        left = _eval_expr(node.left, env)
        for op, comparator in zip(node.ops, node.comparators):
            if not isinstance(op, ALLOWED_CMP_OPS):
                raise ValueError(f"Disallowed comparison operator: {type(op).__name__}")
            right = _eval_expr(comparator, env)
            ok = (
                (isinstance(op, ast.Eq) and left == right) or
                (isinstance(op, ast.NotEq) and left != right) or
                (isinstance(op, ast.Lt) and left < right) or
                (isinstance(op, ast.LtE) and left <= right) or
                (isinstance(op, ast.Gt) and left > right) or
                (isinstance(op, ast.GtE) and left >= right)
            )
            if not ok:
                return False
            left = right
        return True

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ValueError("Only direct function calls are allowed")
        fn_name = node.func.id
        if fn_name not in ALLOWED_FUNCS:
            raise ValueError(f"Disallowed function: {fn_name}")
        args = [_eval_expr(a, env) for a in node.args]
        return ALLOWED_FUNCS[fn_name](*args)

    raise ValueError(f"Unsupported expression node: {type(node).__name__}")


def safe_eval(expr, env):
    tree = ast.parse(expr, mode="eval")
    return _eval_expr(tree, env)


def numeric_close(actual, expected, tolerance):
    if tolerance is None:
        tolerance = 0.0
    return math.isclose(float(actual), float(expected), rel_tol=0.0, abs_tol=float(tolerance))


def derive_checks_from_claims(claims):
    derived = []
    if not isinstance(claims, list):
        return derived
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        if "expected" not in claim or not isinstance(claim.get("expr"), str):
            continue
        derived.append({
            "name": claim.get("name") or claim.get("id") or "unnamed_claim",
            "expr": claim.get("expr"),
            "expected": claim.get("expected"),
            "tolerance": claim.get("tolerance"),
        })
    return derived


def run_checks(payload):
    values = payload.get("values", {})
    claims = payload.get("claims")

    if not isinstance(values, dict):
        raise ValueError("'values' must be an object")

    checks = derive_checks_from_claims(claims)
    results = []
    passed = 0

    for i, chk in enumerate(checks):
        name = chk.get("name") or f"check_{i+1}"
        expr = chk.get("expr")
        expected = chk.get("expected")
        tolerance = chk.get("tolerance")

        if not isinstance(expr, str) or expr.strip() == "":
            results.append({
                "name": name,
                "status": "error",
                "error": "Missing or invalid 'expr'",
            })
            continue

        try:
            actual = safe_eval(expr, values)
            if isinstance(expected, bool):
                ok = bool(actual) is expected
            elif isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
                ok = numeric_close(actual, expected, tolerance)
            else:
                ok = actual == expected

            if ok:
                passed += 1
            results.append({
                "name": name,
                "status": "pass" if ok else "fail",
                "expr": expr,
                "actual": actual,
                "expected": expected,
                "tolerance": tolerance,
            })
        except Exception as exc:
            results.append({
                "name": name,
                "status": "error",
                "expr": expr,
                "error": str(exc),
            })

    return {
        "status": "success",
        "total_checks": len(checks),
        "passed_checks": passed,
        "failed_checks": len([r for r in results if r["status"] == "fail"]),
        "error_checks": len([r for r in results if r["status"] == "error"]),
        "results": results,
    }


def main():
    if len(sys.argv) != 2:
        print("Usage: python skills/xlsx/scripts/workbook_claims_check.py <claims.json>")
        sys.exit(1)

    claims_path = Path(sys.argv[1]).expanduser()
    if not claims_path.exists():
        print(json.dumps({"status": "error", "error": f"File does not exist: {claims_path}"}))
        sys.exit(1)

    try:
        payload = json.loads(claims_path.read_text(encoding="utf-8"))
        result = run_checks(payload)
        print(json.dumps(result, indent=2))
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}))
        sys.exit(1)

    # Non-zero exit when any check failed or errored so this script is
    # composable in shell pipelines (&&, CI gates, etc.).
    failed = result.get("failed_checks", 0) + result.get("error_checks", 0)
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
