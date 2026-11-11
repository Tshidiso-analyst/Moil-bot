from types import SimpleNamespace

import pytest

from execution.demo_pipeline import DemoExecutionError, DemoExecutionPipeline


class FakeMT5:
    ACCOUNT_TRADE_MODE_DEMO = 0
    ACCOUNT_TRADE_MODE_REAL = 2
    SYMBOL_TRADE_MODE_DISABLED = 0
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    TRADE_ACTION_DEAL = 1
    ORDER_TIME_GTC = 0
    ORDER_FILLING_RETURN = 2
    TRADE_RETCODE_DONE = 10009
    TRADE_RETCODE_DONE_PARTIAL = 10010
    DEAL_ENTRY_IN = 0

    def __init__(self, *, trade_mode=0, check_code=0):
        self.sent = []
        self.check_code = check_code
        self.account = SimpleNamespace(
            trade_mode=trade_mode,
            trade_allowed=True,
            trade_expert=True,
            balance=10_000.0,
            margin_free=5_000.0,
        )
        self.info = SimpleNamespace(
            trade_mode=4,
            point=0.00001,
            digits=5,
            trade_stops_level=10,
            volume_step=0.01,
            volume_min=0.01,
            volume_max=100.0,
        )
        self.tick = SimpleNamespace(bid=1.10000, ask=1.10020)

    def account_info(self):
        return self.account

    def last_error(self):
        return (0, "ok")

    def history_deals_get(self, start, end):
        return []

    def positions_get(self):
        return []

    def symbol_select(self, symbol, enabled):
        return True

    def symbol_info(self, symbol):
        return self.info

    def symbol_info_tick(self, symbol):
        return self.tick

    def order_calc_profit(self, order_type, symbol, volume, entry, stop):
        return (stop - entry) * 100_000 * volume if order_type == self.ORDER_TYPE_BUY else (entry - stop) * 100_000 * volume

    def order_calc_margin(self, order_type, symbol, volume, entry):
        return 100.0 * volume

    def order_check(self, request):
        return SimpleNamespace(retcode=self.check_code, comment="checked")

    def order_send(self, request):
        self.sent.append(request)
        return SimpleNamespace(retcode=self.TRADE_RETCODE_DONE, order=12345, deal=12345, price=request["price"], comment="filled")


def execute(fake, **overrides):
    arguments = {
        "symbol": "EURUSD",
        "direction": "bullish",
        "stop_loss": 1.09920,
        "take_profit": 1.10220,
        "risk_percent": 1.0,
        "confirmation": True,
        "session_confirmed": True,
        "no_high_impact_news_confirmed": True,
    }
    arguments.update(overrides)
    return DemoExecutionPipeline(fake).execute_market_order(**arguments)


def test_demo_order_is_sized_from_broker_profit_calculation_and_sent():
    fake = FakeMT5()
    result = execute(fake)

    assert result.status == "accepted"
    assert result.ticket == 12345
    assert result.volume == pytest.approx(0.99)  # conservative floor avoids exceeding the 1% cap
    assert result.estimated_loss <= result.risk_amount
    assert result.request["sl"] == 1.0992
    assert result.request["tp"] == 1.1022
    assert len(fake.sent) == 1


def test_real_account_is_hard_blocked_before_order_send():
    fake = FakeMT5(trade_mode=FakeMT5.ACCOUNT_TRADE_MODE_REAL)

    with pytest.raises(DemoExecutionError, match="only on an MT5 DEMO"):
        execute(fake)

    assert fake.sent == []


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"confirmation": False}, "Explicit demo-order confirmation"),
        ({"session_confirmed": False}, "permitted trading session"),
        ({"no_high_impact_news_confirmed": False}, "high-impact news"),
        ({"risk_percent": 1.01}, "no more than 1%"),
        ({"stop_loss": 1.10100}, "stop loss must be below entry"),
    ],
)
def test_required_safety_confirmations_and_levels_are_enforced(overrides, message):
    fake = FakeMT5()

    with pytest.raises(DemoExecutionError, match=message):
        execute(fake, **overrides)

    assert fake.sent == []


def test_order_check_rejection_prevents_order_send():
    fake = FakeMT5(check_code=10016)

    with pytest.raises(DemoExecutionError, match="order_check rejected"):
        execute(fake)

    assert fake.sent == []


def test_existing_position_blocks_second_trade():
    fake = FakeMT5()
    fake.positions_get = lambda: [SimpleNamespace(ticket=7)]

    with pytest.raises(DemoExecutionError, match="close existing positions"):
        execute(fake)

    assert fake.sent == []


def test_existing_bot_deal_in_last_24_hours_blocks_second_daily_entry():
    fake = FakeMT5()
    fake.history_deals_get = lambda start, end: [
        SimpleNamespace(magic=731111, entry=FakeMT5.DEAL_ENTRY_IN)
    ]

    with pytest.raises(DemoExecutionError, match="already exists"):
        execute(fake)

    assert fake.sent == []
