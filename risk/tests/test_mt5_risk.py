from types import SimpleNamespace

import pytest

from risk.mt5_risk import MT5RiskSpecification, calculate_mt5_position_size


class FakeMT5:
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1

    def __init__(self):
        self.info = SimpleNamespace(
            point=0.01, trade_tick_size=0.01, trade_tick_value=1.0,
            trade_tick_value_profit=1.0, trade_contract_size=100.0,
            volume_min=0.01, volume_max=100.0, volume_step=0.01,
        )
        self.selected = []

    def symbol_select(self, symbol, enabled):
        self.selected.append((symbol, enabled))
        return True

    def symbol_info(self, symbol):
        return self.info

    def order_calc_profit(self, order_type, symbol, volume, entry, stop):
        return (stop - entry) * 100 * volume if order_type == 0 else (entry - stop) * 100 * volume

    def last_error(self):
        return (0, "ok")


def test_mt5_risk_spec_uses_broker_alias_but_canonicalizes_model_symbol():
    fake = FakeMT5()
    result = MT5RiskSpecification(fake).get("XAUUSD.a")
    assert result.symbol == "XAUUSD"
    assert result.contract_size == 100.0
    assert fake.selected == [("XAUUSD.a", True)]


def test_mt5_risk_spec_rejects_non_gold_symbol():
    with pytest.raises(ValueError, match="XAUUSD only"):
        MT5RiskSpecification(FakeMT5()).get("EURUSD")


def test_broker_position_sizing_uses_order_calc_profit_and_caps_at_002():
    fake = FakeMT5()
    result = calculate_mt5_position_size(
        fake, symbol="XAUUSD.a", direction="bullish",
        entry=2500.0, stop_loss=2490.0, risk_amount=100.0,
    )
    assert result.symbol == "XAUUSD"
    assert result.volume == pytest.approx(0.02)
    assert result.estimated_loss == pytest.approx(20.0)
    assert result.estimated_loss <= result.risk_amount


def test_broker_position_sizing_rejects_broker_minimum_above_lot_cap():
    fake = FakeMT5()
    fake.info.volume_min = 0.10
    with pytest.raises(ValueError, match="volume limits"):
        calculate_mt5_position_size(
            fake, symbol="XAUUSD", direction="bullish",
            entry=2500.0, stop_loss=2490.0, risk_amount=100.0,
        )


def test_broker_position_sizing_fails_closed_when_profit_calculation_fails():
    fake = FakeMT5()
    fake.order_calc_profit = lambda *args: None
    with pytest.raises(RuntimeError, match="could not calculate"):
        calculate_mt5_position_size(
            fake, symbol="XAUUSD", direction="bullish",
            entry=2500.0, stop_loss=2490.0, risk_amount=100.0,
        )


def test_broker_position_sizing_rejects_non_gold_symbol():
    with pytest.raises(ValueError, match="XAUUSD only"):
        calculate_mt5_position_size(
            FakeMT5(), symbol="GBPUSD", direction="bullish",
            entry=1.2, stop_loss=1.1, risk_amount=100.0,
        )



def test_broker_position_sizing_refuses_configuration_above_002_lots():
    with pytest.raises(ValueError, match="cannot exceed 0.02"):
        calculate_mt5_position_size(
            FakeMT5(), symbol="XAUUSD", direction="bullish",
            entry=2500.0, stop_loss=2490.0, risk_amount=100.0,
            max_volume=0.03,
        )

def test_broker_final_risk_must_not_exceed_budget_even_by_one_cent():
    fake = FakeMT5()
    original = fake.order_calc_profit
    def slightly_higher_final_loss(order_type, symbol, volume, entry, stop):
        value = original(order_type, symbol, volume, entry, stop)
        return -5.01 if volume == 0.01 else value
    fake.order_calc_profit = slightly_higher_final_loss
    with pytest.raises(ValueError, match="exceeds the configured risk budget"):
        calculate_mt5_position_size(
            fake, symbol="XAUUSDm", direction="bullish",
            entry=2500.0, stop_loss=2495.0, risk_amount=5.0,
        )


def test_r500_equity_rejects_minimum_lot_when_stop_risks_more_than_r5():
    fake = FakeMT5()
    with pytest.raises(ValueError, match="below broker minimum"):
        calculate_mt5_position_size(
            fake, symbol="XAUUSDm", direction="bullish",
            entry=2500.0, stop_loss=2490.0, risk_amount=5.0,
        )
