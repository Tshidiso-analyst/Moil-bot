"""Fail-closed high-impact event-day filter for ICT trade candidates.

This module consumes an externally sourced, timestamped event list. It does
not scrape or invent a calendar. If verified calendar data is unavailable,
the caller is told to block execution rather than assume the day is clear.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Iterable, Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pandas as pd


def relevant_currencies(symbol: str) -> set[str]:
    token = "".join(ch for ch in str(symbol).upper() if ch.isalnum())
    if token in {"XAUUSD", "GOLD", "XAGUSD", "SILVER", "US30", "DJ30", "DOW30",
                 "NAS100", "USTEC", "US100", "SPX500", "US500", "SP500"}:
        return {"USD"}
    if len(token) == 6 and token.isalpha():
        return {token[:3], token[3:]}
    if token in {"GER40", "DAX40", "DE40"}:
        return {"EUR"}
    if token in {"UK100", "FTSE100"}:
        return {"GBP"}
    return set()


def high_impact_event_day_guard(
    symbol: str,
    candidate_timestamp: Any,
    events: Iterable[Mapping[str, Any]] | None,
    *,
    trading_timezone: str = "America/New_York",
) -> tuple[bool, str]:
    """Return (allowed, reason); block if calendar data is absent or invalid."""
    if events is None:
        return False, "Verified economic-calendar data is unavailable; fail-closed news filter blocks execution."
    try:
        zone = ZoneInfo(trading_timezone)
    except (ZoneInfoNotFoundError, TypeError, ValueError):
        raise ValueError("trading_timezone must be a valid IANA timezone.") from None
    candidate = pd.Timestamp(candidate_timestamp)
    if pd.isna(candidate):
        raise ValueError("candidate_timestamp must be a valid timestamp.")
    if candidate.tzinfo is None:
        candidate = candidate.tz_localize("UTC")
    local_day = candidate.tz_convert(zone).date()
    currencies = relevant_currencies(symbol)
    if not currencies:
        return False, f"Cannot determine event currencies for {symbol}; execution blocked."
    matched = []
    for event in events:
        try:
            impact = str(event["impact"]).strip().lower()
            currency = str(event["currency"]).strip().upper()
            timestamp = pd.Timestamp(event["timestamp"])
            if pd.isna(timestamp):
                raise ValueError
            if timestamp.tzinfo is None:
                timestamp = timestamp.tz_localize("UTC")
        except (KeyError, TypeError, ValueError):
            return False, "Economic-calendar record is malformed; execution blocked."
        if impact in {"high", "3", "red"} and currency in currencies:
            if timestamp.tz_convert(zone).date() == local_day:
                matched.append(f"{currency} {event.get('name', 'high-impact event')}")
    if matched:
        return False, "High-impact event day for this instrument: " + ", ".join(sorted(set(matched))) + "."
    return True, "No matching high-impact event recorded for this instrument on this trading day."


__all__ = ["high_impact_event_day_guard", "relevant_currencies"]
