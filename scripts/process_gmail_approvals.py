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
from automation.gmail_approval_processor import process_gmail_approval_emails
from scripts.check_alpaca_paper_connection import load_env_file


def run_gmail_approval_processor_report(
    *,
    env_file: Path | None = Path(".env"),
    approvals_dir: Path = Path("reports/approvals"),
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
            inbox_result = build_blocked_inbox_read_result(
                blocked_reasons=["real Gmail inbox read is disabled"],
            )
            authorized_display = "not loaded"

        elif not confirmation_accepted:
            inbox_result = build_blocked_inbox_read_result(
                blocked_reasons=["real Gmail inbox read confirmation phrase was not accepted"],
            )
            authorized_display = "not loaded"

        else:
            config = load_gmail_approval_inbox_config_from_env()
            inbox_result = read_gmail_approval_inbox(
                config=config,
                max_results=max_results,
                imap_client_factory=injected_imap_client_factory,
            )
            authorized_display = mask_email(config.authorized_from_email)

        process_result = process_gmail_approval_emails(
            inbox_result=inbox_result,
            approvals_dir=approvals_dir,
        )

    except Exception as exc:
        print("GMAIL APPROVAL PROCESSOR REPORT: FAIL")
        print(f"Reason: {exc}")
        print("Inbox client used: false")
        print("Approval records updated: 0")
        print("Broker order call performed: false")
        print("LIVE TRADING: DISABLED")
        return 1

    print("GMAIL APPROVAL PROCESSOR REPORT: PASS")
    print(f"Inbox read enabled: {str(enable_real_inbox_read).lower()}")
    print(f"Confirmation accepted: {str(confirmation_accepted).lower()}")
    print(f"Inbox client used: {str(inbox_result.inbox_client_used).lower()}")
    print(f"Mailbox selected readonly: {str(inbox_result.mailbox_selected_readonly).lower()}")
    print(f"Messages marked read: {str(inbox_result.messages_marked_read).lower()}")
    print(f"Scanned approval emails: {inbox_result.scanned_count}")
    print(f"Authorized sender: {authorized_display}")
    print(f"Processor blocked reasons: {process_result.blocked_reasons}")
    print(f"Processed approval emails: {process_result.processed_count}")
    print(f"Approval records updated: {process_result.applied_count}")

    for item in process_result.processed_emails:
        print("---")
        print(f"Message id: {item.message_id}")
        print(f"From: {mask_email(item.from_email)}")
        print(f"Subject: {item.subject}")
        print(f"Parsed action: {item.action}")
        print(f"Parsed approval id: {item.approval_id}")
        print(f"Command valid: {str(item.command_valid).lower()}")
        print(f"Sender authorized: {str(item.sender_authorized).lower()}")
        print(f"Applied to approval record: {str(item.applied).lower()}")
        print(f"Decision status: {item.decision_status}")
        print(f"Email blocked reasons: {item.blocked_reasons}")

    print("Broker order call performed: false")
    print("LIVE TRADING: DISABLED")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Process Gmail approval commands safely.")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--approvals-dir", type=Path, default=Path("reports/approvals"))
    parser.add_argument("--max-results", type=int, default=10)
    parser.add_argument("--enable-real-inbox-read", action="store_true")
    parser.add_argument("--confirmation", default=None)
    args = parser.parse_args()

    return run_gmail_approval_processor_report(
        env_file=args.env_file,
        approvals_dir=args.approvals_dir,
        max_results=args.max_results,
        enable_real_inbox_read=args.enable_real_inbox_read,
        confirmation=args.confirmation,
    )


if __name__ == "__main__":
    raise SystemExit(main())
