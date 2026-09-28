from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class ScanResult:
    symbol: str
    close: float
    change_percent: float
    average_volume: float


class MarketScanner:
    def scan(
        self,
        datasets: dict[str, pd.DataFrame],
    ) -> list[ScanResult]:
        results = []

        for symbol, dataframe in datasets.items():
            if dataframe.empty or len(dataframe) < 2:
                continue

            previous_close = float(
                dataframe.iloc[-2]["close"]
            )
            latest_close = float(
                dataframe.iloc[-1]["close"]
            )

            if previous_close == 0:
                continue

            change_percent = (
                (latest_close - previous_close)
                / previous_close
                * 100
            )

            average_volume = float(
                dataframe["volume"].tail(20).mean()
            )

            results.append(
                ScanResult(
                    symbol=symbol,
                    close=latest_close,
                    change_percent=change_percent,
                    average_volume=average_volume,
                )
            )

        return sorted(
            results,
            key=lambda result: abs(result.change_percent),
            reverse=True,
        )
