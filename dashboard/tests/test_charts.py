from datetime import datetime, timedelta

import pytest

from dashboard.charts import (
    create_price_and_volume_chart,
    create_price_chart,
    create_volume_chart,
)


def sample_candles():
    start = datetime(2026, 9, 1)

    return [
        {
            "timestamp": start,
            "open": 100,
            "high": 105,
            "low": 98,
            "close": 103,
            "volume": 1000,
        },
        {
            "timestamp": start + timedelta(hours=1),
            "open": 103,
            "high": 108,
            "low": 101,
            "close": 106,
            "volume": 1200,
        },
        {
            "timestamp": start + timedelta(hours=2),
            "open": 106,
            "high": 110,
            "low": 104,
            "close": 109,
            "volume": 1400,
        },
    ]


def test_create_price_chart():
    fig = create_price_chart(
        candles=sample_candles(),
        symbol="GBPUSD",
    )

    assert len(fig.data) == 1
    assert fig.data[0].type == "candlestick"
    assert fig.layout.xaxis.rangeslider.visible is False


def test_create_volume_chart():
    fig = create_volume_chart(
        candles=sample_candles(),
        symbol="US30",
    )

    assert len(fig.data) == 1
    assert fig.data[0].type == "bar"


def test_create_price_and_volume_chart():
    fig = create_price_and_volume_chart(
        candles=sample_candles(),
        symbol="XAUUSD",
    )

    assert len(fig.data) == 2
    assert fig.data[0].type == "candlestick"
    assert fig.data[1].type == "bar"


def test_price_chart_rejects_empty_candles():
    with pytest.raises(ValueError):
        create_price_chart([], "BTCUSD")


def test_price_chart_rejects_missing_fields():
    candles = [
        {
            "timestamp": datetime(2026, 9, 1),
            "open": 100,
            "high": 105,
            "low": 98,
        }
    ]

    with pytest.raises(ValueError):
        create_price_chart(candles, "EURUSD")
