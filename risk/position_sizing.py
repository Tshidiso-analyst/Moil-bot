import math
from decimal import Decimal, ROUND_FLOOR

from risk.models import InstrumentRisk, PositionSize


def _round_volume(
    volume: float,
    instrument: InstrumentRisk,
    *,
    max_volume: float | None = None,
) -> float:
    step = Decimal(str(instrument.volume_step))
    minimum = Decimal(str(instrument.volume_min))
    broker_maximum = Decimal(str(instrument.volume_max))

    if step <= 0 or minimum <= 0 or broker_maximum < minimum:
        raise ValueError("Broker volume limits are invalid.")
    if max_volume is not None:
        if not math.isfinite(float(max_volume)) or float(max_volume) <= 0:
            raise ValueError("max_volume must be finite and greater than zero.")
        broker_maximum = min(broker_maximum, Decimal(str(max_volume)))
    if not math.isfinite(volume) or volume <= 0:
        raise ValueError("Calculated volume must be finite and positive.")

    requested = Decimal(str(volume))
    units = (requested / step).to_integral_value(rounding=ROUND_FLOOR)
    rounded = units * step
    max_units = (broker_maximum / step).to_integral_value(rounding=ROUND_FLOOR)
    rounded = min(rounded, max_units * step)

    if rounded < minimum:
        raise ValueError(
            "Required position size is below the broker minimum or configured lot cap; "
            "trade rejected to protect the risk limit."
        )

    decimals = max(0, -step.normalize().as_tuple().exponent)
    return round(float(rounded), decimals)


def calculate_position_size(
    instrument: InstrumentRisk,
    direction: str,
    entry: float,
    stop_loss: float,
    risk_amount: float,
    *,
    max_volume: float | None = None,
) -> PositionSize:
    values = (entry, stop_loss, risk_amount)
    if not all(math.isfinite(float(value)) for value in values):
        raise ValueError("Entry, stop loss and risk amount must be finite.")
    if direction not in {"bullish", "bearish"}:
        raise ValueError("Direction must be bullish or bearish.")
    if entry <= 0 or stop_loss <= 0:
        raise ValueError("Entry and stop loss must be greater than zero.")
    if risk_amount <= 0:
        raise ValueError("Risk amount must be greater than zero.")
    if direction == "bullish" and stop_loss >= entry:
        raise ValueError("Bullish stop loss must be below entry.")
    if direction == "bearish" and stop_loss <= entry:
        raise ValueError("Bearish stop loss must be above entry.")

    stop_distance = abs(entry - stop_loss)
    ticks = stop_distance / instrument.tick_size
    loss_per_volume = ticks * instrument.tick_value
    if not math.isfinite(loss_per_volume) or loss_per_volume <= 0:
        raise ValueError("Calculated loss per volume must be finite and greater than zero.")

    raw_volume = risk_amount / loss_per_volume
    volume = _round_volume(raw_volume, instrument, max_volume=max_volume)
    estimated_loss = ticks * instrument.tick_value * volume

    return PositionSize(
        symbol=instrument.symbol,
        direction=direction,
        entry=entry,
        stop_loss=stop_loss,
        risk_amount=risk_amount,
        stop_distance=stop_distance,
        volume=volume,
        estimated_loss=estimated_loss,
    )
