"""Demo-account-only execution helpers for MetaTrader 5.

This service deliberately refuses to place or close orders on REAL accounts.
The account type is re-read from the connected terminal immediately before
each trading operation; a UI-selected mode is never treated as proof.
"""
from __future__ import annotations

from math import floor, isfinite
from typing import Any


class MT5ExecutionService:
    """Place guarded market orders only on a verified MT5 DEMO account."""

    def __init__(self, mt5_module: Any | None = None):
        self.mt5 = mt5_module
        self.connected = False
        self.account_mode = "UNKNOWN"

    def _mode(self, info: Any) -> str:
        if self.mt5 is None:
            return "UNKNOWN"
        value = getattr(info, "trade_mode", None)
        modes = {
            getattr(self.mt5, "ACCOUNT_TRADE_MODE_DEMO", 0): "DEMO",
            getattr(self.mt5, "ACCOUNT_TRADE_MODE_CONTEST", 1): "CONTEST",
            getattr(self.mt5, "ACCOUNT_TRADE_MODE_REAL", 2): "REAL",
        }
        return modes.get(value, "UNKNOWN")

    def _verify_demo_account(self) -> Any:
        if self.mt5 is None:
            raise RuntimeError("MetaTrader5 is unavailable.")
        info = self.mt5.account_info()
        if info is None:
            self.connected = False
            self.account_mode = "UNKNOWN"
            raise RuntimeError(f"MT5 account is not connected: {self.mt5.last_error()}")
        mode = self._mode(info)
        self.account_mode = mode
        if mode != "DEMO":
            raise RuntimeError(
                f"Order blocked: connected MT5 account is {mode}, not DEMO. "
                "Moil-bot demo execution cannot trade real-money accounts."
            )
        return info

    def adopt_existing_connection(self) -> dict[str, Any]:
        """Attach to the dashboard's already logged-in terminal after DEMO verification."""
        info = self._verify_demo_account()
        self.connected = True
        return {
            "connected": True,
            "account_mode": "DEMO",
            "login": int(getattr(info, "login", 0) or 0),
            "server": str(getattr(info, "server", "") or ""),
        }

    def connect(
        self,
        login: int,
        password: str,
        server: str = "",
        *,
        path: str | None = None,
    ) -> dict[str, Any]:
        try:
            account_number = int(login)
        except (TypeError, ValueError, OverflowError):
            return {"connected": False, "message": "MT5 login must be a positive account number."}
        normalized_server = str(server or "").strip()
        if account_number <= 0 or not str(password or ""):
            return {
                "connected": False,
                "message": "Provide a positive MT5 login and trading password.",
            }
        if len(normalized_server) > 128 or any(ord(char) < 32 for char in normalized_server):
            return {"connected": False, "message": "MT5 server name is invalid."}
        try:
            if self.mt5 is None:
                import MetaTrader5 as mt5
                self.mt5 = mt5
        except ImportError as exc:  # pragma: no cover - environment dependent
            return {"connected": False, "message": "MetaTrader5 package is unavailable.", "error": str(exc)}

        try:
            try:
                self.mt5.shutdown()
            except Exception:
                pass
            kwargs = {"login": account_number, "password": str(password)}
            if normalized_server:
                kwargs["server"] = normalized_server
            if path:
                kwargs["path"] = str(path)
            if not self.mt5.initialize(**kwargs):
                self.connected = False
                return {"connected": False, "message": "MT5 initialization failed.", "error": self.mt5.last_error()}
            info = self.mt5.account_info()
            if info is not None:
                try:
                    actual_login = int(getattr(info, "login", 0) or 0)
                except (TypeError, ValueError, OverflowError):
                    actual_login = 0
                actual_server = str(getattr(info, "server", "") or "").strip()
                if (
                    actual_login != account_number
                    or not actual_server
                    or (normalized_server and actual_server.casefold() != normalized_server.casefold())
                ):
                    self.mt5.shutdown()
                    self.connected = False
                    self.account_mode = self._mode(info)
                    return {
                        "connected": False,
                        "account_mode": self.account_mode,
                        "message": (
                            "MT5 execution connection refused: terminal account identity does not "
                            f"match requested login {account_number} on {normalized_server or 'the terminal-selected server'!r}; "
                            f"terminal reports login {actual_login} on {actual_server!r}."
                        ),
                    }
            if info is None or self._mode(info) != "DEMO":
                actual = self._mode(info) if info is not None else "UNKNOWN"
                self.mt5.shutdown()
                self.connected = False
                self.account_mode = actual
                return {
                    "connected": False,
                    "account_mode": actual,
                    "message": f"Execution connection refused: MT5 account type is {actual}; DEMO is required.",
                }
            self.connected = True
            self.account_mode = "DEMO"
            return {"connected": True, "account_mode": "DEMO", "message": "Verified MT5 DEMO account connected."}
        except Exception as exc:
            self.connected = False
            self.account_mode = "UNKNOWN"
            try:
                self.mt5.shutdown()
            except Exception:
                pass
            return {"connected": False, "message": f"MT5 connection failed: {exc}"}

    def _require_connection(self) -> Any:
        if not self.connected:
            raise RuntimeError("MT5 execution service is not connected.")
        return self._verify_demo_account()

    def calculate_volume_for_risk(
        self,
        *,
        symbol: str,
        direction: str,
        entry: float,
        stop_loss: float,
        balance: float,
        risk_percent: float = 0.5,
    ) -> float:
        """Calculate a broker-step-aligned volume using MT5's account-currency P/L."""
        self._require_connection()
        if not (isfinite(entry) and isfinite(stop_loss) and entry > 0 and stop_loss > 0):
            raise ValueError("Entry and stop loss must be finite positive prices.")
        if not (0 < risk_percent <= 1.0):
            raise ValueError("Demo risk_percent must be greater than 0 and no more than 1%.")
        if not (isfinite(balance) and balance > 0):
            raise ValueError("Account balance must be positive.")
        side = str(direction).strip().lower()
        if side not in {"buy", "bullish", "sell", "bearish"}:
            raise ValueError("Unsupported direction.")
        order_type = self.mt5.ORDER_TYPE_BUY if side in {"buy", "bullish"} else self.mt5.ORDER_TYPE_SELL
        loss_one_lot = self.mt5.order_calc_profit(order_type, symbol, 1.0, float(entry), float(stop_loss))
        if loss_one_lot is None or not isfinite(float(loss_one_lot)) or float(loss_one_lot) >= 0:
            raise RuntimeError("MT5 could not calculate a valid loss at the proposed stop; trade blocked.")
        info = self.mt5.symbol_info(symbol)
        if info is None:
            raise RuntimeError(f"MT5 symbol information unavailable for {symbol}.")
        step = float(getattr(info, "volume_step", 0.0) or 0.0)
        minimum = float(getattr(info, "volume_min", 0.0) or 0.0)
        maximum = float(getattr(info, "volume_max", 0.0) or 0.0)
        if step <= 0 or minimum <= 0 or maximum < minimum:
            raise RuntimeError(f"Broker volume limits are invalid for {symbol}.")
        risk_cash = float(balance) * (float(risk_percent) / 100.0)
        raw = risk_cash / abs(float(loss_one_lot))
        if raw < minimum:
            raise RuntimeError(
                f"Minimum broker volume {minimum:g} would exceed the {risk_percent:g}% risk budget; trade blocked."
            )
        volume = minimum + floor((raw - minimum) / step) * step
        if volume < minimum:
            raise RuntimeError(
                f"Minimum broker volume {minimum:g} would exceed the {risk_percent:g}% risk budget; trade blocked."
            )
        volume = min(volume, maximum)
        return round(volume, 8)

    def _filling_policy(self, symbol_info: Any) -> int:
        """Choose a volume filling policy supported by this broker and symbol."""
        market_execution = getattr(self.mt5, "SYMBOL_TRADE_EXECUTION_MARKET", 2)
        if getattr(symbol_info, "trade_exemode", None) != market_execution:
            return self.mt5.ORDER_FILLING_RETURN

        try:
            allowed = int(getattr(symbol_info, "filling_mode", 0) or 0)
        except (TypeError, ValueError, OverflowError) as exc:
            raise RuntimeError("Broker returned an invalid symbol filling-mode value.") from exc
        fok_flag = int(getattr(self.mt5, "SYMBOL_FILLING_FOK", 1))
        ioc_flag = int(getattr(self.mt5, "SYMBOL_FILLING_IOC", 2))
        if allowed & fok_flag:
            return self.mt5.ORDER_FILLING_FOK
        if allowed & ioc_flag:
            return self.mt5.ORDER_FILLING_IOC
        raise RuntimeError(
            "Broker symbol uses market execution but advertises no supported FOK/IOC filling policy."
        )

    def _check_order_request(
        self,
        request: dict[str, Any],
        *,
        require_nonnegative_margin: bool = True,
    ) -> Any:
        """Require MT5's server-side funds and request validation before sending."""
        checker = getattr(self.mt5, "order_check", None)
        if not callable(checker):
            raise RuntimeError("MT5 order_check is unavailable; broker margin cannot be verified.")
        checked = checker(request)
        if checked is None:
            raise RuntimeError(f"MT5 order pre-check returned no result: {self.mt5.last_error()}")
        retcode = getattr(checked, "retcode", None)
        if retcode is None or retcode != 0:
            raise RuntimeError(
                "MT5 order pre-check rejected the request: "
                f"retcode={retcode}, comment={getattr(checked, 'comment', '')}, "
                f"error={self.mt5.last_error()}"
            )
        try:
            projected_free_margin = float(getattr(checked, "margin_free"))
        except (AttributeError, TypeError, ValueError, OverflowError) as exc:
            raise RuntimeError("MT5 pre-check did not return valid projected free margin.") from exc
        if not isfinite(projected_free_margin) or (require_nonnegative_margin and projected_free_margin < 0):
            raise RuntimeError("MT5 pre-check reports insufficient or invalid free margin.")
        return checked

    def place_market_order(
        self,
        symbol: str,
        direction: str,
        volume: float,
        *,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        comment: str = "Moil-bot DEMO",
        magic: int = 26001,
        max_risk_amount: float | None = None,
    ) -> dict[str, Any]:
        self._require_connection()
        symbol = str(symbol).strip()
        if not symbol:
            raise ValueError("symbol must not be empty.")
        side = str(direction).strip().lower()
        if side not in {"buy", "sell", "bullish", "bearish"}:
            raise ValueError("direction must be bullish/bearish or buy/sell.")
        if not isfinite(float(volume)) or float(volume) <= 0:
            raise ValueError("volume must be a positive finite number.")
        if stop_loss is None or take_profit is None:
            raise ValueError("A stop loss and take profit are mandatory for demo orders.")

        info = self.mt5.symbol_info(symbol)
        if info is None:
            raise RuntimeError(f"Symbol {symbol} is not available in MT5.")
        if not bool(getattr(info, "visible", True)) and not self.mt5.symbol_select(symbol, True):
            raise RuntimeError(f"MT5 could not select symbol {symbol}: {self.mt5.last_error()}")
        minimum = float(getattr(info, "volume_min", 0.0) or 0.0)
        maximum = float(getattr(info, "volume_max", 0.0) or 0.0)
        step = float(getattr(info, "volume_step", 0.0) or 0.0)
        vol = float(volume)
        if minimum <= 0 or maximum < minimum or step <= 0 or vol < minimum or vol > maximum:
            raise ValueError("Order volume is outside broker limits.")
        steps = round((vol - minimum) / step)
        if abs((minimum + steps * step) - vol) > max(1e-8, step * 1e-6):
            raise ValueError("Order volume does not match the broker volume step.")

        tick = self.mt5.symbol_info_tick(symbol)
        if tick is None:
            raise RuntimeError(f"No live tick available for {symbol}.")
        is_buy = side in {"buy", "bullish"}
        order_type = self.mt5.ORDER_TYPE_BUY if is_buy else self.mt5.ORDER_TYPE_SELL
        price = float(tick.ask if is_buy else tick.bid)
        sl, tp = float(stop_loss), float(take_profit)
        if not (isfinite(price) and price > 0 and isfinite(sl) and isfinite(tp)):
            raise ValueError("Live price, stop loss and take profit must be finite.")
        if is_buy and not (sl < price < tp):
            raise ValueError("For a buy order, stop loss must be below price and take profit above price.")
        if not is_buy and not (tp < price < sl):
            raise ValueError("For a sell order, take profit must be below price and stop loss above price.")

        if (
            max_risk_amount is None
            or isinstance(max_risk_amount, bool)
            or not isfinite(float(max_risk_amount))
            or float(max_risk_amount) <= 0
        ):
            raise ValueError(
                "A finite positive max_risk_amount is mandatory for every DEMO order."
            )

        loss = self.mt5.order_calc_profit(order_type, symbol, vol, price, sl)
        if (
            loss is None
            or not isfinite(float(loss))
            or float(loss) >= 0
            or abs(float(loss)) > float(max_risk_amount) + 0.01
        ):
            raise RuntimeError("Order exceeds the approved risk budget; trade blocked.")

        request = {
            "action": self.mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": vol,
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": 20,
            "magic": int(magic),
            "comment": str(comment)[:31],
            "type_time": self.mt5.ORDER_TIME_GTC,
            "type_filling": self._filling_policy(info),
        }
        self._check_order_request(request)
        result = self.mt5.order_send(request)
        if result is None:
            raise RuntimeError(f"MT5 order_send returned no result: {self.mt5.last_error()}")
        accepted = {
            getattr(self.mt5, "TRADE_RETCODE_DONE", 10009),
            getattr(self.mt5, "TRADE_RETCODE_DONE_PARTIAL", 10010),
        }
        if result.retcode not in accepted:
            raise RuntimeError(
                f"MT5 demo order rejected: retcode={result.retcode}, "
                f"comment={getattr(result, 'comment', '')}, error={self.mt5.last_error()}"
            )
        reported_volume = getattr(result, "volume", None)
        if reported_volume is None:
            if result.retcode == getattr(self.mt5, "TRADE_RETCODE_DONE_PARTIAL", 10010):
                raise RuntimeError(
                    f"MT5 reported a partial fill without the executed volume "
                    f"(order={getattr(result, 'order', 0)}, deal={getattr(result, 'deal', 0)}). "
                    "Inspect the DEMO account before any retry."
                )
            executed_volume = vol
        else:
            try:
                executed_volume = float(reported_volume)
            except (TypeError, ValueError, OverflowError) as exc:
                raise RuntimeError("MT5 returned an invalid executed volume; inspect the DEMO account.") from exc
            if not isfinite(executed_volume) or executed_volume <= 0 or executed_volume > vol:
                raise RuntimeError("MT5 returned an invalid executed volume; inspect the DEMO account.")
        return {
            "ticket": int(getattr(result, "order", 0) or getattr(result, "deal", 0) or 0),
            "symbol": symbol,
            "direction": "bullish" if is_buy else "bearish",
            "volume": executed_volume,
            "price": float(getattr(result, "price", price) or price),
            "retcode": int(result.retcode),
            "request": request,
            "account_mode": "DEMO",
        }

    def close_position(self, ticket: int, *, volume: float | None = None) -> dict[str, Any]:
        self._require_connection()
        try:
            ticket_number = int(ticket)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("Position ticket must be a positive integer.") from exc
        if ticket_number <= 0:
            raise ValueError("Position ticket must be a positive integer.")

        positions = self.mt5.positions_get(ticket=ticket_number)
        if positions is None:
            raise RuntimeError(f"MT5 position lookup failed: {self.mt5.last_error()}")
        if not positions:
            raise RuntimeError(f"No open position found for ticket {ticket_number}.")
        position = positions[0]
        try:
            original_volume = float(position.volume)
            close_volume = float(volume) if volume is not None else original_volume
        except (AttributeError, TypeError, ValueError, OverflowError) as exc:
            raise RuntimeError("MT5 returned invalid position volume data.") from exc
        if (
            not isfinite(original_volume)
            or original_volume <= 0
            or not isfinite(close_volume)
            or close_volume <= 0
            or close_volume > original_volume
        ):
            raise ValueError("Close volume must be finite, positive and no greater than the position volume.")

        symbol = str(getattr(position, "symbol", "") or "").strip()
        if not symbol:
            raise RuntimeError("MT5 position has no valid symbol.")
        position_type = getattr(position, "type", None)
        if position_type == self.mt5.POSITION_TYPE_BUY:
            close_type = self.mt5.ORDER_TYPE_SELL
        elif position_type == getattr(self.mt5, "POSITION_TYPE_SELL", 1):
            close_type = self.mt5.ORDER_TYPE_BUY
        else:
            raise RuntimeError("MT5 position has an unknown direction; close request blocked.")

        symbol_info = self.mt5.symbol_info(symbol)
        if symbol_info is None:
            raise RuntimeError(f"MT5 symbol information unavailable for {symbol}; close request blocked.")
        minimum = float(getattr(symbol_info, "volume_min", 0.0) or 0.0)
        step = float(getattr(symbol_info, "volume_step", 0.0) or 0.0)
        if minimum <= 0 or step <= 0 or close_volume < minimum:
            raise ValueError("Close volume is outside broker minimum/step limits.")
        steps = round(close_volume / step)
        if abs(steps * step - close_volume) > max(1e-8, step * 1e-6):
            raise ValueError("Close volume does not match the broker volume step.")

        tick = self.mt5.symbol_info_tick(symbol)
        if tick is None:
            raise RuntimeError(f"No live tick available for {symbol}.")
        price = float(tick.bid if position_type == self.mt5.POSITION_TYPE_BUY else tick.ask)
        if not isfinite(price) or price <= 0:
            raise RuntimeError(f"MT5 returned an invalid close price for {symbol}.")
        request = {
            "action": self.mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": close_volume,
            "type": close_type,
            "position": ticket_number,
            "price": price,
            "deviation": 20,
            "magic": 26001,
            "comment": "Moil-bot DEMO close",
            "type_time": self.mt5.ORDER_TIME_GTC,
            "type_filling": self._filling_policy(symbol_info),
        }
        # Closing reduces exposure. Require a successful broker request check,
        # but do not block a risk-reducing close solely because projected free
        # margin remains negative on an already-margined account.
        self._check_order_request(request, require_nonnegative_margin=False)
        result = self.mt5.order_send(request)
        if result is None or result.retcode not in {
            getattr(self.mt5, "TRADE_RETCODE_DONE", 10009),
            getattr(self.mt5, "TRADE_RETCODE_DONE_PARTIAL", 10010),
        }:
            raise RuntimeError(f"MT5 demo close rejected: {self.mt5.last_error()}")

        reported_volume = getattr(result, "volume", None)
        if reported_volume is None:
            if result.retcode == getattr(self.mt5, "TRADE_RETCODE_DONE_PARTIAL", 10010):
                raise RuntimeError(
                    f"MT5 reported a partial close without the executed volume "
                    f"(position={ticket_number}). Inspect the DEMO account before any retry."
                )
            executed_volume = close_volume
        else:
            try:
                executed_volume = float(reported_volume)
            except (TypeError, ValueError, OverflowError) as exc:
                raise RuntimeError("MT5 returned invalid executed close volume; inspect the DEMO account.") from exc
            if not isfinite(executed_volume) or executed_volume <= 0 or executed_volume > close_volume:
                raise RuntimeError("MT5 returned invalid executed close volume; inspect the DEMO account.")

        remaining_volume = max(0.0, original_volume - executed_volume)
        fully_closed = (
            result.retcode == getattr(self.mt5, "TRADE_RETCODE_DONE", 10009)
            and remaining_volume <= max(1e-8, step * 1e-6)
        )
        return {
            "ticket": ticket_number,
            "closed": fully_closed,
            "partially_closed": not fully_closed,
            "volume": executed_volume,
            "remaining_volume": remaining_volume,
            "retcode": int(result.retcode),
        }

    def shutdown(self) -> None:
        if self.mt5 is not None:
            try:
                self.mt5.shutdown()
            finally:
                self.connected = False
                self.account_mode = "UNKNOWN"


__all__ = ["MT5ExecutionService"]
