from qualification.models import (
    QualificationResult,
    SetupSignal,
)


class SetupQualifier:
    def qualify(
        self,
        structure_trend: str,
        top_down_alignment: str,
        fvg_direction: str | None,
        fundamental_bias: str,
    ) -> QualificationResult:

        score = 0
        reasons = []

        direction = "neutral"

        if structure_trend in {"bullish", "bearish"}:
            direction = structure_trend
            score += 1
            reasons.append(
                f"Market structure is {structure_trend}."
            )

        if top_down_alignment == direction:
            score += 1
            reasons.append(
                "Top-down analysis agrees with market structure."
            )
        elif top_down_alignment == "mixed":
            reasons.append(
                "Top-down analysis is mixed."
            )

        if fvg_direction == direction:
            score += 1
            reasons.append(
                f"{direction.capitalize()} fair value gap detected."
            )

        if fundamental_bias == direction:
            score += 1
            reasons.append(
                "Fundamental bias agrees with setup direction."
            )
        elif fundamental_bias not in {
            "neutral",
            direction,
        }:
            reasons.append(
                "Fundamental bias conflicts with setup direction."
            )

        qualified = (
            direction != "neutral"
            and score >= 3
        )

        if not reasons:
            reasons.append(
                "Insufficient market evidence."
            )

        return QualificationResult(
            qualified=qualified,
            direction=direction,
            score=score,
            reasons=reasons,
        )


def calculate_risk_reward(
    entry: float,
    stop_loss: float,
    take_profit: float,
) -> float:
    risk = abs(entry - stop_loss)

    if risk == 0:
        raise ValueError(
            "Entry and stop loss cannot be equal."
        )

    reward = abs(take_profit - entry)

    return reward / risk


def create_setup_signal(
    symbol: str,
    direction: str,
    entry: float,
    stop_loss: float,
    take_profit: float,
) -> SetupSignal:
    if direction not in {"bullish", "bearish"}:
        raise ValueError(
            "Direction must be bullish or bearish."
        )

    if direction == "bullish":
        if stop_loss >= entry:
            raise ValueError(
                "Bullish stop loss must be below entry."
            )

        if take_profit <= entry:
            raise ValueError(
                "Bullish take profit must be above entry."
            )

    if direction == "bearish":
        if stop_loss <= entry:
            raise ValueError(
                "Bearish stop loss must be above entry."
            )

        if take_profit >= entry:
            raise ValueError(
                "Bearish take profit must be below entry."
            )

    return SetupSignal(
        symbol=symbol,
        direction=direction,
        entry=entry,
        stop_loss=stop_loss,
        take_profit=take_profit,
        risk_reward=calculate_risk_reward(
            entry,
            stop_loss,
            take_profit,
        ),
    )
