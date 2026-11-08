from __future__ import annotations

from typing import Any

from chat.service import ChatMessage, chat_service


def format_demo_start_result(result: Any) -> str:
    symbol = str(getattr(result, "symbol", "UNKNOWN")).upper()
    status = str(getattr(result, "status", "unknown"))
    direction = str(getattr(result, "direction", "neutral"))
    mode = str(getattr(result, "mode", "UNKNOWN"))
    reason = str(getattr(result, "reason", "")).strip()
    rule_name = getattr(result, "rule_name", None)
    rule_id = getattr(result, "rule_id", None)
    dry_run = bool(getattr(result, "dry_run", True))

    lines = [
        f"**Demo Start · {symbol}**",
        f"Mode: {mode} · Status: {status} · Direction: {direction}",
    ]
    if rule_name or rule_id:
        lines.append(f"Rule: {rule_name or 'unnamed'} ({rule_id or 'no-id'})")

    levels = []
    for key, label in (
        ("entry", "entry"),
        ("stop_loss", "stop"),
        ("take_profit", "target"),
        ("volume", "volume"),
        ("order_ticket", "ticket"),
    ):
        value = getattr(result, key, None)
        if value is not None:
            levels.append(f"{label}={value}")
    if levels:
        lines.append("Plan: " + ", ".join(levels))

    if reason:
        lines.append(reason)

    reasons = list(getattr(result, "reasons", []) or [])
    for item in reasons[:4]:
        lines.append(f"- {item}")

    if dry_run:
        lines.append("Dry-run: no broker order was sent.")
    return "\n".join(lines)


def post_demo_start_result(
    result: Any,
    *,
    room: str = "signals",
    author: str = "Moil Execution",
) -> ChatMessage:
    message = format_demo_start_result(result)
    return chat_service.post_message(author=author, message=message, room=room)


__all__ = ["format_demo_start_result", "post_demo_start_result"]
