import pandas as pd

from scanner.market_scanner import MarketScanner


def test_scanner_returns_results():
    data = {
        "EURUSDm": pd.DataFrame(
            {
                "close": [1.1000, 1.1100],
                "volume": [100, 120],
            }
        ),
        "GBPUSDm": pd.DataFrame(
            {
                "close": [1.3000, 1.2800],
                "volume": [200, 220],
            }
        ),
    }

    results = MarketScanner().scan(data)

    assert len(results) == 2
    assert results[0].symbol == "GBPUSDm"
