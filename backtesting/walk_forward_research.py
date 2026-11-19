"""Walk-forward comparison of causal sweep baselines on offline candles.

Research-only parameter selection; do not reuse holdout to tune parameters.
The full ICT model is NOT learned by this module.
"""
from __future__ import annotations

import pandas as pd

from backtesting.two_market_replay import replay


def sweep_parameter_signal(lookback):
    if not isinstance(lookback, int) or lookback < 2:
        raise ValueError("lookback must be an integer >= 2")

    def signal(symbol, history):
        if len(history) < lookback + 1:
            return None
        earlier = history.iloc[-lookback - 1:-1]
        last = history.iloc[-1]
        low, high = float(earlier.low.min()), float(earlier.high.max())
        close = float(last.close)
        if float(last.low) < low < close:
            stop = float(last.low)
            return {"side": "buy", "stop": stop, "target": close + 3 * (close - stop)}
        if float(last.high) > high > close:
            stop = float(last.high)
            return {"side": "sell", "stop": stop, "target": close - 3 * (stop - close)}
        return None

    return signal


def walk_forward_compare(candles, instruments, *, lookbacks=(5, 10, 20),
                         starting_zar=500, train_fraction=0.6,
                         validation_fraction=0.2):
    """Select on validation only; report untouched later test separately.

    All input frames must cover a shared, UTC-ordered period. Training is
    intentionally not used to fit this fixed-rule baseline. The validation
    window selects lookback; test remains untouched until selection is frozen.
    """
    if not 0 < train_fraction < 1 or not 0 < validation_fraction < 1 or train_fraction + validation_fraction >= 1:
        raise ValueError("Invalid chronological split fractions")
    if not candles:
        raise ValueError("No data")
    timeline = sorted(set.intersection(*[
        set(pd.to_datetime(df.timestamp, utc=True)) for df in candles.values()
    ]))
    if len(timeline) < 30:
        raise ValueError("At least 30 common timestamps required")
    train_end = timeline[int(len(timeline) * train_fraction)]
    valid_end = timeline[int(len(timeline) * (train_fraction + validation_fraction))]
    # Prefix warmup is preserved; truncate at split boundaries. A pending
    # signal cannot fill after the end of a truncated validation segment.
    validation = {
        s: df.loc[(pd.to_datetime(df.timestamp, utc=True) <= valid_end)].copy()
        for s, df in candles.items()
    }
    results = {}
    for lookback in lookbacks:
        fn = sweep_parameter_signal(lookback)
        output = replay(validation, instruments, fn, starting_zar=starting_zar,
                        start=train_end.isoformat())
        results[lookback] = output["ending_balance_zar"] - starting_zar
    best = sorted(results, key=lambda k: (-results[k], k))[0]
    # Test replay with full warmup; only trades from test start count.
    test = replay(candles, instruments, sweep_parameter_signal(best),
                  starting_zar=starting_zar, start=valid_end.isoformat())
    return {
        "method": "chronological validation selection / untouched test",
        "train_end_utc": train_end.isoformat(),
        "validation_end_utc": valid_end.isoformat(),
        "validation_net_zar_by_lookback": results,
        "selected_lookback": best,
        "test_result": test,
        "note": "Fixed-rule baseline comparison, not self-learning ICT or proof of profitability",
    }
