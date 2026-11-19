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


@pytest.mark.parametrize("symbol", ["GBPUSD", "BTCUSD"])
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



def test_history_accepts_broker_alias_input_and_keeps_canonical_data_symbol():
    mt5 = FakeMT5([gold_symbol()], rates=[])
    history = MT5History(mt5_module=mt5)
    result = history.fetch(
        "XAUUSD.a",
        "M15",
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        datetime(2026, 1, 2, tzinfo=timezone.utc),
    )
    assert result.empty
    assert mt5.selected == [("XAUUSD.a", True)]

def test_eurusd_history_requires_verified_currency_metadata():
    rates = [{
        "time": 1_800_000_000, "open": 1.10, "high": 1.11,
        "low": 1.09, "close": 1.105, "tick_volume": 20,
    }]
    euro = SimpleNamespace(name="EURUSDm", currency_base="EUR", currency_profit="USD")
    mt5 = FakeMT5([gold_symbol(), euro], rates=rates)
    frame = MT5History(mt5_module=mt5).fetch(
        "EURUSD", "M15",
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        datetime(2026, 1, 2, tzinfo=timezone.utc),
    )
    assert len(frame) == 1
    assert mt5.selected == [("EURUSDm", True)]


def test_eurusd_rejects_unverified_broker_alias():
    fake = SimpleNamespace(name="EURUSDm", currency_base="GBP", currency_profit="USD")
    mt5 = FakeMT5([fake])
    with pytest.raises(ValueError, match="No verified EURUSD"):
        MT5History(mt5_module=mt5).fetch(
            "EURUSD", "M15",
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 1, 2, tzinfo=timezone.utc),
        )
