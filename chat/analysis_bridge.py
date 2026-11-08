from __future__ import annotations

from typing import Any

from chat.service import ChatMessage, chat_service


def format_pipeline_summary(result: Any) -> str:
    """Build a short plain-language summary from a RealTimePipelineResult-like object."""
    context = getattr(result, "market_context", {}) or {}
    session = context.get("session", "unknown")
    trend = context.get("trend", getattr(result, "direction", "neutral"))
    bias = context.get("bias", trend)
    premium_discount = context.get("premium_discount", "neutral")
    sweeps = context.get("liquidity_sweeps", 0)
    gaps = context.get("fair_value_gaps", 0)

    return (
        f"Session {session}. Trend {trend}, bias {bias}, "
        f"zone {premium_discount}. "
        f"Liquidity sweeps: {sweeps}. Fair value gaps: {gaps}."
    )


def post_pipeline_result(result: Any, room: str = "analysis") -> ChatMessage:
    """Post an explainable analysis card for a pipeline evaluation into chat."""
    summary = format_pipeline_summary(result)
    levels = {
        "entry": getattr(result, "entry", None),
        "stop_loss": getattr(result, "stop_loss", None),
        "take_profit": getattr(result, "take_profit", None),
    }
    reasons = list(getattr(result, "reasons", []) or [])
    return chat_service.post_analysis(
        symbol=str(getattr(result, "symbol", "UNKNOWN")),
        summary=summary,
        direction=str(getattr(result, "direction", "neutral")),
        status=str(getattr(result, "status", "watch")),
        reasons=reasons,
        levels=levels,
        room=room,
    )


__all__ = ["format_pipeline_summary", "post_pipeline_result"]
