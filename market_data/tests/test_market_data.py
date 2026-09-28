from datetime import datetime, timezone

import pandas as pd
import pytest

from market_data.models import Candle
from market_data.validation import validate_market_data


def test_candle_validation():
    candle = Candle(
        symbol="EURUSDm",
        timeframe="H1",
        timestamp=datetime.now(timezone.utc),
        open=1.1000,
        high=1.1050,
        low=1.0950,
        close=1.1020,
        volume=100,
    )

    candle.validate()


def test_invalid_candle_is_rejected():
    candle = Candle(
        symbol="EURUSDm",
        timeframe="H1",
        timestamp=datetime.now(timezone.utc),
        open=1.1100,
        high=1.1050,
        low=1.0950,
        close=1.1020,
        volume=100,
    )

    with pytest.raises(ValueError):
        candle.validate()


def test_market_data_validation():
    dataframe = pd.DataFrame(
        {
            "timestamp": pd.date_range(
                "2026-01-01",
                periods=3,
                freq="h",
            ),
            "open": [1.0, 1.1, 1.2],
            "high": [1.2, 1.3, 1.4],
            "low": [0.9, 1.0, 1.1],
            "close": [1.1, 1.2, 1.3],
            "volume": [100, 110, 120],
        }
    )

    validate_market_data(dataframe)
