from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from math import isfinite
from typing import Any, Callable, Iterable

import pandas as pd

from analysis.smc_patterns import analyze_market_context, find_liquidity_sweeps
from fundamentals.event_risk import EconomicEvent

from strategy.rule_registry import StrategyRuleRegistry
from strategy.trade_decision import TradeDecisionEngine
from strategy.entry_confirmation import EntryConfirmationEvaluator
from risk.trade_guard import TradeGuard


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
    - Default is dry-run planning; order send requires allow_execution=True,
      an explicit confirmation, and a verified demo account mode.
    """

    def __init__(
        self,
        *,
        registry: StrategyRuleRegistry | None = None,
        decision_engine: TradeDecisionEngine | None = None,
        registry_factory: Callable[[], StrategyRuleRegistry] | None = None,
        entry_confirmation_evaluator: EntryConfirmationEvaluator | None = None,
    ):
        self._registry = registry
        self._registry_factory = registry_factory
        self.entry_confirmation_evaluator = entry_confirmation_evaluator or EntryConfirmationEvaluator()
        self.decision_engine = decision_engine or TradeDecisionEngine(
            risk_guard=TradeGuard(
                max_risk_per_trade=1.0,
                max_open_trades=1,
                max_total_exposure_percent=1.0,
                max_daily_loss=1.0,
            )
        )

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
        explicit_confirmation: bool = False,
        proposed_risk_percent: float = 0.5,
        daily_loss_percent: float | None = None,
        open_trades: int | None = None,
        daily_trade_count: int | None = None,
        high_impact_news: bool = False,
        calendar_verified: bool = False,
        fundamental_bias: str = "neutral",
        macro_bias_verified: bool = False,
        executor: Any | None = None,
        volume: float | None = None,
        account_balance: float | None = None,
        events: Iterable[EconomicEvent] = (),
        assessed_at: datetime | None = None,
    ) -> DemoStartResult:
        clean_symbol = str(symbol or "").strip().upper()
        if not clean_symbol:
            raise ValueError("symbol must not be empty")

        mode = str(account_mode or "").strip().upper() or "UNKNOWN"
        if mode == "PAPER" and allow_execution:
            return DemoStartResult(
                symbol=clean_symbol,
                mode=mode,
                status="blocked",
                allowed=False,
                direction="neutral",
                reason="Broker order execution requires a verified MT5 DEMO account; PAPER is simulation-only.",
                dry_run=True,
            )

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

        if allow_execution and explicit_confirmation is not True:
            return DemoStartResult(
                symbol=clean_symbol,
                mode=mode,
                status="blocked",
                allowed=False,
                direction="neutral",
                reason="Explicit DEMO order confirmation is required; no order was sent.",
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

        if allow_execution:
            if calendar_verified is not True:
                return DemoStartResult(
                    symbol=clean_symbol, mode=mode, status="blocked", allowed=False,
                    direction="neutral",
                    reason="Economic calendar is not verified and fresh; DEMO execution is blocked.",
                    dry_run=True,
                )
            if high_impact_news is not False:
                return DemoStartResult(
                    symbol=clean_symbol, mode=mode, status="blocked", allowed=False,
                    direction="neutral",
                    reason="High-impact economic event blackout is active; DEMO execution is blocked.",
                    dry_run=True,
                )
            risk_facts = {
                "daily_loss_percent": daily_loss_percent,
                "open_trades": open_trades,
                "daily_trade_count": daily_trade_count,
            }
            if any(value is None for value in risk_facts.values()):
                missing = ", ".join(name for name, value in risk_facts.items() if value is None)
                return DemoStartResult(
                    symbol=clean_symbol, mode=mode, status="blocked", allowed=False,
                    direction="neutral",
                    reason=f"MT5 risk history is incomplete ({missing}); DEMO execution is blocked.",
                    dry_run=True,
                )
            try:
                loss_value = float(daily_loss_percent)
                open_value = int(open_trades)
                entries_value = int(daily_trade_count)
                if (
                    isinstance(daily_loss_percent, bool)
                    or not isfinite(loss_value)
                    or loss_value < 0
                    or isinstance(open_trades, bool)
                    or open_value != open_trades
                    or open_value < 0
                    or isinstance(daily_trade_count, bool)
                    or entries_value != daily_trade_count
                    or entries_value < 0
                ):
                    raise ValueError
            except (TypeError, ValueError, OverflowError):
                return DemoStartResult(
                    symbol=clean_symbol, mode=mode, status="blocked", allowed=False,
                    direction="neutral",
                    reason="MT5 risk history contains invalid values; DEMO execution is blocked.",
                    dry_run=True,
                )
            if entries_value >= 1:
                return DemoStartResult(
                    symbol=clean_symbol, mode=mode, status="blocked", allowed=False,
                    direction="neutral",
                    reason="One-trade-per-day limit reached. No additional demo order will be sent today.",
                    dry_run=True,
                )
            if open_value >= 1:
                return DemoStartResult(
                    symbol=clean_symbol, mode=mode, status="blocked", allowed=False,
                    direction="neutral",
                    reason="An MT5 position is already open. DEMO execution is blocked.",
                    dry_run=True,
                )
            if loss_value >= 1.0:
                return DemoStartResult(
                    symbol=clean_symbol, mode=mode, status="blocked", allowed=False,
                    direction="neutral",
                    reason="The 1% daily loss limit has been reached; DEMO execution is blocked.",
                    dry_run=True,
                )

        if allow_execution:
            try:
                balance_value = float(account_balance)
                risk_value = float(proposed_risk_percent)
                if (
                    isinstance(account_balance, bool)
                    or not isfinite(balance_value)
                    or balance_value <= 0
                    or isinstance(proposed_risk_percent, bool)
                    or not isfinite(risk_value)
                    or not (0 < risk_value <= 1.0)
                ):
                    raise ValueError
            except (TypeError, ValueError, OverflowError):
                return DemoStartResult(
                    symbol=clean_symbol,
                    mode=mode,
                    status="blocked",
                    allowed=False,
                    direction="neutral",
                    reason=(
                        "DEMO execution requires a finite positive account balance "
                        "and a finite risk setting greater than 0% and no more than 1%."
                    ),
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

        # MT5 history includes the currently forming candle. Use only completed
        # candles for decision and entry-confirmation evidence.
        analysis_frame = dataframe.iloc[:-1].copy() if len(dataframe) > 2 else dataframe.copy()
        assessment = self.decision_engine.assess(
            symbol=clean_symbol,
            dataframe=analysis_frame,
            fundamental_bias=fundamental_bias,
            proposed_risk_percent=proposed_risk_percent,
            daily_loss_percent=float(daily_loss_percent) if daily_loss_percent is not None else 0.0,
            open_trades=int(open_trades) if open_trades is not None else 0,
            high_impact_news=high_impact_news,
        )

        if allow_execution and assessment.direction not in {"bullish", "bearish"}:
            return DemoStartResult(
                symbol=clean_symbol,
                mode=mode,
                status="blocked",
                allowed=False,
                direction="neutral",
                reason="No directional market assessment is available; no DEMO order was sent.",
                reasons=list(assessment.reasons),
                dry_run=True,
            )

        if allow_execution:
            context = analyze_market_context(analysis_frame)
            # The MT5 dataframe includes its current forming candle; the sweep
            # detector intentionally excludes that final row.
            completed_sweeps = find_liquidity_sweeps(dataframe)
            latest_sweep = (
                completed_sweeps[-1]
                if completed_sweeps and completed_sweeps[-1].index >= len(dataframe) - 3
                else None
            )
            sweep_reversal_direction = (
                "bullish" if latest_sweep and latest_sweep.direction == "sell_side"
                else "bearish" if latest_sweep and latest_sweep.direction == "buy_side"
                else "neutral"
            )
            latest_bos = (
                context.bos[-1]
                if context.bos and context.bos[-1]["index"] >= len(analysis_frame) - 2
                else {}
            )
            fvg_retracement_confirmed = False
            if not analysis_frame.empty:
                last_candle = analysis_frame.iloc[-1]
                for gap in reversed(context.fair_value_gaps):
                    if gap.direction != assessment.direction or gap.index >= len(analysis_frame) - 1:
                        continue
                    overlaps_gap = (
                        float(last_candle["low"]) <= gap.upper
                        and float(last_candle["high"]) >= gap.lower
                    )
                    closes_with_direction = (
                        float(last_candle["close"]) > float(last_candle["open"])
                        and float(last_candle["close"]) >= gap.lower
                        if assessment.direction == "bullish"
                        else float(last_candle["close"]) < float(last_candle["open"])
                        and float(last_candle["close"]) <= gap.upper
                    )
                    if overlaps_gap and closes_with_direction:
                        fvg_retracement_confirmed = True
                        break

            confirmation = self.entry_confirmation_evaluator.evaluate(
                symbol=clean_symbol,
                direction=assessment.direction,
                assessed_at=assessed_at or datetime.now(timezone.utc),
                event_calendar_verified=calendar_verified,
                events=events,
                macro_bias_valid=(
                    macro_bias_verified is True
                    and fundamental_bias in {"bullish", "bearish"}
                    and fundamental_bias == assessment.direction
                ),
                daily_trade_count=int(daily_trade_count or 0),
                risk_percent=proposed_risk_percent,
                liquidity_sweep_confirmed=latest_sweep is not None,
                sweep_reversal_direction=sweep_reversal_direction,
                bos_direction=str(latest_bos.get("direction") or "neutral"),
                bos_body_close_confirmed=bool(latest_bos),
                fvg_retracement_confirmed=fvg_retracement_confirmed,
            )
            if not confirmation.qualified:
                return DemoStartResult(
                    symbol=clean_symbol,
                    mode=mode,
                    status="blocked",
                    allowed=False,
                    direction=assessment.direction,
                    reason="Strict NYSE entry confirmation failed; no DEMO order was sent.",
                    reasons=list(assessment.reasons) + list(confirmation.reasons),
                    dry_run=True,
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

        # Demo forward-testing has its own approval flag. This is deliberately
        # separate from execution_enabled, which remains false for real money.
        if not bool(matched.get("demo_execution_enabled")):
            return DemoStartResult(
                symbol=clean_symbol,
                mode=mode,
                status="blocked",
                allowed=False,
                direction=assessment.direction,
                reason=(
                    f"Rule '{matched.get('name')}' has not been approved for DEMO forward-testing. "
                    "Use the explicit demo approval control first."
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
