from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd

from analysis.market_structure import analyse_structure
from analysis.smc_patterns import analyze_market_context
from market_data.mt5_history import MT5History
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
    """Connects MT5 market data, SMC analysis, strategy evaluation, and guard rails."""

    def __init__(self, mt5_path: str | None = None):
        self.mt5_path = mt5_path
        self.history_client = MT5History(path=mt5_path or r"C:\Program Files\MetaTrader 5\terminal64.exe")

    def _fetch_timeframe(self, symbol: str, timeframe: str, bars: int = 250) -> pd.DataFrame:
        if not symbol:
            raise ValueError("Symbol must not be empty.")

        try:
            import MetaTrader5 as mt5
        except ImportError:
            return pd.DataFrame()

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=bars * 2)

        try:
            if not mt5.initialize(path=self.mt5_path or r"C:\Program Files\MetaTrader 5\terminal64.exe"):
                return pd.DataFrame()
            if not mt5.symbol_select(symbol, True):
                return pd.DataFrame()
            rates = mt5.copy_rates_range(symbol, getattr(mt5, f"TIMEFRAME_{timeframe.upper()}", None), start, end)
            if not rates:
                return pd.DataFrame()
            frame = pd.DataFrame(rates)
            if frame.empty:
                return frame
            frame["time"] = pd.to_datetime(frame["time"], unit="s", utc=True)
            frame = frame.rename(columns={"time": "timestamp", "tick_volume": "volume"})
            return frame[["timestamp", "open", "high", "low", "close", "volume"]].copy()
        except Exception:
            return pd.DataFrame()
        finally:
            try:
                mt5.shutdown()
            except Exception:
                pass

    def _build_datasets(self, symbol: str) -> dict[str, pd.DataFrame]:
        datasets: dict[str, pd.DataFrame] = {}
        for timeframe in ("M15", "H1"):
            frame = self._fetch_timeframe(symbol, timeframe, bars=250)
            if not frame.empty and len(frame) >= 20:
                datasets[timeframe] = frame
        if not datasets:
            raise ValueError(f"Unable to load live MT5 candle data for {symbol}.")
        return datasets

    def _calculate_levels(self, dataframe: pd.DataFrame, direction: str) -> tuple[float | None, float | None, float | None]:
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
        symbol = str(symbol).strip().upper()
        if not symbol:
            raise ValueError("Symbol must not be empty.")

        datasets = self._build_datasets(symbol)
        strategy = StrategyEngine().evaluate(
            symbol=symbol,
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

        guard = TradeGuard(
            max_risk_per_trade=1.0,
            max_open_trades=3,
            max_total_exposure_percent=3.0,
            max_daily_loss=5.0,
        )
        risk = calculate_account_risk(balance=balance, risk_percent=risk_percent)

        entry, stop_loss, take_profit = self._calculate_levels(execution_frame, direction)

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

        reasons = []
        reasons.extend(strategy.reasons)
        reasons.extend(qualifier.reasons)
        reasons.append(f"Risk guard: {guard_decision.reason}")

        result = RealTimePipelineResult(
            symbol=symbol,
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

        return result


__all__ = ["RealtimeTradingPipeline", "RealTimePipelineResult"]
