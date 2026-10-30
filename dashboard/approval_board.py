from __future__ import annotations

from typing import Any


def render_trade_approval_card(request: Any) -> str:
    """Render a summary card for the dashboard so the trade plan is visible and approval is explicit."""
    symbol = getattr(request, "symbol", "UNKNOWN")
    direction = getattr(request, "direction", "neutral")
    session = getattr(request, "session", "unknown")
    trend = getattr(request, "trend", "neutral")
    entry = getattr(request, "entry", None)
    stop_loss = getattr(request, "stop_loss", None)
    take_profit = getattr(request, "take_profit", None)
    risk = getattr(request, "risk_percent", 0.0)
    status = getattr(request, "status", "pending")
    notes = getattr(request, "notes", "")
    reasons = list(getattr(request, "reasons", ()))

    reasons_html = "".join(f"<li>{reason}</li>" for reason in reasons[:6])
    entry_html = f"<p><strong>Entry:</strong> {entry}</p>" if entry is not None else "<p><strong>Entry:</strong> n/a</p>"
    sl_html = f"<p><strong>Stop:</strong> {stop_loss}</p>" if stop_loss is not None else "<p><strong>Stop:</strong> n/a</p>"
    tp_html = f"<p><strong>Target:</strong> {take_profit}</p>" if take_profit is not None else "<p><strong>Target:</strong> n/a</p>"

    return f"""
    <div class="card" style="margin-top:20px;">
        <h3>{symbol} trade approval</h3>
        <div class="status demo">{status.upper()}</div>
        <p class="muted">
            Direction: <strong>{direction}</strong> • Session: <strong>{session}</strong> • Trend: <strong>{trend}</strong>
        </p>
        {entry_html}
        {sl_html}
        {tp_html}
        <p><strong>Risk:</strong> {risk}%</p>
        <p class="muted">{notes}</p>
        <ul>
            {reasons_html}
        </ul>
        <div style="display:flex; gap:10px; flex-wrap:wrap; margin-top:12px;">
            <button type="button">Approve Trade</button>
            <button type="button" style="background: linear-gradient(135deg, #ff5d5d, #a31545);">Reject Trade</button>
        </div>
    </div>
    """
