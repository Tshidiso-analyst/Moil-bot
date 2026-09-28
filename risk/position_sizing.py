import math

from risk.models import (
    InstrumentRisk,
    PositionSize,
)


def _round_volume(
    volume: float,
    instrument: InstrumentRisk,
) -> float:
    step = instrument.volume_step

    if step <= 0:
        raise ValueError(
            "Volume step must be greater than zero."
        )

    volume = math.floor(volume / step) * step

    volume = max(
        instrument.volume_min,
        volume,
    )

    volume = min(
        instrument.volume_max,
        volume,
    )

    decimals = max(
        0,
        len(
            str(step).rstrip("0").split(".")[-1]
        ),
    )

    return round(volume, decimals)


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
