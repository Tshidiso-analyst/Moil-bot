"""Read-only XAUUSD execution-plan smoke test.

This script reads a locally logged-in MT5 terminal and never submits orders.
Use execution.demo_smoke_test only for a separately confirmed DEMO order.
"""
from __future__ import annotations

import os

import pandas as pd

from dashboard.mt5_live import MT5LiveService
from execution.orchestrator import TradeExecutionOrchestrator
from market_data.live_data import resolve_mt5_symbol
from strategy.trade_decision import TradeDecisionEngine


def main() -> None:
    try:
        import MetaTrader5 as mt5
    except ImportError as exc:
        raise RuntimeError("MetaTrader5 is available only on the Windows trading workstation.") from exc
    path = os.getenv("MT5_PATH")
    initialized = bool(mt5.initialize(path=path) if path else mt5.initialize())
    if not initialized:
        raise RuntimeError(f"MT5 initialization failed: {mt5.last_error()}")
    try:
        account = mt5.account_info()
        if account is None:
            raise RuntimeError(f"No logged-in MT5 account: {mt5.last_error()}")
        service = MT5LiveService(mt5)
        service.connected = True
        service.account = account

        symbol = resolve_mt5_symbol("XAUUSD", mt5)
        timeframe = mt5.TIMEFRAME_M15
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 1, 250)
        if rates is None or len(rates) < 30:
            raise RuntimeError(f"Insufficient completed XAUUSD candles: {mt5.last_error()}")
        dataframe = pd.DataFrame(rates)
        dataframe["timestamp"] = pd.to_datetime(dataframe["time"], unit="s", utc=True)
        dataframe = dataframe[["timestamp", "open", "high", "low", "close"]].copy()

        # News status is deliberately treated as unknown/blocked in this
        # unattended smoke test. It cannot establish a trade-ready signal.
        assessment = TradeDecisionEngine().assess(
            "XAUUSD",
            dataframe,
            fundamental_bias="neutral",
            proposed_risk_percent=0.5,
            high_impact_news=True,
        )
        orchestrator = TradeExecutionOrchestrator(
            mt5_service=service,
            allow_execution=False,
        )
        plan = orchestrator.build_execution_plan(
            symbol=symbol,
            dataframe=dataframe,
            fundamental_bias="neutral",
            assessment=assessment,
            proposed_risk_percent=assessment.risk_percent,
            daily_loss_percent=0.0,
            current_exposure_percent=0.0,
            account_balance=float(getattr(account, "balance", 0.0) or 0.0),
            risk_percent=assessment.risk_percent,
            magic=731111,
        )
        print("READ-ONLY XAUUSD PLAN")
        print(f"Account mode: {getattr(account, 'trade_mode', 'unknown')}")
        print(f"Broker symbol: {symbol} | Canonical symbol: XAUUSD")
        print(f"Assessment: {assessment.direction} | Confirmed: {assessment.confirmation}")
        print(f"Plan allowed: {plan.allowed} | Status: {plan.status}")
        print(f"Reason: {plan.reason}")
        print("No order was submitted. Execution remains disabled.")
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
