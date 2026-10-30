import pytest

from risk.models import InstrumentRisk
from risk.position_sizing import calculate_position_size


def make_instrument():
    return InstrumentRisk(
        symbol="EURUSD",
        point=0.0001,
        tick_size=0.0001,
        tick_value=1.0,
        contract_size=100000.0,
        volume_min=0.01,
        volume_max=100.0,
        volume_step=0.01,
    )


def test_rejects_position_below_minimum_to_preserve_risk():
    with pytest.raises(ValueError, match="below the broker minimum"):
        calculate_position_size(
            instrument=make_instrument(),
            direction="bullish",
            entry=1.1000,
            stop_loss=1.0990,
            risk_amount=0.05,
        )


def test_volume_rounds_down_and_stays_within_risk_budget():
    result = calculate_position_size(
        instrument=make_instrument(),
        direction="bullish",
        entry=1.1000,
        stop_loss=1.0990,
        risk_amount=1.09,
    )

    assert result.volume == pytest.approx(0.10)
    assert result.estimated_loss <= 1.09


def test_rejects_minimum_lot_for_bearish_trade_when_budget_is_too_small():
    with pytest.raises(ValueError, match="below the broker minimum"):
        calculate_position_size(
            instrument=make_instrument(),
            direction="bearish",
            entry=1.1000,
            stop_loss=1.1010,
            risk_amount=0.05,
        )
