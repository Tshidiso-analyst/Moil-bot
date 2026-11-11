"""Broker-metadata-based position sizing for MT5 research and risk checks.

The helper computes volume from the broker's tick size/value and volume limits.
It never submits an order. Validate tick-value currency conversion with the
broker/account before using any result for execution.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any


@dataclass(frozen=True)
class PositionSizeResult:
    volume: float
    risk_cash: float
    estimated_loss_at_stop: float
    risk_percent: float
    accepted: bool
    reason: str = ""


def calculate_mt5_position_size(
    symbol_info: Any,
    *,
    equity: float,
    risk_percent: float,
    entry_price: float,
    stop_loss: float,
    max_risk_percent: float = 1.0,
) -> PositionSizeResult:
    """Size a position using MT5 tick metadata and round volume down to step."""
    numeric = {
        "equity": equity, "risk_percent": risk_percent,
        "entry_price": entry_price, "stop_loss": stop_loss,
        "max_risk_percent": max_risk_percent,
    }
    for name, value in numeric.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise ValueError(f"{name} must be a finite number.")
    if equity <= 0 or risk_percent <= 0 or max_risk_percent <= 0:
        raise ValueError("Equity and risk percentages must be positive.")
    if risk_percent > max_risk_percent:
        return PositionSizeResult(0.0, equity * risk_percent / 100.0, 0.0,
                                  risk_percent, False,
                                  f"Requested risk {risk_percent:.4g}% exceeds the {max_risk_percent:.4g}% cap.")
    distance = abs(float(entry_price) - float(stop_loss))
    if distance <= 0:
        raise ValueError("Entry and stop-loss prices must differ.")
    if symbol_info is None:
        return PositionSizeResult(0.0, equity * risk_percent / 100.0, 0.0,
                                  risk_percent, False, "MT5 symbol metadata is unavailable.")

    tick_size = float(getattr(symbol_info, "trade_tick_size", 0.0) or 0.0)
    tick_value = float(getattr(symbol_info, "trade_tick_value_loss", 0.0) or
                       getattr(symbol_info, "trade_tick_value", 0.0) or 0.0)
    min_volume = float(getattr(symbol_info, "volume_min", 0.0) or 0.0)
    max_volume = float(getattr(symbol_info, "volume_max", 0.0) or 0.0)
    step = float(getattr(symbol_info, "volume_step", 0.0) or 0.0)
    if min(tick_size, tick_value, min_volume, max_volume, step) <= 0:
        return PositionSizeResult(0.0, equity * risk_percent / 100.0, 0.0,
                                  risk_percent, False, "Broker tick or volume metadata is invalid.")
    loss_per_lot = distance / tick_size * tick_value
    if not math.isfinite(loss_per_lot) or loss_per_lot <= 0:
        return PositionSizeResult(0.0, equity * risk_percent / 100.0, 0.0,
                                  risk_percent, False, "Could not calculate stop-loss value from broker metadata.")
    risk_cash = float(equity) * float(risk_percent) / 100.0
    raw_volume = risk_cash / loss_per_lot
    # Round down, never up, to avoid exceeding the requested risk.
    steps = math.floor((raw_volume + 1e-12) / step)
    volume = min(max_volume, steps * step)
    volume = round(volume, 8)
    if volume < min_volume:
        return PositionSizeResult(0.0, risk_cash, 0.0, risk_percent, False,
                                  "Minimum broker volume would exceed the requested risk budget.")
    estimated_loss = loss_per_lot * volume
    actual_percent = estimated_loss / equity * 100.0
    if actual_percent > risk_percent + 1e-8:
        return PositionSizeResult(0.0, risk_cash, estimated_loss, actual_percent, False,
                                  "Rounded volume would exceed the requested risk budget.")
    return PositionSizeResult(volume, risk_cash, estimated_loss, actual_percent, True,
                              "Volume rounded down using broker tick and volume metadata.")


__all__ = ["PositionSizeResult", "calculate_mt5_position_size"]
