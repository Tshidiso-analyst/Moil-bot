from notifications.service import ContactPreferences, NotificationService


def test_notification_service_send_email_mock():
    service = NotificationService()

    deliveries = service.send(
        "System test message",
        email="test@example.com",
    )

    assert len(deliveries) == 1
    assert deliveries[0].channel == "email"
    assert deliveries[0].destination == "test@example.com"


def test_notification_service_send_update_with_contact_preferences():
    service = NotificationService()

    contact = ContactPreferences(
        email="owner@example.com",
        phone_number="+27123456789",
        email_notifications=True,
        sms_notifications=True,
    )

    deliveries = service.send_update(
        "Approval Update",
        "Your trade was reviewed",
        contact=contact,
    )

    assert len(deliveries) >= 1
    assert any(d.channel == "email" for d in deliveries)
