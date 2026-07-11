from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engines.moonshot.deterministic.br30_read_only_live_market_data_adapter import (
    DEFAULT_RECORDED_RESPONSE_PATH,
    DEFAULT_REPORT_DIR,
    JSON_REPORT_NAME,
    MARKDOWN_REPORT_NAME,
    NORMALIZED_SNAPSHOT_NAME,
    MarketDataRequest,
    read_only_live_market_data_adapter_payload,
    run_read_only_live_market_data_adapter,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run BR-30 read-only market data adapter evidence.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--mode", choices=("offline", "fixture", "recorded_response"), default="offline")
    parser.add_argument("--recorded-response", type=Path, default=DEFAULT_RECORDED_RESPONSE_PATH)
    parser.add_argument("--symbol", action="append", dest="symbols")
    parser.add_argument("--as-of", default=None)
    args = parser.parse_args()

    symbols = tuple(args.symbols) if args.symbols else ("SPY", "QQQ")
    recorded_path = args.recorded_response if args.mode in ("fixture", "recorded_response") else None
    as_of = _parse_as_of(args.as_of)
    request = MarketDataRequest(symbols=symbols, mode=args.mode, recorded_response_path=recorded_path, as_of=as_of)
    result = run_read_only_live_market_data_adapter(request=request, out_dir=args.out_dir)
    payload = read_only_live_market_data_adapter_payload(result)

    print(f"{payload['phase']} {payload['module']}")
    print("LIVE TRADING: DISABLED")
    print(f"label={payload['label']}")
    print(f"request_mode={payload['request_mode']}")
    print(f"accepted_for_shadow_research={payload['accepted_for_shadow_research']}")
    print(f"rejection_reasons={','.join(payload['rejection_reasons']) if payload['rejection_reasons'] else 'none'}")
    print(f"adapter_json={args.out_dir / JSON_REPORT_NAME}")
    print(f"adapter_markdown={args.out_dir / MARKDOWN_REPORT_NAME}")
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
