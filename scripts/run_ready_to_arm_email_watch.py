from __future__ import annotations

import argparse
import ast
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

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


@dataclass(frozen=True)
class ReadyToArmParseResult:
    ready_to_arm: bool | None
    intent_action: str
    reasons: list[str]


def parse_ready_to_arm_output(output: str) -> ReadyToArmParseResult:
    ready_to_arm: bool | None = None
    intent_action = "UNKNOWN"
    reasons: list[str] = []

    for line in output.splitlines():
        stripped = line.strip()

        if stripped.startswith("Intent action:"):
            intent_action = stripped.split(":", 1)[1].strip() or "UNKNOWN"

        elif stripped.startswith("READY TO ARM:"):
            raw_value = stripped.split(":", 1)[1].strip().lower()
            if raw_value == "true":
                ready_to_arm = True
            elif raw_value == "false":
                ready_to_arm = False
            else:
                ready_to_arm = None

        elif stripped.startswith("READY TO ARM REASONS:"):
            raw_reasons = stripped.split(":", 1)[1].strip()
            try:
                parsed = ast.literal_eval(raw_reasons)
                if isinstance(parsed, list):
                    reasons = [str(item) for item in parsed]
                elif parsed:
                    reasons = [str(parsed)]
                else:
                    reasons = []
            except Exception:
                reasons = [raw_reasons] if raw_reasons else []

    return ReadyToArmParseResult(
        ready_to_arm=ready_to_arm,
        intent_action=intent_action,
        reasons=reasons,
    )


def _default_workflow_runner(command: list[str]) -> Any:
    return subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
    )


def run_ready_to_arm_email_watch(
    *,
    env_file: Path | None = Path(".env"),
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

    print("READY TO ARM EMAIL WATCH")
    print(f"Wrapped workflow return code: {returncode}")
    print("Wrapped workflow stdout:")
    print(stdout)

    if stderr:
        print("Wrapped workflow stderr:")
        print(stderr)

    if returncode != 0:
        print("READY TO ARM EMAIL WATCH: FAIL")
        print("Email alert decision: SKIPPED_WORKFLOW_FAILED")
        print("Email sent: false")
        print("LIVE TRADING: DISABLED")
        return returncode

    parsed = parse_ready_to_arm_output(stdout)

    print(f"Ready to arm detected: {str(parsed.ready_to_arm).lower() if parsed.ready_to_arm is not None else 'unknown'}")
    print(f"Parsed intent action: {parsed.intent_action}")
    print(f"Parsed ready reasons: {parsed.reasons}")

    if parsed.ready_to_arm is not True:
        decision = "SKIPPED_READY_TO_ARM_FALSE" if parsed.ready_to_arm is False else "SKIPPED_READY_TO_ARM_UNKNOWN"
        print("READY TO ARM EMAIL WATCH: PASS")
        print(f"Email alert decision: {decision}")
        print("SMTP client used: false")
        print("Email sent: false")
        print("LIVE TRADING: DISABLED")
        return 0

    event = "READY_TO_ARM_TRUE"
    subject = build_email_alert_subject(
        event=event,
        symbol=symbol,
        ready_to_arm=True,
    )
    body = build_email_alert_body(
        event=event,
        engine=engine,
        symbol=symbol,
        intent_action=parsed.intent_action,
        ready_to_arm=True,
        reasons=parsed.reasons,
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
            if env_file is not None:
                load_env_file(env_file)

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
        print("READY TO ARM EMAIL WATCH: FAIL")
        print(f"Reason: {exc}")
        print("Email sent: false")
        print("LIVE TRADING: DISABLED")
        return 1

    print("READY TO ARM EMAIL WATCH: PASS")
    print("Email alert decision: READY_TO_ARM_TRUE")
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
    parser = argparse.ArgumentParser(description="Run Jarvis workflow and email only when READY TO ARM is true.")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--symbol", default="EEM")
    parser.add_argument("--limit", type=int, default=120)
    parser.add_argument("--feed", default="iex")
    parser.add_argument("--engine", default="Wealth")
    parser.add_argument("--enable-real-email-send", action="store_true")
    parser.add_argument("--confirmation", default=None)
    args = parser.parse_args()

    return run_ready_to_arm_email_watch(
        env_file=args.env_file,
        symbol=args.symbol,
        limit=args.limit,
        feed=args.feed,
        engine=args.engine,
        enable_real_email_send=args.enable_real_email_send,
        confirmation=args.confirmation,
    )


if __name__ == "__main__":
    raise SystemExit(main())
