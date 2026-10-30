"""Execution helpers for MetaTrader 5 trading actions."""

from __future__ import annotations

from typing import Any


class MT5ExecutionService:
    """Execute market orders through MetaTrader 5 after validation."""

    def __init__(self, mt5_module: Any | None = None):
        self.mt5 = mt5_module
        self.connected = False

    def connect(
        self,
        login: int,
        password: str,
        server: str,
        *,
        path: str | None = None,
    ) -> dict[str, Any]:
        try:
            import MetaTrader5 as mt5
        except ImportError as exc:  # pragma: no cover - environment dependent
            return {
                "connected": False,
                "message": "MetaTrader5 package is unavailable.",
                "error": str(exc),
            }

        self.mt5 = mt5

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
        magic: int = 0,
    ) -> dict[str, Any]:
        self._require_connection()

        symbol = str(symbol).strip()
        if not symbol:
            raise ValueError("symbol must not be empty.")

        direction = str(direction).strip().lower()
        if direction not in {"buy", "sell", "bullish", "bearish"}:
            raise ValueError("direction must be bullish/bearish or buy/sell.")

        if volume <= 0:
            raise ValueError("volume must be greater than zero.")

        if not self._symbol_ready(symbol):
            raise RuntimeError(f"Symbol {symbol} is not available in MT5.")

        mt5_direction = self.mt5.OP_BUY if direction in {"buy", "bullish"} else self.mt5.OP_SELL

        tick = self.mt5.symbol_info_tick(symbol)
        if tick is None:
            raise RuntimeError(f"No live tick available for {symbol}.")

        price = float(tick.ask if mt5_direction == self.mt5.OP_BUY else tick.bid)

        request = {
            "action": self.mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(volume),
            "type": mt5_direction,
            "price": price,
            "sl": float(stop_loss) if stop_loss is not None else 0.0,
            "tp": float(take_profit) if take_profit is not None else 0.0,
            "deviation": 20,
            "magic": int(magic),
            "comment": str(comment),
            "type_time": self.mt5.ORDER_TIME_GTC,
            "type_filling": self.mt5.ORDER_FILLING_RETURN,
        }

        result = self.mt5.order_send(request)

        if result is None:
            raise RuntimeError("MT5 order_send returned no result.")

        if result.retcode not in {self.mt5.TRADE_RETCODE_DONE, self.mt5.TRADE_RETCODE_DONE_PARTIAL}:
            raise RuntimeError(
                f"MT5 order rejected: retcode={result.retcode}, comment={getattr(result, 'comment', '')}"
            )

        return {
            "ticket": int(result.order),
            "symbol": symbol,
            "direction": direction,
            "volume": float(volume),
            "price": float(result.price),
            "retcode": int(result.retcode),
            "request": request,
        }

    def close_position(self, ticket: int, *, volume: float | None = None) -> dict[str, Any]:
        self._require_connection()

        positions = self.mt5.positions_get(ticket=ticket)
        if not positions:
            raise RuntimeError(f"No open position found for ticket {ticket}.")

        position = positions[0]
        close_volume = float(volume) if volume is not None else float(position.volume)

        request = {
            "action": self.mt5.TRADE_ACTION_DEAL,
            "symbol": position.symbol,
            "volume": close_volume,
            "type": self.mt5.OP_SELL if position.type == self.mt5.POSITION_TYPE_BUY else self.mt5.OP_BUY,
            "position": int(ticket),
            "price": 0.0,
            "deviation": 20,
            "magic": 0,
            "comment": "Moil-bot close",
            "type_time": self.mt5.ORDER_TIME_GTC,
            "type_filling": self.mt5.ORDER_FILLING_RETURN,
        }

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
