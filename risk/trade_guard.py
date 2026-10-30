from __future__ import annotations

from dataclasses import dataclass

from risk.limits import can_open_trade
from risk.models import RiskLimits


@dataclass(frozen=True)
class GuardDecision:
    allowed: bool
    reason: str = ""


class TradeGuard:
    """Central risk gate for trade qualification and execution approval."""

    def __init__(
        self,
        *,
        max_risk_per_trade: float = 1.0,
        max_open_trades: int = 3,
        max_total_exposure_percent: float = 3.0,
        max_daily_loss: float = 5.0,
    ):
        self.max_risk_per_trade = float(max_risk_per_trade)
        self.max_open_trades = int(max_open_trades)
        self.max_total_exposure_percent = float(max_total_exposure_percent)
        self.max_daily_loss = float(max_daily_loss)
        self.limits = RiskLimits(
            max_risk_per_trade_percent=self.max_risk_per_trade,
            max_open_trades=self.max_open_trades,
            max_total_exposure_percent=self.max_total_exposure_percent,
            max_daily_loss_percent=self.max_daily_loss,
        )

    def evaluate(
        self,
        *,
        proposed_risk_percent: float,
        daily_loss_percent: float,
        open_trades: int,
        confirmation: bool,
        high_impact_news: bool,
        structure_valid: bool,
        liquidity_valid: bool,
        macro_bias_valid: bool,
        current_exposure_percent: float = 0.0,
    ) -> GuardDecision:
        if not confirmation:
            return GuardDecision(False, "Trade setup is not confirmed.")

        if not structure_valid:
            return GuardDecision(False, "Market structure check failed.")

        if not liquidity_valid:
            return GuardDecision(False, "Liquidity context is not valid.")

        if not macro_bias_valid:
            return GuardDecision(False, "Macro bias is not aligned with the trade idea.")

        if high_impact_news:
            return GuardDecision(False, "High-impact news is active; no new execution is allowed.")

        if not can_open_trade(
            limits=self.limits,
            current_open_trades=open_trades,
            current_exposure_percent=current_exposure_percent,
            proposed_risk_percent=proposed_risk_percent,
            daily_loss_percent=daily_loss_percent,
        ):
            reason = "Risk guard rejected the trade."

            if open_trades >= self.max_open_trades:
                reason = (
                    f"Open trade limit reached: {open_trades}/{self.max_open_trades}."
                )
            elif (
                current_exposure_percent + proposed_risk_percent
                > self.max_total_exposure_percent
            ):
                reason = (
                    "Total exposure would exceed the maximum allowed exposure percent."
                )
            elif daily_loss_percent >= self.max_daily_loss:
                reason = (
                    "Daily loss threshold is already at or above the allowed limit."
                )
            elif proposed_risk_percent > self.max_risk_per_trade:
                reason = (
                    "Proposed trade risk exceeds the maximum allowed risk per trade."
                )

            return GuardDecision(False, reason)

        return GuardDecision(True, "Risk checks passed.")


__all__ = ["GuardDecision", "TradeGuard"]
