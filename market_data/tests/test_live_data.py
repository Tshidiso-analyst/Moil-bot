from types import SimpleNamespace

import pytest

from market_data.live_data import resolve_mt5_symbol


class FakeMT5:
    def __init__(self, symbols):
        self.symbols = symbols

    def symbol_info(self, name):
        return next(
            (item for item in self.symbols if item.name.upper() == name.upper()),
            None,
        )

    def symbols_get(self):
        return self.symbols


def symbol(name, base="XAU", profit="USD"):
    return SimpleNamespace(
        name=name,
        currency_base=base,
        currency_profit=profit,
    )


def test_resolves_exact_gold_symbol():
    mt5 = FakeMT5([symbol("XAUUSD")])
    assert resolve_mt5_symbol("XAUUSD", mt5) == "XAUUSD"


def test_resolves_broker_gold_suffix():
    mt5 = FakeMT5([symbol("XAUUSD.a")])
    assert resolve_mt5_symbol("XAUUSD", mt5) == "XAUUSD.a"


def test_resolves_gold_m_suffix():
    mt5 = FakeMT5([symbol("XAUUSDm")])
    assert resolve_mt5_symbol("XAUUSD", mt5) == "XAUUSDm"


@pytest.mark.parametrize("requested", ["EURUSD", "GBPUSD", "BTCUSD", "XAUUSD.a"])
def test_rejects_noncanonical_requests(requested):
    mt5 = FakeMT5([symbol("XAUUSD.a")])
    with pytest.raises(ValueError, match="XAUUSD"):
        resolve_mt5_symbol(requested, mt5)


def test_rejects_symbol_with_conflicting_base_currency():
    mt5 = FakeMT5([symbol("XAUUSD.a", base="EUR")])
    with pytest.raises(ValueError, match="verified XAUUSD"):
        resolve_mt5_symbol("XAUUSD", mt5)


def test_rejects_symbol_with_conflicting_profit_currency():
    mt5 = FakeMT5([symbol("XAUUSD.a", profit="EUR")])
    with pytest.raises(ValueError, match="verified XAUUSD"):
        resolve_mt5_symbol("XAUUSD", mt5)


def test_does_not_match_arbitrary_substring():
    mt5 = FakeMT5([symbol("MYXAUUSD_SPECIAL")])
    with pytest.raises(ValueError, match="verified XAUUSD"):
        resolve_mt5_symbol("XAUUSD", mt5)


def test_rejects_suffix_without_gold_metadata():
    mt5 = FakeMT5([symbol("XAUUSD.pro", base="", profit="")])
    with pytest.raises(ValueError, match="verified XAUUSD"):
        resolve_mt5_symbol("XAUUSD", mt5)


def test_rejects_empty_symbol():
    mt5 = FakeMT5([])
    with pytest.raises(ValueError, match="must not be empty"):
        resolve_mt5_symbol("", mt5)
