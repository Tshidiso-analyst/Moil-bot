"""Portfolio-wide daily entry limit using New York calendar dates.

This is a reusable risk helper. Callers must supply the portfolio's executed
entry records; it does not fetch broker history or enable order execution.
"""
from __future__ import annotations

from datetime import datetime, timezone
from numbers import Integral
from typing import Any, Iterable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

NEW_YORK = ZoneInfo("America/New_York")


def _as_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        if not text:
            raise ValueError("timestamp must not be empty")
        if text.endswith(("Z", "z")):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
    # Naive broker/history timestamps are treated as UTC, consistently with
    # the market-data pipeline.
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def portfolio_daily_trade_guard(
    trades: Iterable[dict[str, Any]],
    *,
    candidate_timestamp: Any,
    max_trades_per_day: int = 10,
    timezone_name: str = "America/New_York",
) -> tuple[bool, str]:
    """Allow an entry only while the portfolio has fewer than N NY-day entries.

    All symbols share the same portfolio limit. Invalid input fails closed.
    """
    if isinstance(max_trades_per_day, bool) or not isinstance(max_trades_per_day, Integral) or max_trades_per_day <= 0:
        raise ValueError("max_trades_per_day must be a positive integer")
    try:
        market_tz = ZoneInfo(timezone_name)
        candidate_day = _as_timestamp(candidate_timestamp).astimezone(market_tz).date()
        entries = list(trades)
        count = 0
        for trade in entries:
            if not isinstance(trade, dict) or "entry_time" not in trade:
                raise ValueError("every trade must contain entry_time")
            entry_day = _as_timestamp(trade["entry_time"]).astimezone(market_tz).date()
            if entry_day == candidate_day:
                count += 1
    except (TypeError, ValueError, ZoneInfoNotFoundError, OverflowError):
        return False, "Daily trade guard rejected invalid portfolio timestamps or timezone."

    if count >= max_trades_per_day:
        return False, (
            f"Daily entry limit reached: {count}/{max_trades_per_day} "
            "across all instruments for the New York calendar day."
        )
    return True, f"Daily entry limit available: {count}/{max_trades_per_day}."
