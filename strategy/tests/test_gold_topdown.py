"""No-lookahead and fail-closed checks for gold top-down research."""
from strategy.gold_topdown import confirmed_pivots, structure_bias, inspect_gold_topdown


def bars_from_closes(values):
    return [{"open": v, "close": v, "high": v + 0.1, "low": v - 0.1}
            for v in values]


def test_pivot_requires_two_later_closed_bars():
    bars = bars_from_closes([1, 2, 5, 2])
    assert confirmed_pivots(bars)["highs"] == []
    bars.append({"open": 1, "close": 1, "high": 1.1, "low": 0.9})
    assert confirmed_pivots(bars)["highs"][0]["index"] == 2
    assert confirmed_pivots(bars)["highs"][0]["confirmed_index"] == 4


def test_short_or_invalid_input_never_approves_execution():
    valid = bars_from_closes([100] * 15)
    outcome = inspect_gold_topdown(d1_bars=valid, h4_bars=valid,
                                   h1_bars=valid, m15_bars=valid)
    assert outcome["status"] == "WAIT"
    assert outcome["execution_ready"] is False
    assert outcome["direction"] == "neutral"
    missing = inspect_gold_topdown(d1_bars=[], h4_bars=valid,
                                   h1_bars=valid, m15_bars=valid)
    assert missing["stage"] == "data"
    assert missing["execution_ready"] is False


def test_mixed_structure_is_neutral():
    bars = bars_from_closes([1, 2, 4, 2, 1, 2, 5, 2, 1, 2, 4, 2, 1])
    assert structure_bias(bars)["bias"] == "neutral"


def test_invalid_ohlc_fails_closed():
    valid = bars_from_closes([100] * 15)
    invalid = list(valid)
    invalid[4] = {"open": 1, "close": 2, "high": 1, "low": 0}
    outcome = inspect_gold_topdown(d1_bars=invalid, h4_bars=valid,
                                   h1_bars=valid, m15_bars=valid)
    assert outcome["stage"] == "data"
    assert outcome["execution_ready"] is False
