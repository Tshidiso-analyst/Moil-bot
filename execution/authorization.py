"""Fail-closed checks for strategy authorization of new gold entries.

An enabled broker adapter is not sufficient authorization for an entry.
"""
from __future__ import annotations

from typing import Any

from risk.symbols import canonicalize_symbol


def require_strategy_authorization(assessment: Any, *, symbol: str, direction: str) -> None:
    """Require an explicit confirmed assessment; reject unvalidated entry requests."""
    canonicalize_symbol(symbol)
    if assessment is None:
        raise RuntimeError("Validated strategy assessment is required for new orders.")
    canonicalize_symbol(getattr(assessment, "symbol", ""))
    expected = "bullish" if direction in {"buy", "bullish"} else "bearish"
    if str(getattr(assessment, "direction", "")).lower() != expected:
        raise RuntimeError("Strategy assessment direction does not match the order.")
    required = ("setup_valid", "confirmation", "structure_valid", "liquidity_valid", "macro_bias_valid")
    if any(getattr(assessment, field, None) is not True for field in required):
        raise RuntimeError("Strategy assessment confirmation or safety checks are incomplete.")
    if getattr(assessment, "high_impact_news", None) is not False:
        raise RuntimeError("Strategy assessment has unverified or prohibited high-impact news.")
