from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engines.moonshot.deterministic.br19_historical_replay_evidence_pack import (
    DEFAULT_FIXTURE_PATH,
    DEFAULT_REPORT_DIR,
    JSON_REPORT_NAME,
    MARKDOWN_REPORT_NAME,
    historical_replay_evidence_pack_payload,
    run_historical_replay_evidence_pack,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run BR-19 historical replay evidence pack.")
    parser.add_argument("--fixture-path", type=Path, default=DEFAULT_FIXTURE_PATH)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_REPORT_DIR)
    args = parser.parse_args()

    pack = run_historical_replay_evidence_pack(fixture_path=args.fixture_path, out_dir=args.out_dir)
    payload = historical_replay_evidence_pack_payload(pack)
    print(f"{payload['phase']} {payload['module']}")
    print("LIVE TRADING: DISABLED")
    print(f"label={payload['label']}")
    print(f"replay_window_count={payload['metrics']['replay_window_count']}")
    print(f"replay_record_count={payload['metrics']['replay_record_count']}")
    print(f"blocked_risk_gate_count={payload['metrics']['blocked_risk_gate_count']}")
    print(f"paper_only_change_count={payload['metrics']['paper_only_change_count']}")
    print(f"evidence_json={args.out_dir / JSON_REPORT_NAME}")
    print(f"evidence_markdown={args.out_dir / MARKDOWN_REPORT_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
