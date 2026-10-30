import pandas as pd
import pytest

from backtesting.market_runner import run_walk_forward


def sample_data(count=10):
    timestamps = pd.date_range(
        "2026-01-01",
        periods=count,
        freq="h",
        tz="UTC",
    )

    return pd.DataFrame({
        "timestamp": timestamps,
        "open": [100.0] * count,
        "high": [100.5] * count,
        "low": [99.5] * count,
        "close": [100.1] * count,
        "volume": [100] * count,
    })


def no_signal(history):
    return None


def test_walk_forward_uses_chronological_expanding_windows():
    data = sample_data()

    folds = run_walk_forward(
        dataframe=data,
        symbol="EURUSD",
        signal_fn=no_signal,
        initial_train_bars=4,
        test_bars=2,
        stop_distance=1.0,
        reward_multiple=2.0,
        spread=0.0,
        slippage=0.0,
        commission_per_unit_per_side=0.0,
        initial_equity=1000.0,
    )

    assert len(folds) == 3

    assert [fold.fold_number for fold in folds] == [1, 2, 3]
    assert [fold.train_bars for fold in folds] == [4, 6, 8]
    assert [fold.test_bars for fold in folds] == [2, 2, 2]

    for index, fold in enumerate(folds):
        expected_start = data.iloc[4 + index * 2]["timestamp"]
        expected_end = data.iloc[5 + index * 2]["timestamp"]

        assert fold.test_start == expected_start
        assert fold.test_end == expected_end
        assert fold.result.split_timestamp == expected_start


def test_walk_forward_rejects_insufficient_training_data():
    with pytest.raises(ValueError, match="Not enough candles"):
        run_walk_forward(
            dataframe=sample_data(5),
            symbol="EURUSD",
            signal_fn=no_signal,
            initial_train_bars=5,
            test_bars=2,
            stop_distance=1.0,
            spread=0.0,
            slippage=0.0,
            commission_per_unit_per_side=0.0,
        )


def test_walk_forward_rejects_invalid_window_sizes():
    with pytest.raises(ValueError, match="initial_train_bars"):
        run_walk_forward(
            dataframe=sample_data(),
            symbol="EURUSD",
            signal_fn=no_signal,
            initial_train_bars=1,
            test_bars=2,
            stop_distance=1.0,
            spread=0.0,
            slippage=0.0,
            commission_per_unit_per_side=0.0,
        )

    with pytest.raises(ValueError, match="test_bars"):
        run_walk_forward(
            dataframe=sample_data(),
            symbol="EURUSD",
            signal_fn=no_signal,
            initial_train_bars=4,
            test_bars=0,
            stop_distance=1.0,
            spread=0.0,
            slippage=0.0,
            commission_per_unit_per_side=0.0,
        )


def test_walk_forward_rejects_missing_market_columns():
    data = sample_data().drop(columns=["high"])

    with pytest.raises(ValueError, match="missing columns"):
        run_walk_forward(
            dataframe=data,
            symbol="EURUSD",
            signal_fn=no_signal,
            initial_train_bars=4,
            test_bars=2,
            stop_distance=1.0,
            spread=0.0,
            slippage=0.0,
            commission_per_unit_per_side=0.0,
        )
