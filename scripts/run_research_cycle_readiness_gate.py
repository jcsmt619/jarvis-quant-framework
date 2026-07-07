from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.research_cycle_readiness_gate import (
    DEFAULT_RESEARCH_CYCLE_READINESS_GATE_DIR,
    build_default_research_cycle_readiness_gate_input,
    write_research_cycle_readiness_gate,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Write the 20A research cycle readiness gate.")
    parser.add_argument("--out-dir", default=str(DEFAULT_RESEARCH_CYCLE_READINESS_GATE_DIR))
    parser.add_argument("--gate-date", default=None, help="YYYY-MM-DD; defaults to today UTC.")
    parser.add_argument("--manifest-path", default=None)
    parser.add_argument("--audit-summary-path", default=None)
    parser.add_argument("--release-bundle-path", default=None)
    parser.add_argument("--operator-dashboard-snapshot-path", default=None)
    parser.add_argument("--report-index-path", default=None)
    parser.add_argument("--safe-workflow-catalog-path", default=None)
    parser.add_argument("--queue-path", default=None)
    parser.add_argument("--safety-scanner-path", default=None)
    parser.add_argument("--max-report-age-days", type=int, default=1)
    args = parser.parse_args()

    gate_date = (
        datetime.strptime(args.gate_date, "%Y-%m-%d").date()
        if args.gate_date
        else None
    )
    gate_input = build_default_research_cycle_readiness_gate_input(
        gate_date=gate_date,
        now=datetime.now(tz=UTC),
    )
    overrides = {
        "manifest_path": args.manifest_path,
        "audit_summary_path": args.audit_summary_path,
        "release_bundle_path": args.release_bundle_path,
        "operator_dashboard_snapshot_path": args.operator_dashboard_snapshot_path,
        "report_index_path": args.report_index_path,
        "safe_workflow_catalog_path": args.safe_workflow_catalog_path,
        "queue_path": args.queue_path,
        "safety_scanner_path": args.safety_scanner_path,
    }
    gate_input = gate_input.__class__(
        **{
            **gate_input.__dict__,
            **{
                key: Path(value)
                for key, value in overrides.items()
                if value is not None
            },
            "max_report_age_days": args.max_report_age_days,
        }
    )
    json_path, markdown_path = write_research_cycle_readiness_gate(
        gate_input,
        out_dir=Path(args.out_dir),
    )

    print("JARVIS 20A RESEARCH CYCLE READINESS GATE: COMPLETE")
    print("RESEARCH_ONLY / MONITOR_ONLY / PAPER_ONLY / HUMAN_REVIEW_REQUIRED")
    print("Decision is one of READY_FOR_HUMAN_REVIEW, BLOCKED_BY_SAFETY_GATE, NEEDS_OPERATOR_REVIEW")
    print("LIVE TRADING: DISABLED")
    print("No secrets, credential files, broker routing, broker calls, or order execution are used")
    print(f"JSON: {json_path}")
    print(f"Markdown: {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
