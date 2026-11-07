from datetime import datetime, timedelta, timezone

from alerts.engine import AlertEngine
from alerts.event_alerts import build_economic_event_alerts
from fundamentals.event_risk import EconomicEvent


NOW = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)


def event(**overrides):
    values = {
        "name": "CPI",
        "currency": "USD",
        "scheduled_at": NOW + timedelta(minutes=45),
        "impact": "high",
        "source": "fixture-calendar",
        "source_url": "https://example.test/calendar",
    }
    values.update(overrides)
    return EconomicEvent(**values)


def test_upcoming_high_impact_event_creates_warning_for_matching_symbol():
    alerts = build_economic_event_alerts([event()], "EURUSD", now=NOW)

    assert len(alerts) == 1
    assert alerts[0].severity == "warning"
    assert alerts[0].alert_type == "fundamental_event"
    assert "CPI" in alerts[0].title
    assert "fixture-calendar" in alerts[0].message
    assert alerts[0].dedupe_key.startswith("economic-event:USD:")


def test_event_inside_blackout_creates_critical_alert():
    alerts = build_economic_event_alerts(
        [event(scheduled_at=NOW - timedelta(minutes=5))],
        "EURUSD",
        now=NOW,
    )

    assert len(alerts) == 1
    assert alerts[0].severity == "critical"
    assert "blackout active" in alerts[0].title


def test_events_outside_alert_window_and_non_high_impact_are_ignored():
    alerts = build_economic_event_alerts(
        [
            event(scheduled_at=NOW + timedelta(hours=3)),
            event(name="Retail Sales", impact="medium"),
        ],
        "EURUSD",
        now=NOW,
    )

    assert alerts == []


def test_event_for_unrelated_currency_is_ignored():
    assert build_economic_event_alerts([event()], "GBPJPY", now=NOW) == []


def test_repeated_event_alert_is_stored_and_not_resent():
    engine = AlertEngine()
    alert_event = build_economic_event_alerts([event()], "EURUSD", now=NOW)[0]

    first = engine.process(alert_event)
    second = engine.process(alert_event)

    assert first.alert.alert_id == second.alert.alert_id
    assert len(first.notifications) == 1
    assert second.notifications == []
    assert len(engine.get_all_alerts()) == 1


def test_empty_events_do_not_create_alerts():
    assert build_economic_event_alerts([], "EURUSD", now=NOW) == []
