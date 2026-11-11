from risk.portfolio_guard import portfolio_daily_trade_guard


def test_one_trade_per_day_is_shared_across_symbols():
    trades = [{"symbol": "EURUSD", "entry_time": "2026-06-10T13:00:00Z"}]
    allowed, reason = portfolio_daily_trade_guard(
        trades, candidate_timestamp="2026-06-10T14:00:00Z"
    )
    assert not allowed
    assert "across all instruments" in reason


def test_trade_on_previous_local_day_does_not_block():
    trades = [{"symbol": "XAUUSD", "entry_time": "2026-06-10T01:00:00Z"}]
    allowed, _ = portfolio_daily_trade_guard(
        trades, candidate_timestamp="2026-06-10T15:00:00Z"
    )
    assert allowed


def test_empty_portfolio_allows_first_trade():
    allowed, _ = portfolio_daily_trade_guard(
        [], candidate_timestamp="2026-06-10T14:00:00Z"
    )
    assert allowed
