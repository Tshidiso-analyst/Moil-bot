"""Demo-only MT5 execution pipeline with broker-aware sizing and hard safety gates.

This module intentionally refuses real/contest accounts. It is an execution
smoke-test path, not proof that the research strategy is profitable.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_FLOOR
import math
from typing import Any


@dataclass(frozen=True)
class DemoExecutionResult:
    status: str
    message: str
    symbol: str
    direction: str
    volume: float = 0.0
    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    risk_amount: float = 0.0
    estimated_loss: float = 0.0
    margin_required: float = 0.0
    ticket: int | None = None
    request: dict[str, Any] | None = None


class DemoExecutionError(RuntimeError):
    """Raised when a demo order fails a required safety check."""


class DemoExecutionPipeline:
    """Place a single explicitly confirmed order on a verified MT5 DEMO account."""

    def __init__(self, mt5_module: Any | None = None, *, magic: int = 731111):
        if mt5_module is None:
            try:
                import MetaTrader5 as mt5_module
            except ImportError as exc:  # pragma: no cover - Windows runtime
                raise DemoExecutionError(
                    "MetaTrader5 is unavailable. Run this on Windows with the MT5 package installed."
                ) from exc
        self.mt5 = mt5_module
        self.magic = int(magic)

    def execute_market_order(
        self,
        *,
        symbol: str,
        direction: str,
        stop_loss: float,
        take_profit: float,
        risk_percent: float = 1.0,
        confirmation: bool = False,
        session_confirmed: bool = False,
        no_high_impact_news_confirmed: bool = False,
        comment: str = "Moil-bot DEMO test",
    ) -> DemoExecutionResult:
        symbol = str(symbol or "").strip()
        direction = str(direction or "").strip().lower()
        if not confirmation:
            raise DemoExecutionError("Explicit demo-order confirmation is required.")
        if not session_confirmed:
            raise DemoExecutionError("Confirm that this is within your permitted trading session.")
        if not no_high_impact_news_confirmed:
            raise DemoExecutionError("Confirm that no prohibited high-impact news event is active.")
        if not symbol:
            raise DemoExecutionError("A symbol is required.")
        if direction not in {"bullish", "bearish"}:
            raise DemoExecutionError("Direction must be bullish or bearish.")
        try:
            risk_percent = float(risk_percent)
            stop_loss = float(stop_loss)
            take_profit = float(take_profit)
        except (TypeError, ValueError):
            raise DemoExecutionError("Risk, stop loss and take profit must be numeric.") from None
        if not math.isfinite(risk_percent) or not 0 < risk_percent <= 1.0:
            raise DemoExecutionError("Demo risk must be greater than 0% and no more than 1%.")
        if not all(math.isfinite(value) and value > 0 for value in (stop_loss, take_profit)):
            raise DemoExecutionError("Stop loss and take profit must be finite positive prices.")

        account = self.mt5.account_info()
        if account is None:
            raise DemoExecutionError(f"MT5 account is unavailable: {self.mt5.last_error()}")
        demo_mode = getattr(self.mt5, "ACCOUNT_TRADE_MODE_DEMO", None)
        if demo_mode is None or getattr(account, "trade_mode", None) != demo_mode:
            raise DemoExecutionError("Hard safety block: Moil-bot can place orders only on an MT5 DEMO account.")
        if not bool(getattr(account, "trade_allowed", False)):
            raise DemoExecutionError("Trading is not allowed for this MT5 account.")
        if not bool(getattr(account, "trade_expert", False)):
            raise DemoExecutionError("Expert/automated trading is disabled in the MT5 account.")
        balance = float(getattr(account, "balance", 0.0) or 0.0)
        free_margin = float(getattr(account, "margin_free", 0.0) or 0.0)
        if not math.isfinite(balance) or balance <= 0 or not math.isfinite(free_margin) or free_margin <= 0:
            raise DemoExecutionError("Account balance or free margin is invalid.")

        self._enforce_daily_limit()
        positions = self.mt5.positions_get()
        if positions is None:
            raise DemoExecutionError(f"Could not verify open positions: {self.mt5.last_error()}")
        if len(positions) > 0:
            raise DemoExecutionError("One-trade-at-a-time rule: close existing positions before a demo test.")

        if not self.mt5.symbol_select(symbol, True):
            raise DemoExecutionError(f"Could not select {symbol}: {self.mt5.last_error()}")
        info = self.mt5.symbol_info(symbol)
        tick = self.mt5.symbol_info_tick(symbol)
        if info is None or tick is None:
            raise DemoExecutionError(f"Broker quote or symbol metadata is unavailable for {symbol}.")
        disabled = getattr(self.mt5, "SYMBOL_TRADE_MODE_DISABLED", None)
        if disabled is not None and getattr(info, "trade_mode", None) == disabled:
            raise DemoExecutionError(f"Broker has disabled trading for {symbol}.")

        order_type = self.mt5.ORDER_TYPE_BUY if direction == "bullish" else self.mt5.ORDER_TYPE_SELL
        entry = float(tick.ask if direction == "bullish" else tick.bid)
        point = float(getattr(info, "point", 0.0) or 0.0)
        digits = int(getattr(info, "digits", 5))
        if not math.isfinite(entry) or entry <= 0 or point <= 0:
            raise DemoExecutionError("Broker returned an invalid quote or point size.")
        stop_gap = max(0, int(getattr(info, "trade_stops_level", 0) or 0)) * point
        if direction == "bullish":
            if not stop_loss < entry < take_profit:
                raise DemoExecutionError("For a BUY, stop loss must be below entry and take profit above entry.")
            if entry - stop_loss < stop_gap or take_profit - entry < stop_gap:
                raise DemoExecutionError("Stop loss or take profit is inside the broker's minimum stop distance.")
        else:
            if not take_profit < entry < stop_loss:
                raise DemoExecutionError("For a SELL, take profit must be below entry and stop loss above entry.")
            if stop_loss - entry < stop_gap or entry - take_profit < stop_gap:
                raise DemoExecutionError("Stop loss or take profit is inside the broker's minimum stop distance.")

        risk_amount = balance * risk_percent / 100.0
        one_lot_result = self.mt5.order_calc_profit(order_type, symbol, 1.0, entry, stop_loss)
        if one_lot_result is None:
            raise DemoExecutionError(f"Broker could not calculate stop-loss value: {self.mt5.last_error()}")
        loss_per_lot = abs(float(one_lot_result))
        if not math.isfinite(loss_per_lot) or loss_per_lot <= 0:
            raise DemoExecutionError("Broker returned an invalid loss estimate for one lot.")
        raw_volume = risk_amount / loss_per_lot
        step = Decimal(str(getattr(info, "volume_step", 0.0) or 0.0))
        minimum = Decimal(str(getattr(info, "volume_min", 0.0) or 0.0))
        maximum = Decimal(str(getattr(info, "volume_max", 0.0) or 0.0))
        if step <= 0 or minimum <= 0 or maximum < minimum:
            raise DemoExecutionError("Broker volume limits are invalid.")
        volume_units = (Decimal(str(raw_volume)) / step).to_integral_value(rounding=ROUND_FLOOR)
        volume = min(volume_units * step, (maximum / step).to_integral_value(rounding=ROUND_FLOOR) * step)
        if volume < minimum:
            raise DemoExecutionError("Safe volume is below broker minimum; trade rejected rather than exceeding the 1% risk cap.")
        volume_decimals = max(0, -step.normalize().as_tuple().exponent)
        volume_float = round(float(volume), volume_decimals)

        actual_loss_result = self.mt5.order_calc_profit(order_type, symbol, volume_float, entry, stop_loss)
        if actual_loss_result is None:
            raise DemoExecutionError("Broker could not verify the final position risk.")
        estimated_loss = abs(float(actual_loss_result))
        if not math.isfinite(estimated_loss) or estimated_loss > risk_amount + max(0.01, risk_amount * 0.001):
            raise DemoExecutionError("Final position size exceeds the configured risk budget.")

        margin = self.mt5.order_calc_margin(order_type, symbol, volume_float, entry)
        if margin is None or not math.isfinite(float(margin)) or float(margin) <= 0:
            raise DemoExecutionError("Broker could not calculate required margin.")
        margin_required = float(margin)
        if margin_required > free_margin:
            raise DemoExecutionError("Insufficient free margin for this demo order.")

        request = {
            "action": self.mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume_float,
            "type": order_type,
            "price": round(entry, digits),
            "sl": round(stop_loss, digits),
            "tp": round(take_profit, digits),
            "deviation": 20,
            "magic": self.magic,
            "comment": str(comment)[:31],
            "type_time": self.mt5.ORDER_TIME_GTC,
            "type_filling": self.mt5.ORDER_FILLING_RETURN,
        }
        checked = self.mt5.order_check(request)
        if checked is None:
            raise DemoExecutionError(f"MT5 order_check returned no result: {self.mt5.last_error()}")
        check_code = getattr(checked, "retcode", None)
        accepted_check_codes = {0, getattr(self.mt5, "TRADE_RETCODE_DONE", 10009)}
        if check_code not in accepted_check_codes:
            raise DemoExecutionError(
                f"MT5 order_check rejected the request: retcode={check_code}, "
                f"comment={getattr(checked, 'comment', '')}"
            )

        result = self.mt5.order_send(request)
        if result is None:
            raise DemoExecutionError(f"MT5 order_send returned no result: {self.mt5.last_error()}")
        accepted_codes = {
            getattr(self.mt5, "TRADE_RETCODE_DONE", 10009),
            getattr(self.mt5, "TRADE_RETCODE_DONE_PARTIAL", 10010),
        }
        if getattr(result, "retcode", None) not in accepted_codes:
            raise DemoExecutionError(
                f"MT5 rejected the demo order: retcode={getattr(result, 'retcode', None)}, "
                f"comment={getattr(result, 'comment', '')}"
            )

        ticket = int(getattr(result, "order", 0) or getattr(result, "deal", 0) or 0) or None
        return DemoExecutionResult(
            status="accepted",
            message=f"DEMO order accepted by MT5: {getattr(result, 'comment', 'done')}",
            symbol=symbol,
            direction=direction,
            volume=volume_float,
            entry_price=float(getattr(result, "price", 0.0) or entry),
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_amount=risk_amount,
            estimated_loss=estimated_loss,
            margin_required=margin_required,
            ticket=ticket,
            request=request,
        )

    def _enforce_daily_limit(self) -> None:
        history_fn = getattr(self.mt5, "history_deals_get", None)
        if not callable(history_fn):
            raise DemoExecutionError("Cannot verify the one-trade-per-day limit; broker deal history is unavailable.")
        now = datetime.now()
        start = now - timedelta(days=1)
        deals = history_fn(start, now)
        if deals is None:
            raise DemoExecutionError(f"Cannot verify today's trade history: {self.mt5.last_error()}")
        entry_code = getattr(self.mt5, "DEAL_ENTRY_IN", 0)
        for deal in deals:
            if int(getattr(deal, "magic", 0) or 0) == self.magic and int(getattr(deal, "entry", -1)) == entry_code:
                raise DemoExecutionError("One-trade-per-day rule: a Moil-bot demo entry already exists in the last 24 hours.")


__all__ = ["DemoExecutionError", "DemoExecutionPipeline", "DemoExecutionResult"]
