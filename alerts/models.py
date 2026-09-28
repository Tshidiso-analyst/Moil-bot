from dataclasses import dataclass, field
from datetime import datetime


VALID_SEVERITIES = {"info", "warning", "critical"}
VALID_STATUSES = {"new", "acknowledged", "resolved"}

VALID_EVIDENCE_SOURCES = {
    "technical",
    "fundamental",
    "risk",
    "tradingview",
    "mt5",
    "system",
}

VALID_EVIDENCE_IMPACTS = {
    "supporting",
    "neutral",
    "warning",
    "blocking",
}

VALID_DECISION_STATUSES = {
    "qualified",
    "rejected",
    "entered",
    "monitoring",
    "closed",
}

VALID_TRADE_DIRECTIONS = {"BUY", "SELL"}

VALID_NOTIFICATION_CHANNELS = {
    "in_app",
    "email",
    "message",
}


@dataclass(frozen=True)
class Evidence:
    category: str
    fact: str
    source: str
    impact: str = "supporting"

    def __post_init__(self):
        if not self.category.strip():
            raise ValueError("Evidence category must not be empty.")

        if not self.fact.strip():
            raise ValueError("Evidence fact must not be empty.")

        if self.source not in VALID_EVIDENCE_SOURCES:
            raise ValueError(
                f"Invalid evidence source: {self.source}. "
                f"Expected one of {sorted(VALID_EVIDENCE_SOURCES)}."
            )

        if self.impact not in VALID_EVIDENCE_IMPACTS:
            raise ValueError(
                f"Invalid evidence impact: {self.impact}. "
                f"Expected one of {sorted(VALID_EVIDENCE_IMPACTS)}."
            )


@dataclass(frozen=True)
class TradingViewReference:
    """
    Reference to external TradingView information.

    This model stores externally supplied information only.
    Moil Bot must never pretend its own analysis came from TradingView.
    """

    symbol: str
    timeframe: str
    summary: str
    url: str = ""

    def __post_init__(self):
        if not self.symbol.strip():
            raise ValueError("TradingView symbol must not be empty.")

        if not self.timeframe.strip():
            raise ValueError("TradingView timeframe must not be empty.")

        if not self.summary.strip():
            raise ValueError("TradingView summary must not be empty.")


@dataclass(frozen=True)
class TradeDecision:
    decision_id: str
    symbol: str
    market: str
    asset_class: str
    direction: str
    strategy: str
    timeframes: tuple[str, ...]
    decision: str
    entry: float
    stop_loss: float
    take_profit: float
    expected_move: float
    risk_percent: float
    risk_reward: float
    technical_evidence: tuple[Evidence, ...] = field(default_factory=tuple)
    fundamental_evidence: tuple[Evidence, ...] = field(default_factory=tuple)
    risk_evidence: tuple[Evidence, ...] = field(default_factory=tuple)
    tradingview_references: tuple[TradingViewReference, ...] = field(
        default_factory=tuple
    )
    invalidation_conditions: tuple[str, ...] = field(default_factory=tuple)
    reason: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        if not self.decision_id.strip():
            raise ValueError("Decision ID must not be empty.")

        if not self.symbol.strip():
            raise ValueError("Symbol must not be empty.")

        if not self.market.strip():
            raise ValueError("Market must not be empty.")

        if not self.asset_class.strip():
            raise ValueError("Asset class must not be empty.")

        if self.direction not in VALID_TRADE_DIRECTIONS:
            raise ValueError(
                f"Invalid direction: {self.direction}. "
                f"Expected one of {sorted(VALID_TRADE_DIRECTIONS)}."
            )

        if not self.strategy.strip():
            raise ValueError("Strategy must not be empty.")

        if not self.timeframes:
            raise ValueError("At least one timeframe is required.")

        if self.decision not in VALID_DECISION_STATUSES:
            raise ValueError(
                f"Invalid decision: {self.decision}. "
                f"Expected one of {sorted(VALID_DECISION_STATUSES)}."
            )

        if self.entry <= 0:
            raise ValueError("Entry must be greater than zero.")

        if self.stop_loss <= 0:
            raise ValueError("Stop loss must be greater than zero.")

        if self.take_profit <= 0:
            raise ValueError("Take profit must be greater than zero.")

        if self.expected_move <= 0:
            raise ValueError("Expected move must be greater than zero.")

        if not 0 < self.risk_percent <= 100:
            raise ValueError("Risk percent must be greater than 0 and <= 100.")

        if self.risk_reward <= 0:
            raise ValueError("Risk/reward must be greater than zero.")

        if not self.reason.strip():
            raise ValueError("Trade decision reason must not be empty.")

        if not self.invalidation_conditions:
            raise ValueError(
                "At least one invalidation condition is required."
            )


@dataclass(frozen=True)
class NotificationSettings:
    enabled: bool = True
    trade_entered: bool = True
    stop_loss_hit: bool = True
    take_profit_hit: bool = True
    fundamental_events: bool = True
    technical_setup_alerts: bool = True
    risk_warnings: bool = True
    trade_explanations: bool = True
    in_app: bool = True
    email: bool = False
    message: bool = False

    def enabled_channels(self) -> tuple[str, ...]:
        if not self.enabled:
            return ()

        channels = []

        if self.in_app:
            channels.append("in_app")

        if self.email:
            channels.append("email")

        if self.message:
            channels.append("message")

        return tuple(channels)


@dataclass(frozen=True)
class Alert:
    alert_id: str
    symbol: str
    alert_type: str
    severity: str
    title: str
    message: str
    created_at: datetime
    status: str = "new"
    decision_id: str | None = None

    def __post_init__(self):
        if not self.alert_id.strip():
            raise ValueError("Alert ID must not be empty.")

        if not self.symbol.strip():
            raise ValueError("Symbol must not be empty.")

        if not self.alert_type.strip():
            raise ValueError("Alert type must not be empty.")

        if self.severity not in VALID_SEVERITIES:
            raise ValueError(
                f"Invalid severity: {self.severity}. "
                f"Expected one of {sorted(VALID_SEVERITIES)}."
            )

        if not self.title.strip():
            raise ValueError("Alert title must not be empty.")

        if not self.message.strip():
            raise ValueError("Alert message must not be empty.")

        if self.status not in VALID_STATUSES:
            raise ValueError(
                f"Invalid status: {self.status}. "
                f"Expected one of {sorted(VALID_STATUSES)}."
            )


@dataclass(frozen=True)
class AlertEvent:
    symbol: str
    alert_type: str
    severity: str
    title: str
    message: str
    decision_id: str | None = None

    def __post_init__(self):
        if not self.symbol.strip():
            raise ValueError("Symbol must not be empty.")

        if not self.alert_type.strip():
            raise ValueError("Alert type must not be empty.")

        if self.severity not in VALID_SEVERITIES:
            raise ValueError(
                f"Invalid severity: {self.severity}. "
                f"Expected one of {sorted(VALID_SEVERITIES)}."
            )

        if not self.title.strip():
            raise ValueError("Alert title must not be empty.")

        if not self.message.strip():
            raise ValueError("Alert message must not be empty.")
