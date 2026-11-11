"""Exploratory, causal ICT/SMC backtest adapter.

Signals are evaluated on completed-candle prefixes only. This adapter does
not promote research candidates to approved execution rules.
"""
from __future__ import annotations

from datetime import time
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from backtesting.cost_aware_engine import CostAwareBacktestEngine, CostAwareSplitResult
from strategy.trade_decision import TradeDecisionEngine


NEW_YORK = ZoneInfo("America/New_York")


def make_smc_signal_function(
    symbol: str,
    *,
    decision_engine: Any | None = None,
    risk_percent: float = 0.5,
    session_start: time = time(10, 30),
    session_end: time = time(15, 45),
):
    """Build a stateful signal callback with a New York cash-session filter.

    The first eligible signal is after the NYSE opening hour. The last signal
    is 15:45 New York time so a 15-minute next-bar entry does not begin after
    the regular session. A decision engine only sees the supplied history.
    """
    engine = decision_engine or TradeDecisionEngine()
    traded_signal_dates: set[object] = set()
    clean_symbol = str(symbol or "").strip().upper()
    if not clean_symbol:
        raise ValueError("symbol must not be empty.")
    if not 0 < float(risk_percent) <= 1.0:
        raise ValueError("risk_percent must be greater than 0 and no more than 1.")

    def signal(history: pd.DataFrame) -> str | None:
        if history.empty or "timestamp" not in history.columns:
            return None
        timestamp = pd.Timestamp(history.iloc[-1]["timestamp"])
        if timestamp.tzinfo is None:
            timestamp = timestamp.tz_localize("UTC")
        local_time = timestamp.tz_convert(NEW_YORK)
        if not session_start <= local_time.time() <= session_end:
            return None
        if local_time.date() in traded_signal_dates:
            return None

        assessment = engine.assess(
            clean_symbol,
            history.copy(deep=True),
            fundamental_bias="neutral",
            proposed_risk_percent=float(risk_percent),
            daily_loss_percent=0.0,
            open_trades=0,
            high_impact_news=False,
        )
        if not getattr(assessment, "setup_valid", False):
            return None
        direction = str(getattr(assessment, "direction", "")).strip().lower()
        if direction not in {"bullish", "bearish"}:
            return None
        traded_signal_dates.add(local_time.date())
        return direction

    return signal


def run_smc_backtest(
    dataframe: pd.DataFrame,
    symbol: str,
    *,
    stop_distance: float,
    reward_multiple: float = 2.0,
    spread: float = 0.0,
    slippage: float = 0.0,
    commission_per_unit_per_side: float = 0.0,
    position_size: float = 1.0,
    initial_equity: float = 10_000.0,
    train_fraction: float = 0.7,
    decision_engine: Any | None = None,
) -> CostAwareSplitResult:
    """Run a chronological train/holdout simulation with costs and no overlap."""
    signal_fn = make_smc_signal_function(symbol, decision_engine=decision_engine)
    return CostAwareBacktestEngine().run_train_test(
        dataframe,
        symbol,
        signal_fn,
        train_fraction=train_fraction,
        stop_distance=stop_distance,
        reward_multiple=reward_multiple,
        spread=spread,
        slippage=slippage,
        commission_per_unit_per_side=commission_per_unit_per_side,
        position_size=position_size,
        initial_equity=initial_equity,
        max_trades_per_day=1,
        trading_timezone="America/New_York",
    )


__all__ = ["make_smc_signal_function", "run_smc_backtest"]
