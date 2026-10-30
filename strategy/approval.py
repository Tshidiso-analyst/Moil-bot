from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from analysis.smc_patterns import analyze_market_context


@dataclass(frozen=True)
class TradeApprovalRequest:
    symbol: str
    direction: str
    session: str
    trend: str
    entry: float | None
    stop_loss: float | None
    take_profit: float | None
    risk_percent: float
    reasons: tuple[str, ...] = ()
    status: str = "pending"
    approval_required: bool = True
    notes: str = ""


def build_approval_request(
    symbol: str,
    dataframe: pd.DataFrame,
    *,
    fundamental_bias: str = "neutral",
    proposed_risk_percent: float = 0.5,
    daily_loss_percent: float = 0.0,
    open_trades: int = 0,
    high_impact_news: bool = False,
) -> TradeApprovalRequest:
    if dataframe.empty:
        raise ValueError("dataframe must not be empty")

    context = analyze_market_context(dataframe)
    direction = "neutral"

    if context.trend == "bullish" and not context.distribution:
        direction = "bullish"
    elif context.trend == "bearish" and not context.distribution:
        direction = "bearish"

    if fundamental_bias in {"bullish", "bearish"} and direction != "neutral":
        if fundamental_bias != direction:
            direction = "neutral"

    if context.session not in {"london", "new_york", "london_new_york_overlap"}:
        direction = "neutral"

    if context.consolidation:
        direction = "neutral"

    reasons = list(context.reasons)
    if direction == "neutral":
        reasons.append("No trade approval is granted because the market context does not satisfy the confirmation rules.")
        return TradeApprovalRequest(
            symbol=str(symbol).upper(),
            direction="neutral",
            session=context.session,
            trend=context.trend,
            entry=None,
            stop_loss=None,
            take_profit=None,
            risk_percent=proposed_risk_percent,
            reasons=tuple(reasons),
            status="rejected",
            approval_required=True,
            notes="Manual approval required after the bot decides the setup is valid.",
        )

    last_close = float(dataframe["close"].iloc[-1])
    last_low = float(dataframe["low"].iloc[-1])
    last_high = float(dataframe["high"].iloc[-1])

    if direction == "bullish":
        entry = last_close
        stop_loss = min(last_low, last_close * 0.998)
        take_profit = max(last_high, last_close * 1.008)
    else:
        entry = last_close
        stop_loss = max(last_high, last_close * 1.002)
        take_profit = min(last_low, last_close * 0.992)

    reasons.append(
        f"Approval required before execution: {symbol} {direction} risk={proposed_risk_percent}% daily_loss={daily_loss_percent}% open_trades={open_trades}."
    )
    if high_impact_news:
        reasons.append("High-impact macro event is active; the bot should not execute without explicit user approval.")

    return TradeApprovalRequest(
        symbol=str(symbol).upper(),
        direction=direction,
        session=context.session,
        trend=context.trend,
        entry=entry,
        stop_loss=stop_loss,
        take_profit=take_profit,
        risk_percent=proposed_risk_percent,
        reasons=tuple(reasons),
        status="pending",
        approval_required=True,
        notes="Human approval required before demo execution.",
    )


def approve_request(request: TradeApprovalRequest, approved: bool, *, note: str = "") -> TradeApprovalRequest:
    if not isinstance(request, TradeApprovalRequest):
        raise TypeError("request must be a TradeApprovalRequest")

    status = "approved" if approved else "rejected"
    note_text = note.strip()
    return TradeApprovalRequest(
        symbol=request.symbol,
        direction=request.direction,
        session=request.session,
        trend=request.trend,
        entry=request.entry,
        stop_loss=request.stop_loss,
        take_profit=request.take_profit,
        risk_percent=request.risk_percent,
        reasons=request.reasons,
        status=status,
        approval_required=True,
        notes=note_text or ("Approved by human operator." if approved else "Rejected by human operator."),
    )


__all__ = ["TradeApprovalRequest", "approve_request", "build_approval_request"]
