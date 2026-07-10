from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engines.moonshot.deterministic.br22_paper_outcome_tracker import (
    DEFAULT_REPORT_DIR,
    JSON_REPORT_NAME,
    MARKDOWN_REPORT_NAME,
    paper_outcome_tracker_payload,
    run_paper_outcome_tracker,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run BR-22 paper outcome tracker.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_REPORT_DIR)
    args = parser.parse_args()

    tracker = run_paper_outcome_tracker(out_dir=args.out_dir)
    payload = paper_outcome_tracker_payload(tracker)
    print(f"{payload['phase']} {payload['module']}")
    print("LIVE TRADING: DISABLED")
    print(f"label={payload['label']}")
    print(f"outcome_record_count={payload['metrics']['outcome_record_count']}")
    print(f"paper_held_count={payload['metrics']['paper_held_count']}")
    print(f"rejected_count={payload['metrics']['rejected_count']}")
    print(f"sent_for_review_count={payload['metrics']['sent_for_review_count']}")
    print(f"outcome_json={args.out_dir / JSON_REPORT_NAME}")
    print(f"outcome_markdown={args.out_dir / MARKDOWN_REPORT_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
