from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage


def send_email(
    to_email: str,
    subject: str,
    body: str,
    *,
    smtp_host: str | None = None,
    smtp_port: int | None = None,
    smtp_user: str | None = None,
    smtp_password: str | None = None,
    from_email: str | None = None,
) -> bool:
    """Send email over SMTP; return False when only a development preview is printed."""
    if not str(to_email or "").strip():
        raise ValueError("to_email must not be empty.")
    if not str(subject or "").strip():
        raise ValueError("subject must not be empty.")

    host = (os.getenv("SMTP_HOST", "") if smtp_host is None else smtp_host).strip()
    if not host:
        print("[EMAIL DEV MODE]")
        print(f"To: {to_email}")
        print(f"Subject: {subject}")
        print(body)
        return False

    port = int(os.getenv("SMTP_PORT", "587")) if smtp_port is None else int(smtp_port)
    username = (os.getenv("SMTP_USER", "") if smtp_user is None else smtp_user).strip()
    password = os.getenv("SMTP_PASSWORD", "") if smtp_password is None else smtp_password
    sender = (
        os.getenv("FROM_EMAIL", username or "noreply@localhost")
        if from_email is None else from_email
    ).strip()

    if bool(username) != bool(password):
        raise ValueError("SMTP_USER and SMTP_PASSWORD must be configured together.")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = to_email
    message.set_content(body)

    context = ssl.create_default_context()
    with smtplib.SMTP(host, port, timeout=15) as server:
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()
        if username:
            server.login(username, password)
        server.send_message(message)
    return True


def send_sms(to_phone: str, message: str) -> bool:
    """Send SMS through Twilio, or print a local development preview."""
    if not str(to_phone or "").strip():
        raise ValueError("to_phone must not be empty.")
    if not str(message or "").strip():
        raise ValueError("message must not be empty.")

    account_sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
    auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
    from_number = os.getenv("TWILIO_FROM_NUMBER", "").strip()

    configured = (bool(account_sid), bool(auth_token), bool(from_number))
    if not any(configured):
        print("[SMS DEV MODE]")
        print(f"To: {to_phone}")
        print(message)
        return False
    if not all(configured):
        raise ValueError(
            "TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER "
            "must be configured together."
        )

    try:
        from twilio.rest import Client
    except ImportError as exc:  # pragma: no cover - optional dependency path
        raise RuntimeError("Twilio dependency is not installed.") from exc

    client = Client(account_sid, auth_token)
    client.messages.create(body=message, from_=from_number, to=to_phone)
    return True


__all__ = ["send_email", "send_sms"]
