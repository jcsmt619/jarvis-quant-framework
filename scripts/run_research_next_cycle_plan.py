from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.research_next_cycle_plan import (
    DEFAULT_RESEARCH_NEXT_CYCLE_PLAN_DIR,
    build_default_research_next_cycle_plan_input,
    write_research_next_cycle_plan,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Write the 24B next research cycle plan.")
    parser.add_argument("--out-dir", default=str(DEFAULT_RESEARCH_NEXT_CYCLE_PLAN_DIR))
    parser.add_argument("--next-cycle-plan-date", default=None, help="YYYY-MM-DD; defaults to today UTC.")
    parser.add_argument("--rollover-gate-path", default=None)
    parser.add_argument("--archive-index-path", default=None)
    parser.add_argument("--operations-console-path", default=None)
    parser.add_argument("--operator-signoff-packet-path", default=None)
    parser.add_argument("--readiness-gate-path", default=None)
    parser.add_argument("--retention-policy-path", default=None)
    parser.add_argument("--report-index-path", default=None)
    parser.add_argument("--safe-workflow-catalog-path", default=None)
    parser.add_argument("--queue-status-path", default=None)
    parser.add_argument("--safety-scanner-path", default=None)
    args = parser.parse_args()

    next_cycle_plan_date = (
        datetime.strptime(args.next_cycle_plan_date, "%Y-%m-%d").date()
        if args.next_cycle_plan_date
        else None
    )
    plan_input = build_default_research_next_cycle_plan_input(
        next_cycle_plan_date=next_cycle_plan_date,
        now=datetime.now(tz=UTC),
    )
    overrides = {
        "rollover_gate_path": args.rollover_gate_path,
        "archive_index_path": args.archive_index_path,
        "operations_console_path": args.operations_console_path,
        "operator_signoff_packet_path": args.operator_signoff_packet_path,
        "readiness_gate_path": args.readiness_gate_path,
        "retention_policy_path": args.retention_policy_path,
        "report_index_path": args.report_index_path,
        "safe_workflow_catalog_path": args.safe_workflow_catalog_path,
        "queue_status_path": args.queue_status_path,
        "safety_scanner_path": args.safety_scanner_path,
    }
    plan_input = plan_input.__class__(
        **{
            **plan_input.__dict__,
            **{key: Path(value) for key, value in overrides.items() if value is not None},
        }
    )
    json_path, markdown_path = write_research_next_cycle_plan(
        plan_input,
        out_dir=Path(args.out_dir),
    )

    print("JARVIS 24B NEXT RESEARCH CYCLE PLAN: COMPLETE")
    print("RESEARCH_ONLY / MONITOR_ONLY / PAPER_ONLY / HUMAN_REVIEW_REQUIRED / BLOCKED_BY_SAFETY_GATE")
    print("Next-cycle plan is read-only and records-only")
    print("The next cycle is not run and artifacts are not mutated or deleted")
    print("No trade instructions, broker actions, live-trading approvals, automatic actions, or execution permissions are created")
    print("BLOCKED_BY_SAFETY_GATE prerequisites remain blocked")
    print("LIVE TRADING: DISABLED")
    print("No secrets, credential files, broker routing, broker calls, live trading, or order execution are used")
    print(f"JSON: {json_path}")
    print(f"Markdown: {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
