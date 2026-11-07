from __future__ import annotations

from typing import Any

from chat.service import ChatMessage, chat_service


def _fmt_number(value: Any, digits: int = 2) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number == float("inf"):
        return "inf"
    return f"{number:.{digits}f}"


def format_simple_backtest(result: Any, symbol: str | None = None) -> str:
    """Format a basic BacktestResult into a short chat summary."""
    trades = list(getattr(result, "trades", []) or [])
    total = len(trades)
    wins = int(getattr(result, "winning_trades", 0) or 0)
    losses = int(getattr(result, "losing_trades", 0) or 0)
    win_rate = float(getattr(result, "win_rate", 0.0) or 0.0)
    total_profit = float(getattr(result, "total_profit", 0.0) or 0.0)
    label = (symbol or (trades[0].symbol if trades else "STRATEGY")).upper()

    lines = [
        f"**Backtest · {label}**",
        f"Trades: {total} (W {wins} / L {losses})",
        f"Win rate: {_fmt_number(win_rate, 1)}%",
        f"Total profit: {_fmt_number(total_profit)}",
    ]
    if total == 0:
        lines.append("No completed trades in this sample.")
    return "\n".join(lines)


def format_cost_aware_backtest(result: Any) -> str:
    """Format a CostAwareBacktestResult into a short chat summary."""
    symbol = str(getattr(result, "symbol", "STRATEGY")).upper()
    trades = list(getattr(result, "trades", []) or [])
    total = len(trades)
    wins = int(getattr(result, "winning_trades", 0) or 0)
    losses = int(getattr(result, "losing_trades", 0) or 0)
    breakeven = int(getattr(result, "breakeven_trades", 0) or 0)
    win_rate = float(getattr(result, "win_rate", 0.0) or 0.0)
    net = float(getattr(result, "total_net_profit", 0.0) or 0.0)
    costs = float(getattr(result, "total_costs", 0.0) or 0.0)
    profit_factor = getattr(result, "profit_factor", None)
    max_dd = float(getattr(result, "max_drawdown", 0.0) or 0.0)
    max_dd_pct = float(getattr(result, "max_drawdown_pct", 0.0) or 0.0)
    initial = float(getattr(result, "initial_equity", 0.0) or 0.0)
    ending = float(getattr(result, "ending_equity", 0.0) or 0.0)
    bars = int(getattr(result, "bars_evaluated", 0) or 0)

    pf_text = "n/a" if profit_factor is None else _fmt_number(profit_factor)
    lines = [
        f"**Cost-aware backtest · {symbol}**",
        f"Sample: {total} trades over {bars} bars",
        f"Results: W {wins} / L {losses} / BE {breakeven} · win rate {_fmt_number(win_rate, 1)}%",
        f"Net P&L: {_fmt_number(net)} (costs {_fmt_number(costs)})",
        f"Profit factor: {pf_text}",
        f"Max drawdown: {_fmt_number(max_dd)} ({_fmt_number(max_dd_pct, 1)}%)",
        f"Equity: {_fmt_number(initial)} → {_fmt_number(ending)}",
    ]
    if total == 0:
        lines.append("No completed trades in this sample.")
    if total > 0 and total < 30:
        lines.append("Sample is small; treat results as research only.")
    return "\n".join(lines).replace("P&L", "P&L")


def post_backtest_result(
    result: Any,
    *,
    symbol: str | None = None,
    room: str = "analysis",
    author: str = "Moil Backtest",
) -> ChatMessage:
    """Post a backtest summary into the chatboard.

    Supports both simple BacktestResult and CostAwareBacktestResult objects.
    """
    if hasattr(result, "total_net_profit") and hasattr(result, "max_drawdown"):
        message = format_cost_aware_backtest(result)
    else:
        message = format_simple_backtest(result, symbol=symbol)
    return chat_service.post_message(author=author, message=message, room=room)


__all__ = [
    "format_simple_backtest",
    "format_cost_aware_backtest",
    "post_backtest_result",
]
