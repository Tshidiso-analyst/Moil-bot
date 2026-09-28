from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class BacktestTrade:
    symbol: str
    direction: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    stop_loss: float
    take_profit: float
    profit: float
    result: str


@dataclass(frozen=True)
class BacktestResult:
    trades: list[BacktestTrade]
    total_profit: float
    winning_trades: int
    losing_trades: int
    win_rate: float
