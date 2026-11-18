"""Read-only XAUUSDm DEMO broker preflight. Never calls order_send."""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone

from execution.quote_safety import require_fresh_tick
from risk.symbols import canonicalize_symbol


def inspect_demo(mt5, symbol="XAUUSDm", stop_distances=(1, 2, 5, 10, 20)):
    """Return diagnostic data only; no trading authorization or order submission."""
    canonicalize_symbol(symbol)
    result = {"symbol": symbol, "ready_for_order": False, "checks": {}, "scenarios": []}
    checks = result["checks"]
    account = mt5.account_info()
    if account is None:
        checks["account"] = "BLOCKED: account unavailable"
        return result
    demo = getattr(mt5, "ACCOUNT_TRADE_MODE_DEMO", None)
    if demo is None or getattr(account, "trade_mode", None) != demo:
        checks["account"] = "BLOCKED: DEMO account not verified"
        return result
    checks["account"] = "PASS: DEMO"
    if getattr(account, "trade_allowed", None) is not True or getattr(account, "trade_expert", None) is not True:
        checks["permissions"] = "BLOCKED: trading permissions disabled"
        return result
    checks["permissions"] = "PASS"
    balance = float(getattr(account, "balance", 0) or 0)
    equity = float(getattr(account, "equity", 0) or 0)
    free_margin = float(getattr(account, "margin_free", 0) or 0)
    if not all(math.isfinite(v) and v > 0 for v in (balance, equity, free_margin)):
        checks["funds"] = "BLOCKED: invalid balance, equity, or margin"
        return result
    budget = min(balance, equity) * 0.01
    result["account_currency"] = str(getattr(account, "currency", "unknown"))
    result["risk_budget"] = round(budget, 2)
    checks["funds"] = "PASS"
    if not mt5.symbol_select(symbol, True):
        checks["symbol"] = "BLOCKED: symbol_select failed"
        return result
    info = mt5.symbol_info(symbol)
    tick = mt5.symbol_info_tick(symbol)
    if info is None or tick is None:
        checks["symbol"] = "BLOCKED: symbol info or tick unavailable"
        return result
    try:
        require_fresh_tick(tick)
    except RuntimeError as exc:
        checks["quote"] = f"BLOCKED: {exc}"
        return result
    checks["quote"] = "PASS"
    if getattr(info, "trade_mode", None) != getattr(mt5, "SYMBOL_TRADE_MODE_FULL", None):
        checks["symbol"] = "BLOCKED: symbol is not in full trading mode"
        return result
    checks["symbol"] = "PASS"
    minimum = float(getattr(info, "volume_min", 0) or 0)
    step = float(getattr(info, "volume_step", 0) or 0)
    maximum = float(getattr(info, "volume_max", 0) or 0)
    if not all(math.isfinite(v) and v > 0 for v in (minimum, step, maximum)) or minimum > min(maximum, 0.02):
        checks["volume"] = "BLOCKED: invalid broker minimum/step or exceeds 0.02 cap"
        return result
    if not math.isclose(minimum / step, round(minimum / step), abs_tol=1e-8):
        checks["volume"] = "BLOCKED: broker minimum not aligned to lot step"
        return result
    checks["volume"] = "PASS"
    result["minimum_lot"] = minimum
    result["preferred_lot_cap"] = 0.02
    price = float(getattr(tick, "ask", 0) or 0)
    if not math.isfinite(price) or price <= 0:
        checks["quote"] = "BLOCKED: invalid ask"
        return result
    for distance in stop_distances:
        if not math.isfinite(float(distance)) or distance <= 0 or price <= distance:
            continue
        loss = mt5.order_calc_profit(mt5.ORDER_TYPE_BUY, symbol, minimum, price, price - distance)
        margin = mt5.order_calc_margin(mt5.ORDER_TYPE_BUY, symbol, minimum, price)
        valid = (loss is not None and math.isfinite(float(loss)) and float(loss) < 0
                 and margin is not None and math.isfinite(float(margin)) and float(margin) > 0)
        allowed = bool(valid and abs(float(loss)) <= budget and float(margin) <= free_margin)
        result["scenarios"].append({
            "stop_distance_usd": distance,
            "minimum_lot": minimum,
            "estimated_loss": round(abs(float(loss)), 2) if valid else None,
            "estimated_margin": round(float(margin), 2) if valid else None,
            "within_1pct_and_margin": allowed,
        })
    checks["risk_scenarios"] = ("PASS: at least one sample meets risk/margin"
                                if any(s["within_1pct_and_margin"] for s in result["scenarios"])
                                else "BLOCKED: no sampled stop distance meets 1% risk and margin")
    # A scenario pass is NOT trade authorization: strategy, news, sessions, portfolio,
    # stops, slippage, and final order checks still require independent verification.
    return result


def main():
    parser = argparse.ArgumentParser(description="Read-only MT5 DEMO gold safety diagnostic")
    parser.add_argument("--symbol", default="XAUUSDm")
    args = parser.parse_args()
    import MetaTrader5 as mt5
    if not mt5.initialize():
        raise SystemExit(f"MT5 initialize failed: {mt5.last_error()}")
    try:
        print(json.dumps(inspect_demo(mt5, args.symbol), indent=2))
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
