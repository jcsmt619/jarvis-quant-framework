"""Read-only Alpaca paper account state snapshot.

Phase 9A safety layer.

This module reads paper account state only:
- account status
- cash
- portfolio value
- current symbol position
- open symbol orders

It never submits, replaces, cancels, or modifies orders.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from paper_trading.alpaca_config import AlpacaPaperConfig, validate_alpaca_paper_config


FINAL_ORDER_STATUSES = {
    "filled",
    "canceled",
    "cancelled",
    "expired",
    "rejected",
}


@dataclass(frozen=True)
class AlpacaPaperSymbolState:
    timestamp_utc: str
    symbol: str
    account_status: str
    cash: str
    portfolio_value: str
    buying_power: str
    position_quantity: float
    position_open: bool
    open_symbol_orders_count: int
    open_symbol_order_ids: list[str]
    read_only: bool
    order_submission_enabled: bool
    broker_order_call_performed: bool
    live_trading_enabled: bool
    note: str = (
        "READ ONLY ACCOUNT STATE: no paper order, live order, cancel, replace, "
        "or broker execution was submitted."
    )


def _get_attr(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _text(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "value"):
        value = value.value
    return str(value)


def _quantity_to_float(value: Any) -> float:
    if value is None:
        return 0.0
    if hasattr(value, "value"):
        value = value.value
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _symbol_matches(value: Any, symbol: str) -> bool:
    return _text(value).upper() == symbol.upper()


def _is_open_order(order: Any) -> bool:
    status = _text(_get_attr(order, "status", "")).lower()
    return status not in FINAL_ORDER_STATUSES


def _read_positions(client: Any) -> list[Any]:
    if hasattr(client, "get_all_positions"):
        return list(client.get_all_positions())

    if hasattr(client, "list_positions"):
        return list(client.list_positions())

    raise AttributeError(
        "paper client does not support position listing; expected get_all_positions() or list_positions()"
    )


def _read_orders(client: Any) -> list[Any]:
    if hasattr(client, "get_orders"):
        return list(client.get_orders())

    if hasattr(client, "list_orders"):
        try:
            return list(client.list_orders(status="open"))
        except TypeError:
            return list(client.list_orders())

    raise AttributeError(
        "paper client does not support order listing; expected get_orders() or list_orders()"
    )


def build_alpaca_paper_symbol_state(
    *,
    config: AlpacaPaperConfig,
    symbol: str,
    paper_client_factory: Callable[[], Any],
) -> AlpacaPaperSymbolState:
    """Build a read-only paper account state snapshot for one symbol."""

    validate_alpaca_paper_config(config)

    if not symbol or not symbol.strip():
        raise ValueError("symbol is required")

    if paper_client_factory is None:
        raise ValueError("paper_client_factory is required")

    normalized_symbol = symbol.strip().upper()
    client = paper_client_factory()

    account = client.get_account()
    positions = _read_positions(client)
    orders = _read_orders(client)

    position_quantity = 0.0
    for position in positions:
        if _symbol_matches(_get_attr(position, "symbol", ""), normalized_symbol):
            position_quantity += _quantity_to_float(_get_attr(position, "qty", 0))

    open_symbol_order_ids: list[str] = []
    for order in orders:
        if not _symbol_matches(_get_attr(order, "symbol", ""), normalized_symbol):
            continue
        if not _is_open_order(order):
            continue
        order_id = _text(_get_attr(order, "id", ""))
        if order_id:
            open_symbol_order_ids.append(order_id)

    return AlpacaPaperSymbolState(
        timestamp_utc=datetime.now(UTC).isoformat(),
        symbol=normalized_symbol,
        account_status=_text(_get_attr(account, "status", "")),
        cash=_text(_get_attr(account, "cash", "")),
        portfolio_value=_text(_get_attr(account, "portfolio_value", "")),
        buying_power=_text(_get_attr(account, "buying_power", "")),
        position_quantity=position_quantity,
        position_open=abs(position_quantity) > 0,
        open_symbol_orders_count=len(open_symbol_order_ids),
        open_symbol_order_ids=open_symbol_order_ids,
        read_only=True,
        order_submission_enabled=False,
        broker_order_call_performed=False,
        live_trading_enabled=False,
    )


def write_alpaca_paper_symbol_state(
    state: AlpacaPaperSymbolState,
    *,
    output_dir: Path = Path("reports/paper_trading"),
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = output_dir / f"alpaca_paper_symbol_state_{state.symbol.lower()}_{timestamp}.json"

    path.write_text(json.dumps(asdict(state), indent=2, sort_keys=True), encoding="utf-8")
    return path
