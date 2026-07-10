from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engines.moonshot.deterministic.br16_fixture_to_real_data_boundary import (
    DEFAULT_FIXTURE_PATH,
    DEFAULT_REPORT_DIR,
    fixture_to_real_data_boundary_payload,
    run_fixture_to_real_data_boundary,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run BR-16 fixture-to-real-data boundary design.")
    parser.add_argument("--fixture-path", type=Path, default=DEFAULT_FIXTURE_PATH)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_REPORT_DIR)
    args = parser.parse_args()

    report = run_fixture_to_real_data_boundary(fixture_path=args.fixture_path, out_dir=args.out_dir)
    payload = fixture_to_real_data_boundary_payload(report)
    json_path = args.out_dir / "fixture_to_real_data_boundary.json"
    markdown_path = args.out_dir / "fixture_to_real_data_boundary.md"
    print(f"{payload['phase']} {payload['module']}")
    print("LIVE TRADING: DISABLED")
    print(f"label={payload['label']}")
    print(f"interfaces={payload['metrics']['interface_count']}")
    print(f"boundary_json={json_path}")
    print(f"boundary_markdown={markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
