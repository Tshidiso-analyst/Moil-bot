from __future__ import annotations

import os
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
    ) -> MT5ConnectionResult:
        """Initialize and log in to the local MetaTrader 5 terminal."""
        del requested_mode  # Account mode is determined by the MT5 account itself.
        if self.mt5 is None:
            self.connected = False
            self.last_error = "MetaTrader5 package is not installed in this Python environment."
            return MT5ConnectionResult(connected=False, message=self.last_error)
        if login is None:
            self.connected = False
            self.last_error = "MT5 login is required."
            return MT5ConnectionResult(connected=False, message=self.last_error)

        try:
            if not self.mt5.initialize(path=self.path):
                self.connected = False
                self.last_error = f"MT5 initialization failed: {self.mt5.last_error()}"
                return MT5ConnectionResult(connected=False, message=self.last_error)
            if not self.mt5.login(int(login), password=password, server=server, timeout=60000):
                self.last_error = f"MT5 login failed: {self.mt5.last_error()}"
                self.mt5.shutdown()
                self.connected = False
                return MT5ConnectionResult(connected=False, message=self.last_error)
            info = self.mt5.account_info()
            if info is None:
                self.last_error = f"MT5 login succeeded but account info is unavailable: {self.mt5.last_error()}"
                self.mt5.shutdown()
                self.connected = False
                return MT5ConnectionResult(connected=False, message=self.last_error)
        except Exception as exc:
            self.last_error = f"MT5 connection failed: {exc}"
            self.connected = False
            try:
                self.mt5.shutdown()
            except Exception:
                pass
            return MT5ConnectionResult(connected=False, message=self.last_error)

        self.connected = True
        self.account = info
        self.last_error = ""
        account_type = getattr(info, "trade_mode", "")
        mode_map = {0: "DEMO", 1: "REAL", 2: "CONTEST", 3: "FUTURES"}
        account_type = mode_map.get(account_type, str(account_type))
        values = {
            "login": int(getattr(info, "login", login) or login),
            "server": str(getattr(info, "server", server) or server),
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
        if self.mt5 is None or not self.connected:
            return []
        try:
            raw_positions = self.mt5.positions_get()
            if raw_positions is None:
                return []
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
        except Exception as exc:
            self.last_error = f"MT5 positions lookup failed: {exc}"
            return []

    def open_trade_count(self) -> int:
        return len(self.positions()) if self.connected and self.mt5 is not None else 0

    def open_trade_summary(self) -> dict[str, float | int]:
        positions = self.positions() if self.connected and self.mt5 is not None else []
        return {"count": len(positions), "volume": sum(float(p.get("volume", 0.0)) for p in positions), "profit": sum(float(p.get("profit", 0.0)) for p in positions)}


__all__ = ["MT5ConnectionResult", "MT5LiveService"]
