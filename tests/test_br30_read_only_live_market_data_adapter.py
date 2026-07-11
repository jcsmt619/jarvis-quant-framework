from __future__ import annotations

import json
import shutil
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from engines.moonshot.deterministic.br26_read_only_data_snapshot_import_contract import (
    import_read_only_data_snapshot,
)
from engines.moonshot.deterministic.br30_read_only_live_market_data_adapter import (
    DEFAULT_RECORDED_RESPONSE_PATH,
    DEFAULT_REPORT_DIR,
    JSON_REPORT_NAME,
    MARKDOWN_REPORT_NAME,
    MODULE_NAME,
    NORMALIZED_SNAPSHOT_NAME,
    PHASE_ID,
    MarketDataRequest,
    build_read_only_live_market_data_adapter_evidence,
    read_only_live_market_data_adapter_payload,
    render_markdown_read_only_live_market_data_adapter,
    run_read_only_live_market_data_adapter,
    safety_manifest,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


MODULE_PATH = Path("engines/moonshot/deterministic/br30_read_only_live_market_data_adapter.py")
SCRIPT_PATH = Path("scripts/run_br30_read_only_live_market_data_adapter.py")
DOC_PATH = Path("docs/brendan_strategy/br30_read_only_live_market_data_adapter.md")


def test_br30_safety_manifest_is_read_only_offline_and_disabled() -> None:
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
    assert manifest["provider_independent_interface"] is True
    assert manifest["tastytrade_compatible_adapter"] is True
    assert manifest["offline_by_default"] is True
    assert manifest["fail_closed_by_default"] is True
    assert manifest["account_capabilities_available"] is False
    assert manifest["execution_capabilities_available"] is False
    assert manifest["data_provider_calls_authorized"] is False
    assert manifest["broker_write_operations_authorized"] is False
    assert manifest["external_routing_paths_authorized"] is False
    assert manifest["LIVE TRADING"] == "DISABLED"


def test_br30_default_runtime_is_offline_and_fail_closed() -> None:
    result = build_read_only_live_market_data_adapter_evidence()
    payload = read_only_live_market_data_adapter_payload(result)

    assert payload["phase"] == "BR-30"
    assert payload["label"] == BLOCKED_BY_SAFETY_GATE
    assert payload["request_mode"] == "offline"
    assert payload["accepted_for_shadow_research"] is False
    assert "runtime_mode_not_allowed" in payload["rejection_reasons"]
    assert "runtime_config_missing" in payload["rejection_reasons"]
    assert payload["normalized_snapshot"] is None
    assert payload["readiness_state"]["ready_for_live_trading"] is False


def test_br30_recorded_response_normalizes_to_br26_snapshot_contract() -> None:
    request = MarketDataRequest(
        symbols=("SPY", "QQQ"),
        mode="recorded_response",
        recorded_response_path=DEFAULT_RECORDED_RESPONSE_PATH,
        as_of=datetime(2026, 7, 11, 16, 5, tzinfo=timezone.utc),
    )
    result = build_read_only_live_market_data_adapter_evidence(request)
    payload = read_only_live_market_data_adapter_payload(result)
    snapshot = payload["normalized_snapshot"]

    assert DEFAULT_RECORDED_RESPONSE_PATH.exists()
    assert payload["accepted_for_shadow_research"] is True
    assert payload["label"] == HUMAN_REVIEW_REQUIRED
    assert payload["rejection_reasons"] == ()
    assert payload["evidence"]["feed_identity"] == "tastytrade.market-data.read-only"
    assert payload["evidence"]["raw_checksum_sha256"]
    assert payload["evidence"]["normalized_checksum_sha256"]
    assert snapshot["snapshot_version"] == "1"
    assert snapshot["source_kind"] == "approved_offline_file"
    assert snapshot["data_domain"] == "daily_ohlcv"
    assert snapshot["provenance"]["provider_name"] == "tastytrade"
    assert snapshot["provenance"]["schema_name"] == "br26.read_only_data_snapshot.v1"
    assert set(snapshot["symbols"]) == {"SPY", "QQQ"}
    assert len(snapshot["records"]) == 2
    assert snapshot["provider_metadata"]["quote_metadata"]
    assert snapshot["provider_metadata"]["option_chain_metadata"]
    assert all(payload["acceptance_criteria"].values())


def test_br30_written_normalized_snapshot_is_importable_by_br26_when_approved() -> None:
    out_dir = Path(".codex_pytest_tmp/br30_adapter_test")
    if out_dir.exists():
        shutil.rmtree(out_dir)
    request = MarketDataRequest(
        symbols=("SPY", "QQQ"),
        mode="recorded_response",
        recorded_response_path=DEFAULT_RECORDED_RESPONSE_PATH,
        as_of=datetime(2026, 7, 11, 16, 5, tzinfo=timezone.utc),
    )

    result = run_read_only_live_market_data_adapter(request=request, out_dir=out_dir)
    payload = read_only_live_market_data_adapter_payload(result)
    snapshot_path = out_dir / NORMALIZED_SNAPSHOT_NAME
    decision = import_read_only_data_snapshot(
        snapshot_path,
        approved_snapshot_paths=(snapshot_path,),
        as_of=datetime(2026, 7, 11, 16, 5, tzinfo=timezone.utc),
    )

    assert payload["accepted_for_shadow_research"] is True
    assert (out_dir / JSON_REPORT_NAME).exists()
    assert (out_dir / MARKDOWN_REPORT_NAME).exists()
    assert snapshot_path.exists()
    assert decision.accepted is True
    assert decision.label == HUMAN_REVIEW_REQUIRED
    assert DEFAULT_REPORT_DIR.name in str(DEFAULT_REPORT_DIR)

    shutil.rmtree(out_dir)


@pytest.mark.parametrize(
    ("name", "update", "expected_reason"),
    [
        ("reconnect.json", {"events": {0: {"connection_state": "reconnect_open"}}}, "reconnect_boundary_open"),
        ("retry.json", {"events": {0: {"retry_count": 4}}}, "retry_boundary_exceeded"),
        ("rate_limit.json", {"events": {0: {"rate_limit_remaining": -1}}}, "rate_limit_boundary_exceeded"),
        ("duplicate.json", {"events": {1: {"symbol": "SPY", "exchange_timestamp": "2026-07-11T16:00:00+00:00", "duplicate": True}}}, "duplicate_event"),
        ("timezone.json", {"events": {0: {"provider_timestamp": "2026-07-11T16:00:05"}}}, "timezone_invalid"),
        ("missing_bar.json", {"remove_event_index": 1}, "missing_bar"),
        ("delayed.json", {"events": {0: {"quality_flags": ["authorized", "delayed"]}}}, "delayed_feed"),
        ("sandbox_reset.json", {"events": {0: {"sandbox_reset": True}}}, "sandbox_reset_detected"),
        ("feed_mismatch.json", {"feed": "tastytrade.unapproved-feed"}, "feed_not_approved"),
        ("clock_skew.json", {"events": {0: {"provider_timestamp": "2026-07-11T16:05:00+00:00"}}}, "clock_skew_exceeded"),
        ("low_provenance.json", {"events": {0: {"provenance_score": 0.1}}}, "low_provenance"),
        ("incomplete.json", {"events": {0: {"close": None}}}, "missing_bar"),
    ],
)
def test_br30_rejects_required_boundary_failures(name: str, update: dict[str, object], expected_reason: str) -> None:
    tmp_dir = _tmp_dir("boundary_failures")
    variant = _write_variant(tmp_dir, name, update)
    request = MarketDataRequest(
        symbols=("SPY", "QQQ"),
        mode="recorded_response",
        recorded_response_path=variant,
        as_of=datetime(2026, 7, 11, 16, 5, tzinfo=timezone.utc),
    )

    result = build_read_only_live_market_data_adapter_evidence(request)
    payload = read_only_live_market_data_adapter_payload(result)

    assert payload["accepted_for_shadow_research"] is False
    assert payload["label"] == BLOCKED_BY_SAFETY_GATE
    assert expected_reason in payload["rejection_reasons"]

    shutil.rmtree(tmp_dir)


def test_br30_rejects_malformed_runtime_config_inside_repository_and_secrets() -> None:
    tmp_dir = _tmp_dir("runtime_config")
    config_path = tmp_dir / "runtime_config.json"
    config_path.write_text(json.dumps({"api_key": "do-not-use"}), encoding="utf-8")
    request = MarketDataRequest(
        symbols=("SPY",),
        mode="recorded_response",
        recorded_response_path=DEFAULT_RECORDED_RESPONSE_PATH,
        runtime_config_path=config_path,
        as_of=datetime(2026, 7, 11, 16, 5, tzinfo=timezone.utc),
    )

    result = build_read_only_live_market_data_adapter_evidence(request)
    payload = read_only_live_market_data_adapter_payload(result)

    assert payload["accepted_for_shadow_research"] is False
    assert "runtime_config_inside_repository" in payload["rejection_reasons"]
    assert "runtime_config_contains_secret_material" in payload["rejection_reasons"]

    shutil.rmtree(tmp_dir)


def test_br30_markdown_script_and_doc_record_required_sections() -> None:
    request = MarketDataRequest(
        symbols=("SPY", "QQQ"),
        mode="recorded_response",
        recorded_response_path=DEFAULT_RECORDED_RESPONSE_PATH,
        as_of=datetime(2026, 7, 11, 16, 5, tzinfo=timezone.utc),
    )
    result = build_read_only_live_market_data_adapter_evidence(request)
    markdown = render_markdown_read_only_live_market_data_adapter(result)
    doc_text = DOC_PATH.read_text(encoding="utf-8")
    script_text = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "BR-30 Read Only Live Market Data Adapter" in markdown
    assert "LIVE TRADING: DISABLED" in markdown
    assert "## Evidence Checks" in markdown
    assert "## Boundary Evidence" in markdown
    assert "does not read `.env`" in doc_text
    assert "does not call data providers" in doc_text
    assert "does not provide account mutation capabilities" in doc_text
    assert "does not provide execution methods" in doc_text
    assert "does not submit orders" in doc_text
    assert "does not create order paths" in doc_text
    assert "does not mutate paper state" in doc_text
    assert "does not mutate live state" in doc_text
    assert "does not authorize live trading" in doc_text
    assert "live_trading_enabled=false" in doc_text
    assert JSON_REPORT_NAME in doc_text
    assert MARKDOWN_REPORT_NAME in doc_text
    assert NORMALIZED_SNAPSHOT_NAME in doc_text
    assert script_text.count("LIVE TRADING: DISABLED") == 1


def test_br30_validation_rejects_unsafe_mutations() -> None:
    result = build_read_only_live_market_data_adapter_evidence()

    with pytest.raises(ValueError, match="cannot set live_trading_enabled"):
        replace(result, safety={**result.safety, "live_trading_enabled": True}).validate()

    with pytest.raises(ValueError, match="cannot set credential_loading_attempted"):
        replace(result, safety={**result.safety, "credential_loading_attempted": True}).validate()

    with pytest.raises(ValueError, match="cannot set data_provider_call_attempted"):
        replace(result, safety={**result.safety, "data_provider_call_attempted": True}).validate()

    with pytest.raises(ValueError, match="cannot set broker_order_call_performed"):
        replace(result, safety={**result.safety, "broker_order_call_performed": True}).validate()

    with pytest.raises(ValueError, match="cannot allow execution_capabilities_available"):
        replace(result, safety={**result.safety, "execution_capabilities_available": True}).validate()

    with pytest.raises(ValueError, match="must keep LIVE TRADING disabled"):
        replace(result, safety={**result.safety, "LIVE TRADING": "ENABLED"}).validate()

    with pytest.raises(ValueError, match="must be blocked by safety gate"):
        replace(result, label=MONITOR_ONLY).validate()


def test_br30_source_does_not_introduce_forbidden_execution_labels_or_network_clients() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    disallowed = [
        "BUY" + "_NOW",
        "SELL" + "_NOW",
        "EXECUTE" + "_TRADE",
        "AUTO" + "_TRADE",
        "requests.",
        "httpx.",
        "urllib.request",
        "submit_order",
        "place_order",
    ]

    for token in disallowed:
        assert token not in source


def _write_variant(tmp_dir: Path, name: str, update: dict[str, object]) -> Path:
    payload = json.loads(DEFAULT_RECORDED_RESPONSE_PATH.read_text(encoding="utf-8"))
    remove_index = update.get("remove_event_index")
    if isinstance(remove_index, int):
        payload["events"].pop(remove_index)
    for key, value in update.items():
        if key == "events" and isinstance(value, dict):
            for index, event_updates in value.items():
                payload["events"][index].update(event_updates)
        elif key != "remove_event_index":
            payload[key] = value
    path = tmp_dir / name
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _tmp_dir(name: str) -> Path:
    path = Path(".codex_pytest_tmp/br30_read_only_market_data_tests") / name
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    return path
