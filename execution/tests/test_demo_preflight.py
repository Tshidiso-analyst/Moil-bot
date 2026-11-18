"""Safety tests for read-only DEMO preflight."""
import time
from types import SimpleNamespace

from execution.demo_preflight import inspect_demo


class FakeMT5:
    ACCOUNT_TRADE_MODE_DEMO = 0
    SYMBOL_TRADE_MODE_FULL = 4
    ORDER_TYPE_BUY = 0

    def __init__(self, *, balance=500, mode=0, min_lot=0.01, quote_age=0):
        self.account = SimpleNamespace(
            trade_mode=mode, trade_allowed=True, trade_expert=True,
            balance=balance, equity=balance, margin_free=balance, currency="ZAR"
        )
        self.info = SimpleNamespace(volume_min=min_lot, volume_step=0.01,
                                    volume_max=200, trade_mode=4)
        self.tick = SimpleNamespace(ask=3771.0, time=time.time() - quote_age)
        self.sent = []

    def account_info(self):
        return self.account

    def symbol_select(self, symbol, enabled):
        return True

    def symbol_info(self, symbol):
        return self.info

    def symbol_info_tick(self, symbol):
        return self.tick

    def order_calc_profit(self, order_type, symbol, volume, entry, stop):
        return (stop - entry) * volume * 1717.5

    def order_calc_margin(self, order_type, symbol, volume, entry):
        return 3237.5 * volume

    def order_send(self, request):
        self.sent.append(request)
        raise AssertionError("Preflight must never send an order")


def test_small_zar_account_blocks_all_sampled_gold_stops():
    mt5 = FakeMT5()
    result = inspect_demo(mt5)
    assert result["ready_for_order"] is False
    assert result["risk_budget"] == 5.0
    assert all(not item["within_1pct_and_margin"] for item in result["scenarios"])
    assert mt5.sent == []


def test_preflight_never_authorizes_orders_even_if_scenario_affordable():
    mt5 = FakeMT5(balance=100000)
    result = inspect_demo(mt5)
    assert any(item["within_1pct_and_margin"] for item in result["scenarios"])
    assert result["ready_for_order"] is False
    assert mt5.sent == []


def test_real_account_fails_closed_without_sending():
    mt5 = FakeMT5(mode=2)
    result = inspect_demo(mt5)
    assert "BLOCKED" in result["checks"]["account"]
    assert result["scenarios"] == []
    assert mt5.sent == []


def test_stale_quote_fails_closed():
    mt5 = FakeMT5(quote_age=120)
    result = inspect_demo(mt5)
    assert "BLOCKED" in result["checks"]["quote"]
    assert mt5.sent == []


def test_broker_minimum_above_cap_fails_closed():
    mt5 = FakeMT5(min_lot=0.1)
    result = inspect_demo(mt5)
    assert "BLOCKED" in result["checks"]["volume"]
    assert mt5.sent == []
