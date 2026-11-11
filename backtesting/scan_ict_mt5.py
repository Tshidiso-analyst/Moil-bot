"""Scan broker-available MT5 instruments for explainable ICT candidates.

Research only: this command never submits or modifies orders.
"""
from __future__ import annotations

import argparse

import pandas as pd

from market_data.instrument_universe import discover_instruments
from strategy.ict_setup import scan_ict_markets


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scan MT5 markets using the ICT research model")
    parser.add_argument("--timeframe", default="M15", choices=("M5", "M15", "M30"))
    parser.add_argument("--higher-timeframe", default="H1", choices=("M30", "H1", "H4", "D1"))
    parser.add_argument("--bars", type=int, default=500)
    parser.add_argument("--include-unwatchlisted", action="store_true")
    parser.add_argument("--mt5-path", default=None)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.bars < 100:
        raise SystemExit("--bars must be at least 100.")
    try:
        import MetaTrader5 as mt5
    except ImportError as exc:
        raise SystemExit("MetaTrader5 is available only in the local Windows environment.") from exc

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
            raise SystemExit(f"Could not initialize MT5: {mt5.last_error()}")

        instruments = discover_instruments(mt5, include_unwatchlisted=args.include_unwatchlisted)
        if not instruments:
            raise SystemExit("No supported instruments were discovered in this broker's Market Watch/catalogue.")

        execution: dict[str, pd.DataFrame] = {}
        higher: dict[str, pd.DataFrame] = {}
        for instrument in instruments:
            symbol = instrument.broker_symbol
            if not mt5.symbol_select(symbol, True):
                continue
            for timeframe_name, destination in ((args.timeframe, execution), (args.higher_timeframe, higher)):
                timeframe = getattr(mt5, f"TIMEFRAME_{timeframe_name}")
                rates = mt5.copy_rates_from_pos(symbol, timeframe, 1, args.bars)
                if rates is None or len(rates) < 30:
                    continue
                frame = pd.DataFrame(rates)
                frame["timestamp"] = pd.to_datetime(frame["time"], unit="s", utc=True)
                destination[instrument.canonical] = frame[["timestamp", "open", "high", "low", "close"]].copy()

        results = scan_ict_markets(execution, higher)
        print(f"Discovered instruments: {len(instruments)}")
        print(f"Loaded {args.timeframe}: {len(execution)} | Loaded {args.higher_timeframe}: {len(higher)}")
        print("RESEARCH CANDIDATES — NO ORDERS WILL BE PLACED")
        if not results:
            print("No symbols had sufficient data on both timeframes.")
        for result in results:
            status = "CANDIDATE" if result.valid else "NO SETUP"
            print(f"\n{result.symbol} | {status} | {result.direction} | {result.session}")
            if result.valid:
                print(f"Entry zone midpoint: {result.entry} | SL: {result.stop_loss} | TP: {result.take_profit} | RR: {result.risk_reward:.2f}")
                for item in result.confirmations:
                    print(f"  + {item}")
            for item in result.rejections:
                print(f"  - {item}")
        return 0
    finally:
        if initialized_here:
            mt5.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
