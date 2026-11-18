from dataclasses import dataclass
import math


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

    def __post_init__(self) -> None:
        if not str(self.symbol).strip():
            raise ValueError("Instrument symbol must not be empty.")
        for name in (
            "point", "tick_size", "tick_value", "contract_size",
            "volume_min", "volume_max", "volume_step",
        ):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and greater than zero.")
        if self.volume_max < self.volume_min:
            raise ValueError("volume_max cannot be less than volume_min.")


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
    max_trades_per_day: int = 10
    max_position_volume: float = 0.02
    trading_timezone: str = "America/New_York"
