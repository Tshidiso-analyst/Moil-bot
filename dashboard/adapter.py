from backtesting.metrics import calculate_profit_factor
from backtesting.models import BacktestResult
from dashboard.models import (
    BacktestOverview,
    MarketOverview,
    RiskOverview,
    SetupOverview,
)
from fundamentals.models import FundamentalContext
from instruments.classifier import classify_symbol
from qualification.models import QualificationResult
from risk.models import AccountRisk


class DashboardAdapter:

    def market_from_analysis(
        self,
        symbol: str,
        price: float,
        structure: str,
        top_down_alignment: str,
        fundamentals: FundamentalContext,
        description: str = "",
    ) -> MarketOverview:

        return MarketOverview(
            symbol=symbol,
            asset_class=classify_symbol(
                symbol,
                description,
            ),
            price=price,
            structure=structure,
            top_down_alignment=top_down_alignment,
            fundamental_bias=fundamentals.bias,
        )

    def setup_from_qualification(
        self,
        symbol: str,
        qualification: QualificationResult,
        entry: float | None = None,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        risk_reward: float | None = None,
    ) -> SetupOverview:

        return SetupOverview(
            symbol=symbol,
            direction=qualification.direction,
            qualified=qualification.qualified,
            score=qualification.score,
            entry=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_reward=risk_reward,
            reasons=qualification.reasons,
        )

    def risk_from_account(
        self,
        account: AccountRisk,
        open_trades: int = 0,
        exposure_percent: float = 0.0,
        daily_loss_percent: float = 0.0,
    ) -> RiskOverview:

        return RiskOverview(
            balance=account.balance,
            risk_percent=account.risk_percent,
            risk_amount=account.risk_amount,
            open_trades=open_trades,
            exposure_percent=exposure_percent,
            daily_loss_percent=daily_loss_percent,
        )

    def backtest_from_result(
        self,
        symbol: str,
        result: BacktestResult,
    ) -> BacktestOverview:

        return BacktestOverview(
            symbol=symbol,
            total_trades=len(result.trades),
            winning_trades=result.winning_trades,
            losing_trades=result.losing_trades,
            win_rate=result.win_rate,
            total_profit=result.total_profit,
            profit_factor=calculate_profit_factor(
                result
            ),
        )
