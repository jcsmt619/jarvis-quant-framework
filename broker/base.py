"""
broker/base.py
==============
The abstract broker interface (adapter pattern): strategy, risk manager,
and gatekeeper talk to THIS, never to a vendor SDK. Adding a venue means
implementing this class -- nothing else in the system changes.

Scope note: this is the core execution/reconciliation contract actually
consumed by the framework today (gatekeeper + pipeline + paper loop).
Brackets and websocket subscriptions are deliberately NOT abstracted yet
-- abstractions for consumers that don't exist are how interfaces rot.
Extend when a second consumer appears. (get_bars was added exactly this
way when the paper loop became its first consumer.)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Account:
    equity: float
    cash: float
    buying_power: float
    status: str = "UNKNOWN"


@dataclass
class Position:
    symbol: str
    qty: float                  # signed: negative = short
    avg_entry_price: float
    market_value: float = 0.0


@dataclass
class Order:
    id: str
    symbol: str
    side: str                   # 'buy' | 'sell'
    qty: float
    order_type: str             # 'market' | 'limit'
    status: str                 # 'accepted' | 'filled' | 'rejected' | ...
    filled_qty: float = 0.0
    reason: str = ""            # populated on rejection
    raw: dict = field(default_factory=dict)


class BaseBroker(ABC):
    """Sync by default. Async-native venues should implement a parallel
    async adapter rather than mixing async/sync methods here."""

    @abstractmethod
    def get_account(self) -> Account: ...

    @abstractmethod
    def get_positions(self) -> list[Position]: ...

    @abstractmethod
    def submit_order(self, symbol: str, qty: float, side: str,
                     order_type: str = "market",
                     limit_price: float | None = None) -> Order: ...

    @abstractmethod
    def cancel_order(self, order_id: str) -> None: ...

    @abstractmethod
    def close_position(self, symbol: str) -> None: ...

    @abstractmethod
    def close_all_positions(self) -> None: ...

    @abstractmethod
    def is_market_open(self) -> bool: ...

    @abstractmethod
    def get_bars(self, symbols: list[str], timeframe: str = "1Min",
                 limit: int = 100) -> dict:
        """{symbol: DataFrame with a 'close' column, ascending time index}.
        Missing/failed symbols are simply absent from the dict."""
        ...

    # ------------------------------------------------------------------
    def position_map(self) -> dict[str, float]:
        """{symbol: signed qty} -- the gatekeeper's reconciliation input."""
        return {p.symbol: p.qty for p in self.get_positions() if p.qty != 0}

    def reconcile(self, gatekeeper) -> dict:
        """Startup reality check: local book vs this broker's book. Any
        mismatch disarms the gatekeeper (see utils.state_gatekeeper)."""
        return gatekeeper.reconcile_with_broker(self.position_map())

    def guarded_order(self, gatekeeper, symbol: str, qty: float, side: str,
                      order_type: str = "market",
                      limit_price: float | None = None) -> Order:
        """The only order path the pipeline should use: refuses while the
        gatekeeper is disarmed, and books synchronous fills into the local
        ledger so reconciliation stays truthful. Partial/async fills are
        caught by the next startup reconcile()."""
        if not gatekeeper.armed:
            return Order(id="", symbol=symbol, side=side,
                         qty=abs(float(qty)), order_type=order_type,
                         status="rejected",
                         reason="gatekeeper disarmed: "
                                + gatekeeper.state["strategy"]["halt_reason"])
        order = self.submit_order(symbol, qty, side, order_type, limit_price)
        if order.status == "filled" and order.filled_qty > 0:
            px = limit_price
            if px is None:
                pos = {p.symbol: p for p in self.get_positions()}.get(symbol)
                px = pos.avg_entry_price if pos else 0.0
            gatekeeper.update_position(symbol, order.filled_qty, float(px),
                                       side.upper())
        return order
