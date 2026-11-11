from types import SimpleNamespace

import pandas as pd

from backtesting.cost_aware_engine import CostAwareBacktestEngine
from backtesting.smc_runner import make_smc_signal_function


class AlwaysConfirmed:
    def assess(self, symbol, history, **kwargs):
        return SimpleNamespace(setup_valid=True, direction="bullish")


def test_smc_signal_waits_until_after_first_nyse_hour_and_only_signals_once_per_day():
    signal = make_smc_signal_function("EURUSD", decision_engine=AlwaysConfirmed())
    before_open_hour = pd.DataFrame({
        "timestamp": [pd.Timestamp("2026-06-10 13:15:00", tz="UTC")],
        "open": [1.1], "high": [1.101], "low": [1.099], "close": [1.1],
    })
    after_open_hour = pd.DataFrame({
        "timestamp": [pd.Timestamp("2026-06-10 13:30:00", tz="UTC")],
        "open": [1.1], "high": [1.101], "low": [1.099], "close": [1.1],
    })
    later_same_day = pd.DataFrame({
        "timestamp": [pd.Timestamp("2026-06-10 14:00:00", tz="UTC")],
        "open": [1.1], "high": [1.101], "low": [1.099], "close": [1.1],
    })

    assert signal(before_open_hour) is None
    assert signal(after_open_hour) == "bullish"
    assert signal(later_same_day) is None


def test_cost_aware_engine_can_limit_entries_to_one_per_new_york_day():
    data = pd.DataFrame([
        ("2026-06-10 13:30:00+00:00", 100, 100.2, 99.8, 100),
        ("2026-06-10 13:45:00+00:00", 100, 103, 99.8, 102.5),
        ("2026-06-10 14:00:00+00:00", 102.5, 105, 102, 104),
        ("2026-06-11 13:30:00+00:00", 104, 104.2, 103.8, 104),
        ("2026-06-11 13:45:00+00:00", 104, 107, 103.8, 106.5),
    ], columns=["timestamp", "open", "high", "low", "close"])
    data["timestamp"] = pd.to_datetime(data["timestamp"], utc=True)

    result = CostAwareBacktestEngine().run(
        data,
        "TEST",
        lambda history: "bullish",
        stop_distance=1,
        reward_multiple=2,
        max_trades_per_day=1,
        trading_timezone="America/New_York",
    )

    assert len(result.trades) == 2
    entry_days = [
        trade.entry_time.tz_convert("America/New_York").date()
        for trade in result.trades
    ]
    assert len(entry_days) == len(set(entry_days))


def test_cost_aware_engine_rejects_invalid_daily_limit_and_timezone():
    data = pd.DataFrame([
        ("2026-06-10 14:30:00+00:00", 100, 100.2, 99.8, 100),
        ("2026-06-10 14:45:00+00:00", 100, 100.2, 99.8, 100),
    ], columns=["timestamp", "open", "high", "low", "close"])
    data["timestamp"] = pd.to_datetime(data["timestamp"], utc=True)

    import pytest

    with pytest.raises(ValueError, match="max_trades_per_day"):
        CostAwareBacktestEngine().run(
            data, "TEST", lambda _: None, stop_distance=1, max_trades_per_day=0
        )
    with pytest.raises(ValueError, match="trading_timezone"):
        CostAwareBacktestEngine().run(
            data, "TEST", lambda _: None, stop_distance=1, trading_timezone="Not/A_Timezone"
        )
