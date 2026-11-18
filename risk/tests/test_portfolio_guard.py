import pytest

from risk.portfolio_guard import portfolio_daily_trade_guard


def _trades(count, *, start="2026-06-10T13:00:00Z", symbol="XAUUSD"):
    return [{"symbol": symbol, "entry_time": start} for _ in range(count)]


def test_ninth_entry_is_allowed_and_tenth_entry_is_rejected_portfolio_wide():
    trades = _trades(9, symbol="EURUSD")
    allowed, _ = portfolio_daily_trade_guard(
        trades, candidate_timestamp="2026-06-10T14:00:00Z"
    )
    assert allowed

    allowed, reason = portfolio_daily_trade_guard(
        _trades(10, symbol="XAUUSD"),
        candidate_timestamp="2026-06-10T14:00:00Z",
    )
    assert not allowed
    assert "10/10" in reason
    assert "across all instruments" in reason


def test_entries_on_previous_new_york_calendar_day_do_not_block():
    # 01:00 UTC on June 10 is 21:00 on June 9 in New York.
    trades = _trades(10, start="2026-06-10T01:00:00Z")
    allowed, _ = portfolio_daily_trade_guard(
        trades, candidate_timestamp="2026-06-10T15:00:00Z"
    )
    assert allowed


def test_new_york_midnight_boundary_is_respected():
    trades = _trades(10, start="2026-06-11T03:30:00Z")  # June 10, 23:30 EDT
    allowed, _ = portfolio_daily_trade_guard(
        trades, candidate_timestamp="2026-06-11T04:30:00Z"  # June 11, 00:30 EDT
    )
    assert allowed


def test_empty_portfolio_allows_first_entry():
    allowed, _ = portfolio_daily_trade_guard(
        [], candidate_timestamp="2026-06-10T14:00:00Z"
    )
    assert allowed


def test_invalid_timestamps_fail_closed():
    allowed, reason = portfolio_daily_trade_guard(
        [{"symbol": "XAUUSD", "entry_time": "not-a-time"}],
        candidate_timestamp="2026-06-10T14:00:00Z",
    )
    assert not allowed
    assert "invalid" in reason


@pytest.mark.parametrize("limit", [0, -1, 1.5, True])
def test_daily_limit_must_be_positive_integer(limit):
    with pytest.raises(ValueError, match="positive integer"):
        portfolio_daily_trade_guard(
            [], candidate_timestamp="2026-06-10T14:00:00Z",
            max_trades_per_day=limit,
        )



def test_daily_guard_rejects_limit_above_ten():
    allowed, reason = portfolio_daily_trade_guard(
        [], candidate_timestamp="2026-06-10T13:00:00Z",
        max_trades_per_day=11,
    )
    assert allowed is False
    assert "invalid" in reason.lower()


def test_daily_guard_requires_new_york_calendar():
    allowed, reason = portfolio_daily_trade_guard(
        [], candidate_timestamp="2026-06-10T13:00:00Z",
        timezone_name="UTC",
    )
    assert allowed is False
    assert "America/New_York" in reason
