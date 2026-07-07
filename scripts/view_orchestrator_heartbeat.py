from __future__ import annotations

import argparse
from pathlib import Path

from automation.orchestrator_heartbeat import HEARTBEAT_FILE_NAME, read_heartbeat


def run_orchestrator_heartbeat_report(
    *,
    orchestrator_dir: Path = Path("reports/orchestrator"),
) -> int:
    path = orchestrator_dir / HEARTBEAT_FILE_NAME

    print("ORCHESTRATOR HEARTBEAT REPORT: PASS")
    print(f"Heartbeat path: {path}")

    if not path.exists():
        print("Heartbeat present: false")
        print("Broker order call performed: false")
        print("LIVE TRADING: DISABLED")
        return 0

    data = read_heartbeat(path)

    print("Heartbeat present: true")
    print(f"Session id: {data.get('session_id')}")
    print(f"Timestamp UTC: {data.get('timestamp_utc')}")
    print(f"Cycle number: {data.get('cycle_number')}")
    print(f"Symbol: {data.get('symbol')}")
    print(f"Engine: {data.get('engine')}")
    print(f"Last decision: {data.get('last_decision')}")
    print(f"Cycles attempted: {data.get('cycles_attempted')}")
    print(f"Max cycles: {data.get('max_cycles')}")
    print(f"Stop requested: {str(data.get('stop_requested')).lower()}")
    print(f"Pause requested: {str(data.get('pause_requested')).lower()}")
    print(f"Resume marker present: {str(data.get('resume_marker_present')).lower()}")
    print(f"Audit ledger path: {data.get('audit_ledger_path')}")
    print(f"Session manifest path: {data.get('session_manifest_path')}")
    print(f"Inbox processing enabled: {str(data.get('inbox_processing_enabled')).lower()}")
    print(f"Paper arm enabled: {str(data.get('paper_arm_enabled')).lower()}")
    print(f"Broker order call performed: {str(data.get('broker_order_call_performed')).lower()}")
    print(f"Live trading enabled: {str(data.get('live_trading_enabled')).lower()}")
    print(f"Heartbeat notes: {data.get('notes')}")
    print("Broker order call performed: false")
    print("LIVE TRADING: DISABLED")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="View the local orchestrator heartbeat file.")
    parser.add_argument("--orchestrator-dir", type=Path, default=Path("reports/orchestrator"))
    args = parser.parse_args()

    return run_orchestrator_heartbeat_report(orchestrator_dir=args.orchestrator_dir)


if __name__ == "__main__":
    raise SystemExit(main())
