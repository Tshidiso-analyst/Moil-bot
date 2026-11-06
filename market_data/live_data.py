from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pandas as pd

from market_data.validation import validate_market_data


def resolve_mt5_symbol(symbol: str, mt5_module=None) -> str:
    """Resolve a requested instrument to a symbol available on this broker."""
    requested = str(symbol or "").strip().upper()
    if not requested:
        raise ValueError("Symbol must not be empty.")
    if mt5_module is None:
        import MetaTrader5 as mt5_module

    info = mt5_module.symbol_info(requested)
    if info is not None:
        return str(getattr(info, "name", requested))

    raw_symbols = mt5_module.symbols_get()
    names = [str(getattr(item, "name", "")) for item in (raw_symbols or ())]
    names = [name for name in names if name]
    exact = next((name for name in names if name.upper() == requested), None)
    if exact:
        return exact

    # Broker symbols commonly add suffixes (EURUSDm, EURUSD.a). Prefer a
    # prefix match to avoid accidentally selecting an unrelated containing name.
    candidates = [name for name in names if name.upper().startswith(requested)]
    if not candidates:
        candidates = [name for name in names if requested in name.upper()]
    if not candidates:
        raise ValueError(f"Symbol {requested} is not available in this MT5 account.")
    return sorted(candidates, key=lambda name: (not name.upper().startswith(requested), len(name), name))[0]


def fetch_live_candle_data(
    symbol: str,
    timeframe: str,
    bars: int = 250,
    mt5_path: str | None = None,
) -> pd.DataFrame:
    """Fetch validated OHLCV data, reusing an existing local MT5 session."""
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
    initialized_here = False
    try:
        try:
            already_initialized = mt5.terminal_info() is not None
        except Exception:
            already_initialized = False
        if not already_initialized:
            mt5_path = mt5_path or os.getenv("MT5_PATH", r"C:\Program Files\MetaTrader 5\terminal64.exe")
            if not mt5.initialize(path=mt5_path):
                return pd.DataFrame()
            initialized_here = True

        try:
            actual_symbol = resolve_mt5_symbol(symbol, mt5)
        except Exception:
            return pd.DataFrame()
        if not mt5.symbol_select(actual_symbol, True):
            return pd.DataFrame()

        tf = getattr(mt5, f"TIMEFRAME_{timeframe}", None)
        if tf is None:
            return pd.DataFrame()
        rates = mt5.copy_rates_range(actual_symbol, tf, start, end)
        if rates is None or len(rates) == 0:
            return pd.DataFrame()

        frame = pd.DataFrame(rates)
        if frame.empty or "time" not in frame.columns:
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
        if initialized_here:
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
        raise ValueError(f"Unable to load live MT5 candle data for {symbol}; check the broker symbol name and MT5 history availability.")
    return datasets


__all__ = ["fetch_live_candle_data", "load_live_market_datasets", "resolve_mt5_symbol"]
