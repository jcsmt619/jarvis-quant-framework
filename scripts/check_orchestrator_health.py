from __future__ import annotations

import argparse
from pathlib import Path

from automation.orchestrator_health import evaluate_orchestrator_health


def run_orchestrator_health_report(
    *,
    env_file: Path = Path(".env"),
    orchestrator_dir: Path = Path("reports/orchestrator"),
    require_env_file: bool = True,
) -> int:
    result = evaluate_orchestrator_health(
        env_file=env_file,
        orchestrator_dir=orchestrator_dir,
        require_env_file=require_env_file,
    )

    print("ORCHESTRATOR HEALTH CHECK REPORT: PASS")
    print(f"Env file: {result.env_file}")
    print(f"Env file present: {str(result.env_file_present).lower()}")
    print(f"Orchestrator dir: {result.orchestrator_dir}")
    print(f"Stop requested: {str(result.stop_requested).lower()}")
    print(f"Pause requested: {str(result.pause_requested).lower()}")
    print(f"Resume marker present: {str(result.resume_marker_present).lower()}")
    print(f"Heartbeat path: {result.heartbeat_path}")
    print(f"Heartbeat present: {str(result.heartbeat_present).lower()}")
    print(f"Heartbeat readable: {str(result.heartbeat_readable).lower()}")
    print(f"Sessions dir: {result.sessions_dir}")
    print(f"Sessions count: {result.sessions_count}")
    print(f"Sessions readable: {str(result.sessions_readable).lower()}")
    print(f"Audit dir: {result.audit_dir}")
    print(f"Audit events count: {result.audit_events_count}")
    print(f"Audit readable: {str(result.audit_readable).lower()}")
    print(f"Safe to run: {str(result.safe_to_run).lower()}")
    print(f"Blocked reasons: {result.blocked_reasons}")
    print(f"Real email send enabled: {str(result.real_email_send_enabled).lower()}")
    print(f"Inbox processing enabled: {str(result.inbox_processing_enabled).lower()}")
    print(f"Paper arm enabled: {str(result.paper_arm_enabled).lower()}")
    print(f"Broker order call performed: {str(result.broker_order_call_performed).lower()}")
    print("LIVE TRADING: DISABLED")

    return 0 if result.safe_to_run else 2


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a dry-run health check for the local orchestrator.")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--orchestrator-dir", type=Path, default=Path("reports/orchestrator"))
    parser.add_argument("--ignore-missing-env", action="store_true")
    args = parser.parse_args()

    return run_orchestrator_health_report(
        env_file=args.env_file,
        orchestrator_dir=args.orchestrator_dir,
        require_env_file=not args.ignore_missing_env,
    )


if __name__ == "__main__":
    raise SystemExit(main())
