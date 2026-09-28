import pandas as pd

from backtesting.models import (
    BacktestResult,
    BacktestTrade,
)


class BacktestEngine:
    def run(
        self,
        dataframe: pd.DataFrame,
        symbol: str,
        direction: str,
        entry_column: str = "close",
        stop_distance: float = 0.005,
        reward_multiple: float = 2.0,
    ) -> BacktestResult:

        if dataframe.empty:
            return BacktestResult(
                trades=[],
                total_profit=0.0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0.0,
            )

        required = {
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            entry_column,
        }

        missing = required - set(dataframe.columns)

        if missing:
            raise ValueError(
                f"Missing required columns: {sorted(missing)}"
            )

        if direction not in {"bullish", "bearish"}:
            raise ValueError(
                "Direction must be bullish or bearish."
            )

        if stop_distance <= 0:
            raise ValueError(
                "stop_distance must be greater than zero."
            )

        if reward_multiple <= 0:
            raise ValueError(
                "reward_multiple must be greater than zero."
            )

        data = (
            dataframe
            .sort_values("timestamp")
            .reset_index(drop=True)
        )

        trades = []
        i = 0

        while i < len(data) - 1:
            row = data.iloc[i]

            entry = float(row[entry_column])

            if direction == "bullish":
                stop_loss = entry - stop_distance
                take_profit = (
                    entry
                    + stop_distance * reward_multiple
                )
            else:
                stop_loss = entry + stop_distance
                take_profit = (
                    entry
                    - stop_distance * reward_multiple
                )

            exit_price = None
            exit_time = None
            result = None
            exit_index = None

            for j in range(i + 1, len(data)):
                future = data.iloc[j]

                high = float(future["high"])
                low = float(future["low"])

                if direction == "bullish":
                    hit_stop = low <= stop_loss
                    hit_target = high >= take_profit
                else:
                    hit_stop = high >= stop_loss
                    hit_target = low <= take_profit

                if hit_stop and hit_target:
                    exit_price = stop_loss
                    result = "loss"
                    exit_time = future["timestamp"]
                    exit_index = j
                    break

                if hit_stop:
                    exit_price = stop_loss
                    result = "loss"
                    exit_time = future["timestamp"]
                    exit_index = j
                    break

                if hit_target:
                    exit_price = take_profit
                    result = "win"
                    exit_time = future["timestamp"]
                    exit_index = j
                    break

            if exit_price is None:
                break

            if direction == "bullish":
                profit = exit_price - entry
            else:
                profit = entry - exit_price

            trades.append(
                BacktestTrade(
                    symbol=symbol,
                    direction=direction,
                    entry_time=row["timestamp"],
                    exit_time=exit_time,
                    entry_price=entry,
                    exit_price=exit_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    profit=profit,
                    result=result,
                )
            )

            i = exit_index

        total_profit = sum(
            trade.profit
            for trade in trades
        )

        winning_trades = sum(
            trade.result == "win"
            for trade in trades
        )

        losing_trades = sum(
            trade.result == "loss"
            for trade in trades
        )

        total_trades = len(trades)

        win_rate = (
            winning_trades / total_trades * 100
            if total_trades
            else 0.0
        )

        return BacktestResult(
            trades=trades,
            total_profit=total_profit,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
        )
