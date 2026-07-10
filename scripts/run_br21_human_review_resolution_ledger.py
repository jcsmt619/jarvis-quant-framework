from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engines.moonshot.deterministic.br21_human_review_resolution_ledger import (
    DEFAULT_REPORT_DIR,
    JSON_REPORT_NAME,
    MARKDOWN_REPORT_NAME,
    human_review_resolution_ledger_payload,
    run_human_review_resolution_ledger,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run BR-21 human review resolution ledger.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_REPORT_DIR)
    args = parser.parse_args()

    ledger = run_human_review_resolution_ledger(out_dir=args.out_dir)
    payload = human_review_resolution_ledger_payload(ledger)
    print(f"{payload['phase']} {payload['module']}")
    print("LIVE TRADING: DISABLED")
    print(f"label={payload['label']}")
    print(f"resolution_record_count={payload['metrics']['resolution_record_count']}")
    print(f"source_phase_count={payload['metrics']['source_phase_count']}")
    for category in payload["resolution_categories"]:
        print(f"{category}_count={payload['metrics'][category + '_count']}")
    print(f"ledger_json={args.out_dir / JSON_REPORT_NAME}")
    print(f"ledger_markdown={args.out_dir / MARKDOWN_REPORT_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
