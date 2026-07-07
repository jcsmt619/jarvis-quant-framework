from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.safe_workflow_catalog import (
    DEFAULT_SAFE_WORKFLOW_CATALOG_DIR,
    build_default_safe_workflow_catalog_input,
    write_safe_workflow_catalog,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the 18A safe workflow catalog.")
    parser.add_argument("--out-dir", default=str(DEFAULT_SAFE_WORKFLOW_CATALOG_DIR))
    parser.add_argument("--catalog-date", default=None, help="YYYY-MM-DD; defaults to today UTC.")
    args = parser.parse_args()

    catalog_date = (
        datetime.strptime(args.catalog_date, "%Y-%m-%d").date()
        if args.catalog_date
        else None
    )
    catalog_input = build_default_safe_workflow_catalog_input(
        catalog_date=catalog_date,
        now=datetime.now(tz=UTC),
    )
    json_path, markdown_path = write_safe_workflow_catalog(
        catalog_input,
        out_dir=Path(args.out_dir),
    )
    print("JARVIS 18A SAFE WORKFLOW CATALOG: COMPLETE")
    print("RESEARCH_ONLY / MONITOR_ONLY / PAPER_ONLY / HUMAN_REVIEW_REQUIRED")
    print("BLOCKED_BY_SAFETY_GATE behaviors remain blocked")
    print("LIVE TRADING: DISABLED")
    print("No secrets, credential files, broker routing, broker calls, or order execution are used")
    print(f"JSON: {json_path}")
    print(f"Markdown: {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
