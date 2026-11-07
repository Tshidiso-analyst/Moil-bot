from unittest.mock import patch

from notifications.service import ContactPreferences, NotificationService


@patch("notifications.service.send_email", return_value=False)
def test_notification_service_send_email_mock(mock_send_email):
    service = NotificationService()

    deliveries = service.send(
        "System test message",
        email="test@example.com",
    )

    assert len(deliveries) == 1
    assert deliveries[0].channel == "email"
    assert deliveries[0].destination == "test@example.com"
    assert deliveries[0].detail == "dev_preview"
    mock_send_email.assert_called_once()


@patch("notifications.service.send_sms", return_value=False)
@patch("notifications.service.send_email", return_value=False)
def test_notification_service_send_update_with_contact_preferences(
    mock_send_email,
    mock_send_sms,
):
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
    assert any(d.channel == "sms" for d in deliveries)
    mock_send_email.assert_called_once()
    mock_send_sms.assert_called_once()


def test_notification_service_dashboard_only():
    service = NotificationService()
    deliveries = service.send("Dashboard only message")
    assert len(deliveries) == 1
    assert deliveries[0].channel == "dashboard"
    assert deliveries[0].delivered is True
