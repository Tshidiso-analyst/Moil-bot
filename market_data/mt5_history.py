from datetime import datetime
from pathlib import Path

import MetaTrader5 as mt5
import pandas as pd


MT5_PATH = r"C:\Program Files\MetaTrader 5\terminal64.exe"


TIMEFRAME_MAP = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
}


class MT5History:
    def __init__(self, path: str = MT5_PATH):
        self.path = path

    def connect(self) -> None:
        if not mt5.initialize(path=self.path):
            raise RuntimeError(
                f"MT5 initialization failed: {mt5.last_error()}"
            )

    def shutdown(self) -> None:
        mt5.shutdown()

    def fetch(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> pd.DataFrame:
        if timeframe not in TIMEFRAME_MAP:
            raise ValueError(
                f"Unsupported timeframe: {timeframe}"
            )

        if start >= end:
            raise ValueError("start must be before end.")

        if not mt5.symbol_select(symbol, True):
            raise RuntimeError(
                f"Unable to select MT5 symbol: {symbol}"
            )

        rates = mt5.copy_rates_range(
            symbol,
            TIMEFRAME_MAP[timeframe],
            start,
            end,
        )

        if rates is None:
            raise RuntimeError(
                f"Unable to retrieve rates: {mt5.last_error()}"
            )

        dataframe = pd.DataFrame(rates)

        if dataframe.empty:
            return dataframe

        dataframe["time"] = pd.to_datetime(
            dataframe["time"],
            unit="s",
            utc=True,
        )

        dataframe = dataframe.rename(
            columns={
                "time": "timestamp",
                "tick_volume": "volume",
            }
        )

        columns = [
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]

        return dataframe[columns].copy()


def save_history(
    dataframe: pd.DataFrame,
    symbol: str,
    timeframe: str,
    directory: str = "market_data/storage",
) -> Path:
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=True)

    filename = f"{symbol}_{timeframe}.csv"
    output = path / filename

    dataframe.to_csv(output, index=False)

    return output
