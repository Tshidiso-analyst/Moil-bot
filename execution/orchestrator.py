from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from execution.mt5_executor import MT5ExecutionService

from risk.models import InstrumentRisk
from risk.position_sizing import calculate_position_size
from risk.trade_guard import TradeGuard


@dataclass(frozen=True)
class ExecutionPlan:
    symbol: str
    direction: str
    status: str
    allowed: bool
    reason: str
    risk: Any | None = None
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
    request: dict[str, Any] | None = None


class TradeExecutionOrchestrator:
    """Creates a risk-guarded execution plan and sends the order only when allowed."""

    def __init__(
        self,
        mt5_service: Any,
        executor: Any | None = None,
        trade_guard: TradeGuard | None = None,
        *,
        allow_execution: bool = False,
    ):
        self.mt5_service = mt5_service
        self.executor = executor or MT5ExecutionService(mt5_module=getattr(mt5_service, "mt5", None) if hasattr(mt5_service, "mt5") else None)
        self.trade_guard = trade_guard or TradeGuard()
        self.allow_execution = allow_execution

    def build_execution_plan(
        self,
        *,
        symbol: str,
        dataframe: pd.DataFrame,
        fundamental_bias: str,
        proposed_risk_percent: float,
        daily_loss_percent: float,
        current_exposure_percent: float,
        account_balance: float,
        risk_percent: float,
    ) -> ExecutionPlan:
        if dataframe.empty:
            return ExecutionPlan(
                symbol=symbol,
                direction="neutral",
                status="blocked",
                allowed=False,
                reason="No market data available for execution.",
            )

        latest = dataframe.iloc[-1]
        previous = dataframe.iloc[-2] if len(dataframe) > 1 else latest

        bullish = float(latest["close"]) > float(previous["close"])
        bearish = float(latest["close"]) < float(previous["close"])

        if bullish:
            direction = "bullish"
        elif bearish:
            direction = "bearish"
        else:
            direction = "neutral"

        if direction == "neutral":
            return ExecutionPlan(
                symbol=symbol,
                direction="neutral",
                status="blocked",
                allowed=False,
                reason="Market direction is neutral; no trade executed.",
            )

        guard = self.trade_guard.evaluate(
            proposed_risk_percent=proposed_risk_percent,
            daily_loss_percent=daily_loss_percent,
            open_trades=0,
            confirmation=True,
            high_impact_news=False,
            structure_valid=True,
            liquidity_valid=True,
            macro_bias_valid=(fundamental_bias.lower() == direction.lower()),
            current_exposure_percent=current_exposure_percent,
        )

        if not guard.allowed:
            return ExecutionPlan(
                symbol=symbol,
                direction=direction,
                status="blocked",
                allowed=False,
                reason=guard.reason,
            )

        entry = float(latest["close"])
        stop_loss = float(min(latest["low"], previous["low"]))
        if direction == "bullish":
            take_profit = float(entry * 1.02)
        else:
            take_profit = float(entry * 0.98)

        risk_amount = float(account_balance) * (float(risk_percent) / 100.0)
        instrument = InstrumentRisk(
            symbol=symbol,
            point=0.00001,
            tick_size=0.00001,
            tick_value=1.0,
            contract_size=100000.0,
            volume_min=0.01,
            volume_max=50.0,
            volume_step=0.01,
        )
        position = calculate_position_size(
            instrument=instrument,
            direction=direction,
            entry=entry,
            stop_loss=stop_loss,
            risk_amount=risk_amount,
        )

        order = {
            "symbol": symbol,
            "entry": entry,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "volume": position.volume,
        }

        return ExecutionPlan(
            symbol=symbol,
            direction=direction,
            status="accepted",
            allowed=True,
            reason="Setup passed all validation checks.",
            risk=position,
            order=order,
        )

    def execute(
        self,
        *,
        symbol: str,
        dataframe: pd.DataFrame,
        fundamental_bias: str,
        proposed_risk_percent: float,
        daily_loss_percent: float,
        current_exposure_percent: float,
        account_balance: float,
        risk_percent: float,
        magic: int,
        comment: str = "Moil-bot",
    ) -> ExecutionResult:
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
                volume=float(plan.order.get("volume", 0.0)),
                price=float(plan.order.get("entry", 0.0)),
                status="blocked",
                reason=plan.reason,
                request=None,
            )

        if not self.allow_execution:
            return ExecutionResult(
                symbol=symbol,
                order_ticket=None,
                direction=plan.direction,
                volume=float(plan.order.get("volume", 0.0)),
                price=float(plan.order.get("entry", 0.0)),
                status="disabled",
                reason="Execution is disabled. Turn on allow_execution=True in DEMO mode.",
                request=None,
            )

        # This legacy orchestrator does not carry the reviewed-rule,
        # verified-calendar, one-trade-per-day and explicit-confirmation
        # checks required by the supported DEMO Start workflow. Keep it
        # analysis-only; the dashboard's DemoStartController is the sole
        # strategy order path and its MT5 adapter hard-blocks REAL accounts.
        return ExecutionResult(
            symbol=symbol,
            order_ticket=None,
            direction=plan.direction,
            volume=float(plan.order["volume"]),
            price=float(plan.order["entry"]),
            status="disabled",
            reason=(
                "Legacy orchestrator order submission is disabled. "
                "Use the guarded dashboard DEMO Start workflow."
            ),
            request=None,
        )

