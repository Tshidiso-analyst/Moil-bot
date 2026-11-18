from datetime import datetime, timezone
import time
from types import SimpleNamespace

import pandas as pd

from execution.orchestrator import TradeExecutionOrchestrator, MT5ExecutionService
from execution.account_policy import AccountPolicy
import pytest


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

    def __init__(self):
        self.account = SimpleNamespace(
            trade_mode=0, trade_allowed=True, trade_expert=True,
            balance=10_000.0, equity=10_000.0, margin_free=5_000.0,
        )
        self.info = SimpleNamespace(
            name="XAUUSD.a", point=0.01, trade_tick_size=0.01,
            trade_tick_value=1.0, trade_contract_size=100.0,
            volume_min=0.01, volume_max=100.0, volume_step=0.01,
            trade_stops_level=10,
        )
        self.tick = SimpleNamespace(bid=2500.0, ask=2500.2, time=time.time())
        self.positions = []
        self.deals = []
        self.sent = []

    def account_info(self):
        return self.account

    def positions_get(self):
        return self.positions

    def history_deals_get(self, start, end):
        return self.deals

    def order_calc_profit(self, order_type, symbol, volume, entry, stop):
        if order_type == self.ORDER_TYPE_BUY:
            return (stop - entry) * 100 * volume
        return (entry - stop) * 100 * volume

    def order_calc_margin(self, order_type, symbol, volume, price):
        return 100.0 * volume

    def symbol_select(self, symbol, enabled):
        return True

    def symbol_info(self, symbol):
        return self.info

    def symbol_info_tick(self, symbol):
        return self.tick

    def order_check(self, request):
        return SimpleNamespace(retcode=0, comment="checked")

    def order_send(self, request):
        self.sent.append(request)
        return SimpleNamespace(
            retcode=self.TRADE_RETCODE_DONE, order=123, deal=123,
            price=request["price"], comment="filled",
        )

    def last_error(self):
        return (0, "ok")


def make_orchestrator(*, allow_execution=False, mt5=None):
    fake = mt5 or FakeMT5()
    service = SimpleNamespace(mt5=fake, connected=True)
    return TradeExecutionOrchestrator(service, allow_execution=allow_execution), fake


def assessment(**overrides):
    values = {
        "symbol": "XAUUSD",
        "direction": "bullish",
        "setup_valid": True,
        "confirmation": True,
        "structure_valid": True,
        "liquidity_valid": True,
        "macro_bias_valid": True,
        "high_impact_news": False,
        "stop_loss": 2485.0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def market_data():
    return pd.DataFrame([
        {"close": 2495.0, "low": 2485.0, "high": 2505.0},
        {"close": 2500.0, "low": 2490.0, "high": 2510.0},
    ])


def plan(orchestrator, **overrides):
    args = {
        "symbol": "XAUUSD.a",
        "dataframe": market_data(),
        "fundamental_bias": "bullish",
        "assessment": assessment(),
        "proposed_risk_percent": 1.0,
        "daily_loss_percent": 0.0,
        "current_exposure_percent": 0.0,
        "account_balance": 10_000.0,
        "risk_percent": 1.0,
    }
    args.update(overrides)
    return orchestrator.build_execution_plan(**args)


def test_plan_uses_broker_gold_spec_and_caps_volume_at_002():
    orchestrator, _ = make_orchestrator()
    result = plan(orchestrator)
    assert result.allowed is True
    assert result.symbol == "XAUUSD.a"
    assert result.order["volume"] == 0.02
    assert result.risk.estimated_loss <= result.risk.risk_amount


def test_non_gold_symbol_is_rejected():
    orchestrator, _ = make_orchestrator()
    result = plan(orchestrator, symbol="EURUSD")
    assert result.allowed is False
    assert "XAUUSD only" in result.reason


def test_ten_daily_entries_block_new_execution_plan():
    fake = FakeMT5()
    fake.deals = [
        SimpleNamespace(magic=731111, entry=FakeMT5.DEAL_ENTRY_IN, order=1000 + i,
                        type=FakeMT5.DEAL_TYPE_BUY, profit=0, commission=0, swap=0, fee=0)
        for i in range(10)
    ]
    orchestrator, _ = make_orchestrator(mt5=fake)
    result = plan(orchestrator)
    assert result.allowed is False
    assert "Daily entry limit reached" in result.reason


def test_three_open_positions_block_new_execution_plan():
    fake = FakeMT5()
    fake.positions = [
        SimpleNamespace(symbol="XAUUSD.a", volume=0.01, price_open=2500.0,
                        sl=2499.0, type=FakeMT5.POSITION_TYPE_BUY,
                        profit=0.0, swap=0.0,
                        time=int(datetime.now(timezone.utc).timestamp()))
        for _ in range(3)
    ]
    orchestrator, _ = make_orchestrator(mt5=fake)
    result = plan(orchestrator)
    assert result.allowed is False
    assert "Open trade limit reached" in result.reason


def test_missing_portfolio_history_fails_closed():
    fake = FakeMT5()
    fake.history_deals_get = lambda start, end: None
    orchestrator, _ = make_orchestrator(mt5=fake)
    result = plan(orchestrator)
    assert result.allowed is False
    assert "deal history unavailable" in result.reason


def test_execution_is_disabled_by_default_even_when_plan_passes():
    orchestrator, fake = make_orchestrator()
    result = orchestrator.execute(
        symbol="XAUUSD.a", dataframe=market_data(), fundamental_bias="bullish", assessment=assessment(),
        proposed_risk_percent=1.0, daily_loss_percent=0.0,
        current_exposure_percent=0.0, account_balance=10_000.0,
        risk_percent=1.0, magic=731111,
    )
    assert result.status == "disabled"
    assert fake.sent == []


def test_enabled_execution_still_requires_demo_and_uses_injected_mt5():
    orchestrator, fake = make_orchestrator(allow_execution=True)
    result = orchestrator.execute(
        symbol="XAUUSD.a", dataframe=market_data(), fundamental_bias="bullish", assessment=assessment(),
        proposed_risk_percent=1.0, daily_loss_percent=0.0,
        current_exposure_percent=0.0, account_balance=10_000.0,
        risk_percent=1.0, magic=731111,
    )
    assert result.status == "accepted"
    assert len(fake.sent) == 1
    assert fake.sent[0]["volume"] == 0.02


def test_real_account_is_rejected_even_if_execution_flag_is_enabled():
    fake = FakeMT5()
    fake.account.trade_mode = 2
    orchestrator, fake = make_orchestrator(allow_execution=True, mt5=fake)
    result = orchestrator.execute(
        symbol="XAUUSD.a", dataframe=market_data(), fundamental_bias="bullish", assessment=assessment(),
        proposed_risk_percent=1.0, daily_loss_percent=0.0,
        current_exposure_percent=0.0, account_balance=10_000.0,
        risk_percent=1.0, magic=731111,
    )
    assert result.status == "rejected"
    assert fake.sent == []



def test_missing_strategy_assessment_blocks_candle_only_execution():
    orchestrator, _ = make_orchestrator()
    result = plan(orchestrator, assessment=None)
    assert result.allowed is False
    assert "TradeAssessment is required" in result.reason


def test_unconfirmed_strategy_assessment_blocks_execution():
    orchestrator, _ = make_orchestrator()
    result = plan(orchestrator, assessment=assessment(confirmation=False, setup_valid=False))
    assert result.allowed is False
    assert "not confirmed" in result.reason


def test_invalid_structure_or_missing_liquidity_blocks_execution():
    orchestrator, _ = make_orchestrator()
    result = plan(orchestrator, assessment=assessment(liquidity_valid=False))
    assert result.allowed is False
    assert "Liquidity context" in result.reason

def test_plan_uses_lower_equity_not_higher_balance_for_risk_budget():
    fake = FakeMT5()
    fake.account.balance = 10_000.0
    fake.account.equity = 500.0
    orchestrator, _ = make_orchestrator(mt5=fake)
    result = plan(orchestrator)
    assert result.allowed is False
    assert "below broker minimum" in result.reason


def test_plan_fails_closed_when_equity_unavailable():
    fake = FakeMT5()
    del fake.account.equity
    orchestrator, _ = make_orchestrator(mt5=fake)
    result = plan(orchestrator)
    assert result.allowed is False
    assert "equity is invalid" in result.reason

def test_orchestrator_blocks_stale_tick_before_order_send():
    orchestrator, fake = make_orchestrator(allow_execution=True)
    fake.tick.time = time.time() - 120
    result = orchestrator.execute(
        symbol="XAUUSD.a", dataframe=market_data(), fundamental_bias="bullish",
        assessment=assessment(), proposed_risk_percent=1.0,
        daily_loss_percent=0.0, current_exposure_percent=0.0,
        account_balance=10_000.0, risk_percent=1.0, magic=731111,
    )
    assert result.status == "blocked"
    assert "stale" in result.reason
    assert fake.sent == []


def test_orchestrator_rechecks_portfolio_after_order_check():
    orchestrator, fake = make_orchestrator(allow_execution=True)
    original = fake.order_check

    def changed_portfolio(request):
        fake.deals = [
            SimpleNamespace(magic=731111, entry=FakeMT5.DEAL_ENTRY_IN,
                            order=1000 + i, type=FakeMT5.DEAL_TYPE_BUY,
                            profit=0, commission=0, swap=0, fee=0)
            for i in range(10)
        ]
        return original(request)

    fake.order_check = changed_portfolio
    result = orchestrator.execute(
        symbol="XAUUSD.a", dataframe=market_data(), fundamental_bias="bullish",
        assessment=assessment(), proposed_risk_percent=1.0,
        daily_loss_percent=0.0, current_exposure_percent=0.0,
        account_balance=10_000.0, risk_percent=1.0, magic=731111,
    )
    assert result.status == "rejected"
    assert "Portfolio limits changed" in result.reason
    assert fake.sent == []


def test_orchestrator_rechecks_demo_account_after_order_check():
    orchestrator, fake = make_orchestrator(allow_execution=True)
    original = fake.order_check

    def changed_account(request):
        fake.account.trade_mode = 2
        return original(request)

    fake.order_check = changed_account
    result = orchestrator.execute(
        symbol="XAUUSD.a", dataframe=market_data(), fundamental_bias="bullish",
        assessment=assessment(), proposed_risk_percent=1.0,
        daily_loss_percent=0.0, current_exposure_percent=0.0,
        account_balance=10_000.0, risk_percent=1.0, magic=731111,
    )
    assert result.status == "rejected"
    assert "account mode changed" in result.reason
    assert fake.sent == []

def test_broker_adapter_rejects_direct_order_without_assessment():
    fake = FakeMT5()
    adapter = MT5ExecutionService(mt5_module=fake, enabled=True)
    with pytest.raises(RuntimeError, match="Validated strategy assessment"):
        adapter.open_market_order(
            symbol="XAUUSD.a", direction="bullish", volume=0.02,
            price=2500.2, stop_loss=2485.0, take_profit=2530.6,
        )
    assert fake.sent == []


def test_broker_adapter_rejects_direct_order_with_unconfirmed_assessment():
    fake = FakeMT5()
    adapter = MT5ExecutionService(mt5_module=fake, enabled=True)
    with pytest.raises(RuntimeError, match="confirmation or safety checks"):
        adapter.open_market_order(
            symbol="XAUUSD.a", direction="bullish", volume=0.02,
            price=2500.2, stop_loss=2485.0, take_profit=2530.6,
            assessment=assessment(confirmation=False),
        )
    assert fake.sent == []

def test_real_order_requires_explicit_real_policy_and_matching_account():
    fake = FakeMT5()
    fake.account.trade_mode = fake.ACCOUNT_TRADE_MODE_REAL
    service = SimpleNamespace(mt5=fake, connected=True)
    policy = AccountPolicy(mode="real", execution_enabled=True, real_trading_approved=True)
    orchestrator = TradeExecutionOrchestrator(service, allow_execution=True, account_policy=policy)
    result = orchestrator.execute(
        symbol="XAUUSD.a", dataframe=market_data(), fundamental_bias="bullish",
        assessment=assessment(), proposed_risk_percent=1.0,
        daily_loss_percent=0.0, current_exposure_percent=0.0,
        account_balance=10_000.0, risk_percent=1.0, magic=731111,
    )
    assert result.status == "accepted"
    assert len(fake.sent) == 1


def test_real_order_kill_switch_blocks_submission():
    fake = FakeMT5()
    fake.account.trade_mode = fake.ACCOUNT_TRADE_MODE_REAL
    service = SimpleNamespace(mt5=fake, connected=True)
    policy = AccountPolicy(mode="real", execution_enabled=True, real_trading_approved=True, kill_switch=True)
    orchestrator = TradeExecutionOrchestrator(service, allow_execution=True, account_policy=policy)
    result = orchestrator.execute(
        symbol="XAUUSD.a", dataframe=market_data(), fundamental_bias="bullish",
        assessment=assessment(), proposed_risk_percent=1.0,
        daily_loss_percent=0.0, current_exposure_percent=0.0,
        account_balance=10_000.0, risk_percent=1.0, magic=731111,
    )
    assert result.status == "rejected"
    assert fake.sent == []

def test_orchestrator_blocks_duplicate_order_within_one_minute():
    orchestrator, fake = make_orchestrator(allow_execution=True)
    kwargs = dict(
        symbol="XAUUSD.a", dataframe=market_data(), fundamental_bias="bullish",
        assessment=assessment(), proposed_risk_percent=1.0,
        daily_loss_percent=0.0, current_exposure_percent=0.0,
        account_balance=10_000.0, risk_percent=1.0, magic=731111,
    )
    first = orchestrator.execute(**kwargs)
    second = orchestrator.execute(**kwargs)
    assert first.status == "accepted"
    assert second.status == "blocked"
    assert "Duplicate" in second.reason
    assert len(fake.sent) == 1
