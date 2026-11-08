from types import SimpleNamespace

import pytest

from execution.mt5_executor import MT5ExecutionService


class FakeMT5:
    ACCOUNT_TRADE_MODE_DEMO = 0
    ACCOUNT_TRADE_MODE_CONTEST = 1
    ACCOUNT_TRADE_MODE_REAL = 2
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    TRADE_ACTION_DEAL = 1
    ORDER_TIME_GTC = 0
    ORDER_FILLING_RETURN = 2
    TRADE_RETCODE_DONE = 10009
    TRADE_RETCODE_DONE_PARTIAL = 10010
    POSITION_TYPE_BUY = 0

    def __init__(self, trade_mode=0):
        self.trade_mode = trade_mode
        self.sent = []
        self.info = SimpleNamespace(visible=True, volume_min=0.01, volume_max=10.0, volume_step=0.01)
        self.tick = SimpleNamespace(bid=1.1000, ask=1.1002)

    def account_info(self):
        return SimpleNamespace(trade_mode=self.trade_mode, login=12345, server="Broker-Demo")

    def symbol_info(self, symbol):
        return self.info

    def symbol_info_tick(self, symbol):
        return self.tick

    def order_calc_profit(self, order_type, symbol, volume, entry, stop):
        return -1000.0 * float(volume)

    def order_send(self, request):
        self.sent.append(request)
        return SimpleNamespace(retcode=10009, order=98765, deal=98765, price=request["price"])

    def last_error(self):
        return (0, "ok")

    def shutdown(self):
        pass


def test_execution_refuses_real_account():
    mt5 = FakeMT5(trade_mode=2)
    service = MT5ExecutionService(mt5)
    with pytest.raises(RuntimeError, match="not DEMO"):
        service.adopt_existing_connection()
    assert mt5.sent == []


def test_demo_account_can_be_adopted_and_volume_is_risk_sized():
    mt5 = FakeMT5(trade_mode=0)
    service = MT5ExecutionService(mt5)
    connected = service.adopt_existing_connection()
    volume = service.calculate_volume_for_risk(
        symbol="EURUSD", direction="bullish", entry=1.1002,
        stop_loss=1.0990, balance=10000.0, risk_percent=0.5,
    )
    assert connected["account_mode"] == "DEMO"
    assert volume == pytest.approx(0.05)


def test_demo_market_order_is_sent_only_with_protective_levels_and_risk_cap():
    mt5 = FakeMT5(trade_mode=0)
    service = MT5ExecutionService(mt5)
    service.adopt_existing_connection()
    result = service.place_market_order(
        symbol="EURUSD", direction="bullish", volume=0.05,
        stop_loss=1.0990, take_profit=1.1020, max_risk_amount=50.0,
    )
    assert result["ticket"] == 98765
    assert result["account_mode"] == "DEMO"
    assert len(mt5.sent) == 1
    assert mt5.sent[0]["sl"] == 1.0990
    assert mt5.sent[0]["tp"] == 1.1020


def test_real_account_switch_after_connection_blocks_order():
    mt5 = FakeMT5(trade_mode=0)
    service = MT5ExecutionService(mt5)
    service.adopt_existing_connection()
    mt5.trade_mode = 2
    with pytest.raises(RuntimeError, match="not DEMO"):
        service.place_market_order(
            "EURUSD", "bullish", 0.01, stop_loss=1.0990, take_profit=1.1020
        )
    assert mt5.sent == []


def test_market_order_rejects_missing_stop_loss_or_take_profit():
    mt5 = FakeMT5(trade_mode=0)
    service = MT5ExecutionService(mt5)
    service.adopt_existing_connection()
    with pytest.raises(ValueError, match="mandatory"):
        service.place_market_order("EURUSD", "bullish", 0.01)
    assert mt5.sent == []


def test_market_order_requires_a_finite_positive_risk_budget():
    mt5 = FakeMT5(trade_mode=0)
    service = MT5ExecutionService(mt5)
    service.adopt_existing_connection()

    for budget in (None, 0.0, float("nan"), float("inf")):
        with pytest.raises(ValueError, match="max_risk_amount"):
            service.place_market_order(
                "EURUSD", "bullish", 0.01,
                stop_loss=1.0990, take_profit=1.1020,
                max_risk_amount=budget,
            )

    assert mt5.sent == []


def test_market_order_rejects_non_finite_broker_loss_calculation():
    mt5 = FakeMT5(trade_mode=0)
    mt5.order_calc_profit = lambda *args: float("nan")
    service = MT5ExecutionService(mt5)
    service.adopt_existing_connection()

    with pytest.raises(RuntimeError, match="risk budget"):
        service.place_market_order(
            "EURUSD", "bullish", 0.05,
            stop_loss=1.0990, take_profit=1.1020,
            max_risk_amount=50.0,
        )

    assert mt5.sent == []
