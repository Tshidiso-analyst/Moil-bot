from dataclasses import dataclass
import os
from typing import Protocol

from alerts.models import Alert, NotificationSettings
from notifications.emailer import send_email, send_sms


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
        self.smtp_host = smtp_host or os.getenv("SMTP_HOST", "").strip()
        self.smtp_port = smtp_port
        self.username = username or os.getenv("SMTP_USER", "").strip()
        self.password = password or os.getenv("SMTP_PASSWORD", "")
        self.recipient = recipient or os.getenv(
            "MOILBOT_ALERT_EMAIL_TO",
            os.getenv("ALERT_EMAIL_TO", ""),
        ).strip()

    def send(self, alert: Alert) -> NotificationResult:
        if not self.recipient:
            return NotificationResult(
                channel=self.name,
                sent=False,
                message="Email recipient is not configured.",
            )
        try:
            send_email(self.recipient, alert.title, alert.message)
        except Exception as exc:
            return NotificationResult(
                channel=self.name,
                sent=False,
                message=f"Email delivery failed: {exc}",
            )
        return NotificationResult(
            channel=self.name,
            sent=True,
            message=f"Email delivered to {self.recipient}.",
        )


class MessageNotificationChannel:
    name = "message"

    def __init__(self, recipient: str = ""):
        self.recipient = recipient or os.getenv(
            "MOILBOT_ALERT_SMS_TO",
            os.getenv("ALERT_SMS_TO", ""),
        ).strip()

    def send(self, alert: Alert) -> NotificationResult:
        if not self.recipient:
            return NotificationResult(
                channel=self.name,
                sent=False,
                message="SMS recipient is not configured.",
            )
        try:
            send_sms(self.recipient, f"{alert.title}: {alert.message}")
        except Exception as exc:
            return NotificationResult(
                channel=self.name,
                sent=False,
                message=f"SMS delivery failed: {exc}",
            )
        return NotificationResult(
            channel=self.name,
            sent=True,
            message=f"SMS delivered to {self.recipient}.",
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

    def update_settings(self, settings: NotificationSettings) -> None:
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
