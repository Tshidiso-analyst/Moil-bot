import math
from numbers import Integral
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from risk.models import RiskLimits


def validate_risk_limits(limits: RiskLimits) -> RiskLimits:
    if isinstance(limits.max_risk_per_trade_percent, bool) or not math.isfinite(float(limits.max_risk_per_trade_percent)) or not 0 < limits.max_risk_per_trade_percent <= 1.0:
        raise ValueError("max_risk_per_trade_percent must be finite, greater than 0 and at most 1%.")
    if isinstance(limits.max_open_trades, bool) or not isinstance(limits.max_open_trades, Integral) or limits.max_open_trades <= 0 or limits.max_open_trades > 3:
        raise ValueError("max_open_trades must be an integer from 1 to 3.")
    if isinstance(limits.max_total_exposure_percent, bool) or not math.isfinite(float(limits.max_total_exposure_percent)) or not 0 < limits.max_total_exposure_percent <= 3.0:
        raise ValueError("max_total_exposure_percent must be finite, greater than 0 and at most 3%.")
    if isinstance(limits.max_daily_loss_percent, bool) or not math.isfinite(float(limits.max_daily_loss_percent)) or not 0 < limits.max_daily_loss_percent <= 5.0:
        raise ValueError("max_daily_loss_percent must be finite, greater than 0 and at most 5%.")
    if isinstance(limits.max_trades_per_day, bool) or not isinstance(limits.max_trades_per_day, Integral) or limits.max_trades_per_day <= 0 or limits.max_trades_per_day > 10:
        raise ValueError("max_trades_per_day must be an integer from 1 to 10.")
    if isinstance(limits.max_position_volume, bool) or not math.isfinite(float(limits.max_position_volume)) or not 0 < limits.max_position_volume <= 0.02:
        raise ValueError("max_position_volume must be finite, greater than zero and no more than 0.02 lots.")
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
    if isinstance(current_open_trades, bool) or not isinstance(current_open_trades, Integral) or current_open_trades < 0:
        raise ValueError("current_open_trades must be a non-negative integer.")
    if isinstance(current_daily_entries, bool) or not isinstance(current_daily_entries, Integral) or current_daily_entries < 0:
        raise ValueError("current_daily_entries must be a non-negative integer.")
    metrics = (current_exposure_percent, proposed_risk_percent, daily_loss_percent)
    if any(isinstance(value, bool) for value in metrics) or not all(math.isfinite(float(value)) for value in metrics):
        raise ValueError("Risk percentages must be finite numbers.")
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
