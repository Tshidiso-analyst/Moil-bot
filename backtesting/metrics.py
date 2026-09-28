from backtesting.models import BacktestResult


def calculate_profit_factor(
    result: BacktestResult,
) -> float:
    gross_profit = sum(
        trade.profit
        for trade in result.trades
        if trade.profit > 0
    )

    gross_loss = abs(
        sum(
            trade.profit
            for trade in result.trades
            if trade.profit < 0
        )
    )

    if gross_loss == 0:
        if gross_profit > 0:
            return float("inf")

        return 0.0

    return gross_profit / gross_loss
