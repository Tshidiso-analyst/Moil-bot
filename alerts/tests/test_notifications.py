from datetime import datetime

from alerts.models import Alert, NotificationSettings
from alerts.notifications import (
    InAppNotificationChannel,
    MessageNotificationChannel,
    NotificationResult,
    NotificationService,
)


def make_alert():
    return Alert(
        alert_id="ALT-00001",
        symbol="EURUSD",
        alert_type="trade_entered",
        severity="info",
        title="Trade Entered",
        message="EURUSD BUY trade entered.",
        created_at=datetime.utcnow(),
        decision_id="DEC-00001",
    )


def test_in_app_notification_is_sent():
    channel = InAppNotificationChannel()

    result = channel.send(make_alert())

    assert result.channel == "in_app"
    assert result.sent is True


def test_message_channel_reports_missing_provider():
    channel = MessageNotificationChannel()

    result = channel.send(make_alert())

    assert result.channel == "message"
    assert result.sent is False
    assert "not configured" in result.message.lower()


def test_notification_service_sends_in_app():
    service = NotificationService(
        settings=NotificationSettings(
            enabled=True,
            in_app=True,
            email=False,
            message=False,
        )
    )

    results = service.send(make_alert())

    assert len(results) == 1
    assert results[0].channel == "in_app"
    assert results[0].sent is True


def test_notification_service_can_send_multiple_channels():
    service = NotificationService(
        settings=NotificationSettings(
            enabled=True,
            in_app=True,
            email=True,
            message=False,
        )
    )

    results = service.send(make_alert())

    assert len(results) == 2
    assert {result.channel for result in results} == {
        "in_app",
        "email",
    }


def test_notification_service_stops_when_disabled():
    service = NotificationService(
        settings=NotificationSettings(enabled=False)
    )

    results = service.send(make_alert())

    assert results == []


def test_notification_result_is_immutable():
    result = NotificationResult(
        channel="in_app",
        sent=True,
        message="Delivered.",
    )

    assert result.sent is True


def test_email_channel_dispatches_through_configured_provider(monkeypatch):
    from alerts.notifications import EmailNotificationChannel

    sent = []
    monkeypatch.setattr(
        "alerts.notifications.send_email",
        lambda recipient, subject, body: sent.append((recipient, subject, body)),
    )
    channel = EmailNotificationChannel(recipient="trader@example.test")

    result = channel.send(make_alert())

    assert result.sent is True
    assert result.channel == "email"
    assert sent == [(
        "trader@example.test",
        "Trade Entered",
        "EURUSD BUY trade entered.",
    )]


def test_email_channel_reports_provider_failure(monkeypatch):
    from alerts.notifications import EmailNotificationChannel

    def fail(*args):
        raise RuntimeError("SMTP unavailable")

    monkeypatch.setattr("alerts.notifications.send_email", fail)
    result = EmailNotificationChannel(recipient="trader@example.test").send(make_alert())

    assert result.sent is False
    assert "SMTP unavailable" in result.message


def test_message_channel_dispatches_sms_through_configured_provider(monkeypatch):
    sent = []
    monkeypatch.setattr(
        "alerts.notifications.send_sms",
        lambda recipient, body: sent.append((recipient, body)),
    )
    channel = MessageNotificationChannel(recipient="+15551234567")

    result = channel.send(make_alert())

    assert result.sent is True
    assert result.channel == "message"
    assert sent == [(
        "+15551234567",
        "Trade Entered: EURUSD BUY trade entered.",
    )]


def test_message_channel_reports_provider_failure(monkeypatch):
    def fail(*args):
        raise RuntimeError("SMS provider unavailable")

    monkeypatch.setattr("alerts.notifications.send_sms", fail)
    result = MessageNotificationChannel(recipient="+15551234567").send(make_alert())

    assert result.sent is False
    assert "SMS provider unavailable" in result.message
