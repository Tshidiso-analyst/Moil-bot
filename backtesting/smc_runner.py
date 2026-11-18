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
from risk.symbols import canonicalize_symbol


NEW_YORK = ZoneInfo("America/New_York")


def make_smc_signal_function(
    symbol: str,
    *,
    decision_engine: Any | None = None,
    risk_percent: float = 0.5,
    session_start: time = time(9, 30),
    session_end: time = time(10, 15),
):
    """Build a signal callback filtered to the first NYSE trading hour.

    Multiple independently confirmed setups may signal during the eligible
    window; the cost-aware engine enforces the portfolio's daily entry cap.
    """
    engine = decision_engine or TradeDecisionEngine()
    clean_symbol = canonicalize_symbol(symbol)
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
    position_size: float = 0.02,
    initial_equity: float = 10_000.0,
    train_fraction: float = 0.7,
    decision_engine: Any | None = None,
) -> CostAwareSplitResult:
    """Run a chronological train/holdout simulation with costs and no overlap."""
    clean_symbol = canonicalize_symbol(symbol)
    signal_fn = make_smc_signal_function(clean_symbol, decision_engine=decision_engine)
    return CostAwareBacktestEngine().run_train_test(
        dataframe,
        clean_symbol,
        signal_fn,
        train_fraction=train_fraction,
        stop_distance=stop_distance,
        reward_multiple=reward_multiple,
        spread=spread,
        slippage=slippage,
        commission_per_unit_per_side=commission_per_unit_per_side,
        position_size=position_size,
        initial_equity=initial_equity,
        max_trades_per_day=10,
        trading_timezone="America/New_York",
    )


__all__ = ["make_smc_signal_function", "run_smc_backtest"]
