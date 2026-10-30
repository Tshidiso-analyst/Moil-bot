import math
from decimal import Decimal, ROUND_FLOOR

from risk.models import (
    InstrumentRisk,
    PositionSize,
)


def _round_volume(
    volume: float,
    instrument: InstrumentRisk,
) -> float:
    step = Decimal(str(instrument.volume_step))
    minimum = Decimal(str(instrument.volume_min))
    maximum = Decimal(str(instrument.volume_max))

    if step <= 0:
        raise ValueError("Volume step must be greater than zero.")

    if minimum <= 0 or maximum < minimum:
        raise ValueError("Broker volume limits are invalid.")

    if not math.isfinite(volume) or volume <= 0:
        raise ValueError("Calculated volume must be finite and positive.")

    # Round down to a valid lot step. Never force a small position
    # upward to the broker minimum, because that can exceed the risk budget.
    requested = Decimal(str(volume))
    units = (requested / step).to_integral_value(rounding=ROUND_FLOOR)
    rounded = units * step

    max_units = (maximum / step).to_integral_value(rounding=ROUND_FLOOR)
    rounded = min(rounded, max_units * step)

    if rounded < minimum:
        raise ValueError(
            "Required position size is below the broker minimum; "
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
) -> PositionSize:

    if direction not in {"bullish", "bearish"}:
        raise ValueError(
            "Direction must be bullish or bearish."
        )

    if entry <= 0 or stop_loss <= 0:
        raise ValueError(
            "Entry and stop loss must be greater than zero."
        )

    if risk_amount <= 0:
        raise ValueError(
            "Risk amount must be greater than zero."
        )

    if instrument.tick_size <= 0:
        raise ValueError(
            "Tick size must be greater than zero."
        )

    if instrument.tick_value <= 0:
        raise ValueError(
            "Tick value must be greater than zero."
        )

    if direction == "bullish" and stop_loss >= entry:
        raise ValueError(
            "Bullish stop loss must be below entry."
        )

    if direction == "bearish" and stop_loss <= entry:
        raise ValueError(
            "Bearish stop loss must be above entry."
        )

    stop_distance = abs(entry - stop_loss)

    ticks = stop_distance / instrument.tick_size

    loss_per_volume = ticks * instrument.tick_value

    if loss_per_volume <= 0:
        raise ValueError(
            "Calculated loss per volume must be greater than zero."
        )

    raw_volume = risk_amount / loss_per_volume

    volume = _round_volume(
        raw_volume,
        instrument,
    )

    estimated_loss = (
        ticks
        * instrument.tick_value
        * volume
    )

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
