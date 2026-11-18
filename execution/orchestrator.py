"""Fail-closed XAUUSD execution planning and optional DEMO order routing.

Order execution remains disabled by default. All live portfolio state and
broker instrument metadata must be available before a plan can be approved.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import threading
from typing import Any

import pandas as pd

try:  # MetaTrader5 is optional outside the Windows trading workstation.
    import MetaTrader5 as _mt5
except ImportError:  # pragma: no cover - platform dependent
    _mt5 = None

from execution.quote_safety import require_fresh_tick
from risk.mt5_portfolio import PortfolioSnapshotError, build_mt5_portfolio_snapshot
from risk.mt5_risk import calculate_mt5_position_size
from risk.trade_guard import TradeGuard
from risk.symbols import canonicalize_symbol as canonical_xauusd_symbol


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


class MT5ExecutionService:
    """Thin broker adapter; portfolio and sizing checks belong to the orchestrator."""

    def __init__(self, mt5_module: Any | None = None, *, enabled: bool = False, magic: int = 731111):
        self.mt5 = mt5_module if mt5_module is not None else _mt5
        self.enabled = enabled is True
        if isinstance(magic, bool) or not isinstance(magic, int) or magic <= 0:
            raise ValueError("magic must be a positive integer.")
        self.magic = magic

    def is_connected(self) -> bool:
        try:
            return self.mt5 is not None and self.mt5.account_info() is not None
        except Exception:
            return False

    def open_market_order(
        self,
        *,
        symbol: str,
        direction: str,
        volume: float,
        price: float,
        stop_loss: float,
        take_profit: float,
        magic: int | None = None,
        comment: str = "Moil-bot",
    ) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("MT5 order execution is disabled by default.")
        if not self.is_connected():
            raise RuntimeError("MT5 is not connected.")
        canonical_xauusd_symbol(symbol)
        symbol = str(symbol).strip()
        if direction not in {"bullish", "bearish"}:
            raise ValueError(f"Unsupported direction: {direction}")
        numeric_prices = (price, stop_loss, take_profit)
        if not all(math.isfinite(float(value)) and float(value) > 0 for value in numeric_prices):
            raise ValueError("Order prices must be finite and greater than zero.")
        if not math.isfinite(float(volume)) or not 0 < float(volume) <= 0.02:
            raise ValueError("Order volume must be greater than zero and no more than 0.02 lots.")
        if magic is not None and (isinstance(magic, bool) or not isinstance(magic, int) or magic <= 0):
            raise ValueError("magic must be a positive integer.")
        magic_value = self.magic if magic is None else magic
        account = self.mt5.account_info()
        demo_mode = getattr(self.mt5, "ACCOUNT_TRADE_MODE_DEMO", None)
        if account is None or demo_mode is None or getattr(account, "trade_mode", None) != demo_mode:
            raise RuntimeError("Hard safety block: MT5 orders are permitted only on a verified DEMO account.")
        if not bool(getattr(account, "trade_allowed", False)) or not bool(getattr(account, "trade_expert", False)):
            raise RuntimeError("MT5 account or expert trading permission is disabled.")
        info = self.mt5.symbol_info(symbol)
        tick = self.mt5.symbol_info_tick(symbol)
        if info is None or tick is None:
            raise RuntimeError(f"Broker symbol metadata or quote is unavailable for {symbol}.")
        require_fresh_tick(tick)
        point = float(getattr(info, "point", 0.0) or 0.0)
        volume_min = float(getattr(info, "volume_min", 0.0) or 0.0)
        volume_max = float(getattr(info, "volume_max", 0.0) or 0.0)
        volume_step = float(getattr(info, "volume_step", 0.0) or 0.0)
        if not all(math.isfinite(value) and value > 0 for value in (volume_min, volume_max, volume_step)):
            raise RuntimeError("Broker volume specifications are invalid.")
        if float(volume) < volume_min or float(volume) > min(volume_max, 0.02):
            raise ValueError("Order volume is outside the broker limits or 0.02-lot ceiling.")
        step_units = float(volume) / volume_step
        if not math.isclose(step_units, round(step_units), rel_tol=0.0, abs_tol=1e-8):
            raise ValueError("Order volume does not match the broker volume step.")
        stop_gap = float(getattr(info, "trade_stops_level", 0) or 0) * point
        if not math.isfinite(point) or point <= 0:
            raise RuntimeError("Broker returned an invalid point size.")
        current_price = float(tick.ask if direction == "bullish" else tick.bid)
        if not math.isfinite(current_price) or current_price <= 0:
            raise RuntimeError("Broker returned an invalid executable quote.")
        if abs(current_price - float(price)) > max(20.0 * point, 0.0):
            raise RuntimeError("Execution quote is stale; rebuild the plan using the latest broker price.")
        disabled_mode = getattr(self.mt5, "SYMBOL_TRADE_MODE_DISABLED", None)
        if disabled_mode is not None and getattr(info, "trade_mode", None) == disabled_mode:
            raise RuntimeError(f"Broker has disabled trading for {symbol}.")
        if direction == "bullish":
            if not stop_loss < price < take_profit:
                raise ValueError("BUY stop loss/entry/take profit levels are invalid.")
            if price - stop_loss < stop_gap or take_profit - price < stop_gap:
                raise ValueError("Order levels violate the broker minimum stop distance.")
            order_type = self.mt5.ORDER_TYPE_BUY
        else:
            if not take_profit < price < stop_loss:
                raise ValueError("SELL stop loss/entry/take profit levels are invalid.")
            if stop_loss - price < stop_gap or price - take_profit < stop_gap:
                raise ValueError("Order levels violate the broker minimum stop distance.")
            order_type = self.mt5.ORDER_TYPE_SELL

        order_loss = self.mt5.order_calc_profit(order_type, symbol, float(volume), float(price), float(stop_loss))
        if order_loss is None:
            raise RuntimeError(f"Broker could not calculate order risk: {self.mt5.last_error()}")
        balance = float(getattr(account, "balance", 0.0) or 0.0)
        equity = float(getattr(account, "equity", 0.0) or 0.0)
        if not all(math.isfinite(x) and x > 0 for x in (balance, equity)):
            raise RuntimeError("MT5 account balance or equity is invalid.")
        if not math.isfinite(float(order_loss)) or float(order_loss) >= 0:
            raise RuntimeError("Broker returned a non-loss result for the proposed stop loss.")
        risk_percent = abs(float(order_loss)) / min(balance, equity) * 100.0
        if not math.isfinite(risk_percent) or risk_percent > 1.0:
            raise RuntimeError("Broker-calculated order risk exceeds the 1% per-trade limit.")
        margin = self.mt5.order_calc_margin(order_type, symbol, float(volume), float(price))
        free_margin = float(getattr(account, "margin_free", 0.0) or 0.0)
        if margin is None or not math.isfinite(float(margin)) or float(margin) <= 0:
            raise RuntimeError("Broker could not calculate required order margin.")
        if not math.isfinite(free_margin) or free_margin <= 0 or float(margin) > free_margin:
            raise RuntimeError("Insufficient or unverifiable free margin for the proposed order.")
        portfolio = build_mt5_portfolio_snapshot(self.mt5, magic=magic_value)
        if portfolio.daily_entries >= 10:
            raise RuntimeError(f"Daily entry limit reached: {portfolio.daily_entries}/10.")
        if portfolio.open_positions >= 3:
            raise RuntimeError(f"Open position limit reached: {portfolio.open_positions}/3.")
        if portfolio.daily_loss_percent >= 5.0:
            raise RuntimeError("Daily loss threshold reached: 5%.")
        if portfolio.exposure_percent + risk_percent > 3.0:
            raise RuntimeError("Order would exceed the 3% total portfolio exposure limit.")

        fill_mode = getattr(info, "filling_mode", None)
        if fill_mode is not None and int(fill_mode) & int(getattr(self.mt5, "SYMBOL_FILLING_IOC", 2)):
            filling = self.mt5.ORDER_FILLING_IOC
        elif fill_mode is not None and int(fill_mode) & int(getattr(self.mt5, "SYMBOL_FILLING_FOK", 1)):
            filling = self.mt5.ORDER_FILLING_FOK
        else:
            filling = self.mt5.ORDER_FILLING_RETURN

        request = {
            "action": self.mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(volume),
            "type": order_type,
            "price": float(price),
            "sl": float(stop_loss),
            "tp": float(take_profit),
            "deviation": 20,
            "magic": magic_value,
            "comment": str(comment)[:31],
            "type_time": self.mt5.ORDER_TIME_GTC,
            "type_filling": filling,
        }
        checked = self.mt5.order_check(request)
        if checked is None:
            raise RuntimeError(f"MT5 order_check returned no result: {self.mt5.last_error()}")
        accepted_check = {0, getattr(self.mt5, "TRADE_RETCODE_DONE", 10009)}
        if getattr(checked, "retcode", None) not in accepted_check:
            raise RuntimeError(
                f"MT5 order_check rejected request: {getattr(checked, 'retcode', None)} "
                f"{getattr(checked, 'comment', '')}"
            )
        latest = self.mt5.symbol_info_tick(symbol)
        require_fresh_tick(latest)
        latest_price = float(latest.ask if direction == "bullish" else latest.bid)
        if not math.isfinite(latest_price) or abs(latest_price - float(price)) > 20.0 * point:
            raise RuntimeError("Execution quote changed; rebuild the plan before sending.")
        latest_account = self.mt5.account_info()
        if (latest_account is None
                or getattr(latest_account, "trade_mode", None) != demo_mode
                or not bool(getattr(latest_account, "trade_allowed", False))
                or not bool(getattr(latest_account, "trade_expert", False))):
            raise RuntimeError("Account permissions or DEMO mode changed before submission.")
        latest_balance = float(getattr(latest_account, "balance", 0.0) or 0.0)
        latest_equity = float(getattr(latest_account, "equity", 0.0) or 0.0)
        if (not all(math.isfinite(x) and x > 0 for x in (latest_balance, latest_equity))
                or abs(float(order_loss)) > min(latest_balance, latest_equity) * 0.01):
            raise RuntimeError("Account equity or order risk changed before submission.")
        latest_portfolio = build_mt5_portfolio_snapshot(self.mt5, magic=magic_value)
        if (latest_portfolio.daily_entries >= 10 or latest_portfolio.open_positions >= 3
                or latest_portfolio.daily_loss_percent >= 5.0
                or latest_portfolio.exposure_percent + abs(float(order_loss)) / min(latest_balance, latest_equity) * 100.0 > 3.0):
            raise RuntimeError("Portfolio limits changed before order submission.")
        result = self.mt5.order_send(request)
        accepted = {
            getattr(self.mt5, "TRADE_RETCODE_DONE", 10009),
            getattr(self.mt5, "TRADE_RETCODE_DONE_PARTIAL", 10010),
        }
        if result is None or getattr(result, "retcode", None) not in accepted:
            raise RuntimeError(
                f"MT5 order rejected: {self.mt5.last_error() if result is None else getattr(result, 'comment', '')}"
            )
        ticket = int(getattr(result, "order", 0) or getattr(result, "deal", 0)) or None
        return {
            "ticket": ticket,
            "retcode": int(result.retcode),
            "symbol": symbol,
            "direction": direction,
            "volume": float(volume),
            "request": request,
        }


class TradeExecutionOrchestrator:
    """Build risk-checked XAUUSD plans and route only explicitly enabled DEMO orders."""

    def __init__(
        self,
        mt5_service: Any,
        executor: Any | None = None,
        trade_guard: TradeGuard | None = None,
        *,
        allow_execution: bool = False,
    ):
        self.mt5_service = mt5_service
        self.allow_execution = allow_execution is True
        mt5_module = getattr(mt5_service, "mt5", mt5_service)
        self.executor = executor or MT5ExecutionService(mt5_module=mt5_module, enabled=self.allow_execution)
        self.trade_guard = trade_guard or TradeGuard()
        self._execution_lock = threading.RLock()

    def _mt5_module(self) -> Any:
        module = getattr(self.mt5_service, "mt5", self.mt5_service)
        if module is None:
            raise PortfolioSnapshotError("MT5 service is unavailable.")
        connected = getattr(self.mt5_service, "connected", True)
        if not connected:
            raise PortfolioSnapshotError("MT5 service is not connected.")
        return module

    @staticmethod
    def _blocked(symbol: str, reason: str, direction: str = "neutral") -> ExecutionPlan:
        return ExecutionPlan(
            symbol=symbol,
            direction=direction,
            status="blocked",
            allowed=False,
            reason=reason,
        )

    def build_execution_plan(
        self,
        *,
        symbol: str,
        dataframe: pd.DataFrame,
        fundamental_bias: str,
        assessment: Any | None = None,
        proposed_risk_percent: float,
        daily_loss_percent: float,
        current_exposure_percent: float,
        account_balance: float,
        risk_percent: float,
        magic: int = 731111,
    ) -> ExecutionPlan:
        del current_exposure_percent, account_balance, daily_loss_percent  # broker snapshot is authoritative
        try:
            canonical_xauusd_symbol(symbol)
            module = self._mt5_module()
            snapshot = build_mt5_portfolio_snapshot(module, magic=magic)
        except (ValueError, PortfolioSnapshotError) as exc:
            return self._blocked(symbol, str(exc))

        if assessment is None:
            return self._blocked(symbol, "A validated TradeAssessment is required; candle direction alone cannot authorize a trade.")
        try:
            assessment_symbol = canonical_xauusd_symbol(getattr(assessment, "symbol", ""))
            direction = str(getattr(assessment, "direction", "")).strip().lower()
            if assessment_symbol != "XAUUSD" or direction not in {"bullish", "bearish"}:
                return self._blocked(symbol, "Trade assessment symbol or direction is invalid.")
            boolean_fields = ("setup_valid", "confirmation", "structure_valid", "liquidity_valid", "high_impact_news", "macro_bias_valid")
            if any(not isinstance(getattr(assessment, field, None), bool) for field in boolean_fields):
                return self._blocked(symbol, "Strategy assessment is missing explicit boolean safety checks.", direction)
            if not assessment.setup_valid or not assessment.confirmation:
                return self._blocked(symbol, "Strategy assessment is not confirmed.", direction)
            structure_valid = assessment.structure_valid
            liquidity_valid = assessment.liquidity_valid
            high_impact_news = assessment.high_impact_news
            assessment_macro_valid = assessment.macro_bias_valid
            macro_input = str(fundamental_bias or "").strip().lower()
            macro_bias_valid = assessment_macro_valid and macro_input in {"neutral", direction}

            if not isinstance(dataframe, pd.DataFrame) or dataframe.empty:
                return self._blocked(symbol, "No market data available for execution.", direction)
            required = {"close", "low", "high"}
            if not required.issubset(dataframe.columns):
                return self._blocked(symbol, "Market data is missing required OHLC columns.", direction)
            latest = dataframe.iloc[-1]
            previous = dataframe.iloc[-2] if len(dataframe) > 1 else latest
            values = [float(latest[name]) for name in ("close", "low", "high")]
            values += [float(previous[name]) for name in ("close", "low", "high")]
            if not all(math.isfinite(value) and value > 0 for value in values):
                return self._blocked(symbol, "Market data contains invalid prices.", direction)

            risk_pct = float(proposed_risk_percent)
            sizing_pct = float(risk_percent)
            loss_pct = float(snapshot.daily_loss_percent)
            if not all(math.isfinite(x) for x in (risk_pct, sizing_pct, loss_pct)):
                return self._blocked(symbol, "Risk inputs must be finite numbers.", direction)
            if not 0 < risk_pct <= 1.0 or not 0 < sizing_pct <= 1.0:
                return self._blocked(symbol, "Maximum risk per trade is 1%.", direction)
            if loss_pct < 0:
                return self._blocked(symbol, "Daily loss percentage cannot be negative.", direction)

            guard = self.trade_guard.evaluate(
                proposed_risk_percent=min(risk_pct, sizing_pct),
                daily_loss_percent=loss_pct,
                open_trades=snapshot.open_positions,
                current_daily_entries=snapshot.daily_entries,
                confirmation=True,
                high_impact_news=high_impact_news,
                structure_valid=structure_valid,
                liquidity_valid=liquidity_valid,
                macro_bias_valid=macro_bias_valid,
                current_exposure_percent=snapshot.exposure_percent,
            )
            if not guard.allowed:
                return self._blocked(symbol, guard.reason, direction)

            if not module.symbol_select(symbol, True):
                return self._blocked(symbol, f"Broker could not select {symbol}: {module.last_error()}", direction)
            info = module.symbol_info(symbol)
            tick = module.symbol_info_tick(symbol)
            if info is None or tick is None:
                return self._blocked(symbol, f"Broker metadata or quote unavailable for {symbol}.", direction)
            require_fresh_tick(tick)

            entry = float(tick.ask if direction == "bullish" else tick.bid)
            stop_loss = float(getattr(assessment, "stop_loss", 0.0) or 0.0)
            if not all(math.isfinite(x) and x > 0 for x in (entry, stop_loss)):
                return self._blocked(symbol, "Broker quote or stop level is invalid.", direction)
            take_profit = entry + (entry - stop_loss) * 2.0 if direction == "bullish" else entry - (stop_loss - entry) * 2.0

            account = module.account_info()
            if account is None:
                return self._blocked(symbol, "MT5 account unavailable for equity risk verification.", direction)
            balance = float(getattr(account, "balance", 0.0) or 0.0)
            equity = float(getattr(account, "equity", 0.0) or 0.0)
            if not all(math.isfinite(x) and x > 0 for x in (balance, equity)):
                return self._blocked(symbol, "MT5 balance or equity is invalid.", direction)
            risk_amount = min(snapshot.balance, balance, equity) * min(risk_pct, sizing_pct) / 100.0
            position = calculate_mt5_position_size(
                module,
                symbol=symbol,
                direction=direction,
                entry=entry,
                stop_loss=stop_loss,
                risk_amount=risk_amount,
                max_volume=self.trade_guard.limits.max_position_volume,
            )
            order = {
                "symbol": str(getattr(info, "name", symbol)),
                "entry": entry,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "volume": position.volume,
            }
            return ExecutionPlan(
                symbol=str(getattr(info, "name", symbol)),
                direction=direction,
                status="accepted",
                allowed=True,
                reason="Broker metadata, portfolio snapshot and risk checks passed.",
                risk=position,
                order=order,
            )
        except Exception as exc:
            return self._blocked(symbol, f"Execution plan rejected: {exc}", locals().get("direction", "neutral"))

    def execute(
        self,
        *,
        symbol: str,
        dataframe: pd.DataFrame,
        fundamental_bias: str,
        assessment: Any | None = None,
        proposed_risk_percent: float,
        daily_loss_percent: float,
        current_exposure_percent: float,
        account_balance: float,
        risk_percent: float,
        magic: int,
        comment: str = "Moil-bot",
    ) -> ExecutionResult:
        with self._execution_lock:
            plan = self.build_execution_plan(
                symbol=symbol,
                dataframe=dataframe,
                fundamental_bias=fundamental_bias,
                assessment=assessment,
                proposed_risk_percent=proposed_risk_percent,
                daily_loss_percent=daily_loss_percent,
                current_exposure_percent=current_exposure_percent,
                account_balance=account_balance,
                risk_percent=risk_percent,
                magic=magic,
            )
            if not plan.allowed:
                return ExecutionResult(symbol, None, plan.direction, 0.0, 0.0, "blocked", plan.reason)
            if not self.allow_execution:
                return ExecutionResult(
                    plan.symbol, None, plan.direction, float(plan.order["volume"]),
                    float(plan.order["entry"]), "disabled",
                    "Execution is disabled by default. Explicit DEMO-only enablement is required.",
                )

            try:
                module = self._mt5_module()
                account = module.account_info()
                demo_mode = getattr(module, "ACCOUNT_TRADE_MODE_DEMO", None)
                if account is None or demo_mode is None or getattr(account, "trade_mode", None) != demo_mode:
                    raise RuntimeError("Hard safety block: order routing is permitted only on a verified MT5 DEMO account.")
                if not bool(getattr(account, "trade_allowed", False)) or not bool(getattr(account, "trade_expert", False)):
                    raise RuntimeError("MT5 account or expert trading permission is disabled.")
                result = self.executor.open_market_order(
                    symbol=plan.order["symbol"],
                    direction=plan.direction,
                    volume=float(plan.order["volume"]),
                    price=float(plan.order["entry"]),
                    stop_loss=float(plan.order["stop_loss"]),
                    take_profit=float(plan.order["take_profit"]),
                    magic=magic,
                    comment=comment,
                )
                return ExecutionResult(
                    plan.symbol, result.get("ticket"), plan.direction,
                    float(plan.order["volume"]), float(plan.order["entry"]),
                    "accepted", ("DEMO order accepted by MT5." if result.get("ticket") else "MT5 accepted the DEMO order but returned no ticket; reconcile the account history before any retry."), result.get("request"),
                )
            except Exception as exc:
                return ExecutionResult(
                    plan.symbol, None, plan.direction, float(plan.order["volume"]),
                    float(plan.order["entry"]), "rejected", str(exc),
                )


__all__ = [
    "ExecutionPlan",
    "ExecutionResult",
    "MT5ExecutionService",
    "TradeExecutionOrchestrator",
    "canonical_xauusd_symbol",
]
