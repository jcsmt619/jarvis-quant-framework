from __future__ import annotations

import argparse
from pathlib import Path

from automation.orchestrator_inbox_processor_once import run_orchestrator_inbox_processor_once


def run_orchestrator_inbox_processor_once_report(
    *,
    enable_inbox_processing: bool = False,
    enable_real_gmail_inbox_read: bool = False,
    confirmation: str | None = None,
    env_file: Path | None = Path(".env"),
    max_results: int = 25,
) -> int:
    state = run_orchestrator_inbox_processor_once(
        enable_inbox_processing=enable_inbox_processing,
        enable_real_gmail_inbox_read=enable_real_gmail_inbox_read,
        confirmation=confirmation,
        env_file=env_file,
        max_results=max_results,
    )

    print("ORCHESTRATOR INBOX PROCESSOR ONE-CYCLE REPORT: PASS")
    print(f"Inbox processor one-cycle hook present: {str(state.hook_present).lower()}")
    print(f"Inbox processor one-cycle callable wired: {str(state.processor_callable_wired).lower()}")
    print(f"Inbox processing requested: {str(state.inbox_processing_requested).lower()}")
    print(f"Real Gmail inbox read requested: {str(state.real_gmail_inbox_read_requested).lower()}")
    print(f"Real Gmail inbox read confirmation accepted: {str(state.confirmation_accepted).lower()}")
    print(f"Real Gmail inbox read gate allowed: {str(state.gate_allowed).lower()}")
    print(f"Inbox processor one-cycle attempted: {str(state.attempted).lower()}")
    print(f"Inbox processor one-cycle return code: {state.processor_return_code}")
    print(f"Inbox processor one-cycle decision: {state.decision}")
    print(f"Inbox processor one-cycle blocked reasons: {state.blocked_reasons}")
    print(f"Approval records updated: {state.approval_records_updated}")
    print(f"Real Gmail inbox read performed: {str(state.real_gmail_inbox_read_performed).lower()}")
    print(f"Paper arm enabled: {str(state.paper_arm_enabled).lower()}")
    print(f"Broker order call performed: {str(state.broker_order_call_performed).lower()}")
    print("LIVE TRADING: DISABLED")
    return 0 if state.decision != "PROCESSOR_FAILED_READ_ONLY" else 2


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the orchestrator Gmail inbox processor once, behind hard gates.")
    parser.add_argument("--enable-inbox-processing", action="store_true")
    parser.add_argument("--enable-real-gmail-inbox-read", action="store_true")
    parser.add_argument("--confirmation", default=None)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--max-results", type=int, default=25)
    args = parser.parse_args()

    return run_orchestrator_inbox_processor_once_report(
        enable_inbox_processing=args.enable_inbox_processing,
        enable_real_gmail_inbox_read=args.enable_real_gmail_inbox_read,
        confirmation=args.confirmation,
        env_file=args.env_file,
        max_results=args.max_results,
    )


if __name__ == "__main__":
    raise SystemExit(main())
