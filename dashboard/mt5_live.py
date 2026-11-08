from __future__ import annotations

import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from math import isfinite
from dataclasses import dataclass, field
from typing import Any

try:
    import MetaTrader5 as mt5
except ImportError:  # pragma: no cover - optional dependency at runtime
    mt5 = None


@dataclass
class MT5ConnectionResult:
    connected: bool
    message: str
    login: int | None = None
    server: str = ""
    account_type: str = ""
    balance: float = 0.0
    equity: float = 0.0
    free_margin: float = 0.0
    profit: float = 0.0
    currency: str = "USD"
    raw: Any | None = None
    data: dict[str, Any] = field(default_factory=dict)


class MT5LiveService:
    """Live MT5 status, account summary, and open-position monitoring."""

    def __init__(self, mt5_module: Any | None = None, path: str | None = None):
        self.mt5 = mt5_module or mt5
        self.path = path or os.getenv("MT5_PATH", r"C:\Program Files\MetaTrader 5\terminal64.exe")
        self.connected = False
        self.account = None
        self.last_error = ""

    def connect(
        self,
        login: int | None = None,
        password: str = "",
        server: str = "",
        requested_mode: str = "DEMO",
        terminal_path: str | None = None,
    ) -> MT5ConnectionResult:
        """Initialize and log in to the local MetaTrader 5 terminal."""
        # A reconnect attempt must never leave a previous account looking active.
        self.connected = False
        self.account = None
        requested = str(requested_mode or "DEMO").strip().upper()
        if requested not in {"DEMO", "REAL"}:
            self.last_error = "Unsupported account mode. Select DEMO or REAL."
            return MT5ConnectionResult(connected=False, message=self.last_error)
        if login is not None:
            try:
                login_number = int(login)
            except (TypeError, ValueError, OverflowError):
                self.last_error = "MT5 login must be a positive account number."
                return MT5ConnectionResult(connected=False, message=self.last_error)
            normalized_server = str(server or "").strip()
            if login_number <= 0:
                self.last_error = "MT5 login must be a positive account number."
                return MT5ConnectionResult(connected=False, message=self.last_error)
            if not password:
                self.last_error = "Enter the trading password for this MT5 account."
                return MT5ConnectionResult(connected=False, message=self.last_error)
            # Empty server uses the server already configured in the selected MT5 terminal.
            # This supports broker-branded terminals without guessing account-specific servers.
            if len(normalized_server) > 128 or any(ord(char) < 32 for char in normalized_server):
                self.last_error = "MT5 server name is invalid."
                return MT5ConnectionResult(connected=False, message=self.last_error)
            login = login_number
            server = normalized_server
        if self.mt5 is None:
            self.last_error = "MetaTrader5 package is not installed in this Python environment."
            return MT5ConnectionResult(connected=False, message=self.last_error)
        target_path = str(terminal_path or self.path).strip()
        if not target_path or len(target_path) > 512 or any(ord(char) < 32 for char in target_path):
            self.last_error = "MT5 terminal path is invalid."
            return MT5ConnectionResult(connected=False, message=self.last_error)
        try:
            # Release any previous Python-to-terminal session before switching
            # broker accounts or broker-branded terminal installations.
            try:
                self.mt5.shutdown()
            except Exception:
                pass
            if not self.mt5.initialize(path=target_path):
                self.connected = False
                self.last_error = f"MT5 initialization failed: {self.mt5.last_error()}"
                return MT5ConnectionResult(connected=False, message=self.last_error)

            # If credentials are supplied, explicitly log in. Otherwise reuse
            # the account already authenticated in the running MT5 terminal.
            if login is not None:
                login_options = {"password": password, "timeout": 60000}
                # Omit the server argument when the selected terminal already
                # has this account's server configured; MT5 then uses its saved server.
                if server:
                    login_options["server"] = server
                if not self.mt5.login(int(login), **login_options):
                    self.last_error = f"MT5 login failed: {self.mt5.last_error()}"
                    self.mt5.shutdown()
                    self.connected = False
                    return MT5ConnectionResult(connected=False, message=self.last_error)

            info = self.mt5.account_info()
            if info is None:
                self.last_error = (
                    "No MT5 account is logged in. Open the MT5 terminal and sign in, "
                    "or provide login, password, and server."
                    f" MT5 detail: {self.mt5.last_error()}"
                )
                self.mt5.shutdown()
                self.connected = False
                return MT5ConnectionResult(connected=False, message=self.last_error)
            if login is not None:
                try:
                    actual_login = int(getattr(info, "login", 0) or 0)
                except (TypeError, ValueError, OverflowError):
                    actual_login = 0
                actual_server = str(getattr(info, "server", "") or "").strip()
                if actual_login != login or (server and actual_server.casefold() != server.casefold()) or not actual_server:
                    self.mt5.shutdown()
                    self.connected = False
                    self.account = None
                    self.last_error = (
                        "MT5 connected account identity does not match the requested login/server. "
                        f"Requested login {login} on {server or 'the terminal-selected server'!r}; "
                        f"terminal reports login {actual_login} on {actual_server!r}. "
                        "No session was created."
                    )
                    return MT5ConnectionResult(connected=False, message=self.last_error)
        except Exception as exc:
            self.last_error = f"MT5 connection failed: {exc}"
            self.connected = False
            try:
                self.mt5.shutdown()
            except Exception:
                pass
            return MT5ConnectionResult(connected=False, message=self.last_error)

        self.path = target_path
        self.connected = True
        self.account = info
        self.last_error = ""
        # MetaTrader5 ACCOUNT_TRADE_MODE values are DEMO=0, CONTEST=1, REAL=2.
        # Never trust the mode selected in the dashboard form.
        trade_mode = getattr(info, "trade_mode", None)
        mode_map = {
            getattr(self.mt5, "ACCOUNT_TRADE_MODE_DEMO", 0): "DEMO",
            getattr(self.mt5, "ACCOUNT_TRADE_MODE_CONTEST", 1): "CONTEST",
            getattr(self.mt5, "ACCOUNT_TRADE_MODE_REAL", 2): "REAL",
        }
        account_type = mode_map.get(trade_mode, "UNKNOWN")
        if account_type != requested:
            self.mt5.shutdown()
            self.connected = False
            self.account = None
            self.last_error = (
                f"Selected {requested} mode does not match the connected MT5 "
                f"account type ({account_type}). No session was created."
            )
            return MT5ConnectionResult(connected=False, message=self.last_error)
        values = {
            "login": int(getattr(info, "login", login) or login or 0),
            "server": str(getattr(info, "server", server) or server or ""),
            "account_type": account_type,
            "balance": float(getattr(info, "balance", 0.0) or 0.0),
            "equity": float(getattr(info, "equity", 0.0) or 0.0),
            "free_margin": float(getattr(info, "margin_free", 0.0) or 0.0),
            "profit": float(getattr(info, "profit", 0.0) or 0.0),
            "currency": str(getattr(info, "currency", "USD") or "USD"),
        }
        return MT5ConnectionResult(
            connected=True,
            message="Connected successfully.",
            raw=info,
            data=values.copy(),
            **values,
        )

    def disconnect(self) -> None:
        if self.mt5 is not None:
            try:
                self.mt5.shutdown()
            except Exception:
                pass
        self.connected = False
        self.account = None

    def shutdown(self) -> None:
        self.disconnect()

    def account_summary(self) -> dict[str, float | int | bool]:
        if self.mt5 is None or not self.connected:
            return {"connected": False, "balance": 0.0, "equity": 0.0, "margin": 0.0, "free_margin": 0.0, "profit": 0.0}
        try:
            info = self.mt5.account_info()
            if info is None:
                self.last_error = f"MT5 account info unavailable: {self.mt5.last_error()}"
                return {"connected": False, "balance": 0.0, "equity": 0.0, "margin": 0.0, "free_margin": 0.0, "profit": 0.0}
            return {
                "connected": True,
                "balance": float(getattr(info, "balance", 0.0) or 0.0),
                "equity": float(getattr(info, "equity", 0.0) or 0.0),
                "margin": float(getattr(info, "margin", 0.0) or 0.0),
                "free_margin": float(getattr(info, "margin_free", 0.0) or 0.0),
                "profit": float(getattr(info, "profit", 0.0) or 0.0),
            }
        except Exception as exc:
            self.last_error = f"MT5 account summary failed: {exc}"
            return {"connected": False, "balance": 0.0, "equity": 0.0, "margin": 0.0, "free_margin": 0.0, "profit": 0.0}

    def _market_row(self, symbol_name: str) -> dict[str, Any] | None:
        if not self.mt5.symbol_select(symbol_name, True):
            self.last_error = f"MT5 could not select symbol {symbol_name}: {self.mt5.last_error()}"
            return None
        info = self.mt5.symbol_info(symbol_name)
        if info is None:
            self.last_error = f"MT5 has no symbol info for {symbol_name}: {self.mt5.last_error()}"
            return None
        tick = self.mt5.symbol_info_tick(symbol_name)
        bid = float(getattr(tick, "bid", 0.0) or getattr(info, "bid", 0.0) or 0.0) if tick is not None else float(getattr(info, "bid", 0.0) or 0.0)
        ask = float(getattr(tick, "ask", 0.0) or getattr(info, "ask", 0.0) or 0.0) if tick is not None else float(getattr(info, "ask", 0.0) or 0.0)
        digits = int(getattr(info, "digits", 5) or 5)
        return {
            "symbol": symbol_name,
            "description": getattr(info, "description", ""),
            "digits": digits,
            "bid": bid,
            "ask": ask,
            "spread": max(0.0, ask - bid),
        }

    def symbols(self) -> list[dict[str, Any]]:
        if self.mt5 is None or not self.connected:
            self.last_error = "MT5 service is not connected. Reconnect from the dashboard."
            return []
        try:
            raw_symbols = self.mt5.symbols_get()
            if raw_symbols is None:
                self.last_error = f"MT5 returned no symbols: {self.mt5.last_error()}"
                return []
            rows = []
            for symbol in raw_symbols:
                row = self._market_row(symbol.name)
                if row is not None:
                    rows.append(row)
                    if len(rows) >= 25:
                        break
            if not rows and not self.last_error:
                self.last_error = "MT5 returned symbols but none could be selected/read."
            return rows
        except Exception as exc:
            self.last_error = f"MT5 symbol lookup failed: {exc}"
            return []

    def symbol(self, symbol_name: str) -> dict[str, Any] | None:
        if self.mt5 is None or not self.connected:
            self.last_error = "MT5 service is not connected. Reconnect from the dashboard."
            return None
        try:
            row = self._market_row(symbol_name)
            if row is None:
                # Exness and other brokers can append suffixes to instruments.
                candidates = self.mt5.symbols_get(group=f"*{symbol_name}*") or ()
                if candidates:
                    row = self._market_row(candidates[0].name)
            return row
        except Exception as exc:
            self.last_error = f"MT5 lookup for {symbol_name} failed: {exc}"
            return None

    def positions(self) -> list[dict[str, Any]]:
        """Return open positions, failing closed when MT5 cannot verify them."""
        if self.mt5 is None or not self.connected:
            self.last_error = "MT5 must be connected to verify open positions."
            raise RuntimeError(self.last_error)
        try:
            raw_positions = self.mt5.positions_get()
            if raw_positions is None:
                self.last_error = f"MT5 positions lookup failed: {self.mt5.last_error()}"
                raise RuntimeError(self.last_error)
            return [
                {
                    "ticket": int(getattr(p, "ticket", 0) or 0),
                    "symbol": getattr(p, "symbol", ""),
                    "volume": float(getattr(p, "volume", 0.0) or 0.0),
                    "profit": float(getattr(p, "profit", 0.0) or 0.0),
                    "swap": float(getattr(p, "swap", 0.0) or 0.0),
                    "comment": getattr(p, "comment", ""),
                    "type": getattr(p, "type", 0),
                    "price_open": float(getattr(p, "price_open", 0.0) or 0.0),
                    "price_current": float(getattr(p, "price_current", 0.0) or 0.0),
                }
                for p in raw_positions
            ]
        except RuntimeError:
            raise
        except Exception as exc:
            self.last_error = f"MT5 positions lookup failed: {exc}"
            raise RuntimeError(self.last_error) from exc

    @staticmethod
    def _new_york_trading_window(now: datetime | None = None) -> tuple[datetime, datetime]:
        """Return today's New York midnight and now as UTC MT5 history bounds."""
        checked_at = now or datetime.now(timezone.utc)
        if checked_at.tzinfo is None or checked_at.utcoffset() is None:
            raise ValueError("now must be timezone-aware.")
        utc_now = checked_at.astimezone(timezone.utc)
        new_york = ZoneInfo("America/New_York")
        local_midnight = utc_now.astimezone(new_york).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return local_midnight.astimezone(timezone.utc), utc_now

    def today_entry_count(self, now: datetime | None = None) -> int:
        """Count today's opening deals across the connected account.

        If MT5 cannot provide deal history, fail closed instead of silently
        bypassing the one-new-trade-per-day rule.
        """
        if self.mt5 is None or not self.connected:
            raise RuntimeError("MT5 must be connected to check today's trade limit.")
        history = getattr(self.mt5, "history_deals_get", None)
        if history is None:
            raise RuntimeError("This MT5 package cannot verify today's trade count.")
        # MT5 history arguments are UTC, but the strategy's trading day is New York.
        start, end = self._new_york_trading_window(now)
        deals = history(start, end)
        if deals is None:
            raise RuntimeError(f"MT5 could not verify today's deal history: {self.mt5.last_error()}")
        entry_values = {
            getattr(self.mt5, "DEAL_ENTRY_IN", 0),
            getattr(self.mt5, "DEAL_ENTRY_INOUT", 2),
        }
        trade_types = {
            getattr(self.mt5, "DEAL_TYPE_BUY", 0),
            getattr(self.mt5, "DEAL_TYPE_SELL", 1),
        }
        order_ids: set[int] = set()
        for deal in deals:
            entry = getattr(deal, "entry", None)
            deal_type = getattr(deal, "type", None)
            if entry is None or deal_type is None:
                raise RuntimeError(
                    "MT5 returned malformed deal history; today's trade count cannot be verified."
                )
            if entry in entry_values and deal_type in trade_types:
                order_id = getattr(deal, "order", None)
                try:
                    order_number = int(order_id or 0)
                except (TypeError, ValueError, OverflowError):
                    order_number = 0
                if order_number <= 0:
                    raise RuntimeError(
                        "MT5 entry deal has no valid order ID; today's distinct trade count cannot be verified."
                    )
                # One order can generate multiple partial-fill deals. Count the
                # order once, while a later reversal/new order counts separately.
                order_ids.add(order_number)
        return len(order_ids)

    def today_loss_percent(self, now: datetime | None = None) -> float:
        """Estimate today's realized plus floating trading loss as % of start balance."""
        if self.mt5 is None or not self.connected:
            raise RuntimeError("MT5 must be connected to verify today's loss limit.")
        history = getattr(self.mt5, "history_deals_get", None)
        if history is None:
            raise RuntimeError("This MT5 package cannot verify today's loss.")
        # Use the same New York trading-day boundary as the entry-count guard.
        start, end = self._new_york_trading_window(now)
        deals = history(start, end)
        if deals is None:
            raise RuntimeError(f"MT5 could not verify today's P/L history: {self.mt5.last_error()}")

        trade_types = {
            getattr(self.mt5, "DEAL_TYPE_BUY", 0),
            getattr(self.mt5, "DEAL_TYPE_SELL", 1),
        }
        try:
            if any(getattr(deal, "type", None) is None for deal in deals):
                raise RuntimeError("MT5 returned malformed deal history; daily loss cannot be verified.")
            non_trade_adjustments = [
                deal for deal in deals
                if getattr(deal, "type", None) not in trade_types
                and any(
                    float(getattr(deal, field, 0.0) or 0.0) != 0.0
                    for field in ("profit", "commission", "swap", "fee")
                )
            ]
            if non_trade_adjustments:
                raise RuntimeError(
                    "MT5 history contains a deposit, withdrawal, credit or other "
                    "non-trading balance adjustment today; daily loss cannot be "
                    "verified safely until the next New York trading day."
                )
            realized = sum(
                float(getattr(deal, "profit", 0.0) or 0.0)
                + float(getattr(deal, "commission", 0.0) or 0.0)
                + float(getattr(deal, "swap", 0.0) or 0.0)
                + float(getattr(deal, "fee", 0.0) or 0.0)
                for deal in deals
                if getattr(deal, "type", None) in trade_types
            )
        except (TypeError, ValueError, OverflowError) as exc:
            raise RuntimeError("MT5 returned invalid realized P/L values.") from exc
        if not isfinite(realized):
            raise RuntimeError("MT5 returned non-finite realized P/L; daily risk cannot be verified.")

        account = self.mt5.account_info()
        if account is None:
            raise RuntimeError("MT5 account balance is unavailable for daily loss calculation.")
        try:
            balance = float(getattr(account, "balance", 0.0) or 0.0)
            raw_positions = self.mt5.positions_get()
            if raw_positions is None:
                raise RuntimeError(
                    f"MT5 open positions are unavailable for daily loss calculation: {self.mt5.last_error()}"
                )
            floating = sum(
                float(getattr(position, "profit", 0.0) or 0.0)
                + float(getattr(position, "swap", 0.0) or 0.0)
                for position in raw_positions
            )
        except RuntimeError:
            raise
        except (TypeError, ValueError, OverflowError) as exc:
            raise RuntimeError("MT5 returned invalid account or floating P/L values.") from exc

        start_balance = balance - realized
        if (
            not isfinite(balance)
            or balance <= 0
            or not isfinite(floating)
            or not isfinite(start_balance)
            or start_balance <= 0
        ):
            raise RuntimeError("MT5 account or start-of-day balance is invalid.")
        loss_percent = -(realized + floating) / start_balance * 100.0
        if not isfinite(loss_percent):
            raise RuntimeError("Daily loss calculation is non-finite; DEMO execution is blocked.")
        return max(0.0, loss_percent)

    def open_trade_count(self) -> int:
        """Count positions only after MT5 successfully verifies the position list."""
        return len(self.positions())

    def open_trade_summary(self) -> dict[str, float | int]:
        """Summarize verified open positions; unavailable data must raise, not look empty."""
        positions = self.positions()
        return {
            "count": len(positions),
            "volume": sum(float(position["volume"]) for position in positions),
            "profit": sum(float(position["profit"]) for position in positions),
        }


__all__ = ["MT5ConnectionResult", "MT5LiveService"]
