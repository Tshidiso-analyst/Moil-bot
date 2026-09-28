import pytest

from risk.account import calculate_account_risk
from risk.models import InstrumentRisk
from risk.position_sizing import calculate_position_size


def forex_instrument():
    return InstrumentRisk(
        symbol="EURUSD",
        point=0.00001,
        tick_size=0.00001,
        tick_value=1.0,
        contract_size=100000,
        volume_min=0.01,
        volume_max=100.0,
        volume_step=0.01,
    )


def index_instrument():
    return InstrumentRisk(
        symbol="US30",
        point=0.1,
        tick_size=0.1,
        tick_value=1.0,
        contract_size=1.0,
        volume_min=0.1,
        volume_max=100.0,
        volume_step=0.1,
    )


def stock_instrument():
    return InstrumentRisk(
        symbol="AAPL",
        point=0.01,
        tick_size=0.01,
        tick_value=0.01,
        contract_size=1.0,
        volume_min=1.0,
        volume_max=1000.0,
        volume_step=1.0,
    )


def commodity_instrument():
    return InstrumentRisk(
        symbol="XAUUSD",
        point=0.01,
        tick_size=0.01,
        tick_value=1.0,
        contract_size=100.0,
        volume_min=0.01,
        volume_max=100.0,
        volume_step=0.01,
    )


def crypto_instrument():
    return InstrumentRisk(
        symbol="BTCUSD",
        point=0.01,
        tick_size=0.01,
        tick_value=0.01,
        contract_size=1.0,
        volume_min=0.01,
        volume_max=100.0,
        volume_step=0.01,
    )


def test_account_risk():
    result = calculate_account_risk(
        balance=10000,
        risk_percent=1,
    )

    assert result.risk_amount == 100


def test_forex_position_size():
    result = calculate_position_size(
        instrument=forex_instrument(),
        direction="bullish",
        entry=1.10000,
        stop_loss=1.09500,
        risk_amount=100,
    )

    assert result.symbol == "EURUSD"
    assert result.volume > 0
    assert result.estimated_loss <= 100


def test_index_position_size():
    result = calculate_position_size(
        instrument=index_instrument(),
        direction="bearish",
        entry=45000,
        stop_loss=45100,
        risk_amount=100,
    )

    assert result.symbol == "US30"
    assert result.volume > 0
    assert result.estimated_loss <= 100


def test_stock_position_size():
    result = calculate_position_size(
        instrument=stock_instrument(),
        direction="bullish",
        entry=250,
        stop_loss=245,
        risk_amount=100,
    )

    assert result.symbol == "AAPL"
    assert result.volume > 0
    assert result.estimated_loss <= 100


def test_commodity_position_size():
    result = calculate_position_size(
        instrument=commodity_instrument(),
        direction="bullish",
        entry=2500,
        stop_loss=2480,
        risk_amount=100,
    )

    assert result.symbol == "XAUUSD"
    assert result.volume > 0
    assert result.estimated_loss <= 100


def test_crypto_position_size():
    result = calculate_position_size(
        instrument=crypto_instrument(),
        direction="bearish",
        entry=100000,
        stop_loss=102000,
        risk_amount=100,
    )

    assert result.symbol == "BTCUSD"
    assert result.volume > 0
    assert result.estimated_loss <= 100


def test_invalid_direction():
    with pytest.raises(ValueError):
        calculate_position_size(
            instrument=forex_instrument(),
            direction="sideways",
            entry=1.1000,
            stop_loss=1.0950,
            risk_amount=100,
        )


def test_invalid_bullish_stop():
    with pytest.raises(ValueError):
        calculate_position_size(
            instrument=forex_instrument(),
            direction="bullish",
            entry=1.1000,
            stop_loss=1.1050,
            risk_amount=100,
        )


def test_invalid_bearish_stop():
    with pytest.raises(ValueError):
        calculate_position_size(
            instrument=forex_instrument(),
            direction="bearish",
            entry=1.1000,
            stop_loss=1.0950,
            risk_amount=100,
        )


def test_invalid_account_balance():
    with pytest.raises(ValueError):
        calculate_account_risk(
            balance=0,
            risk_percent=1,
        )


def test_invalid_risk_percentage():
    with pytest.raises(ValueError):
        calculate_account_risk(
            balance=10000,
            risk_percent=101,
        )


def default_limits():
    from risk.models import RiskLimits

    return RiskLimits(
        max_risk_per_trade_percent=1.0,
        max_open_trades=3,
        max_total_exposure_percent=3.0,
        max_daily_loss_percent=5.0,
    )


def test_risk_limits_allow_valid_trade():
    from risk.limits import can_open_trade

    assert can_open_trade(
        limits=default_limits(),
        current_open_trades=1,
        current_exposure_percent=1.0,
        proposed_risk_percent=1.0,
        daily_loss_percent=1.0,
    )


def test_risk_limits_reject_excessive_trade_risk():
    from risk.limits import can_open_trade

    assert not can_open_trade(
        limits=default_limits(),
        current_open_trades=1,
        current_exposure_percent=1.0,
        proposed_risk_percent=2.0,
        daily_loss_percent=1.0,
    )


def test_risk_limits_reject_max_open_trades():
    from risk.limits import can_open_trade

    assert not can_open_trade(
        limits=default_limits(),
        current_open_trades=3,
        current_exposure_percent=1.0,
        proposed_risk_percent=1.0,
        daily_loss_percent=1.0,
    )


def test_risk_limits_reject_excessive_exposure():
    from risk.limits import can_open_trade

    assert not can_open_trade(
        limits=default_limits(),
        current_open_trades=1,
        current_exposure_percent=2.5,
        proposed_risk_percent=1.0,
        daily_loss_percent=1.0,
    )


def test_risk_limits_reject_daily_loss_limit():
    from risk.limits import can_open_trade

    assert not can_open_trade(
        limits=default_limits(),
        current_open_trades=1,
        current_exposure_percent=1.0,
        proposed_risk_percent=1.0,
        daily_loss_percent=5.0,
    )


def test_invalid_risk_limits():
    from risk.limits import validate_risk_limits
    from risk.models import RiskLimits

    with pytest.raises(ValueError):
        validate_risk_limits(
            RiskLimits(
                max_risk_per_trade_percent=0,
                max_open_trades=3,
                max_total_exposure_percent=3,
                max_daily_loss_percent=5,
            )
        )


def test_bullish_stop_loss():
    from risk.stops import calculate_stop_loss

    stop = calculate_stop_loss(
        entry=100,
        direction="bullish",
        distance=5,
    )

    assert stop == 95


def test_bearish_stop_loss():
    from risk.stops import calculate_stop_loss

    stop = calculate_stop_loss(
        entry=100,
        direction="bearish",
        distance=5,
    )

    assert stop == 105


def test_bullish_take_profit():
    from risk.stops import calculate_take_profit

    target = calculate_take_profit(
        entry=100,
        stop_loss=95,
        direction="bullish",
        reward_multiple=2,
    )

    assert target == 110


def test_bearish_take_profit():
    from risk.stops import calculate_take_profit

    target = calculate_take_profit(
        entry=100,
        stop_loss=105,
        direction="bearish",
        reward_multiple=2,
    )

    assert target == 90


def test_invalid_stop_direction():
    from risk.stops import calculate_stop_loss

    with pytest.raises(ValueError):
        calculate_stop_loss(
            entry=100,
            direction="sideways",
            distance=5,
        )


def test_invalid_reward_multiple():
    from risk.stops import calculate_take_profit

    with pytest.raises(ValueError):
        calculate_take_profit(
            entry=100,
            stop_loss=95,
            direction="bullish",
            reward_multiple=0,
        )
