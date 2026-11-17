from datetime import datetime, timezone
from types import SimpleNamespace

import pandas as pd
import pytest

from market_data.mt5_history import MT5History


class FakeMT5:
    TIMEFRAME_M15 = 15

    def __init__(self, symbols, rates=None):
        self.symbols = symbols
        self.rates = rates if rates is not None else []
        self.selected = []
        self.requested = []

    def symbol_info(self, name):
        return next(
            (item for item in self.symbols if item.name.upper() == name.upper()),
            None,
        )

    def symbols_get(self):
        return self.symbols

    def symbol_select(self, name, enabled):
        self.selected.append((name, enabled))
        return True

    def copy_rates_range(self, name, timeframe, start, end):
        self.requested.append((name, timeframe, start, end))
        return self.rates

    def last_error(self):
        return (0, "no error")

    def initialize(self, path=None):
        return True

    def shutdown(self):
        return None


def gold_symbol(name="XAUUSD.a", base="XAU", profit="USD"):
    return SimpleNamespace(
        name=name,
        currency_base=base,
        currency_profit=profit,
    )


def test_history_fetch_resolves_broker_alias_but_uses_gold_data():
    rates = [{
        "time": 1_800_000_000,
        "open": 2000.0,
        "high": 2005.0,
        "low": 1995.0,
        "close": 2002.0,
        "tick_volume": 100,
    }]
    mt5 = FakeMT5([gold_symbol()], rates=rates)
    history = MT5History(mt5_module=mt5)

    result = history.fetch(
        "XAUUSD",
        "M15",
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        datetime(2026, 1, 2, tzinfo=timezone.utc),
    )

    assert list(result.columns) == [
        "timestamp", "open", "high", "low", "close", "volume"
    ]
    assert len(result) == 1
    assert mt5.selected == [("XAUUSD.a", True)]
    assert mt5.requested[0][0:2] == ("XAUUSD.a", mt5.TIMEFRAME_M15)


@pytest.mark.parametrize("symbol", ["EURUSD", "GBPUSD", "BTCUSD", "XAUUSD.a"])
def test_history_rejects_noncanonical_symbol(symbol):
    mt5 = FakeMT5([gold_symbol()])
    history = MT5History(mt5_module=mt5)

    with pytest.raises(ValueError, match="XAUUSD"):
        history.fetch(
            symbol,
            "M15",
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 1, 2, tzinfo=timezone.utc),
        )


def test_history_rejects_unknown_timeframe():
    mt5 = FakeMT5([gold_symbol()])
    history = MT5History(mt5_module=mt5)

    with pytest.raises(ValueError, match="Unsupported timeframe"):
        history.fetch(
            "XAUUSD",
            "W1",
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 1, 2, tzinfo=timezone.utc),
        )
