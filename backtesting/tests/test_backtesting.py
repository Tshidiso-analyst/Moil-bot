import pandas as pd
import pytest

from backtesting.engine import BacktestEngine
from backtesting.metrics import calculate_profit_factor
from backtesting.replay import MarketReplay


def bullish_data():
    return pd.DataFrame(
        {
            "timestamp": pd.date_range(
                "2026-01-01",
                periods=5,
                freq="h",
            ),
            "open": [
                100,
                100.5,
                101,
                102,
                103,
            ],
            "high": [
                100.5,
                101,
                102,
                103,
                105,
            ],
            "low": [
                99.8,
                100.2,
                100.8,
                101.8,
                102.8,
            ],
            "close": [
                100,
                100.8,
                101.5,
                102.5,
                104,
            ],
        }
    )


def bearish_data():
    return pd.DataFrame(
        {
            "timestamp": pd.date_range(
                "2026-01-01",
                periods=5,
                freq="h",
            ),
            "open": [
                100,
                99.5,
                99,
                98,
                97,
            ],
            "high": [
                100.2,
                99.8,
                99.2,
                98.2,
                97.2,
            ],
            "low": [
                99.5,
                99,
                98,
                97,
                95,
            ],
            "close": [
                100,
                99.2,
                98.5,
                97.5,
                96,
            ],
        }
    )


def test_bullish_backtest():
    result = BacktestEngine().run(
        bullish_data(),
        symbol="AAPL",
        direction="bullish",
        stop_distance=0.5,
        reward_multiple=2,
    )

    assert len(result.trades) >= 1
    assert result.winning_trades >= 1


def test_bearish_backtest():
    result = BacktestEngine().run(
        bearish_data(),
        symbol="US30",
        direction="bearish",
        stop_distance=0.5,
        reward_multiple=2,
    )

    assert len(result.trades) >= 1
    assert result.winning_trades >= 1


def test_empty_backtest():
    result = BacktestEngine().run(
        pd.DataFrame(),
        symbol="NVDA",
        direction="bullish",
    )

    assert result.total_profit == 0
    assert result.win_rate == 0


def test_profit_factor():
    result = BacktestEngine().run(
        bullish_data(),
        symbol="AAPL",
        direction="bullish",
        stop_distance=0.5,
        reward_multiple=2,
    )

    factor = calculate_profit_factor(result)

    assert factor >= 0


def test_replay():
    replay = MarketReplay(bullish_data())

    candles = list(replay.candles())

    assert len(candles) == 5
    assert candles[0].index == 0
    assert candles[-1].index == 4


def test_invalid_direction():
    with pytest.raises(ValueError):
        BacktestEngine().run(
            bullish_data(),
            symbol="TSLA",
            direction="sideways",
        )
