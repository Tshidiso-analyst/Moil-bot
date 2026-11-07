from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Iterable

from fundamentals.event_risk import EconomicEvent


@dataclass(frozen=True)
class ReleaseComponent:
    name: str
    category: str
    actual: float | None
    forecast: float | None
    previous: float | None
    comparison: str
    source: str


@dataclass(frozen=True)
class ReleaseAnalysis:
    release_type: str
    currency: str
    release_date: date
    components: tuple[ReleaseComponent, ...]
    assessment: str
    observations: tuple[str, ...]
    macro_bias: str = "unverified"
    trade_direction: str = "none"
    trade_approval: bool = False


# Match specific labels before broad ones to avoid treating core CPI as headline CPI.
_RELEASE_MATCHERS = (
    ("NFP", ("nonfarm payroll", "non-farm payroll", "nonfarm employment", "non-farm employment", "payroll employment", "unemployment rate", "average hourly earnings", "hourly earnings", "labor force participation")),
    ("CPI", ("core cpi", "consumer price index", "cpi")),
    ("FOMC", ("federal funds rate", "fed funds rate", "fomc", "federal reserve interest rate")),
)


def _release_type(name: str) -> str | None:
    normalized = " ".join(name.casefold().replace("_", " ").split())
    for release_type, terms in _RELEASE_MATCHERS:
        if any(term in normalized for term in terms):
            return release_type
    return None


def _component_category(name: str, release_type: str) -> str:
    normalized = name.casefold()
    if release_type == "NFP":
        if "average hourly" in normalized or "hourly earnings" in normalized:
            return "wage_growth"
        if "unemployment" in normalized:
            return "unemployment_rate"
        if "participation" in normalized:
            return "labor_force_participation"
        if "payroll" in normalized or "employment" in normalized:
            return "headline_payrolls"
    if release_type == "CPI":
        if "core" in normalized:
            return "core_inflation"
        if "month" in normalized or "mom" in normalized:
            return "monthly_inflation"
        if "year" in normalized or "yoy" in normalized:
            return "annual_inflation"
        return "headline_inflation"
    if release_type == "FOMC":
        if "press conference" in normalized:
            return "press_conference"
        if "statement" in normalized:
            return "policy_statement"
        if "projection" in normalized or "dot plot" in normalized:
            return "economic_projections"
        if "federal funds" in normalized or "fed funds" in normalized or "interest rate" in normalized:
            return "policy_rate"
        return "policy_communication"
    return "other"


def _comparison(actual: float | None, forecast: float | None) -> str:
    if actual is None or forecast is None:
        return "unavailable"
    if actual > forecast:
        return "above_forecast"
    if actual < forecast:
        return "below_forecast"
    return "in_line"


class EconomicReleaseAnalyzer:
    """Describe release components without converting surprises into trade bias.

    Events are grouped by currency, UTC release date and release family. The
    component comparisons are descriptive only: they do not infer the currency
    reaction, central-bank response, or a trading signal.
    """

    def analyze(self, events: Iterable[EconomicEvent]) -> tuple[ReleaseAnalysis, ...]:
        groups: dict[tuple[str, date, str], list[EconomicEvent]] = {}
        for event in events:
            release_type = _release_type(event.name)
            if release_type is None:
                continue
            if event.scheduled_at.tzinfo is None or event.scheduled_at.utcoffset() is None:
                raise ValueError("Economic event timestamps must be timezone-aware.")
            scheduled = event.scheduled_at.astimezone(timezone.utc)
            key = (event.currency.upper(), scheduled.date(), release_type)
            groups.setdefault(key, []).append(event)

        results: list[ReleaseAnalysis] = []
        for (currency, release_date, release_type), items in sorted(groups.items()):
            components: list[ReleaseComponent] = []
            for event in sorted(items, key=lambda item: (item.scheduled_at, item.name.casefold())):
                comparison = _comparison(event.actual, event.forecast)
                category = _component_category(event.name, release_type)
                components.append(
                    ReleaseComponent(
                        name=event.name,
                        category=category,
                        actual=float(event.actual) if event.actual is not None else None,
                        forecast=float(event.forecast) if event.forecast is not None else None,
                        previous=float(event.previous) if event.previous is not None else None,
                        comparison=comparison,
                        source=event.source,
                    )
                )

            observed = {item.comparison for item in components if item.comparison != "unavailable"}
            if not observed:
                assessment = "unavailable"
                observations = ("Actual-versus-forecast values are not available for this release.",)
            elif "above_forecast" in observed and "below_forecast" in observed:
                assessment = "mixed"
                observations = ("Release components disagree: some were above forecast and others below forecast.",)
            elif observed == {"in_line"}:
                assessment = "in_line"
                observations = ("All comparable release components matched forecast.",)
            elif observed == {"above_forecast"}:
                assessment = "above_forecast"
                observations = ("All comparable release components were above forecast.",)
            elif observed == {"below_forecast"}:
                assessment = "below_forecast"
                observations = ("All comparable release components were below forecast.",)
            else:
                assessment = "partial"
                observations = ("Only some release components have actual-versus-forecast comparisons.",)

            results.append(
                ReleaseAnalysis(
                    release_type=release_type,
                    currency=currency,
                    release_date=release_date,
                    components=tuple(components),
                    assessment=assessment,
                    observations=observations,
                )
            )
        return tuple(results)


__all__ = [
    "EconomicReleaseAnalyzer",
    "ReleaseAnalysis",
    "ReleaseComponent",
]
