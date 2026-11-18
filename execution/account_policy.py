"""Explicit MT5 account-mode policy. REAL routing is not enabled by this module."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AccountPolicy:
    """Account-mode configuration, deliberately fail-closed for real money."""

    mode: str = "demo"
    execution_enabled: bool = False
    real_trading_approved: bool = False
    kill_switch: bool = False

    def verify(self, mt5: Any, account: Any) -> None:
        if self.kill_switch:
            raise RuntimeError("Emergency kill switch is active.")
        if not self.execution_enabled:
            raise RuntimeError("MT5 execution is disabled.")
        if self.mode not in {"demo", "real"}:
            raise RuntimeError("Unsupported MT5 account mode.")
        if account is None:
            raise RuntimeError("MT5 account information is unavailable.")
        if self.mode == "real":
            if not self.real_trading_approved:
                raise RuntimeError("REAL trading requires separate explicit authorization.")
            # Intentionally not yet routable: broker integration and real-mode
            # acceptance tests must be completed before removing this block.
            raise RuntimeError("REAL order routing is pending broker acceptance testing.")
        demo = getattr(mt5, "ACCOUNT_TRADE_MODE_DEMO", None)
        if demo is None or getattr(account, "trade_mode", None) != demo:
            raise RuntimeError("DEMO policy refuses a non-DEMO account.")
        if not bool(getattr(account, "trade_allowed", False)) or not bool(getattr(account, "trade_expert", False)):
            raise RuntimeError("MT5 account or expert trading permission is disabled.")
