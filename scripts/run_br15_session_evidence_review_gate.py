from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engines.moonshot.deterministic.br15_session_evidence_review_gate import (
    DEFAULT_EVIDENCE_DIR,
    DEFAULT_REPORT_DIR,
    run_session_evidence_review_gate,
    session_evidence_review_payload,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run BR-15 session evidence review gate.")
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_REPORT_DIR)
    args = parser.parse_args()

    report = run_session_evidence_review_gate(evidence_dir=args.evidence_dir, out_dir=args.out_dir)
    payload = session_evidence_review_payload(report)
    json_path = args.out_dir / "session_evidence_review_gate.json"
    markdown_path = args.out_dir / "session_evidence_review_gate.md"
    print(f"{payload['phase']} {payload['module']}")
    print("LIVE TRADING: DISABLED")
    print(f"label={payload['label']}")
    print(f"readiness_state={payload['readiness_state']['state']}")
    print(f"review_json={json_path}")
    print(f"review_markdown={markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
