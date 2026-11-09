import os
import smtplib
from email.message import EmailMessage


def send_email(to_email: str, subject: str, body: str) -> None:
    """Send an email through SMTP when configured, otherwise print locally."""
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    from_email = os.getenv("FROM_EMAIL", smtp_user or "noreply@localhost")

    if not smtp_host:
        print("[EMAIL DEV MODE]")
        print(f"To: {to_email}")
        print(f"Subject: {subject}")
        print(body)
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email
    msg.set_content(body)

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            if smtp_user and smtp_password:
                server.starttls()
                server.login(smtp_user, smtp_password)
            server.send_message(msg)
    except Exception as exc:
        print(f"[EMAIL SEND FAILED] {exc}")
        raise


def send_sms(to_phone: str, message: str) -> None:
    """Send an SMS via Twilio when configured, otherwise print locally."""
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_FROM_NUMBER")

    if not account_sid or not auth_token or not from_number:
        print("[SMS DEV MODE]")
        print(f"To: {to_phone}")
        print(message)
        return

    try:
        from twilio.rest import Client
    except Exception as exc:  # pragma: no cover - optional dependency path
        raise RuntimeError("Twilio dependency not installed") from exc

    client = Client(account_sid, auth_token)
    client.messages.create(
        body=message,
        from_=from_number,
        to=to_phone,
    )


__all__ = ["send_email", "send_sms"]
