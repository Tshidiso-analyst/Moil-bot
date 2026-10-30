from __future__ import annotations

from datetime import timedelta
import math
from typing import Sequence


def record_walk_forward_backtest(
    registry,
    rule_id: str,
    folds: Sequence,
    *,
    minimum_folds: int = 3,
    costs_included: bool,
    no_future_leakage: bool,
) -> dict:
    """
    Convert walk-forward test-fold trades into a registry backtest record.

    Only each fold's out-of-sample test trades are used. This function
    records evidence; it does not approve a rule or enable execution.
    """

    if not isinstance(minimum_folds, int) or isinstance(minimum_folds, bool):
        raise ValueError("minimum_folds must be an integer.")

    if minimum_folds < 1:
        raise ValueError("minimum_folds must be at least 1.")

    if not isinstance(costs_included, bool):
        raise ValueError("costs_included must be a boolean.")

    if not isinstance(no_future_leakage, bool):
        raise ValueError("no_future_leakage must be a boolean.")

    if len(folds) < minimum_folds:
        raise ValueError(
            f"At least {minimum_folds} walk-forward folds are required; "
            f"received {len(folds)}."
        )

    ordered_folds = sorted(folds, key=lambda fold: fold.test_start)

    for previous, current in zip(ordered_folds, ordered_folds[1:]):
        if current.test_start <= previous.test_end:
            raise ValueError(
                "Walk-forward test periods overlap or are not chronological."
            )

    all_net_profits = []

    for fold in ordered_folds:
        test_result = fold.result.test
        trades = test_result.trades

        if not isinstance(trades, (list, tuple)):
            raise ValueError("A fold's test trades must be a list or tuple.")

        for trade in trades:
            try:
                net_profit = float(trade.net_profit)
            except (AttributeError, TypeError, ValueError) as exc:
                raise ValueError(
                    "Every test trade must have a numeric net_profit."
                ) from exc

            if not math.isfinite(net_profit):
                raise ValueError("Trade net_profit values must be finite.")

            all_net_profits.append(net_profit)

    if not all_net_profits:
        raise ValueError(
            "No out-of-sample trades were produced. "
            "There is not enough evidence to record a qualification backtest."
        )

    gross_wins = sum(value for value in all_net_profits if value > 0)
    gross_losses = abs(sum(value for value in all_net_profits if value < 0))

    if gross_losses == 0:
        raise ValueError(
            "Profit factor cannot be established because there are no "
            "losing out-of-sample trades. More evidence is required."
        )

    profit_factor = gross_wins / gross_losses

    initial_equity_values = [
        float(fold.result.test.initial_equity)
        for fold in ordered_folds
    ]

    if not initial_equity_values:
        raise ValueError("The test folds do not contain initial equity values.")

    initial_equity = initial_equity_values[0]

    if not math.isfinite(initial_equity) or initial_equity <= 0:
        raise ValueError("Initial equity must be finite and greater than zero.")

    if any(
        not math.isclose(value, initial_equity, rel_tol=1e-9, abs_tol=1e-9)
        for value in initial_equity_values
    ):
        raise ValueError(
            "All folds must use the same initial equity for this aggregation."
        )

    equity = initial_equity
    equity_peak = initial_equity
    maximum_drawdown = 0.0

    for net_profit in all_net_profits:
        equity += net_profit
        equity_peak = max(equity_peak, equity)

        if equity_peak > 0:
            drawdown_pct = (
                (equity_peak - equity) / equity_peak
            ) * 100.0
            maximum_drawdown = max(maximum_drawdown, drawdown_pct)

    net_profit_total = sum(all_net_profits)
    net_return_pct = (net_profit_total / initial_equity) * 100.0

    if not all(
        math.isfinite(value)
        for value in (
            profit_factor,
            maximum_drawdown,
            net_return_pct,
        )
    ):
        raise ValueError("Aggregated backtest metrics must be finite.")

    first_test_date = ordered_folds[0].test_start.date()
    last_test_date = ordered_folds[-1].test_end.date()

    # The registry expects an exclusive end date and rejects equal dates.
    period_end_exclusive = last_test_date + timedelta(days=1)

    result = {
        "trade_count": len(all_net_profits),
        "costs_included": costs_included,
        "out_of_sample": True,
        "no_future_leakage": no_future_leakage,
        "period_start": first_test_date.isoformat(),
        "period_end": period_end_exclusive.isoformat(),
        "profit_factor": profit_factor,
        "max_drawdown_pct": maximum_drawdown,
        "net_return_pct": net_return_pct,
        "walk_forward_fold_count": len(ordered_folds),
        "minimum_walk_forward_folds": minimum_folds,
        "aggregation": "combined_out_of_sample_net_trade_results",
    }

    recorded = registry.record_backtest(rule_id, result)

    # Recording evidence must never approve a rule or enable execution.
    rule = registry._find_rule(rule_id)
    rule["status"] = "draft"
    rule["execution_enabled"] = False
    registry._save()

    return recorded
