from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import pandas as pd

from backtesting.cost_aware_engine import (
    CostAwareBacktestEngine,
    CostAwareSplitResult,
)
from market_data.mt5_history import MT5History, save_history


SignalFunction = Callable[[pd.DataFrame], Optional[str]]


@dataclass(frozen=True)
class WalkForwardFold:
    fold_number: int
    train_bars: int
    test_bars: int
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    result: CostAwareSplitResult


def run_mt5_backtest(
    symbol: str,
    timeframe: str,
    start: datetime,
    end: datetime,
    signal_fn: SignalFunction,
    *,
    stop_distance: float,
    reward_multiple: float = 2.0,
    spread: float,
    slippage: float,
    commission_per_unit_per_side: float,
    position_size: float = 1.0,
    initial_equity: float = 10_000.0,
    train_fraction: float = 0.70,
    save_directory: Optional[str] = None,
) -> CostAwareSplitResult:
    """
    Download candles from MT5 and run a cost-aware chronological
    train/test backtest.

    Costs must be supplied by the caller. Do not assume that zero
    spread, slippage, or commission represents real broker conditions.
    """
    history = MT5History()

    history.connect()
    try:
        dataframe = history.fetch(
            symbol=symbol,
            timeframe=timeframe,
            start=start,
            end=end,
        )
    finally:
        history.shutdown()

    if dataframe.empty:
        raise ValueError(
            f"MT5 returned no historical candles for {symbol} {timeframe}."
        )

    required = {"timestamp", "open", "high", "low", "close"}
    missing = required - set(dataframe.columns)
    if missing:
        raise ValueError(
            f"Historical data is missing columns: {sorted(missing)}"
        )

    dataframe = dataframe.sort_values("timestamp").reset_index(drop=True)

    if save_directory is not None:
        save_history(
            dataframe,
            symbol=symbol,
            timeframe=timeframe,
            directory=save_directory,
        )

    engine = CostAwareBacktestEngine()
    return engine.run_train_test(
        dataframe=dataframe,
        symbol=symbol,
        signal_fn=signal_fn,
        train_fraction=train_fraction,
        stop_distance=stop_distance,
        reward_multiple=reward_multiple,
        spread=spread,
        slippage=slippage,
        commission_per_unit_per_side=commission_per_unit_per_side,
        position_size=position_size,
        initial_equity=initial_equity,
    )


def run_walk_forward(
    dataframe: pd.DataFrame,
    symbol: str,
    signal_fn: SignalFunction,
    *,
    initial_train_bars: int,
    test_bars: int,
    step_bars: Optional[int] = None,
    stop_distance: float,
    reward_multiple: float = 2.0,
    spread: float,
    slippage: float,
    commission_per_unit_per_side: float,
    position_size: float = 1.0,
    initial_equity: float = 10_000.0,
) -> list[WalkForwardFold]:
    """
    Run expanding-window walk-forward tests.

    Each fold trains on all candles before its test window. The test
    window is evaluated chronologically, with earlier candles retained
    as signal warmup by run_train_test().
    """
    if not isinstance(dataframe, pd.DataFrame):
        raise TypeError("dataframe must be a pandas DataFrame.")

    if initial_train_bars < 2:
        raise ValueError("initial_train_bars must be at least 2.")

    if test_bars < 1:
        raise ValueError("test_bars must be at least 1.")

    if step_bars is None:
        step_bars = test_bars

    if step_bars < 1:
        raise ValueError("step_bars must be at least 1.")

    required = {"timestamp", "open", "high", "low", "close"}
    missing = required - set(dataframe.columns)
    if missing:
        raise ValueError(
            f"Historical data is missing columns: {sorted(missing)}"
        )

    data = (
        dataframe.sort_values("timestamp")
        .reset_index(drop=True)
        .copy()
    )

    if len(data) <= initial_train_bars:
        raise ValueError(
            "Not enough candles: data must include training bars "
            "and at least one test candle."
        )

    engine = CostAwareBacktestEngine()
    folds: list[WalkForwardFold] = []
    fold_number = 1

    for test_start_index in range(
        initial_train_bars,
        len(data),
        step_bars,
    ):
        test_end_index = min(
            test_start_index + test_bars,
            len(data),
        )

        window = data.iloc[:test_end_index].copy()
        train_fraction = (
            test_start_index + 0.5
        ) / test_end_index

        result = engine.run_train_test(
            dataframe=window,
            symbol=symbol,
            signal_fn=signal_fn,
            train_fraction=train_fraction,
            stop_distance=stop_distance,
            reward_multiple=reward_multiple,
            spread=spread,
            slippage=slippage,
            commission_per_unit_per_side=commission_per_unit_per_side,
            position_size=position_size,
            initial_equity=initial_equity,
        )

        folds.append(
            WalkForwardFold(
                fold_number=fold_number,
                train_bars=test_start_index,
                test_bars=test_end_index - test_start_index,
                test_start=pd.Timestamp(
                    data.iloc[test_start_index]["timestamp"]
                ),
                test_end=pd.Timestamp(
                    data.iloc[test_end_index - 1]["timestamp"]
                ),
                result=result,
            )
        )

        fold_number += 1

    return folds
