from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.research_release_bundle import (
    DEFAULT_RESEARCH_RELEASE_BUNDLE_DIR,
    build_default_research_release_bundle_input,
    write_research_release_bundle,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the 18B research release bundle.")
    parser.add_argument("--out-dir", default=str(DEFAULT_RESEARCH_RELEASE_BUNDLE_DIR))
    parser.add_argument("--bundle-date", default=None, help="YYYY-MM-DD; defaults to today UTC.")
    args = parser.parse_args()

    bundle_date = (
        datetime.strptime(args.bundle_date, "%Y-%m-%d").date()
        if args.bundle_date
        else None
    )
    bundle_input = build_default_research_release_bundle_input(
        bundle_date=bundle_date,
        now=datetime.now(tz=UTC),
    )
    json_path, markdown_path = write_research_release_bundle(
        bundle_input,
        out_dir=Path(args.out_dir),
    )
    print("JARVIS 18B RESEARCH RELEASE BUNDLE: COMPLETE")
    print("RESEARCH_ONLY / MONITOR_ONLY / PAPER_ONLY / HUMAN_REVIEW_REQUIRED")
    print("BLOCKED_BY_SAFETY_GATE missing artifacts and blocked workflows remain blocked")
    print("LIVE TRADING: DISABLED")
    print("No secrets, credential files, broker routing, broker calls, or order execution are used")
    print(f"JSON: {json_path}")
    print(f"Markdown: {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
