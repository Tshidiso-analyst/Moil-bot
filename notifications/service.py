from __future__ import annotations

from dataclasses import dataclass

from .emailer import send_email, send_sms


@dataclass(frozen=True)
class ContactPreferences:
    email: str | None = None
    phone_number: str | None = None
    email_notifications: bool = True
    sms_notifications: bool = True


@dataclass(frozen=True)
class NotificationDelivery:
    channel: str
    destination: str
    message: str
    delivered: bool = False
    detail: str = ""


@dataclass(frozen=True)
class Notification:
    """Compatibility model for notification messages."""

    title: str
    details: str
    channel: str = "dashboard"
    destination: str = "dashboard"
    message: str = ""

    def __post_init__(self) -> None:
        if not self.message:
            object.__setattr__(self, "message", f"{self.title}: {self.details}".strip())


class NotificationService:
    """Notification service that records events and delivers email/SMS when configured."""

    def __init__(self) -> None:
        self._events: list[NotificationDelivery] = []

    def _deliver_email(self, destination: str, message: str, subject: str) -> NotificationDelivery:
        try:
            sent = send_email(to_email=destination, subject=subject, body=message)
            return NotificationDelivery(
                channel="email",
                destination=destination,
                message=message,
                delivered=bool(sent),
                detail="sent" if sent else "dev_preview",
            )
        except Exception as exc:
            return NotificationDelivery(
                channel="email",
                destination=destination,
                message=message,
                delivered=False,
                detail=f"failed: {exc}",
            )

    def _deliver_sms(self, destination: str, message: str) -> NotificationDelivery:
        try:
            sent = send_sms(to_phone=destination, message=message)
            return NotificationDelivery(
                channel="sms",
                destination=destination,
                message=message,
                delivered=bool(sent),
                detail="sent" if sent else "dev_preview",
            )
        except Exception as exc:
            return NotificationDelivery(
                channel="sms",
                destination=destination,
                message=message,
                delivered=False,
                detail=f"failed: {exc}",
            )

    def send(
        self,
        message: str,
        *,
        email: str | None = None,
        phone_number: str | None = None,
        room: str | None = None,
        channel: str = "dashboard",
        subject: str = "Moil Bot notification",
    ) -> list[NotificationDelivery]:
        message = (message or "").strip()
        if not message:
            raise ValueError("message must not be empty")

        deliveries: list[NotificationDelivery] = []
        if email:
            deliveries.append(self._deliver_email(email, message, subject))
        if phone_number:
            deliveries.append(self._deliver_sms(phone_number, message))

        if not deliveries:
            deliveries.append(
                NotificationDelivery(
                    channel=channel,
                    destination=room or "dashboard",
                    message=message,
                    delivered=True,
                    detail="recorded",
                )
            )

        self._events.extend(deliveries)
        return deliveries

    def send_update(
        self,
        title: str,
        details: str,
        *,
        contact: ContactPreferences | None = None,
        room: str | None = None,
    ) -> list[NotificationDelivery]:
        body = f"{title}: {details}".strip()
        subject = (title or "Moil Bot update").strip() or "Moil Bot update"
        if contact is None:
            return self.send(body, room=room, subject=subject)

        deliveries: list[NotificationDelivery] = []
        if contact.email_notifications and contact.email:
            deliveries.append(self._deliver_email(contact.email, body, subject))
        if contact.sms_notifications and contact.phone_number:
            deliveries.append(self._deliver_sms(contact.phone_number, body))

        if deliveries:
            self._events.extend(deliveries)
            return deliveries

        return self.send(body, room=room, subject=subject)

    def history(self) -> list[NotificationDelivery]:
        return list(self._events)


notification_service = NotificationService()

__all__ = [
    "ContactPreferences",
    "Notification",
    "NotificationDelivery",
    "NotificationService",
    "notification_service",
]
