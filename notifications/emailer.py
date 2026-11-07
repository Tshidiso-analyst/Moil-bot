from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage


def send_email(to_email: str, subject: str, body: str) -> None:
    """Send email over SMTP with STARTTLS, or print a local development preview."""
    if not str(to_email or "").strip():
        raise ValueError("to_email must not be empty.")
    if not str(subject or "").strip():
        raise ValueError("subject must not be empty.")

    smtp_host = os.getenv("SMTP_HOST", "").strip()
    if not smtp_host:
        print("[EMAIL DEV MODE]")
        print(f"To: {to_email}")
        print(f"Subject: {subject}")
        print(body)
        return

    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "").strip()
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    from_email = os.getenv("FROM_EMAIL", smtp_user or "noreply@localhost").strip()

    if bool(smtp_user) != bool(smtp_password):
        raise ValueError("SMTP_USER and SMTP_PASSWORD must be configured together.")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = from_email
    message["To"] = to_email
    message.set_content(body)

    context = ssl.create_default_context()
    with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()
        if smtp_user:
            server.login(smtp_user, smtp_password)
        server.send_message(message)


def send_sms(to_phone: str, message: str) -> None:
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
        return
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


__all__ = ["send_email", "send_sms"]
