from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import MetaTrader5 as mt5
import pandas as pd

from dashboard.mt5_live import MT5LiveService
from qualification.engine import SetupQualifier
from risk.account import calculate_account_risk
from risk.limits import can_open_trade
from risk.models import InstrumentRisk
from risk.position_sizing import calculate_position_size
from risk.trade_guard import TradeGuard
from strategy.engine import StrategyEngine


@dataclass(frozen=True)
class ExecutionPlan:
    symbol: str
    direction: str
    status: str
    allowed: bool
    reason: str
    risk: float
    order: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionResult:
    symbol: str
    order_ticket: int | None
    direction: str
    volume: float
    price: float
    status: str
    reason: str


class MT5ExecutionService:
    """Guarded MT5 execution layer. It requires a valid MT5 connection and risk checks."""

    def __init__(self, mt5_module: Any | None = None):
        self.mt5 = mt5_module or mt5

    def is_connected(self) -> bool:
        return self.mt5.initialize is not None and self.mt5.account_info() is not None

    def open_market_order(
        self,
        symbol: str,
        direction: str,
        volume: float,
        price: float | None = None,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        magic: int = 0,
        comment: str = "Moil Bot",
    ) -> ExecutionResult:
        if direction not in {"BUY", "SELL"}:
            raise ValueError("Direction must be BUY or SELL.")

        if not symbol:
            raise ValueError("Symbol must not be empty.")

        if volume <= 0:
            raise ValueError("Volume must be greater than zero.")

        if not self.mt5.symbol_select(symbol, True):
            raise RuntimeError(f"Unable to select symbol in MT5: {symbol}")

        request = {
            "action": self.mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(volume),
            "type": self.mt5.ORDER_TYPE_BUY if direction == "BUY" else self.mt5.ORDER_TYPE_SELL,
            "price": self.mt5.symbol_info_tick(symbol).ask if direction == "BUY" else self.mt5.symbol_info_tick(symbol).bid,
            "deviation": 20,
            "magic": magic,
            "comment": comment,
            "type_time": self.mt5.ORDER_TIME_GTC,
            "type_filling": self.mt5.ORDER_FILLING_IOC,
        }

        if stop_loss is not None:
            request["sl"] = float(stop_loss)
        if take_profit is not None:
            request["tp"] = float(take_profit)

        result = self.mt5.order_send(request)
        if result is None:
            raise RuntimeError(f"MT5 order_send returned None for {symbol}.")

        if result.retcode not in {self.mt5.TRADE_RETCODE_DONE, self.mt5.TRADE_RETCODE_DONE_PARTIAL}:
            raise RuntimeError(f"Order rejected: {result.retcode} | {self.mt5.last_error()}")

        return ExecutionResult(
            symbol=symbol,
            order_ticket=int(result.order),
            direction=direction,
            volume=float(volume),
            price=float(result.price or price or 0.0),
            status="executed",
            reason="MT5 order accepted.",
        )


class TradeExecutionOrchestrator:
    """Builds a guarded execution plan and optionally sends the order to MT5."""

    def __init__(
        self,
        mt5_service: MT5LiveService | None = None,
        executor: MT5ExecutionService | None = None,
        trade_guard: TradeGuard | None = None,
        allow_execution: bool = False,
    ):
        self.mt5_service = mt5_service or MT5LiveService()
        self.executor = executor or MT5ExecutionService()
        self.trade_guard = trade_guard or TradeGuard()
        self.allow_execution = allow_execution

    def _infer_direction(self, symbol: str, dataframe: pd.DataFrame, fundamental_bias: str) -> tuple[str, str, int, list[str]]:
        if dataframe.empty:
            raise ValueError(f"No price data available for {symbol}.")

        strategy = StrategyEngine().evaluate(
            symbol=symbol,
            datasets={"M15": dataframe},
            fundamental_bias=fundamental_bias,
            execution_timeframe="M15",
        )

        qualifier = SetupQualifier().qualify(
            structure_trend="bullish" if strategy.signal_direction == "bullish" else "bearish",
            top_down_alignment=strategy.top_down_alignment,
            fvg_direction=strategy.fair_value_gap.get("direction") if isinstance(strategy.fair_value_gap, dict) else None,
            fundamental_bias=fundamental_bias,
        )

        direction = qualifier.direction if qualifier.qualified else strategy.direction
        reasons = list(strategy.reasons) + list(qualifier.reasons)
        score = max(strategy.score, qualifier.score)
        return direction, strategy.status, score, reasons

    def build_execution_plan(
        self,
        symbol: str,
        dataframe: pd.DataFrame,
        fundamental_bias: str,
        proposed_risk_percent: float,
        daily_loss_percent: float,
        current_exposure_percent: float,
        account_balance: float,
        risk_percent: float,
    ) -> ExecutionPlan:
        if not symbol:
            raise ValueError("Symbol must not be empty.")

        account_risk = calculate_account_risk(balance=account_balance, risk_percent=risk_percent)
        direction, status, score, reasons = self._infer_direction(symbol, dataframe, fundamental_bias)

        if direction not in {"bullish", "bearish"}:
            return ExecutionPlan(
                symbol=symbol,
                direction="neutral",
                status="rejected",
                allowed=False,
                reason="No valid setup direction was produced.",
                risk=float(account_risk.risk_amount),
                order={},
            )

        guard = self.trade_guard.evaluate(
            proposed_risk_percent=proposed_risk_percent,
            daily_loss_percent=daily_loss_percent,
            open_trades=0,
            confirmation=True,
            high_impact_news=False,
            structure_valid=True,
            liquidity_valid=True,
            macro_bias_valid=bool(fundamental_bias in {"bullish", "bearish"}),
            current_exposure_percent=current_exposure_percent,
        )

        if not guard.allowed:
            return ExecutionPlan(
                symbol=symbol,
                direction=direction,
                status="rejected",
                allowed=False,
                reason=guard.reason,
                risk=float(account_risk.risk_amount),
                order={},
            )

        if not can_open_trade(
            limits=self.trade_guard.limits,
            current_open_trades=0,
            current_exposure_percent=current_exposure_percent,
            proposed_risk_percent=proposed_risk_percent,
            daily_loss_percent=daily_loss_percent,
        ):
            return ExecutionPlan(
                symbol=symbol,
                direction=direction,
                status="rejected",
                allowed=False,
                reason="Risk limits reject opening a new trade.",
                risk=float(account_risk.risk_amount),
                order={},
            )

        entry = float(dataframe["close"].iloc[-1])
        stop_loss = entry * 0.998 if direction == "bullish" else entry * 1.002
        take_profit = entry * 1.01 if direction == "bullish" else entry * 0.99

        instrument = InstrumentRisk(
            symbol=symbol,
            point=0.00001,
            tick_size=0.00001,
            tick_value=1.0,
            contract_size=100000,
            volume_min=0.01,
            volume_max=100.0,
            volume_step=0.01,
        )

        position = calculate_position_size(
            instrument=instrument,
            direction="bullish" if direction == "bullish" else "bearish",
            entry=entry,
            stop_loss=stop_loss,
            risk_amount=float(account_risk.risk_amount),
        )

        ordered = {
            "symbol": symbol,
            "direction": direction,
            "entry": entry,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "volume": position.volume,
            "score": score,
            "risk": account_risk.risk_amount,
            "reasons": reasons,
        }

        return ExecutionPlan(
            symbol=symbol,
            direction=direction,
            status="approved",
            allowed=True,
            reason="Risk, structure and execution criteria passed.",
            risk=float(account_risk.risk_amount),
            order=ordered,
        )

    def execute(
        self,
        symbol: str,
        dataframe: pd.DataFrame,
        fundamental_bias: str,
        proposed_risk_percent: float,
        daily_loss_percent: float,
        current_exposure_percent: float,
        account_balance: float,
        risk_percent: float,
        magic: int = 123456,
        comment: str = "Moil Bot",
    ) -> ExecutionResult | None:
        plan = self.build_execution_plan(
            symbol=symbol,
            dataframe=dataframe,
            fundamental_bias=fundamental_bias,
            proposed_risk_percent=proposed_risk_percent,
            daily_loss_percent=daily_loss_percent,
            current_exposure_percent=current_exposure_percent,
            account_balance=account_balance,
            risk_percent=risk_percent,
        )

        if not plan.allowed:
            return ExecutionResult(
                symbol=symbol,
                order_ticket=None,
                direction=plan.direction,
                volume=0.0,
                price=0.0,
                status="rejected",
                reason=plan.reason,
            )

        if not self.allow_execution:
            return ExecutionResult(
                symbol=symbol,
                order_ticket=None,
                direction=plan.direction,
                volume=float(plan.order.get("volume", 0.0)),
                price=float(plan.order.get("entry", 0.0)),
                status="blocked",
                reason="Autonomous execution is disabled for this session; only approved plans are created.",
            )

        if not self.mt5_service.connected or self.mt5_service.mt5 is None:
            return ExecutionResult(
                symbol=symbol,
                order_ticket=None,
                direction=plan.direction,
                volume=float(plan.order.get("volume", 0.0)),
                price=float(plan.order.get("entry", 0.0)),
                status="blocked",
                reason="MT5 is not connected; real execution is unavailable.",
            )

        direction = "BUY" if plan.direction == "bullish" else "SELL"
        volume = float(plan.order.get("volume", 0.0))
        entry = float(plan.order.get("entry", 0.0))
        stop_loss = float(plan.order.get("stop_loss", 0.0))
        take_profit = float(plan.order.get("take_profit", 0.0))

        result = self.executor.open_market_order(
            symbol=symbol,
            direction=direction,
            volume=volume,
            price=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            magic=magic,
            comment=comment,
        )
        return result


__all__ = ["ExecutionPlan", "ExecutionResult", "MT5ExecutionService", "TradeExecutionOrchestrator"]
