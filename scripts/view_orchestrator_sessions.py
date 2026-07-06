from __future__ import annotations

import argparse
from pathlib import Path

from automation.orchestrator_session import SESSION_MANIFESTS_DIR_NAME, list_session_manifests


def run_orchestrator_session_report(
    *,
    orchestrator_dir: Path = Path("reports/orchestrator"),
    limit: int = 10,
) -> int:
    session_dir = orchestrator_dir / SESSION_MANIFESTS_DIR_NAME
    manifests = list_session_manifests(session_dir=session_dir)
    shown = manifests[-limit:] if limit > 0 else []

    print("ORCHESTRATOR SESSION REPORT: PASS")
    print(f"Session dir: {session_dir}")
    print(f"Sessions count: {len(manifests)}")
    print(f"Sessions shown: {len(shown)}")

    for manifest in shown:
        print("---")
        print(f"Manifest path: {manifest.get('_path')}")
        print(f"Session id: {manifest.get('session_id')}")
        print(f"Started at UTC: {manifest.get('started_at_utc')}")
        print(f"Ended at UTC: {manifest.get('ended_at_utc')}")
        print(f"Symbol: {manifest.get('symbol')}")
        print(f"Engine: {manifest.get('engine')}")
        print(f"Max cycles: {manifest.get('max_cycles')}")
        print(f"Cycles attempted: {manifest.get('cycles_attempted')}")
        print(f"Final decision: {manifest.get('final_decision')}")
        print(f"Final return code: {manifest.get('final_return_code')}")
        print(f"Audit ledger path: {manifest.get('audit_ledger_path')}")
        print(f"Inbox processing enabled: {str(manifest.get('inbox_processing_enabled')).lower()}")
        print(f"Paper arm enabled: {str(manifest.get('paper_arm_enabled')).lower()}")
        print(f"Broker order call performed: {str(manifest.get('broker_order_call_performed')).lower()}")
        print(f"Live trading enabled: {str(manifest.get('live_trading_enabled')).lower()}")

    print("Broker order call performed: false")
    print("LIVE TRADING: DISABLED")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="View local orchestrator session manifests.")
    parser.add_argument("--orchestrator-dir", type=Path, default=Path("reports/orchestrator"))
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    return run_orchestrator_session_report(
        orchestrator_dir=args.orchestrator_dir,
        limit=args.limit,
    )


if __name__ == "__main__":
    raise SystemExit(main())
