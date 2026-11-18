from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pandas as pd

from market_data.validation import validate_market_data
from risk.symbols import canonicalize_symbol


def _is_verified_gold_symbol(info, fallback_name: str = "") -> bool:
    """Return True only for XAU/USD symbols with compatible broker metadata."""
    name = str(getattr(info, "name", "") or fallback_name).strip().upper()
    if not name:
        return False

    # The canonical name may have no metadata on some terminals. Broker
    # aliases (XAUUSDm, XAUUSD.a, etc.) must explicitly identify XAU/USD.
    if name != "XAUUSD" and not name.startswith("XAUUSD"):
        return False

    base = str(getattr(info, "currency_base", "") or "").strip().upper()
    profit = str(getattr(info, "currency_profit", "") or "").strip().upper()

    if base and base != "XAU":
        return False
    if profit and profit != "USD":
        return False

    if name != "XAUUSD":
        return base == "XAU" and profit == "USD"

    return True


def resolve_mt5_symbol(symbol: str, mt5_module=None) -> str:
    """
    Resolve canonical XAUUSD to a verified broker-specific MT5 gold symbol.

    The returned broker name is for MT5 data retrieval only. Strategy,
    backtesting and reporting code must continue using canonical XAUUSD.
    """
    requested = canonicalize_symbol(symbol)

    if mt5_module is None:
        import MetaTrader5 as mt5_module

    info = mt5_module.symbol_info("XAUUSD")
    if info is not None:
        actual_name = str(getattr(info, "name", "") or "").strip()
        if actual_name and _is_verified_gold_symbol(info, actual_name):
            return actual_name

    raw_symbols = mt5_module.symbols_get()
    candidates: list[str] = []
    for item in raw_symbols or ():
        name = str(getattr(item, "name", "") or "").strip()
        if name and _is_verified_gold_symbol(item, name):
            candidates.append(name)

    if not candidates:
        raise ValueError(
            "No verified XAUUSD gold symbol is available in this MT5 account. "
            "Check Market Watch and confirm the broker's XAU/USD symbol metadata."
        )

    return sorted(
        candidates,
        key=lambda name: (
            name.upper() != "XAUUSD",
            len(name),
            name.upper(),
        ),
    )[0]


def fetch_live_candle_data(
    symbol: str,
    timeframe: str,
    bars: int = 250,
    mt5_path: str | None = None,
) -> pd.DataFrame:
    """Fetch validated OHLCV data, reusing an existing local MT5 session."""
    symbol = canonicalize_symbol(symbol)
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
