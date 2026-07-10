from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engines.moonshot.deterministic.br23_promotion_gate_evidence_checklist import (
    DEFAULT_REPORT_DIR,
    JSON_REPORT_NAME,
    MARKDOWN_REPORT_NAME,
    promotion_gate_evidence_checklist_payload,
    run_promotion_gate_evidence_checklist,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run BR-23 promotion gate evidence checklist.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_REPORT_DIR)
    args = parser.parse_args()

    checklist = run_promotion_gate_evidence_checklist(out_dir=args.out_dir)
    payload = promotion_gate_evidence_checklist_payload(checklist)
    print(f"{payload['phase']} {payload['module']}")
    print("LIVE TRADING: DISABLED")
    print(f"label={payload['label']}")
    print(f"checklist_record_count={payload['metrics']['checklist_record_count']}")
    print(f"blocked_count={payload['metrics']['blocked_count']}")
    print(f"review_required_count={payload['metrics']['review_required_count']}")
    print(f"paper_only_count={payload['metrics']['paper_only_count']}")
    print(f"checklist_json={args.out_dir / JSON_REPORT_NAME}")
    print(f"checklist_markdown={args.out_dir / MARKDOWN_REPORT_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
