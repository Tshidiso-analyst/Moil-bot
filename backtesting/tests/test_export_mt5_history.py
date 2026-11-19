from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from backtesting.export_mt5_history import export_history


class FakeHistoryMT5:
    TIMEFRAME_M15 = 15
    TIMEFRAME_H1 = 60
    TIMEFRAME_H4 = 240
    TIMEFRAME_D1 = 1440

    def __init__(self):
        self.selected = []
        self.requests = []
        self.shutdown_called = False
        self.symbols = [
            SimpleNamespace(name="EURUSDm", currency_base="EUR", currency_profit="USD"),
            SimpleNamespace(name="XAUUSDm", currency_base="XAU", currency_profit="USD"),
        ]

    def initialize(self, path=None):
        return True

    def shutdown(self):
        self.shutdown_called = True

    def symbol_info(self, name):
        return None

    def symbols_get(self):
        return self.symbols

    def symbol_select(self, name, enabled):
        self.selected.append(name)
        return True

    def copy_rates_range(self, name, timeframe, start, end):
        self.requests.append((name, timeframe))
        return [dict(time=1767225600, open=100, high=101, low=99,
                     close=100.5, tick_volume=10)]

    def last_error(self):
        return (0, "OK")


def test_export_eight_datasets_with_verified_broker_aliases(tmp_path):
    fake = FakeHistoryMT5()
    result = export_history(
        datetime(2025, 12, 1, tzinfo=timezone.utc),
        datetime(2026, 2, 1, tzinfo=timezone.utc),
        directory=str(tmp_path), mt5_module=fake,
    )
    assert len(result) == 8
    assert (tmp_path / "EURUSD_M15.csv").exists()
    assert (tmp_path / "XAUUSD_D1.csv").exists()
    assert {name for name, _ in fake.requests} == {"EURUSDm", "XAUUSDm"}
    assert fake.shutdown_called


def test_export_rejects_invalid_date_order(tmp_path):
    fake = FakeHistoryMT5()
    dt = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="ordered"):
        export_history(dt, dt, directory=str(tmp_path), mt5_module=fake)
    assert fake.requests == []
