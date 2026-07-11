from __future__ import annotations

import json
from pathlib import Path

from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


DOC_PATH = Path("docs/UI_00_JARVIS_APPLICATION_ARCHITECTURE_CONTRACT.md")
SCHEMA_PATH = Path("ui_contracts/ui00_application_architecture_contract.schema.json")
FIXTURE_PATH = Path("ui_contracts/fixtures/ui00_application_architecture_contract.fixture.json")

REQUIRED_BOUNDARIES = {
    "quant_engine",
    "local_service_api",
    "event_stream",
    "frontend",
    "desktop_shell",
}

REQUIRED_MODULES = {
    "system_health",
    "data_status",
    "research",
    "screener",
    "opportunities",
    "analyst_theses",
    "market_regime",
    "lifecycle",
    "risk_gate",
    "portfolio",
    "alerts",
    "models",
    "performance_analytics",
    "backtests",
    "paper_activity",
    "options",
    "moonshot_research",
}

REQUIRED_FAILURE_STATES = {
    "DISCONNECTED",
    "STALE",
    "DEGRADED",
    "AUTH_REQUIRED",
    "FORBIDDEN",
    "COMMAND_REJECTED",
    "IDEMPOTENCY_CONFLICT",
    "SCHEMA_VERSION_UNSUPPORTED",
    "SAFETY_GATE_BLOCKED",
    "RESYNC_REQUIRED",
    "READ_MODEL_UNAVAILABLE",
}


def test_ui00_fixture_matches_contract_identity_and_safety_labels() -> None:
    payload = _fixture()

    assert payload["phase_id"] == "UI-00"
    assert payload["contract_id"] == "jarvis.ui00.application_architecture_contract"
    assert payload["schema_version"] == "v1"
    assert payload["labels"] == [
        RESEARCH_ONLY,
        MONITOR_ONLY,
        PAPER_ONLY,
        HUMAN_REVIEW_REQUIRED,
        BLOCKED_BY_SAFETY_GATE,
    ]
    assert payload["live_trading_status"] == "LIVE TRADING: DISABLED"
    assert all(value is False for value in payload["safety"].values())


def test_ui00_schema_and_fixture_record_required_architecture_boundaries() -> None:
    schema = _schema()
    payload = _fixture()

    assert schema["$id"] == "jarvis.ui00.application_architecture_contract.v1"
    assert set(schema["required"]) >= {
        "boundaries",
        "read_models",
        "commands",
        "events",
        "api",
        "updates",
        "auth",
        "audit",
        "failure_states",
        "dashboard_modules",
        "design",
    }
    assert {boundary["name"] for boundary in payload["boundaries"]} == REQUIRED_BOUNDARIES
    assert {module["name"] for module in payload["read_models"]} == REQUIRED_MODULES
    assert set(payload["dashboard_modules"]) == REQUIRED_MODULES


def test_ui00_commands_keep_read_only_and_non_execution_state_change_boundary() -> None:
    payload = _fixture()

    read_only = payload["commands"]["read_only"]
    state_changing = payload["commands"]["state_changing"]
    forbidden = set(payload["commands"]["forbidden"])

    assert read_only
    assert state_changing
    assert all(command["classification"] == "read_only" for command in read_only)
    assert all(command["classification"] == "state_changing" for command in state_changing)
    assert all("correlation_id" in command["required_fields"] for command in read_only + state_changing)
    assert all("idempotency_key" in command["required_fields"] for command in state_changing)
    assert all(command["audit_required"] is True for command in state_changing)
    assert {
        "create_broker_connection",
        "submit_order",
        "route_order",
        "enable_live_trading",
        "bypass_safety_gate",
        "modify_secret",
    }.issubset(forbidden)


def test_ui00_event_api_update_auth_audit_contracts_are_traceable() -> None:
    payload = _fixture()

    assert payload["api"]["base_version"] == "v1"
    assert {"schema_version", "contract_id", "correlation_id", "created_at"}.issubset(
        set(payload["api"]["required_payload_fields"])
    )
    assert {"event_id", "sequence", "correlation_id", "causation_id", "label", "safety"}.issubset(
        set(payload["events"]["required_fields"])
    )
    assert payload["updates"]["transport_style"] == "local_websocket_style"
    assert "resync_required" in payload["updates"]["message_types"]
    assert "resume_from_last_seen_sequence" in payload["updates"]["reconnect"]
    assert {role["name"] for role in payload["auth"]["roles"]} == {
        "viewer",
        "researcher",
        "operator",
        "auditor",
        "admin",
    }
    assert {"correlation_id", "idempotency_key", "live_trading_status"}.issubset(
        set(payload["audit"]["required_fields"])
    )
    assert set(payload["failure_states"]) == REQUIRED_FAILURE_STATES


def test_ui00_document_records_required_safety_and_design_language() -> None:
    text = DOC_PATH.read_text(encoding="utf-8")

    assert "LIVE TRADING: DISABLED" in text
    assert "PowerShell on PC, Cline, Python scripts, tests, scheduled automation" in text
    assert "provider_credentials_stored_in_ui=false" in text
    assert "broker_credentials_stored_in_ui=false" in text
    assert "ui_required_for_engine_operation=false" in text
    assert "futuristic dark holographic HUD" in text
    assert "legible, truthful, keyboard-accessible, screen-reader-friendly" in text
    assert "These artifacts are contract fixtures for future implementation work" in text


def test_ui00_contract_files_do_not_introduce_forbidden_trade_labels_or_runtime_code() -> None:
    paths = (DOC_PATH, SCHEMA_PATH, FIXTURE_PATH)
    disallowed = [
        "BUY" + "_NOW",
        "SELL" + "_NOW",
        "EXECUTE" + "_TRADE",
        "AUTO" + "_TRADE",
    ]

    for path in paths:
        text = path.read_text(encoding="utf-8")
        for label in disallowed:
            assert label not in text

    assert not Path("ui").exists()
    assert not Path("frontend").exists()
    assert not Path("desktop").exists()


def _schema() -> dict[str, object]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _fixture() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
