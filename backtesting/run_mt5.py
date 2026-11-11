"""Run an exploratory SMC holdout backtest on completed candles from local MT5.

Example (PowerShell):
    python -m backtesting.run_mt5 --symbol EURUSD --timeframe M15 --bars 3000 --stop-distance 0.0010 --spread 0.00010 --slippage 0.00002

No orders are submitted by this module.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone

import pandas as pd

from backtesting.smc_runner import run_smc_backtest
from market_data.live_data import resolve_mt5_symbol


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Moil-bot MT5 historical SMC backtest (simulation only)")
    parser.add_argument("--symbol", default="EURUSD")
    parser.add_argument("--timeframe", default="M15", choices=("M5", "M15", "M30", "H1", "H4", "D1"))
    parser.add_argument("--bars", type=int, default=3000)
    parser.add_argument("--stop-distance", type=float, required=True, help="Fixed stop distance in symbol price units")
    parser.add_argument("--reward-multiple", type=float, default=2.0)
    parser.add_argument("--spread", type=float, default=0.0, help="Full spread in symbol price units")
    parser.add_argument("--slippage", type=float, default=0.0, help="Adverse slippage per side in price units")
    parser.add_argument("--commission-per-unit-per-side", type=float, default=0.0)
    parser.add_argument("--position-size", type=float, default=1.0)
    parser.add_argument("--initial-equity", type=float, default=10_000.0)
    parser.add_argument("--train-fraction", type=float, default=0.7)
    parser.add_argument("--mt5-path", default=None)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.bars < 100:
        raise SystemExit("--bars must be at least 100.")
    try:
        import MetaTrader5 as mt5
    except ImportError as exc:
        raise SystemExit("MetaTrader5 is available only in the local Windows environment. Install requirements.txt.") from exc

    initialized_here = False
    try:
        try:
            initialized = mt5.terminal_info() is not None
        except Exception:
            initialized = False
        if not initialized:
            initialized = bool(mt5.initialize(path=args.mt5_path) if args.mt5_path else mt5.initialize())
            initialized_here = initialized
        if not initialized:
            raise SystemExit(f"Could not initialize local MT5 terminal: {mt5.last_error()}")

        actual_symbol = resolve_mt5_symbol(args.symbol, mt5)
        if not mt5.symbol_select(actual_symbol, True):
            raise SystemExit(f"Could not select {actual_symbol}: {mt5.last_error()}")
        timeframe = getattr(mt5, f"TIMEFRAME_{args.timeframe}")
        # Start at position 1 to exclude the still-forming candle.
        rates = mt5.copy_rates_from_pos(actual_symbol, timeframe, 1, args.bars)
        if rates is None or len(rates) < 100:
            raise SystemExit(
                f"MT5 returned insufficient completed candles for {actual_symbol}: "
                f"{0 if rates is None else len(rates)}"
            )
        data = pd.DataFrame(rates)
        data["timestamp"] = pd.to_datetime(data["time"], unit="s", utc=True)
        data = data[["timestamp", "open", "high", "low", "close"]].copy()

        split = run_smc_backtest(
            data,
            actual_symbol,
            stop_distance=args.stop_distance,
            reward_multiple=args.reward_multiple,
            spread=args.spread,
            slippage=args.slippage,
            commission_per_unit_per_side=args.commission_per_unit_per_side,
            position_size=args.position_size,
            initial_equity=args.initial_equity,
            train_fraction=args.train_fraction,
        )

        def show(label, result):
            print(f"\n{label}")
            print("-" * len(label))
            print(f"Bars evaluated: {result.bars_evaluated}")
            print(f"Trades: {len(result.trades)}")
            print(f"Wins / losses / breakeven: {result.winning_trades} / {result.losing_trades} / {result.breakeven_trades}")
            print(f"Win rate: {result.win_rate:.2f}%")
            print(f"Profit factor: {'n/a' if result.profit_factor is None else f'{result.profit_factor:.3f}'}")
            print(f"Gross P/L: {result.total_gross_profit:.2f}")
            print(f"Costs: {result.total_costs:.2f}")
            print(f"Net P/L: {result.total_net_profit:.2f}")
            print(f"Max drawdown: {result.max_drawdown:.2f} ({result.max_drawdown_pct:.2f}%)")
            print(f"Ending equity: {result.ending_equity:.2f}")

        print(f"Symbol: {actual_symbol} | Timeframe: {args.timeframe} | Candles: {len(data)}")
        print(f"Data range UTC: {data['timestamp'].iloc[0]} to {data['timestamp'].iloc[-1]}")
        print(f"Holdout split UTC: {split.split_timestamp}")
        show("IN-SAMPLE TRAIN", split.train)
        show("OUT-OF-SAMPLE HOLDOUT", split.test)
        print("\nRESEARCH LIMITATIONS")
        print("- SMC signals are exploratory and are not approved strategy rules.")
        print("- Historical high-impact news dates are not filtered automatically; manually verify event data.")
        print("- Spread, slippage, commission and fixed stop distance must reflect the broker/instrument.")
        print("- This is candle-based simulation, not tick-level execution or a profit guarantee.")
        return 0
    finally:
        if initialized_here:
            mt5.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
