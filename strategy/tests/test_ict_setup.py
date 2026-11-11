from types import SimpleNamespace

import pandas as pd

from strategy.ict_setup import scan_ict_markets


def make_data(start, count, base=100.0):
    times = pd.date_range(start, periods=count, freq="15min", tz="UTC")
    rows = []
    for i, stamp in enumerate(times):
        price = base + i * 0.01
        rows.append((stamp, price, price + 0.04, price - 0.04, price + 0.005))
    return pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close"])


def test_multi_market_scanner_handles_missing_htf_and_returns_rejected_candidate():
    execution = {"EURUSD": make_data("2026-06-10 13:00", 40),
                 "XAUUSD": make_data("2026-06-10 13:00", 40, 2300)}
    htf = {"EURUSD": make_data("2026-06-01 00:00", 25)}
    results = scan_ict_markets(execution, htf)
    assert len(results) == 1
    assert results[0].symbol == "EURUSD"
    assert not results[0].valid
    assert results[0].rejections


def test_scanner_is_deterministic_and_keeps_symbol_identity():
    execution = {"GBPUSD": make_data("2026-06-10 13:00", 40),
                 "EURUSD": make_data("2026-06-10 13:00", 40)}
    htf = {symbol: make_data("2026-06-01 00:00", 25) for symbol in execution}
    results = scan_ict_markets(execution, htf)
    assert {item.symbol for item in results} == {"GBPUSD", "EURUSD"}
    assert all(not item.valid for item in results)
