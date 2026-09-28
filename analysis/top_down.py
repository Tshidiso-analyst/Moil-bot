from dataclasses import dataclass

import pandas as pd

from analysis.market_structure import analyse_structure


@dataclass(frozen=True)
class TimeframeAnalysis:
    timeframe: str
    trend: str


@dataclass(frozen=True)
class TopDownAnalysis:
    analyses: list[TimeframeAnalysis]
    alignment: str


class TopDownAnalyzer:
    def analyse(
        self,
        datasets: dict[str, pd.DataFrame],
    ) -> TopDownAnalysis:
        analyses = []

        for timeframe, dataframe in datasets.items():
            structure = analyse_structure(dataframe)

            analyses.append(
                TimeframeAnalysis(
                    timeframe=timeframe,
                    trend=structure.trend,
                )
            )

        trends = {
            analysis.trend
            for analysis in analyses
            if analysis.trend != "neutral"
        }

        if len(trends) == 1:
            alignment = next(iter(trends))
        elif len(trends) > 1:
            alignment = "mixed"
        else:
            alignment = "neutral"

        return TopDownAnalysis(
            analyses=analyses,
            alignment=alignment,
        )
