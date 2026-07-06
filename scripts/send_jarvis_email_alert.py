from __future__ import annotations

import argparse
from pathlib import Path
from typing import Callable

from paper_trading.email_alerts import (
    GMAIL_EMAIL_CONFIRMATION,
    build_blocked_email_result,
    build_email_alert_body,
    build_email_alert_subject,
    load_gmail_email_config_from_env,
    mask_email,
    send_email_alert,
)
from scripts.check_alpaca_paper_connection import load_env_file


def run_email_alert_report(
    *,
    env_file: Path | None = None,
    event: str = "TEST_ALERT",
    engine: str = "Jarvis",
    symbol: str = "EEM",
    intent_action: str = "UNKNOWN",
    ready_to_arm: bool | None = None,
    reasons: list[str] | None = None,
    enable_real_email_send: bool = False,
    confirmation: str | None = None,
    injected_smtp_client_factory: Callable | None = None,
) -> int:
    if env_file is not None:
        load_env_file(env_file)

    subject = build_email_alert_subject(
        event=event,
        symbol=symbol,
        ready_to_arm=ready_to_arm,
    )
    body = build_email_alert_body(
        event=event,
        engine=engine,
        symbol=symbol,
        intent_action=intent_action,
        ready_to_arm=ready_to_arm,
        reasons=reasons or [],
    )

    confirmation_accepted = confirmation == GMAIL_EMAIL_CONFIRMATION

    try:
        if not enable_real_email_send:
            result = build_blocked_email_result(
                event=event,
                subject=subject,
                body=body,
                blocked_reasons=["real email send is disabled"],
            )
            from_display = "not loaded"
            to_display = "not loaded"

        elif not confirmation_accepted:
            result = build_blocked_email_result(
                event=event,
                subject=subject,
                body=body,
                blocked_reasons=["real email confirmation phrase was not accepted"],
            )
            from_display = "not loaded"
            to_display = "not loaded"

        else:
            config = load_gmail_email_config_from_env()
            result = send_email_alert(
                config=config,
                event=event,
                subject=subject,
                body=body,
                smtp_client_factory=injected_smtp_client_factory,
            )
            from_display = mask_email(config.from_email)
            to_display = mask_email(config.to_email)

    except Exception as exc:
        print("EMAIL ALERT REPORT: FAIL")
        print(f"Reason: {exc}")
        print("EMAIL SENT: false")
        print("LIVE TRADING: DISABLED")
        return 1

    print("EMAIL ALERT REPORT: PASS")
    print(f"Event: {result.event}")
    print(f"Email send enabled: {str(enable_real_email_send).lower()}")
    print(f"Confirmation accepted: {str(confirmation_accepted).lower()}")
    print(f"SMTP client used: {str(result.smtp_client_used).lower()}")
    print(f"Email sent: {str(result.sent).lower()}")
    print(f"From: {from_display}")
    print(f"To: {to_display}")
    print(f"Blocked reasons: {result.blocked_reasons}")
    print(f"Subject: {result.subject}")
    print("Email body:")
    print(result.body)
    print("LIVE TRADING: DISABLED")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Send or dry-run a Jarvis Gmail email alert.")
    parser.add_argument("--env-file", type=Path, default=None)
    parser.add_argument("--event", default="TEST_ALERT")
    parser.add_argument("--engine", default="Jarvis")
    parser.add_argument("--symbol", default="EEM")
    parser.add_argument("--intent-action", default="UNKNOWN")
    parser.add_argument("--ready-to-arm", choices=["true", "false", "unknown"], default="unknown")
    parser.add_argument("--reason", action="append", default=[])
    parser.add_argument("--enable-real-email-send", action="store_true")
    parser.add_argument("--confirmation", default=None)
    args = parser.parse_args()

    ready_to_arm = None
    if args.ready_to_arm == "true":
        ready_to_arm = True
    elif args.ready_to_arm == "false":
        ready_to_arm = False

    return run_email_alert_report(
        env_file=args.env_file,
        event=args.event,
        engine=args.engine,
        symbol=args.symbol,
        intent_action=args.intent_action,
        ready_to_arm=ready_to_arm,
        reasons=args.reason,
        enable_real_email_send=args.enable_real_email_send,
        confirmation=args.confirmation,
    )


if __name__ == "__main__":
    raise SystemExit(main())
