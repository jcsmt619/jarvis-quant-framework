"""Local-only Alpaca paper connection check.

This script:
- reads environment variables from the current shell and optionally .env
- validates Alpaca paper-only configuration
- performs a read-only paper account health check through get_account()
- submits zero orders

Never paste API keys into ChatGPT, Cline, screenshots, or GitHub.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from paper_trading.alpaca_config import AlpacaConfigError, load_alpaca_paper_config
from paper_trading.alpaca_health import (
    AlpacaHealthCheckError,
    check_alpaca_paper_connection,
)


def load_env_file(path: Path) -> None:
    """Load simple KEY=VALUE lines from a local .env file into os.environ.

    Existing environment variables are not overwritten.
    This avoids requiring python-dotenv for a tiny local-only script.
    """
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value


def run_check(env_file: Path | None = None) -> int:
    """Run paper-only Alpaca config validation and read-only health check."""
    if env_file is not None:
        load_env_file(env_file)

    try:
        config = load_alpaca_paper_config()
    except AlpacaConfigError as exc:
        print("ALPACA PAPER CONFIG: FAIL")
        print(f"Reason: {exc}")
        return 1

    print("ALPACA PAPER CONFIG: PASS")
    print(f"Safe config summary: {config.redacted_summary()}")

    try:
        result = check_alpaca_paper_connection(config)
    except AlpacaHealthCheckError as exc:
        print("ALPACA PAPER HEALTH: FAIL")
        print(f"Reason: {exc}")
        return 1
    except AlpacaConfigError as exc:
        print("ALPACA PAPER HEALTH: FAIL")
        print(f"Reason: {exc}")
        return 1

    print("ALPACA PAPER HEALTH:", "PASS" if result.ok else "FAIL")
    print(f"Health result: {result}")
    print("ORDER SUBMISSION: DISABLED")
    print("LIVE TRADING: DISABLED")

    return 0 if result.ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Alpaca paper config and run a read-only health check."
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env"),
        help="Optional local .env file path. Defaults to .env.",
    )

    args = parser.parse_args()
    return run_check(env_file=args.env_file)


if __name__ == "__main__":
    raise SystemExit(main())
