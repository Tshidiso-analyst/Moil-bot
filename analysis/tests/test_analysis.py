import pandas as pd

from analysis.market_structure import analyse_structure
from analysis.smc_patterns import find_fair_value_gaps
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
