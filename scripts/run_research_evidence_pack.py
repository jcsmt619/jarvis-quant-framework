from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.research_evidence_pack import (
    DEFAULT_RESEARCH_EVIDENCE_PACK_DIR,
    build_default_research_evidence_pack_input,
    write_research_evidence_pack,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the 16A research evidence pack.")
    parser.add_argument("--out-dir", default=str(DEFAULT_RESEARCH_EVIDENCE_PACK_DIR))
    parser.add_argument("--evidence-date", default=None, help="YYYY-MM-DD; defaults to today UTC.")
    args = parser.parse_args()

    evidence_date = (
        datetime.strptime(args.evidence_date, "%Y-%m-%d").date()
        if args.evidence_date
        else None
    )
    pack_input = build_default_research_evidence_pack_input(
        evidence_date=evidence_date,
        now=datetime.now(tz=UTC),
    )
    json_path, markdown_path = write_research_evidence_pack(
        pack_input,
        out_dir=Path(args.out_dir),
    )
    print("JARVIS 16A RESEARCH EVIDENCE PACK: COMPLETE")
    print("RESEARCH_ONLY / MONITOR_ONLY / PAPER_ONLY / HUMAN_REVIEW_REQUIRED")
    print("BLOCKED_BY_SAFETY_GATE findings remain blocked")
    print("LIVE TRADING: DISABLED")
    print("No secrets, credential files, broker routing, broker calls, or order execution are used")
    print(f"JSON: {json_path}")
    print(f"Markdown: {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
