from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class ReplayCandle:
    index: int
    timestamp: object
    open: float
    high: float
    low: float
    close: float


class MarketReplay:
    def __init__(self, dataframe: pd.DataFrame):
        required = {
            "timestamp",
            "open",
            "high",
            "low",
            "close",
        }

        missing = required - set(dataframe.columns)

        if missing:
            raise ValueError(
                f"Missing replay columns: {sorted(missing)}"
            )

        self.dataframe = (
            dataframe
            .sort_values("timestamp")
            .reset_index(drop=True)
        )

    def candles(self):
        for index, row in self.dataframe.iterrows():
            yield ReplayCandle(
                index=index,
                timestamp=row["timestamp"],
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
            )
