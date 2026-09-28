from risk.models import RiskLimits


def validate_risk_limits(
    limits: RiskLimits,
) -> RiskLimits:

    if not 0 < limits.max_risk_per_trade_percent <= 100:
        raise ValueError(
            "max_risk_per_trade_percent must be greater than 0 and at most 100."
        )

    if limits.max_open_trades <= 0:
        raise ValueError(
            "max_open_trades must be greater than zero."
        )

    if not 0 < limits.max_total_exposure_percent <= 100:
        raise ValueError(
            "max_total_exposure_percent must be greater than 0 and at most 100."
        )

    if not 0 < limits.max_daily_loss_percent <= 100:
        raise ValueError(
            "max_daily_loss_percent must be greater than 0 and at most 100."
        )

    return limits


def can_open_trade(
    limits: RiskLimits,
    current_open_trades: int,
    current_exposure_percent: float,
    proposed_risk_percent: float,
    daily_loss_percent: float,
) -> bool:

    validate_risk_limits(limits)

    if current_open_trades < 0:
        raise ValueError(
            "current_open_trades cannot be negative."
        )

    if current_exposure_percent < 0:
        raise ValueError(
            "current_exposure_percent cannot be negative."
        )

    if proposed_risk_percent <= 0:
        raise ValueError(
            "proposed_risk_percent must be greater than zero."
        )

    if daily_loss_percent < 0:
        raise ValueError(
            "daily_loss_percent cannot be negative."
        )

    if current_open_trades >= limits.max_open_trades:
        return False

    if (
        current_exposure_percent
        + proposed_risk_percent
        > limits.max_total_exposure_percent
    ):
        return False

    if daily_loss_percent >= limits.max_daily_loss_percent:
        return False

    if proposed_risk_percent > limits.max_risk_per_trade_percent:
        return False

    return True
