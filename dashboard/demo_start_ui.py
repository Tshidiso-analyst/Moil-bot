from __future__ import annotations

from typing import Any

from execution.demo_start import DemoStartController, DemoStartResult
from chat.execution_bridge import post_demo_start_result
from chat.service import chat_service


def list_reviewed_rules() -> list[dict[str, Any]]:
    try:
        return DemoStartController().reviewed_rules()
    except Exception:
        return []


def run_demo_start_dry_run(
    *,
    symbol: str,
    dataframe: Any,
    account_mode: str = "DEMO",
) -> DemoStartResult:
    result = DemoStartController().start(
        symbol=symbol,
        dataframe=dataframe,
        account_mode=account_mode,
        allow_execution=False,
        proposed_risk_percent=0.5,
        fundamental_bias="neutral",
        high_impact_news=False,
    )
    try:
        post_demo_start_result(result)
    except Exception:
        pass
    return result


def result_to_session_dict(result: DemoStartResult) -> dict[str, Any]:
    return {
        "status": result.status,
        "direction": result.direction,
        "reason": result.reason,
        "rule_id": result.rule_id,
        "rule_name": result.rule_name,
        "dry_run": result.dry_run,
        "symbol": result.symbol,
    }


def latest_signal_message() -> str | None:
    messages = chat_service.list_messages("signals", limit=1)
    if not messages:
        return None
    return messages[-1].message


__all__ = [
    "list_reviewed_rules",
    "run_demo_start_dry_run",
    "result_to_session_dict",
    "latest_signal_message",
]
