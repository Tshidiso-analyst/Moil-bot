from __future__ import annotations

from dataclasses import dataclass
import math

import pandas as pd

from analysis.smc_patterns import analyze_market_context
from risk.trade_guard import TradeGuard
from risk.symbols import canonicalize_symbol


@dataclass(frozen=True)
class TradeAssessment:
    symbol: str
    direction: str
    session: str
    trend: str
    setup_valid: bool
    confirmation: bool
    reasons: list[str]
    entry: float | None
    stop_loss: float | None
    take_profit: float | None
    risk_percent: float
    max_risk_per_trade: float = 1.0
    max_daily_loss: float = 5.0
    max_open_trades: int = 3
    max_trades_per_day: int = 10
    max_position_volume: float = 0.02
    structure_valid: bool = False
    liquidity_valid: bool = False
    macro_bias_valid: bool = False
    high_impact_news: bool = False


class TradeDecisionEngine:
    """Combine ICT/SMC context, macro risk, and confirmation into a candidate evaluation."""

    def __init__(
        self,
        risk_guard: TradeGuard | None = None,
        min_confirmation_score: int = 3,
    ):
        self.risk_guard = risk_guard or TradeGuard()
        self.min_confirmation_score = min_confirmation_score

    def assess(
        self,
        symbol: str,
        dataframe: pd.DataFrame,
        *,
        fundamental_bias: str = "neutral",
        proposed_risk_percent: float = 0.5,
        daily_loss_percent: float = 0.0,
        open_trades: int = 0,
        current_daily_entries: int = 0,
        high_impact_news: bool = True,
    ) -> TradeAssessment:
        symbol = canonicalize_symbol(symbol)
        if fundamental_bias not in {"bullish", "bearish", "neutral"}:
            raise ValueError("fundamental_bias must be bullish, bearish or neutral.")
        try:
            proposed_risk_percent = float(proposed_risk_percent)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("proposed_risk_percent must be numeric.") from None
        if not math.isfinite(proposed_risk_percent) or not 0 < proposed_risk_percent <= 1.0:
            raise ValueError("proposed_risk_percent must be greater than 0 and no more than 1%.")
        if not isinstance(dataframe, pd.DataFrame) or dataframe.empty:
            raise ValueError("dataframe must be a non-empty pandas DataFrame")
        if not isinstance(high_impact_news, bool):
            raise ValueError("high_impact_news must be a boolean.")

        context = analyze_market_context(dataframe)
        reasons: list[str] = []
        reasons.extend(context.reasons)

        direction = "neutral"
        if context.trend == "bullish" and not context.distribution:
            direction = "bullish"
        elif context.trend == "bearish" and not context.distribution:
            direction = "bearish"
        else:
            direction = "neutral"

        if fundamental_bias in {"bullish", "bearish"} and direction != "neutral":
            if fundamental_bias != direction:
                reasons.append(
                    f"Fundamental bias {fundamental_bias} conflicts with technical direction {direction}; no trade."
                )
                direction = "neutral"
            else:
                reasons.append("Fundamental bias confirms the technical direction.")

        if context.session not in {"london", "new_york", "london_new_york_overlap"}:
            reasons.append("Trading session is not in a high-probability active window.")
            direction = "neutral"

        if context.consolidation:
            reasons.append("Consolidation means wait for structure and confirmation before entry.")
            direction = "neutral"

        confirmation_score = 0
        if context.fair_value_gaps:
            last_gap = context.fair_value_gaps[-1]
            if last_gap.direction == direction:
                confirmation_score += 1
                reasons.append(f"Fair value gap aligns with {direction}.")
            else:
                reasons.append("Fair value gap does not align with the directional bias.")

        if context.bos:
            last_bos = context.bos[-1]
            if last_bos["direction"] == direction:
                confirmation_score += 1
                reasons.append(f"Latest BOS supports {direction}.")

        if context.choch:
            last_choch = context.choch[-1]
            if last_choch["direction"] == direction:
                confirmation_score += 1
                reasons.append(f"Latest CHoCH supports {direction}.")

        if context.liquidity:
            last_sweep = context.liquidity[-1]
            if last_sweep.direction == ("sell_side" if direction == "bullish" else "buy_side"):
                confirmation_score += 1
                reasons.append("Liquidity sweep is aligned with the intended directional move.")

        confirmation = confirmation_score >= self.min_confirmation_score and direction != "neutral"
        structure_valid = direction != "neutral" and context.trend == direction and not context.distribution and not context.consolidation
        liquidity_valid = bool(context.liquidity)
        macro_bias_valid = fundamental_bias == "neutral" or fundamental_bias == direction

        if direction == "neutral":
            reasons.append("Direction is neutral after full market context analysis.")
            return TradeAssessment(
                symbol=str(symbol).upper(),
                direction="neutral",
                session=context.session,
                trend=context.trend,
                setup_valid=False,
                confirmation=False,
                reasons=reasons,
                entry=None,
                stop_loss=None,
                take_profit=None,
                risk_percent=proposed_risk_percent,
                max_risk_per_trade=self.risk_guard.max_risk_per_trade,
                max_daily_loss=self.risk_guard.max_daily_loss,
                max_open_trades=self.risk_guard.max_open_trades,
                max_trades_per_day=self.risk_guard.max_trades_per_day,
                max_position_volume=self.risk_guard.max_position_volume,
                structure_valid=False,
                liquidity_valid=False,
                macro_bias_valid=False,
                high_impact_news=high_impact_news,
            )

        last_close = float(dataframe["close"].iloc[-1])
        last_low = float(dataframe["low"].iloc[-1])
        last_high = float(dataframe["high"].iloc[-1])

        if direction == "bullish":
            entry = last_close
            stop_loss = min(last_low, last_close * 0.998)
            take_profit = max(last_high, last_close * 1.008)
        else:
            entry = last_close
            stop_loss = max(last_high, last_close * 1.002)
            take_profit = min(last_low, last_close * 0.992)

        guard_decision = self.risk_guard.evaluate(
            proposed_risk_percent=proposed_risk_percent,
            daily_loss_percent=daily_loss_percent,
            open_trades=open_trades,
            confirmation=confirmation,
            high_impact_news=high_impact_news,
            structure_valid=structure_valid,
            liquidity_valid=liquidity_valid,
            macro_bias_valid=macro_bias_valid,
            current_daily_entries=current_daily_entries,
        )

        if not guard_decision.allowed:
            reasons.append(f"Risk guard blocked execution: {guard_decision.reason}")
            confirmation = False

        return TradeAssessment(
            symbol=str(symbol).upper(),
            direction=direction,
            session=context.session,
            trend=context.trend,
            setup_valid=confirmation,
            confirmation=confirmation,
            reasons=reasons,
            entry=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_percent=proposed_risk_percent,
            max_risk_per_trade=self.risk_guard.max_risk_per_trade,
            max_daily_loss=self.risk_guard.max_daily_loss,
            max_open_trades=self.risk_guard.max_open_trades,
            max_trades_per_day=self.risk_guard.max_trades_per_day,
            max_position_volume=self.risk_guard.max_position_volume,
            structure_valid=structure_valid,
            liquidity_valid=liquidity_valid,
            macro_bias_valid=macro_bias_valid,
            high_impact_news=high_impact_news,
        )


__all__ = ["TradeAssessment", "TradeDecisionEngine"]
