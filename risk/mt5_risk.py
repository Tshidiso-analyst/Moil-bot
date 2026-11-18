"""Broker-aware instrument specifications for the supported XAUUSD instrument."""
from __future__ import annotations

from typing import Any

from risk.models import InstrumentRisk
from risk.symbols import canonicalize_symbol


class MT5RiskSpecification:
    def __init__(self, mt5_module: Any | None = None):
        if mt5_module is None:
            try:
                import MetaTrader5 as mt5_module
            except ImportError as exc:  # pragma: no cover - Windows runtime
                raise RuntimeError("MetaTrader5 package is unavailable.") from exc
        self.mt5 = mt5_module

    def get(self, symbol: str) -> InstrumentRisk:
        canonicalize_symbol(symbol)
        if not self.mt5.symbol_select(symbol, True):
            raise RuntimeError(f"Unable to select MT5 symbol {symbol}: {self.mt5.last_error()}")
        info = self.mt5.symbol_info(symbol)
        if info is None:
            raise RuntimeError(f"Unable to retrieve MT5 information for {symbol}: {self.mt5.last_error()}")
        return InstrumentRisk(
            symbol="XAUUSD",
            point=float(getattr(info, "point", 0.0) or 0.0),
            tick_size=float(getattr(info, "trade_tick_size", 0.0) or 0.0),
            tick_value=float(getattr(info, "trade_tick_value", 0.0) or getattr(info, "trade_tick_value_profit", 0.0) or 0.0),
            contract_size=float(getattr(info, "trade_contract_size", 0.0) or 0.0),
            volume_min=float(getattr(info, "volume_min", 0.0) or 0.0),
            volume_max=float(getattr(info, "volume_max", 0.0) or 0.0),
            volume_step=float(getattr(info, "volume_step", 0.0) or 0.0),
        )
