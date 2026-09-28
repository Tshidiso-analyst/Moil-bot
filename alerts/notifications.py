from dataclasses import dataclass
from typing import Protocol

from alerts.models import Alert, NotificationSettings


@dataclass(frozen=True)
class NotificationResult:
    channel: str
    sent: bool
    message: str


class NotificationChannel(Protocol):
    name: str

    def send(self, alert: Alert) -> NotificationResult:
        ...


class InAppNotificationChannel:
    name = "in_app"

    def send(self, alert: Alert) -> NotificationResult:
        return NotificationResult(
            channel=self.name,
            sent=True,
            message=f"In-app alert created: {alert.alert_id}",
        )


class EmailNotificationChannel:
    name = "email"

    def __init__(
        self,
        smtp_host: str = "",
        smtp_port: int = 587,
        username: str = "",
        password: str = "",
        recipient: str = "",
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.recipient = recipient

    def send(self, alert: Alert) -> NotificationResult:
        if not all(
            [
                self.smtp_host,
                self.username,
                self.password,
                self.recipient,
            ]
        ):
            return NotificationResult(
                channel=self.name,
                sent=False,
                message="Email configuration is incomplete.",
            )

        # SMTP delivery will be enabled when valid credentials
        # are supplied through the application's environment.
        return NotificationResult(
            channel=self.name,
            sent=False,
            message="SMTP delivery is configured but not yet dispatched.",
        )


class MessageNotificationChannel:
    name = "message"

    def send(self, alert: Alert) -> NotificationResult:
        return NotificationResult(
            channel=self.name,
            sent=False,
            message=(
                "External messaging provider is not configured."
            ),
        )


class NotificationService:
    def __init__(
        self,
        settings: NotificationSettings | None = None,
        channels: dict[str, NotificationChannel] | None = None,
    ):
        self.settings = settings or NotificationSettings()

        self.channels = channels or {
            "in_app": InAppNotificationChannel(),
            "email": EmailNotificationChannel(),
            "message": MessageNotificationChannel(),
        }

    def update_settings(
        self,
        settings: NotificationSettings,
    ) -> None:
        self.settings = settings

    def send(self, alert: Alert) -> list[NotificationResult]:
        if not self.settings.enabled:
            return []

        results = []

        for channel_name in self.settings.enabled_channels():
            channel = self.channels.get(channel_name)

            if channel is None:
                results.append(
                    NotificationResult(
                        channel=channel_name,
                        sent=False,
                        message="Notification channel is not configured.",
                    )
                )
                continue

            results.append(channel.send(alert))

        return results
