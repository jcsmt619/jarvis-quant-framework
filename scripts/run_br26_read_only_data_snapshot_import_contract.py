from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engines.moonshot.deterministic.br26_read_only_data_snapshot_import_contract import (
    DEFAULT_APPROVED_SNAPSHOT_PATHS,
    DEFAULT_REPORT_DIR,
    JSON_REPORT_NAME,
    MARKDOWN_REPORT_NAME,
    read_only_data_snapshot_import_contract_payload,
    run_read_only_data_snapshot_import_contract,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run BR-26 read-only data snapshot import contract.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--snapshot", type=Path, action="append", dest="snapshots")
    args = parser.parse_args()

    snapshot_paths = tuple(args.snapshots) if args.snapshots else DEFAULT_APPROVED_SNAPSHOT_PATHS
    contract = run_read_only_data_snapshot_import_contract(
        snapshot_paths=snapshot_paths,
        approved_snapshot_paths=DEFAULT_APPROVED_SNAPSHOT_PATHS,
        out_dir=args.out_dir,
    )
    payload = read_only_data_snapshot_import_contract_payload(contract)
    print(f"{payload['phase']} {payload['module']}")
    print("LIVE TRADING: DISABLED")
    print(f"label={payload['label']}")
    print(f"accepted_snapshot_count={payload['metrics']['accepted_snapshot_count']}")
    print(f"rejected_snapshot_count={payload['metrics']['rejected_snapshot_count']}")
    print(f"contract_json={args.out_dir / JSON_REPORT_NAME}")
    print(f"contract_markdown={args.out_dir / MARKDOWN_REPORT_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
