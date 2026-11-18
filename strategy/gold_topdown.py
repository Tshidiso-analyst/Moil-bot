"""Fail-closed, closed-candle gold top-down research. Never authorizes orders.

Swing pivots are confirmed only after two later CLOSED candles. No future
candles beyond the supplied input are consulted. This is a research hypothesis.
"""
from __future__ import annotations

import math


def _valid(bars, minimum=12):
    if bars is None or len(bars) < minimum:
        return False
    try:
        return all(
            all(math.isfinite(float(bar[k])) for k in ("open", "high", "low", "close"))
            and float(bar["low"]) <= min(float(bar["open"]), float(bar["close"]))
            <= max(float(bar["open"]), float(bar["close"])) <= float(bar["high"])
            for bar in bars
        )
    except (KeyError, ValueError, TypeError):
        return False


def confirmed_pivots(bars, width=2):
    """Return highs/lows known by the last supplied closed bar."""
    if not _valid(bars, 2 * width + 1):
        return {"highs": [], "lows": []}
    highs, lows = [], []
    for i in range(width, len(bars) - width):
        high = float(bars[i]["high"])
        low = float(bars[i]["low"])
        before_after = bars[i-width:i] + bars[i+1:i+width+1]
        if all(high > float(x["high"]) for x in before_after):
            highs.append({"index": i, "price": high, "confirmed_index": i + width})
        if all(low < float(x["low"]) for x in before_after):
            lows.append({"index": i, "price": low, "confirmed_index": i + width})
    return {"highs": highs, "lows": lows}


def structure_bias(bars):
    pivots = confirmed_pivots(bars)
    highs, lows = pivots["highs"], pivots["lows"]
    if len(highs) < 2 or len(lows) < 2:
        return {"bias": "neutral", "reason": "Insufficient confirmed swing highs and lows.", "pivots": pivots}
    hh = highs[-1]["price"] > highs[-2]["price"]
    hl = lows[-1]["price"] > lows[-2]["price"]
    lh = highs[-1]["price"] < highs[-2]["price"]
    ll = lows[-1]["price"] < lows[-2]["price"]
    bias = "bullish" if hh and hl else "bearish" if lh and ll else "neutral"
    return {"bias": bias, "reason": "Confirmed HH/HL" if bias == "bullish" else
            "Confirmed LH/LL" if bias == "bearish" else "Mixed confirmed structure.",
            "pivots": pivots}


def inspect_gold_topdown(*, d1_bars, h4_bars, h1_bars, m15_bars):
    """Pure research-only D1/H4/H1/M15 context; caller passes CLOSED bars."""
    result = {"status": "WAIT", "execution_ready": False, "direction": "neutral",
              "stage": "data", "reasons": [], "timeframes": {}}
    for tf, bars in (("D1", d1_bars), ("H4", h4_bars), ("H1", h1_bars), ("M15", m15_bars)):
        if not _valid(bars, 12):
            result["reasons"].append(f"{tf}: insufficient or invalid closed OHLC candles.")
            return result
    daily = structure_bias(d1_bars)
    four = structure_bias(h4_bars)
    hour = structure_bias(h1_bars)
    result["timeframes"] = {
        "D1": {"bias": daily["bias"], "reason": daily["reason"]},
        "H4": {"bias": four["bias"], "reason": four["reason"]},
        "H1": {"bias": hour["bias"], "reason": hour["reason"]},
        "M15": {"bias": structure_bias(m15_bars)["bias"]},
    }
    # Confirmed swing levels are diagnostic references, not entry triggers.
    result["next_checks"] = []
    for tf, analysis, candles in (("D1", daily, d1_bars), ("H4", four, h4_bars),
                                   ("H1", hour, h1_bars)):
        highs, lows = analysis["pivots"]["highs"], analysis["pivots"]["lows"]
        info = result["timeframes"][tf]
        info["close"] = float(candles[-1]["close"])
        info["last_confirmed_swing_high"] = highs[-1]["price"] if highs else None
        info["last_confirmed_swing_low"] = lows[-1]["price"] if lows else None
        info["swing_counts"] = {"highs": len(highs), "lows": len(lows)}
        if tf in ("D1", "H4"):
            if info["bias"] == "neutral":
                result["next_checks"].append(
                    f"{tf}: wait for two confirmed rising highs AND lows (bullish), "
                    "or two confirmed falling highs AND lows (bearish).")
            high, low = info["last_confirmed_swing_high"], info["last_confirmed_swing_low"]
            if high is not None and low is not None:
                result["next_checks"].append(
                    f"{tf} confirmed swing references: high {high:.3f}, low {low:.3f}. "
                    "A price crossing either level alone is NOT an entry signal.")
    result["stage"] = "higher_timeframe"
    if daily["bias"] == "neutral" or four["bias"] != daily["bias"]:
        result["reasons"].append("D1 and H4 confirmed structure are not aligned; no directional setup.")
        return result
    result["direction"] = daily["bias"]
    result["stage"] = "h4_dealing_range"
    pivots = four["pivots"]
    hi = pivots["highs"][-1]["price"]
    lo = pivots["lows"][-1]["price"]
    if hi <= lo:
        result["reasons"].append("Invalid H4 dealing range.")
        return result
    midpoint = (hi + lo) / 2
    price = float(h4_bars[-1]["close"])
    result["next_checks"].append(f"H4 midpoint {midpoint:.3f}: prefer discount for longs, premium for shorts.")
    result["h4_range"] = {"high": hi, "low": lo, "midpoint": midpoint,
                          "zone": "discount" if price < midpoint else "premium" if price > midpoint else "equilibrium"}
    zone_ok = (daily["bias"] == "bullish" and price < midpoint) or (
        daily["bias"] == "bearish" and price > midpoint)
    if not zone_ok:
        result["reasons"].append("H4 price is not in the preferred premium/discount area.")
        return result
    result["stage"] = "h1_structure"
    if hour["bias"] != daily["bias"]:
        result["reasons"].append("H1 confirmed structure does not align with D1/H4.")
        return result
    result["next_checks"].append("Next: M15 sweep, close-confirmed MSS, FVG and later retracement; calendar and risk checks remain pending.")
    result["stage"] = "m15_confirmation"
    result["reasons"].append("HTF structure and H4 location align; M15 sweep/MSS/FVG, session, calendar and risk still required.")
    return result


__all__ = ["confirmed_pivots", "structure_bias", "inspect_gold_topdown"]
