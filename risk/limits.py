from numbers import Integral
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from risk.models import RiskLimits


def validate_risk_limits(limits: RiskLimits) -> RiskLimits:
    if not 0 < limits.max_risk_per_trade_percent <= 100:
        raise ValueError("max_risk_per_trade_percent must be greater than 0 and at most 100.")
    if isinstance(limits.max_open_trades, bool) or not isinstance(limits.max_open_trades, Integral) or limits.max_open_trades <= 0:
        raise ValueError("max_open_trades must be a positive integer.")
    if not 0 < limits.max_total_exposure_percent <= 100:
        raise ValueError("max_total_exposure_percent must be greater than 0 and at most 100.")
    if not 0 < limits.max_daily_loss_percent <= 100:
        raise ValueError("max_daily_loss_percent must be greater than 0 and at most 100.")
    if isinstance(limits.max_trades_per_day, bool) or not isinstance(limits.max_trades_per_day, Integral) or limits.max_trades_per_day <= 0:
        raise ValueError("max_trades_per_day must be a positive integer.")
    if limits.max_position_volume <= 0:
        raise ValueError("max_position_volume must be greater than zero.")
    try:
        ZoneInfo(limits.trading_timezone)
    except (ZoneInfoNotFoundError, TypeError):
        raise ValueError("trading_timezone must be a valid IANA timezone.") from None
    return limits


def can_open_trade(
    limits: RiskLimits,
    current_open_trades: int,
    current_exposure_percent: float,
    proposed_risk_percent: float,
    daily_loss_percent: float,
    current_daily_entries: int = 0,
) -> bool:
    validate_risk_limits(limits)
    if isinstance(current_open_trades, bool) or current_open_trades < 0:
        raise ValueError("current_open_trades must be a non-negative integer.")
    if isinstance(current_daily_entries, bool) or not isinstance(current_daily_entries, Integral) or current_daily_entries < 0:
        raise ValueError("current_daily_entries must be a non-negative integer.")
    if current_exposure_percent < 0:
        raise ValueError("current_exposure_percent cannot be negative.")
    if proposed_risk_percent <= 0:
        raise ValueError("proposed_risk_percent must be greater than zero.")
    if daily_loss_percent < 0:
        raise ValueError("daily_loss_percent cannot be negative.")
    if current_open_trades >= limits.max_open_trades:
        return False
    if current_daily_entries >= limits.max_trades_per_day:
        return False
    if current_exposure_percent + proposed_risk_percent > limits.max_total_exposure_percent:
        return False
    if daily_loss_percent >= limits.max_daily_loss_percent:
        return False
    if proposed_risk_percent > limits.max_risk_per_trade_percent:
        return False
    return True
