from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

from dashboard.app import (
    MoilBotHandler,
    clear_login_failures,
    login_rate_limited,
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
