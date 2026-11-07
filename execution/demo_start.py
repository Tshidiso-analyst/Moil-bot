from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from strategy.rule_registry import StrategyRuleRegistry
from strategy.trade_decision import TradeDecisionEngine


@dataclass(frozen=True)
class DemoStartResult:
    symbol: str
    mode: str
    status: str
    allowed: bool
    direction: str
    reason: str
    rule_id: str | None = None
    rule_name: str | None = None
    entry: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    volume: float | None = None
    order_ticket: int | None = None
    reasons: list[str] = field(default_factory=list)
    dry_run: bool = True


class DemoStartController:
    """Explicit Start path for DEMO accounts only.

    Safety rules:
    - Never auto-starts; caller must invoke start(...).
    - Uses only human-reviewed registry rules (sources marked reviewed).
    - Does not enable live/real-money trading.
    - Default is dry-run planning; order send requires allow_execution=True
      and a confirmed demo account mode.
    """

    def __init__(
        self,
        *,
        registry: StrategyRuleRegistry | None = None,
        decision_engine: TradeDecisionEngine | None = None,
        registry_factory: Callable[[], StrategyRuleRegistry] | None = None,
    ):
        self._registry = registry
        self._registry_factory = registry_factory
        self.decision_engine = decision_engine or TradeDecisionEngine()

    def _load_registry(self) -> StrategyRuleRegistry:
        if self._registry is not None:
            return self._registry
        if self._registry_factory is not None:
            return self._registry_factory()
        return StrategyRuleRegistry()

    def reviewed_rules(self) -> list[dict[str, Any]]:
        registry = self._load_registry()
        selected = []
        for rule in registry.all_rules():
            sources = rule.get("sources") or []
            if not sources:
                continue
            if not all(bool(source.get("human_review_confirmed")) for source in sources):
                continue
            # Draft rules with reviewed evidence may guide demo research.
            # execution_enabled remains a separate hard gate for order send.
            selected.append(rule)
        return selected

    def _match_rule(self, direction: str, rules: list[dict[str, Any]]) -> dict[str, Any] | None:
        if direction not in {"bullish", "bearish"}:
            return None
        for rule in rules:
            rule_direction = str(rule.get("direction") or "either").lower()
            if rule_direction in {direction, "either"}:
                return rule
        return None

    def start(
        self,
        *,
        symbol: str,
        dataframe: pd.DataFrame,
        account_mode: str = "DEMO",
        allow_execution: bool = False,
        proposed_risk_percent: float = 0.5,
        daily_loss_percent: float = 0.0,
        open_trades: int = 0,
        high_impact_news: bool = False,
        fundamental_bias: str = "neutral",
        executor: Any | None = None,
        volume: float | None = None,
        account_balance: float | None = None,
    ) -> DemoStartResult:
        clean_symbol = str(symbol or "").strip().upper()
        if not clean_symbol:
            raise ValueError("symbol must not be empty")

        mode = str(account_mode or "").strip().upper() or "UNKNOWN"
        if mode not in {"DEMO", "PAPER"}:
            return DemoStartResult(
                symbol=clean_symbol,
                mode=mode,
                status="blocked",
                allowed=False,
                direction="neutral",
                reason=(
                    f"Start is blocked for account mode '{mode}'. "
                    "Only DEMO/PAPER accounts are allowed."
                ),
                dry_run=True,
            )

        if dataframe is None or dataframe.empty:
            return DemoStartResult(
                symbol=clean_symbol,
                mode=mode,
                status="blocked",
                allowed=False,
                direction="neutral",
                reason="No market data available for demo start.",
                dry_run=True,
            )

        rules = self.reviewed_rules()
        if not rules:
            return DemoStartResult(
                symbol=clean_symbol,
                mode=mode,
                status="blocked",
                allowed=False,
                direction="neutral",
                reason=(
                    "No human-reviewed strategy rules are available. "
                    "Add reviewed evidence and a registry draft before Start."
                ),
                dry_run=True,
            )

        assessment = self.decision_engine.assess(
            symbol=clean_symbol,
            dataframe=dataframe,
            fundamental_bias=fundamental_bias,
            proposed_risk_percent=proposed_risk_percent,
            daily_loss_percent=daily_loss_percent,
            open_trades=open_trades,
            high_impact_news=high_impact_news,
        )

        matched = self._match_rule(assessment.direction, rules)
        if matched is None:
            return DemoStartResult(
                symbol=clean_symbol,
                mode=mode,
                status="blocked",
                allowed=False,
                direction=assessment.direction,
                reason=(
                    "No reviewed rule matches the current market direction. "
                    "Start will not invent a trade."
                ),
                reasons=list(assessment.reasons),
                dry_run=True,
            )

        if not assessment.setup_valid or not assessment.confirmation:
            return DemoStartResult(
                symbol=clean_symbol,
                mode=mode,
                status="blocked",
                allowed=False,
                direction=assessment.direction,
                reason="Reviewed rule exists, but setup confirmation failed.",
                rule_id=str(matched.get("rule_id") or ""),
                rule_name=str(matched.get("name") or ""),
                reasons=list(assessment.reasons),
                dry_run=True,
            )

        planned_volume = float(volume) if volume is not None else 0.01
        if allow_execution and volume is None:
            if account_balance is None or not hasattr(executor, "calculate_volume_for_risk"):
                return DemoStartResult(
                    symbol=clean_symbol,
                    mode=mode,
                    status="blocked",
                    allowed=False,
                    direction=assessment.direction,
                    reason="Demo execution requires account balance and broker-based risk sizing.",
                    rule_id=str(matched.get("rule_id") or ""),
                    rule_name=str(matched.get("name") or ""),
                    entry=assessment.entry,
                    stop_loss=assessment.stop_loss,
                    take_profit=assessment.take_profit,
                    reasons=list(assessment.reasons),
                    dry_run=True,
                )
            try:
                planned_volume = float(executor.calculate_volume_for_risk(
                    symbol=clean_symbol,
                    direction=assessment.direction,
                    entry=float(assessment.entry),
                    stop_loss=float(assessment.stop_loss),
                    balance=float(account_balance),
                    risk_percent=min(float(proposed_risk_percent), 1.0),
                ))
            except Exception as exc:
                return DemoStartResult(
                    symbol=clean_symbol,
                    mode=mode,
                    status="blocked",
                    allowed=False,
                    direction=assessment.direction,
                    reason=f"Demo risk sizing failed: {exc}",
                    rule_id=str(matched.get("rule_id") or ""),
                    rule_name=str(matched.get("name") or ""),
                    entry=assessment.entry,
                    stop_loss=assessment.stop_loss,
                    take_profit=assessment.take_profit,
                    reasons=list(assessment.reasons),
                    dry_run=True,
                )
        dry_run = not bool(allow_execution)

        if dry_run:
            return DemoStartResult(
                symbol=clean_symbol,
                mode=mode,
                status="planned",
                allowed=True,
                direction=assessment.direction,
                reason=(
                    f"Demo plan ready using reviewed rule '{matched.get('name')}'. "
                    "Dry-run only; no order was sent."
                ),
                rule_id=str(matched.get("rule_id") or ""),
                rule_name=str(matched.get("name") or ""),
                entry=assessment.entry,
                stop_loss=assessment.stop_loss,
                take_profit=assessment.take_profit,
                volume=planned_volume,
                reasons=list(assessment.reasons),
                dry_run=True,
            )

        # Hard gate: registry execution_enabled must be true for order send.
        if not bool(matched.get("execution_enabled")):
            return DemoStartResult(
                symbol=clean_symbol,
                mode=mode,
                status="blocked",
                allowed=False,
                direction=assessment.direction,
                reason=(
                    f"Rule '{matched.get('name')}' is reviewed but execution_enabled=false. "
                    "Enable it only after explicit human approval."
                ),
                rule_id=str(matched.get("rule_id") or ""),
                rule_name=str(matched.get("name") or ""),
                entry=assessment.entry,
                stop_loss=assessment.stop_loss,
                take_profit=assessment.take_profit,
                volume=planned_volume,
                reasons=list(assessment.reasons),
                dry_run=True,
            )

        if executor is None:
            return DemoStartResult(
                symbol=clean_symbol,
                mode=mode,
                status="blocked",
                allowed=False,
                direction=assessment.direction,
                reason="allow_execution=True requires an MT5 executor instance.",
                rule_id=str(matched.get("rule_id") or ""),
                rule_name=str(matched.get("name") or ""),
                dry_run=True,
            )

        try:
            order = executor.place_market_order(
                symbol=clean_symbol,
                direction=assessment.direction,
                volume=planned_volume,
                stop_loss=assessment.stop_loss,
                take_profit=assessment.take_profit,
                comment=f"Moil demo start rule={matched.get('rule_id')}",
                max_risk_amount=(
                    float(account_balance) * min(float(proposed_risk_percent), 1.0) / 100.0
                    if account_balance is not None else None
                ),
            )
        except Exception as exc:
            return DemoStartResult(
                symbol=clean_symbol,
                mode=mode,
                status="rejected",
                allowed=False,
                direction=assessment.direction,
                reason=f"Demo order failed: {exc}",
                rule_id=str(matched.get("rule_id") or ""),
                rule_name=str(matched.get("name") or ""),
                entry=assessment.entry,
                stop_loss=assessment.stop_loss,
                take_profit=assessment.take_profit,
                volume=planned_volume,
                reasons=list(assessment.reasons),
                dry_run=False,
            )

        return DemoStartResult(
            symbol=clean_symbol,
            mode=mode,
            status="executed",
            allowed=True,
            direction=assessment.direction,
            reason=f"Demo order sent using reviewed rule '{matched.get('name')}'.",
            rule_id=str(matched.get("rule_id") or ""),
            rule_name=str(matched.get("name") or ""),
            entry=float(order.get("price") or assessment.entry or 0.0),
            stop_loss=assessment.stop_loss,
            take_profit=assessment.take_profit,
            volume=float(order.get("volume") or planned_volume),
            order_ticket=order.get("ticket"),
            reasons=list(assessment.reasons),
            dry_run=False,
        )


__all__ = ["DemoStartController", "DemoStartResult"]
