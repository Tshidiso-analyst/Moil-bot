from types import SimpleNamespace

from dashboard.app import MoilBotHandler, parse_mt5_credentials


def _request(remote="127.0.0.1", origin="http://127.0.0.1:8501", host="127.0.0.1:8501"):
    return SimpleNamespace(
        client_address=(remote, 54321),
        headers={"Origin": origin, "Host": host},
    )


def test_demo_action_accepts_same_origin_loopback_request():
    request = _request()
    assert MoilBotHandler.is_local_dashboard_request(request) is True


def test_demo_action_rejects_non_loopback_client():
    request = _request(remote="192.0.2.10")
    assert MoilBotHandler.is_local_dashboard_request(request) is False


def test_demo_action_rejects_cross_origin_post():
    request = _request(origin="https://attacker.example")
    assert MoilBotHandler.is_local_dashboard_request(request) is False


def test_demo_action_rejects_wrong_host_or_port():
    request = _request(host="127.0.0.1:9999")
    assert MoilBotHandler.is_local_dashboard_request(request) is False


def test_demo_action_rejects_missing_origin_header():
    request = _request()
    request.headers = {"Host": "127.0.0.1:8501"}
    assert MoilBotHandler.is_local_dashboard_request(request) is False


def test_mt5_credentials_allow_serverless_login_for_preconfigured_terminal():
    assert parse_mt5_credentials({
        "login": "12345678",
        "password": "trading-password",
        "server": "",
    }) == (12345678, "trading-password", "")


def test_mt5_credentials_reject_password_without_account_login():
    try:
        parse_mt5_credentials({"login": "", "password": "secret", "server": ""})
    except ValueError as exc:
        assert "account number and trading password" in str(exc)
    else:
        raise AssertionError("Incomplete broker credentials must be rejected.")


def test_mt5_credentials_accept_exact_server_for_any_broker():
    assert parse_mt5_credentials({
        "login": "12345678",
        "password": "trading-password",
        "server": "BrokerName-Live42",
    }) == (12345678, "trading-password", "BrokerName-Live42")


def test_mt5_broker_directory_launches_selected_terminal_without_shell(tmp_path, monkeypatch):
    import dashboard.app as dashboard_app

    terminal = tmp_path / "Broker MT5" / "terminal64.exe"
    terminal.parent.mkdir()
    terminal.write_text("test executable placeholder")
    calls = []
    monkeypatch.setattr(dashboard_app.subprocess, "Popen", lambda args, **kwargs: calls.append((args, kwargs)))

    dashboard_app.launch_mt5_broker_directory(str(terminal))

    assert calls == [([str(terminal)], {"shell": False, "close_fds": True})]


def test_mt5_broker_directory_rejects_non_terminal_executable(tmp_path):
    from dashboard.app import launch_mt5_broker_directory

    executable = tmp_path / "powershell.exe"
    executable.write_text("placeholder")
    try:
        launch_mt5_broker_directory(str(executable))
    except ValueError as exc:
        assert "terminal64.exe" in str(exc)
    else:
        raise AssertionError("Broker search must only launch a MetaTrader terminal executable.")


def test_mt5_broker_directory_rejects_missing_terminal(tmp_path):
    from dashboard.app import launch_mt5_broker_directory

    missing = tmp_path / "terminal64.exe"
    try:
        launch_mt5_broker_directory(str(missing))
    except FileNotFoundError as exc:
        assert "terminal was not found" in str(exc)
    else:
        raise AssertionError("A missing MT5 terminal must produce a clear error.")


def test_connection_page_exposes_native_broker_server_search():
    from dashboard.app import connection_form

    page = connection_form()
    assert 'action="/broker_search"' in page
    assert "File &gt; Open an Account" in page
    assert "Exness" in page
