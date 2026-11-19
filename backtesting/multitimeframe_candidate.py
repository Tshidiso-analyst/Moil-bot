"""Causal multi-timeframe research signal adapter for historical replay.

Hypothesis only: not source-approved or broker execution ready.
All HTF frames are filtered by their *closing* timestamps, never opening
timestamps. M15 signal history is supplied by the replay engine.
"""
from __future__ import annotations

import pandas as pd

from strategy.gold_topdown import inspect_gold_topdown
from strategy.smc_research import inspect_smc


FREQUENCIES = {"M15": pd.Timedelta(minutes=15),
               "H1": pd.Timedelta(hours=1),
               "H4": pd.Timedelta(hours=4),
               "D1": pd.Timedelta(days=1)}


def _closed(frame, decision_time, timeframe):
    data = frame.copy()
    data["timestamp"] = pd.to_datetime(data["timestamp"], utc=True)
    # Timestamp represents bar open, so require actual bar close <= decision.
    data = data.loc[data.timestamp + FREQUENCIES[timeframe] <= decision_time]
    return data.sort_values("timestamp").tail(250).to_dict("records")


def make_multitimeframe_signal(datasets):
    """Return signal_fn(symbol, M15_history), strictly causal and fail closed.

    The scanner's RESEARCH_CANDIDATE is a hypothesis only. It does not
    establish a trade-ready strategy; conservative additional gates apply.
    """
    if not datasets or not set(datasets) <= {"EURUSD", "XAUUSD"}:
        raise ValueError("Only EURUSD and XAUUSD datasets supported")
    for symbol, frames in datasets.items():
        if set(frames) != {"D1", "H4", "H1", "M15"}:
            raise ValueError(f"{symbol}: require D1/H4/H1/M15")
    seen = set()

    def signal(symbol, history):
        if symbol not in datasets or len(history) < 25:
            return None
        # The replay passes history through a closed M15 bar. It is not
        # observable until 15 minutes after that bar's OPEN timestamp.
        decision = pd.Timestamp(history.iloc[-1].timestamp)
        if decision.tzinfo is None:
            raise ValueError("UTC-aware timestamps required")
        decision += FREQUENCIES["M15"]
        frames = datasets[symbol]
        d1 = _closed(frames["D1"], decision, "D1")
        h4 = _closed(frames["H4"], decision, "H4")
        h1 = _closed(frames["H1"], decision, "H1")
        m15 = _closed(history, decision, "M15")
        context = inspect_gold_topdown(
            d1_bars=d1, h4_bars=h4, h1_bars=h1, m15_bars=m15)
        if context["stage"] != "m15_confirmation":
            return None
        research = inspect_smc(m15, htf_bars=h1)
        if research["status"] != "RESEARCH_CANDIDATE":
            return None
        side = "buy" if context["direction"] == "bullish" else "sell"
        if research["direction"] != context["direction"]:
            return None
        # Only a newly completed M15 retest can produce a fresh signal.
        retests = [event for event in research["events"]
                   if event.get("type") == "fvg_retest"]
        if not retests or retests[-1]["index"] != len(m15[-60:]) - 1:
            return None
        key = (symbol, str(m15[-1]["timestamp"]), side)
        if key in seen:
            return None
        seen.add(key)
        recent = m15[-12:]
        stop = min(float(x["low"]) for x in recent) if side == "buy" else max(float(x["high"]) for x in recent)
        reference = float(m15[-1]["close"])
        distance = (reference - stop) if side == "buy" else (stop - reference)
        if distance <= 0:
            return None
        target = reference + 3 * distance if side == "buy" else reference - 3 * distance
        return {"side": side, "stop": stop, "target": target}

    return signal
