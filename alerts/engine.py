from datetime import datetime, timezone
from uuid import uuid4

from alerts.models import Alert, AlertEvent, NotificationSettings
from alerts.notifications import NotificationResult, NotificationService
from alerts.store import AlertStore


ALERT_SETTING_MAP = {
    "trade_entered": "trade_entered",
    "stop_loss_hit": "stop_loss_hit",
    "take_profit_hit": "take_profit_hit",
    "fundamental_event": "fundamental_events",
    "setup_qualified": "technical_setup_alerts",
    "risk_warning": "risk_warnings",
    "thesis_weakening": "trade_explanations",
    "thesis_invalidated": "trade_explanations",
}


class AlertDispatch:
    def __init__(
        self,
        alert: Alert,
        notifications: list[NotificationResult],
    ):
        self.alert = alert
        self.notifications = notifications


class AlertEngine:
    def __init__(
        self,
        store=None,
        settings=None,
        notification_service=None,
    ):
        self.store = store or AlertStore()
        self.settings = settings or NotificationSettings()
        self.notification_service = (
            notification_service
            or NotificationService(settings=self.settings)
        )

    def update_settings(self, settings):
        self.settings = settings
        self.notification_service.update_settings(settings)
        return self.settings

    def notifications_enabled_for(self, alert_type):
        if not self.settings.enabled:
            return False

        setting_name = ALERT_SETTING_MAP.get(alert_type)

        if setting_name is None:
            return True

        return bool(getattr(self.settings, setting_name))

    def process(self, event: AlertEvent) -> AlertDispatch:
        """
        Create and store the alert regardless of notification settings.

        Notification settings control delivery only. This keeps alert
        history available even when notifications are paused.
        """
        alert_id = self._generate_alert_id()

        alert = self.store.create(
            event=event,
            alert_id=alert_id,
            created_at=datetime.now(timezone.utc),
        )

        if not self.notifications_enabled_for(event.alert_type):
            return AlertDispatch(
                alert=alert,
                notifications=[],
            )

        notifications = self.notification_service.send(alert)

        return AlertDispatch(
            alert=alert,
            notifications=notifications,
        )

    def acknowledge(self, alert_id):
        return self.store.acknowledge(alert_id)

    def resolve(self, alert_id):
        return self.store.resolve(alert_id)

    def get_alert(self, alert_id):
        return self.store.get(alert_id)

    def get_all_alerts(self):
        return self.store.all()

    def get_symbol_alerts(self, symbol):
        return self.store.by_symbol(symbol)

    def get_new_alerts(self):
        return self.store.by_status("new")

    @staticmethod
    def _generate_alert_id():
        return f"ALT-{uuid4().hex[:12].upper()}"