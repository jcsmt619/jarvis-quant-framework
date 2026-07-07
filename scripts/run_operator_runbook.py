from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.operator_runbook import (
    DEFAULT_OPERATOR_RUNBOOK_DIR,
    build_default_operator_runbook_input,
    write_operator_runbook,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the 15B operator runbook.")
    parser.add_argument("--out-dir", default=str(DEFAULT_OPERATOR_RUNBOOK_DIR))
    parser.add_argument("--runbook-date", default=None, help="YYYY-MM-DD; defaults to today UTC.")
    args = parser.parse_args()

    runbook_date = (
        datetime.strptime(args.runbook_date, "%Y-%m-%d").date()
        if args.runbook_date
        else None
    )
    runbook_input = build_default_operator_runbook_input(
        runbook_date=runbook_date,
        now=datetime.now(tz=UTC),
    )
    json_path, markdown_path = write_operator_runbook(
        runbook_input,
        out_dir=Path(args.out_dir),
    )
    print("JARVIS 15B OPERATOR RUNBOOK: COMPLETE")
    print("RESEARCH_ONLY / MONITOR_ONLY / PAPER_ONLY / HUMAN_REVIEW_REQUIRED")
    print("LIVE TRADING: DISABLED")
    print(f"JSON: {json_path}")
    print(f"Markdown: {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
