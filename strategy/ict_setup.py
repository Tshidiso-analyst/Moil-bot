"""Deterministic ICT-style research setup evaluator.

This is a research candidate generator, not an execution approval. It requires
a higher-timeframe directional bias, a liquidity raid, displacement, a body-
close market-structure shift, and a retracement into a three-candle FVG.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd


NEW_YORK = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class ICTSetup:
    symbol: str
    direction: str
    valid: bool
    session: str
    entry: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    fvg_lower: float | None = None
    fvg_upper: float | None = None
    swept_level: float | None = None
    confirmations: tuple[str, ...] = ()
    rejections: tuple[str, ...] = ()
    risk_reward: float | None = None


def _session(timestamp: Any) -> str:
    stamp = pd.Timestamp(timestamp)
    if stamp.tzinfo is None:
        stamp = stamp.tz_localize("UTC")
    local = stamp.tz_convert(NEW_YORK).time()
    if time(2, 0) <= local <= time(5, 0):
        return "london_killzone"
    if time(7, 0) <= local <= time(10, 0):
        return "new_york_killzone"
    return "off_session"


def _valid_ohlc(frame: pd.DataFrame, label: str) -> None:
    required = {"timestamp", "open", "high", "low", "close"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"{label} data missing columns: {', '.join(sorted(missing))}")
    if frame.empty:
        raise ValueError(f"{label} data must not be empty.")


def _htf_bias(frame: pd.DataFrame) -> str:
    # A deliberately simple, causal directional filter: last close relative
    # to the midpoint of the last 20 completed HTF candles.
    if len(frame) < 20:
        return "neutral"
    sample = frame.tail(20)
    midpoint = (float(sample["high"].max()) + float(sample["low"].min())) / 2
    close = float(sample["close"].iloc[-1])
    return "bullish" if close > midpoint else "bearish" if close < midpoint else "neutral"


def evaluate_ict_setup(
    symbol: str,
    execution_data: pd.DataFrame,
    higher_timeframe_data: pd.DataFrame,
    *,
    liquidity_lookback: int = 20,
    displacement_body_multiple: float = 1.5,
    minimum_reward_risk: float = 2.0,
    allowed_sessions: tuple[str, ...] = ("london_killzone", "new_york_killzone"),
    max_pattern_age: int = 8,
) -> ICTSetup:
    """Evaluate only completed candles and return an explainable ICT candidate."""
    _valid_ohlc(execution_data, "Execution timeframe")
    _valid_ohlc(higher_timeframe_data, "Higher timeframe")
    if liquidity_lookback < 5 or max_pattern_age < 2:
        raise ValueError("liquidity_lookback must be >= 5 and max_pattern_age >= 2.")
    if displacement_body_multiple <= 0 or minimum_reward_risk <= 0:
        raise ValueError("Displacement and reward/risk thresholds must be positive.")

    data = execution_data.sort_values("timestamp").reset_index(drop=True)
    latest_execution_time = pd.Timestamp(data.iloc[-1]["timestamp"])
    htf = higher_timeframe_data.sort_values("timestamp").reset_index(drop=True)
    htf_times = pd.to_datetime(htf["timestamp"], utc=True)
    execution_time_utc = latest_execution_time.tz_localize("UTC") if latest_execution_time.tzinfo is None else latest_execution_time.tz_convert("UTC")
    htf = htf.loc[htf_times <= execution_time_utc].reset_index(drop=True)
    session = _session(data.iloc[-1]["timestamp"])
    confirmations: list[str] = []
    rejections: list[str] = []

    bias = _htf_bias(htf)
    if bias == "neutral":
        rejections.append("Higher-timeframe bias is neutral or lacks 20 completed candles.")
    else:
        confirmations.append(f"Higher-timeframe bias: {bias}.")

    if session not in allowed_sessions:
        rejections.append(f"{session} is outside the configured ICT kill zones.")
    else:
        confirmations.append(f"Active session: {session}.")

    if len(data) < max(liquidity_lookback + 3, 30):
        rejections.append("Insufficient execution-timeframe history.")
        return ICTSetup(str(symbol).upper(), "neutral", False, session,
                        confirmations=tuple(confirmations), rejections=tuple(rejections))

    last_i = len(data) - 1
    start = max(0, last_i - max_pattern_age)
    match: dict[str, float | str] | None = None

    # Find a recent sweep followed by directional displacement and a body-close
    # through the pre-sweep structure. FVG must be retested by the latest candle.
    for sweep_i in range(last_i - 2, start - 1, -1):
        prior = data.iloc[max(0, sweep_i - liquidity_lookback):sweep_i]
        if len(prior) < liquidity_lookback:
            continue
        sweep = data.iloc[sweep_i]
        direction = "bullish" if float(sweep["low"]) < float(prior["low"].min()) and float(sweep["close"]) > float(prior["low"].min()) else (
            "bearish" if float(sweep["high"]) > float(prior["high"].max()) and float(sweep["close"]) < float(prior["high"].max()) else ""
        )
        if not direction or direction != bias:
            continue

        sweep_level = float(prior["low"].min() if direction == "bullish" else prior["high"].max())
        for displacement_i in range(sweep_i + 1, min(last_i, sweep_i + 4)):
            if displacement_i < 2:
                continue
            candle = data.iloc[displacement_i]
            body = abs(float(candle["close"]) - float(candle["open"]))
            prior_bodies = (data.iloc[max(0, displacement_i - 20):displacement_i]["close"] -
                            data.iloc[max(0, displacement_i - 20):displacement_i]["open"]).abs()
            average_body = float(prior_bodies.mean()) if not prior_bodies.empty else 0.0
            if average_body <= 0 or body < average_body * displacement_body_multiple:
                continue
            if direction == "bullish" and float(candle["close"]) <= float(candle["open"]):
                continue
            if direction == "bearish" and float(candle["close"]) >= float(candle["open"]):
                continue

            structure = data.iloc[max(0, sweep_i - 5):sweep_i]
            if structure.empty:
                continue
            mss = (float(candle["close"]) > float(structure["high"].max()) if direction == "bullish"
                   else float(candle["close"]) < float(structure["low"].min()))
            if not mss:
                continue

            left, right = data.iloc[displacement_i - 2], candle
            if direction == "bullish":
                lower, upper = float(left["high"]), float(right["low"])
                if upper <= lower:
                    continue
            else:
                lower, upper = float(right["high"]), float(left["low"])
                if upper <= lower:
                    continue

            latest = data.iloc[last_i]
            retested = float(latest["low"]) <= upper and float(latest["high"]) >= lower
            if not retested:
                continue
            entry = (lower + upper) / 2.0
            stop = float(data.iloc[sweep_i]["low"]) if direction == "bullish" else float(data.iloc[sweep_i]["high"])
            risk = entry - stop if direction == "bullish" else stop - entry
            if risk <= 0:
                continue
            target = float(prior["high"].max() if direction == "bullish" else prior["low"].min())
            reward = target - entry if direction == "bullish" else entry - target
            rr = reward / risk if reward > 0 else 0.0
            if rr < minimum_reward_risk:
                rejections.append(f"Available liquidity target offers only {rr:.2f}R; minimum is {minimum_reward_risk:.2f}R.")
                continue
            match = {"direction": direction, "sweep_level": sweep_level,
                     "lower": lower, "upper": upper, "entry": entry,
                     "stop": stop, "target": target, "rr": rr}
            break
        if match:
            break

    if match is None:
        rejections.append("No complete liquidity-raid → displacement → body-close MSS → FVG-retest sequence found.")
        return ICTSetup(str(symbol).upper(), "neutral", False, session,
                        confirmations=tuple(confirmations), rejections=tuple(rejections))

    confirmations.extend([
        "Liquidity raid rejected back inside the prior range.",
        "Directional displacement exceeded the recent average candle body.",
        "Market structure shift confirmed by candle-body close.",
        "Price retraced into the displacement fair value gap.",
        f"Opposing liquidity target provides {float(match['rr']):.2f}R.",
    ])
    direction = str(match["direction"])
    return ICTSetup(
        symbol=str(symbol).upper(), direction=direction, valid=True, session=session,
        entry=float(match["entry"]), stop_loss=float(match["stop"]),
        take_profit=float(match["target"]), fvg_lower=float(match["lower"]),
        fvg_upper=float(match["upper"]), swept_level=float(match["sweep_level"]),
        confirmations=tuple(confirmations), rejections=tuple(rejections),
        risk_reward=float(match["rr"]),
    )


def scan_ict_markets(
    execution_data: dict[str, pd.DataFrame],
    higher_timeframe_data: dict[str, pd.DataFrame],
    **settings: Any,
) -> list[ICTSetup]:
    """Scan every symbol with both timeframes and return valid candidates first."""
    results: list[ICTSetup] = []
    for symbol, frame in execution_data.items():
        htf = higher_timeframe_data.get(symbol)
        if htf is None or frame is None or frame.empty:
            continue
        try:
            results.append(evaluate_ict_setup(symbol, frame, htf, **settings))
        except (ValueError, KeyError, TypeError) as exc:
            results.append(ICTSetup(
                symbol=str(symbol).upper(), direction="neutral", valid=False,
                session="unknown", rejections=(f"Data rejected: {exc}",),
            ))
    return sorted(results, key=lambda item: (not item.valid, -(item.risk_reward or 0.0), item.symbol))


__all__ = ["ICTSetup", "evaluate_ict_setup", "scan_ict_markets"]
