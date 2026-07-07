from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.human_review_queue import (
    DEFAULT_HUMAN_REVIEW_QUEUE_DIR,
    build_default_human_review_queue_input,
    write_human_review_queue,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Write the 21A human review queue.")
    parser.add_argument("--out-dir", default=str(DEFAULT_HUMAN_REVIEW_QUEUE_DIR))
    parser.add_argument("--review-date", default=None, help="YYYY-MM-DD; defaults to today UTC.")
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

    review_date = (
        datetime.strptime(args.review_date, "%Y-%m-%d").date()
        if args.review_date
        else None
    )
    review_input = build_default_human_review_queue_input(
        review_date=review_date,
        now=datetime.now(tz=UTC),
    )
    overrides = {
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
    review_input = review_input.__class__(
        **{
            **review_input.__dict__,
            **{
                key: Path(value)
                for key, value in overrides.items()
                if value is not None
            },
            "max_source_age_days": args.max_source_age_days,
        }
    )
    json_path, markdown_path = write_human_review_queue(
        review_input,
        out_dir=Path(args.out_dir),
    )

    print("JARVIS 21A HUMAN REVIEW QUEUE: COMPLETE")
    print("RESEARCH_ONLY / MONITOR_ONLY / PAPER_ONLY / HUMAN_REVIEW_REQUIRED")
    print("Review items only; no trade instructions, execution instructions, broker actions, or live-trading approvals")
    print("BLOCKED_BY_SAFETY_GATE workflows remain blocked")
    print("LIVE TRADING: DISABLED")
    print("No secrets, credential files, broker routing, broker calls, or order execution are used")
    print(f"JSON: {json_path}")
    print(f"Markdown: {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
