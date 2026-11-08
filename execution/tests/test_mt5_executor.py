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
    SYMBOL_TRADE_EXECUTION_MARKET = 2
    SYMBOL_FILLING_FOK = 1
    SYMBOL_FILLING_IOC = 2
    ORDER_FILLING_FOK = 0
    ORDER_FILLING_IOC = 1

    def __init__(self, trade_mode=0):
        self.trade_mode = trade_mode
        self.sent = []
        self.initialize_calls = []
        self.requested_login = None
        self.requested_server = ""
        self.order_checks = []
        self.check_result = SimpleNamespace(retcode=0, margin_free=10000.0, comment="Done")
        self.position_result = None
        self.info = SimpleNamespace(visible=True, volume_min=0.01, volume_max=10.0, volume_step=0.01)
        self.tick = SimpleNamespace(bid=1.1000, ask=1.1002)

    def initialize(self, **kwargs):
        self.initialize_calls.append(kwargs)
        self.requested_login = int(kwargs.get("login", 0) or 0)
        self.requested_server = str(kwargs.get("server", ""))
        return True

    def account_info(self):
        return SimpleNamespace(
            trade_mode=self.trade_mode,
            login=self.requested_login or 12345,
            server=self.requested_server or "Broker-Demo",
        )

    def symbol_info(self, symbol):
        return self.info

    def symbol_info_tick(self, symbol):
        return self.tick

    def order_calc_profit(self, order_type, symbol, volume, entry, stop):
        return -1000.0 * float(volume)

    def order_check(self, request):
        self.order_checks.append(request)
        return self.check_result

    def positions_get(self, ticket=None):
        if ticket is None:
            return []
        if self.position_result is not None:
            return self.position_result
        return [SimpleNamespace(
            ticket=ticket, volume=0.05, type=self.POSITION_TYPE_BUY, symbol="EURUSD"
        )]

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



def test_partial_fill_reports_actual_executed_volume():
    mt5 = FakeMT5(trade_mode=0)
    mt5.order_send = lambda request: SimpleNamespace(
        retcode=mt5.TRADE_RETCODE_DONE_PARTIAL,
        order=98765,
        deal=98766,
        price=request["price"],
        volume=0.02,
    )
    service = MT5ExecutionService(mt5)
    service.adopt_existing_connection()

    result = service.place_market_order(
        symbol="EURUSD",
        direction="bullish",
        volume=0.05,
        stop_loss=1.0990,
        take_profit=1.1020,
        max_risk_amount=50.0,
    )

    assert result["volume"] == pytest.approx(0.02)


def test_partial_fill_without_confirmed_volume_requires_manual_inspection():
    mt5 = FakeMT5(trade_mode=0)
    mt5.order_send = lambda request: SimpleNamespace(
        retcode=mt5.TRADE_RETCODE_DONE_PARTIAL,
        order=98765,
        deal=98766,
        price=request["price"],
    )
    service = MT5ExecutionService(mt5)
    service.adopt_existing_connection()

    with pytest.raises(RuntimeError, match="Inspect the DEMO account"):
        service.place_market_order(
            symbol="EURUSD",
            direction="bullish",
            volume=0.05,
            stop_loss=1.0990,
            take_profit=1.1020,
            max_risk_amount=50.0,
        )


def test_execution_connect_accepts_exact_server_for_any_mt5_broker():
    for server in ("Exness-MT5Trial8", "ICMarketsSC-Demo", "Pepperstone-Demo"):
        mt5 = FakeMT5(trade_mode=0)
        service = MT5ExecutionService(mt5)
        result = service.connect(12345, "demo-password", f" {server} ")
        assert result["connected"] is True
        assert mt5.initialize_calls[0]["server"] == server


def test_execution_connect_rejects_missing_or_invalid_credentials_before_initialize():
    for login, password, server in (
        (0, "password", "Broker-Demo"),
        (12345, "", "Broker-Demo"),
    ):
        mt5 = FakeMT5(trade_mode=0)
        service = MT5ExecutionService(mt5)
        result = service.connect(login, password, server)
        assert result["connected"] is False
        assert mt5.initialize_calls == []


def test_market_order_runs_broker_margin_check_before_order_send():
    mt5 = FakeMT5(trade_mode=0)
    service = MT5ExecutionService(mt5)
    service.adopt_existing_connection()

    service.place_market_order(
        "EURUSD", "bullish", 0.05,
        stop_loss=1.0990, take_profit=1.1020,
        max_risk_amount=50.0,
    )

    assert len(mt5.order_checks) == 1
    assert len(mt5.sent) == 1
    assert mt5.order_checks[0] == mt5.sent[0]


def test_market_order_blocks_when_broker_margin_check_fails():
    for check_result in (
        None,
        SimpleNamespace(retcode=10019, margin_free=0.0, comment="No money"),
        SimpleNamespace(retcode=0, margin_free=-1.0, comment="Invalid free margin"),
        SimpleNamespace(retcode=0, margin_free=float("nan"), comment="Invalid free margin"),
    ):
        mt5 = FakeMT5(trade_mode=0)
        mt5.check_result = check_result
        service = MT5ExecutionService(mt5)
        service.adopt_existing_connection()

        with pytest.raises(RuntimeError, match="pre-check|free margin"):
            service.place_market_order(
                "EURUSD", "bullish", 0.05,
                stop_loss=1.0990, take_profit=1.1020,
                max_risk_amount=50.0,
            )
        assert mt5.sent == []


def test_market_order_blocks_when_broker_margin_check_is_unavailable():
    mt5 = FakeMT5(trade_mode=0)
    mt5.order_check = None
    service = MT5ExecutionService(mt5)
    service.adopt_existing_connection()

    with pytest.raises(RuntimeError, match="order_check is unavailable"):
        service.place_market_order(
            "EURUSD", "bullish", 0.05,
            stop_loss=1.0990, take_profit=1.1020,
            max_risk_amount=50.0,
        )
    assert mt5.sent == []


def test_close_position_requires_successful_broker_precheck():
    mt5 = FakeMT5(trade_mode=0)
    mt5.check_result = None
    service = MT5ExecutionService(mt5)
    service.adopt_existing_connection()

    with pytest.raises(RuntimeError, match="pre-check returned no result"):
        service.close_position(12345)

    assert mt5.sent == []
    assert len(mt5.order_checks) == 1


def test_close_position_sends_only_after_broker_precheck():
    mt5 = FakeMT5(trade_mode=0)
    service = MT5ExecutionService(mt5)
    service.adopt_existing_connection()

    result = service.close_position(12345)

    assert result["closed"] is True
    assert len(mt5.order_checks) == 1
    assert len(mt5.sent) == 1


def test_market_execution_uses_broker_supported_ioc_filling_policy():
    mt5 = FakeMT5(trade_mode=0)
    mt5.info.trade_exemode = mt5.SYMBOL_TRADE_EXECUTION_MARKET
    mt5.info.filling_mode = mt5.SYMBOL_FILLING_IOC
    service = MT5ExecutionService(mt5)
    service.adopt_existing_connection()

    service.place_market_order(
        "EURUSD", "bullish", 0.05,
        stop_loss=1.0990, take_profit=1.1020,
        max_risk_amount=50.0,
    )

    assert mt5.sent[0]["type_filling"] == mt5.ORDER_FILLING_IOC


def test_market_execution_prefers_fok_when_broker_supports_both():
    mt5 = FakeMT5(trade_mode=0)
    mt5.info.trade_exemode = mt5.SYMBOL_TRADE_EXECUTION_MARKET
    mt5.info.filling_mode = mt5.SYMBOL_FILLING_FOK | mt5.SYMBOL_FILLING_IOC
    service = MT5ExecutionService(mt5)
    service.adopt_existing_connection()

    service.place_market_order(
        "EURUSD", "bullish", 0.05,
        stop_loss=1.0990, take_profit=1.1020,
        max_risk_amount=50.0,
    )

    assert mt5.sent[0]["type_filling"] == mt5.ORDER_FILLING_FOK


def test_market_execution_without_supported_filling_policy_blocks_order():
    mt5 = FakeMT5(trade_mode=0)
    mt5.info.trade_exemode = mt5.SYMBOL_TRADE_EXECUTION_MARKET
    mt5.info.filling_mode = 0
    service = MT5ExecutionService(mt5)
    service.adopt_existing_connection()

    with pytest.raises(RuntimeError, match="no supported FOK/IOC"):
        service.place_market_order(
            "EURUSD", "bullish", 0.05,
            stop_loss=1.0990, take_profit=1.1020,
            max_risk_amount=50.0,
        )

    assert mt5.order_checks == []
    assert mt5.sent == []


def test_close_position_does_not_treat_unavailable_positions_as_missing_ticket():
    mt5 = FakeMT5(trade_mode=0)
    mt5.position_result = None
    mt5.positions_get = lambda ticket=None: None
    service = MT5ExecutionService(mt5)
    service.adopt_existing_connection()

    with pytest.raises(RuntimeError, match="position lookup failed"):
        service.close_position(12345)

    assert mt5.sent == []


def test_partial_close_reports_executed_and_remaining_volume():
    mt5 = FakeMT5(trade_mode=0)
    mt5.order_send = lambda request: SimpleNamespace(
        retcode=mt5.TRADE_RETCODE_DONE_PARTIAL,
        order=98765,
        deal=98766,
        price=request["price"],
        volume=0.02,
    )
    service = MT5ExecutionService(mt5)
    service.adopt_existing_connection()

    result = service.close_position(12345)

    assert result["closed"] is False
    assert result["partially_closed"] is True
    assert result["volume"] == pytest.approx(0.02)
    assert result["remaining_volume"] == pytest.approx(0.03)


def test_partial_close_without_reported_volume_requires_manual_inspection():
    mt5 = FakeMT5(trade_mode=0)
    def partial_close(request):
        mt5.sent.append(request)
        return SimpleNamespace(
            retcode=mt5.TRADE_RETCODE_DONE_PARTIAL,
            order=98765,
            deal=98766,
            price=request["price"],
        )
    mt5.order_send = partial_close
    service = MT5ExecutionService(mt5)
    service.adopt_existing_connection()

    with pytest.raises(RuntimeError, match="partial close without the executed volume"):
        service.close_position(12345)

    assert len(mt5.sent) == 1


def test_close_position_can_reduce_exposure_when_free_margin_is_negative():
    mt5 = FakeMT5(trade_mode=0)
    mt5.check_result = SimpleNamespace(retcode=0, margin_free=-25.0, comment="Close allowed")
    service = MT5ExecutionService(mt5)
    service.adopt_existing_connection()

    result = service.close_position(12345)

    assert result["closed"] is True
    assert len(mt5.sent) == 1


def test_execution_connect_rejects_mismatched_account_identity():
    mt5 = FakeMT5(trade_mode=0)
    mt5.account_info = lambda: SimpleNamespace(
        trade_mode=0,
        login=99999999,
        server="Different-Broker-Server",
    )
    service = MT5ExecutionService(mt5)

    result = service.connect(12345, "password", "Exness-MT5Trial8")

    assert result["connected"] is False
    assert "identity does not match" in result["message"]
    assert mt5.sent == []


def test_execution_connect_uses_terminal_selected_server_when_server_is_blank():
    mt5 = FakeMT5(trade_mode=0)
    service = MT5ExecutionService(mt5)

    result = service.connect(12345, "demo-password", "   ")

    assert result["connected"] is True
    assert "server" not in mt5.initialize_calls[0]
    assert result["account_mode"] == "DEMO"


def test_execution_connect_rejects_control_characters_in_server_name():
    mt5 = FakeMT5(trade_mode=0)
    service = MT5ExecutionService(mt5)

    result = service.connect(12345, "demo-password", "Broker-Demo\nInjected")

    assert result["connected"] is False
    assert "server name is invalid" in result["message"]
    assert mt5.initialize_calls == []
