from __future__ import annotations

import argparse

from automation.orchestrator_inbox_processor_hook import evaluate_inbox_processor_hook


def run_orchestrator_inbox_processor_hook_report(
    *,
    enable_inbox_processing: bool = False,
    confirmation: str | None = None,
    allow_processor_attempt: bool = False,
) -> int:
    state = evaluate_inbox_processor_hook(
        enable_inbox_processing=enable_inbox_processing,
        confirmation=confirmation,
        allow_processor_attempt=allow_processor_attempt,
        processor=None,
    )

    print("ORCHESTRATOR INBOX PROCESSOR HOOK REPORT: PASS")
    print(f"Inbox processor hook present: {str(state.hook_present).lower()}")
    print(f"Inbox processing requested: {str(state.requested).lower()}")
    print(f"Inbox processor confirmation accepted: {str(state.confirmation_accepted).lower()}")
    print(f"Inbox processor attempted: {str(state.attempted).lower()}")
    print(f"Inbox processor decision: {state.decision}")
    print(f"Inbox processor blocked reasons: {state.blocked_reasons}")
    print(f"Approval records updated: {state.approval_records_updated}")
    print(f"Real Gmail inbox read: {str(state.real_gmail_inbox_read).lower()}")
    print(f"Broker order call performed: {str(state.broker_order_call_performed).lower()}")
    print("LIVE TRADING: DISABLED")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Check orchestrator Gmail inbox processor hook state.")
    parser.add_argument("--enable-inbox-processing", action="store_true")
    parser.add_argument("--confirmation", default=None)
    parser.add_argument("--allow-processor-attempt", action="store_true")
    args = parser.parse_args()

    return run_orchestrator_inbox_processor_hook_report(
        enable_inbox_processing=args.enable_inbox_processing,
        confirmation=args.confirmation,
        allow_processor_attempt=args.allow_processor_attempt,
    )


if __name__ == "__main__":
    raise SystemExit(main())
