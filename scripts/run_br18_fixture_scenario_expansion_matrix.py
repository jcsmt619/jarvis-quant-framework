from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engines.moonshot.deterministic.br18_fixture_scenario_expansion_matrix import (
    DEFAULT_FIXTURE_PATH,
    DEFAULT_REPORT_DIR,
    JSON_REPORT_NAME,
    MARKDOWN_REPORT_NAME,
    fixture_scenario_expansion_matrix_payload,
    run_fixture_scenario_expansion_matrix,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run BR-18 fixture scenario expansion matrix.")
    parser.add_argument("--fixture-path", type=Path, default=DEFAULT_FIXTURE_PATH)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_REPORT_DIR)
    args = parser.parse_args()

    report = run_fixture_scenario_expansion_matrix(fixture_path=args.fixture_path, out_dir=args.out_dir)
    payload = fixture_scenario_expansion_matrix_payload(report)
    print(f"{payload['phase']} {payload['module']}")
    print("LIVE TRADING: DISABLED")
    print(f"label={payload['label']}")
    print(f"scenario_count={payload['metrics']['scenario_count']}")
    print(f"matrix_cell_count={payload['metrics']['matrix_cell_count']}")
    print(f"blocked_scenario_count={payload['metrics']['blocked_scenario_count']}")
    print(f"paper_hold_scenario_count={payload['metrics']['paper_hold_scenario_count']}")
    print(f"matrix_json={args.out_dir / JSON_REPORT_NAME}")
    print(f"matrix_markdown={args.out_dir / MARKDOWN_REPORT_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
