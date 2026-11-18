"""Paper viewer must never submit broker orders."""
import time
from types import SimpleNamespace

import pytest

from dashboard.paper_trading import paper_snapshot, page


class FakeMT5:
    ACCOUNT_TRADE_MODE_DEMO = 0
    TIMEFRAME_M15 = 15
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1

    def __init__(self):
        self.account = SimpleNamespace(trade_mode=0, balance=500, equity=500, currency="ZAR")
        self.tick = SimpleNamespace(time=time.time(), bid=3765.1, ask=3765.3)
        self.sent = []
        now = int(time.time()) - 35 * 900
        self.rates = [
            dict(time=now + i * 900, open=3700 + i * .1,
                 high=3701 + i * .1, low=3699 + i * .1, close=3700 + i * .1)
            for i in range(30)
        ]

    def account_info(self):
        return self.account

    def symbol_select(self, symbol, enabled):
        return True

    def symbol_info_tick(self, symbol):
        return self.tick

    def copy_rates_from_pos(self, symbol, timeframe, start, count):
        return self.rates

    def order_calc_profit(self, order_type, symbol, volume, entry, exit_price):
        return (exit_price - entry) * volume * 1717.5 * (1 if order_type == 0 else -1)

    def order_send(self, request):
        self.sent.append(request)
        raise AssertionError("Paper viewer must never submit an order")


def test_read_only_snapshot_and_html():
    fake = FakeMT5()
    data = paper_snapshot(fake)
    assert data["execution"] == "DISABLED"
    assert data["risk_budget"] == 5
    assert b"MT5 ORDERS: DISABLED" in page(data)
    assert fake.sent == []


def test_rejects_real_account():
    fake = FakeMT5()
    fake.account.trade_mode = 2
    with pytest.raises(RuntimeError, match="DEMO"):
        paper_snapshot(fake)
    assert fake.sent == []


def test_rejects_stale_quotes():
    fake = FakeMT5()
    fake.tick.time -= 120
    with pytest.raises(RuntimeError, match="stale"):
        paper_snapshot(fake)
    assert fake.sent == []


def test_rejects_non_gold():
    fake = FakeMT5()
    with pytest.raises(ValueError):
        paper_snapshot(fake, "EURUSD")
    assert fake.sent == []
