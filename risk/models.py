from dataclasses import dataclass
import math


@dataclass(frozen=True)
class AccountRisk:
    balance: float
    risk_percent: float
    risk_amount: float

    def __post_init__(self) -> None:
        values = (self.balance, self.risk_percent, self.risk_amount)
        if not all(math.isfinite(float(value)) for value in values):
            raise ValueError("Account risk values must be finite.")
        if self.balance <= 0:
            raise ValueError("Account balance must be greater than zero.")
        if not 0 < self.risk_percent <= 1.0:
            raise ValueError("Account risk percentage must be greater than zero and at most 1%.")
        expected = float(self.balance) * float(self.risk_percent) / 100.0
        if self.risk_amount <= 0 or not math.isclose(
            float(self.risk_amount), expected, rel_tol=1e-9, abs_tol=1e-9
        ):
            raise ValueError("Account risk amount does not match balance and risk percentage.")


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

    def __post_init__(self) -> None:
        if not str(self.symbol).strip():
            raise ValueError("Position symbol must not be empty.")
        if self.direction not in {"bullish", "bearish"}:
            raise ValueError("Position direction must be bullish or bearish.")
        values = (
            self.entry, self.stop_loss, self.risk_amount,
            self.stop_distance, self.volume, self.estimated_loss,
        )
        if not all(math.isfinite(float(value)) for value in values):
            raise ValueError("Position sizing values must be finite.")
        if self.entry <= 0 or self.stop_loss <= 0 or self.risk_amount <= 0:
            raise ValueError("Entry, stop loss and risk amount must be greater than zero.")
        if self.stop_distance <= 0 or self.volume <= 0 or self.estimated_loss < 0:
            raise ValueError("Stop distance and volume must be positive; estimated loss cannot be negative.")
        if self.estimated_loss > self.risk_amount + max(0.01, self.risk_amount * 0.001):
            raise ValueError("Estimated loss exceeds the configured risk amount.")


@dataclass(frozen=True)
class RiskLimits:
    max_risk_per_trade_percent: float
    max_open_trades: int
    max_total_exposure_percent: float
    max_daily_loss_percent: float
    max_trades_per_day: int = 10
    max_position_volume: float = 0.02
    trading_timezone: str = "America/New_York"
