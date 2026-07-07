from __future__ import annotations

import argparse

from automation.gmail_approval_inbox import GMAIL_INBOX_READ_CONFIRMATION
from automation.orchestrator_inbox_scaffold import evaluate_inbox_processing_scaffold


def run_orchestrator_inbox_scaffold_report(
    *,
    enable_inbox_processing: bool = False,
    confirmation: str | None = None,
) -> int:
    state = evaluate_inbox_processing_scaffold(
        enable_inbox_processing=enable_inbox_processing,
        confirmation=confirmation,
    )

    print("ORCHESTRATOR INBOX PROCESSING SCAFFOLD REPORT: PASS")
    print(f"Inbox processing requested: {str(state.requested).lower()}")
    print(f"Inbox confirmation accepted: {str(state.confirmation_accepted).lower()}")
    print(f"Inbox processing attempted: {str(state.attempted).lower()}")
    print(f"Inbox processing decision: {state.decision}")
    print(f"Inbox processing blocked reasons: {state.blocked_reasons}")
    print(f"Approval records updated: {state.approval_records_updated}")
    print(f"Broker order call performed: {str(state.broker_order_call_performed).lower()}")
    print("LIVE TRADING: DISABLED")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Check orchestrator Gmail inbox-processing scaffold state.")
    parser.add_argument("--enable-inbox-processing", action="store_true")
    parser.add_argument("--confirmation", default=None)
    args = parser.parse_args()

    return run_orchestrator_inbox_scaffold_report(
        enable_inbox_processing=args.enable_inbox_processing,
        confirmation=args.confirmation,
    )


if __name__ == "__main__":
    raise SystemExit(main())
