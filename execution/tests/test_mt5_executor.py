from types import SimpleNamespace

import pytest

from execution.mt5_executor import MT5ExecutionService


class FakeMT5:
    ACCOUNT_TRADE_MODE_DEMO = 0
    ACCOUNT_TRADE_MODE_REAL = 2
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    POSITION_TYPE_BUY = 0
    POSITION_TYPE_SELL = 1
    DEAL_ENTRY_IN = 0
    DEAL_ENTRY_INOUT = 2
    DEAL_ENTRY_OUT = 1
    DEAL_ENTRY_OUT_BY = 3
    DEAL_TYPE_BUY = 0
    DEAL_TYPE_SELL = 1
    TRADE_ACTION_DEAL = 1
    ORDER_TIME_GTC = 0
    ORDER_FILLING_RETURN = 2
    TRADE_RETCODE_DONE = 10009
    TRADE_RETCODE_DONE_PARTIAL = 10010

    def __init__(self, trade_mode=0):
        self.account = SimpleNamespace(
            trade_mode=trade_mode, trade_allowed=True, trade_expert=True,
            balance=10_000.0, equity=10_000.0, margin_free=5_000.0,
        )
        self.info = SimpleNamespace(
            visible=True, point=0.01, trade_stops_level=10,
            trade_mode=4, volume_min=0.01, volume_max=100.0, volume_step=0.01,
        )
        self.tick = SimpleNamespace(bid=2500.0, ask=2500.2)
        self.sent = []

    def account_info(self):
        return self.account

    def symbol_info(self, symbol):
        return self.info

    def symbol_info_tick(self, symbol):
        return self.tick

    def order_calc_margin(self, order_type, symbol, volume, price):
        return 100.0 * volume

    def symbol_select(self, symbol, enabled):
        return True

    def order_calc_profit(self, order_type, symbol, volume, entry, stop):
        return (stop - entry) * 100 * volume if order_type == 0 else (entry - stop) * 100 * volume

    def positions_get(self):
        return []

    def history_deals_get(self, start, end):
        return []

    def order_check(self, request):
        return SimpleNamespace(retcode=0)

    def order_send(self, request):
        self.sent.append(request)
        return SimpleNamespace(
            retcode=self.TRADE_RETCODE_DONE, order=123,
            price=request["price"], comment="filled",
        )

    def last_error(self):
        return (0, "ok")


def execute(service, **kwargs):
    return service.place_market_order(
        "XAUUSD.a", "bullish", 0.02,
        stop_loss=2490.0, take_profit=2520.0, **kwargs,
    )


def test_direct_mt5_order_service_is_disabled_by_default():
    fake = FakeMT5()
    service = MT5ExecutionService(fake)
    service.connected = True
    with pytest.raises(RuntimeError, match="disabled by default"):
        execute(service)
    assert fake.sent == []


def test_direct_mt5_order_service_requires_demo_account():
    fake = FakeMT5(trade_mode=FakeMT5.ACCOUNT_TRADE_MODE_REAL)
    service = MT5ExecutionService(fake, enabled=True)
    service.connected = True
    with pytest.raises(RuntimeError, match="verified DEMO"):
        execute(service)
    assert fake.sent == []


def test_direct_mt5_order_service_enforces_portfolio_and_broker_risk():
    fake = FakeMT5()
    service = MT5ExecutionService(fake, enabled=True)
    service.connected = True
    result = execute(service)
    assert result["ticket"] == 123
    assert result["symbol"] == "XAUUSD.a"
    assert result["volume"] == 0.02
    assert len(fake.sent) == 1


def test_direct_mt5_order_service_rejects_non_gold():
    fake = FakeMT5()
    service = MT5ExecutionService(fake, enabled=True)
    service.connected = True
    with pytest.raises(ValueError, match="XAUUSD only"):
        service.place_market_order("EURUSD", "buy", 0.01, stop_loss=1.0, take_profit=1.2)
    assert fake.sent == []


def test_direct_mt5_order_service_rejects_risk_above_one_percent():
    fake = FakeMT5()
    service = MT5ExecutionService(fake, enabled=True)
    service.connected = True
    with pytest.raises(RuntimeError, match="1% per-trade"):
        service.place_market_order(
            "XAUUSD", "buy", 0.02, stop_loss=2000.0, take_profit=2600.0,
        )
    assert fake.sent == []

def test_direct_executor_rejects_risk_based_on_equity_not_balance():
    fake = FakeMT5()
    fake.account.equity = 500.0
    service = MT5ExecutionService(fake, enabled=True)
    service.connected = True
    with pytest.raises(RuntimeError, match="1% per-trade"):
        execute(service)
    assert fake.sent == []


def test_direct_executor_fails_closed_without_equity():
    fake = FakeMT5()
    del fake.account.equity
    service = MT5ExecutionService(fake, enabled=True)
    service.connected = True
    with pytest.raises(RuntimeError, match="account balance or proposed order risk"):
        execute(service)
    assert fake.sent == []
