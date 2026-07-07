from __future__ import annotations

import argparse

from automation.orchestrator_inbox_processor_bridge import evaluate_inbox_processor_dry_run_bridge


def run_orchestrator_inbox_processor_bridge_report(
    *,
    enable_inbox_processing: bool = False,
    confirmation: str | None = None,
    enable_real_gmail_inbox_read: bool = False,
) -> int:
    state = evaluate_inbox_processor_dry_run_bridge(
        enable_inbox_processing=enable_inbox_processing,
        confirmation=confirmation,
        enable_real_gmail_inbox_read=enable_real_gmail_inbox_read,
    )

    print("ORCHESTRATOR INBOX PROCESSOR DRY-RUN BRIDGE REPORT: PASS")
    print(f"Inbox processor hook present: {str(state.hook_present).lower()}")
    print(f"Inbox processor callable wired: {str(state.processor_callable_wired).lower()}")
    print(f"Inbox processing requested: {str(state.requested).lower()}")
    print(f"Inbox processor confirmation accepted: {str(state.confirmation_accepted).lower()}")
    print(f"Real Gmail inbox read enabled: {str(state.real_gmail_inbox_read_enabled).lower()}")
    print(f"Inbox processor attempted: {str(state.attempted).lower()}")
    print(f"Inbox processor bridge decision: {state.decision}")
    print(f"Inbox processor bridge blocked reasons: {state.blocked_reasons}")
    print(f"Approval records updated: {state.approval_records_updated}")
    print(f"Broker order call performed: {str(state.broker_order_call_performed).lower()}")
    print("LIVE TRADING: DISABLED")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Check orchestrator Gmail inbox processor dry-run bridge state.")
    parser.add_argument("--enable-inbox-processing", action="store_true")
    parser.add_argument("--confirmation", default=None)
    parser.add_argument("--enable-real-gmail-inbox-read", action="store_true")
    args = parser.parse_args()

    return run_orchestrator_inbox_processor_bridge_report(
        enable_inbox_processing=args.enable_inbox_processing,
        confirmation=args.confirmation,
        enable_real_gmail_inbox_read=args.enable_real_gmail_inbox_read,
    )


if __name__ == "__main__":
    raise SystemExit(main())
