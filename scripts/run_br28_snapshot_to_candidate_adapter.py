from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engines.moonshot.deterministic.br28_snapshot_to_candidate_adapter import (
    DEFAULT_BR27_REPORT_PATH,
    DEFAULT_REPORT_DIR,
    DEFAULT_SOURCE_PATHS,
    JSON_REPORT_NAME,
    MARKDOWN_REPORT_NAME,
    snapshot_to_candidate_adapter_payload,
    run_snapshot_to_candidate_adapter,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run BR-28 snapshot-to-candidate deterministic adapter.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--br27-report", type=Path, default=DEFAULT_BR27_REPORT_PATH)
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=DEFAULT_SOURCE_PATHS["BR-27-reviewed approved offline snapshot"],
    )
    args = parser.parse_args()

    result = run_snapshot_to_candidate_adapter(
        source_paths={
            "BR-27 approved snapshot intake review gate": args.br27_report,
            "BR-27-reviewed approved offline snapshot": args.snapshot,
        },
        out_dir=args.out_dir,
    )
    payload = snapshot_to_candidate_adapter_payload(result)
    print(f"{payload['phase']} {payload['module']}")
    print("LIVE TRADING: DISABLED")
    print(f"label={payload['label']}")
    print(f"candidate_count={payload['metrics']['candidate_count']}")
    print(f"blocked_record_count={payload['metrics']['blocked_record_count']}")
    print(f"adapter_json={args.out_dir / JSON_REPORT_NAME}")
    print(f"adapter_markdown={args.out_dir / MARKDOWN_REPORT_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
