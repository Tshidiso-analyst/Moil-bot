from instruments.classifier import classify_symbol


def test_forex_classification():
    assert classify_symbol("EURUSDm") == "forex"
    assert classify_symbol("GBPUSD") == "forex"
    assert classify_symbol("USDJPYm") == "forex"


def test_index_classification():
    assert classify_symbol("US30") == "index"
    assert classify_symbol("NAS100") == "index"
    assert classify_symbol("GER40") == "index"


def test_commodity_classification():
    assert classify_symbol("XAUUSD") == "commodity"
    assert classify_symbol("GOLD") == "commodity"


def test_crypto_classification():
    assert classify_symbol("BTCUSD") == "crypto"
    assert classify_symbol("ETHUSD") == "crypto"


def test_stock_classification():
    assert classify_symbol(
        "AAPL",
        "Apple Inc."
    ) == "stock_or_other"

    assert classify_symbol(
        "NVDA",
        "NVIDIA Corporation"
    ) == "stock_or_other"
