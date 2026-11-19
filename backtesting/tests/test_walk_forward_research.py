import pandas as pd
import pytest

from backtesting.walk_forward_research import (
    sweep_parameter_signal, walk_forward_compare,
)
from backtesting.two_market_replay import Instrument


def test_parameter_signal_never_reads_future_rows():
    signal = sweep_parameter_signal(2)
    frame = pd.DataFrame([
        dict(open=100, high=101, low=99, close=100),
        dict(open=100, high=101, low=99, close=100),
        dict(open=100, high=101, low=98, close=100),
    ])
    assert signal("EURUSD", frame.iloc[:2]) is None
    assert signal("EURUSD", frame) == {
        "side": "buy", "stop": 98.0, "target": 106.0
    }


def test_walk_forward_requires_enough_common_candles():
    frame = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=5, freq="15min", tz="UTC"),
        "open": [100] * 5, "high": [101] * 5,
        "low": [99] * 5, "close": [100] * 5,
    })
    spec = Instrument("EURUSD", 0, 0, 10, 0.01, 0.01, 1)
    with pytest.raises(ValueError, match="30 common timestamps"):
        walk_forward_compare({"EURUSD": frame}, {"EURUSD": spec})


def test_walk_forward_separates_validation_and_test():
    times = pd.date_range("2026-01-01", periods=60, freq="15min", tz="UTC")
    frame = pd.DataFrame({
        "timestamp": times, "open": [100] * 60,
        "high": [101] * 60, "low": [99] * 60,
        "close": [100] * 60,
    })
    spec = Instrument("EURUSD", 0, 0, 10, 0.01, 0.01, 1)
    result = walk_forward_compare({"EURUSD": frame}, {"EURUSD": spec})
    assert result["selected_lookback"] == 5
    assert result["train_end_utc"] < result["validation_end_utc"]
    assert result["test_result"]["closed_trades"] == []
