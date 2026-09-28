from dashboard.models import (
    BacktestOverview,
    DashboardSnapshot,
    MarketOverview,
    RiskOverview,
    SetupOverview,
)


class DashboardService:

    def create_market_overview(
        self,
        symbol: str,
        asset_class: str,
        price: float,
        structure: str,
        top_down_alignment: str,
        fundamental_bias: str,
    ) -> MarketOverview:

        if not symbol:
            raise ValueError(
                "Symbol must not be empty."
            )

        if price <= 0:
            raise ValueError(
                "Price must be greater than zero."
            )

        return MarketOverview(
            symbol=symbol,
            asset_class=asset_class,
            price=price,
            structure=structure,
            top_down_alignment=top_down_alignment,
            fundamental_bias=fundamental_bias,
        )

    def create_setup_overview(
        self,
        symbol: str,
        direction: str,
        qualified: bool,
        score: int,
        entry: float | None = None,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        risk_reward: float | None = None,
        reasons: list[str] | None = None,
    ) -> SetupOverview:

        if not symbol:
            raise ValueError(
                "Symbol must not be empty."
            )

        if direction not in {
            "bullish",
            "bearish",
            "neutral",
        }:
            raise ValueError(
                "Direction must be bullish, bearish or neutral."
            )

        if score < 0:
            raise ValueError(
                "Score cannot be negative."
            )

        return SetupOverview(
            symbol=symbol,
            direction=direction,
            qualified=qualified,
            score=score,
            entry=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_reward=risk_reward,
            reasons=reasons or [],
        )

    def create_risk_overview(
        self,
        balance: float,
        risk_percent: float,
        risk_amount: float,
        open_trades: int,
        exposure_percent: float,
        daily_loss_percent: float,
    ) -> RiskOverview:

        if balance < 0:
            raise ValueError(
                "Balance cannot be negative."
            )

        if risk_percent < 0:
            raise ValueError(
                "Risk percentage cannot be negative."
            )

        if risk_amount < 0:
            raise ValueError(
                "Risk amount cannot be negative."
            )

        if open_trades < 0:
            raise ValueError(
                "Open trades cannot be negative."
            )

        if exposure_percent < 0:
            raise ValueError(
                "Exposure percentage cannot be negative."
            )

        if daily_loss_percent < 0:
            raise ValueError(
                "Daily loss percentage cannot be negative."
            )

        return RiskOverview(
            balance=balance,
            risk_percent=risk_percent,
            risk_amount=risk_amount,
            open_trades=open_trades,
            exposure_percent=exposure_percent,
            daily_loss_percent=daily_loss_percent,
        )

    def create_backtest_overview(
        self,
        symbol: str,
        total_trades: int,
        winning_trades: int,
        losing_trades: int,
        win_rate: float,
        total_profit: float,
        profit_factor: float,
    ) -> BacktestOverview:

        if not symbol:
            raise ValueError(
                "Symbol must not be empty."
            )

        if total_trades < 0:
            raise ValueError(
                "Total trades cannot be negative."
            )

        if winning_trades < 0 or losing_trades < 0:
            raise ValueError(
                "Trade counts cannot be negative."
            )

        if not 0 <= win_rate <= 100:
            raise ValueError(
                "Win rate must be between 0 and 100."
            )

        return BacktestOverview(
            symbol=symbol,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            total_profit=total_profit,
            profit_factor=profit_factor,
        )

    def create_snapshot(
        self,
        market: MarketOverview,
        risk: RiskOverview,
        setup: SetupOverview | None = None,
        backtest: BacktestOverview | None = None,
    ) -> DashboardSnapshot:

        return DashboardSnapshot(
            market=market,
            setup=setup,
            risk=risk,
            backtest=backtest,
        )
