from datetime import datetime, timedelta, timezone

import pytest

from fundamentals.event_risk import EconomicEvent, EconomicEventAnalyzer


NOW = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)


def event(**overrides):
    values = {
        "name": "US CPI",
        "currency": "USD",
        "scheduled_at": NOW + timedelta(minutes=10),
        "impact": "high",
        "source": "test-calendar",
        "source_url": "https://example.com/calendar",
    }
    values.update(overrides)
    return EconomicEvent(**values)


def test_high_impact_event_inside_blackout_blocks_new_trades():
    result = EconomicEventAnalyzer().assess([event()], now=NOW)

    assert result.blackout_active is True
    assert result.block_new_trades is True
    assert "US CPI" in result.reasons[0]


def test_event_outside_blackout_does_not_block():
    result = EconomicEventAnalyzer().assess(
        [event(scheduled_at=NOW + timedelta(hours=2))],
        now=NOW,
    )

    assert result.block_new_trades is False
    assert result.high_impact_events[0].minutes_until_release == 120


def test_post_release_blackout_is_respected():
    result = EconomicEventAnalyzer().assess(
        [event(scheduled_at=NOW - timedelta(minutes=5))],
        now=NOW,
    )

    assert result.block_new_trades is True


def test_low_impact_event_does_not_trigger_high_impact_blackout():
    result = EconomicEventAnalyzer().assess(
        [event(impact="low")],
        now=NOW,
    )

    assert result.block_new_trades is False
    assert result.high_impact_events == ()


def test_actual_forecast_surprise_is_reported_without_guessing_context():
    result = EconomicEventAnalyzer().assess(
        [event(actual=3.4, forecast=3.1, surprise_bias="context_dependent")],
        now=NOW,
    )

    item = result.high_impact_events[0]
    assert item.surprise == pytest.approx(0.3)
    assert item.directional_bias == "neutral"
    assert "broader policy" in item.release_interpretation


def test_explicit_surprise_mapping_can_interpret_direction():
    result = EconomicEventAnalyzer().assess(
        [
            event(
                actual=3.4,
                forecast=3.1,
                surprise_bias="higher_is_currency_positive",
            )
        ],
        now=NOW,
    )

    assert result.high_impact_events[0].directional_bias == "currency_positive"


def test_missing_actual_or_forecast_has_no_directional_bias():
    result = EconomicEventAnalyzer().assess([event(actual=3.4)], now=NOW)

    item = result.high_impact_events[0]
    assert item.surprise is None
    assert item.directional_bias == "neutral"


def test_naive_datetimes_are_rejected():
    with pytest.raises(ValueError, match="timezone-aware"):
        event(scheduled_at=datetime(2026, 11, 7, 12, 0))


def test_negative_blackout_window_is_rejected():
    with pytest.raises(ValueError, match="cannot be negative"):
        EconomicEventAnalyzer(blackout_before=timedelta(minutes=-1))


def test_naive_assessment_time_is_rejected():
    with pytest.raises(ValueError, match="timezone-aware"):
        EconomicEventAnalyzer().assess([], now=datetime(2026, 11, 7, 12, 0))
