"""Explicitly confirmed DEMO-only MT5 order smoke test.

The MT5 desktop terminal must already be logged into a DEMO account.
This command cannot submit orders to REAL, contest, or futures accounts.
"""
from __future__ import annotations

import argparse
import os


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Moil-bot DEMO order smoke test")
    parser.add_argument("--symbol", required=True, help="Exact broker symbol, including any suffix")
    parser.add_argument("--direction", required=True, choices=("bullish", "bearish"))
    parser.add_argument("--stop-loss", required=True, type=float)
    parser.add_argument("--take-profit", required=True, type=float)
    parser.add_argument("--risk-percent", type=float, default=1.0)
    parser.add_argument("--mt5-path", default=os.getenv("MT5_PATH"))
    parser.add_argument("--confirm-demo-order", action="store_true", help="Explicitly authorize one DEMO order")
    parser.add_argument("--confirm-session", action="store_true", help="Confirm this is within your allowed NYSE trading window")
    parser.add_argument("--confirm-no-high-impact-news", action="store_true", help="Confirm no prohibited high-impact event is active")
    return parser


def main() -> int:
    args = _parser().parse_args()
    if not (
        args.confirm_demo_order
        and args.confirm_session
        and args.confirm_no_high_impact_news
    ):
        raise SystemExit(
            "Refusing to send an order. Supply --confirm-demo-order, "
            "--confirm-session and --confirm-no-high-impact-news after checking the setup."
        )

    try:
        import MetaTrader5 as mt5
    except ImportError as exc:
        raise SystemExit("Install requirements.txt in Windows Python with MetaTrader 5 installed.") from exc

    initialized = bool(mt5.initialize(path=args.mt5_path) if args.mt5_path else mt5.initialize())
    if not initialized:
        raise SystemExit(f"MT5 initialization failed: {mt5.last_error()}")
    try:
        from execution.demo_pipeline import DemoExecutionError, DemoExecutionPipeline

        account = mt5.account_info()
        if account is None:
            raise SystemExit(f"MT5 account is not logged in: {mt5.last_error()}")
        print(
            f"Connected account: {getattr(account, 'login', 'unknown')} | "
            f"Server: {getattr(account, 'server', 'unknown')} | "
            f"Trade mode: {getattr(account, 'trade_mode', 'unknown')}"
        )
        result = DemoExecutionPipeline(mt5).execute_market_order(
            symbol=args.symbol,
            direction=args.direction,
            stop_loss=args.stop_loss,
            take_profit=args.take_profit,
            risk_percent=args.risk_percent,
            confirmation=args.confirm_demo_order,
            session_confirmed=args.confirm_session,
            no_high_impact_news_confirmed=args.confirm_no_high_impact_news,
        )
        print("\nDEMO EXECUTION RESULT")
        print(f"Status: {result.status}")
        print(f"Message: {result.message}")
        print(f"Ticket: {result.ticket}")
        print(f"Symbol / direction: {result.symbol} / {result.direction}")
        print(f"Volume: {result.volume}")
        print(f"Entry / SL / TP: {result.entry_price} / {result.stop_loss} / {result.take_profit}")
        print(f"Risk budget / estimated loss: {result.risk_amount:.2f} / {result.estimated_loss:.2f}")
        print(f"Margin required: {result.margin_required:.2f}")
        return 0
    except DemoExecutionError as exc:
        raise SystemExit(f"DEMO ORDER BLOCKED: {exc}") from exc
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
