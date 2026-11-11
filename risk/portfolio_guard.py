"""Portfolio-wide daily trade-count guard across all instruments.

Call this at the portfolio/execution boundary with the account's trades for
the trading day. It is stateless by design; callers must supply broker/account
records rather than relying on a process-local counter.
"""
from __future__ import annotations

from datetime import date
from typing import Iterable, Mapping, Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pandas as pd


def portfolio_daily_trade_guard(
    trades: Iterable[Mapping[str, Any]],
    *,
    candidate_timestamp: Any,
    max_trades_per_day: int = 1,
    trading_timezone: str = "America/New_York",
) -> tuple[bool, str]:
    """Return whether another trade is permitted across the whole portfolio."""
    if isinstance(max_trades_per_day, bool) or not isinstance(max_trades_per_day, int) or max_trades_per_day < 1:
        raise ValueError("max_trades_per_day must be a positive integer.")
    try:
        zone = ZoneInfo(trading_timezone)
    except (ZoneInfoNotFoundError, TypeError, ValueError):
        raise ValueError("trading_timezone must be a valid IANA timezone.") from None

    candidate = pd.Timestamp(candidate_timestamp)
    if pd.isna(candidate):
        raise ValueError("candidate_timestamp must be a valid timestamp.")
    if candidate.tzinfo is None:
        candidate = candidate.tz_localize("UTC")
    candidate_day = candidate.tz_convert(zone).date()

    count = 0
    for trade in trades:
        raw = trade.get("timestamp") or trade.get("time") or trade.get("entry_time")
        if raw is None:
            continue
        stamp = pd.Timestamp(raw)
        if pd.isna(stamp):
            continue
        if stamp.tzinfo is None:
            stamp = stamp.tz_localize("UTC")
        if stamp.tz_convert(zone).date() == candidate_day:
            count += 1
    if count >= max_trades_per_day:
        return False, (f"Portfolio daily trade limit reached: {count}/{max_trades_per_day} "
                       f"across all instruments for {candidate_day}.")
    return True, f"Portfolio daily trade allowance available: {count}/{max_trades_per_day}."


__all__ = ["portfolio_daily_trade_guard"]
