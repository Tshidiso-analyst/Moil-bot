from risk.models import AccountRisk


def calculate_account_risk(
    balance: float,
    risk_percent: float,
) -> AccountRisk:
    if balance <= 0:
        raise ValueError(
            "Account balance must be greater than zero."
        )

    if risk_percent <= 0:
        raise ValueError(
            "Risk percentage must be greater than zero."
        )

    if risk_percent > 100:
        raise ValueError(
            "Risk percentage cannot exceed 100."
        )

    risk_amount = balance * (risk_percent / 100)

    return AccountRisk(
        balance=balance,
        risk_percent=risk_percent,
        risk_amount=risk_amount,
    )
