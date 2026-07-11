from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engines.moonshot.deterministic.br29_offline_snapshot_research_replay_evidence_pack import (
    DEFAULT_BR28_REPORT_PATH,
    DEFAULT_REPORT_DIR,
    JSON_REPORT_NAME,
    MARKDOWN_REPORT_NAME,
    offline_snapshot_research_replay_evidence_pack_payload,
    run_offline_snapshot_research_replay_evidence_pack,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run BR-29 offline snapshot research replay evidence pack.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--br28-report", type=Path, default=DEFAULT_BR28_REPORT_PATH)
    args = parser.parse_args()

    pack = run_offline_snapshot_research_replay_evidence_pack(
        br28_report_path=args.br28_report,
        out_dir=args.out_dir,
    )
    payload = offline_snapshot_research_replay_evidence_pack_payload(pack)
    print(f"{payload['phase']} {payload['module']}")
    print("LIVE TRADING: DISABLED")
    print(f"label={payload['label']}")
    print(f"candidate_count={payload['metrics']['candidate_count']}")
    print(f"advanced_candidate_count={payload['metrics']['advanced_candidate_count']}")
    print(f"blocked_candidate_count={payload['metrics']['blocked_candidate_count']}")
    print(f"alpha_claimed={payload['metrics']['alpha_claimed']}")
    print(f"replay_json={args.out_dir / JSON_REPORT_NAME}")
    print(f"replay_markdown={args.out_dir / MARKDOWN_REPORT_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
