from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.report_index import (
    DEFAULT_REPORT_INDEX_DIR,
    build_default_report_index_input,
    write_report_index,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the 17A report index.")
    parser.add_argument("--out-dir", default=str(DEFAULT_REPORT_INDEX_DIR))
    parser.add_argument("--index-date", default=None, help="YYYY-MM-DD; defaults to today UTC.")
    args = parser.parse_args()

    index_date = (
        datetime.strptime(args.index_date, "%Y-%m-%d").date()
        if args.index_date
        else None
    )
    index_input = build_default_report_index_input(
        index_date=index_date,
        now=datetime.now(tz=UTC),
    )
    json_path, markdown_path = write_report_index(index_input, out_dir=Path(args.out_dir))
    print("JARVIS 17A REPORT INDEX: COMPLETE")
    print("RESEARCH_ONLY / MONITOR_ONLY / PAPER_ONLY / HUMAN_REVIEW_REQUIRED")
    print("BLOCKED_BY_SAFETY_GATE missing or unsafe report metadata remains blocked")
    print("LIVE TRADING: DISABLED")
    print("No secrets, credential files, broker routing, broker calls, or order execution are used")
    print(f"JSON: {json_path}")
    print(f"Markdown: {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
