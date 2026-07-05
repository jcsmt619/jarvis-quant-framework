"""Alpaca paper account snapshot logging.

Phase 3B safety layer only.

This module reads paper account state through safe read-only calls.
It does not submit orders.
It does not implement broker execution.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from paper_trading.alpaca_config import AlpacaPaperConfig
from paper_trading.alpaca_health import create_alpaca_paper_client


@dataclass(frozen=True)
class AlpacaPaperAccountSnapshot:
    """Redacted paper account snapshot with no API secrets."""

    timestamp_utc: str
    account_status: str | None
    cash: str | None
    buying_power: str | None
    portfolio_value: str | None
    equity: str | None
    trading_blocked: bool
    account_blocked: bool
    positions_count: int
    open_orders_count: int
    order_submission_enabled: bool = False
    live_trading_enabled: bool = False

    def as_dict(self) -> dict[str, object]:
        """Return JSON-serializable snapshot data."""
        return asdict(self)


def _attr_as_str(obj: Any, name: str) -> str | None:
    value = getattr(obj, name, None)
    if value is None:
        return None
    return str(value)


def collect_alpaca_paper_account_snapshot(
    config: AlpacaPaperConfig,
    client_factory: Callable[..., Any] | None = None,
) -> AlpacaPaperAccountSnapshot:
    """Collect a read-only paper account snapshot.

    Allowed client calls:
    - get_account()
    - list_positions()
    - list_orders(status='open')

    Forbidden:
    - submit_order()
    - cancel_order()
    - any order mutation
    """
    client = create_alpaca_paper_client(config, client_factory=client_factory)

    account = client.get_account()
    positions = client.list_positions()
    open_orders = client.list_orders(status="open")

    return AlpacaPaperAccountSnapshot(
        timestamp_utc=datetime.now(UTC).isoformat(),
        account_status=_attr_as_str(account, "status"),
        cash=_attr_as_str(account, "cash"),
        buying_power=_attr_as_str(account, "buying_power"),
        portfolio_value=_attr_as_str(account, "portfolio_value"),
        equity=_attr_as_str(account, "equity"),
        trading_blocked=bool(getattr(account, "trading_blocked", False)),
        account_blocked=bool(getattr(account, "account_blocked", False)),
        positions_count=len(positions),
        open_orders_count=len(open_orders),
        order_submission_enabled=False,
        live_trading_enabled=False,
    )


def write_alpaca_paper_account_snapshot(
    snapshot: AlpacaPaperAccountSnapshot,
    output_dir: Path | str = "reports/paper_trading",
) -> Path:
    """Write paper account snapshot to a local JSON report file."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    file_path = output_path / f"alpaca_paper_account_snapshot_{stamp}.json"

    file_path.write_text(
        json.dumps(snapshot.as_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    return file_path
