from types import SimpleNamespace

import pytest

from market_data.instrument_universe import discover_instruments, resolve_instrument


class FakeMT5:
    def symbols_get(self):
        return [
            SimpleNamespace(name="EURUSDm", description="Euro vs US Dollar"),
            SimpleNamespace(name="XAUUSD.a", description="Gold vs US Dollar"),
            SimpleNamespace(name="GOLD.pro", description="Gold"),
            SimpleNamespace(name="USTEC", description="NASDAQ 100"),
            SimpleNamespace(name="GBPJPYm", description="British Pound vs Japanese Yen"),
        ]


def test_discovers_broker_suffixes_and_asset_classes():
    instruments = discover_instruments(FakeMT5())
    by_canonical = {item.canonical: item for item in instruments}
    assert by_canonical["EURUSD"].broker_symbol == "EURUSDm"
    assert by_canonical["XAUUSD"].broker_symbol == "XAUUSD.a"
    assert by_canonical["NAS100"].broker_symbol == "USTEC"
    assert by_canonical["GBPJPY"].asset_class == "forex"


def test_resolves_canonical_and_broker_names():
    instruments = discover_instruments(FakeMT5())
    assert resolve_instrument("XAUUSD", instruments) == "XAUUSD.a"
    assert resolve_instrument("EURUSDm", instruments) == "EURUSDm"
    with pytest.raises(ValueError, match="not available"):
        resolve_instrument("BTCUSD", instruments)
