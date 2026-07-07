from __future__ import annotations

import argparse

from automation.orchestrator_real_inbox_gate import evaluate_real_gmail_inbox_read_gate


def run_orchestrator_real_inbox_gate_report(
    *,
    enable_inbox_processing: bool = False,
    enable_real_gmail_inbox_read: bool = False,
    confirmation: str | None = None,
) -> int:
    state = evaluate_real_gmail_inbox_read_gate(
        enable_inbox_processing=enable_inbox_processing,
        enable_real_gmail_inbox_read=enable_real_gmail_inbox_read,
        confirmation=confirmation,
    )

    print("ORCHESTRATOR REAL GMAIL INBOX READ GATE REPORT: PASS")
    print(f"Inbox processing requested: {str(state.inbox_processing_requested).lower()}")
    print(f"Real Gmail inbox read requested: {str(state.real_gmail_inbox_read_requested).lower()}")
    print(f"Real Gmail inbox read confirmation accepted: {str(state.confirmation_accepted).lower()}")
    print(f"Real Gmail inbox read gate allowed: {str(state.gate_allowed).lower()}")
    print(f"Real Gmail inbox read attempted: {str(state.attempted).lower()}")
    print(f"Real Gmail inbox read performed: {str(state.real_gmail_inbox_read_performed).lower()}")
    print(f"Real Gmail inbox read decision: {state.decision}")
    print(f"Real Gmail inbox read blocked reasons: {state.blocked_reasons}")
    print(f"Approval records updated: {state.approval_records_updated}")
    print(f"Broker order call performed: {str(state.broker_order_call_performed).lower()}")
    print("LIVE TRADING: DISABLED")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Check orchestrator real Gmail inbox read gate state.")
    parser.add_argument("--enable-inbox-processing", action="store_true")
    parser.add_argument("--enable-real-gmail-inbox-read", action="store_true")
    parser.add_argument("--confirmation", default=None)
    args = parser.parse_args()

    return run_orchestrator_real_inbox_gate_report(
        enable_inbox_processing=args.enable_inbox_processing,
        enable_real_gmail_inbox_read=args.enable_real_gmail_inbox_read,
        confirmation=args.confirmation,
    )


if __name__ == "__main__":
    raise SystemExit(main())
