import math


def calculate_stop_loss(entry: float, direction: str, distance: float) -> float:
    try:
        entry = float(entry)
        distance = float(distance)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("Entry and stop distance must be numeric.") from None
    if not math.isfinite(entry) or entry <= 0:
        raise ValueError("Entry must be finite and greater than zero.")
    if not math.isfinite(distance) or distance <= 0:
        raise ValueError("Stop distance must be finite and greater than zero.")
    if direction == "bullish":
        stop = entry - distance
    elif direction == "bearish":
        stop = entry + distance
    else:
        raise ValueError("Direction must be bullish or bearish.")
    if not math.isfinite(stop) or stop <= 0:
        raise ValueError("Calculated stop loss must be finite and greater than zero.")
    return stop


def calculate_take_profit(
    entry: float,
    stop_loss: float,
    direction: str,
    reward_multiple: float,
) -> float:
    try:
        entry = float(entry)
        stop_loss = float(stop_loss)
        reward_multiple = float(reward_multiple)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("Entry, stop loss and reward multiple must be numeric.") from None
    if not all(math.isfinite(value) for value in (entry, stop_loss, reward_multiple)):
        raise ValueError("Entry, stop loss and reward multiple must be finite.")
    if entry <= 0 or stop_loss <= 0:
        raise ValueError("Entry and stop loss must be greater than zero.")
    if reward_multiple <= 0:
        raise ValueError("Reward multiple must be greater than zero.")
    if direction == "bullish":
        if stop_loss >= entry:
            raise ValueError("Bullish stop loss must be below entry.")
        target = entry + (entry - stop_loss) * reward_multiple
    elif direction == "bearish":
        if stop_loss <= entry:
            raise ValueError("Bearish stop loss must be above entry.")
        target = entry - (stop_loss - entry) * reward_multiple
    else:
        raise ValueError("Direction must be bullish or bearish.")
    if not math.isfinite(target) or target <= 0:
        raise ValueError("Calculated take profit must be finite and greater than zero.")
    return target
