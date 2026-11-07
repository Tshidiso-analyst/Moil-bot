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

    def initialize(self, **kwargs):
        return True

    def login(self, *args, **kwargs):
        return True

    def account_info(self):
        return type("Account", (), {
            "trade_mode": self.trade_mode,
            "login": 12345,
            "server": "Broker-Demo",
            "balance": 10000.0,
            "equity": 10000.0,
            "margin_free": 10000.0,
            "profit": 0.0,
            "currency": "USD",
        })()

    def history_deals_get(self, start, end):
        assert start.hour == 0 and start.minute == 0
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
            "profit": -100.0, "commission": -2.0, "swap": 0.0, "fee": 0.0
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
