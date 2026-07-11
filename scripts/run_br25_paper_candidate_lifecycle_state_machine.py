from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engines.moonshot.deterministic.br25_paper_candidate_lifecycle_state_machine import (
    DEFAULT_REPORT_DIR,
    JSON_REPORT_NAME,
    MARKDOWN_REPORT_NAME,
    paper_candidate_lifecycle_state_machine_payload,
    run_paper_candidate_lifecycle_state_machine,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run BR-25 paper candidate lifecycle state machine.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_REPORT_DIR)
    args = parser.parse_args()

    state_machine = run_paper_candidate_lifecycle_state_machine(out_dir=args.out_dir)
    payload = paper_candidate_lifecycle_state_machine_payload(state_machine)
    print(f"{payload['phase']} {payload['module']}")
    print("LIVE TRADING: DISABLED")
    print(f"label={payload['label']}")
    print(f"state_count={payload['metrics']['state_count']}")
    print(f"allowed_transition_count={payload['metrics']['allowed_transition_count']}")
    print(f"forbidden_transition_count={payload['metrics']['forbidden_transition_count']}")
    print(f"state_machine_json={args.out_dir / JSON_REPORT_NAME}")
    print(f"state_machine_markdown={args.out_dir / MARKDOWN_REPORT_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
