from __future__ import annotations

import os
import threading
from datetime import datetime, timedelta, timezone
from typing import Iterable

from alerts.engine import AlertEngine
from alerts.event_alerts import build_economic_event_alerts
from fundamentals.calendar_feed import CalendarFeedError, CalendarSnapshot, HttpEconomicCalendarProvider
from fundamentals.event_risk import EconomicEventAnalyzer
from fundamentals.release_analysis import EconomicReleaseAnalyzer


class EconomicCalendarMonitor:
    """Poll a configured, coverage-certified calendar and publish event alerts."""

    def __init__(
        self,
        provider: HttpEconomicCalendarProvider | None = None,
        alert_engine: AlertEngine | None = None,
        symbols: Iterable[str] | None = None,
        poll_seconds: int | None = None,
        alert_window: timedelta = timedelta(minutes=60),
    ) -> None:
        poll_seconds = (
            int(os.getenv("MOILBOT_CALENDAR_POLL_SECONDS", "300"))
            if poll_seconds is None
            else poll_seconds
        )
        if poll_seconds < 30:
            raise ValueError("Calendar poll interval must be at least 30 seconds.")
        self.provider = provider if provider is not None else HttpEconomicCalendarProvider.from_environment()
        self.alert_engine = alert_engine or AlertEngine()
        configured_symbols = symbols if symbols is not None else (
            item.strip().upper()
            for item in os.getenv("MOILBOT_CALENDAR_SYMBOLS", "EURUSD,GBPUSD,USDJPY,XAUUSD").split(",")
            if item.strip()
        )
        self.symbols = tuple(dict.fromkeys(str(item).strip().upper() for item in configured_symbols if str(item).strip()))
        self.poll_seconds = poll_seconds
        self.alert_window = alert_window
        self.analyzer = EconomicEventAnalyzer()
        self.release_analyzer = EconomicReleaseAnalyzer()
        self._snapshot: CalendarSnapshot | None = None
        self._last_error = "Calendar provider is not configured." if self.provider is None else ""
        self._last_attempt: datetime | None = None
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def refresh_once(self, now: datetime | None = None) -> bool:
        checked_at = now or datetime.now(timezone.utc)
        if checked_at.tzinfo is None or checked_at.utcoffset() is None:
            raise ValueError("now must be timezone-aware.")
        with self._lock:
            self._last_attempt = checked_at.astimezone(timezone.utc)
        if self.provider is None:
            with self._lock:
                self._last_error = "Calendar provider is not configured."
            return False
        try:
            snapshot = self.provider.fetch(now=checked_at)
            for symbol in self.symbols:
                for event in build_economic_event_alerts(
                    snapshot.events,
                    symbol=symbol,
                    now=checked_at,
                    alert_window=self.alert_window,
                    analyzer=self.analyzer,
                ):
                    self.alert_engine.process(event)
        except Exception as exc:
            with self._lock:
                self._last_error = str(exc)
            return False
        with self._lock:
            self._snapshot = snapshot
            self._last_error = ""
        return True

    def is_verified(self, now: datetime | None = None) -> bool:
        checked_at = now or datetime.now(timezone.utc)
        if checked_at.tzinfo is None or checked_at.utcoffset() is None:
            raise ValueError("now must be timezone-aware.")
        checked_at = checked_at.astimezone(timezone.utc)
        with self._lock:
            snapshot = self._snapshot
        if snapshot is None:
            return False
        max_age = getattr(self.provider, "max_age", timedelta(minutes=15))
        return (
            timedelta(0) <= checked_at - snapshot.fetched_at <= max_age
            and snapshot.coverage_start <= checked_at <= snapshot.coverage_end
        )

    def has_active_high_impact(self, symbol: str, now: datetime | None = None) -> bool:
        events = self.events_for_symbol(symbol, now=now)
        return self.analyzer.assess(events, now=now).block_new_trades

    def events_for_symbol(self, symbol: str, now: datetime | None = None):
        normalized = str(symbol or "").upper()
        with self._lock:
            snapshot = self._snapshot
        if snapshot is None or not self.is_verified(now=now):
            return ()
        return tuple(
            event for event in snapshot.events
            if event.currency.upper() in normalized
        )

    def status(self, now: datetime | None = None) -> dict[str, object]:
        with self._lock:
            snapshot = self._snapshot
            error = self._last_error
            attempted = self._last_attempt
        verified = self.is_verified(now=now)
        release_analysis = []
        if snapshot is not None and verified:
            for release in self.release_analyzer.analyze(snapshot.events):
                release_analysis.append({
                    "release_type": release.release_type,
                    "currency": release.currency,
                    "release_date": release.release_date.isoformat(),
                    "assessment": release.assessment,
                    "macro_bias": release.macro_bias,
                    "trade_direction": release.trade_direction,
                    "trade_approval": release.trade_approval,
                    "components": [
                        {
                            "name": component.name,
                            "category": component.category,
                            "actual": component.actual,
                            "forecast": component.forecast,
                            "previous": component.previous,
                            "comparison": component.comparison,
                        }
                        for component in release.components
                    ],
                    "observations": list(release.observations),
                })
        return {
            "configured": self.provider is not None,
            "verified": verified,
            "source": snapshot.source if snapshot else "",
            "fetched_at": snapshot.fetched_at if snapshot else None,
            "coverage_start": snapshot.coverage_start if snapshot else None,
            "coverage_end": snapshot.coverage_end if snapshot else None,
            "event_count": len(snapshot.events) if snapshot else 0,
            "release_analysis": release_analysis,
            "last_attempt": attempted,
            "error": error,
        }

    def start(self) -> None:
        if self.provider is None or (self._thread and self._thread.is_alive()):
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="moilbot-economic-calendar",
            daemon=True,
        )
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)

    def _run(self) -> None:
        while not self._stop.is_set():
            self.refresh_once()
            self._stop.wait(self.poll_seconds)


__all__ = ["EconomicCalendarMonitor"]
