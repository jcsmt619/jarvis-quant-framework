"""Gmail SMTP email alert helpers for Jarvis Quant.

Phase 10A safety layer.

This module can send email alerts, but it does not trade, does not submit
broker orders, and does not enable live trading.
"""

from __future__ import annotations

import os
import smtplib
import ssl
from dataclasses import dataclass
from datetime import UTC, datetime
from email.message import EmailMessage
from typing import Any, Callable


GMAIL_EMAIL_CONFIRMATION = "I_UNDERSTAND_THIS_SENDS_A_REAL_EMAIL"


class GmailEmailConfigError(ValueError):
    """Raised when Gmail email config is missing or unsafe."""


@dataclass(frozen=True)
class GmailEmailConfig:
    username: str
    app_password: str
    from_email: str
    to_email: str
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 465


@dataclass(frozen=True)
class EmailAlertResult:
    timestamp_utc: str
    event: str
    subject: str
    body: str
    sent: bool
    smtp_client_used: bool
    blocked_reasons: list[str]
    from_email: str | None = None
    to_email: str | None = None
    live_trading_enabled: bool = False


def _read_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise GmailEmailConfigError(f"missing required environment variable: {name}")
    return value


def load_gmail_email_config_from_env() -> GmailEmailConfig:
    """Load Gmail SMTP config from environment variables."""

    username = _read_env("GMAIL_SMTP_USERNAME")
    from_email = os.environ.get("GMAIL_SMTP_FROM", "").strip() or username

    return GmailEmailConfig(
        username=username,
        app_password=_read_env("GMAIL_SMTP_APP_PASSWORD"),
        from_email=from_email,
        to_email=_read_env("JARVIS_ALERT_EMAIL_TO"),
    )


def mask_email(email: str) -> str:
    if "@" not in email:
        return "***"
    name, domain = email.split("@", 1)
    if not name:
        masked_name = "***"
    elif len(name) <= 2:
        masked_name = name[0] + "***"
    else:
        masked_name = name[0] + "***" + name[-1]
    return f"{masked_name}@{domain}"


def build_email_alert_subject(
    *,
    event: str,
    symbol: str = "EEM",
    ready_to_arm: bool | None = None,
) -> str:
    ready_text = "UNKNOWN" if ready_to_arm is None else str(ready_to_arm).upper()
    return f"Jarvis Alert: {event} | {symbol} | READY_TO_ARM={ready_text}"


def build_email_alert_body(
    *,
    event: str,
    engine: str = "Jarvis",
    symbol: str = "EEM",
    intent_action: str = "UNKNOWN",
    ready_to_arm: bool | None = None,
    reasons: list[str] | None = None,
) -> str:
    reason_text = "\n".join(f"- {reason}" for reason in (reasons or []))
    ready_text = "unknown" if ready_to_arm is None else str(ready_to_arm).lower()

    lines = [
        f"Jarvis Alert: {event}",
        "",
        f"Engine: {engine}",
        f"Symbol: {symbol}",
        f"Intent: {intent_action}",
        f"READY TO ARM: {ready_text}",
        "",
        "Reasons:",
        reason_text if reason_text else "- none",
        "",
        "Safety:",
        "- LIVE TRADING: DISABLED",
        "- This email alert does not submit broker orders.",
    ]
    return "\n".join(lines)


def _create_smtp_ssl_client(host: str, port: int, context: ssl.SSLContext) -> Any:
    return smtplib.SMTP_SSL(host, port, context=context)


def send_email_alert(
    *,
    config: GmailEmailConfig,
    event: str,
    subject: str,
    body: str,
    smtp_client_factory: Callable[[str, int, ssl.SSLContext], Any] | None = None,
) -> EmailAlertResult:
    """Send an email alert through Gmail SMTP."""

    message = EmailMessage()
    message["From"] = config.from_email
    message["To"] = config.to_email
    message["Subject"] = subject
    message.set_content(body)

    context = ssl.create_default_context()
    factory = smtp_client_factory or _create_smtp_ssl_client

    with factory(config.smtp_host, config.smtp_port, context) as smtp:
        smtp.login(config.username, config.app_password)
        smtp.send_message(message)

    return EmailAlertResult(
        timestamp_utc=datetime.now(UTC).isoformat(),
        event=event,
        subject=subject,
        body=body,
        sent=True,
        smtp_client_used=True,
        blocked_reasons=[],
        from_email=config.from_email,
        to_email=config.to_email,
        live_trading_enabled=False,
    )


def build_blocked_email_result(
    *,
    event: str,
    subject: str,
    body: str,
    blocked_reasons: list[str],
) -> EmailAlertResult:
    return EmailAlertResult(
        timestamp_utc=datetime.now(UTC).isoformat(),
        event=event,
        subject=subject,
        body=body,
        sent=False,
        smtp_client_used=False,
        blocked_reasons=blocked_reasons,
        from_email=None,
        to_email=None,
        live_trading_enabled=False,
    )
