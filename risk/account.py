import math

from risk.models import AccountRisk


def calculate_account_risk(balance: float, risk_percent: float) -> AccountRisk:
    try:
        balance = float(balance)
        risk_percent = float(risk_percent)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("Account balance and risk percentage must be numeric.") from None
    if not math.isfinite(balance) or balance <= 0:
        raise ValueError("Account balance must be finite and greater than zero.")
    if not math.isfinite(risk_percent) or not 0 < risk_percent <= 100:
        raise ValueError("Risk percentage must be finite, greater than zero and at most 100.")
    risk_amount = balance * (risk_percent / 100.0)
    return AccountRisk(balance=balance, risk_percent=risk_percent, risk_amount=risk_amount)
