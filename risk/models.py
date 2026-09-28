from dataclasses import dataclass


@dataclass(frozen=True)
class AccountRisk:
    balance: float
    risk_percent: float
    risk_amount: float


@dataclass(frozen=True)
class InstrumentRisk:
    symbol: str
    point: float
    tick_size: float
    tick_value: float
    contract_size: float
    volume_min: float
    volume_max: float
    volume_step: float


@dataclass(frozen=True)
class PositionSize:
    symbol: str
    direction: str
    entry: float
    stop_loss: float
    risk_amount: float
    stop_distance: float
    volume: float
    estimated_loss: float


@dataclass(frozen=True)
class RiskLimits:
    max_risk_per_trade_percent: float
    max_open_trades: int
    max_total_exposure_percent: float
    max_daily_loss_percent: float
