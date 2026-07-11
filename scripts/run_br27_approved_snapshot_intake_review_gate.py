from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engines.moonshot.deterministic.br27_approved_snapshot_intake_review_gate import (
    DEFAULT_APPROVED_SNAPSHOT_PATH,
    DEFAULT_BR26_REPORT_PATH,
    DEFAULT_REPORT_DIR,
    JSON_REPORT_NAME,
    MARKDOWN_REPORT_NAME,
    approved_snapshot_intake_review_gate_payload,
    run_approved_snapshot_intake_review_gate,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run BR-27 approved snapshot intake review gate.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--br26-report", type=Path, default=DEFAULT_BR26_REPORT_PATH)
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_APPROVED_SNAPSHOT_PATH)
    args = parser.parse_args()

    gate = run_approved_snapshot_intake_review_gate(
        source_paths={
            "BR-26 import contract": args.br26_report,
            "approved offline snapshot": args.snapshot,
        },
        out_dir=args.out_dir,
    )
    payload = approved_snapshot_intake_review_gate_payload(gate)
    print(f"{payload['phase']} {payload['module']}")
    print("LIVE TRADING: DISABLED")
    print(f"label={payload['label']}")
    print(f"accepted_research_evidence_count={payload['metrics']['accepted_research_evidence_count']}")
    print(f"rejected_snapshot_count={payload['metrics']['rejected_snapshot_count']}")
    print(f"review_json={args.out_dir / JSON_REPORT_NAME}")
    print(f"review_markdown={args.out_dir / MARKDOWN_REPORT_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
