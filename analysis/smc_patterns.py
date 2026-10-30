from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class FairValueGap:
    index: int
    direction: str
    lower: float
    upper: float


@dataclass(frozen=True)
class LiquiditySweep:
    index: int
    direction: str
    level: float
    type: str


@dataclass(frozen=True)
class MarketContext:
    trend: str
    session: str
    liquidity: list[LiquiditySweep]
    fair_value_gaps: list[FairValueGap]
    bos: list[dict]
    choch: list[dict]
    distribution: bool
    consolidation: bool
    premium_discount: str
    bias: str
    reasons: list[str]


def detect_session(timestamp: pd.Timestamp | object) -> str:
    """Return the active trading session from a timestamp in UTC."""
    if timestamp is None:
        return "off_session"
    try:
        dt = pd.Timestamp(timestamp)
    except Exception:
        return "off_session"

    if dt.tzinfo is None:
        dt = dt.tz_localize("UTC")
    else:
        dt = dt.tz_convert("UTC")

    hour = dt.hour
    if 22 <= hour or hour < 1:
        return "asian"
    if 1 <= hour < 7:
        return "asian"
    if 7 <= hour < 10:
        return "london"
    if 10 <= hour < 12:
        return "london_new_york_overlap"
    if 12 <= hour < 17:
        return "new_york"
    return "off_session"


def _last_swing_high(dataframe: pd.DataFrame, lookback: int = 2) -> float | None:
    if len(dataframe) < lookback + 1:
        return None
    recent = dataframe["high"].tail(lookback + 1).tolist()
    if not recent:
        return None
    return max(recent[:-1]) if len(recent) > 1 else recent[0]


def _last_swing_low(dataframe: pd.DataFrame, lookback: int = 2) -> float | None:
    if len(dataframe) < lookback + 1:
        return None
    recent = dataframe["low"].tail(lookback + 1).tolist()
    if not recent:
        return None
    return min(recent[:-1]) if len(recent) > 1 else recent[0]


def find_fair_value_gaps(dataframe: pd.DataFrame) -> list[FairValueGap]:
    gaps: list[FairValueGap] = []
    if len(dataframe) < 3:
        return gaps

    for i in range(2, len(dataframe)):
        candle_before = dataframe.iloc[i - 2]
        candle_after = dataframe.iloc[i]

        if candle_after["low"] > candle_before["high"]:
            gaps.append(
                FairValueGap(
                    index=i,
                    direction="bullish",
                    lower=float(candle_before["high"]),
                    upper=float(candle_after["low"]),
                )
            )
        elif candle_after["high"] < candle_before["low"]:
            gaps.append(
                FairValueGap(
                    index=i,
                    direction="bearish",
                    lower=float(candle_after["high"]),
                    upper=float(candle_before["low"]),
                )
            )

    return gaps


def find_bos_choch(dataframe: pd.DataFrame) -> tuple[list[dict], list[dict]]:
    bos: list[dict] = []
    choch: list[dict] = []
    if len(dataframe) < 3:
        return bos, choch

    for i in range(2, len(dataframe)):
        prev = dataframe.iloc[i - 1]
        curr = dataframe.iloc[i]
        if curr["close"] > prev["high"]:
            bos.append({"index": i, "type": "BOS", "direction": "bullish"})
        elif curr["close"] < prev["low"]:
            bos.append({"index": i, "type": "BOS", "direction": "bearish"})

        if curr["close"] > prev["close"] and curr["low"] < prev["low"]:
            choch.append({"index": i, "type": "CHoCH", "direction": "bullish"})
        elif curr["close"] < prev["close"] and curr["high"] > prev["high"]:
            choch.append({"index": i, "type": "CHoCH", "direction": "bearish"})

    return bos, choch


def find_liquidity_sweeps(dataframe: pd.DataFrame, lookback: int = 3) -> list[LiquiditySweep]:
    sweeps: list[LiquiditySweep] = []
    if len(dataframe) < lookback + 2:
        return sweeps

    for i in range(lookback, len(dataframe) - 1):
        prev = dataframe.iloc[i - lookback : i]
        current = dataframe.iloc[i]
        hb = float(prev["high"].max())
        lb = float(prev["low"].min())

        if current["high"] > hb and current["close"] < hb:
            sweeps.append(
                LiquiditySweep(
                    index=i,
                    direction="sell_side",
                    level=float(hb),
                    type="liquidity_sweep",
                )
            )
        if current["low"] < lb and current["close"] > lb:
            sweeps.append(
                LiquiditySweep(
                    index=i,
                    direction="buy_side",
                    level=float(lb),
                    type="liquidity_sweep",
                )
            )

    return sweeps


def premium_discount_zone(dataframe: pd.DataFrame) -> str:
    if dataframe.empty:
        return "neutral"
    recent = dataframe.iloc[-20:]
    midpoint = (float(recent["high"].max()) + float(recent["low"].min())) / 2
    last_close = float(recent["close"].iloc[-1])
    if last_close > midpoint:
        return "premium"
    if last_close < midpoint:
        return "discount"
    return "neutral"


def detect_distribution_or_consolidation(dataframe: pd.DataFrame) -> tuple[bool, bool]:
    if len(dataframe) < 10:
        return False, False

    recent = dataframe.iloc[-10:]
    recent_range = float(recent["high"].max()) - float(recent["low"].min())

    if len(dataframe) >= 20:
        previous = dataframe.iloc[-20:-10]
        prev_range = float(previous["high"].max()) - float(previous["low"].min())
    else:
        prev_range = recent_range

    if recent_range > prev_range * 1.2:
        return True, False
    if recent_range < prev_range * 0.8:
        return False, True
    return False, False


def analyze_market_context(
    dataframe: pd.DataFrame,
    execution_timeframe: str = "M15",
) -> MarketContext:
    if dataframe.empty:
        raise ValueError("dataframe must not be empty")

    gaps = find_fair_value_gaps(dataframe)
    bos, choch = find_bos_choch(dataframe)
    liquidity = find_liquidity_sweeps(dataframe)
    distribution, consolidation = detect_distribution_or_consolidation(dataframe)
    pd_zone = premium_discount_zone(dataframe)
    session = detect_session(dataframe.iloc[-1].get("timestamp"))

    last_close = float(dataframe["close"].iloc[-1])
    last_open = float(dataframe["open"].iloc[-1])
    swing_high = _last_swing_high(dataframe)
    swing_low = _last_swing_low(dataframe)

    if swing_high is not None and swing_low is not None:
        if last_close > swing_high and last_open > swing_low:
            trend = "bullish"
        elif last_close < swing_low and last_open < swing_high:
            trend = "bearish"
        else:
            trend = "neutral"
    else:
        trend = "neutral"

    if bos:
        last_bos = bos[-1]
        if last_bos["direction"] == "bullish":
            trend = "bullish"
        elif last_bos["direction"] == "bearish":
            trend = "bearish"

    if choch and trend != "neutral":
        last_choch = choch[-1]
        if last_choch["direction"] != trend:
            trend = "neutral"

    if gaps:
        final_gap = gaps[-1]
        if final_gap.direction == "bullish":
            bias = "bullish"
        elif final_gap.direction == "bearish":
            bias = "bearish"
        else:
            bias = "neutral"
    else:
        bias = trend

    reasons = [
        f"Primary session: {session}.",
        f"Trend bias: {trend}.",
        f"Premium/discount state: {pd_zone}.",
        f"Liquidity sweeps detected: {len(liquidity)}.",
        f"Fair value gaps detected: {len(gaps)}.",
        f"Distribution: {distribution}; consolidation: {consolidation}.",
    ]

    if distribution:
        reasons.append("Market is distributing and is vulnerable to reversals or failed continuation.")
    if consolidation:
        reasons.append("Market is consolidating and is typically waiting for directional confirmation.")
    if liquidity:
        sweep = liquidity[-1]
        reasons.append(f"Latest liquidity sweep: {sweep.direction} at {sweep.level}.")
    if bos:
        reasons.append(f"Latest BOS: {bos[-1]['direction']}.")
    if choch:
        reasons.append(f"Latest CHoCH: {choch[-1]['direction']}.")

    return MarketContext(
        trend=trend,
        session=session,
        liquidity=liquidity,
        fair_value_gaps=gaps,
        bos=bos,
        choch=choch,
        distribution=distribution,
        consolidation=consolidation,
        premium_discount=pd_zone,
        bias=bias,
        reasons=reasons,
    )


__all__ = [
    "FairValueGap",
    "LiquiditySweep",
    "MarketContext",
    "analyze_market_context",
    "detect_session",
    "detect_distribution_or_consolidation",
    "find_bos_choch",
    "find_fair_value_gaps",
    "find_liquidity_sweeps",
    "premium_discount_zone",
]
