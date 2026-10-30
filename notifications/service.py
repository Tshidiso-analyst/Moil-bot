from dataclasses import dataclass


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


class NotificationService:
    """Simple notification service for user updates and bot status messages."""

    def __init__(self) -> None:
        self._events: list[NotificationDelivery] = []

    def send(
        self,
        message: str,
        *,
        email: str | None = None,
        phone_number: str | None = None,
        room: str | None = None,
        channel: str = "dashboard",
    ) -> list[NotificationDelivery]:
        message = (message or "").strip()
        if not message:
            raise ValueError("message must not be empty")

        deliveries: list[NotificationDelivery] = []
        if email:
            deliveries.append(
                NotificationDelivery(
                    channel="email",
                    destination=email,
                    message=message,
                )
            )
        if phone_number:
            deliveries.append(
                NotificationDelivery(
                    channel="sms",
                    destination=phone_number,
                    message=message,
                )
            )

        if not deliveries:
            deliveries.append(
                NotificationDelivery(
                    channel=channel,
                    destination=room or "dashboard",
                    message=message,
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
        if contact is None:
            return self.send(body, room=room)

        deliveries: list[NotificationDelivery] = []
        if contact.email_notifications and contact.email:
            deliveries.append(
                NotificationDelivery(
                    channel="email",
                    destination=contact.email,
                    message=body,
                )
            )
        if contact.sms_notifications and contact.phone_number:
            deliveries.append(
                NotificationDelivery(
                    channel="sms",
                    destination=contact.phone_number,
                    message=body,
                )
            )

        if deliveries:
            self._events.extend(deliveries)
            return deliveries

        return self.send(body, room=room)

    def history(self) -> list[NotificationDelivery]:
        return list(self._events)


notification_service = NotificationService()

__all__ = [
    "ContactPreferences",
    "NotificationDelivery",
    "NotificationService",
    "notification_service",
]
