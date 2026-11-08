from notifications import (
    ContactPreferences,
    Notification,
    NotificationDelivery,
    NotificationService,
    send_email,
    send_sms,
)


def test_notification_package_exports_public_api():
    assert ContactPreferences is not None
    assert Notification is not None
    assert NotificationDelivery is not None
    assert NotificationService is not None
    assert callable(send_email)
    assert callable(send_sms)


def test_email_uses_starttls_and_sends_message(monkeypatch):
    calls = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            calls.append(("connect", host, port, timeout))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def ehlo(self):
            calls.append(("ehlo",))

        def starttls(self, context):
            calls.append(("starttls", context))

        def login(self, username, password):
            calls.append(("login", username, password))

        def send_message(self, message):
            calls.append(("send", message["To"], message["Subject"]))

    monkeypatch.setenv("SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "mailer@example.test")
    monkeypatch.setenv("SMTP_PASSWORD", "test-secret")
    monkeypatch.setenv("FROM_EMAIL", "mailer@example.test")
    monkeypatch.setattr("notifications.emailer.smtplib.SMTP", FakeSMTP)

    delivered = send_email("user@example.test", "Moil-bot alert", "Test message")

    assert delivered is True

    assert ("connect", "smtp.example.test", 587, 15) in calls
    assert any(call[0] == "starttls" for call in calls)
    assert ("login", "mailer@example.test", "test-secret") in calls
    assert ("send", "user@example.test", "Moil-bot alert") in calls


def test_email_rejects_partial_smtp_credentials(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("SMTP_USER", "mailer@example.test")
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)

    import pytest

    with pytest.raises(ValueError, match="must be configured together"):
        send_email("user@example.test", "Alert", "Test")


def test_email_development_mode_is_explicit_when_smtp_is_not_configured(monkeypatch, capsys):
    monkeypatch.delenv("SMTP_HOST", raising=False)

    delivered = send_email("user@example.test", "Alert", "Test message")

    assert delivered is False

    output = capsys.readouterr().out
    assert "[EMAIL DEV MODE]" in output
    assert "user@example.test" in output


def test_sms_development_mode_is_explicit_when_twilio_is_not_configured(monkeypatch, capsys):
    for key in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM_NUMBER"):
        monkeypatch.delenv(key, raising=False)

    delivered = send_sms("+15551234567", "Test message")

    assert delivered is False

    output = capsys.readouterr().out
    assert "[SMS DEV MODE]" in output
    assert "+15551234567" in output


def test_sms_rejects_partial_twilio_configuration(monkeypatch):
    import pytest

    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "test-account")
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("TWILIO_FROM_NUMBER", raising=False)

    with pytest.raises(ValueError, match="must be configured together"):
        send_sms("+15551234567", "Test message")
