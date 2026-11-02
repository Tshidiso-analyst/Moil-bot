from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pandas as pd

from market_data.validation import validate_market_data


def fetch_live_candle_data(
    symbol: str,
    timeframe: str,
    bars: int = 250,
    mt5_path: str | None = None,
) -> pd.DataFrame:
    """Fetch a valid OHLCV dataset from local MT5 if available.

    Returns an empty DataFrame when there is no MT5 installation or no live feed.
    """
    symbol = str(symbol or "").strip().upper()
    if not symbol:
        raise ValueError("Symbol must not be empty.")

    timeframe = str(timeframe).upper()
    try:
        import MetaTrader5 as mt5
    except ImportError:
        return pd.DataFrame()

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=max(1, bars * 2))

    try:
        mt5_path = mt5_path or os.getenv("MT5_PATH", r"C:\Program Files\MetaTrader 5\terminal64.exe")
        if not mt5.initialize(path=mt5_path):
            return pd.DataFrame()
        if not mt5.symbol_select(symbol, True):
            return pd.DataFrame()

        tf = getattr(mt5, f"TIMEFRAME_{timeframe}", None)
        if tf is None:
            return pd.DataFrame()

        rates = mt5.copy_rates_range(symbol, tf, start, end)
        if not rates:
            return pd.DataFrame()

        frame = pd.DataFrame(rates)
        if frame.empty:
            return frame

        if "time" not in frame.columns:
            return pd.DataFrame()

        frame["time"] = pd.to_datetime(frame["time"], unit="s", utc=True)
        frame = frame.rename(columns={"time": "timestamp", "tick_volume": "volume"})
        data = frame[["timestamp", "open", "high", "low", "close", "volume"]].copy()
        for column in ["open", "high", "low", "close", "volume"]:
            data[column] = pd.to_numeric(data[column], errors="coerce")
        data = data.dropna().reset_index(drop=True)

        if data.empty:
            return data

        validate_market_data(data)
        return data
    except Exception:
        return pd.DataFrame()
    finally:
        try:
            mt5.shutdown()
        except Exception:
            pass


def load_live_market_datasets(
    symbol: str,
    timeframes: tuple[str, ...] = ("M15", "H1"),
    bars: int = 250,
    mt5_path: str | None = None,
) -> dict[str, pd.DataFrame]:
    datasets: dict[str, pd.DataFrame] = {}
    for timeframe in timeframes:
        frame = fetch_live_candle_data(symbol=symbol, timeframe=timeframe, bars=bars, mt5_path=mt5_path)
        if not frame.empty and len(frame) >= 20:
            datasets[timeframe] = frame
    if not datasets:
        raise ValueError(f"Unable to load live MT5 candle data for {symbol}.")
    return datasets


__all__ = ["fetch_live_candle_data", "load_live_market_datasets"]
