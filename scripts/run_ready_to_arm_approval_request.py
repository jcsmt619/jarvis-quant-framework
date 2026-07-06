from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from automation.approval_gateway import ApprovalRecord, create_approval_record, write_approval_record
from paper_trading.email_alerts import (
    GMAIL_EMAIL_CONFIRMATION,
    build_blocked_email_result,
    load_gmail_email_config_from_env,
    mask_email,
    send_email_alert,
)
from scripts.check_alpaca_paper_connection import load_env_file
from scripts.run_ready_to_arm_email_watch import parse_ready_to_arm_output


@dataclass(frozen=True)
class ReadyToArmApprovalRequestResult:
    workflow_return_code: int
    ready_to_arm: bool | None
    intent_action: str
    ready_reasons: list[str]
    approval_record_created: bool
    approval_id: str | None
    approval_path: str | None
    email_sent: bool
    smtp_client_used: bool
    blocked_reasons: list[str]
    broker_order_call_performed: bool = False
    live_trading_enabled: bool = False


def _default_workflow_runner(command: list[str]) -> Any:
    return subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
    )


def build_ready_to_arm_approval_subject(
    *,
    symbol: str,
    approval_id: str,
) -> str:
    return f"Jarvis Approval Required: READY_TO_ARM_TRUE | {symbol} | {approval_id}"


def build_ready_to_arm_approval_body(
    *,
    engine: str,
    symbol: str,
    intent_action: str,
    approval_record: ApprovalRecord,
    ready_reasons: list[str],
) -> str:
    reasons = ready_reasons or ["none"]

    lines = [
        "Jarvis READY TO ARM approval request",
        "",
        f"Engine: {engine}",
        f"Symbol: {symbol}",
        f"Intent action: {intent_action}",
        f"Approval ID: {approval_record.approval_id}",
        f"Expires UTC: {approval_record.expires_at_utc}",
        "",
        "Reply with exactly one of these commands as the first line:",
        f"APPROVE {approval_record.approval_id}",
        f"DENY {approval_record.approval_id}",
        "",
        "Ready reasons:",
    ]

    for reason in reasons:
        lines.append(f"- {reason}")

    lines.extend(
        [
            "",
            "Safety:",
            "- This email only requests approval.",
            "- This email does not submit broker orders.",
            "- Gmail approval does not enable live trading.",
            "- LIVE TRADING: DISABLED",
        ]
    )

    return "\n".join(lines)


def run_ready_to_arm_approval_request(
    *,
    env_file: Path | None = Path(".env"),
    approvals_dir: Path = Path("reports/approvals"),
    symbol: str = "EEM",
    limit: int = 120,
    feed: str = "iex",
    engine: str = "Wealth",
    enable_real_email_send: bool = False,
    confirmation: str | None = None,
    injected_workflow_runner: Callable[[list[str]], Any] | None = None,
    injected_smtp_client_factory: Callable | None = None,
) -> int:
    command = [
        sys.executable,
        "-m",
        "scripts.run_fetch_then_real_paper_executor",
        "--symbol",
        symbol,
        "--limit",
        str(limit),
        "--feed",
        feed,
    ]

    if env_file is not None:
        command.extend(["--env-file", str(env_file)])

    workflow_runner = injected_workflow_runner or _default_workflow_runner
    completed = workflow_runner(command)

    stdout = getattr(completed, "stdout", "") or ""
    stderr = getattr(completed, "stderr", "") or ""
    returncode = int(getattr(completed, "returncode", 1))

    print("READY TO ARM APPROVAL REQUEST REPORT")
    print(f"Wrapped workflow return code: {returncode}")
    print("Wrapped workflow stdout:")
    print(stdout)

    if stderr:
        print("Wrapped workflow stderr:")
        print(stderr)

    if returncode != 0:
        print("READY TO ARM APPROVAL REQUEST: FAIL")
        print("Approval record created: false")
        print("Email sent: false")
        print("Broker order call performed: false")
        print("LIVE TRADING: DISABLED")
        return returncode

    parsed = parse_ready_to_arm_output(stdout)

    print(f"Ready to arm detected: {str(parsed.ready_to_arm).lower() if parsed.ready_to_arm is not None else 'unknown'}")
    print(f"Parsed intent action: {parsed.intent_action}")
    print(f"Parsed ready reasons: {parsed.reasons}")

    if parsed.ready_to_arm is not True:
        decision = "SKIPPED_READY_TO_ARM_FALSE" if parsed.ready_to_arm is False else "SKIPPED_READY_TO_ARM_UNKNOWN"
        print("READY TO ARM APPROVAL REQUEST: PASS")
        print(f"Approval request decision: {decision}")
        print("Approval record created: false")
        print("Email sent: false")
        print("Broker order call performed: false")
        print("LIVE TRADING: DISABLED")
        return 0

    approval_record = create_approval_record(
        target="READY_TO_ARM_REVIEW",
        source="gmail",
        note=f"{engine} {symbol} {parsed.intent_action} READY_TO_ARM review",
    )
    approval_path = write_approval_record(approval_record, output_dir=approvals_dir)

    subject = build_ready_to_arm_approval_subject(
        symbol=symbol,
        approval_id=approval_record.approval_id,
    )
    body = build_ready_to_arm_approval_body(
        engine=engine,
        symbol=symbol,
        intent_action=parsed.intent_action,
        approval_record=approval_record,
        ready_reasons=parsed.reasons,
    )

    confirmation_accepted = confirmation == GMAIL_EMAIL_CONFIRMATION

    try:
        if not enable_real_email_send:
            email_result = build_blocked_email_result(
                event="READY_TO_ARM_APPROVAL_REQUEST",
                subject=subject,
                body=body,
                blocked_reasons=["real email send is disabled"],
            )
            from_display = "not loaded"
            to_display = "not loaded"

        elif not confirmation_accepted:
            email_result = build_blocked_email_result(
                event="READY_TO_ARM_APPROVAL_REQUEST",
                subject=subject,
                body=body,
                blocked_reasons=["real email confirmation phrase was not accepted"],
            )
            from_display = "not loaded"
            to_display = "not loaded"

        else:
            if env_file is not None:
                load_env_file(env_file)

            config = load_gmail_email_config_from_env()
            email_result = send_email_alert(
                config=config,
                event="READY_TO_ARM_APPROVAL_REQUEST",
                subject=subject,
                body=body,
                smtp_client_factory=injected_smtp_client_factory,
            )
            from_display = mask_email(config.from_email)
            to_display = mask_email(config.to_email)

    except Exception as exc:
        print("READY TO ARM APPROVAL REQUEST: FAIL")
        print(f"Reason: {exc}")
        print(f"Approval record created: true")
        print(f"Approval id: {approval_record.approval_id}")
        print(f"Approval path: {approval_path}")
        print("Email sent: false")
        print("Broker order call performed: false")
        print("LIVE TRADING: DISABLED")
        return 1

    print("READY TO ARM APPROVAL REQUEST: PASS")
    print("Approval request decision: READY_TO_ARM_TRUE")
    print("Approval record created: true")
    print(f"Approval id: {approval_record.approval_id}")
    print(f"Approval path: {approval_path}")
    print(f"Approval command: APPROVE {approval_record.approval_id}")
    print(f"Deny command: DENY {approval_record.approval_id}")
    print(f"Email send enabled: {str(enable_real_email_send).lower()}")
    print(f"Confirmation accepted: {str(confirmation_accepted).lower()}")
    print(f"SMTP client used: {str(email_result.smtp_client_used).lower()}")
    print(f"Email sent: {str(email_result.sent).lower()}")
    print(f"From: {from_display}")
    print(f"To: {to_display}")
    print(f"Blocked reasons: {email_result.blocked_reasons}")
    print(f"Subject: {email_result.subject}")
    print("Email body:")
    print(email_result.body)
    print("Broker order call performed: false")
    print("LIVE TRADING: DISABLED")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Create and email approval request when READY TO ARM is true.")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--approvals-dir", type=Path, default=Path("reports/approvals"))
    parser.add_argument("--symbol", default="EEM")
    parser.add_argument("--limit", type=int, default=120)
    parser.add_argument("--feed", default="iex")
    parser.add_argument("--engine", default="Wealth")
    parser.add_argument("--enable-real-email-send", action="store_true")
    parser.add_argument("--confirmation", default=None)
    args = parser.parse_args()

    return run_ready_to_arm_approval_request(
        env_file=args.env_file,
        approvals_dir=args.approvals_dir,
        symbol=args.symbol,
        limit=args.limit,
        feed=args.feed,
        engine=args.engine,
        enable_real_email_send=args.enable_real_email_send,
        confirmation=args.confirmation,
    )


if __name__ == "__main__":
    raise SystemExit(main())
