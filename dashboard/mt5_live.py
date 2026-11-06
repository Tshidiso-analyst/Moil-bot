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

    def connect(
        self,
        login: int | None = None,
        password: str = "",
        server: str = "",
        requested_mode: str = "DEMO",
    ) -> MT5ConnectionResult:
        """Initialize and log in to the local MetaTrader 5 terminal.

        The actual MetaTrader5 Python package accepts a login/password/server
        flow and does not support the older custom app contract that passed
        requested_mode into the connect method.
        """
        if self.mt5 is None:
            return MT5ConnectionResult(
                connected=False,
                message="MetaTrader5 package is not installed in this Python environment.",
            )

        if login is None:
            return MT5ConnectionResult(
                connected=False,
                message="MT5 login is required.",
            )

        try:
            initialized = bool(self.mt5.initialize(path=self.path))
        except Exception as exc:  # pragma: no cover - runtime-specific
            return MT5ConnectionResult(
                connected=False,
                message=f"MT5 initialization failed: {exc}",
            )

        if not initialized:
            return MT5ConnectionResult(
                connected=False,
                message=f"MT5 initialization failed: {self.mt5.last_error()}",
            )

        try:
            logged_in = bool(self.mt5.login(login, password, server, timeout=60000))
        except Exception as exc:
            self.mt5.shutdown()
            return MT5ConnectionResult(
                connected=False,
                message=f"MT5 login failed: {exc}",
            )

        if not logged_in:
            self.mt5.shutdown()
            return MT5ConnectionResult(
                connected=False,
                message=f"MT5 login failed: {self.mt5.last_error()}",
            )

        info = self.mt5.account_info()
        self.connected = True
        self.account = info

        account_type = getattr(info, "trade_mode", "")
        if account_type in {0, 1, 2, 3}:
            mode_map = {
                0: "ACCOUNT_TYPE_DEMO",
                1: "ACCOUNT_TYPE_REAL",
                2: "ACCOUNT_TYPE_CONTEST",
                3: "ACCOUNT_TYPE_FORTS",
            }
            account_type = mode_map.get(account_type, str(account_type))

        result = MT5ConnectionResult(
            connected=True,
            message="Connected successfully.",
            login=int(login),
            server=str(server),
            account_type=str(account_type),
            balance=float(getattr(info, "balance", 0.0) or 0.0),
            equity=float(getattr(info, "equity", 0.0) or 0.0),
            free_margin=float(getattr(info, "margin_free", 0.0) or 0.0),
            profit=float(getattr(info, "profit", 0.0) or 0.0),
            currency=str(getattr(info, "currency", "USD") or "USD"),
            raw=info,
            data={
                "login": int(login),
                "server": str(server),
                "account_type": str(account_type),
                "balance": float(getattr(info, "balance", 0.0) or 0.0),
                "equity": float(getattr(info, "equity", 0.0) or 0.0),
                "free_margin": float(getattr(info, "margin_free", 0.0) or 0.0),
                "profit": float(getattr(info, "profit", 0.0) or 0.0),
                "currency": str(getattr(info, "currency", "USD") or "USD"),
            },
        )
        return result

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
        if self.mt5 is None or not self.connected or self.account is None:
            return {
                "connected": False,
                "balance": 0.0,
                "equity": 0.0,
                "margin": 0.0,
                "free_margin": 0.0,
                "profit": 0.0,
            }

        try:
            info = self.mt5.account_info()
            if info is None:
                return {
                    "connected": False,
                    "balance": 0.0,
                    "equity": 0.0,
                    "margin": 0.0,
                    "free_margin": 0.0,
                    "profit": 0.0,
                }

            return {
                "connected": True,
                "balance": float(getattr(info, "balance", 0.0) or 0.0),
                "equity": float(getattr(info, "equity", 0.0) or 0.0),
                "margin": float(getattr(info, "margin", 0.0) or 0.0),
                "free_margin": float(getattr(info, "margin_free", 0.0) or 0.0),
                "profit": float(getattr(info, "profit", 0.0) or 0.0),
            }
        except Exception:
            return {
                "connected": False,
                "balance": 0.0,
                "equity": 0.0,
                "margin": 0.0,
                "free_margin": 0.0,
                "profit": 0.0,
            }

    def symbols(self) -> list[dict[str, Any]]:
        if self.mt5 is None or not self.connected:
            return []
        try:
            raw_symbols = self.mt5.symbols_get()
            if raw_symbols is None:
                return []
            result: list[dict[str, Any]] = []
            for symbol in raw_symbols[:25]:
                info = self.mt5.symbol_info(symbol.name)
                if info is None:
                    continue
                result.append(
                    {
                        "symbol": symbol.name,
                        "description": getattr(info, "description", ""),
                        "digits": getattr(info, "digits", 5),
                        "bid": float(getattr(info, "bid", 0.0) or 0.0),
                        "ask": float(getattr(info, "ask", 0.0) or 0.0),
                        "spread": float(getattr(info, "spread", 0.0) or 0.0),
                    }
                )
            return result
        except Exception:
            return []

    def symbol(self, symbol_name: str) -> dict[str, Any] | None:
        if self.mt5 is None or not self.connected:
            return None
        try:
            info = self.mt5.symbol_info(symbol_name)
            if info is None:
                return None
            return {
                "symbol": symbol_name,
                "description": getattr(info, "description", ""),
                "digits": getattr(info, "digits", 5),
                "bid": float(getattr(info, "bid", 0.0) or 0.0),
                "ask": float(getattr(info, "ask", 0.0) or 0.0),
                "spread": float(getattr(info, "spread", 0.0) or 0.0),
            }
        except Exception:
            return None

    def positions(self) -> list[dict[str, Any]]:
        if self.mt5 is None or not self.connected:
            return []

        try:
            raw_positions = self.mt5.positions_get()
            if raw_positions is None:
                return []

            result: list[dict[str, Any]] = []
            for position in raw_positions:
                result.append(
                    {
                        "ticket": int(getattr(position, "ticket", 0) or 0),
                        "symbol": getattr(position, "symbol", ""),
                        "volume": float(getattr(position, "volume", 0.0) or 0.0),
                        "profit": float(getattr(position, "profit", 0.0) or 0.0),
                        "swap": float(getattr(position, "swap", 0.0) or 0.0),
                        "comment": getattr(position, "comment", ""),
                        "type": getattr(position, "type", 0),
                        "price_open": float(getattr(position, "price_open", 0.0) or 0.0),
                        "price_current": float(getattr(position, "price_current", 0.0) or 0.0),
                    }
                )
            return result
        except Exception:
            return []

    def open_trade_count(self) -> int:
        """Return the number of open live MT5 positions."""
        if not self.connected or self.mt5 is None:
            return 0
        return len(self.positions())

    def open_trade_summary(self) -> dict[str, float | int]:
        """Return the aggregate open-trade volume and profit for risk checks."""
        if not self.connected or self.mt5 is None:
            return {"count": 0, "volume": 0.0, "profit": 0.0}

        positions = self.positions()
        return {
            "count": len(positions),
            "volume": sum(float(item.get("volume", 0.0)) for item in positions),
            "profit": sum(float(item.get("profit", 0.0)) for item in positions),
        }


__all__ = ["MT5ConnectionResult", "MT5LiveService"]
