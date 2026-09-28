from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class FairValueGap:
    index: int
    direction: str
    lower: float
    upper: float


def find_fair_value_gaps(
    dataframe: pd.DataFrame,
) -> list[FairValueGap]:
    gaps = []

    if len(dataframe) < 3:
        return gaps

    for i in range(2, len(dataframe)):
        candle_before = dataframe.iloc[i - 2]
        candle_after = dataframe.iloc[i]

        if candle_after["low"] > candle_before["high"]:
            gaps.append(
                FairValueGap(
                    index=i,
                    direction="bullish",
                    lower=float(candle_before["high"]),
                    upper=float(candle_after["low"]),
                )
            )

        elif candle_after["high"] < candle_before["low"]:
            gaps.append(
                FairValueGap(
                    index=i,
                    direction="bearish",
                    lower=float(candle_after["high"]),
                    upper=float(candle_before["low"]),
                )
            )

    return gaps
