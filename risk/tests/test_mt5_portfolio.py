from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from risk.mt5_portfolio import PortfolioSnapshotError, build_mt5_portfolio_snapshot


class FakeMT5:
    DEAL_ENTRY_IN = 0
    DEAL_ENTRY_INOUT = 2
    DEAL_TYPE_BUY = 0
    DEAL_TYPE_SELL = 1
    POSITION_TYPE_BUY = 0
    POSITION_TYPE_SELL = 1
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1

    def __init__(self):
        self.account = SimpleNamespace(balance=10_000.0)
        self.positions = []
        self.deals = []
        self.history_range = None

    def account_info(self):
        return self.account

    def positions_get(self):
        return self.positions

    def history_deals_get(self, start, end):
        self.history_range = (start, end)
        return self.deals

    def order_calc_profit(self, order_type, symbol, volume, entry, stop):
        if order_type == self.ORDER_TYPE_BUY:
            return (stop - entry) * 100 * volume
        return (entry - stop) * 100 * volume

    def last_error(self):
        return (0, "ok")


def test_snapshot_counts_only_bot_entry_deals_across_symbols():
    mt5 = FakeMT5()
    mt5.deals = [
        SimpleNamespace(magic=731111, entry=0, type=0, profit=0, commission=0, swap=0, fee=0, symbol="XAUUSD.a", order=100),
        SimpleNamespace(magic=731111, entry=0, type=1, profit=0, commission=0, swap=0, fee=0, symbol="XAUUSD", order=101),
        SimpleNamespace(magic=123, entry=0, type=0, profit=0, commission=0, swap=0, fee=0, symbol="EURUSD", order=102),
        SimpleNamespace(magic=731111, entry=1, type=0, profit=0, commission=0, swap=0, fee=0, symbol="XAUUSD", order=103),
    ]
    now = datetime(2026, 6, 10, 15, 0, tzinfo=timezone.utc)
    snapshot = build_mt5_portfolio_snapshot(mt5, magic=731111, now=now)
    assert snapshot.daily_entries == 2
    assert snapshot.open_positions == 0
    assert snapshot.exposure_percent == 0
    assert snapshot.daily_loss_percent == 0
    assert snapshot.ny_trade_date == "2026-06-10"


def test_snapshot_uses_new_york_midnight_for_history_window():
    mt5 = FakeMT5()
    now = datetime(2026, 6, 10, 3, 0, tzinfo=timezone.utc)
    build_mt5_portfolio_snapshot(mt5, magic=731111, now=now)
    start, end = mt5.history_range
    assert start == datetime(2026, 6, 9, 4, 0, tzinfo=timezone.utc)
    assert end == now


def test_snapshot_counts_open_positions_and_stop_risk():
    mt5 = FakeMT5()
    mt5.positions = [
        SimpleNamespace(
            symbol="XAUUSD.a", volume=0.02, price_open=2500.0,
            sl=2490.0, type=FakeMT5.POSITION_TYPE_BUY, profit=5.0, swap=-1.0, time=1781100000,
        )
    ]
    snapshot = build_mt5_portfolio_snapshot(
        mt5, magic=731111,
        now=datetime(2026, 6, 10, 15, 0, tzinfo=timezone.utc),
    )
    assert snapshot.open_positions == 1
    assert snapshot.exposure_percent == pytest.approx(0.2)
    assert snapshot.daily_net_pnl == pytest.approx(4.0)


def test_snapshot_calculates_daily_loss_from_realized_and_floating_pnl():
    mt5 = FakeMT5()
    mt5.account.balance = 9_895.0
    mt5.deals = [
        SimpleNamespace(magic=731111, entry=1, order=500, type=FakeMT5.DEAL_TYPE_BUY,
                        profit=-100.0, commission=-5.0, swap=0.0, fee=0.0)
    ]
    snapshot = build_mt5_portfolio_snapshot(
        mt5, magic=731111,
        now=datetime(2026, 6, 10, 15, 0, tzinfo=timezone.utc),
    )
    assert snapshot.daily_net_pnl == pytest.approx(-105.0)
    assert snapshot.daily_loss_percent == pytest.approx(1.05)


@pytest.mark.parametrize("method", ["account_info", "positions_get", "history_deals_get"])
def test_snapshot_fails_closed_when_broker_data_is_missing(method):
    mt5 = FakeMT5()
    setattr(mt5, method, lambda *args: None)
    with pytest.raises(PortfolioSnapshotError):
        build_mt5_portfolio_snapshot(
            mt5, magic=731111,
            now=datetime(2026, 6, 10, 15, 0, tzinfo=timezone.utc),
        )


def test_snapshot_fails_closed_for_open_position_without_stop_loss():
    mt5 = FakeMT5()
    mt5.positions = [
        SimpleNamespace(
            symbol="XAUUSD", volume=0.02, price_open=2500.0,
            sl=0.0, type=FakeMT5.POSITION_TYPE_BUY, profit=0.0, swap=0.0, time=1781100000,
        )
    ]
    with pytest.raises(PortfolioSnapshotError, match="position stop loss"):
        build_mt5_portfolio_snapshot(
            mt5, magic=731111,
            now=datetime(2026, 6, 10, 15, 0, tzinfo=timezone.utc),
        )


def test_snapshot_requires_timezone_aware_now():
    with pytest.raises(ValueError, match="timezone-aware"):
        build_mt5_portfolio_snapshot(FakeMT5(), magic=731111, now=datetime(2026, 6, 10))



def test_snapshot_fails_closed_for_position_carried_from_previous_day():
    mt5 = FakeMT5()
    mt5.positions = [
        SimpleNamespace(
            symbol="XAUUSD", volume=0.02, price_open=2500.0,
            sl=2490.0, type=FakeMT5.POSITION_TYPE_BUY,
            profit=0.0, swap=0.0, time=1781010000,
        )
    ]
    with pytest.raises(PortfolioSnapshotError, match="predates the New York trading day"):
        build_mt5_portfolio_snapshot(
            mt5, magic=731111,
            now=datetime(2026, 6, 10, 15, 0, tzinfo=timezone.utc),
        )


def test_snapshot_fails_closed_for_non_trading_account_adjustment():
    mt5 = FakeMT5()
    mt5.deals = [
        SimpleNamespace(
            magic=0, entry=0, order=900, type=2, profit=500.0,
            commission=0.0, swap=0.0, fee=0.0,
        )
    ]
    with pytest.raises(PortfolioSnapshotError, match="non-trading account adjustment"):
        build_mt5_portfolio_snapshot(
            mt5, magic=731111,
            now=datetime(2026, 6, 10, 15, 0, tzinfo=timezone.utc),
        )
