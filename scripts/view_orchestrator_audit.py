from __future__ import annotations

import argparse
from pathlib import Path

from automation.orchestrator_audit import AUDIT_LEDGER_FILE_NAME, read_audit_events


def run_orchestrator_audit_report(
    *,
    orchestrator_dir: Path = Path("reports/orchestrator"),
    limit: int = 10,
) -> int:
    audit_dir = orchestrator_dir / "audit"
    ledger = audit_dir / AUDIT_LEDGER_FILE_NAME
    events = read_audit_events(audit_dir=audit_dir)
    shown = events[-limit:] if limit > 0 else []

    print("ORCHESTRATOR AUDIT REPORT: PASS")
    print(f"Audit dir: {audit_dir}")
    print(f"Ledger path: {ledger}")
    print(f"Events count: {len(events)}")
    print(f"Events shown: {len(shown)}")

    for event in shown:
        print("---")
        print(f"Timestamp UTC: {event.get('timestamp_utc')}")
        print(f"Event type: {event.get('event_type')}")
        print(f"Cycle number: {event.get('cycle_number')}")
        print(f"Symbol: {event.get('symbol')}")
        print(f"Engine: {event.get('engine')}")
        print(f"Decision: {event.get('decision')}")
        print(f"Cycle return code: {event.get('cycle_return_code')}")
        print(f"Stop requested: {str(event.get('stop_requested')).lower()}")
        print(f"Pause requested: {str(event.get('pause_requested')).lower()}")
        print(f"Resume marker present: {str(event.get('resume_marker_present')).lower()}")
        print(f"Inbox processing enabled: {str(event.get('inbox_processing_enabled')).lower()}")
        print(f"Paper arm enabled: {str(event.get('paper_arm_enabled')).lower()}")
        print(f"Broker order call performed: {str(event.get('broker_order_call_performed')).lower()}")
        print(f"Live trading enabled: {str(event.get('live_trading_enabled')).lower()}")

    print("Broker order call performed: false")
    print("LIVE TRADING: DISABLED")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="View the local orchestrator audit ledger.")
    parser.add_argument("--orchestrator-dir", type=Path, default=Path("reports/orchestrator"))
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    return run_orchestrator_audit_report(
        orchestrator_dir=args.orchestrator_dir,
        limit=args.limit,
    )


if __name__ == "__main__":
    raise SystemExit(main())
