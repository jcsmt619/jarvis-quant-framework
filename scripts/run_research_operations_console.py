from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.research_operations_console import (
    DEFAULT_RESEARCH_OPERATIONS_CONSOLE_DIR,
    build_default_research_operations_console_input,
    write_research_operations_console,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Write the 23A research operations console.")
    parser.add_argument("--out-dir", default=str(DEFAULT_RESEARCH_OPERATIONS_CONSOLE_DIR))
    parser.add_argument("--console-date", default=None, help="YYYY-MM-DD; defaults to today UTC.")
    parser.add_argument("--closeout-gate-path", default=None)
    parser.add_argument("--operator-acknowledgment-ledger-path", default=None)
    parser.add_argument("--human-review-queue-path", default=None)
    parser.add_argument("--readiness-gate-path", default=None)
    parser.add_argument("--retention-policy-path", default=None)
    parser.add_argument("--audit-summary-path", default=None)
    parser.add_argument("--manifest-path", default=None)
    parser.add_argument("--release-bundle-path", default=None)
    parser.add_argument("--operator-dashboard-snapshot-path", default=None)
    parser.add_argument("--report-index-path", default=None)
    parser.add_argument("--safe-workflow-catalog-path", default=None)
    parser.add_argument("--queue-status-path", default=None)
    parser.add_argument("--safety-scanner-path", default=None)
    parser.add_argument("--max-source-age-days", type=int, default=1)
    args = parser.parse_args()

    console_date = (
        datetime.strptime(args.console_date, "%Y-%m-%d").date()
        if args.console_date
        else None
    )
    console_input = build_default_research_operations_console_input(
        console_date=console_date,
        now=datetime.now(tz=UTC),
    )
    overrides = {
        "closeout_gate_path": args.closeout_gate_path,
        "operator_acknowledgment_ledger_path": args.operator_acknowledgment_ledger_path,
        "human_review_queue_path": args.human_review_queue_path,
        "readiness_gate_path": args.readiness_gate_path,
        "retention_policy_path": args.retention_policy_path,
        "audit_summary_path": args.audit_summary_path,
        "manifest_path": args.manifest_path,
        "release_bundle_path": args.release_bundle_path,
        "operator_dashboard_snapshot_path": args.operator_dashboard_snapshot_path,
        "report_index_path": args.report_index_path,
        "safe_workflow_catalog_path": args.safe_workflow_catalog_path,
        "queue_status_path": args.queue_status_path,
        "safety_scanner_path": args.safety_scanner_path,
    }
    console_input = console_input.__class__(
        **{
            **console_input.__dict__,
            **{
                key: Path(value)
                for key, value in overrides.items()
                if value is not None
            },
            "max_source_age_days": args.max_source_age_days,
        }
    )
    json_path, markdown_path = write_research_operations_console(
        console_input,
        out_dir=Path(args.out_dir),
    )

    print("JARVIS 23A RESEARCH OPERATIONS CONSOLE: COMPLETE")
    print("RESEARCH_ONLY / MONITOR_ONLY / PAPER_ONLY / HUMAN_REVIEW_REQUIRED / BLOCKED_BY_SAFETY_GATE")
    print("Console is records-only; it does not enable live trading, broker routing, broker calls, order execution, or automatic actions")
    print("BLOCKED_BY_SAFETY_GATE workflows remain blocked")
    print("LIVE TRADING: DISABLED")
    print("No secrets, credential files, broker routing, broker calls, live trading, or order execution are used")
    print(f"JSON: {json_path}")
    print(f"Markdown: {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
