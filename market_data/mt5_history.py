from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from market_data.live_data import resolve_mt5_symbol


MT5_PATH = r"C:\Program Files\MetaTrader 5\terminal64.exe"

TIMEFRAME_NAMES = ("M1", "M5", "M15", "M30", "H1", "H4", "D1")


class MT5History:
    """Fetch historical XAUUSD candles from a local MT5 terminal."""

    def __init__(self, path: str = MT5_PATH, mt5_module=None):
        self.path = path
        self._mt5 = mt5_module

    @property
    def mt5(self):
        if self._mt5 is None:
            try:
                import MetaTrader5 as mt5
            except ImportError as exc:
                raise RuntimeError(
                    "MetaTrader5 is available only in the local Windows environment."
                ) from exc
            self._mt5 = mt5
        return self._mt5

    def connect(self) -> None:
        if not self.mt5.initialize(path=self.path):
            raise RuntimeError(
                f"MT5 initialization failed: {self.mt5.last_error()}"
            )

    def shutdown(self) -> None:
        self.mt5.shutdown()

    def fetch(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> pd.DataFrame:
        requested = str(symbol or "").strip().upper()
        if requested != "XAUUSD":
            raise ValueError("Moil-bot historical MT5 data supports XAUUSD (gold) only.")

        timeframe = str(timeframe).upper()
        if timeframe not in TIMEFRAME_NAMES:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        if start >= end:
            raise ValueError("start must be before end.")

        actual_symbol = resolve_mt5_symbol("XAUUSD", self.mt5)
        if not self.mt5.symbol_select(actual_symbol, True):
            raise RuntimeError(
                f"Unable to select verified XAUUSD broker symbol: {actual_symbol}"
            )

        timeframe_value = getattr(self.mt5, f"TIMEFRAME_{timeframe}", None)
        if timeframe_value is None:
            raise ValueError(f"MT5 does not expose timeframe {timeframe}.")

        rates = self.mt5.copy_rates_range(
            actual_symbol,
            timeframe_value,
            start,
            end,
        )

        if rates is None:
            raise RuntimeError(
                f"Unable to retrieve XAUUSD rates: {self.mt5.last_error()}"
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
    canonical_symbol = str(symbol or "").strip().upper()
    if canonical_symbol != "XAUUSD":
        raise ValueError("Historical MT5 datasets must be stored under canonical symbol XAUUSD.")

    path = Path(directory)
    path.mkdir(parents=True, exist_ok=True)

    filename = f"XAUUSD_{timeframe}.csv"
    output = path / filename

    dataframe.to_csv(output, index=False)

    return output
