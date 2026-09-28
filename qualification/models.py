from dataclasses import dataclass


@dataclass(frozen=True)
class SetupSignal:
    symbol: str
    direction: str
    entry: float
    stop_loss: float
    take_profit: float
    risk_reward: float


@dataclass(frozen=True)
class QualificationResult:
    qualified: bool
    direction: str
    score: int
    reasons: list[str]
