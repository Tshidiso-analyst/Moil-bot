from risk.economic_calendar_guard import high_impact_event_day_guard, relevant_currencies


def test_gold_uses_usd_calendar_and_blocks_high_impact_day():
    events = [{"timestamp": "2026-06-10T12:30:00Z", "currency": "USD",
               "impact": "high", "name": "CPI"}]
    allowed, reason = high_impact_event_day_guard(
        "XAUUSD", "2026-06-10T14:00:00Z", events
    )
    assert not allowed
    assert "CPI" in reason


def test_relevant_forex_currencies_are_both_sides():
    assert relevant_currencies("GBPJPYm") == {"GBP", "JPY"}


def test_missing_calendar_fails_closed():
    allowed, reason = high_impact_event_day_guard(
        "EURUSD", "2026-06-10T14:00:00Z", None
    )
    assert not allowed
    assert "unavailable" in reason


def test_other_currency_event_does_not_block_pair():
    events = [{"timestamp": "2026-06-10T12:30:00Z", "currency": "JPY",
               "impact": "high", "name": "BOJ"}]
    allowed, _ = high_impact_event_day_guard(
        "EURUSD", "2026-06-10T14:00:00Z", events
    )
    assert allowed


def test_high_impact_event_on_different_local_day_does_not_block():
    events = [{"timestamp": "2026-06-10T02:00:00Z", "currency": "USD",
               "impact": "high", "name": "Fed speech"}]
    allowed, _ = high_impact_event_day_guard(
        "XAUUSD", "2026-06-10T15:00:00Z", events
    )
    # 02:00 UTC is the prior New York calendar day in June.
    assert allowed
