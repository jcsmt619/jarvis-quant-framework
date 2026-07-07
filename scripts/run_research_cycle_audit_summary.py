from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.research_cycle_audit_summary import (
    DEFAULT_RESEARCH_CYCLE_AUDIT_SUMMARY_DIR,
    build_default_research_cycle_audit_summary_input,
    write_research_cycle_audit_summary,
)
from core.research_cycle_runner import DEFAULT_RESEARCH_CYCLE_RUNNER_DIR, RESEARCH_CYCLE_MANIFEST_JSON


def main() -> int:
    parser = argparse.ArgumentParser(description="Write the 19B research cycle audit summary.")
    parser.add_argument("--out-dir", default=str(DEFAULT_RESEARCH_CYCLE_AUDIT_SUMMARY_DIR))
    parser.add_argument(
        "--manifest-path",
        default=str(DEFAULT_RESEARCH_CYCLE_RUNNER_DIR / RESEARCH_CYCLE_MANIFEST_JSON),
        help="Repo-relative path to a completed 19A research_cycle_manifest.json.",
    )
    parser.add_argument("--queue-path", default="config/jarvis_master_plan_queue.json")
    parser.add_argument("--audit-date", default=None, help="YYYY-MM-DD; defaults to today UTC.")
    args = parser.parse_args()

    audit_date = (
        datetime.strptime(args.audit_date, "%Y-%m-%d").date()
        if args.audit_date
        else None
    )
    audit_input = build_default_research_cycle_audit_summary_input(
        audit_date=audit_date,
        now=datetime.now(tz=UTC),
        manifest_path=Path(args.manifest_path),
        queue_path=Path(args.queue_path),
    )
    json_path, markdown_path = write_research_cycle_audit_summary(
        audit_input,
        out_dir=Path(args.out_dir),
    )

    print("JARVIS 19B RESEARCH CYCLE AUDIT SUMMARY: COMPLETE")
    print("RESEARCH_ONLY / MONITOR_ONLY / PAPER_ONLY / HUMAN_REVIEW_REQUIRED")
    print("Allowed human-review workflows are separated from BLOCKED_BY_SAFETY_GATE workflows")
    print("LIVE TRADING: DISABLED")
    print("No secrets, credential files, broker routing, broker calls, or order execution are used")
    print(f"JSON: {json_path}")
    print(f"Markdown: {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
