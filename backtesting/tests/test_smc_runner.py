from types import SimpleNamespace

import pandas as pd

from backtesting.cost_aware_engine import CostAwareBacktestEngine
from backtesting.smc_runner import make_smc_signal_function


class AlwaysConfirmed:
    def assess(self, symbol, history, **kwargs):
        return SimpleNamespace(setup_valid=True, direction="bullish")


def _history(timestamp):
    return pd.DataFrame({
        "timestamp": [pd.Timestamp(timestamp)],
        "open": [1.1], "high": [1.101], "low": [1.099], "close": [1.1],
    })


def test_smc_signal_is_limited_to_first_nyse_hour_but_allows_multiple_setups():
    signal = make_smc_signal_function("XAUUSD", decision_engine=AlwaysConfirmed())

    assert signal(_history("2026-06-10 13:15:00+00:00")) is None  # 09:15 NY
    assert signal(_history("2026-06-10 13:30:00+00:00")) == "bullish"  # 09:30 NY
    assert signal(_history("2026-06-10 14:00:00+00:00")) == "bullish"  # 10:00 NY
    assert signal(_history("2026-06-10 14:15:00+00:00")) == "bullish"  # 10:15 NY
    assert signal(_history("2026-06-10 14:30:00+00:00")) is None  # 10:30 NY


def test_cost_aware_engine_can_configure_a_daily_limit():
    data = pd.DataFrame([
        ("2026-06-10 13:30:00+00:00", 100, 100.2, 99.8, 100),
        ("2026-06-10 13:45:00+00:00", 100, 103, 99.8, 102.5),
        ("2026-06-10 14:00:00+00:00", 102.5, 105, 102, 104),
        ("2026-06-11 13:30:00+00:00", 104, 104.2, 103.8, 104),
        ("2026-06-11 13:45:00+00:00", 104, 107, 103.8, 106.5),
    ], columns=["timestamp", "open", "high", "low", "close"])
    data["timestamp"] = pd.to_datetime(data["timestamp"], utc=True)

    result = CostAwareBacktestEngine().run(
        data, "TEST", lambda history: "bullish",
        stop_distance=1, reward_multiple=2,
        max_trades_per_day=1, trading_timezone="America/New_York",
    )
    assert len(result.trades) == 2
    entry_days = [
        trade.entry_time.tz_convert("America/New_York").date()
        for trade in result.trades
    ]
    assert len(entry_days) == len(set(entry_days))


def test_cost_aware_engine_rejects_invalid_daily_limit_and_timezone():
    import pytest

    data = pd.DataFrame([
        ("2026-06-10 14:30:00+00:00", 100, 100.2, 99.8, 100),
        ("2026-06-10 14:45:00+00:00", 100, 100.2, 99.8, 100),
    ], columns=["timestamp", "open", "high", "low", "close"])
    data["timestamp"] = pd.to_datetime(data["timestamp"], utc=True)

    with pytest.raises(ValueError, match="max_trades_per_day"):
        CostAwareBacktestEngine().run(
            data, "TEST", lambda _: None, stop_distance=1, max_trades_per_day=0
        )
    with pytest.raises(ValueError, match="trading_timezone"):
        CostAwareBacktestEngine().run(
            data, "TEST", lambda _: None, stop_distance=1, trading_timezone="Not/A_Timezone"
        )
