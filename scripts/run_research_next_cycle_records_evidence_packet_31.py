from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.research_next_cycle_records_evidence_packet_31 import (
    DEFAULT_RESEARCH_NEXT_CYCLE_RECORDS_EVIDENCE_PACKET_31_DIR,
    build_default_research_next_cycle_records_evidence_packet_31_input,
    write_research_next_cycle_records_evidence_packet_31,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Write the 31B next cycle records evidence packet 31.")
    parser.add_argument("--out-dir", default=str(DEFAULT_RESEARCH_NEXT_CYCLE_RECORDS_EVIDENCE_PACKET_31_DIR))
    parser.add_argument("--records-evidence-packet-31-date", default=None, help="YYYY-MM-DD; defaults to today UTC.")
    parser.add_argument("--records-review-gate-31-path", default=None)
    parser.add_argument("--frozen-start-evidence-packet-path", default=None)
    parser.add_argument("--frozen-start-review-gate-path", default=None)
    parser.add_argument("--frozen-launch-packet-path", default=None)
    parser.add_argument("--start-authorization-gate-path", default=None)
    parser.add_argument("--start-checklist-packet-path", default=None)
    parser.add_argument("--start-preconditions-gate-path", default=None)
    parser.add_argument("--operator-handoff-packet-path", default=None)
    parser.add_argument("--launch-control-gate-path", default=None)
    parser.add_argument("--report-index-path", default=None)
    parser.add_argument("--safe-workflow-catalog-path", default=None)
    parser.add_argument("--queue-status-path", default=None)
    parser.add_argument("--safety-scanner-path", default=None)
    args = parser.parse_args()

    gate_date = (
        datetime.strptime(args.records_evidence_packet_31_date, "%Y-%m-%d").date()
        if args.records_evidence_packet_31_date
        else None
    )
    gate_input = build_default_research_next_cycle_records_evidence_packet_31_input(
        records_evidence_packet_31_date=gate_date,
        now=datetime.now(tz=UTC),
    )
    overrides = {
        "records_review_gate_31_path": args.records_review_gate_31_path,
        "frozen_start_evidence_packet_path": args.frozen_start_evidence_packet_path,
        "frozen_start_review_gate_path": args.frozen_start_review_gate_path,
        "frozen_launch_packet_path": args.frozen_launch_packet_path,
        "start_authorization_gate_path": args.start_authorization_gate_path,
        "start_checklist_packet_path": args.start_checklist_packet_path,
        "start_preconditions_gate_path": args.start_preconditions_gate_path,
        "operator_handoff_packet_path": args.operator_handoff_packet_path,
        "launch_control_gate_path": args.launch_control_gate_path,
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
    json_path, markdown_path = write_research_next_cycle_records_evidence_packet_31(
        gate_input,
        out_dir=Path(args.out_dir),
    )

    print("JARVIS 31B NEXT CYCLE RECORDS EVIDENCE PACKET 31: COMPLETE")
    print("RESEARCH_ONLY / MONITOR_ONLY / PAPER_ONLY / HUMAN_REVIEW_REQUIRED / BLOCKED_BY_SAFETY_GATE")
    print("Records Evidence Packet 31 is read-only and records-only")
    print("Inert command hints are records only and are not executed")
    print("The next cycle is not run and artifacts are not mutated or deleted")
    print("No trade instructions, broker actions, live-trading approvals, automatic actions, execution permissions, broker routes, broker calls, or order paths are created")
    print("Records Evidence Packet 31 records do not grant execution permission")
    print("BLOCKED_BY_SAFETY_GATE prerequisites remain blocked")
    print("LIVE TRADING: DISABLED")
    print("No secrets, credential files, broker routing, broker calls, live trading, or order execution are used")
    print(f"JSON: {json_path}")
    print(f"Markdown: {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
