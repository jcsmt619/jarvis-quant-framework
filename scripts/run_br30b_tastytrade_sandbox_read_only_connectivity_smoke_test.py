from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engines.moonshot.deterministic.br30b_tastytrade_sandbox_read_only_connectivity_smoke_test import (
    APPROVED_SYMBOLS,
    DEFAULT_REPORT_DIR,
    JSON_REPORT_NAME,
    MARKDOWN_REPORT_NAME,
    NORMALIZED_SNAPSHOT_NAME,
    SandboxSmokeTestRequest,
    run_tastytrade_sandbox_read_only_connectivity_smoke_test,
    tastytrade_sandbox_read_only_connectivity_payload,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run BR-30B tastytrade sandbox read-only smoke evidence.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--mode", choices=("offline", "sandbox_network"), default="offline")
    parser.add_argument("--symbol", action="append", dest="symbols")
    parser.add_argument("--as-of", default=None)
    args = parser.parse_args()

    symbols = tuple(args.symbols) if args.symbols else APPROVED_SYMBOLS
    request = SandboxSmokeTestRequest(symbols=symbols, mode=args.mode, as_of=_parse_as_of(args.as_of))
    result = run_tastytrade_sandbox_read_only_connectivity_smoke_test(request=request, out_dir=args.out_dir)
    payload = tastytrade_sandbox_read_only_connectivity_payload(result)

    print(f"{payload['phase']} {payload['module']}")
    print("LIVE TRADING: DISABLED")
    print(f"label={payload['label']}")
    print(f"request_mode={payload['request_mode']}")
    print(f"accepted_for_monitoring={payload['accepted_for_monitoring']}")
    print(f"rejection_reasons={','.join(payload['rejection_reasons']) if payload['rejection_reasons'] else 'none'}")
    print(f"json={args.out_dir / JSON_REPORT_NAME}")
    print(f"markdown={args.out_dir / MARKDOWN_REPORT_NAME}")
    if payload["normalized_snapshot"]:
        print(f"normalized_snapshot={args.out_dir / NORMALIZED_SNAPSHOT_NAME}")
    return 0


def _parse_as_of(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


if __name__ == "__main__":
    raise SystemExit(main())
