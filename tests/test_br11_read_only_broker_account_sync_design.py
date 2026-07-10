from __future__ import annotations

from pathlib import Path

import pytest

from broker import get_broker
from broker.account_sync_design import (
    ALLOWED_SYNC_FIELDS,
    MODULE_NAME,
    PHASE_ID,
    BrokerAccountOpenOrderSnapshot,
    BrokerAccountPositionSnapshot,
    BrokerAccountSyncSnapshot,
    evaluate_broker_account_sync_design,
    runtime_notes,
    safety_manifest,
    validate_account_sync_snapshot,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


MODULE_PATH = Path("broker/account_sync_design.py")
DOC_PATH = Path("docs/brendan_strategy/br11_read_only_broker_account_sync_design.md")


def test_br11_safety_manifest_is_design_only_and_disabled() -> None:
    manifest = safety_manifest()

    assert manifest["phase"] == PHASE_ID
    assert manifest["module"] == MODULE_NAME
    assert manifest["labels"] == (
        RESEARCH_ONLY,
        MONITOR_ONLY,
        PAPER_ONLY,
        HUMAN_REVIEW_REQUIRED,
        BLOCKED_BY_SAFETY_GATE,
    )
    assert manifest["read_only"] is True
    assert manifest["credential_loading_required"] is False
    assert manifest["broker_connection_attempted"] is False
    assert manifest["broker_read_call_performed"] is False
    assert manifest["broker_order_call_performed"] is False
    assert manifest["account_state_imported"] is False
    assert manifest["order_routing_enabled"] is False
    assert manifest["live_trading_enabled"] is False
    assert manifest["LIVE TRADING"] == "DISABLED"


def test_br11_disabled_by_default_requires_no_provider_or_credentials() -> None:
    state = evaluate_broker_account_sync_design()

    assert state.requested is False
    assert state.provider_supplied is False
    assert state.provider_reads_allowed is False
    assert state.credential_loading_required is False
    assert state.broker_connection_attempted is False
    assert state.broker_read_call_performed is False
    assert state.broker_order_call_performed is False
    assert state.account_state_imported is False
    assert state.order_routing_enabled is False
    assert state.live_trading_enabled is False
    assert state.decision == "DESIGN_ONLY_DISABLED_BY_DEFAULT"


def test_br11_requested_without_provider_is_blocked_without_connection() -> None:
    state = evaluate_broker_account_sync_design(request_account_sync=True)

    assert state.requested is True
    assert state.provider_supplied is False
    assert state.credential_loading_required is False
    assert state.broker_connection_attempted is False
    assert state.account_state_imported is False
    assert state.decision == "BLOCKED_NO_READ_ONLY_PROVIDER"
    assert state.blocked_reasons == ("no read-only account sync provider supplied",)


def test_br11_provider_shape_ready_still_does_not_import_or_call_broker() -> None:
    state = evaluate_broker_account_sync_design(
        request_account_sync=True,
        provider_supplied=True,
        provider_reads_allowed=True,
    )

    assert state.provider_supplied is True
    assert state.provider_reads_allowed is True
    assert state.broker_connection_attempted is False
    assert state.broker_read_call_performed is False
    assert state.broker_order_call_performed is False
    assert state.account_state_imported is False
    assert state.live_trading_enabled is False
    assert state.decision == "DESIGN_INTERFACE_READY_IMPORT_DISABLED_IN_BR_11"


def test_br11_runtime_notes_include_required_disabled_flags() -> None:
    state = evaluate_broker_account_sync_design(
        request_account_sync=True,
        provider_supplied=True,
    )

    notes = runtime_notes(state)

    assert "credential_loading_required=false" in notes
    assert "broker_connection_attempted=false" in notes
    assert "broker_read_call_performed=false" in notes
    assert "broker_order_call_performed=false" in notes
    assert "account_state_imported=false" in notes
    assert "order_routing_enabled=false" in notes
    assert "live_trading_enabled=false" in notes
    assert "LIVE TRADING: DISABLED" in notes


def test_br11_validates_local_snapshot_without_credentials_or_connection() -> None:
    snapshot = BrokerAccountSyncSnapshot(
        broker_name="fixture_broker",
        source_timestamp_utc="2026-07-10T00:00:00+00:00",
        account_status="ACTIVE",
        cash=1000.0,
        equity=1250.0,
        buying_power=2000.0,
        positions=(
            BrokerAccountPositionSnapshot(
                symbol="EEM",
                quantity=2.0,
                market_value=100.0,
                average_entry_price=45.0,
            ),
        ),
        open_orders=(
            BrokerAccountOpenOrderSnapshot(
                broker_order_id_hash="sha256:example",
                symbol="EEM",
                status="accepted",
                quantity=1.0,
                side="buy",
            ),
        ),
    )

    assert validate_account_sync_snapshot(snapshot) is snapshot


def test_br11_rejects_snapshot_that_enables_unsafe_flags() -> None:
    snapshot = BrokerAccountSyncSnapshot(
        broker_name="fixture_broker",
        source_timestamp_utc="2026-07-10T00:00:00+00:00",
        account_status="ACTIVE",
        cash=1000.0,
        equity=1250.0,
        buying_power=2000.0,
        broker_order_call_performed=True,
    )

    with pytest.raises(ValueError, match="cannot perform broker order calls"):
        validate_account_sync_snapshot(snapshot)


def test_br11_allowed_sync_fields_are_account_state_only() -> None:
    assert ALLOWED_SYNC_FIELDS == (
        "account_status",
        "cash",
        "equity",
        "buying_power",
        "positions",
        "open_orders",
        "source_timestamp_utc",
    )


def test_br11_is_not_registered_as_a_broker_adapter() -> None:
    with pytest.raises(KeyError):
        get_broker("account_sync_design")


def test_br11_design_doc_records_scope_and_safety_flags() -> None:
    text = DOC_PATH.read_text(encoding="utf-8")

    assert "BR-11 Read Only Broker Account Sync Design" in text
    assert "LIVE TRADING: DISABLED" in text
    assert "credential_loading_required=false" in text
    assert "broker_connection_attempted=false" in text
    assert "broker_read_call_performed=false" in text
    assert "broker_order_call_performed=false" in text
    assert "account_state_imported=false" in text
    assert "order_routing_enabled=false" in text
    assert "live_trading_enabled=false" in text
    assert "does not require credentials" in text
    assert "does not connect to Alpaca, IBKR, TradeStation, or any broker" in text


def test_br11_source_does_not_introduce_forbidden_execution_labels() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    disallowed = [
        "BUY" + "_NOW",
        "SELL" + "_NOW",
        "EXECUTE" + "_TRADE",
        "AUTO" + "_TRADE",
    ]

    for label in disallowed:
        assert label not in source
