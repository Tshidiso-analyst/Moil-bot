from types import SimpleNamespace

from risk.mt5_position_sizer import calculate_mt5_position_size


def info(**overrides):
    values = dict(trade_tick_size=0.0001, trade_tick_value_loss=1.0,
                  volume_min=0.01, volume_max=100.0, volume_step=0.01)
    values.update(overrides)
    return SimpleNamespace(**values)


def test_sizes_down_to_volume_step_without_exceeding_one_percent():
    result = calculate_mt5_position_size(
        info(), equity=10_000, risk_percent=1.0,
        entry_price=1.1000, stop_loss=1.0900,
    )
    assert result.accepted
    assert result.volume == 10.0
    assert result.estimated_loss_at_stop == 100.0
    assert result.risk_percent <= 1.0


def test_rejects_risk_above_cap():
    result = calculate_mt5_position_size(
        info(), equity=10_000, risk_percent=1.5,
        entry_price=1.1, stop_loss=1.09,
    )
    assert not result.accepted
    assert result.volume == 0


def test_rejects_when_minimum_volume_exceeds_risk_budget():
    result = calculate_mt5_position_size(
        info(volume_min=0.1), equity=100, risk_percent=0.1,
        entry_price=1.1, stop_loss=1.09,
    )
    assert not result.accepted


def test_rejects_missing_broker_metadata():
    result = calculate_mt5_position_size(
        None, equity=10_000, risk_percent=1.0,
        entry_price=1.1, stop_loss=1.09,
    )
    assert not result.accepted
