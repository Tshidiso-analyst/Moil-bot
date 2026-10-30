from dataclasses import dataclass


@dataclass(frozen=True)
class SourcePassage:
    source_type: str
    title: str
    locator: str
    snippet: str
    score: float = 0.0
    url: str = ""


@dataclass(frozen=True)
class StrategyDecision:
    symbol: str
    status: str
    direction: str
    score: int
    timeframe_trends: dict[str, str]
    top_down_alignment: str
    fair_value_gap: dict | None
    fundamental_bias: str
    reasons: tuple[str, ...]
    source_passages: tuple[SourcePassage, ...]
    source_rule_status: str
    backtest_ready: bool = False
    execution_ready: bool = False
