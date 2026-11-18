from datetime import datetime, timezone
import time
from types import SimpleNamespace

import pytest

from execution.demo_pipeline import DemoExecutionError, DemoExecutionPipeline


class FakeMT5:
    ACCOUNT_TRADE_MODE_DEMO = 0
    ACCOUNT_TRADE_MODE_REAL = 2
    SYMBOL_TRADE_MODE_DISABLED = 0
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    POSITION_TYPE_BUY = 0
    POSITION_TYPE_SELL = 1
    TRADE_ACTION_DEAL = 1
    ORDER_TIME_GTC = 0
    ORDER_FILLING_RETURN = 2
    TRADE_RETCODE_DONE = 10009
    TRADE_RETCODE_DONE_PARTIAL = 10010
    DEAL_ENTRY_IN = 0
    DEAL_ENTRY_INOUT = 2
    DEAL_ENTRY_OUT = 1
    DEAL_ENTRY_OUT_BY = 3
    DEAL_TYPE_BUY = 0
    DEAL_TYPE_SELL = 1

    def __init__(self, *, trade_mode=0, check_code=0):
        self.sent = []
        self.check_code = check_code
        self.account = SimpleNamespace(
            trade_mode=trade_mode,
            trade_allowed=True,
            trade_expert=True,
            balance=10_000.0,
            equity=10_000.0,
            margin_free=5_000.0,
        )
        self.info = SimpleNamespace(
            name="XAUUSD",
            trade_mode=4,
            point=0.01,
            digits=2,
            trade_tick_size=0.01,
            trade_tick_value=1.0,
            trade_contract_size=100.0,
            trade_stops_level=10,
            volume_step=0.01,
            volume_min=0.01,
            volume_max=100.0,
        )
        self.tick = SimpleNamespace(bid=2500.00, ask=2500.20, time=time.time())

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
        if order_type == self.ORDER_TYPE_BUY:
            return (stop - entry) * 100 * volume
        return (entry - stop) * 100 * volume

    def order_calc_margin(self, order_type, symbol, volume, entry):
        return 100.0 * volume

    def order_check(self, request):
        return SimpleNamespace(retcode=self.check_code, comment="checked")

    def order_send(self, request):
        self.sent.append(request)
        return SimpleNamespace(
            retcode=self.TRADE_RETCODE_DONE,
            order=12345,
            deal=12345,
            price=request["price"],
            comment="filled",
        )


def execute(fake, **overrides):
    arguments = {
        "symbol": "XAUUSD",
        "direction": "bullish",
        "stop_loss": 2499.20,
        "take_profit": 2502.20,
        "risk_percent": 1.0,
        "confirmation": True,
        "session_confirmed": True,
        "no_high_impact_news_confirmed": True,
    }
    arguments["assessment"] = SimpleNamespace(symbol="XAUUSD", direction="bullish",
        setup_valid=True, confirmation=True, structure_valid=True,
        liquidity_valid=True, macro_bias_valid=True, high_impact_news=False)
    arguments.update(overrides)
    return DemoExecutionPipeline(fake, enabled=True).execute_market_order(**arguments)


def test_demo_order_is_sized_from_broker_profit_calculation_and_sent():
    fake = FakeMT5()
    result = execute(fake)
    assert result.status == "accepted"
    assert result.ticket == 12345
    assert result.volume == pytest.approx(0.02)
    assert result.estimated_loss <= result.risk_amount
    assert result.request["sl"] == 2499.2
    assert result.request["tp"] == 2502.2
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
        ({"confirmation": "true"}, "Explicit demo-order confirmation"),
        ({"risk_percent": float("nan")}, "no more than 1%"),
        ({"session_confirmed": False}, "permitted trading session"),
        ({"no_high_impact_news_confirmed": False}, "high-impact news"),
        ({"risk_percent": 1.01}, "no more than 1%"),
        ({"stop_loss": 2501.00}, "stop loss must be below entry"),
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


def test_three_existing_positions_block_a_fourth_trade():
    fake = FakeMT5()
    fake.positions_get = lambda: [
        SimpleNamespace(
            ticket=i, symbol="XAUUSD", volume=0.01, price_open=2500.0,
            sl=2499.0, type=FakeMT5.POSITION_TYPE_BUY, profit=0.0, swap=0.0,
            time=int(datetime.now(timezone.utc).timestamp()),
        )
        for i in range(3)
    ]
    with pytest.raises(DemoExecutionError, match="Maximum open positions"):
        execute(fake)
    assert fake.sent == []


def test_ten_bot_entries_in_new_york_day_block_an_eleventh():
    fake = FakeMT5()
    fake.history_deals_get = lambda start, end: [
        SimpleNamespace(
            magic=731111, entry=FakeMT5.DEAL_ENTRY_IN, order=1000 + i,
            type=FakeMT5.DEAL_TYPE_BUY, profit=0.0, commission=0.0,
            swap=0.0, fee=0.0,
        )
        for i in range(10)
    ]
    with pytest.raises(DemoExecutionError, match="Daily entry limit reached"):
        execute(fake)
    assert fake.sent == []


def test_minimum_lot_is_not_forced_when_it_would_exceed_risk_budget():
    fake = FakeMT5()
    fake.order_calc_profit = lambda order_type, symbol, volume, entry, stop: -100_000_000.0 * volume
    with pytest.raises(DemoExecutionError, match="below broker minimum"):
        execute(fake)
    assert fake.sent == []


def test_insufficient_margin_blocks_order_before_send():
    fake = FakeMT5()
    fake.order_calc_margin = lambda order_type, symbol, volume, entry: 6_000.0
    with pytest.raises(DemoExecutionError, match="Insufficient free margin"):
        execute(fake)
    assert fake.sent == []


def test_broker_filling_flags_select_supported_order_type():
    fake = FakeMT5()
    fake.SYMBOL_FILLING_FOK = 1
    fake.SYMBOL_FILLING_IOC = 2
    fake.ORDER_FILLING_FOK = 0
    fake.ORDER_FILLING_IOC = 1
    fake.info.filling_mode = fake.SYMBOL_FILLING_IOC
    result = execute(fake)
    assert result.request["type_filling"] == fake.ORDER_FILLING_IOC


def test_demo_execution_is_disabled_by_default():
    fake = FakeMT5()
    arguments = {
        "symbol": "XAUUSD",
        "direction": "bullish",
        "stop_loss": 2499.20,
        "take_profit": 2502.20,
        "confirmation": True,
        "session_confirmed": True,
        "no_high_impact_news_confirmed": True,
    }
    with pytest.raises(DemoExecutionError, match="disabled by default"):
        DemoExecutionPipeline(fake).execute_market_order(**arguments)
    assert fake.sent == []


def test_non_gold_symbol_is_rejected():
    fake = FakeMT5()
    with pytest.raises(DemoExecutionError, match="XAUUSD only"):
        execute(fake, symbol="EURUSD")
    assert fake.sent == []

def test_demo_pipeline_rejects_order_when_equity_is_below_balance():
    fake = FakeMT5()
    fake.account.equity = 50.0
    with pytest.raises(DemoExecutionError, match="below broker minimum"):
        execute(fake)
    assert fake.sent == []


def test_demo_pipeline_fails_closed_without_equity():
    fake = FakeMT5()
    del fake.account.equity
    with pytest.raises(DemoExecutionError, match="balance or free margin is invalid"):
        execute(fake)
    assert fake.sent == []


def test_demo_pipeline_requires_validated_strategy_assessment():
    fake = FakeMT5()
    with pytest.raises(DemoExecutionError, match="Validated strategy assessment"):
        DemoExecutionPipeline(fake, enabled=True).execute_market_order(
            symbol="XAUUSD", direction="bullish", stop_loss=2499.2,
            take_profit=2502.2, confirmation=True, session_confirmed=True,
            no_high_impact_news_confirmed=True,
        )
    assert fake.sent == []


def test_demo_entry_rejects_stale_quote():
    fake = FakeMT5()
    fake.tick.time = time.time() - 120
    with pytest.raises(DemoExecutionError, match="quote is stale"):
        execute(fake)
    assert fake.sent == []


def test_demo_entry_rejects_future_quote():
    fake = FakeMT5()
    fake.tick.time = time.time() + 120
    with pytest.raises(DemoExecutionError, match="in the future"):
        execute(fake)
    assert fake.sent == []


def test_demo_pipeline_rechecks_account_after_order_check():
    fake = FakeMT5()
    def change_account(request):
        fake.account.trade_mode = fake.ACCOUNT_TRADE_MODE_REAL
        return SimpleNamespace(retcode=0, comment="checked")
    fake.order_check = change_account
    with pytest.raises(DemoExecutionError, match="changed before submission"):
        execute(fake)
    assert fake.sent == []


def test_demo_pipeline_rechecks_quote_after_order_check():
    fake = FakeMT5()
    def change_quote(request):
        fake.tick.ask += 5.0
        return SimpleNamespace(retcode=0, comment="checked")
    fake.order_check = change_quote
    with pytest.raises(DemoExecutionError, match="quote moved"):
        execute(fake)
    assert fake.sent == []
