from __future__ import annotations

import argparse
from pathlib import Path
from typing import Callable

from automation.gmail_approval_inbox import (
    GMAIL_INBOX_READ_CONFIRMATION,
    build_blocked_inbox_read_result,
    load_gmail_approval_inbox_config_from_env,
    mask_email,
    read_gmail_approval_inbox,
)
from scripts.check_alpaca_paper_connection import load_env_file


def run_gmail_approval_inbox_report(
    *,
    env_file: Path | None = None,
    max_results: int = 10,
    enable_real_inbox_read: bool = False,
    confirmation: str | None = None,
    injected_imap_client_factory: Callable | None = None,
) -> int:
    if env_file is not None:
        load_env_file(env_file)

    confirmation_accepted = confirmation == GMAIL_INBOX_READ_CONFIRMATION

    try:
        if not enable_real_inbox_read:
            result = build_blocked_inbox_read_result(
                blocked_reasons=["real Gmail inbox read is disabled"],
            )
            authorized_display = "not loaded"

        elif not confirmation_accepted:
            result = build_blocked_inbox_read_result(
                blocked_reasons=["real Gmail inbox read confirmation phrase was not accepted"],
            )
            authorized_display = "not loaded"

        else:
            config = load_gmail_approval_inbox_config_from_env()
            result = read_gmail_approval_inbox(
                config=config,
                max_results=max_results,
                imap_client_factory=injected_imap_client_factory,
            )
            authorized_display = mask_email(config.authorized_from_email)

    except Exception as exc:
        print("GMAIL APPROVAL INBOX REPORT: FAIL")
        print(f"Reason: {exc}")
        print("Inbox client used: false")
        print("Messages marked read: false")
        print("Broker order call performed: false")
        print("LIVE TRADING: DISABLED")
        return 1

    print("GMAIL APPROVAL INBOX REPORT: PASS")
    print(f"Inbox read enabled: {str(enable_real_inbox_read).lower()}")
    print(f"Confirmation accepted: {str(confirmation_accepted).lower()}")
    print(f"Inbox client used: {str(result.inbox_client_used).lower()}")
    print(f"Mailbox selected readonly: {str(result.mailbox_selected_readonly).lower()}")
    print(f"Messages marked read: {str(result.messages_marked_read).lower()}")
    print(f"Scanned approval emails: {result.scanned_count}")
    print(f"Authorized sender: {authorized_display}")
    print(f"Blocked reasons: {result.blocked_reasons}")

    for email in result.approval_emails:
        print("---")
        print(f"Message id: {email.message_id}")
        print(f"From: {mask_email(email.from_email)}")
        print(f"Subject: {email.subject}")
        print(f"Body first line: {email.body_first_line}")
        print(f"Parsed action: {email.command.action}")
        print(f"Parsed approval id: {email.command.approval_id}")
        print(f"Command valid: {str(email.command.valid).lower()}")
        print(f"Sender authorized: {str(email.sender_authorized).lower()}")
        print(f"Email blocked reasons: {email.blocked_reasons}")

    print("Approval execution performed: false")
    print("Broker order call performed: false")
    print("LIVE TRADING: DISABLED")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Read Gmail approval inbox safely.")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--max-results", type=int, default=10)
    parser.add_argument("--enable-real-inbox-read", action="store_true")
    parser.add_argument("--confirmation", default=None)
    args = parser.parse_args()

    return run_gmail_approval_inbox_report(
        env_file=args.env_file,
        max_results=args.max_results,
        enable_real_inbox_read=args.enable_real_inbox_read,
        confirmation=args.confirmation,
    )


if __name__ == "__main__":
    raise SystemExit(main())
