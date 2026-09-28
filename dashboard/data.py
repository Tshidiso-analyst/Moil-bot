from dataclasses import asdict
from typing import Any

from dashboard.models import (
    BacktestOverview,
    DashboardSnapshot,
    MarketOverview,
    RiskOverview,
    SetupOverview,
)


class DashboardData:

    @staticmethod
    def market(
        overview: MarketOverview,
    ) -> dict[str, Any]:
        return asdict(overview)

    @staticmethod
    def setup(
        overview: SetupOverview | None,
    ) -> dict[str, Any] | None:

        if overview is None:
            return None

        return asdict(overview)

    @staticmethod
    def risk(
        overview: RiskOverview,
    ) -> dict[str, Any]:
        return asdict(overview)

    @staticmethod
    def backtest(
        overview: BacktestOverview | None,
    ) -> dict[str, Any] | None:

        if overview is None:
            return None

        return asdict(overview)

    @classmethod
    def snapshot(
        cls,
        snapshot: DashboardSnapshot,
    ) -> dict[str, Any]:

        return {
            "market": cls.market(snapshot.market),
            "setup": cls.setup(snapshot.setup),
            "risk": cls.risk(snapshot.risk),
            "backtest": cls.backtest(snapshot.backtest),
        }
