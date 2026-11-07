from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timezone
from typing import Iterable
from zoneinfo import ZoneInfo

from fundamentals.event_risk import EconomicEvent


NEW_YORK = ZoneInfo("America/New_York")
NYSE_OPEN = time(9, 30)
OPENING_HOUR_END = time(10, 30)


@dataclass(frozen=True)
class EntryConfirmationDecision:
    qualified: bool
    direction: str
    entry_model: str
    assessed_at: datetime
    reasons: tuple[str, ...]
    execution_approved: bool = False


class EntryConfirmationEvaluator:
    """Apply the user's conservative NY opening-hour research checklist.

    A qualified result means only that supplied evidence passed this checklist.
    It is not a broker instruction, position-size calculation, validated edge,
    or permission to execute. MT5 execution remains outside this module.
    """

    def evaluate(
        self,
        *,
        symbol: str,
        direction: str,
        assessed_at: datetime,
        event_calendar_verified: bool,
        events: Iterable[EconomicEvent],
        macro_bias_valid: bool,
        daily_trade_count: int,
        risk_percent: float,
        liquidity_sweep_confirmed: bool,
        sweep_reversal_direction: str,
        bos_direction: str,
        bos_body_close_confirmed: bool,
        fvg_retracement_confirmed: bool = False,
        order_block_retest_confirmed: bool = False,
    ) -> EntryConfirmationDecision:
        normalized_symbol = str(symbol or "").strip().upper()
        normalized_direction = str(direction or "").strip().lower()
        if not normalized_symbol:
            raise ValueError("symbol must not be empty.")
        if normalized_direction not in {"bullish", "bearish"}:
            raise ValueError("direction must be bullish or bearish.")
        if assessed_at.tzinfo is None or assessed_at.utcoffset() is None:
            raise ValueError("assessed_at must be timezone-aware.")
        if isinstance(daily_trade_count, bool) or daily_trade_count < 0:
            raise ValueError("daily_trade_count must be a non-negative integer.")
        if isinstance(daily_trade_count, float) and not daily_trade_count.is_integer():
            raise ValueError("daily_trade_count must be a non-negative integer.")
        if isinstance(risk_percent, bool) or not isinstance(risk_percent, (int, float)):
            raise ValueError("risk_percent must be numeric.")
        if risk_percent <= 0:
            raise ValueError("risk_percent must be greater than zero.")

        local_time = assessed_at.astimezone(NEW_YORK)
        reasons: list[str] = []

        if local_time.weekday() >= 5:
            reasons.append("The New York date is a weekend; the NYSE is not in its regular weekday session.")
        elif not (NYSE_OPEN <= local_time.time().replace(tzinfo=None) < OPENING_HOUR_END):
            reasons.append("Outside the permitted NYSE opening hour (09:30–10:30 America/New_York).")

        if daily_trade_count >= 1:
            reasons.append("The one-trade-per-day limit has already been reached.")

        if float(risk_percent) > 1.0:
            reasons.append("Planned risk exceeds the 1% maximum per trade.")

        if not event_calendar_verified:
            reasons.append("Economic calendar is unverified; event-day clearance cannot be established.")
        else:
            relevant_events = [
                event for event in events
                if event.impact == "high"
                and event.currency.upper() in normalized_symbol
                and event.scheduled_at.astimezone(NEW_YORK).date() == local_time.date()
            ]
            if relevant_events:
                names = ", ".join(sorted({event.name for event in relevant_events}))
                reasons.append(f"High-impact event day for {normalized_symbol}: {names}. No trade on this event day.")

        if not macro_bias_valid:
            reasons.append("A separately verified macro bias aligned with the setup has not been supplied.")

        if not liquidity_sweep_confirmed:
            reasons.append("A confirmed liquidity sweep is required.")
        elif str(sweep_reversal_direction).strip().lower() != normalized_direction:
            reasons.append("The liquidity-sweep reversal direction does not match the proposed setup.")

        if str(bos_direction).strip().lower() != normalized_direction:
            reasons.append("BOS direction does not match the proposed setup.")
        if not bos_body_close_confirmed:
            reasons.append("BOS must be confirmed by a candle-body close; a wick-only break is not accepted.")

        if not (fvg_retracement_confirmed or order_block_retest_confirmed):
            reasons.append("Wait for a confirmed FVG retracement or order-block retest entry location.")

        qualified = not reasons
        if qualified:
            entry_model = (
                "liquidity_sweep_bos_fvg_retracement"
                if fvg_retracement_confirmed
                else "liquidity_sweep_bos_order_block_retest"
            )
            reasons.append("All configured research checklist conditions passed; independent rule validation is still required.")
        else:
            entry_model = "none"

        return EntryConfirmationDecision(
            qualified=qualified,
            direction=normalized_direction,
            entry_model=entry_model,
            assessed_at=assessed_at.astimezone(timezone.utc),
            reasons=tuple(reasons),
            execution_approved=False,
        )


__all__ = [
    "EntryConfirmationDecision",
    "EntryConfirmationEvaluator",
    "NEW_YORK",
    "NYSE_OPEN",
    "OPENING_HOUR_END",
]
