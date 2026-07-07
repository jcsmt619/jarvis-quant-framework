from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.operator_dashboard_snapshot import (
    DEFAULT_OPERATOR_DASHBOARD_SNAPSHOT_DIR,
    build_default_operator_dashboard_snapshot_input,
    write_operator_dashboard_snapshot,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the 17B operator dashboard snapshot.")
    parser.add_argument("--out-dir", default=str(DEFAULT_OPERATOR_DASHBOARD_SNAPSHOT_DIR))
    parser.add_argument("--snapshot-date", default=None, help="YYYY-MM-DD; defaults to today UTC.")
    args = parser.parse_args()

    snapshot_date = (
        datetime.strptime(args.snapshot_date, "%Y-%m-%d").date()
        if args.snapshot_date
        else None
    )
    snapshot_input = build_default_operator_dashboard_snapshot_input(
        snapshot_date=snapshot_date,
        now=datetime.now(tz=UTC),
    )
    json_path, markdown_path = write_operator_dashboard_snapshot(
        snapshot_input,
        out_dir=Path(args.out_dir),
    )
    print("JARVIS 17B OPERATOR DASHBOARD SNAPSHOT: COMPLETE")
    print("RESEARCH_ONLY / MONITOR_ONLY / PAPER_ONLY / HUMAN_REVIEW_REQUIRED")
    print("BLOCKED_BY_SAFETY_GATE workflows remain separated from allowed review workflows")
    print("LIVE TRADING: DISABLED")
    print("No secrets, credential files, broker routing, broker calls, or order execution are used")
    print(f"JSON: {json_path}")
    print(f"Markdown: {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
