import pandas as pd
import pytest

from backtesting.cost_aware_engine import CostAwareBacktestEngine


def bars(rows):
    return pd.DataFrame(
        rows,
        columns=["timestamp", "open", "high", "low", "close"],
    ).assign(timestamp=lambda frame: pd.to_datetime(frame["timestamp"], utc=True))


def base_data():
    return bars([
        ("2026-01-01 00:00", 100.0, 100.5, 99.8, 100.0),
        ("2026-01-01 01:00", 100.0, 101.0, 99.8, 100.5),
        ("2026-01-01 02:00", 100.5, 103.0, 100.2, 102.5),
        ("2026-01-01 03:00", 102.5, 103.0, 102.0, 102.4),
        ("2026-01-01 04:00", 102.4, 103.0, 101.5, 102.0),
        ("2026-01-01 05:00", 102.0, 102.5, 101.0, 101.5),
    ])


def one_bullish_signal(history):
    return "bullish" if len(history) == 1 else None


def test_signal_enters_at_next_candle_open_and_costs_reduce_profit():
    result = CostAwareBacktestEngine().run(
        base_data(),
        "EURUSD",
        one_bullish_signal,
        stop_distance=1.0,
        reward_multiple=2.0,
        spread=0.2,
        slippage=0.1,
        commission_per_unit_per_side=0.01,
        position_size=1.0,
    )

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.signal_index == 0
    assert trade.entry_index == 1
    assert trade.reference_entry_price == 100.0
    assert trade.entry_fill_price == pytest.approx(100.2)
    assert trade.reference_exit_price == pytest.approx(102.0)
    assert trade.gross_profit == pytest.approx(2.0)
    assert trade.trading_costs == pytest.approx(0.4)
    assert trade.commission_costs == pytest.approx(0.02)
    assert trade.net_profit == pytest.approx(1.58)
    assert result.total_net_profit == pytest.approx(1.58)
    assert result.winning_trades == 1


def test_callback_only_receives_historical_prefix():
    data = base_data()
    observed = []

    def signal(history):
        observed.append((len(history), history["timestamp"].max()))
        return None

    CostAwareBacktestEngine().run(data, "TEST", signal, stop_distance=1.0)

    assert observed
    assert [length for length, _ in observed] == list(range(1, len(data)))
    for length, latest_timestamp in observed:
        assert latest_timestamp == data.iloc[length - 1]["timestamp"]


def test_both_stop_and_target_touched_uses_stop_first():
    data = bars([
        ("2026-01-01 00:00", 100, 100.2, 99.8, 100),
        ("2026-01-01 01:00", 100, 100.5, 99.5, 100),
        ("2026-01-01 02:00", 100, 103, 98, 101),
        ("2026-01-01 03:00", 101, 101.5, 100.5, 101),
    ])
    result = CostAwareBacktestEngine().run(
        data, "TEST", one_bullish_signal, stop_distance=1, reward_multiple=2
    )
    assert result.trades[0].exit_reason == "stop_loss_ambiguous_candle"
    assert result.trades[0].reference_exit_price == pytest.approx(99)


def test_gap_through_stop_uses_adverse_open_price():
    data = bars([
        ("2026-01-01 00:00", 100, 100.2, 99.8, 100),
        ("2026-01-01 01:00", 100, 100.5, 99.5, 100),
        ("2026-01-01 02:00", 97, 98, 96, 97.5),
    ])
    result = CostAwareBacktestEngine().run(
        data, "TEST", one_bullish_signal, stop_distance=1, reward_multiple=2
    )
    assert result.trades[0].exit_reason == "stop_loss_gap"
    assert result.trades[0].reference_exit_price == pytest.approx(97)


def test_favorable_gap_through_target_exits_at_target():
    data = bars([
        ("2026-01-01 00:00", 100, 100.2, 99.8, 100),
        ("2026-01-01 01:00", 100, 100.5, 99.8, 100.1),
        ("2026-01-01 02:00", 103, 104, 102.5, 103.5),
    ])
    result = CostAwareBacktestEngine().run(
        data, "TEST", one_bullish_signal, stop_distance=1, reward_multiple=2
    )
    assert result.trades[0].exit_reason == "take_profit_gap"
    # Use target price, not a potentially optimistic opening fill.
    assert result.trades[0].reference_exit_price == pytest.approx(102)


def test_unclosed_trade_is_closed_at_last_close():
    data = bars([
        ("2026-01-01 00:00", 100, 100.2, 99.8, 100),
        ("2026-01-01 01:00", 100, 100.4, 99.7, 100.1),
        ("2026-01-01 02:00", 100.1, 100.8, 99.9, 100.6),
    ])
    result = CostAwareBacktestEngine().run(
        data, "TEST", one_bullish_signal, stop_distance=10, reward_multiple=2
    )
    assert len(result.trades) == 1
    assert result.trades[0].exit_reason == "end_of_data"
    assert result.trades[0].reference_exit_price == pytest.approx(100.6)


def test_train_test_split_is_chronological_and_test_can_use_warmup():
    data = base_data()
    calls = []

    def signal(history):
        calls.append(history["timestamp"].max())
        # Produce exactly one test signal at the first test segment candle.
        return "bullish" if history["timestamp"].max() == data.iloc[4]["timestamp"] else None

    split = CostAwareBacktestEngine().run_train_test(
        data,
        "TEST",
        signal,
        train_fraction=0.6,
        stop_distance=0.5,
        reward_multiple=1.0,
    )
    assert split.split_timestamp == data.iloc[3]["timestamp"]
    assert all(t.entry_index >= 1 for t in split.train.trades)
    assert all(t.signal_index >= 3 for t in split.test.trades)
    assert all(t.entry_index >= 4 for t in split.test.trades)
    assert split.test.trades


def test_rejects_bad_prices_duplicate_timestamps_and_invalid_signal():
    invalid = base_data()
    invalid.loc[0, "high"] = 98
    with pytest.raises(ValueError, match="Invalid OHLC"):
        CostAwareBacktestEngine().run(invalid, "TEST", lambda _: None, stop_distance=1)

    duplicate = base_data()
    duplicate.loc[1, "timestamp"] = duplicate.loc[0, "timestamp"]
    with pytest.raises(ValueError, match="unique"):
        CostAwareBacktestEngine().run(duplicate, "TEST", lambda _: None, stop_distance=1)

    with pytest.raises(ValueError, match="signal_fn must return"):
        CostAwareBacktestEngine().run(
            base_data(), "TEST", lambda _: "sideways", stop_distance=1
        )


def test_rejects_invalid_costs_and_split_fraction():
    engine = CostAwareBacktestEngine()
    with pytest.raises(ValueError, match="spread"):
        engine.run(base_data(), "TEST", lambda _: None, stop_distance=1, spread=-0.1)
    with pytest.raises(ValueError, match="train_fraction"):
        engine.run_train_test(base_data(), "TEST", lambda _: None, train_fraction=1.0, stop_distance=1)


def test_empty_input_returns_zeroed_result():
    result = CostAwareBacktestEngine().run(
        pd.DataFrame(), "TEST", lambda _: None, stop_distance=1
    )
    assert result.trades == []
    assert result.total_net_profit == 0
    assert result.win_rate == 0
    assert result.ending_equity == result.initial_equity


def test_profit_factor_and_drawdown_are_reported_from_net_trade_results():
    data = bars([
        ("2026-01-01 00:00", 100, 100.2, 99.8, 100),
        ("2026-01-01 01:00", 100, 100.5, 99.8, 100.1),
        ("2026-01-01 02:00", 100.1, 103, 99.8, 102.5),
        ("2026-01-01 03:00", 102.5, 103, 102, 102.2),
    ])
    result = CostAwareBacktestEngine().run(
        data, "TEST", one_bullish_signal, stop_distance=1, reward_multiple=2, initial_equity=100
    )
    # Profit factor is undefined when the sample has no losing trades.
    assert result.profit_factor is None
    assert result.max_drawdown >= 0
    assert result.ending_equity == pytest.approx(100 + result.total_net_profit)
