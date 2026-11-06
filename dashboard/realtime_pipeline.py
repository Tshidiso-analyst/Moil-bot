from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from analysis.market_structure import analyse_structure
from analysis.smc_patterns import analyze_market_context
from market_data.live_data import load_live_market_datasets, resolve_mt5_symbol
from qualification.engine import SetupQualifier
from risk.account import calculate_account_risk
from risk.trade_guard import TradeGuard
from strategy.engine import StrategyEngine


@dataclass
class RealTimePipelineResult:
    symbol: str
    status: str
    direction: str
    qualified: bool
    score: int
    entry: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    risk_percent: float = 0.0
    risk_amount: float = 0.0
    reasons: list[str] = field(default_factory=list)
    market_context: dict[str, Any] = field(default_factory=dict)


class RealtimeTradingPipeline:
    """Fetch MT5 data and produce explainable analysis; never submits orders."""

    def __init__(self, mt5_path: str | None = None):
        self.mt5_path = mt5_path

    def _build_datasets(self, requested_symbol: str) -> tuple[str, dict[str, pd.DataFrame]]:
        try:
            import MetaTrader5 as mt5
        except ImportError as exc:
            raise ValueError("MetaTrader5 Python package is unavailable in this environment.") from exc

        try:
            actual_symbol = resolve_mt5_symbol(requested_symbol, mt5)
        except Exception as exc:
            raise ValueError(
                f"{requested_symbol} is not available in the connected MT5 terminal. "
                "Open Market Watch in MT5 and confirm the broker's exact instrument name."
            ) from exc

        try:
            datasets = load_live_market_datasets(
                symbol=actual_symbol,
                timeframes=("M15", "H1"),
                bars=250,
                mt5_path=self.mt5_path,
            )
        except Exception as exc:
            raise ValueError(
                f"Could not load M15/H1 candle history for {actual_symbol}. "
                "Open that symbol's chart in MT5, load history, and try again. "
                f"Details: {exc}"
            ) from exc
        if "M15" not in datasets or len(datasets["M15"]) < 20:
            raise ValueError(f"At least 20 M15 candles are needed to analyze {actual_symbol}.")
        return actual_symbol, datasets

    @staticmethod
    def _calculate_levels(dataframe: pd.DataFrame, direction: str) -> tuple[float | None, float | None, float | None]:
        if dataframe.empty:
            return None, None, None
        last_close = float(dataframe["close"].iloc[-1])
        recent_high = float(dataframe["high"].tail(20).max())
        recent_low = float(dataframe["low"].tail(20).min())
        if direction == "bullish":
            stop_loss = recent_low
            take_profit = last_close + max(2 * abs(last_close - stop_loss), 0.0005 * last_close)
            return last_close, stop_loss, take_profit
        if direction == "bearish":
            stop_loss = recent_high
            take_profit = last_close - max(2 * abs(stop_loss - last_close), 0.0005 * last_close)
            return last_close, stop_loss, take_profit
        return last_close, None, None

    def evaluate(self, symbol: str, balance: float, risk_percent: float = 1.0) -> RealTimePipelineResult:
        requested_symbol = str(symbol or "").strip().upper()
        if not requested_symbol:
            raise ValueError("Symbol must not be empty.")

        try:
            actual_symbol, datasets = self._build_datasets(requested_symbol)
            strategy = StrategyEngine().evaluate(
                symbol=actual_symbol,
                datasets=datasets,
                fundamental_bias="neutral",
                execution_timeframe="M15",
            )
            execution_frame = datasets["M15"].copy()
            structure = analyse_structure(execution_frame)
            market_context = analyze_market_context(execution_frame, "M15")
            qualifier = SetupQualifier().qualify(
                structure_trend=structure.trend,
                top_down_alignment=strategy.top_down_alignment,
                fvg_direction=(market_context.fair_value_gaps[-1].direction if market_context.fair_value_gaps else None),
                fundamental_bias=strategy.fundamental_bias,
            )
            direction = strategy.direction if strategy.direction in {"bullish", "bearish"} else qualifier.direction
            qualified = strategy.status in {"research_candidate", "needs_source_evidence"} and qualifier.qualified
            risk = calculate_account_risk(balance=balance, risk_percent=risk_percent)
            entry, stop_loss, take_profit = self._calculate_levels(execution_frame, direction)
            guard = TradeGuard(
                max_risk_per_trade=1.0,
                max_open_trades=3,
                max_total_exposure_percent=3.0,
                max_daily_loss=5.0,
            )
            guard_decision = guard.evaluate(
                proposed_risk_percent=risk_percent,
                daily_loss_percent=0.0,
                open_trades=0,
                confirmation=qualified,
                high_impact_news=False,
                structure_valid=structure.trend in {"bullish", "bearish"},
                liquidity_valid=bool(market_context.liquidity),
                macro_bias_valid=True,
                current_exposure_percent=0.0,
            )
            reasons = list(strategy.reasons) + list(qualifier.reasons)
            reasons.append(f"Risk guard: {guard_decision.reason}")
            return RealTimePipelineResult(
                symbol=actual_symbol,
                status="accepted" if guard_decision.allowed and qualified else ("rejected" if not guard_decision.allowed else "watch"),
                direction=direction,
                qualified=bool(guard_decision.allowed and qualified),
                score=max(strategy.score, qualifier.score),
                entry=entry,
                stop_loss=stop_loss,
                take_profit=take_profit,
                risk_percent=risk_percent,
                risk_amount=risk.risk_amount,
                reasons=reasons,
                market_context={
                    "session": market_context.session,
                    "trend": market_context.trend,
                    "bias": market_context.bias,
                    "distribution": market_context.distribution,
                    "consolidation": market_context.consolidation,
                    "premium_discount": market_context.premium_discount,
                    "liquidity_sweeps": len(market_context.liquidity),
                    "fair_value_gaps": len(market_context.fair_value_gaps),
                    "bos": len(market_context.bos),
                    "choch": len(market_context.choch),
                },
            )
        except Exception as exc:
            # Keep the web page available and show a useful diagnosis instead
            # of allowing an MT5/data error to become an HTTP 500.
            return RealTimePipelineResult(
                symbol=requested_symbol,
                status="data_unavailable",
                direction="neutral",
                qualified=False,
                score=0,
                risk_percent=risk_percent,
                risk_amount=float(balance) * float(risk_percent) / 100.0 if balance else 0.0,
                reasons=[str(exc)],
            )


__all__ = ["RealtimeTradingPipeline", "RealTimePipelineResult"]
