from datetime import timezone

from dashboard.mt5_live import MT5LiveService


class FakeMT5:
    ACCOUNT_TRADE_MODE_DEMO = 0
    ACCOUNT_TRADE_MODE_CONTEST = 1
    ACCOUNT_TRADE_MODE_REAL = 2
    DEAL_ENTRY_IN = 0
    DEAL_ENTRY_INOUT = 2
    DEAL_TYPE_BUY = 0
    DEAL_TYPE_SELL = 1

    def __init__(self, trade_mode=0, deals=()):
        self.trade_mode = trade_mode
        self.deals = deals
        self.login_calls = []
        self.requested_server = ""
        self.initialize_calls = []

    def initialize(self, **kwargs):
        self.initialize_calls.append(kwargs)
        return True

    def login(self, *args, **kwargs):
        self.login_calls.append((args, kwargs))
        self.requested_server = str(kwargs.get("server", ""))
        return True

    def account_info(self):
        return type("Account", (), {
            "trade_mode": self.trade_mode,
            "login": 12345,
            "server": self.requested_server or "Broker-Demo",
            "balance": 10000.0,
            "equity": 10000.0,
            "margin_free": 10000.0,
            "profit": 0.0,
            "currency": "USD",
        })()

    def history_deals_get(self, start, end):
        assert start.hour == 0 and start.minute == 0
        assert start.tzinfo == timezone.utc
        assert end.tzinfo == timezone.utc
        return self.deals

    def positions_get(self):
        return ()

    def last_error(self):
        return (0, "ok")

    def shutdown(self):
        pass


def test_connection_reports_actual_mt5_demo_mode():
    service = MT5LiveService(mt5_module=FakeMT5(trade_mode=0))
    result = service.connect(login=12345, password="x", server="Broker-Demo", requested_mode="DEMO")
    assert result.connected is True
    assert result.account_type == "DEMO"


def test_real_account_is_not_mislabeled_as_demo():
    service = MT5LiveService(mt5_module=FakeMT5(trade_mode=2))
    result = service.connect(login=12345, password="x", server="Broker-Real", requested_mode="DEMO")
    assert result.connected is False
    assert "does not match" in result.message


def test_contest_account_is_not_mislabeled_as_real():
    service = MT5LiveService(mt5_module=FakeMT5(trade_mode=1))
    result = service.connect(login=12345, password="x", server="Broker-Contest", requested_mode="REAL")
    assert result.connected is False
    assert "CONTEST" in result.message


def test_today_entry_count_counts_only_entry_and_reversal_deals():
    deals = [
        type("Deal", (), {"entry": 0, "type": 0})(),
        type("Deal", (), {"entry": 1, "type": 1})(),
        type("Deal", (), {"entry": 2, "type": 1})(),
        type("Deal", (), {"entry": 0, "type": 2})(),
    ]
    service = MT5LiveService(mt5_module=FakeMT5(deals=deals))
    service.connected = True
    assert service.today_entry_count() == 2


def test_today_loss_percent_calculates_realized_loss():
    deals = [
        type("Deal", (), {
            "type": 0, "profit": -100.0, "commission": -2.0, "swap": 0.0, "fee": 0.0
        })()
    ]
    service = MT5LiveService(mt5_module=FakeMT5(deals=deals))
    service.connected = True
    loss = service.today_loss_percent()
    assert 0.9 < loss < 1.1



def test_connection_reuses_already_logged_in_terminal_without_credentials():
    fake = FakeMT5(trade_mode=0)
    service = MT5LiveService(mt5_module=fake)

    result = service.connect(requested_mode="DEMO")

    assert result.connected is True
    assert result.account_type == "DEMO"
    assert result.login == 12345
    assert result.server == "Broker-Demo"


def test_existing_real_terminal_account_is_rejected_in_demo_mode():
    service = MT5LiveService(mt5_module=FakeMT5(trade_mode=2))

    result = service.connect(requested_mode="DEMO")

    assert result.connected is False
    assert "does not match" in result.message

def test_open_trade_count_fails_closed_when_mt5_returns_none():
    fake = FakeMT5()
    fake.positions_get = lambda: None
    service = MT5LiveService(mt5_module=fake)
    service.connected = True

    try:
        service.open_trade_count()
    except RuntimeError as exc:
        assert "positions lookup failed" in str(exc)
    else:
        raise AssertionError("Unavailable MT5 positions must not be treated as zero open trades.")


def test_open_trade_count_fails_closed_when_mt5_positions_lookup_raises():
    fake = FakeMT5()
    def fail_positions():
        raise OSError("terminal unavailable")
    fake.positions_get = fail_positions
    service = MT5LiveService(mt5_module=fake)
    service.connected = True

    try:
        service.open_trade_count()
    except RuntimeError as exc:
        assert "positions lookup failed" in str(exc)
    else:
        raise AssertionError("MT5 positions errors must block the open-trade check.")


def test_open_trade_count_requires_a_connected_mt5_session():
    service = MT5LiveService(mt5_module=FakeMT5())

    try:
        service.open_trade_count()
    except RuntimeError as exc:
        assert "must be connected" in str(exc)
    else:
        raise AssertionError("A disconnected MT5 service must not report zero open trades.")


def test_today_loss_fails_closed_after_non_trading_balance_adjustment():
    trade = type("Deal", (), {
        "type": 0, "profit": -100.0, "commission": -2.0, "swap": 0.0, "fee": 0.0
    })()
    deposit = type("Deal", (), {
        "type": 2, "profit": 5000.0, "commission": 0.0, "swap": 0.0, "fee": 0.0
    })()
    service = MT5LiveService(mt5_module=FakeMT5(deals=[trade, deposit]))
    service.connected = True

    try:
        service.today_loss_percent()
    except RuntimeError as exc:
        assert "balance adjustment" in str(exc)
    else:
        raise AssertionError("Daily loss must be unverifiable after a same-day balance adjustment.")


def test_today_loss_fails_closed_on_non_finite_trading_pnl():
    bad_deal = type("Deal", (), {
        "type": 0, "profit": float("nan"), "commission": 0.0, "swap": 0.0, "fee": 0.0
    })()
    service = MT5LiveService(mt5_module=FakeMT5(deals=[bad_deal]))
    service.connected = True

    try:
        service.today_loss_percent()
    except RuntimeError as exc:
        assert "non-finite" in str(exc)
    else:
        raise AssertionError("Non-finite P/L must block daily risk verification.")

def test_open_trade_summary_fails_closed_when_disconnected():
    service = MT5LiveService(mt5_module=FakeMT5())

    try:
        service.open_trade_summary()
    except RuntimeError as exc:
        assert "must be connected" in str(exc)
    else:
        raise AssertionError("Disconnected MT5 must not be summarized as zero open positions.")


def test_open_trade_summary_reports_verified_empty_positions():
    service = MT5LiveService(mt5_module=FakeMT5())
    service.connected = True

    assert service.open_trade_summary() == {"count": 0, "volume": 0, "profit": 0}



def test_today_entry_count_uses_utc_day_boundaries():
    fake = FakeMT5(deals=[])
    service = MT5LiveService(mt5_module=fake)
    service.connected = True

    assert service.today_entry_count() == 0



def test_today_entry_count_fails_closed_on_malformed_deal():
    malformed = type("Deal", (), {"type": 0})()
    service = MT5LiveService(mt5_module=FakeMT5(deals=[malformed]))
    service.connected = True

    try:
        service.today_entry_count()
    except RuntimeError as exc:
        assert "malformed deal history" in str(exc)
    else:
        raise AssertionError("Malformed deal history must not be interpreted as zero trades.")


def test_today_loss_fails_closed_on_malformed_deal_type():
    malformed = type("Deal", (), {
        "profit": 0.0, "commission": 0.0, "swap": 0.0, "fee": 0.0
    })()
    service = MT5LiveService(mt5_module=FakeMT5(deals=[malformed]))
    service.connected = True

    try:
        service.today_loss_percent()
    except RuntimeError as exc:
        assert "malformed deal history" in str(exc)
    else:
        raise AssertionError("Malformed deal history must block daily risk verification.")

def test_connection_rejects_unsupported_requested_account_mode():
    fake = FakeMT5(trade_mode=0)
    service = MT5LiveService(mt5_module=fake)

    result = service.connect(requested_mode="CONTEST")

    assert result.connected is False
    assert "Select DEMO or REAL" in result.message
    assert service.connected is False


def test_failed_reconnect_clears_stale_account_state():
    class FailedInitializeMT5(FakeMT5):
        def initialize(self, **kwargs):
            return False

    service = MT5LiveService(mt5_module=FailedInitializeMT5())
    service.connected = True
    service.account = object()

    result = service.connect(requested_mode="DEMO")

    assert result.connected is False
    assert service.connected is False
    assert service.account is None


def test_login_passes_exact_server_name_for_multiple_mt5_brokers():
    server_names = (
        ("Exness-MT5Trial8", 0, "DEMO"),
        ("Exness-MT5Real10", 2, "REAL"),
        ("ICMarketsSC-Demo", 0, "DEMO"),
        ("Pepperstone-Demo", 0, "DEMO"),
        ("FTMO-Demo", 0, "DEMO"),
    )
    for server, trade_mode, requested_mode in server_names:
        fake = FakeMT5(trade_mode=trade_mode)
        service = MT5LiveService(mt5_module=fake)
        result = service.connect(
            login=12345678,
            password="test-password",
            server=f"  {server}  ",
            requested_mode=requested_mode,
        )
        assert result.connected is True
        assert result.account_type == requested_mode
        assert result.server == server
        assert fake.login_calls[0][1]["server"] == server


def test_credentials_login_rejects_missing_server_before_initializing_terminal():
    fake = FakeMT5(trade_mode=0)
    service = MT5LiveService(mt5_module=fake)

    result = service.connect(
        login=12345678,
        password="test-password",
        server="   ",
        requested_mode="DEMO",
    )

    assert result.connected is False
    assert "exact MT5 server" in result.message
    assert fake.login_calls == []


def test_credentials_login_rejects_invalid_account_number():
    fake = FakeMT5(trade_mode=0)
    service = MT5LiveService(mt5_module=fake)

    result = service.connect(
        login=0,
        password="test-password",
        server="Exness-MT5Trial8",
        requested_mode="DEMO",
    )

    assert result.connected is False
    assert "positive account number" in result.message
    assert fake.login_calls == []


def test_connection_uses_selected_broker_terminal_executable_path():
    fake = FakeMT5(trade_mode=0)
    service = MT5LiveService(mt5_module=fake)
    terminal_path = r"C:\Program Files\Exness MT5\terminal64.exe"

    result = service.connect(
        login=12345678,
        password="test-password",
        server="Exness-MT5Trial8",
        requested_mode="DEMO",
        terminal_path=terminal_path,
    )

    assert result.connected is True
    assert fake.initialize_calls[0]["path"] == terminal_path
    assert service.path == terminal_path


def test_connection_rejects_invalid_terminal_path_before_initialization():
    fake = FakeMT5(trade_mode=0)
    service = MT5LiveService(mt5_module=fake)

    result = service.connect(
        requested_mode="DEMO",
        terminal_path="   ",
    )

    assert result.connected is False
    assert "terminal path is invalid" in result.message
    assert fake.initialize_calls == []
