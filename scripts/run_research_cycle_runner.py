from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.research_cycle_runner import (
    DEFAULT_RESEARCH_CYCLE_RUNNER_DIR,
    build_default_research_cycle_runner_input,
    run_research_cycle,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the 19A safe research/reporting cycle.")
    parser.add_argument("--report-root", default="reports")
    parser.add_argument("--manifest-dir", default=str(DEFAULT_RESEARCH_CYCLE_RUNNER_DIR))
    parser.add_argument("--cycle-date", default=None, help="YYYY-MM-DD; defaults to today UTC.")
    parser.add_argument(
        "--include-weekly-review",
        action="store_true",
        help="Write the weekly review artifact instead of recording it as skipped/stubbed.",
    )
    args = parser.parse_args()

    cycle_date = (
        datetime.strptime(args.cycle_date, "%Y-%m-%d").date()
        if args.cycle_date
        else None
    )
    cycle_input = build_default_research_cycle_runner_input(
        cycle_date=cycle_date,
        now=datetime.now(tz=UTC),
        report_root=Path(args.report_root),
        manifest_dir=Path(args.manifest_dir),
        include_weekly_review=args.include_weekly_review,
    )
    manifest, json_path, markdown_path = run_research_cycle(cycle_input)

    print("JARVIS 19A RESEARCH CYCLE RUNNER: COMPLETE")
    print("RESEARCH_ONLY / MONITOR_ONLY / PAPER_ONLY / HUMAN_REVIEW_REQUIRED")
    print("BLOCKED_BY_SAFETY_GATE workflows remain blocked")
    print("LIVE TRADING: DISABLED")
    print("No secrets, credential files, broker routing, broker calls, or order execution are used")
    print(f"Commands: {manifest['summary']['command_count']}")
    print(f"Skipped steps: {manifest['summary']['skipped_step_count']}")
    print(f"Missing artifacts: {manifest['summary']['missing_artifact_count']}")
    print(f"Safety scanner status: {manifest['summary']['safety_scanner_status']}")
    print(f"JSON: {json_path}")
    print(f"Markdown: {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
