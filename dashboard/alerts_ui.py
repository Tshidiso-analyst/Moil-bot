from __future__ import annotations

import html

from alerts.engine import AlertEngine
from alerts.models import VALID_SEVERITIES


# One shared engine instance for this dashboard process.
# Alert persistence and automatic producers will be integrated separately.
alert_engine = AlertEngine()


def _e(value) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def render_alerts_content(notice: str = "", error: str = "") -> str:
    alerts = sorted(
        alert_engine.get_all_alerts(),
        key=lambda item: item.created_at,
        reverse=True,
    )

    statuses = ("new", "acknowledged", "resolved")
    counts = {
        status: sum(1 for alert in alerts if alert.status == status)
        for status in statuses
    }

    pieces = []

    if notice:
        pieces.append(
            '<div class="card" role="status" '
            'style="margin-bottom:16px;">'
            + _e(notice) + "</div>"
        )

    if error:
        pieces.append(
            '<div class="card" role="alert" '
            'style="margin-bottom:16px;border-left:4px solid #dc2626;">'
            + _e(error) + "</div>"
        )

    pieces.append("""
    <section class="grid"
        style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;">
    """)

    for status in statuses:
        pieces.append(
            '<div class="card"><div class="muted">'
            + _e(status.title())
            + '</div><h2 style="margin:8px 0;">'
            + str(counts[status])
            + "</h2></div>"
        )

    pieces.append("</section>")

    severity_values = sorted(VALID_SEVERITIES)
    default_severity = (
        "warning" if "warning" in VALID_SEVERITIES
        else severity_values[0]
    )

    options = "".join(
        '<option value="' + _e(severity) + '"' +
        (" selected" if severity == default_severity else "") +
        ">" + _e(severity.title()) + "</option>"
        for severity in severity_values
    )

    pieces.append("""
    <section class="card" style="margin-top:16px;">
      <h2>Automatic alert monitoring</h2>
      <p>
        This feed is intended for strategy signals, economic events,
        execution updates and risk warnings.
      </p>
      <p class="muted">
        Automatic event producers are not connected yet. Do not rely on
        this page for live trading alerts until that integration is complete.
      </p>
    </section>
    """)

    pieces.append('<section class="card" style="margin-top:16px;">')
    pieces.append("<h2>Alert history</h2>")

    if not alerts:
        pieces.append("""
        <p>No alerts have been generated in this dashboard process yet.</p>
        <p class="muted">
          Automatic event producers are not connected to the shared engine yet.
          Automatic event producers are not connected, so live market alerts are not generated yet.
          Alert history is currently held in memory and will not survive a process restart.
        </p>
        """)
    else:
        for alert in alerts:
            created = alert.created_at.strftime("%Y-%m-%d %H:%M UTC")

            pieces.append(
                '<article style="padding:14px 0;border-bottom:1px solid #d1d5db;">'
                '<div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center;">'
                '<strong>' + _e(alert.title) + '</strong>'
                '<span class="muted">' + _e(alert.severity.title()) + '</span>'
                '<span class="muted">Status: ' + _e(alert.status.title()) + '</span>'
                '</div>'
                '<p>' + _e(alert.message) + '</p>'
                '<p class="muted">Symbol: ' + _e(alert.symbol)
                + ' | Type: ' + _e(alert.alert_type)
                + ' | Created: ' + _e(created)
                + ' | ID: ' + _e(alert.alert_id) + '</p>'
                + (
                    '<form method="post" action="/alerts/action" '
                    'style="display:inline-block;margin-right:8px;">'
                    '<input type="hidden" name="action" value="acknowledge">'
                    '<input type="hidden" name="alert_id" value="'
                    + _e(alert.alert_id) + '">'
                    '<button type="submit">Acknowledge</button></form>'
                    if alert.status == "new" else ""
                )
                + (
                    '<form method="post" action="/alerts/action" '
                    'style="display:inline-block;">'
                    '<input type="hidden" name="action" value="resolve">'
                    '<input type="hidden" name="alert_id" value="'
                    + _e(alert.alert_id) + '">'
                    '<button type="submit">Resolve</button></form>'
                    if alert.status != "resolved" else ""
                )
                + "</article>"
            )

    pieces.append("</section>")
    return "\n".join(pieces)


def handle_alert_action(form: dict[str, str]) -> str:
    action = form.get("action", "").strip()

    if action == "create":
        raise ValueError(
            "Manual alert creation is disabled. Alerts must come "
            "from automated market, strategy, news or risk events."
        )

    alert_id = form.get("alert_id", "").strip()
    if not alert_id:
        raise ValueError("Alert ID is required.")

    if action == "acknowledge":
        alert_engine.acknowledge(alert_id)
        return "Alert acknowledged."

    if action == "resolve":
        alert_engine.resolve(alert_id)
        return "Alert resolved."

    raise ValueError("Unsupported alert action.")
