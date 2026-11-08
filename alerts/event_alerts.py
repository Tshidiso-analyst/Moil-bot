from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable

from alerts.models import AlertEvent
from fundamentals.event_risk import EconomicEvent, EconomicEventAnalyzer


def build_economic_event_alerts(
    events: Iterable[EconomicEvent],
    symbol: str,
    now: datetime | None = None,
    alert_window: timedelta = timedelta(minutes=60),
    analyzer: EconomicEventAnalyzer | None = None,
) -> list[AlertEvent]:
    """Create deduplicatable alerts for relevant upcoming high-impact events.

    This function consumes caller-supplied events only. It does not fetch a
    calendar or treat an empty event list as verified calendar coverage.
    """
    normalized_symbol = str(symbol or "").strip().upper()
    if not normalized_symbol:
        raise ValueError("symbol must not be empty.")
    if alert_window < timedelta(0):
        raise ValueError("alert_window cannot be negative.")

    assessed_at = now or datetime.now(timezone.utc)
    if assessed_at.tzinfo is None or assessed_at.utcoffset() is None:
        raise ValueError("now must be timezone-aware.")

    event_list = list(events)
    event_analyzer = analyzer or EconomicEventAnalyzer()
    assessment = event_analyzer.assess(event_list, now=assessed_at)

    alerts = []
    for event in event_list:
        if event.impact != "high" or event.currency.upper() not in normalized_symbol:
            continue

        minutes = (event.scheduled_at - assessed_at).total_seconds() / 60
        if minutes > alert_window.total_seconds() / 60:
            continue
        if minutes < -15:
            continue

        active = (
            event.scheduled_at - event_analyzer.blackout_before
            <= assessed_at
            <= event.scheduled_at + event_analyzer.blackout_after
        )
        severity = "critical" if active else "warning"
        phase = "blackout active" if active else "approaching"
        source_text = f" Source: {event.source}." if event.source else ""
        source_url_text = f" Source URL: {event.source_url}" if event.source_url else ""
        interpretation = next(
            (
                item.release_interpretation
                for item in assessment.high_impact_events
                if item.name == event.name and item.currency == event.currency.upper()
            ),
            "No release interpretation available.",
        )
        minutes_text = (
            f"{abs(minutes):.0f} minutes ago"
            if minutes < 0
            else f"in {minutes:.0f} minutes"
        )
        alerts.append(
            AlertEvent(
                symbol=normalized_symbol,
                alert_type="fundamental_event",
                severity=severity,
                title=f"{event.name}: {phase}",
                message=(
                    f"{event.name} ({event.currency.upper()}) is {minutes_text}. "
                    f"Impact: high. {interpretation}{source_text}{source_url_text}"
                ),
                dedupe_key=(
                    "economic-event:"
                    f"{normalized_symbol}:"
                    f"{event.currency.upper()}:"
                    f"{event.name.strip().lower()}:"
                    f"{event.scheduled_at.isoformat()}"
                ),
            )
        )

    return alerts


__all__ = ["build_economic_event_alerts"]
