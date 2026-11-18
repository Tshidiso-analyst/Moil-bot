"""Broker tick freshness guard for new XAUUSD entries."""
from __future__ import annotations

import math
import time
from typing import Any


def require_fresh_tick(tick: Any, *, max_age_seconds: float = 30.0) -> None:
    """Reject absent, future-dated, or stale broker ticks before new orders."""
    timestamp = getattr(tick, "time", None)
    if isinstance(timestamp, bool) or timestamp is None:
        raise RuntimeError("Broker quote timestamp is unavailable.")
    try:
        timestamp = float(timestamp)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Broker quote timestamp is invalid.") from exc
    now = time.time()
    if not math.isfinite(timestamp) or timestamp <= 0 or timestamp > now + 2:
        raise RuntimeError("Broker quote timestamp is invalid or in the future.")
    if now - timestamp > max_age_seconds:
        raise RuntimeError("Broker quote is stale; new order rejected.")
