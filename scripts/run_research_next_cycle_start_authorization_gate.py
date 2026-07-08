from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.research_next_cycle_start_authorization_gate import (
    DEFAULT_RESEARCH_NEXT_CYCLE_START_AUTHORIZATION_GATE_DIR,
    build_default_research_next_cycle_start_authorization_gate_input,
    write_research_next_cycle_start_authorization_gate,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Write the 29A next cycle start authorization gate.")
    parser.add_argument("--out-dir", default=str(DEFAULT_RESEARCH_NEXT_CYCLE_START_AUTHORIZATION_GATE_DIR))
    parser.add_argument("--start-authorization-gate-date", default=None, help="YYYY-MM-DD; defaults to today UTC.")
    parser.add_argument("--start-checklist-packet-path", default=None)
    parser.add_argument("--start-preconditions-gate-path", default=None)
    parser.add_argument("--operator-handoff-packet-path", default=None)
    parser.add_argument("--launch-control-gate-path", default=None)
    parser.add_argument("--acceptance-packet-path", default=None)
    parser.add_argument("--dry-run-manifest-path", default=None)
    parser.add_argument("--safety-preflight-path", default=None)
    parser.add_argument("--next-cycle-plan-path", default=None)
    parser.add_argument("--report-index-path", default=None)
    parser.add_argument("--safe-workflow-catalog-path", default=None)
    parser.add_argument("--queue-status-path", default=None)
    parser.add_argument("--safety-scanner-path", default=None)
    args = parser.parse_args()

    start_authorization_gate_date = (
        datetime.strptime(args.start_authorization_gate_date, "%Y-%m-%d").date()
        if args.start_authorization_gate_date
        else None
    )
    packet_input = build_default_research_next_cycle_start_authorization_gate_input(
        start_authorization_gate_date=start_authorization_gate_date,
        now=datetime.now(tz=UTC),
    )
    overrides = {
        "start_checklist_packet_path": args.start_checklist_packet_path,
        "start_preconditions_gate_path": args.start_preconditions_gate_path,
        "operator_handoff_packet_path": args.operator_handoff_packet_path,
        "launch_control_gate_path": args.launch_control_gate_path,
        "acceptance_packet_path": args.acceptance_packet_path,
        "dry_run_manifest_path": args.dry_run_manifest_path,
        "safety_preflight_path": args.safety_preflight_path,
        "next_cycle_plan_path": args.next_cycle_plan_path,
        "report_index_path": args.report_index_path,
        "safe_workflow_catalog_path": args.safe_workflow_catalog_path,
        "queue_status_path": args.queue_status_path,
        "safety_scanner_path": args.safety_scanner_path,
    }
    packet_input = packet_input.__class__(
        **{
            **packet_input.__dict__,
            **{key: Path(value) for key, value in overrides.items() if value is not None},
        }
    )
    json_path, markdown_path = write_research_next_cycle_start_authorization_gate(
        packet_input,
        out_dir=Path(args.out_dir),
    )

    print("JARVIS 29A NEXT CYCLE START AUTHORIZATION GATE: COMPLETE")
    print("RESEARCH_ONLY / MONITOR_ONLY / PAPER_ONLY / HUMAN_REVIEW_REQUIRED / BLOCKED_BY_SAFETY_GATE")
    print("Next-cycle start authorization gate is read-only and records-only")
    print("Inert command hints are records only and are not executed")
    print("Planned records-only steps are listed but not started")
    print("The next cycle is not started and artifacts are not mutated or deleted")
    print("No trade instructions, broker actions, live-trading approvals, automatic actions, execution permissions, broker routes, broker calls, or order paths are created")
    print("BLOCKED_BY_SAFETY_GATE prerequisites remain blocked")
    print("LIVE TRADING: DISABLED")
    print("No secrets, credential files, broker routing, broker calls, live trading, or order execution are used")
    print(f"JSON: {json_path}")
    print(f"Markdown: {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
