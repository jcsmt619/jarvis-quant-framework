"""Gmail approval inbox reader for Jarvis Quant.

Phase 10B safety layer.

This module reads recent Gmail approval messages and parses commands.
It does not execute approvals, does not trade, does not submit broker orders,
and does not enable live trading.
"""

from __future__ import annotations

import imaplib
import os
from dataclasses import dataclass
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr
from typing import Any, Callable

from automation.approval_gateway import ApprovalCommand, parse_approval_command


GMAIL_INBOX_READ_CONFIRMATION = "I_UNDERSTAND_THIS_READS_MY_GMAIL_INBOX"


class GmailApprovalInboxConfigError(ValueError):
    """Raised when Gmail approval inbox config is missing."""


@dataclass(frozen=True)
class GmailApprovalInboxConfig:
    username: str
    app_password: str
    authorized_from_email: str
    imap_host: str = "imap.gmail.com"
    imap_port: int = 993
    mailbox: str = "INBOX"


@dataclass(frozen=True)
class InboundApprovalEmail:
    message_id: str
    from_email: str
    subject: str
    body_first_line: str
    command: ApprovalCommand
    sender_authorized: bool
    blocked_reasons: list[str]
    live_trading_enabled: bool = False


@dataclass(frozen=True)
class GmailApprovalInboxReadResult:
    inbox_client_used: bool
    mailbox_selected_readonly: bool
    messages_marked_read: bool
    scanned_count: int
    approval_emails: list[InboundApprovalEmail]
    blocked_reasons: list[str]
    broker_order_call_performed: bool = False
    live_trading_enabled: bool = False


def _read_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise GmailApprovalInboxConfigError(f"missing required environment variable: {name}")
    return value


def load_gmail_approval_inbox_config_from_env() -> GmailApprovalInboxConfig:
    username = _read_env("GMAIL_SMTP_USERNAME")
    app_password = _read_env("GMAIL_SMTP_APP_PASSWORD")
    authorized_from_email = (
        os.environ.get("JARVIS_APPROVAL_EMAIL_FROM", "").strip()
        or os.environ.get("JARVIS_ALERT_EMAIL_TO", "").strip()
        or username
    )

    if not authorized_from_email:
        raise GmailApprovalInboxConfigError(
            "missing authorized approval sender: JARVIS_APPROVAL_EMAIL_FROM"
        )

    return GmailApprovalInboxConfig(
        username=username,
        app_password=app_password,
        authorized_from_email=authorized_from_email.lower(),
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


def _create_imap_ssl_client(host: str, port: int) -> Any:
    return imaplib.IMAP4_SSL(host, port)


def _extract_text_body(message: Any) -> str:
    if message.is_multipart():
        for part in message.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", "")).lower()
            if content_type == "text/plain" and "attachment" not in disposition:
                try:
                    return part.get_content()
                except Exception:
                    payload = part.get_payload(decode=True) or b""
                    return payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        return ""

    try:
        return message.get_content()
    except Exception:
        payload = message.get_payload(decode=True) or b""
        return payload.decode(message.get_content_charset() or "utf-8", errors="replace")


def _parse_raw_email(
    *,
    message_id: str,
    raw_email: bytes,
    authorized_from_email: str,
) -> InboundApprovalEmail:
    message = BytesParser(policy=policy.default).parsebytes(raw_email)
    from_email = parseaddr(message.get("From", ""))[1].lower()
    subject = str(message.get("Subject", ""))
    body = _extract_text_body(message).strip()
    body_first_line = body.splitlines()[0].strip() if body else ""

    command = parse_approval_command(body_first_line)
    sender_authorized = from_email == authorized_from_email.lower()

    blocked_reasons = list(command.blocked_reasons)
    if not sender_authorized:
        blocked_reasons.append(f"sender is not authorized: {mask_email(from_email)}")

    return InboundApprovalEmail(
        message_id=message_id,
        from_email=from_email,
        subject=subject,
        body_first_line=body_first_line,
        command=command,
        sender_authorized=sender_authorized,
        blocked_reasons=blocked_reasons,
        live_trading_enabled=False,
    )


def read_gmail_approval_inbox(
    *,
    config: GmailApprovalInboxConfig,
    max_results: int = 10,
    imap_client_factory: Callable[[str, int], Any] | None = None,
) -> GmailApprovalInboxReadResult:
    factory = imap_client_factory or _create_imap_ssl_client
    client = factory(config.imap_host, config.imap_port)

    approval_emails: list[InboundApprovalEmail] = []

    try:
        client.login(config.username, config.app_password)
        status, _ = client.select(config.mailbox, readonly=True)
        if status != "OK":
            raise GmailApprovalInboxConfigError(f"could not select mailbox: {config.mailbox}")

        status, data = client.search(None, "UNSEEN")
        if status != "OK":
            raise GmailApprovalInboxConfigError("could not search Gmail inbox")

        message_ids = []
        if data and data[0]:
            message_ids = data[0].split()

        for raw_id in message_ids[:max_results]:
            message_id = raw_id.decode("utf-8", errors="replace")
            status, fetched = client.fetch(raw_id, "(RFC822)")
            if status != "OK":
                continue

            for item in fetched:
                if isinstance(item, tuple) and len(item) >= 2 and isinstance(item[1], bytes):
                    approval_emails.append(
                        _parse_raw_email(
                            message_id=message_id,
                            raw_email=item[1],
                            authorized_from_email=config.authorized_from_email,
                        )
                    )
                    break

    finally:
        try:
            client.close()
        except Exception:
            pass
        try:
            client.logout()
        except Exception:
            pass

    return GmailApprovalInboxReadResult(
        inbox_client_used=True,
        mailbox_selected_readonly=True,
        messages_marked_read=False,
        scanned_count=len(approval_emails),
        approval_emails=approval_emails,
        blocked_reasons=[],
        broker_order_call_performed=False,
        live_trading_enabled=False,
    )


def build_blocked_inbox_read_result(*, blocked_reasons: list[str]) -> GmailApprovalInboxReadResult:
    return GmailApprovalInboxReadResult(
        inbox_client_used=False,
        mailbox_selected_readonly=False,
        messages_marked_read=False,
        scanned_count=0,
        approval_emails=[],
        blocked_reasons=blocked_reasons,
        broker_order_call_performed=False,
        live_trading_enabled=False,
    )
