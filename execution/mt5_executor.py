"""Execution helpers for MetaTrader 5 trading actions."""

from __future__ import annotations

from typing import Any
import math

from execution.authorization import require_strategy_authorization
from execution.quote_safety import require_fresh_tick
from risk.mt5_portfolio import build_mt5_portfolio_snapshot
from risk.symbols import canonicalize_symbol


class MT5ExecutionService:
    """Execute market orders through MetaTrader 5 after validation."""

    def __init__(self, mt5_module: Any | None = None, *, enabled: bool = False, magic: int = 731111):
        self.mt5 = mt5_module
        self.connected = False
        self.enabled = enabled is True
        if isinstance(magic, bool) or not isinstance(magic, int) or magic <= 0:
            raise ValueError("magic must be a positive integer.")
        self.magic = magic

    def connect(
        self,
        login: int,
        password: str,
        server: str,
        *,
        path: str | None = None,
    ) -> dict[str, Any]:
        if self.mt5 is None:
            try:
                import MetaTrader5 as mt5
            except ImportError as exc:  # pragma: no cover - environment dependent
                return {
                    "connected": False,
                    "message": "MetaTrader5 package is unavailable.",
                    "error": str(exc),
                }
            self.mt5 = mt5
        mt5 = self.mt5

        try:
            mt5.shutdown()
        except Exception:
            pass

        if path is not None:
            initialized = mt5.initialize(
                login=int(login),
                password=str(password),
                server=str(server),
                path=str(path),
            )
        else:
            initialized = mt5.initialize(
                login=int(login),
                password=str(password),
                server=str(server),
            )

        if not initialized:
            self.connected = False
            return {
                "connected": False,
                "message": "MT5 initialization failed.",
                "error": mt5.last_error(),
            }

        self.connected = True
        return {
            "connected": True,
            "message": "MT5 connected successfully.",
        }

    def _require_connection(self):
        if not self.connected or self.mt5 is None:
            raise RuntimeError("MT5 is not connected.")

    def _symbol_ready(self, symbol: str) -> bool:
        if self.mt5 is None:
            return False

        info = self.mt5.symbol_info(str(symbol).strip())
        if info is None:
            return False
        if not info.visible:
            self.mt5.symbol_select(str(symbol).strip(), True)
        return True

    def place_market_order(
        self,
        symbol: str,
        direction: str,
        volume: float,
        *,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        comment: str = "Moil-bot",
        magic: int = 731111,
        assessment: Any | None = None,
    ) -> dict[str, Any]:
        self._require_connection()
        if not self.enabled:
            raise RuntimeError("MT5 order execution is disabled by default.")
        require_strategy_authorization(assessment, symbol=symbol, direction=str(direction).lower())

        if isinstance(magic, bool) or not isinstance(magic, int) or magic <= 0:
            raise ValueError("magic must be a positive integer.")
        symbol = str(symbol).strip()
        canonicalize_symbol(symbol)
        if not symbol:
            raise ValueError("symbol must not be empty.")

        direction = str(direction).strip().lower()
        if direction not in {"buy", "sell", "bullish", "bearish"}:
            raise ValueError("direction must be bullish/bearish or buy/sell.")

        if not math.isfinite(float(volume)) or not 0 < float(volume) <= 0.02:
            raise ValueError("volume must be greater than zero and no more than 0.02 lots.")
        if stop_loss is None or take_profit is None:
            raise ValueError("A protective stop loss and take profit are required.")
        account = self.mt5.account_info()
        demo_mode = getattr(self.mt5, "ACCOUNT_TRADE_MODE_DEMO", None)
        if account is None or demo_mode is None or getattr(account, "trade_mode", None) != demo_mode:
            raise RuntimeError("Hard safety block: orders are permitted only on a verified DEMO account.")
        if not bool(getattr(account, "trade_allowed", False)) or not bool(getattr(account, "trade_expert", False)):
            raise RuntimeError("MT5 account or expert trading permission is disabled.")

        if not self._symbol_ready(symbol):
            raise RuntimeError(f"Symbol {symbol} is not available in MT5.")

        mt5_direction = self.mt5.ORDER_TYPE_BUY if direction in {"buy", "bullish"} else self.mt5.ORDER_TYPE_SELL

        tick = self.mt5.symbol_info_tick(symbol)
        if tick is None:
            raise RuntimeError(f"No live tick available for {symbol}.")
        require_fresh_tick(tick)

        price = float(tick.ask if mt5_direction == self.mt5.ORDER_TYPE_BUY else tick.bid)
        if not math.isfinite(price) or price <= 0:
            raise RuntimeError(f"Invalid broker quote for {symbol}.")
        stop_loss = float(stop_loss)
        take_profit = float(take_profit)
        info = self.mt5.symbol_info(symbol)
        if info is None:
            raise RuntimeError(f"Broker metadata unavailable for {symbol}.")
        disabled_mode = getattr(self.mt5, "SYMBOL_TRADE_MODE_DISABLED", None)
        if disabled_mode is not None and getattr(info, "trade_mode", None) == disabled_mode:
            raise RuntimeError(f"Broker has disabled trading for {symbol}.")
        volume_min = float(getattr(info, "volume_min", 0.0) or 0.0)
        volume_max = float(getattr(info, "volume_max", 0.0) or 0.0)
        volume_step = float(getattr(info, "volume_step", 0.0) or 0.0)
        if not all(math.isfinite(value) and value > 0 for value in (volume_min, volume_max, volume_step)):
            raise RuntimeError("Broker volume specifications are invalid.")
        if float(volume) < volume_min or float(volume) > min(volume_max, 0.02):
            raise ValueError("Volume is outside broker limits or the 0.02-lot ceiling.")
        if not math.isclose(float(volume) / volume_step, round(float(volume) / volume_step), rel_tol=0.0, abs_tol=1e-8):
            raise ValueError("Volume does not match the broker volume step.")
        point = float(getattr(info, "point", 0.0) or 0.0)
        if not math.isfinite(point) or point <= 0:
            raise RuntimeError("Broker point size is invalid.")
        stop_gap = float(getattr(info, "trade_stops_level", 0) or 0) * point
        if not all(math.isfinite(value) and value > 0 for value in (stop_loss, take_profit)):
            raise ValueError("Stop loss and take profit must be finite positive prices.")
        if direction in {"buy", "bullish"} and not stop_loss < price < take_profit:
            raise ValueError("BUY stop loss/entry/take profit levels are invalid.")
        if direction in {"sell", "bearish"} and not take_profit < price < stop_loss:
            raise ValueError("SELL stop loss/entry/take profit levels are invalid.")
        if direction in {"buy", "bullish"} and (price - stop_loss < stop_gap or take_profit - price < stop_gap):
            raise ValueError("Order levels violate the broker minimum stop distance.")
        if direction in {"sell", "bearish"} and (stop_loss - price < stop_gap or price - take_profit < stop_gap):
            raise ValueError("Order levels violate the broker minimum stop distance.")
        order_loss = self.mt5.order_calc_profit(mt5_direction, symbol, float(volume), price, stop_loss)
        balance = float(getattr(account, "balance", 0.0) or 0.0)
        equity = float(getattr(account, "equity", 0.0) or 0.0)
        if order_loss is None or not all(math.isfinite(x) and x > 0 for x in (balance, equity)):
            raise RuntimeError("Broker could not verify account balance or proposed order risk.")
        if not math.isfinite(float(order_loss)) or float(order_loss) >= 0:
            raise RuntimeError("Broker returned a non-loss result for the proposed stop loss.")
        risk_percent = abs(float(order_loss)) / min(balance, equity) * 100.0
        if not math.isfinite(risk_percent) or risk_percent > 1.0:
            raise RuntimeError("Broker-calculated order risk exceeds the 1% per-trade limit.")
        margin = self.mt5.order_calc_margin(mt5_direction, symbol, float(volume), price)
        free_margin = float(getattr(account, "margin_free", 0.0) or 0.0)
        if margin is None or not math.isfinite(float(margin)) or float(margin) <= 0:
            raise RuntimeError("Broker could not calculate required order margin.")
        if not math.isfinite(free_margin) or free_margin <= 0 or float(margin) > free_margin:
            raise RuntimeError("Insufficient or unverifiable free margin for the proposed order.")
        portfolio = build_mt5_portfolio_snapshot(self.mt5, magic=int(magic))
        if portfolio.daily_entries >= 10 or portfolio.open_positions >= 3:
            raise RuntimeError("Portfolio daily-entry or open-position limit has been reached.")
        if portfolio.daily_loss_percent >= 5.0 or portfolio.exposure_percent + risk_percent > 3.0:
            raise RuntimeError("Portfolio daily-loss or total-exposure limit blocks this order.")

        request = {
            "action": self.mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(volume),
            "type": mt5_direction,
            "price": price,
            "sl": stop_loss,
            "tp": take_profit,
            "deviation": 20,
            "magic": int(magic),
            "comment": str(comment),
            "type_time": self.mt5.ORDER_TIME_GTC,
            "type_filling": (
                self.mt5.ORDER_FILLING_IOC
                if getattr(info, "filling_mode", None) is not None
                and int(info.filling_mode) & int(getattr(self.mt5, "SYMBOL_FILLING_IOC", 2))
                else self.mt5.ORDER_FILLING_FOK
                if getattr(info, "filling_mode", None) is not None
                and int(info.filling_mode) & int(getattr(self.mt5, "SYMBOL_FILLING_FOK", 1))
                else self.mt5.ORDER_FILLING_RETURN
            ),
        }

        checked = self.mt5.order_check(request)
        if checked is None or getattr(checked, "retcode", None) not in {0, getattr(self.mt5, "TRADE_RETCODE_DONE", 10009)}:
            raise RuntimeError("MT5 order_check rejected the order request.")

        result = self.mt5.order_send(request)

        if result is None:
            raise RuntimeError("MT5 order_send returned no result.")

        if result.retcode not in {self.mt5.TRADE_RETCODE_DONE, self.mt5.TRADE_RETCODE_DONE_PARTIAL}:
            raise RuntimeError(
                f"MT5 order rejected: retcode={result.retcode}, comment={getattr(result, 'comment', '')}"
            )

        return {
            "ticket": int(getattr(result, "order", 0) or getattr(result, "deal", 0)),
            "symbol": symbol,
            "direction": direction,
            "volume": float(volume),
            "price": float(result.price),
            "retcode": int(result.retcode),
            "request": request,
        }

    def close_position(self, ticket: int, *, volume: float | None = None) -> dict[str, Any]:
        self._require_connection()
        if not self.enabled:
            raise RuntimeError("MT5 order execution is disabled by default.")
        account = self.mt5.account_info()
        demo_mode = getattr(self.mt5, "ACCOUNT_TRADE_MODE_DEMO", None)
        if account is None or demo_mode is None or getattr(account, "trade_mode", None) != demo_mode:
            raise RuntimeError("Hard safety block: position closing is enabled only on a verified DEMO account.")

        positions = self.mt5.positions_get(ticket=ticket)
        if not positions:
            raise RuntimeError(f"No open position found for ticket {ticket}.")

        position = positions[0]
        canonicalize_symbol(position.symbol)
        close_volume = float(volume) if volume is not None else float(position.volume)
        if not math.isfinite(close_volume) or close_volume <= 0 or close_volume > float(position.volume):
            raise ValueError("Close volume must be positive and no greater than the open position volume.")
        info = self.mt5.symbol_info(position.symbol)
        tick = self.mt5.symbol_info_tick(position.symbol)
        if info is None or tick is None:
            raise RuntimeError("Broker metadata or quote unavailable for position close.")
        step = float(getattr(info, "volume_step", 0.0) or 0.0)
        minimum = float(getattr(info, "volume_min", 0.0) or 0.0)
        if not math.isfinite(step) or not math.isfinite(minimum) or step <= 0 or minimum <= 0:
            raise RuntimeError("Broker volume specifications are invalid for position close.")
        if close_volume < minimum or not math.isclose(close_volume / step, round(close_volume / step), rel_tol=0.0, abs_tol=1e-8):
            raise ValueError("Close volume does not match the broker minimum and volume step.")
        close_type = self.mt5.ORDER_TYPE_SELL if position.type == self.mt5.POSITION_TYPE_BUY else self.mt5.ORDER_TYPE_BUY
        close_price = float(tick.bid if close_type == self.mt5.ORDER_TYPE_SELL else tick.ask)
        if not math.isfinite(close_price) or close_price <= 0:
            raise RuntimeError("Broker returned an invalid close quote.")

        request = {
            "action": self.mt5.TRADE_ACTION_DEAL,
            "symbol": position.symbol,
            "volume": close_volume,
            "type": close_type,
            "position": int(ticket),
            "price": close_price,
            "deviation": 20,
            "magic": 0,
            "comment": "Moil-bot close",
            "type_time": self.mt5.ORDER_TIME_GTC,
            "type_filling": self.mt5.ORDER_FILLING_RETURN,
        }

        checked = self.mt5.order_check(request)
        if checked is None or getattr(checked, "retcode", None) not in {0, getattr(self.mt5, "TRADE_RETCODE_DONE", 10009)}:
            raise RuntimeError("MT5 order_check rejected the close request.")
        result = self.mt5.order_send(request)
        if result is None:
            raise RuntimeError("MT5 close request returned no result.")

        if result.retcode not in {self.mt5.TRADE_RETCODE_DONE, self.mt5.TRADE_RETCODE_DONE_PARTIAL}:
            raise RuntimeError(
                f"MT5 close rejected: retcode={result.retcode}, comment={getattr(result, 'comment', '')}"
            )

        return {
            "ticket": int(ticket),
            "closed": True,
            "retcode": int(result.retcode),
        }

    def shutdown(self):
        if self.mt5 is not None:
            try:
                self.mt5.shutdown()
            finally:
                self.mt5 = None
                self.connected = False
        else:
            self.connected = False


__all__ = ["MT5ExecutionService"]
