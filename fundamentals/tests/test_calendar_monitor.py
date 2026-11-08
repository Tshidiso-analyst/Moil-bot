from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from fundamentals.calendar_feed import CalendarSnapshot
from fundamentals.calendar_monitor import EconomicCalendarMonitor
from fundamentals.event_risk import EconomicEvent


NOW = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)


def snapshot(events=(), fetched_at=NOW):
    return CalendarSnapshot(
        events=tuple(events),
        fetched_at=fetched_at,
        coverage_start=NOW - timedelta(hours=1),
        coverage_end=NOW + timedelta(days=7),
        source="test-calendar",
    )


def test_monitor_marks_successful_covered_feed_verified():
    provider = Mock()
    provider.fetch.return_value = snapshot()
    provider.max_age = timedelta(minutes=15)
    monitor = EconomicCalendarMonitor(provider=provider, symbols=["EURUSD"])

    assert monitor.refresh_once(now=NOW) is True
    assert monitor.is_verified(now=NOW) is True
    assert monitor.status(now=NOW)["source"] == "test-calendar"


def test_monitor_stays_unverified_when_provider_is_missing():
    monitor = EconomicCalendarMonitor(provider=None)

    assert monitor.refresh_once(now=NOW) is False
    assert monitor.is_verified(now=NOW) is False
    assert monitor.status(now=NOW)["configured"] is False


def test_failed_refresh_does_not_replace_previous_snapshot_or_claim_freshness():
    provider = Mock()
    provider.fetch.side_effect = [snapshot(), RuntimeError("provider down")]
    provider.max_age = timedelta(minutes=15)
    monitor = EconomicCalendarMonitor(provider=provider, symbols=[])

    assert monitor.refresh_once(now=NOW) is True
    assert monitor.refresh_once(now=NOW + timedelta(minutes=20)) is False
    assert monitor.is_verified(now=NOW + timedelta(minutes=20)) is False
    assert monitor.status(now=NOW + timedelta(minutes=20))["error"] == "provider down"


def test_monitor_flags_high_impact_release_inside_blackout():
    event = EconomicEvent(
        name="US CPI",
        currency="USD",
        scheduled_at=NOW + timedelta(minutes=10),
        impact="high",
    )
    provider = Mock()
    provider.fetch.return_value = snapshot([event])
    provider.max_age = timedelta(minutes=15)
    monitor = EconomicCalendarMonitor(provider=provider, symbols=["EURUSD"])

    assert monitor.refresh_once(now=NOW) is True
    assert monitor.has_active_high_impact("EURUSD", now=NOW) is True
    assert monitor.has_active_high_impact("EURGBP", now=NOW) is False


def test_monitor_generates_event_alerts_for_configured_symbols():
    event = EconomicEvent(
        name="US CPI",
        currency="USD",
        scheduled_at=NOW + timedelta(minutes=45),
        impact="high",
    )
    provider = Mock()
    provider.fetch.return_value = snapshot([event])
    provider.max_age = timedelta(minutes=15)
    engine = Mock()
    engine.process.return_value = None
    monitor = EconomicCalendarMonitor(
        provider=provider,
        alert_engine=engine,
        symbols=["EURUSD", "GBPUSD"],
    )

    assert monitor.refresh_once(now=NOW) is True
    assert engine.process.call_count == 2

def test_monitor_exposes_release_component_analysis_only_for_verified_snapshot():
    events = [
        EconomicEvent(
            name="Nonfarm Payrolls",
            currency="USD",
            scheduled_at=NOW + timedelta(days=1),
            impact="high",
            actual=220,
            forecast=180,
            previous=150,
        ),
        EconomicEvent(
            name="Unemployment Rate",
            currency="USD",
            scheduled_at=NOW + timedelta(days=1),
            impact="high",
            actual=4.1,
            forecast=4.2,
            previous=4.3,
        ),
    ]
    provider = Mock()
    provider.fetch.return_value = snapshot(events)
    provider.max_age = timedelta(minutes=15)
    monitor = EconomicCalendarMonitor(provider=provider, symbols=[])

    assert monitor.refresh_once(now=NOW) is True
    status = monitor.status(now=NOW)
    assert status["release_analysis"][0]["release_type"] == "NFP"
    assert status["release_analysis"][0]["assessment"] == "mixed"
    assert status["release_analysis"][0]["macro_bias"] == "unverified"
    assert status["release_analysis"][0]["trade_approval"] is False


def test_monitor_does_not_expose_release_analysis_from_stale_snapshot():
    events = [
        EconomicEvent(
            name="US CPI",
            currency="USD",
            scheduled_at=NOW + timedelta(days=1),
            impact="high",
            actual=3.2,
            forecast=3.0,
        )
    ]
    provider = Mock()
    provider.fetch.return_value = snapshot(events)
    provider.max_age = timedelta(minutes=15)
    monitor = EconomicCalendarMonitor(provider=provider, symbols=[])

    assert monitor.refresh_once(now=NOW) is True
    status = monitor.status(now=NOW + timedelta(minutes=20))
    assert status["verified"] is False
    assert status["release_analysis"] == []


def test_monitor_blocks_the_entire_local_date_of_a_high_impact_event():
    event = EconomicEvent(
        name="US CPI",
        currency="USD",
        scheduled_at=NOW + timedelta(hours=5),
        impact="high",
    )
    provider = Mock()
    provider.fetch.return_value = snapshot([event])
    provider.max_age = timedelta(minutes=15)
    monitor = EconomicCalendarMonitor(provider=provider, symbols=["EURUSD"])

    assert monitor.refresh_once(now=NOW) is True
    assert monitor.has_high_impact_today("EURUSD", now=NOW) is True


def test_monitor_does_not_block_the_previous_day_for_tomorrows_event():
    event = EconomicEvent(
        name="US CPI",
        currency="USD",
        scheduled_at=NOW + timedelta(days=1),
        impact="high",
    )
    provider = Mock()
    provider.fetch.return_value = snapshot([event])
    provider.max_age = timedelta(minutes=15)
    monitor = EconomicCalendarMonitor(provider=provider, symbols=["EURUSD"])

    assert monitor.refresh_once(now=NOW) is True
    assert monitor.has_high_impact_today("EURUSD", now=NOW) is False

def test_monitor_uses_new_york_trading_date_across_utc_midnight():
    checked_at = datetime(2026, 11, 8, 4, 45, tzinfo=timezone.utc)
    event = EconomicEvent(
        name="US CPI",
        currency="USD",
        scheduled_at=datetime(2026, 11, 8, 5, 30, tzinfo=timezone.utc),
        impact="high",
    )
    provider = Mock()
    provider.fetch.return_value = snapshot([event], fetched_at=checked_at)
    provider.max_age = timedelta(minutes=15)
    monitor = EconomicCalendarMonitor(provider=provider, symbols=["EURUSD"])

    assert monitor.refresh_once(now=checked_at) is True
    # It is still 23:45 on November 7 in New York; the event is at 00:30
    # on November 8, so the previous New York trading date must not be blocked.
    assert monitor.has_high_impact_today("EURUSD", now=checked_at) is False
