"""Broker-aware instrument specifications and MT5-calculated position sizing."""
from __future__ import annotations

from decimal import Decimal, ROUND_FLOOR
import math
from typing import Any

from risk.models import InstrumentRisk, PositionSize
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


def calculate_mt5_position_size(
    mt5: Any,
    *,
    symbol: str,
    direction: str,
    entry: float,
    stop_loss: float,
    risk_amount: float,
    max_volume: float = 0.02,
) -> PositionSize:
    """Size XAUUSD using the broker's profit calculator and actual volume grid."""
    canonicalize_symbol(symbol)
    if direction not in {"bullish", "bearish"}:
        raise ValueError("Direction must be bullish or bearish.")
    values = (entry, stop_loss, risk_amount, max_volume)
    if not all(math.isfinite(float(value)) for value in values):
        raise ValueError("Entry, stop loss, risk amount and max volume must be finite.")
    if entry <= 0 or stop_loss <= 0 or risk_amount <= 0 or max_volume <= 0:
        raise ValueError("Entry, stop loss, risk amount and max volume must be greater than zero.")
    if direction == "bullish" and stop_loss >= entry:
        raise ValueError("Bullish stop loss must be below entry.")
    if direction == "bearish" and stop_loss <= entry:
        raise ValueError("Bearish stop loss must be above entry.")

    if not mt5.symbol_select(symbol, True):
        raise RuntimeError(f"Unable to select MT5 symbol {symbol}: {mt5.last_error()}")
    info = mt5.symbol_info(symbol)
    if info is None:
        raise RuntimeError(f"Broker metadata unavailable for {symbol}: {mt5.last_error()}")
    order_type = mt5.ORDER_TYPE_BUY if direction == "bullish" else mt5.ORDER_TYPE_SELL
    one_lot_pnl = mt5.order_calc_profit(order_type, symbol, 1.0, float(entry), float(stop_loss))
    if one_lot_pnl is None:
        raise RuntimeError(f"Broker could not calculate stop-loss value for {symbol}: {mt5.last_error()}")
    loss_per_lot = abs(float(one_lot_pnl))
    if not math.isfinite(loss_per_lot) or loss_per_lot <= 0:
        raise ValueError("Broker returned an invalid one-lot stop-loss estimate.")

    step = Decimal(str(getattr(info, "volume_step", 0.0) or 0.0))
    minimum = Decimal(str(getattr(info, "volume_min", 0.0) or 0.0))
    broker_max = Decimal(str(getattr(info, "volume_max", 0.0) or 0.0))
    cap = min(broker_max, Decimal(str(max_volume)))
    if step <= 0 or minimum <= 0 or broker_max < minimum or cap < minimum:
        raise ValueError("Broker volume limits are invalid or exceed the configured 0.02-lot ceiling.")
    raw_volume = Decimal(str(risk_amount / loss_per_lot))
    units = (raw_volume / step).to_integral_value(rounding=ROUND_FLOOR)
    volume = min(units * step, (cap / step).to_integral_value(rounding=ROUND_FLOOR) * step)
    if volume < minimum:
        raise ValueError("Safe volume is below broker minimum; trade rejected rather than exceeding risk.")
    decimals = max(0, -step.normalize().as_tuple().exponent)
    volume_float = round(float(volume), decimals)
    final_pnl = mt5.order_calc_profit(order_type, symbol, volume_float, float(entry), float(stop_loss))
    if final_pnl is None:
        raise RuntimeError(f"Broker could not verify final position risk for {symbol}: {mt5.last_error()}")
    estimated_loss = abs(float(final_pnl))
    tolerance = max(0.01, float(risk_amount) * 0.001)
    if not math.isfinite(estimated_loss) or estimated_loss > float(risk_amount) + tolerance:
        raise ValueError("Broker-calculated position risk exceeds the configured risk budget.")

    return PositionSize(
        symbol="XAUUSD",
        direction=direction,
        entry=float(entry),
        stop_loss=float(stop_loss),
        risk_amount=float(risk_amount),
        stop_distance=abs(float(entry) - float(stop_loss)),
        volume=volume_float,
        estimated_loss=estimated_loss,
    )


__all__ = ["MT5RiskSpecification", "calculate_mt5_position_size"]
