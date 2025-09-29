from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage
from typing import Iterable

from .config import get_settings


def _send_email_sync(message: EmailMessage) -> None:
    settings = get_settings()
    if not settings.smtp_server:
        raise RuntimeError("SMTP server not configured")
    if settings.smtp_use_ssl:
        with smtplib.SMTP_SSL(settings.smtp_server, settings.smtp_port) as smtp:
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(message)
    else:
        with smtplib.SMTP(settings.smtp_server, settings.smtp_port) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(message)


async def send_email(subject: str, body: str, recipients: Iterable[str]) -> None:
    settings = get_settings()
    if not settings.email_from:
        raise RuntimeError("EMAIL_FROM not configured")
    msg = EmailMessage()
    msg["Subject"] = subject
    sender = settings.email_from
    if settings.email_from_name:
        msg["From"] = f"{settings.email_from_name} <{sender}>"
    else:
        msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg.set_content(body)
    await asyncio.to_thread(_send_email_sync, msg)
