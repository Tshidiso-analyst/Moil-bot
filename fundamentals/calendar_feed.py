from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from fundamentals.event_risk import EconomicEvent


class CalendarFeedError(RuntimeError):
    """Raised when a configured economic-calendar feed cannot be trusted."""


@dataclass(frozen=True)
class CalendarSnapshot:
    events: tuple[EconomicEvent, ...]
    fetched_at: datetime
    coverage_start: datetime
    coverage_end: datetime
    source: str


def parse_timestamp(value: Any, field_name: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise CalendarFeedError(f"{field_name} must be an ISO-8601 timestamp.")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise CalendarFeedError(f"{field_name} is not a valid ISO-8601 timestamp.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise CalendarFeedError(f"{field_name} must include a timezone.")
    return parsed.astimezone(timezone.utc)


def _optional_number(value: Any, field_name: str) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CalendarFeedError(f"{field_name} must be numeric or null.")
    return float(value)


class HttpEconomicCalendarProvider:
    """Read a documented JSON calendar endpoint; never scrapes or guesses events.

    Expected response:
      {
        "source": "provider-name",
        "fetched_at": "2026-11-07T12:00:00Z",
        "coverage_start": "2026-11-07T00:00:00Z",
        "coverage_end": "2026-11-14T00:00:00Z",
        "events": [{
          "name": "US CPI", "currency": "USD",
          "scheduled_at": "2026-11-10T13:30:00Z",
          "impact": "high", "actual": null, "forecast": null,
          "previous": null, "surprise_bias": "context_dependent",
          "source_url": "https://provider.example/event/123"
        }]
      }

    The provider must explicitly certify the interval it covers. A successful
    HTTP response alone is not proof that the requested period is complete.
    """

    def __init__(
        self,
        url: str,
        token: str = "",
        timeout_seconds: float = 8.0,
        max_age: timedelta = timedelta(minutes=15),
        max_bytes: int = 2_000_000,
    ) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"https", "http"} or not parsed.netloc:
            raise CalendarFeedError("Calendar URL must be an absolute HTTP(S) URL.")
        if timeout_seconds <= 0 or max_age <= timedelta(0) or max_bytes <= 0:
            raise ValueError("Timeout, maximum age and response size must be positive.")
        self.url = url
        self.token = token
        self.timeout_seconds = timeout_seconds
        self.max_age = max_age
        self.max_bytes = max_bytes

    @classmethod
    def from_environment(cls) -> "HttpEconomicCalendarProvider | None":
        url = os.getenv("MOILBOT_CALENDAR_URL", "").strip()
        if not url:
            return None
        return cls(
            url=url,
            token=os.getenv("MOILBOT_CALENDAR_TOKEN", ""),
            timeout_seconds=float(os.getenv("MOILBOT_CALENDAR_TIMEOUT", "8")),
            max_age=timedelta(seconds=int(os.getenv("MOILBOT_CALENDAR_MAX_AGE_SECONDS", "900"))),
        )

    def fetch(self, now: datetime | None = None) -> CalendarSnapshot:
        checked_at = now or datetime.now(timezone.utc)
        if checked_at.tzinfo is None or checked_at.utcoffset() is None:
            raise ValueError("now must be timezone-aware.")
        checked_at = checked_at.astimezone(timezone.utc)

        headers = {"Accept": "application/json", "User-Agent": "MoilBot-EconomicCalendar/1.0"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = Request(self.url, headers=headers, method="GET")
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read(self.max_bytes + 1)
        except HTTPError as exc:
            raise CalendarFeedError(f"Calendar provider returned HTTP {exc.code}.") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise CalendarFeedError(f"Calendar provider request failed: {exc}") from exc

        if len(raw) > self.max_bytes:
            raise CalendarFeedError("Calendar response exceeded the configured size limit.")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CalendarFeedError("Calendar provider did not return valid UTF-8 JSON.") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("events"), list):
            raise CalendarFeedError("Calendar response must contain an events array.")

        source = str(payload.get("source", "")).strip()
        if not source:
            raise CalendarFeedError("Calendar response must identify its source.")
        fetched_at = parse_timestamp(payload.get("fetched_at"), "fetched_at")
        coverage_start = parse_timestamp(payload.get("coverage_start"), "coverage_start")
        coverage_end = parse_timestamp(payload.get("coverage_end"), "coverage_end")
        if coverage_start >= coverage_end:
            raise CalendarFeedError("Calendar coverage_start must be before coverage_end.")
        if fetched_at > checked_at + timedelta(minutes=2):
            raise CalendarFeedError("Calendar fetched_at is unexpectedly in the future.")
        if checked_at - fetched_at > self.max_age:
            raise CalendarFeedError("Calendar feed is stale; refusing to verify event coverage.")
        if not coverage_start <= checked_at <= coverage_end:
            raise CalendarFeedError("Calendar feed does not cover the current time.")

        events: list[EconomicEvent] = []
        for index, item in enumerate(payload["events"]):
            if not isinstance(item, dict):
                raise CalendarFeedError(f"events[{index}] must be an object.")
            try:
                events.append(
                    EconomicEvent(
                        name=str(item.get("name", "")),
                        currency=str(item.get("currency", "")),
                        scheduled_at=parse_timestamp(item.get("scheduled_at"), f"events[{index}].scheduled_at"),
                        impact=item.get("impact", "unknown"),
                        actual=_optional_number(item.get("actual"), f"events[{index}].actual"),
                        forecast=_optional_number(item.get("forecast"), f"events[{index}].forecast"),
                        previous=_optional_number(item.get("previous"), f"events[{index}].previous"),
                        surprise_bias=item.get("surprise_bias", "context_dependent"),
                        source=source,
                        source_url=str(item.get("source_url", "")),
                    )
                )
            except (TypeError, ValueError) as exc:
                raise CalendarFeedError(f"Invalid calendar event at index {index}: {exc}") from exc

        return CalendarSnapshot(
            events=tuple(events),
            fetched_at=fetched_at,
            coverage_start=coverage_start,
            coverage_end=coverage_end,
            source=source,
        )


__all__ = [
    "CalendarFeedError",
    "CalendarSnapshot",
    "HttpEconomicCalendarProvider",
    "parse_timestamp",
]
