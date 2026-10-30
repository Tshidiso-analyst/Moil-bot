"""Chronological, cost-aware historical backtesting.

This module is deliberately separate from :mod:`backtesting.engine`.
Signals are supplied by the caller. The engine does not invent or approve a
trading strategy, connect to a broker, or submit orders.

A signal function receives a copy of the data available up to and including
one completed candle. If it returns ``"bullish"`` or ``"bearish"``, the trade
is entered at the *next candle's open*. Signal functions must still avoid
using features that were themselves calculated with future data.

Price assumptions:
- OHLC values are reference/mid prices.
- ``spread`` is the full bid/ask spread in price units.
- ``slippage`` is adverse slippage per side, in price units.
- ``commission_per_unit_per_side`` is commission in account-currency units
  per position unit for one side of the trade.
- P&L is returned for the supplied position size. Forex contract sizing,
  quote-to-account-currency conversion, swaps, and broker-specific fill rules
  must be modeled by the caller if relevant to its account.

If a candle reaches both stop loss and take profit and OHLC data cannot tell
which came first, stop loss is assumed to occur first (conservative rule).
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable

import pandas as pd


SignalFunction = Callable[[pd.DataFrame], str | None]
_VALID_SIGNALS = {"bullish", "bearish", "neutral", ""}
_OHLC_COLUMNS = ("open", "high", "low", "close")


@dataclass(frozen=True)
class CostAwareTrade:
    symbol: str
    direction: str
    signal_time: pd.Timestamp
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    signal_index: int
    entry_index: int
    exit_index: int
    reference_entry_price: float
    entry_fill_price: float
    reference_exit_price: float
    exit_fill_price: float
    stop_loss: float
    take_profit: float
    position_size: float
    gross_profit: float
    trading_costs: float
    commission_costs: float
    net_profit: float
    result: str
    exit_reason: str


@dataclass(frozen=True)
class CostAwareBacktestResult:
    symbol: str
    trades: list[CostAwareTrade]
    total_gross_profit: float
    total_trading_costs: float
    total_commission_costs: float
    total_costs: float
    total_net_profit: float
    winning_trades: int
    losing_trades: int
    breakeven_trades: int
    win_rate: float
    profit_factor: float | None
    max_drawdown: float
    max_drawdown_pct: float
    initial_equity: float
    ending_equity: float
    bars_evaluated: int


@dataclass(frozen=True)
class CostAwareSplitResult:
    train: CostAwareBacktestResult
    test: CostAwareBacktestResult
    train_fraction: float
    split_timestamp: pd.Timestamp


class CostAwareBacktestEngine:
    """Backtest a caller-supplied, causal signal function with trading costs."""

    def run(
        self,
        dataframe: pd.DataFrame,
        symbol: str,
        signal_fn: SignalFunction,
        *,
        stop_distance: float,
        reward_multiple: float = 2.0,
        spread: float = 0.0,
        slippage: float = 0.0,
        commission_per_unit_per_side: float = 0.0,
        position_size: float = 1.0,
        initial_equity: float = 10_000.0,
        start_index: int = 0,
        end_index: int | None = None,
    ) -> CostAwareBacktestResult:
        """Run one segment of data in timestamp order.

        ``start_index`` is inclusive and ``end_index`` is exclusive, both
        referring to the sorted candles. For an out-of-sample run, callers can
        set ``start_index`` to the split index while retaining earlier candles
        as indicator warm-up. No trades are opened before ``start_index``.
        """
        clean_symbol = str(symbol).strip().upper()
        if not clean_symbol:
            raise ValueError("symbol must not be empty.")
        if not callable(signal_fn):
            raise ValueError("signal_fn must be callable.")
        self._validate_positive("stop_distance", stop_distance)
        self._validate_positive("reward_multiple", reward_multiple)
        self._validate_nonnegative("spread", spread)
        self._validate_nonnegative("slippage", slippage)
        self._validate_nonnegative(
            "commission_per_unit_per_side", commission_per_unit_per_side
        )
        self._validate_positive("position_size", position_size)
        self._validate_positive("initial_equity", initial_equity)

        data = self._prepare_data(dataframe)
        n = len(data)
        if end_index is None:
            end_index = n
        if isinstance(start_index, bool) or not isinstance(start_index, int):
            raise ValueError("start_index must be an integer.")
        if isinstance(end_index, bool) or not isinstance(end_index, int):
            raise ValueError("end_index must be an integer.")
        if start_index < 0 or start_index > n:
            raise ValueError("start_index is outside the dataset.")
        if end_index < 0 or end_index > n:
            raise ValueError("end_index is outside the dataset.")
        if end_index < start_index:
            raise ValueError("end_index must be >= start_index.")

        if n == 0 or end_index - start_index < 2:
            return self._summarize(clean_symbol, [], initial_equity, 0)

        trades: list[CostAwareTrade] = []
        i = start_index
        bars_evaluated = 0

        # A signal at i enters at the following bar's open, so i must be
        # strictly before end_index - 1.
        while i < end_index - 1:
            history = data.iloc[: i + 1].copy(deep=True)
            bars_evaluated += 1
            raw_signal = signal_fn(history)
            if raw_signal is None:
                i += 1
                continue
            if not isinstance(raw_signal, str):
                raise ValueError(
                    "signal_fn must return 'bullish', 'bearish', 'neutral', or None."
                )
            signal = raw_signal.strip().lower()
            if signal not in _VALID_SIGNALS:
                raise ValueError(
                    "signal_fn must return 'bullish', 'bearish', 'neutral', or None."
                )
            if signal in {"neutral", ""}:
                i += 1
                continue

            entry_index = i + 1
            entry_row = data.iloc[entry_index]
            entry_reference = float(entry_row["open"])
            if signal == "bullish":
                stop_loss = entry_reference - float(stop_distance)
                take_profit = entry_reference + float(stop_distance) * float(reward_multiple)
                entry_fill = entry_reference + float(spread) / 2.0 + float(slippage)
            else:
                stop_loss = entry_reference + float(stop_distance)
                take_profit = entry_reference - float(stop_distance) * float(reward_multiple)
                entry_fill = entry_reference - float(spread) / 2.0 - float(slippage)

            exit_index = end_index - 1
            exit_reference = float(data.iloc[exit_index]["close"])
            exit_reason = "end_of_data"

            # Scan the entry candle onward. Without tick data, if stop and
            # target occur in the same candle the stop is taken first.
            for j in range(entry_index, end_index):
                candle = data.iloc[j]
                o = float(candle["open"])
                h = float(candle["high"])
                l = float(candle["low"])

                if signal == "bullish":
                    # A gap through the stop fills at the worse opening price.
                    if o <= stop_loss:
                        exit_reference, exit_index, exit_reason = o, j, "stop_loss_gap"
                        break
                    if o >= take_profit:
                        exit_reference, exit_index, exit_reason = take_profit, j, "take_profit_gap"
                        break
                    if l <= stop_loss and h >= take_profit:
                        exit_reference, exit_index, exit_reason = stop_loss, j, "stop_loss_ambiguous_candle"
                        break
                    if l <= stop_loss:
                        exit_reference, exit_index, exit_reason = stop_loss, j, "stop_loss"
                        break
                    if h >= take_profit:
                        exit_reference, exit_index, exit_reason = take_profit, j, "take_profit"
                        break
                else:
                    if o >= stop_loss:
                        exit_reference, exit_index, exit_reason = o, j, "stop_loss_gap"
                        break
                    if o <= take_profit:
                        exit_reference, exit_index, exit_reason = take_profit, j, "take_profit_gap"
                        break
                    if h >= stop_loss and l <= take_profit:
                        exit_reference, exit_index, exit_reason = stop_loss, j, "stop_loss_ambiguous_candle"
                        break
                    if h >= stop_loss:
                        exit_reference, exit_index, exit_reason = stop_loss, j, "stop_loss"
                        break
                    if l <= take_profit:
                        exit_reference, exit_index, exit_reason = take_profit, j, "take_profit"
                        break

            if signal == "bullish":
                exit_fill = exit_reference - float(spread) / 2.0 - float(slippage)
                gross_profit = (exit_reference - entry_reference) * float(position_size)
            else:
                exit_fill = exit_reference + float(spread) / 2.0 + float(slippage)
                gross_profit = (entry_reference - exit_reference) * float(position_size)

            trading_costs = (float(spread) + 2.0 * float(slippage)) * float(position_size)
            commission_costs = (
                2.0 * float(commission_per_unit_per_side) * float(position_size)
            )
            net_profit = gross_profit - trading_costs - commission_costs
            if net_profit > 1e-12:
                result = "win"
            elif net_profit < -1e-12:
                result = "loss"
            else:
                result = "breakeven"

            trades.append(
                CostAwareTrade(
                    symbol=clean_symbol,
                    direction=signal,
                    signal_time=data.iloc[i]["timestamp"],
                    entry_time=entry_row["timestamp"],
                    exit_time=data.iloc[exit_index]["timestamp"],
                    signal_index=i,
                    entry_index=entry_index,
                    exit_index=exit_index,
                    reference_entry_price=entry_reference,
                    entry_fill_price=entry_fill,
                    reference_exit_price=exit_reference,
                    exit_fill_price=exit_fill,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    position_size=float(position_size),
                    gross_profit=gross_profit,
                    trading_costs=trading_costs,
                    commission_costs=commission_costs,
                    net_profit=net_profit,
                    result=result,
                    exit_reason=exit_reason,
                )
            )

            # No overlapping trades. A new signal can only be evaluated after
            # the exit candle closes, and any next entry is on a later candle.
            i = exit_index

        return self._summarize(clean_symbol, trades, initial_equity, bars_evaluated)

    def run_train_test(
        self,
        dataframe: pd.DataFrame,
        symbol: str,
        signal_fn: SignalFunction,
        *,
        train_fraction: float = 0.7,
        **run_kwargs,
    ) -> CostAwareSplitResult:
        """Run a chronological train/test split without carrying trades over.

        Test signals can use earlier training candles as historical warm-up,
        but no test trade is opened before the split index. The signal function
        is still called with prefixes only. This is a fixed holdout, not a
        substitute for walk-forward validation or parameter selection controls.
        """
        self._validate_fraction("train_fraction", train_fraction)
        if "start_index" in run_kwargs or "end_index" in run_kwargs:
            raise ValueError("run_train_test controls start_index and end_index.")
        data = self._prepare_data(dataframe)
        n = len(data)
        split_index = int(math.floor(n * float(train_fraction)))
        if split_index < 2 or n - split_index < 2:
            raise ValueError(
                "At least two candles are required in both train and test segments."
            )

        train_result = self.run(
            data.iloc[:split_index].copy(),
            symbol,
            signal_fn,
            **run_kwargs,
        )
        test_result = self.run(
            data,
            symbol,
            signal_fn,
            start_index=split_index,
            end_index=n,
            **run_kwargs,
        )
        return CostAwareSplitResult(
            train=train_result,
            test=test_result,
            train_fraction=float(train_fraction),
            split_timestamp=data.iloc[split_index]["timestamp"],
        )

    @staticmethod
    def _validate_positive(name: str, value: float) -> None:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{name} must be a finite number greater than zero.") from None
        if not math.isfinite(numeric) or numeric <= 0:
            raise ValueError(f"{name} must be a finite number greater than zero.")

    @staticmethod
    def _validate_nonnegative(name: str, value: float) -> None:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{name} must be a finite number >= 0.") from None
        if not math.isfinite(numeric) or numeric < 0:
            raise ValueError(f"{name} must be a finite number >= 0.")

    @staticmethod
    def _validate_fraction(name: str, value: float) -> None:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{name} must be strictly between 0 and 1.") from None
        if not math.isfinite(numeric) or not 0.0 < numeric < 1.0:
            raise ValueError(f"{name} must be strictly between 0 and 1.")

    @staticmethod
    def _prepare_data(dataframe: pd.DataFrame) -> pd.DataFrame:
        if not isinstance(dataframe, pd.DataFrame):
            raise ValueError("dataframe must be a pandas DataFrame.")
        if dataframe.empty:
            return pd.DataFrame(columns=["timestamp", *_OHLC_COLUMNS])
        required = {"timestamp", *_OHLC_COLUMNS}
        missing = required - set(dataframe.columns)
        if missing:
            raise ValueError(f"Missing required columns: {sorted(missing)}")

        data = dataframe.copy(deep=True)
        timestamps = pd.to_datetime(data["timestamp"], errors="coerce", utc=True)
        if timestamps.isna().any():
            raise ValueError("timestamp contains missing or invalid values.")
        data["timestamp"] = timestamps
        data = data.sort_values("timestamp", kind="stable").reset_index(drop=True)
        if data["timestamp"].duplicated().any():
            raise ValueError("timestamp values must be unique.")

        for column in _OHLC_COLUMNS:
            data[column] = pd.to_numeric(data[column], errors="coerce")
            if data[column].isna().any():
                raise ValueError(f"{column} contains missing or non-numeric values.")
            if not all(math.isfinite(float(value)) for value in data[column].tolist()):
                raise ValueError(f"{column} contains non-finite values.")

        invalid = (
            (data["high"] < data[["open", "close", "low"]].max(axis=1))
            | (data["low"] > data[["open", "close", "high"]].min(axis=1))
        )
        if invalid.any():
            rows = data.index[invalid].tolist()[:10]
            raise ValueError(f"Invalid OHLC candle relationships at sorted rows: {rows}")
        return data

    @staticmethod
    def _summarize(
        symbol: str,
        trades: list[CostAwareTrade],
        initial_equity: float,
        bars_evaluated: int,
    ) -> CostAwareBacktestResult:
        gross = sum(item.gross_profit for item in trades)
        trading_costs = sum(item.trading_costs for item in trades)
        commission = sum(item.commission_costs for item in trades)
        total_costs = trading_costs + commission
        net = sum(item.net_profit for item in trades)
        winners = sum(item.result == "win" for item in trades)
        losers = sum(item.result == "loss" for item in trades)
        breakeven = sum(item.result == "breakeven" for item in trades)
        count = len(trades)
        win_rate = (winners / count * 100.0) if count else 0.0
        positive = sum(max(item.net_profit, 0.0) for item in trades)
        negative = sum(abs(min(item.net_profit, 0.0)) for item in trades)
        profit_factor = (positive / negative) if negative > 0.0 else None

        equity = float(initial_equity)
        peak = equity
        max_drawdown = 0.0
        max_drawdown_pct = 0.0
        for trade in trades:
            equity += trade.net_profit
            peak = max(peak, equity)
            drawdown = peak - equity
            max_drawdown = max(max_drawdown, drawdown)
            if peak > 0:
                max_drawdown_pct = max(max_drawdown_pct, drawdown / peak * 100.0)

        return CostAwareBacktestResult(
            symbol=symbol,
            trades=list(trades),
            total_gross_profit=gross,
            total_trading_costs=trading_costs,
            total_commission_costs=commission,
            total_costs=total_costs,
            total_net_profit=net,
            winning_trades=winners,
            losing_trades=losers,
            breakeven_trades=breakeven,
            win_rate=win_rate,
            profit_factor=profit_factor,
            max_drawdown=max_drawdown,
            max_drawdown_pct=max_drawdown_pct,
            initial_equity=float(initial_equity),
            ending_equity=float(initial_equity) + net,
            bars_evaluated=bars_evaluated,
        )
