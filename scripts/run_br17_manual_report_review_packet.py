from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engines.moonshot.deterministic.br17_manual_report_review_packet import (
    DEFAULT_EVIDENCE_DIR,
    DEFAULT_REPORT_DIR,
    JSON_REPORT_NAME,
    MARKDOWN_REPORT_NAME,
    manual_report_review_packet_payload,
    run_manual_report_review_packet,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run BR-17 BR-14 manual report review packet.")
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_REPORT_DIR)
    args = parser.parse_args()

    packet = run_manual_report_review_packet(evidence_dir=args.evidence_dir, out_dir=args.out_dir)
    payload = manual_report_review_packet_payload(packet)
    print(f"{payload['phase']} {payload['module']}")
    print("LIVE TRADING: DISABLED")
    print(f"label={payload['label']}")
    print(f"readiness_state={payload['readiness_state']['state']}")
    print(f"hold={len(payload['hold_reject_review_categories']['hold'])}")
    print(f"review={len(payload['hold_reject_review_categories']['review'])}")
    print(f"reject={len(payload['hold_reject_review_categories']['reject'])}")
    print(f"packet_json={args.out_dir / JSON_REPORT_NAME}")
    print(f"packet_markdown={args.out_dir / MARKDOWN_REPORT_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
