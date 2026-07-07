from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.daily_research_command_center import (
    DEFAULT_DAILY_RESEARCH_DIR,
    build_default_daily_research_input,
    write_daily_research_summary,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the 15A daily research command center.")
    parser.add_argument("--out-dir", default=str(DEFAULT_DAILY_RESEARCH_DIR))
    parser.add_argument("--report-date", default=None, help="YYYY-MM-DD; defaults to today UTC.")
    args = parser.parse_args()

    report_date = (
        datetime.strptime(args.report_date, "%Y-%m-%d").date()
        if args.report_date
        else None
    )
    report_input = build_default_daily_research_input(
        report_date=report_date,
        now=datetime.now(tz=UTC),
    )
    json_path, markdown_path = write_daily_research_summary(
        report_input,
        out_dir=Path(args.out_dir),
    )
    print("JARVIS 15A DAILY RESEARCH COMMAND CENTER: COMPLETE")
    print("RESEARCH_ONLY / MONITOR_ONLY / PAPER_ONLY / HUMAN_REVIEW_REQUIRED")
    print("LIVE TRADING: DISABLED")
    print(f"JSON: {json_path}")
    print(f"Markdown: {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
