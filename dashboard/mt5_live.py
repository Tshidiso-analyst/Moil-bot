from __future__ import annotations

import os
from typing import Any

try:
    import MetaTrader5 as mt5
except ImportError:  # pragma: no cover - optional dependency at runtime
    mt5 = None


class MT5LiveService:
    """Live MT5 status, account summary, and open-position monitoring."""

    def __init__(self, mt5_module: Any | None = None, path: str | None = None):
        self.mt5 = mt5_module or mt5
        self.path = path or os.getenv("MT5_PATH", r"C:\Program Files\MetaTrader 5\terminal64.exe")
        self.connected = False

    def connect(self) -> bool:
        if self.mt5 is None:
            self.connected = False
            return False

        try:
            self.connected = bool(self.mt5.initialize(path=self.path))
        except Exception:
            self.connected = False
        return self.connected

    def disconnect(self) -> None:
        if self.mt5 is not None:
            try:
                self.mt5.shutdown()
            except Exception:
                pass
        self.connected = False

    def account_summary(self) -> dict[str, float | int | bool]:
        if self.mt5 is None or not self.connected:
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
                "balance": float(info.balance or 0.0),
                "equity": float(info.equity or 0.0),
                "margin": float(info.margin or 0.0),
                "free_margin": float(info.margin_free or 0.0),
                "profit": float(info.profit or 0.0),
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


__all__ = ["MT5LiveService"]
