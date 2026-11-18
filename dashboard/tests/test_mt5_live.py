from types import SimpleNamespace

import pytest

from dashboard.mt5_live import MT5LiveService


class FakeMT5:
    def __init__(self, positions=()):
        self._positions = positions

    def positions_get(self):
        return self._positions

    def last_error(self):
        return (1, "history unavailable")


def test_positions_returns_actual_open_position_data():
    fake = FakeMT5([
        SimpleNamespace(
            ticket=7, symbol="XAUUSD.a", volume=0.02, profit=3.0,
            swap=-0.5, comment="Moil-bot", type=0,
            price_open=2500.0, price_current=2503.0, sl=2490.0, tp=2520.0,
        )
    ])
    service = MT5LiveService(fake)
    service.connected = True
    rows = service.positions()
    assert len(rows) == 1
    assert rows[0]["ticket"] == 7
    assert rows[0]["stop_loss"] == 2490.0
    assert service.open_trade_count() == 1


def test_connected_but_unavailable_positions_fail_instead_of_returning_zero():
    service = MT5LiveService(FakeMT5(None))
    service.connected = True
    with pytest.raises(RuntimeError, match="positions lookup failed"):
        service.open_trade_count()


def test_disconnected_positions_fail_instead_of_returning_zero():
    service = MT5LiveService(FakeMT5([]))
    with pytest.raises(RuntimeError, match="not connected"):
        service.open_trade_summary()


def test_verified_empty_positions_return_zero():
    service = MT5LiveService(FakeMT5([]))
    service.connected = True
    assert service.open_trade_count() == 0
    assert service.open_trade_summary()["count"] == 0
