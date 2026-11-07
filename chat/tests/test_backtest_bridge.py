from dataclasses import dataclass

from chat.backtest_bridge import (
    format_cost_aware_backtest,
    format_simple_backtest,
    post_backtest_result,
)
from chat.service import chat_service


@dataclass
class _SimpleResult:
    trades: list
    total_profit: float
    winning_trades: int
    losing_trades: int
    win_rate: float


@dataclass
class _CostResult:
    symbol: str
    trades: list
    total_gross_profit: float
    total_trading_costs: float
    total_commission_costs: float
    total_costs: float
    total_net_profit: float
    winning_trades: int
    losing_trades: int
    breakeven_trades: int
    win_rate: float
    profit_factor: float | None
    max_drawdown: float
    max_drawdown_pct: float
    initial_equity: float
    ending_equity: float
    bars_evaluated: int


def test_format_simple_backtest():
    result = _SimpleResult(
        trades=[],
        total_profit=12.5,
        winning_trades=3,
        losing_trades=2,
        win_rate=60.0,
    )
    text = format_simple_backtest(result, symbol="EURUSD")
    assert "EURUSD" in text
    assert "60.0%" in text
    assert "12.50" in text


def test_format_cost_aware_backtest_and_post():
    result = _CostResult(
        symbol="XAUUSD",
        trades=[object(), object()],
        total_gross_profit=100.0,
        total_trading_costs=8.0,
        total_commission_costs=2.0,
        total_costs=10.0,
        total_net_profit=90.0,
        winning_trades=2,
        losing_trades=0,
        breakeven_trades=0,
        win_rate=100.0,
        profit_factor=None,
        max_drawdown=5.0,
        max_drawdown_pct=0.5,
        initial_equity=10000.0,
        ending_equity=10090.0,
        bars_evaluated=120,
    )
    text = format_cost_aware_backtest(result)
    assert "XAUUSD" in text
    assert "Net P&L" in text
    assert "Sample is small" in text

    message = post_backtest_result(result, room="analysis")
    assert message.room == "analysis"
    assert "XAUUSD" in message.message
    history = chat_service.list_messages("analysis", limit=5)
    assert any("XAUUSD" in item.message for item in history)
