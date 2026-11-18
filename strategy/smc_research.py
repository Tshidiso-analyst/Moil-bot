"""Deterministic SMC research-state scanner for CLOSED gold candles.

Definitions are explicit hypotheses, not verified institutional order flow.
No trade authorization is produced by this module.
"""
from __future__ import annotations

import math


def inspect_smc(bars, *, htf_bars=None, lookback=10):
    """Scan closed OHLC bars, returning explainable WAIT/research-only states.

    Sequence: HTF close vs prior range midpoint, sweep/reclaim of a prior
    extreme, close-based structure break with displacement, 3-candle FVG,
    then later retracement into the gap. OB detection is intentionally deferred.
    """
    result = dict(status="WAIT", execution_ready=False, direction="neutral",
                  stage="higher_timeframe", reasons=[], events=[])
    if len(bars) < max(lookback + 8, 25) or not htf_bars or len(htf_bars) < 5:
        result["reasons"].append("Insufficient closed M15/H1 candles for top-down confirmation.")
        return result
    required = ("open", "high", "low", "close")
    for b in list(bars) + list(htf_bars):
        if any(k not in b or not math.isfinite(float(b[k])) for k in required):
            result["reasons"].append("Invalid OHLC data.")
            return result
    htf = htf_bars[-1]
    history = htf_bars[-5:-1]
    midpoint = (max(x["high"] for x in history) + min(x["low"] for x in history)) / 2
    direction = "bullish" if htf["close"] > midpoint else "bearish" if htf["close"] < midpoint else "neutral"
    result["direction"] = direction
    result["reasons"].append(f"H1 research bias: {direction} (last close vs previous four-bar range midpoint).")
    if direction == "neutral":
        return result
    result["stage"] = "liquidity_sweep"
    # Use only the most recent 60 closed M15 candles; no future data for an event.
    recent = bars[-60:]
    for i in range(lookback, len(recent) - 4):
        prior = recent[i-lookback:i]
        candle = recent[i]
        low = min(b["low"] for b in prior)
        high = max(b["high"] for b in prior)
        swept = (candle["low"] < low and candle["close"] > low) if direction == "bullish" else (candle["high"] > high and candle["close"] < high)
        if not swept:
            continue
        result["stage"] = "structure_confirmation"
        result["events"].append(dict(type="sweep", index=i, level=low if direction == "bullish" else high))
        # Close beyond opposite swing, not a wick; strong candle body vs preceding mean.
        opposite = high if direction == "bullish" else low
        avg_body = sum(abs(b["close"] - b["open"]) for b in prior) / len(prior)
        for j in range(i+1, min(i+7, len(recent)-3)):
            b = recent[j]
            broke = b["close"] > opposite if direction == "bullish" else b["close"] < opposite
            displacement = abs(b["close"] - b["open"]) > 1.5 * avg_body and avg_body > 0
            if not (broke and displacement):
                continue
            result["stage"] = "fvg"
            result["events"].append(dict(type="close_confirmed_mss", index=j, level=opposite))
            # FVG must occur on/around displacement, with no overlapping first/third wicks.
            for k in range(max(i+2, j), min(j+3, len(recent)-1)):
                first, third = recent[k-2], recent[k]
                lower = first["high"] if direction == "bullish" else third["high"]
                upper = third["low"] if direction == "bullish" else first["low"]
                if lower >= upper:
                    continue
                result["stage"] = "retracement"
                result["events"].append(dict(type="fvg", index=k, lower=lower, upper=upper))
                # Only candles AFTER gap creation can confirm a retracement.
                for r in range(k+1, len(recent)):
                    retrace = recent[r]
                    touched = retrace["low"] <= upper and retrace["high"] >= lower
                    if touched:
                        result["status"] = "RESEARCH_CANDIDATE"
                        result["stage"] = "risk_and_external_confirmation"
                        result["events"].append(dict(type="fvg_retest", index=r))
                        result["reasons"].append("Sweep, close-based MSS, displacement and subsequent FVG retest observed.")
                        result["reasons"].append("Still requires session, news, spread, structure stop, risk and source-rule validation.")
                        return result
                result["reasons"].append("Confirmed FVG found; waiting for a later retracement.")
                return result
            result["reasons"].append("Structure shift observed but no aligned three-candle FVG.")
            return result
        result["reasons"].append("Liquidity sweep found; waiting for close-based MSS and displacement.")
        return result
    result["reasons"].append("No aligned sweep/reclaim in recent closed M15 candles.")
    return result
