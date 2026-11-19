"""Read-only local Windows MT5 history export for EURUSD and XAUUSD.

No login credentials are stored and no MT5 orders are sent.
Run: python -m backtesting.export_mt5_history --start 2025-12-01 --end 2026-11-19
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from market_data.mt5_history import MT5History, save_history


def _utc_date(text):
    return datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def export_history(start, end, directory="market_data/storage", mt5_module=None):
    if start.tzinfo is None or end.tzinfo is None or start >= end:
        raise ValueError("Require ordered timezone-aware start/end")
    history = MT5History(mt5_module=mt5_module)
    exported = {}
    history.connect()
    try:
        for symbol in ("EURUSD", "XAUUSD"):
            for timeframe in ("M15", "H1", "H4", "D1"):
                frame = history.fetch(symbol, timeframe, start, end)
                if frame.empty:
                    raise ValueError(f"No MT5 history for {symbol} {timeframe}; check broker history availability")
                exported[f"{symbol}_{timeframe}"] = save_history(
                    frame, symbol, timeframe, directory=directory
                )
    finally:
        history.shutdown()
    return exported


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2025-12-01")
    parser.add_argument("--end", required=True, help="Exclusive end date YYYY-MM-DD UTC")
    parser.add_argument("--out", default="market_data/storage")
    args = parser.parse_args(argv)
    paths = export_history(_utc_date(args.start), _utc_date(args.end), args.out)
    for key, path in paths.items():
        print(f"{key}: {path}")
    print("Read-only export completed. No MT5 orders placed.")


if __name__ == "__main__":
    main()
