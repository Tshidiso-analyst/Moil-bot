import pandas as pd

from backtesting.run_two_market_replay import sweep_reclaim_candidate


def test_sweep_baseline_requires_completed_history():
    rows = [
        dict(timestamp=f"2025-12-{i+1:02d}T00:00:00Z", open=100, high=101, low=99, close=100)
        for i in range(10)
    ]
    assert sweep_reclaim_candidate("EURUSD", pd.DataFrame(rows)) is None
    rows.append(dict(timestamp="2026-01-01T00:00:00Z", open=100, high=100.5, low=98, close=100))
    signal = sweep_reclaim_candidate("EURUSD", pd.DataFrame(rows))
    assert signal == {"side": "buy", "stop": 98.0, "target": 106.0}


def test_sweep_baseline_ignores_non_sweep():
    rows = [dict(open=100, high=101, low=99, close=100) for _ in range(11)]
    assert sweep_reclaim_candidate("XAUUSD", pd.DataFrame(rows)) is None
