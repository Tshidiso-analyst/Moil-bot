"""Fail-closed MT5 DEMO/REAL account policy for XAUUSD execution."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AccountPolicy:
    """REAL requires two independent explicit flags; execution defaults off."""

    mode: str = "demo"
    execution_enabled: bool = False
    real_trading_approved: bool = False
    kill_switch: bool = False

    def verify(self, mt5: Any, account: Any) -> None:
        if self.kill_switch is not False:
            raise RuntimeError("Emergency kill switch is active.")
        if self.execution_enabled is not True:
            raise RuntimeError("MT5 execution is disabled.")
        if self.mode not in {"demo", "real"}:
            raise RuntimeError("Unsupported MT5 account mode.")
        if account is None:
            raise RuntimeError("MT5 account information is unavailable.")
        if self.mode == "real":
            if self.real_trading_approved is not True:
                raise RuntimeError("REAL trading requires separate explicit authorization.")
            expected = getattr(mt5, "ACCOUNT_TRADE_MODE_REAL", None)
            if expected is None or getattr(account, "trade_mode", None) != expected:
                raise RuntimeError("REAL policy refuses an unverified REAL account.")
        else:
            expected = getattr(mt5, "ACCOUNT_TRADE_MODE_DEMO", None)
            if expected is None or getattr(account, "trade_mode", None) != expected:
                raise RuntimeError("DEMO policy refuses a non-DEMO account.")
        if not bool(getattr(account, "trade_allowed", False)) or not bool(getattr(account, "trade_expert", False)):
            raise RuntimeError("MT5 account or expert trading permission is disabled.")
