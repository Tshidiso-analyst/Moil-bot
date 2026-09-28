from dataclasses import dataclass, field


@dataclass(frozen=True)
class MarketOverview:
    symbol: str
    asset_class: str
    price: float
    structure: str
    top_down_alignment: str
    fundamental_bias: str


@dataclass(frozen=True)
class SetupOverview:
    symbol: str
    direction: str
    qualified: bool
    score: int
    entry: float | None
    stop_loss: float | None
    take_profit: float | None
    risk_reward: float | None
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RiskOverview:
    balance: float
    risk_percent: float
    risk_amount: float
    open_trades: int
    exposure_percent: float
    daily_loss_percent: float


@dataclass(frozen=True)
class BacktestOverview:
    symbol: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_profit: float
    profit_factor: float


@dataclass(frozen=True)
class DashboardSnapshot:
    market: MarketOverview
    setup: SetupOverview | None
    risk: RiskOverview
    backtest: BacktestOverview | None
