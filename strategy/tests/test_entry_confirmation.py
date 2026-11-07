from datetime import datetime, timedelta, timezone

import pytest

from fundamentals.event_risk import EconomicEvent
from strategy.entry_confirmation import EntryConfirmationEvaluator


def at_ny(year=2026, month=11, day=9, hour=9, minute=45):
    # November 9, 2026 is in the New York standard-time period (UTC-5).
    return datetime(year, month, day, hour, minute, tzinfo=timezone(timedelta(hours=-5)))


def evaluate(**overrides):
    values = {
        "symbol": "EURUSD",
        "direction": "bullish",
        "assessed_at": at_ny(),
        "event_calendar_verified": True,
        "events": [],
        "macro_bias_valid": True,
        "daily_trade_count": 0,
        "risk_percent": 1.0,
        "liquidity_sweep_confirmed": True,
        "sweep_reversal_direction": "bullish",
        "bos_direction": "bullish",
        "bos_body_close_confirmed": True,
        "fvg_retracement_confirmed": True,
    }
    values.update(overrides)
    return EntryConfirmationEvaluator().evaluate(**values)


def test_complete_ny_opening_hour_checklist_qualifies_for_research_only():
    decision = evaluate()

    assert decision.qualified is True
    assert decision.entry_model == "liquidity_sweep_bos_fvg_retracement"
    assert decision.execution_approved is False


def test_order_block_retest_is_an_alternative_entry_location():
    decision = evaluate(
        fvg_retracement_confirmed=False,
        order_block_retest_confirmed=True,
    )

    assert decision.qualified is True
    assert decision.entry_model == "liquidity_sweep_bos_order_block_retest"


def test_no_setup_after_first_ny_opening_hour_is_rejected():
    decision = evaluate(assessed_at=at_ny(hour=10, minute=30))

    assert decision.qualified is False
    assert any("opening hour" in reason for reason in decision.reasons)


def test_one_trade_per_day_limit_is_enforced():
    decision = evaluate(daily_trade_count=1)

    assert decision.qualified is False
    assert any("one-trade-per-day" in reason for reason in decision.reasons)


def test_risk_above_one_percent_is_rejected():
    decision = evaluate(risk_percent=1.01)

    assert decision.qualified is False
    assert any("1% maximum" in reason for reason in decision.reasons)


def test_unverified_calendar_fails_closed():
    decision = evaluate(event_calendar_verified=False)

    assert decision.qualified is False
    assert any("unverified" in reason for reason in decision.reasons)


def test_high_impact_event_blocks_the_whole_matching_currency_day():
    event = EconomicEvent(
        name="US CPI",
        currency="USD",
        scheduled_at=at_ny(hour=8, minute=30),
        impact="high",
    )
    decision = evaluate(events=[event])

    assert decision.qualified is False
    assert any("No trade on this event day" in reason for reason in decision.reasons)


def test_unrelated_currency_event_does_not_block_symbol():
    event = EconomicEvent(
        name="UK CPI",
        currency="GBP",
        scheduled_at=at_ny(hour=8, minute=30),
        impact="high",
    )
    decision = evaluate(events=[event])

    assert decision.qualified is True


def test_bos_wick_without_body_close_is_rejected():
    decision = evaluate(bos_body_close_confirmed=False)

    assert decision.qualified is False
    assert any("candle-body close" in reason for reason in decision.reasons)


def test_wrong_bos_direction_is_rejected():
    decision = evaluate(bos_direction="bearish")

    assert decision.qualified is False
    assert any("BOS direction" in reason for reason in decision.reasons)


def test_sweep_and_bos_are_both_required():
    decision = evaluate(liquidity_sweep_confirmed=False)

    assert decision.qualified is False
    assert any("liquidity sweep" in reason for reason in decision.reasons)


def test_sweep_reversal_direction_must_match():
    decision = evaluate(sweep_reversal_direction="bearish")

    assert decision.qualified is False
    assert any("reversal direction" in reason for reason in decision.reasons)


def test_fvg_or_order_block_confirmation_is_required():
    decision = evaluate(
        fvg_retracement_confirmed=False,
        order_block_retest_confirmed=False,
    )

    assert decision.qualified is False
    assert any("FVG retracement or order-block retest" in reason for reason in decision.reasons)


def test_macro_bias_must_be_verified_and_aligned():
    decision = evaluate(macro_bias_valid=False)

    assert decision.qualified is False
    assert any("macro bias" in reason for reason in decision.reasons)


def test_weekend_is_rejected():
    # November 7, 2026 is Saturday.
    decision = evaluate(assessed_at=at_ny(day=7))

    assert decision.qualified is False
    assert any("weekend" in reason for reason in decision.reasons)


def test_naive_timestamp_is_rejected():
    with pytest.raises(ValueError, match="timezone-aware"):
        evaluate(assessed_at=datetime(2026, 11, 9, 9, 45))


def test_invalid_direction_is_rejected():
    with pytest.raises(ValueError, match="bullish or bearish"):
        evaluate(direction="neutral")

def test_new_york_dst_conversion_uses_the_correct_opening_hour():
    # March 9, 2026 is after the US daylight-saving transition:
    # 09:45 in New York is 13:45 UTC (not 14:45 UTC).
    utc_time = datetime(2026, 3, 9, 13, 45, tzinfo=timezone.utc)
    decision = evaluate(assessed_at=utc_time)

    assert decision.qualified is True


@pytest.mark.parametrize(
    "field_name",
    [
        "event_calendar_verified",
        "macro_bias_valid",
        "liquidity_sweep_confirmed",
        "bos_body_close_confirmed",
        "fvg_retracement_confirmed",
        "order_block_retest_confirmed",
    ],
)
def test_confirmation_flags_must_be_real_booleans(field_name):
    with pytest.raises(ValueError, match="must be a boolean"):
        evaluate(**{field_name: "false"})
