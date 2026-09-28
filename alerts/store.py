from alerts.models import Alert, AlertEvent


class AlertStore:
    """In-memory repository for Moil Bot alerts."""

    def __init__(self):
        self._alerts: dict[str, Alert] = {}

    def add(self, alert: Alert) -> Alert:
        if alert.alert_id in self._alerts:
            raise ValueError(
                f"Alert already exists: {alert.alert_id}"
            )

        self._alerts[alert.alert_id] = alert
        return alert

    def create(
        self,
        event: AlertEvent,
        alert_id: str,
        created_at,
    ) -> Alert:
        alert = Alert(
            alert_id=alert_id,
            symbol=event.symbol,
            alert_type=event.alert_type,
            severity=event.severity,
            title=event.title,
            message=event.message,
            created_at=created_at,
            decision_id=event.decision_id,
        )

        return self.add(alert)

    def get(self, alert_id: str) -> Alert | None:
        return self._alerts.get(alert_id)

    def all(self) -> list[Alert]:
        return list(self._alerts.values())

    def by_symbol(self, symbol: str) -> list[Alert]:
        return [
            alert
            for alert in self._alerts.values()
            if alert.symbol == symbol
        ]

    def by_status(self, status: str) -> list[Alert]:
        return [
            alert
            for alert in self._alerts.values()
            if alert.status == status
        ]

    def acknowledge(self, alert_id: str) -> Alert:
        alert = self._require(alert_id)

        updated = Alert(
            alert_id=alert.alert_id,
            symbol=alert.symbol,
            alert_type=alert.alert_type,
            severity=alert.severity,
            title=alert.title,
            message=alert.message,
            created_at=alert.created_at,
            status="acknowledged",
            decision_id=alert.decision_id,
        )

        self._alerts[alert_id] = updated
        return updated

    def resolve(self, alert_id: str) -> Alert:
        alert = self._require(alert_id)

        updated = Alert(
            alert_id=alert.alert_id,
            symbol=alert.symbol,
            alert_type=alert.alert_type,
            severity=alert.severity,
            title=alert.title,
            message=alert.message,
            created_at=alert.created_at,
            status="resolved",
            decision_id=alert.decision_id,
        )

        self._alerts[alert_id] = updated
        return updated

    def _require(self, alert_id: str) -> Alert:
        alert = self.get(alert_id)

        if alert is None:
            raise KeyError(f"Alert not found: {alert_id}")

        return alert
