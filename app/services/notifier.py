"""Send a message to a student: Telegram, email, or (if neither is set up) the console."""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

import requests

from ..config import Config

log = logging.getLogger(__name__)


def telegram_ready() -> bool:
    return bool(Config.TELEGRAM_BOT_TOKEN)


def email_ready() -> bool:
    return bool(Config.SMTP_HOST and Config.SMTP_USER and Config.SMTP_PASSWORD)


def send_telegram(chat_id: str, text: str) -> bool:
    url = f"https://api.telegram.org/bot{Config.TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(url, json={"chat_id": chat_id, "text": text,
                                        "disable_web_page_preview": True}, timeout=20)
        if resp.status_code == 200:
            return True
        log.warning("Telegram refused the message (HTTP %d).", resp.status_code)
    except requests.RequestException as exc:
        log.warning("Telegram request failed (%s).", exc.__class__.__name__)
    return False


def send_email(to_address: str, subject: str, body: str) -> bool:
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, Config.SMTP_FROM, to_address
    msg.set_content(body)
    try:
        with smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT, timeout=25) as server:
            server.starttls()
            server.login(Config.SMTP_USER, Config.SMTP_PASSWORD)
            server.send_message(msg)
        return True
    except (smtplib.SMTPException, OSError) as exc:
        log.warning("Email failed (%s).", exc.__class__.__name__)
        return False


def deliver(user, subject: str, body: str) -> str | None:
    """Try Telegram, then email. With neither configured, print to the console (demo mode).
    Returns the channel used, or None if every channel failed."""
    if user["telegram_chat_id"] and telegram_ready():
        if send_telegram(user["telegram_chat_id"], f"{subject}\n\n{body}"):
            return "telegram"
    if user["email"] and email_ready():
        if send_email(user["email"], subject, body):
            return "email"
    if not telegram_ready() and not email_ready():
        # ascii-only so a Windows console never chokes on Hindi or the rupee sign
        line = f"{subject} | {body}".replace("\n", " / ").encode("ascii", "replace").decode("ascii")
        log.info("[console alert] to=%s | %s", user["name"], line)
        return "console"
    return None
