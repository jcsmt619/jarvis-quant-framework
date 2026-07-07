from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.research_artifact_retention_policy import (
    DEFAULT_RESEARCH_ARTIFACT_RETENTION_POLICY_DIR,
    build_default_research_artifact_retention_policy_input,
    write_research_artifact_retention_policy,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Write the 20B research artifact retention policy.")
    parser.add_argument("--out-dir", default=str(DEFAULT_RESEARCH_ARTIFACT_RETENTION_POLICY_DIR))
    parser.add_argument("--retention-date", default=None, help="YYYY-MM-DD; defaults to today UTC.")
    args = parser.parse_args()

    retention_date = (
        datetime.strptime(args.retention_date, "%Y-%m-%d").date()
        if args.retention_date
        else None
    )
    policy_input = build_default_research_artifact_retention_policy_input(
        retention_date=retention_date,
        now=datetime.now(tz=UTC),
    )
    json_path, markdown_path = write_research_artifact_retention_policy(
        policy_input,
        out_dir=Path(args.out_dir),
    )

    print("JARVIS 20B RESEARCH ARTIFACT RETENTION POLICY: COMPLETE")
    print("RESEARCH_ONLY / MONITOR_ONLY / PAPER_ONLY / HUMAN_REVIEW_REQUIRED")
    print("Retention manifest is dry-run only; automatic deletion is disabled")
    print("BLOCKED_BY_SAFETY_GATE artifacts remain blocked_delete")
    print("LIVE TRADING: DISABLED")
    print("No secrets, credential files, broker routing, broker calls, order execution, or automatic file deletion are used")
    print(f"JSON: {json_path}")
    print(f"Markdown: {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
