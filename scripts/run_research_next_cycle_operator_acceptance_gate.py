from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.research_next_cycle_operator_acceptance_gate import (
    DEFAULT_RESEARCH_NEXT_CYCLE_OPERATOR_ACCEPTANCE_GATE_DIR,
    build_default_research_next_cycle_operator_acceptance_gate_input,
    write_research_next_cycle_operator_acceptance_gate,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Write the 26A next cycle operator acceptance gate.")
    parser.add_argument("--out-dir", default=str(DEFAULT_RESEARCH_NEXT_CYCLE_OPERATOR_ACCEPTANCE_GATE_DIR))
    parser.add_argument("--operator-acceptance-gate-date", default=None, help="YYYY-MM-DD; defaults to today UTC.")
    parser.add_argument("--dry-run-manifest-path", default=None)
    parser.add_argument("--safety-preflight-path", default=None)
    parser.add_argument("--next-cycle-plan-path", default=None)
    parser.add_argument("--rollover-gate-path", default=None)
    parser.add_argument("--archive-index-path", default=None)
    parser.add_argument("--operations-console-path", default=None)
    parser.add_argument("--report-index-path", default=None)
    parser.add_argument("--safe-workflow-catalog-path", default=None)
    parser.add_argument("--queue-status-path", default=None)
    parser.add_argument("--safety-scanner-path", default=None)
    args = parser.parse_args()

    operator_acceptance_gate_date = (
        datetime.strptime(args.operator_acceptance_gate_date, "%Y-%m-%d").date()
        if args.operator_acceptance_gate_date
        else None
    )
    manifest_input = build_default_research_next_cycle_operator_acceptance_gate_input(
        operator_acceptance_gate_date=operator_acceptance_gate_date,
        now=datetime.now(tz=UTC),
    )
    overrides = {
        "dry_run_manifest_path": args.dry_run_manifest_path,
        "safety_preflight_path": args.safety_preflight_path,
        "next_cycle_plan_path": args.next_cycle_plan_path,
        "rollover_gate_path": args.rollover_gate_path,
        "archive_index_path": args.archive_index_path,
        "operations_console_path": args.operations_console_path,
        "report_index_path": args.report_index_path,
        "safe_workflow_catalog_path": args.safe_workflow_catalog_path,
        "queue_status_path": args.queue_status_path,
        "safety_scanner_path": args.safety_scanner_path,
    }
    manifest_input = manifest_input.__class__(
        **{
            **manifest_input.__dict__,
            **{key: Path(value) for key, value in overrides.items() if value is not None},
        }
    )
    json_path, markdown_path = write_research_next_cycle_operator_acceptance_gate(
        manifest_input,
        out_dir=Path(args.out_dir),
    )

    print("JARVIS 26A NEXT CYCLE OPERATOR ACCEPTANCE GATE: COMPLETE")
    print("RESEARCH_ONLY / MONITOR_ONLY / PAPER_ONLY / HUMAN_REVIEW_REQUIRED / BLOCKED_BY_SAFETY_GATE")
    print("Next-cycle operator acceptance gate is read-only and records-only")
    print("Command hints are inert records only and are not executed")
    print("The next cycle is not run and artifacts are not mutated or deleted")
    print("No trade instructions, broker actions, live-trading approvals, automatic actions, execution permissions, or order paths are created")
    print("BLOCKED_BY_SAFETY_GATE prerequisites remain blocked")
    print("LIVE TRADING: DISABLED")
    print("No secrets, credential files, broker routing, broker calls, live trading, or order execution are used")
    print(f"JSON: {json_path}")
    print(f"Markdown: {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
