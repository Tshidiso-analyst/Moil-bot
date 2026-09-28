from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class StructurePoint:
    index: int
    price: float
    point_type: str


@dataclass(frozen=True)
class StructureAnalysis:
    trend: str
    swing_highs: list[StructurePoint]
    swing_lows: list[StructurePoint]


def find_swing_highs(
    dataframe: pd.DataFrame,
    lookback: int = 2,
) -> list[StructurePoint]:
    if lookback < 1:
        raise ValueError("lookback must be at least 1.")

    highs = []

    for i in range(
        lookback,
        len(dataframe) - lookback,
    ):
        current = dataframe.iloc[i]["high"]

        left = dataframe.iloc[
            i - lookback:i
        ]["high"]

        right = dataframe.iloc[
            i + 1:i + lookback + 1
        ]["high"]

        if current > left.max() and current > right.max():
            highs.append(
                StructurePoint(
                    index=i,
                    price=float(current),
                    point_type="swing_high",
                )
            )

    return highs


def find_swing_lows(
    dataframe: pd.DataFrame,
    lookback: int = 2,
) -> list[StructurePoint]:
    if lookback < 1:
        raise ValueError("lookback must be at least 1.")

    lows = []

    for i in range(
        lookback,
        len(dataframe) - lookback,
    ):
        current = dataframe.iloc[i]["low"]

        left = dataframe.iloc[
            i - lookback:i
        ]["low"]

        right = dataframe.iloc[
            i + 1:i + lookback + 1
        ]["low"]

        if current < left.min() and current < right.min():
            lows.append(
                StructurePoint(
                    index=i,
                    price=float(current),
                    point_type="swing_low",
                )
            )

    return lows


def analyse_structure(
    dataframe: pd.DataFrame,
    lookback: int = 2,
) -> StructureAnalysis:
    swing_highs = find_swing_highs(
        dataframe,
        lookback,
    )

    swing_lows = find_swing_lows(
        dataframe,
        lookback,
    )

    trend = "neutral"

    if len(swing_highs) >= 2 and len(swing_lows) >= 2:
        higher_high = (
            swing_highs[-1].price
            > swing_highs[-2].price
        )

        higher_low = (
            swing_lows[-1].price
            > swing_lows[-2].price
        )

        lower_high = (
            swing_highs[-1].price
            < swing_highs[-2].price
        )

        lower_low = (
            swing_lows[-1].price
            < swing_lows[-2].price
        )

        if higher_high and higher_low:
            trend = "bullish"
        elif lower_high and lower_low:
            trend = "bearish"

    return StructureAnalysis(
        trend=trend,
        swing_highs=swing_highs,
        swing_lows=swing_lows,
    )
