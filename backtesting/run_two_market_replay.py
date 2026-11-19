"""CLI for an auditable, offline two-market historical replay.

Usage:
python -m backtesting.run_two_market_replay --eurusd EURUSD_M15.csv --gold XAUUSD_M15.csv --specs broker_specs.json --out replay.json

Broker specs JSON must map EURUSD and XAUUSD to fields accepted by Instrument.
Data timestamps are UTC bar opening timestamps. No MT5 broker orders.
The included candidate is a deliberately simple, unvalidated sweep/reclaim
baseline, NOT the full multi-timeframe ICT strategy.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from backtesting.two_market_replay import Instrument, replay, save_replay


def sweep_reclaim_candidate(symbol, history):
    """Causal, test-only baseline: previous ten-bar sweep/reclaim and 2R target.

    Returns a trade candidate only if the current completed candle sweeps the
    previous ten bars and closes back inside the prior extreme. Stop is beyond
    the sweep candle. This is NOT a confirmed MSS/FVG/OB strategy.
    """
    if len(history) < 11:
        return None
    previous = history.iloc[-11:-1]
    bar = history.iloc[-1]
    prior_low = float(previous.low.min())
    prior_high = float(previous.high.max())
    low, high, close = float(bar.low), float(bar.high), float(bar.close)
    if low < prior_low < close:
        stop = low
        distance = close - stop
        if distance > 0:
            return dict(side="buy", stop=stop, target=close + 3 * distance)
    if high > prior_high > close:
        stop = high
        distance = stop - close
        if distance > 0:
            return dict(side="sell", stop=stop, target=close - 3 * distance)
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline EURUSD/XAUUSD simulated replay")
    parser.add_argument("--eurusd", required=True, help="UTC OHLC CSV")
    parser.add_argument("--gold", required=True, help="UTC OHLC CSV")
    parser.add_argument("--specs", required=True, help="Verified broker contract/cost settings JSON")
    parser.add_argument("--out", default="two_market_replay.json")
    parser.add_argument("--start", default="2026-01-01T00:00:00Z")
    parser.add_argument("--balance", type=float, default=500.0)
    args = parser.parse_args(argv)
    raw = json.loads(Path(args.specs).read_text(encoding="utf-8"))
    if set(raw) != {"EURUSD", "XAUUSD"}:
        parser.error("Specs must contain exactly EURUSD and XAUUSD")
    instruments = {s: Instrument(symbol=s, **raw[s]) for s in raw}
    candles = {"EURUSD": pd.read_csv(args.eurusd), "XAUUSD": pd.read_csv(args.gold)}
    result = replay(candles, instruments, sweep_reclaim_candidate,
                    starting_zar=args.balance, start=args.start)
    save_replay(result, args.out)
    print(json.dumps({
        "mode": "UNVALIDATED SWEEP/RECLAIM BASELINE; HISTORICAL SIMULATION ONLY",
        "start": args.start, "starting_zar": result["starting_zar"],
        "ending_balance_zar": result["ending_balance_zar"],
        "closed_trades": len(result["closed_trades"]),
        "open_positions": len(result["open_positions"]),
        "output": args.out,
    }, indent=2))


if __name__ == "__main__":
    main()
