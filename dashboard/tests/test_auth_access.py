from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

from dashboard.app import (
    MoilBotHandler,
    clear_login_failures,
    login_rate_limited,
    parse_mt5_credentials,
)


class Headers(dict):
    def get(self, key, default=None):
        return super().get(key, default)


def test_same_origin_post_accepts_matching_local_origin():
    handler = SimpleNamespace(
        headers=Headers({
            "Origin": "http://127.0.0.1:8501",
            "Host": "127.0.0.1:8501",
        })
    )

    assert MoilBotHandler.same_origin_post(handler) is True


def test_same_origin_post_rejects_foreign_origin():
    handler = SimpleNamespace(
        headers=Headers({
            "Origin": "https://attacker.example",
            "Host": "127.0.0.1:8501",
        })
    )

    assert MoilBotHandler.same_origin_post(handler) is False


def test_same_origin_post_rejects_missing_origin():
    handler = SimpleNamespace(headers=Headers({"Host": "127.0.0.1:8501"}))

    assert MoilBotHandler.same_origin_post(handler) is False


def test_login_throttle_blocks_after_five_failures_and_can_reset():
    client_ip = "192.0.2.10"
    clear_login_failures(client_ip)

    assert login_rate_limited(client_ip) is False
    for _ in range(4):
        assert login_rate_limited(client_ip) is False

    assert login_rate_limited(client_ip) is True
    clear_login_failures(client_ip)
    assert login_rate_limited(client_ip) is False



def test_login_throttle_is_atomic_under_concurrent_attempts():
    client_ip = "192.0.2.11"
    clear_login_failures(client_ip)

    with ThreadPoolExecutor(max_workers=12) as pool:
        allowed = list(pool.map(lambda _index: login_rate_limited(client_ip), range(12)))

    assert allowed.count(False) == 5
    assert allowed.count(True) == 7
    clear_login_failures(client_ip)


def test_mt5_credentials_require_all_three_fields_or_none():
    assert parse_mt5_credentials({}) == (None, "", "")
    assert parse_mt5_credentials({
        "login": "12345678",
        "password": "secret",
        "server": " Exness-MT5Trial8 ",
    }) == (12345678, "secret", "Exness-MT5Trial8")

    for partial in (
        {"login": "12345678"},
        {"password": "secret"},
        {"server": "Exness-MT5Trial8"},
        {"login": "12345678", "password": "secret"},
        {"login": "12345678", "server": "Exness-MT5Trial8"},
        {"password": "secret", "server": "Exness-MT5Trial8"},
    ):
        try:
            parse_mt5_credentials(partial)
        except ValueError as exc:
            assert "provide the account number" in str(exc)
        else:
            raise AssertionError("Partial MT5 credentials must never fall back to another signed-in account.")


def test_mt5_credentials_reject_non_positive_account_numbers():
    for login in ("0", "-1", "not-a-number"):
        try:
            parse_mt5_credentials({
                "login": login,
                "password": "secret",
                "server": "Exness-MT5Trial8",
            })
        except ValueError as exc:
            assert "positive account number" in str(exc)
        else:
            raise AssertionError("Invalid MT5 account numbers must be rejected.")


def test_mt5_connection_requires_loopback_client_and_loopback_origin():
    local = SimpleNamespace(
        client_address=("127.0.0.1", 54321),
        headers=Headers({
            "Origin": "http://127.0.0.1:8501",
            "Host": "127.0.0.1:8501",
        }),
    )
    remote = SimpleNamespace(
        client_address=("192.168.1.20", 54321),
        headers=Headers({
            "Origin": "http://127.0.0.1:8501",
            "Host": "127.0.0.1:8501",
        }),
    )

    assert MoilBotHandler.is_local_dashboard_request(local) is True
    assert MoilBotHandler.is_local_dashboard_request(remote) is False
