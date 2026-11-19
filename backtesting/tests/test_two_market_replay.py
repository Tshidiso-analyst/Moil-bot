import pandas as pd
import pytest

from backtesting.two_market_replay import Instrument, replay


def candles(symbol, values):
    return pd.DataFrame([
        dict(timestamp=f"2026-01-0{i+1}T00:00:00Z", open=v[0], high=v[1], low=v[2], close=v[3])
        for i, v in enumerate(values)
    ])


def instrument(symbol, conversion=10.0, min_lot=0.01):
    return Instrument(symbol=symbol, spread=0, slippage=0,
                      zar_per_price_unit_per_lot=conversion,
                      min_lot=min_lot, lot_step=0.01, max_lot=1.0)


def one_signal(symbol, history):
    if len(history) == 1:
        return dict(side="buy", stop=99, target=102)
    return None


def test_open_and_close_on_historical_bars_without_mt5():
    data = candles("EURUSD", [(100, 100.1, 99.9, 100), (100, 102.5, 99.5, 102)])
    result = replay({"EURUSD": data}, {"EURUSD": instrument("EURUSD")}, one_signal)
    assert [e["action"] for e in result["events"]] == ["SIGNAL", "OPEN", "CLOSE"]
    assert result["closed_trades"][0]["reason"] == "TARGET"
    assert result["ending_balance_zar"] > 500


def test_ambiguous_bar_stops_first():
    data = candles("EURUSD", [(100, 100.1, 99.9, 100), (100, 103, 98, 100)])
    result = replay({"EURUSD": data}, {"EURUSD": instrument("EURUSD")}, one_signal)
    assert result["closed_trades"][0]["reason"] == "STOP_AMBIGUOUS"
    assert result["ending_balance_zar"] < 500


def test_minimum_volume_fails_closed_for_small_account():
    data = candles("EURUSD", [(100, 100.1, 99.9, 100), (100, 101, 99.5, 100)])
    result = replay({"EURUSD": data}, {"EURUSD": instrument("EURUSD", conversion=2000)}, one_signal)
    assert any(e.get("reason") == "minimum_lot_exceeds_risk" for e in result["events"])
    assert not result["closed_trades"]


def test_only_two_supported_symbols_and_no_future_rows():
    data = candles("EURUSD", [(100, 100.1, 99.9, 100), (100, 101, 99.5, 100)])
    seen = []
    def signal(symbol, history):
        seen.append(len(history))
        return None
    replay({"EURUSD": data}, {"EURUSD": instrument("EURUSD")}, signal)
    assert seen == [1]
    with pytest.raises(ValueError, match="Only EURUSD and XAUUSD"):
        replay({"GBPUSD": data}, {"GBPUSD": instrument("GBPUSD")}, signal)


def test_combined_position_limit():
    data = candles("EURUSD", [(100, 100.1, 99.9, 100), (100, 100.1, 99.9, 100), (100, 100.1, 99.9, 100)])
    gold = candles("XAUUSD", [(100, 100.1, 99.9, 100), (100, 100.1, 99.9, 100), (100, 100.1, 99.9, 100)])
    result = replay({"EURUSD": data, "XAUUSD": gold},
                    {"EURUSD": instrument("EURUSD"), "XAUUSD": instrument("XAUUSD")},
                    one_signal, max_open=1)
    assert sum(e["action"] == "OPEN" for e in result["events"]) == 1
    assert any(e.get("reason") == "max_open_positions" for e in result["events"])
