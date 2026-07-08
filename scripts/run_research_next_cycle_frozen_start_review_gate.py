from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.research_next_cycle_frozen_start_review_gate import (
    DEFAULT_RESEARCH_NEXT_CYCLE_FROZEN_START_REVIEW_GATE_DIR,
    build_default_research_next_cycle_frozen_start_review_gate_input,
    write_research_next_cycle_frozen_start_review_gate,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Write the 30A next cycle frozen start review gate.")
    parser.add_argument("--out-dir", default=str(DEFAULT_RESEARCH_NEXT_CYCLE_FROZEN_START_REVIEW_GATE_DIR))
    parser.add_argument("--frozen-start-review-gate-date", default=None, help="YYYY-MM-DD; defaults to today UTC.")
    parser.add_argument("--frozen-launch-packet-path", default=None)
    parser.add_argument("--start-authorization-gate-path", default=None)
    parser.add_argument("--start-checklist-packet-path", default=None)
    parser.add_argument("--start-preconditions-gate-path", default=None)
    parser.add_argument("--operator-handoff-packet-path", default=None)
    parser.add_argument("--launch-control-gate-path", default=None)
    parser.add_argument("--acceptance-packet-path", default=None)
    parser.add_argument("--report-index-path", default=None)
    parser.add_argument("--safe-workflow-catalog-path", default=None)
    parser.add_argument("--queue-status-path", default=None)
    parser.add_argument("--safety-scanner-path", default=None)
    args = parser.parse_args()

    frozen_start_review_gate_date = (
        datetime.strptime(args.frozen_start_review_gate_date, "%Y-%m-%d").date()
        if args.frozen_start_review_gate_date
        else None
    )
    gate_input = build_default_research_next_cycle_frozen_start_review_gate_input(
        frozen_start_review_gate_date=frozen_start_review_gate_date,
        now=datetime.now(tz=UTC),
    )
    overrides = {
        "frozen_launch_packet_path": args.frozen_launch_packet_path,
        "start_authorization_gate_path": args.start_authorization_gate_path,
        "start_checklist_packet_path": args.start_checklist_packet_path,
        "start_preconditions_gate_path": args.start_preconditions_gate_path,
        "operator_handoff_packet_path": args.operator_handoff_packet_path,
        "launch_control_gate_path": args.launch_control_gate_path,
        "acceptance_packet_path": args.acceptance_packet_path,
        "report_index_path": args.report_index_path,
        "safe_workflow_catalog_path": args.safe_workflow_catalog_path,
        "queue_status_path": args.queue_status_path,
        "safety_scanner_path": args.safety_scanner_path,
    }
    gate_input = gate_input.__class__(
        **{
            **gate_input.__dict__,
            **{key: Path(value) for key, value in overrides.items() if value is not None},
        }
    )
    json_path, markdown_path = write_research_next_cycle_frozen_start_review_gate(
        gate_input,
        out_dir=Path(args.out_dir),
    )

    print("JARVIS 30A NEXT CYCLE FROZEN START REVIEW GATE: COMPLETE")
    print("RESEARCH_ONLY / MONITOR_ONLY / PAPER_ONLY / HUMAN_REVIEW_REQUIRED / BLOCKED_BY_SAFETY_GATE")
    print("Frozen start review gate is read-only and records-only")
    print("Inert command hints are records only and are not executed")
    print("The next cycle is not started and artifacts are not mutated or deleted")
    print("No trade instructions, broker actions, live-trading approvals, automatic actions, execution permissions, broker routes, broker calls, or order paths are created")
    print("Frozen start review records do not grant execution permission")
    print("BLOCKED_BY_SAFETY_GATE prerequisites remain blocked")
    print("LIVE TRADING: DISABLED")
    print("No secrets, credential files, broker routing, broker calls, live trading, or order execution are used")
    print(f"JSON: {json_path}")
    print(f"Markdown: {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
