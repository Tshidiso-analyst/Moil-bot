from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import MetaTrader5 as mt5

from dashboard.mt5_live import MT5LiveService
from execution.orchestrator import TradeExecutionOrchestrator


# ----- Replace these with your demo account values -----
LOGIN = 12345678
PASSWORD = "your_demo_password"
SERVER = "Broker-Demo"
SYMBOL = "EURUSD"
BALANCE = 500.0


def main() -> None:
    mt5_service = MT5LiveService()
    result = mt5_service.connect(
        login=LOGIN,
        password=PASSWORD,
        server=SERVER,
        requested_mode="DEMO",
    )

    print("CONNECT RESULT:")
    print(result)

    if not result.connected:
        raise RuntimeError(f"MT5 did not connect: {result.message}")

    print("\nOPEN TRADES:")
    print(mt5_service.open_trade_summary())
    print(mt5_service.positions())

    now = datetime.now()
    candles = mt5.copy_rates_range(
        SYMBOL,
        mt5.TIMEFRAME_M15,
        now - timedelta(hours=4),
        now,
    )

    if not candles:
        raise RuntimeError(f"No candle data returned for {SYMBOL}.")

    df = pd.DataFrame(candles)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df = df[["time", "open", "high", "low", "close"]]

    print("\nLATEST CANDLES:")
    print(df.tail())

    orchestrator = TradeExecutionOrchestrator(
        mt5_service=mt5_service,
        executor=None,
        trade_guard=None,
    )

    plan = orchestrator.build_execution_plan(
        symbol=SYMBOL,
        dataframe=df,
        fundamental_bias="neutral",
        proposed_risk_percent=0.5,
        daily_loss_percent=0.0,
        current_exposure_percent=0.0,
        account_balance=BALANCE,
        risk_percent=1.0,
    )

    print("\nPLAN:")
    print({
        "allowed": plan.allowed,
        "symbol": plan.symbol,
        "direction": plan.direction,
        "status": plan.status,
        "reason": plan.reason,
        "risk": plan.risk,
        "order": plan.order,
    })

    if not plan.allowed:
        print("\nTrade was blocked by risk or setup checks.")
        return

    execution = orchestrator.execute(
        symbol=SYMBOL,
        dataframe=df,
        fundamental_bias="neutral",
        proposed_risk_percent=0.5,
        daily_loss_percent=0.0,
        current_exposure_percent=0.0,
        account_balance=BALANCE,
        risk_percent=1.0,
        magic=123456,
        comment="Moil-bot demo smoke test",
    )

    print("\nEXECUTION RESULT:")
    print(execution)

    mt5_service.shutdown()


if __name__ == "__main__":
    main()
