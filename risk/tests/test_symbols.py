import pytest

from risk.symbols import canonicalize_symbol


@pytest.mark.parametrize("symbol", ["XAUUSD", "xauusd", "XAUUSD.a", "XAUUSDm", "XAUUSD-pro"])
def test_supported_broker_symbols_map_to_canonical_xauusd(symbol):
    assert canonicalize_symbol(symbol) == "XAUUSD"


@pytest.mark.parametrize("symbol", ["EURUSD", "XAUUSDJPY", "GOLD", "XAUUSD.a;EURUSD"])
def test_other_or_ambiguous_symbols_are_rejected(symbol):
    with pytest.raises(ValueError, match="XAUUSD only"):
        canonicalize_symbol(symbol)



def test_empty_symbol_has_specific_validation_error():
    with pytest.raises(ValueError, match="must not be empty"):
        canonicalize_symbol("")
