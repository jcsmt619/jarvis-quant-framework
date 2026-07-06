"""Twilio SMS alert helpers for Jarvis Quant.

Phase 10A safety layer.

This module can send SMS alerts, but it does not trade, does not submit
broker orders, and does not enable live trading.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable


TWILIO_SMS_CONFIRMATION = "I_UNDERSTAND_THIS_SENDS_A_REAL_SMS"


class TwilioSmsConfigError(ValueError):
    """Raised when Twilio SMS config is missing or unsafe."""


@dataclass(frozen=True)
class TwilioSmsConfig:
    account_sid: str
    auth_token: str
    from_number: str
    owner_phone: str


@dataclass(frozen=True)
class SmsAlertResult:
    timestamp_utc: str
    event: str
    body: str
    sent: bool
    twilio_client_used: bool
    message_sid: str | None
    message_status: str | None
    blocked_reasons: list[str]
    live_trading_enabled: bool = False


def _read_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise TwilioSmsConfigError(f"missing required environment variable: {name}")
    return value


def load_twilio_sms_config_from_env() -> TwilioSmsConfig:
    """Load Twilio SMS config from environment variables."""

    return TwilioSmsConfig(
        account_sid=_read_env("TWILIO_ACCOUNT_SID"),
        auth_token=_read_env("TWILIO_AUTH_TOKEN"),
        from_number=_read_env("TWILIO_FROM_NUMBER"),
        owner_phone=_read_env("JARVIS_OWNER_PHONE"),
    )


def mask_phone_number(phone: str) -> str:
    digits = "".join(ch for ch in phone if ch.isdigit())
    if len(digits) < 4:
        return "***"
    return f"***{digits[-4:]}"


def build_sms_alert_body(
    *,
    event: str,
    engine: str = "Jarvis",
    symbol: str = "EEM",
    intent_action: str = "UNKNOWN",
    ready_to_arm: bool | None = None,
    reasons: list[str] | None = None,
) -> str:
    """Build a compact SMS body suitable for Twilio."""

    reason_text = "; ".join(reasons or [])
    if len(reason_text) > 240:
        reason_text = reason_text[:237] + "..."

    ready_text = "unknown" if ready_to_arm is None else str(ready_to_arm).lower()

    lines = [
        f"Jarvis Alert: {event}",
        f"Engine: {engine}",
        f"Symbol: {symbol}",
        f"Intent: {intent_action}",
        f"READY TO ARM: {ready_text}",
    ]

    if reason_text:
        lines.append(f"Reasons: {reason_text}")

    lines.append("LIVE TRADING: DISABLED")
    return "\n".join(lines)


def _create_twilio_client(account_sid: str, auth_token: str) -> Any:
    from twilio.rest import Client

    return Client(account_sid, auth_token)


def send_sms_alert(
    *,
    config: TwilioSmsConfig,
    event: str,
    body: str,
    twilio_client_factory: Callable[[str, str], Any] | None = None,
) -> SmsAlertResult:
    """Send an SMS alert through Twilio.

    This function sends SMS only when called directly by a higher-level script
    that has already passed its confirmation gate.
    """

    client_factory = twilio_client_factory or _create_twilio_client
    client = client_factory(config.account_sid, config.auth_token)

    message = client.messages.create(
        body=body,
        from_=config.from_number,
        to=config.owner_phone,
    )

    return SmsAlertResult(
        timestamp_utc=datetime.now(UTC).isoformat(),
        event=event,
        body=body,
        sent=True,
        twilio_client_used=True,
        message_sid=getattr(message, "sid", None),
        message_status=getattr(message, "status", None),
        blocked_reasons=[],
        live_trading_enabled=False,
    )


def build_blocked_sms_result(
    *,
    event: str,
    body: str,
    blocked_reasons: list[str],
) -> SmsAlertResult:
    return SmsAlertResult(
        timestamp_utc=datetime.now(UTC).isoformat(),
        event=event,
        body=body,
        sent=False,
        twilio_client_used=False,
        message_sid=None,
        message_status=None,
        blocked_reasons=blocked_reasons,
        live_trading_enabled=False,
    )
