from __future__ import annotations

import argparse
from pathlib import Path
from typing import Callable

from paper_trading.sms_alerts import (
    TWILIO_SMS_CONFIRMATION,
    SmsAlertResult,
    build_blocked_sms_result,
    build_sms_alert_body,
    load_twilio_sms_config_from_env,
    mask_phone_number,
    send_sms_alert,
)
from scripts.check_alpaca_paper_connection import load_env_file


def run_sms_alert_report(
    *,
    env_file: Path | None = None,
    event: str = "TEST_ALERT",
    engine: str = "Jarvis",
    symbol: str = "EEM",
    intent_action: str = "UNKNOWN",
    ready_to_arm: bool | None = None,
    reasons: list[str] | None = None,
    enable_real_sms_send: bool = False,
    confirmation: str | None = None,
    injected_twilio_client_factory: Callable | None = None,
) -> int:
    if env_file is not None:
        load_env_file(env_file)

    body = build_sms_alert_body(
        event=event,
        engine=engine,
        symbol=symbol,
        intent_action=intent_action,
        ready_to_arm=ready_to_arm,
        reasons=reasons or [],
    )

    confirmation_accepted = confirmation == TWILIO_SMS_CONFIRMATION

    try:
        if not enable_real_sms_send:
            result = build_blocked_sms_result(
                event=event,
                body=body,
                blocked_reasons=["real SMS send is disabled"],
            )
            owner_display = "not loaded"

        elif not confirmation_accepted:
            result = build_blocked_sms_result(
                event=event,
                body=body,
                blocked_reasons=["real SMS confirmation phrase was not accepted"],
            )
            owner_display = "not loaded"

        else:
            config = load_twilio_sms_config_from_env()
            result = send_sms_alert(
                config=config,
                event=event,
                body=body,
                twilio_client_factory=injected_twilio_client_factory,
            )
            owner_display = mask_phone_number(config.owner_phone)

    except Exception as exc:
        print("SMS ALERT REPORT: FAIL")
        print(f"Reason: {exc}")
        print("SMS SENT: false")
        print("LIVE TRADING: DISABLED")
        return 1

    print("SMS ALERT REPORT: PASS")
    print(f"Event: {result.event}")
    print(f"SMS send enabled: {str(enable_real_sms_send).lower()}")
    print(f"Confirmation accepted: {str(confirmation_accepted).lower()}")
    print(f"Twilio client used: {str(result.twilio_client_used).lower()}")
    print(f"SMS sent: {str(result.sent).lower()}")
    print(f"Message SID: {result.message_sid}")
    print(f"Message status: {result.message_status}")
    print(f"Owner phone: {owner_display}")
    print(f"Blocked reasons: {result.blocked_reasons}")
    print("SMS body:")
    print(result.body)
    print("LIVE TRADING: DISABLED")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Send or dry-run a Jarvis Twilio SMS alert.")
    parser.add_argument("--env-file", type=Path, default=None)
    parser.add_argument("--event", default="TEST_ALERT")
    parser.add_argument("--engine", default="Jarvis")
    parser.add_argument("--symbol", default="EEM")
    parser.add_argument("--intent-action", default="UNKNOWN")
    parser.add_argument("--ready-to-arm", choices=["true", "false", "unknown"], default="unknown")
    parser.add_argument("--reason", action="append", default=[])
    parser.add_argument("--enable-real-sms-send", action="store_true")
    parser.add_argument("--confirmation", default=None)
    args = parser.parse_args()

    ready_to_arm = None
    if args.ready_to_arm == "true":
        ready_to_arm = True
    elif args.ready_to_arm == "false":
        ready_to_arm = False

    return run_sms_alert_report(
        env_file=args.env_file,
        event=args.event,
        engine=args.engine,
        symbol=args.symbol,
        intent_action=args.intent_action,
        ready_to_arm=ready_to_arm,
        reasons=args.reason,
        enable_real_sms_send=args.enable_real_sms_send,
        confirmation=args.confirmation,
    )


if __name__ == "__main__":
    raise SystemExit(main())
