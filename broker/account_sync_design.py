"""BR-11 read-only broker account sync design contracts.

This module defines future account-state import shapes only. It does not
load credentials, construct vendor SDK clients, connect to a broker, route
orders, or submit orders.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


PHASE_ID = "BR-11"
MODULE_NAME = "Read Only Broker Account Sync Design"
REQUIRED_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
ALLOWED_SYNC_FIELDS = (
    "account_status",
    "cash",
    "equity",
    "buying_power",
    "positions",
    "open_orders",
    "source_timestamp_utc",
)


class ReadOnlyBrokerAccountSyncProvider(Protocol):
    """Future provider shape for read-only account-state imports.

    Implementations must provide already-authenticated, read-only snapshots.
    BR-11 does not implement provider construction or credential loading.
    """

    def read_account_snapshot(self) -> "BrokerAccountSyncSnapshot":
        """Return a read-only account-state snapshot."""
        ...


@dataclass(frozen=True)
class BrokerAccountPositionSnapshot:
    symbol: str
    quantity: float
    market_value: float
    average_entry_price: float | None = None
    asset_class: str = "stock"

    def validate(self) -> None:
        _require_text("symbol", self.symbol)
        if self.symbol != self.symbol.upper():
            raise ValueError("position symbol must be uppercase")
        _require_text("asset_class", self.asset_class)


@dataclass(frozen=True)
class BrokerAccountOpenOrderSnapshot:
    broker_order_id_hash: str
    symbol: str
    status: str
    quantity: float
    side: str

    def validate(self) -> None:
        _require_text("broker_order_id_hash", self.broker_order_id_hash)
        _require_text("symbol", self.symbol)
        if self.symbol != self.symbol.upper():
            raise ValueError("open order symbol must be uppercase")
        _require_text("status", self.status)
        if self.side not in ("buy", "sell"):
            raise ValueError("open order side must be buy or sell")


@dataclass(frozen=True)
class BrokerAccountSyncSnapshot:
    broker_name: str
    source_timestamp_utc: str
    account_status: str
    cash: float
    equity: float
    buying_power: float
    positions: tuple[BrokerAccountPositionSnapshot, ...] = ()
    open_orders: tuple[BrokerAccountOpenOrderSnapshot, ...] = ()
    account_id_hash: str | None = None
    label: str = MONITOR_ONLY
    read_only: bool = True
    order_routing_enabled: bool = False
    broker_order_call_performed: bool = False
    live_trading_enabled: bool = False

    def validate(self) -> None:
        _require_text("broker_name", self.broker_name)
        _require_text("source_timestamp_utc", self.source_timestamp_utc)
        _require_text("account_status", self.account_status)
        _require_safe_label(self.label)
        if not self.read_only:
            raise ValueError("broker account sync snapshots must remain read-only")
        if self.order_routing_enabled:
            raise ValueError("broker account sync snapshots cannot enable order routing")
        if self.broker_order_call_performed:
            raise ValueError("broker account sync snapshots cannot perform broker order calls")
        if self.live_trading_enabled:
            raise ValueError("broker account sync snapshots cannot enable live trading")
        for position in self.positions:
            position.validate()
        for open_order in self.open_orders:
            open_order.validate()


@dataclass(frozen=True)
class BrokerAccountSyncDesignState:
    phase: str
    module: str
    labels: tuple[str, ...]
    requested: bool
    provider_supplied: bool
    provider_reads_allowed: bool
    credential_loading_required: bool
    broker_connection_attempted: bool
    broker_read_call_performed: bool
    broker_order_call_performed: bool
    account_state_imported: bool
    order_routing_enabled: bool
    live_trading_enabled: bool
    decision: str
    blocked_reasons: tuple[str, ...]
    live_trading_status: str = "LIVE TRADING: DISABLED"

    def validate(self) -> None:
        if self.phase != PHASE_ID:
            raise ValueError("broker account sync design state has wrong phase")
        if self.labels != REQUIRED_LABELS:
            raise ValueError("broker account sync design state must preserve required labels")
        if self.credential_loading_required:
            raise ValueError("BR-11 cannot require credential loading")
        if self.broker_connection_attempted:
            raise ValueError("BR-11 cannot attempt broker connections")
        if self.broker_order_call_performed:
            raise ValueError("BR-11 cannot perform broker order calls")
        if self.order_routing_enabled:
            raise ValueError("BR-11 cannot enable order routing")
        if self.live_trading_enabled:
            raise ValueError("BR-11 cannot enable live trading")
        if self.live_trading_status != "LIVE TRADING: DISABLED":
            raise ValueError("BR-11 must keep live trading disabled")


def safety_manifest() -> dict[str, object]:
    return {
        "phase": PHASE_ID,
        "module": MODULE_NAME,
        "labels": REQUIRED_LABELS,
        "read_only": True,
        "research_only": True,
        "monitor_only": True,
        "paper_only": True,
        "human_review_required": True,
        "credential_loading_required": False,
        "broker_connection_attempted": False,
        "broker_read_call_performed": False,
        "broker_order_call_performed": False,
        "account_state_imported": False,
        "order_routing_enabled": False,
        "live_trading_enabled": False,
        "LIVE TRADING": "DISABLED",
    }


def evaluate_broker_account_sync_design(
    *,
    request_account_sync: bool = False,
    provider_supplied: bool = False,
    provider_reads_allowed: bool = False,
) -> BrokerAccountSyncDesignState:
    """Evaluate BR-11 design readiness without touching any broker.

    Provider reads are modeled as a future phase flag. This function never
    receives or calls a provider object, so it cannot connect or require
    credentials by default.
    """

    if not request_account_sync:
        state = BrokerAccountSyncDesignState(
            phase=PHASE_ID,
            module=MODULE_NAME,
            labels=REQUIRED_LABELS,
            requested=False,
            provider_supplied=provider_supplied,
            provider_reads_allowed=False,
            credential_loading_required=False,
            broker_connection_attempted=False,
            broker_read_call_performed=False,
            broker_order_call_performed=False,
            account_state_imported=False,
            order_routing_enabled=False,
            live_trading_enabled=False,
            decision="DESIGN_ONLY_DISABLED_BY_DEFAULT",
            blocked_reasons=("read-only broker account sync is disabled by default",),
        )
        state.validate()
        return state

    if not provider_supplied:
        state = BrokerAccountSyncDesignState(
            phase=PHASE_ID,
            module=MODULE_NAME,
            labels=REQUIRED_LABELS,
            requested=True,
            provider_supplied=False,
            provider_reads_allowed=False,
            credential_loading_required=False,
            broker_connection_attempted=False,
            broker_read_call_performed=False,
            broker_order_call_performed=False,
            account_state_imported=False,
            order_routing_enabled=False,
            live_trading_enabled=False,
            decision="BLOCKED_NO_READ_ONLY_PROVIDER",
            blocked_reasons=("no read-only account sync provider supplied",),
        )
        state.validate()
        return state

    state = BrokerAccountSyncDesignState(
        phase=PHASE_ID,
        module=MODULE_NAME,
        labels=REQUIRED_LABELS,
        requested=True,
        provider_supplied=True,
        provider_reads_allowed=provider_reads_allowed,
        credential_loading_required=False,
        broker_connection_attempted=False,
        broker_read_call_performed=False,
        broker_order_call_performed=False,
        account_state_imported=False,
        order_routing_enabled=False,
        live_trading_enabled=False,
        decision="DESIGN_INTERFACE_READY_IMPORT_DISABLED_IN_BR_11",
        blocked_reasons=("BR-11 defines interface shape only; account import remains future work",),
    )
    state.validate()
    return state


def validate_account_sync_snapshot(snapshot: BrokerAccountSyncSnapshot) -> BrokerAccountSyncSnapshot:
    snapshot.validate()
    return snapshot


def runtime_notes(state: BrokerAccountSyncDesignState) -> tuple[str, ...]:
    state.validate()
    return (
        f"br11_account_sync_requested={str(state.requested).lower()}",
        f"br11_read_only_provider_supplied={str(state.provider_supplied).lower()}",
        f"br11_provider_reads_allowed={str(state.provider_reads_allowed).lower()}",
        f"credential_loading_required={str(state.credential_loading_required).lower()}",
        f"broker_connection_attempted={str(state.broker_connection_attempted).lower()}",
        f"broker_read_call_performed={str(state.broker_read_call_performed).lower()}",
        f"broker_order_call_performed={str(state.broker_order_call_performed).lower()}",
        f"account_state_imported={str(state.account_state_imported).lower()}",
        f"order_routing_enabled={str(state.order_routing_enabled).lower()}",
        f"live_trading_enabled={str(state.live_trading_enabled).lower()}",
        state.live_trading_status,
        f"br11_decision={state.decision}",
    )


def _require_text(field_name: str, value: str) -> None:
    if not value or not value.strip():
        raise ValueError(f"{field_name} is required")


def _require_safe_label(label: str) -> None:
    if label not in REQUIRED_LABELS:
        raise ValueError("label must be a safe BR-11 research, monitor, paper, review, or blocked label")
