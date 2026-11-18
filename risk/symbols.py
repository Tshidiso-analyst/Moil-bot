"""Canonical symbol policy for the current Moil-bot instrument scope."""
from __future__ import annotations

import re


_XAUUSD_ALIAS = re.compile(r"^XAUUSD(?:[._-][A-Z0-9]+|[A-Z])?$", re.IGNORECASE)


def canonicalize_symbol(symbol: str) -> str:
    """Return canonical XAUUSD for supported broker suffix aliases.

    Examples accepted: XAUUSD, XAUUSD.a, XAUUSD-pro, XAUUSDm.
    Other instruments and ambiguous multi-symbol strings are rejected.
    """
    value = str(symbol or "").strip().upper()
    if not value:
        raise ValueError("Symbol must not be empty.")
    if not _XAUUSD_ALIAS.fullmatch(value):
        raise ValueError("Moil-bot currently supports XAUUSD only.")
    return "XAUUSD"


__all__ = ["canonicalize_symbol"]
