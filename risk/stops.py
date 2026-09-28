def calculate_stop_loss(
    entry: float,
    direction: str,
    distance: float,
) -> float:

    if entry <= 0:
        raise ValueError(
            "Entry must be greater than zero."
        )

    if distance <= 0:
        raise ValueError(
            "Stop distance must be greater than zero."
        )

    if direction == "bullish":
        return entry - distance

    if direction == "bearish":
        return entry + distance

    raise ValueError(
        "Direction must be bullish or bearish."
    )


def calculate_take_profit(
    entry: float,
    stop_loss: float,
    direction: str,
    reward_multiple: float,
) -> float:

    if entry <= 0 or stop_loss <= 0:
        raise ValueError(
            "Entry and stop loss must be greater than zero."
        )

    if reward_multiple <= 0:
        raise ValueError(
            "Reward multiple must be greater than zero."
        )

    risk_distance = abs(entry - stop_loss)

    if risk_distance == 0:
        raise ValueError(
            "Entry and stop loss cannot be equal."
        )

    if direction == "bullish":
        return entry + (
            risk_distance * reward_multiple
        )

    if direction == "bearish":
        return entry - (
            risk_distance * reward_multiple
        )

    raise ValueError(
        "Direction must be bullish or bearish."
    )
