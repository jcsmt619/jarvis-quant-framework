from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.decision_journal import (
    DEFAULT_DECISION_JOURNAL_DIR,
    build_default_decision_journal_input,
    write_decision_journal,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the 16B decision journal.")
    parser.add_argument("--out-dir", default=str(DEFAULT_DECISION_JOURNAL_DIR))
    parser.add_argument("--journal-date", default=None, help="YYYY-MM-DD; defaults to today UTC.")
    args = parser.parse_args()

    journal_date = (
        datetime.strptime(args.journal_date, "%Y-%m-%d").date()
        if args.journal_date
        else None
    )
    journal_input = build_default_decision_journal_input(
        journal_date=journal_date,
        now=datetime.now(tz=UTC),
    )
    json_path, markdown_path = write_decision_journal(
        journal_input,
        out_dir=Path(args.out_dir),
    )
    print("JARVIS 16B DECISION JOURNAL: COMPLETE")
    print("RESEARCH_ONLY / MONITOR_ONLY / PAPER_ONLY / HUMAN_REVIEW_REQUIRED")
    print("BLOCKED_BY_SAFETY_GATE workflows and outcomes remain blocked")
    print("LIVE TRADING: DISABLED")
    print("No secrets, credential files, broker routing, broker calls, or order execution are used")
    print(f"JSON: {json_path}")
    print(f"Markdown: {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
