from alerts.models import AlertEvent, TradeDecision


def trade_entered_alert(decision: TradeDecision) -> AlertEvent:
    return AlertEvent(
        symbol=decision.symbol,
        alert_type="trade_entered",
        severity="info",
        title=f"{decision.direction} Trade Entered",
        message=(
            f"{decision.symbol} {decision.direction} trade entered. "
            f"Strategy: {decision.strategy}. "
            f"Entry: {decision.entry}. "
            f"Stop loss: {decision.stop_loss}. "
            f"Take profit: {decision.take_profit}. "
            f"Expected move: {decision.expected_move}."
        ),
        decision_id=decision.decision_id,
    )


def setup_qualified_alert(decision: TradeDecision) -> AlertEvent:
    return AlertEvent(
        symbol=decision.symbol,
        alert_type="setup_qualified",
        severity="info",
        title=f"{decision.symbol} Setup Qualified",
        message=(
            f"{decision.symbol} {decision.direction} setup qualified. "
            f"Strategy: {decision.strategy}. "
            f"Risk/reward: {decision.risk_reward:.2f}. "
            f"Reason: {decision.reason}"
        ),
        decision_id=decision.decision_id,
    )


def stop_loss_hit_alert(
    decision: TradeDecision,
    exit_price: float,
) -> AlertEvent:
    return AlertEvent(
        symbol=decision.symbol,
        alert_type="stop_loss_hit",
        severity="warning",
        title=f"{decision.symbol} Stop Loss Hit",
        message=(
            f"{decision.symbol} {decision.direction} trade reached its "
            f"stop loss. Entry: {decision.entry}. "
            f"Exit: {exit_price}. "
            f"Configured stop loss: {decision.stop_loss}."
        ),
        decision_id=decision.decision_id,
    )


def take_profit_hit_alert(
    decision: TradeDecision,
    exit_price: float,
) -> AlertEvent:
    return AlertEvent(
        symbol=decision.symbol,
        alert_type="take_profit_hit",
        severity="info",
        title=f"{decision.symbol} Take Profit Hit",
        message=(
            f"{decision.symbol} {decision.direction} trade reached its "
            f"take-profit target. Entry: {decision.entry}. "
            f"Exit: {exit_price}. "
            f"Configured target: {decision.take_profit}."
        ),
        decision_id=decision.decision_id,
    )


def fundamental_event_alert(
    symbol: str,
    title: str,
    message: str,
    severity: str = "warning",
) -> AlertEvent:
    return AlertEvent(
        symbol=symbol,
        alert_type="fundamental_event",
        severity=severity,
        title=title,
        message=message,
    )


def risk_warning_alert(
    symbol: str,
    message: str,
    decision_id: str | None = None,
) -> AlertEvent:
    return AlertEvent(
        symbol=symbol,
        alert_type="risk_warning",
        severity="critical",
        title=f"{symbol} Risk Warning",
        message=message,
        decision_id=decision_id,
    )


def thesis_weakening_alert(
    decision: TradeDecision,
    reason: str,
) -> AlertEvent:
    return AlertEvent(
        symbol=decision.symbol,
        alert_type="thesis_weakening",
        severity="warning",
        title=f"{decision.symbol} Trade Thesis Weakening",
        message=(
            f"The original {decision.direction} thesis is weakening. "
            f"Reason: {reason}"
        ),
        decision_id=decision.decision_id,
    )


def thesis_invalidated_alert(
    decision: TradeDecision,
    reason: str,
) -> AlertEvent:
    return AlertEvent(
        symbol=decision.symbol,
        alert_type="thesis_invalidated",
        severity="critical",
        title=f"{decision.symbol} Trade Thesis Invalidated",
        message=(
            f"The original {decision.direction} thesis has been "
            f"invalidated. Reason: {reason}"
        ),
        decision_id=decision.decision_id,
    )
