import pandas as pd

from analysis.market_structure import analyse_structure
from analysis.smc_patterns import find_fair_value_gaps, find_liquidity_sweeps
from analysis.top_down import TopDownAnalyzer


def sample_data():
    return pd.DataFrame(
        {
            "open": [
                1, 2, 1, 3, 2, 4, 3, 5, 4, 6
            ],
            "high": [
                2, 3, 2, 4, 3, 5, 4, 6, 5, 7
            ],
            "low": [
                0, 1, 0, 2, 1, 3, 2, 4, 3, 5
            ],
            "close": [
                1.5, 2.5, 1.5, 3.5, 2.5,
                4.5, 3.5, 5.5, 4.5, 6.5
            ],
        }
    )


def test_market_structure_runs():
    result = analyse_structure(sample_data())

    assert result.trend in {
        "bullish",
        "bearish",
        "neutral",
    }


def test_fair_value_gap_detection():
    dataframe = pd.DataFrame(
        {
            "high": [10, 11, 15],
            "low": [8, 9, 14],
        }
    )

    gaps = find_fair_value_gaps(dataframe)

    assert len(gaps) == 1
    assert gaps[0].direction == "bullish"


def test_top_down_analysis():
    dataframe = sample_data()

    result = TopDownAnalyzer().analyse(
        {
            "H4": dataframe,
            "H1": dataframe,
            "M15": dataframe,
        }
    )

    assert len(result.analyses) == 3
    assert result.alignment in {
        "bullish",
        "bearish",
        "mixed",
        "neutral",
    }



def test_high_sweep_is_labelled_buy_side_liquidity():
    dataframe = pd.DataFrame({
        "open": [1.05, 1.10, 1.08, 1.15, 1.14],
        "high": [1.10, 1.20, 1.15, 1.25, 1.16],
        "low": [1.00, 1.05, 1.03, 1.10, 1.12],
        "close": [1.08, 1.18, 1.10, 1.19, 1.15],
    })

    sweeps = find_liquidity_sweeps(dataframe)

    assert len(sweeps) == 1
    assert sweeps[0].direction == "buy_side"


def test_low_sweep_is_labelled_sell_side_liquidity():
    dataframe = pd.DataFrame({
        "open": [1.05, 1.10, 1.08, 1.02, 1.03],
        "high": [1.10, 1.15, 1.12, 1.08, 1.10],
        "low": [1.00, 1.05, 1.02, 0.95, 1.01],
        "close": [1.08, 1.10, 1.05, 1.01, 1.07],
    })

    sweeps = find_liquidity_sweeps(dataframe)

    assert len(sweeps) == 1
    assert sweeps[0].direction == "sell_side"
