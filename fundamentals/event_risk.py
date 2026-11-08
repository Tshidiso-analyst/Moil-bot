from __future__ import annotations

from dataclasses import dataclass
import math
from datetime import datetime, timedelta, timezone
from typing import Iterable, Literal


Impact = Literal["high", "medium", "low", "unknown"]
SurpriseBias = Literal[
    "higher_is_currency_positive",
    "lower_is_currency_positive",
    "context_dependent",
]


@dataclass(frozen=True)
class EconomicEvent:
    """A calendar event supplied by a trusted calendar or a user.

    Times must be timezone-aware. The analyzer deliberately does not fetch a
    calendar or invent release values; callers own source validation.
    """

    name: str
    currency: str
    scheduled_at: datetime
    impact: Impact = "unknown"
    actual: float | None = None
    forecast: float | None = None
    previous: float | None = None
    surprise_bias: SurpriseBias = "context_dependent"
    source: str = ""
    source_url: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Event name must be a non-empty string.")
        if not isinstance(self.currency, str) or not self.currency.strip():
            raise ValueError("Event currency must be a non-empty string.")
        if (
            not isinstance(self.scheduled_at, datetime)
            or self.scheduled_at.tzinfo is None
            or self.scheduled_at.utcoffset() is None
        ):
            raise ValueError("scheduled_at must be a timezone-aware datetime.")
        if self.impact not in {"high", "medium", "low", "unknown"}:
            raise ValueError("impact must be high, medium, low or unknown.")
        if self.surprise_bias not in {
            "higher_is_currency_positive",
            "lower_is_currency_positive",
            "context_dependent",
        }:
            raise ValueError("Unsupported surprise_bias.")
        for field_name in ("actual", "forecast", "previous"):
            value = getattr(self, field_name)
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{field_name} must be numeric or None.")
            try:
                finite = math.isfinite(float(value))
            except (OverflowError, ValueError):
                finite = False
            if not finite:
                raise ValueError(f"{field_name} must be finite.")


@dataclass(frozen=True)
class EventAssessment:
    name: str
    currency: str
    impact: Impact
    minutes_until_release: float
    blackout_active: bool
    surprise: float | None
    release_interpretation: str
    directional_bias: str
    source: str
    source_url: str


@dataclass(frozen=True)
class EventRiskAssessment:
    assessed_at: datetime
    blackout_active: bool
    block_new_trades: bool
    high_impact_events: tuple[EventAssessment, ...]
    reasons: tuple[str, ...]


class EconomicEventAnalyzer:
    """Assess event proximity and reported surprises without forecasting.

    Defaults are intentionally conservative: 30 minutes before and 15 minutes
    after a high-impact release. A blackout blocks new trades only; it does not
    instruct callers to close existing positions.
    """

    def __init__(
        self,
        blackout_before: timedelta = timedelta(minutes=30),
        blackout_after: timedelta = timedelta(minutes=15),
    ) -> None:
        if blackout_before < timedelta(0) or blackout_after < timedelta(0):
            raise ValueError("Blackout windows cannot be negative.")
        self.blackout_before = blackout_before
        self.blackout_after = blackout_after

    @staticmethod
    def _bias(event: EconomicEvent, surprise: float | None) -> tuple[str, str]:
        if surprise is None:
            return "neutral", "No actual-versus-forecast surprise is available."
        if surprise == 0:
            return "neutral", "Actual matched forecast; no directional surprise."
        if event.surprise_bias == "context_dependent":
            return (
                "neutral",
                "A surprise exists, but this event requires broader policy and market context.",
            )
        positive_surprise = surprise > 0
        currency_positive = (
            positive_surprise
            if event.surprise_bias == "higher_is_currency_positive"
            else not positive_surprise
        )
        return (
            "currency_positive" if currency_positive else "currency_negative",
            "Actual beat forecast." if positive_surprise else "Actual missed forecast.",
        )

    def assess(
        self,
        events: Iterable[EconomicEvent],
        now: datetime | None = None,
    ) -> EventRiskAssessment:
        assessed_at = now or datetime.now(timezone.utc)
        if assessed_at.tzinfo is None or assessed_at.utcoffset() is None:
            raise ValueError("now must be timezone-aware.")

        high_impact = []
        reasons = []
        for event in events:
            if event.impact != "high":
                continue
            minutes = (event.scheduled_at - assessed_at).total_seconds() / 60
            blackout_start = event.scheduled_at - self.blackout_before
            blackout_end = event.scheduled_at + self.blackout_after
            active = blackout_start <= assessed_at <= blackout_end
            surprise = (
                float(event.actual) - float(event.forecast)
                if event.actual is not None and event.forecast is not None
                else None
            )
            bias, interpretation = self._bias(event, surprise)
            high_impact.append(
                EventAssessment(
                    name=event.name,
                    currency=event.currency.upper(),
                    impact=event.impact,
                    minutes_until_release=minutes,
                    blackout_active=active,
                    surprise=surprise,
                    release_interpretation=interpretation,
                    directional_bias=bias,
                    source=event.source,
                    source_url=event.source_url,
                )
            )
            if active:
                reasons.append(
                    f"{event.name} ({event.currency.upper()}) is inside the configured "
                    "high-impact news blackout window."
                )

        high_impact.sort(key=lambda item: item.minutes_until_release)
        if not high_impact:
            reasons.append("No high-impact events were supplied; calendar coverage is unverified.")
        elif not reasons:
            reasons.append("No supplied high-impact event is inside the configured blackout window.")

        return EventRiskAssessment(
            assessed_at=assessed_at,
            blackout_active=bool(reasons and any(item.blackout_active for item in high_impact)),
            block_new_trades=any(item.blackout_active for item in high_impact),
            high_impact_events=tuple(high_impact),
            reasons=tuple(reasons),
        )


__all__ = [
    "EconomicEvent",
    "EconomicEventAnalyzer",
    "EventAssessment",
    "EventRiskAssessment",
]
