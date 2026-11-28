"""Transactional email delivery boundary for identity workflows."""

import asyncio
import smtplib
from email.message import EmailMessage
from typing import Protocol

from stagingnextgenearth.core.config import Settings


class EmailDeliveryError(RuntimeError):
    """Raised when a configured transactional email transport cannot deliver."""


class EmailSender(Protocol):
    async def send(self, recipient: str, subject: str, text_body: str, html_body: str) -> None:
        """Deliver one transactional message to one recipient."""


class SMTPEmailSender:
    """Small SMTP adapter; credentials remain in deployment configuration."""

    def __init__(self, settings: Settings) -> None:
        if not settings.smtp_host or not settings.smtp_sender or settings.smtp_password is None:
            raise ValueError("SMTP delivery is not fully configured")
        self.host = settings.smtp_host
        self.port = settings.smtp_port
        self.username = settings.smtp_username
        self.password = settings.smtp_password.get_secret_value()
        self.sender = settings.smtp_sender
        self.starttls = settings.smtp_starttls
        self.timeout = settings.smtp_timeout_seconds

    def _send_sync(self, message: EmailMessage) -> None:
        try:
            with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as client:
                client.ehlo()
                if self.starttls:
                    client.starttls()
                    client.ehlo()
                if self.username:
                    client.login(self.username, self.password)
                client.send_message(message)
        except (OSError, smtplib.SMTPException) as exc:
            raise EmailDeliveryError("Transactional email delivery failed") from exc

    async def send(self, recipient: str, subject: str, text_body: str, html_body: str) -> None:
        message = EmailMessage()
        message["From"] = self.sender
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(text_body)
        message.add_alternative(html_body, subtype="html")
        await asyncio.to_thread(self._send_sync, message)


def create_email_sender(settings: Settings) -> EmailSender | None:
    """Return a configured sender or None; never invent delivery credentials."""
    if not settings.smtp_host:
        return None
    return SMTPEmailSender(settings)
