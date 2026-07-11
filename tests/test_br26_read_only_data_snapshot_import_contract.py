from __future__ import annotations

import json
import shutil
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from engines.moonshot.deterministic.br26_read_only_data_snapshot_import_contract import (
    DEFAULT_APPROVED_SNAPSHOT_PATHS,
    DEFAULT_FIXTURE_PATH,
    DEFAULT_REPORT_DIR,
    JSON_REPORT_NAME,
    MARKDOWN_REPORT_NAME,
    MODULE_NAME,
    PHASE_ID,
    REDACTED_FIELDS,
    REJECTION_REASONS,
    REQUIRED_DISABLED_FLAGS,
    REQUIRED_PROVENANCE_FIELDS,
    REQUIRED_RECORD_FIELDS,
    REQUIRED_TOP_LEVEL_FIELDS,
    build_read_only_data_snapshot_import_contract,
    import_read_only_data_snapshot,
    read_only_data_snapshot_import_contract_payload,
    render_markdown_read_only_data_snapshot_import_contract,
    run_read_only_data_snapshot_import_contract,
    safety_manifest,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


MODULE_PATH = Path("engines/moonshot/deterministic/br26_read_only_data_snapshot_import_contract.py")
SCRIPT_PATH = Path("scripts/run_br26_read_only_data_snapshot_import_contract.py")
DOC_PATH = Path("docs/brendan_strategy/br26_read_only_data_snapshot_import_contract.md")
STALE_FIXTURE_PATH = Path("engines/moonshot/deterministic/fixtures/br26_read_only_data_snapshot_stale.json")


def test_br26_safety_manifest_is_file_based_offline_and_disabled() -> None:
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
    assert manifest["file_based"] is True
    assert manifest["offline_by_default"] is True
    assert manifest["read_only_import_contract"] is True
    assert manifest["approved_files_only"] is True
    assert manifest["account_imports_allowed"] is False
    assert manifest["data_provider_calls_authorized"] is False
    assert manifest["broker_actions_authorized"] is False
    assert manifest["order_paths_authorized"] is False
    for field_name in REQUIRED_DISABLED_FLAGS:
        assert manifest[field_name] is False
    assert manifest["LIVE TRADING"] == "DISABLED"


def test_br26_accepts_default_fixture_snapshot_contract() -> None:
    contract = build_read_only_data_snapshot_import_contract(
        as_of=datetime(2026, 7, 11, tzinfo=timezone.utc)
    )
    payload = read_only_data_snapshot_import_contract_payload(contract)

    assert DEFAULT_FIXTURE_PATH.exists()
    assert DEFAULT_APPROVED_SNAPSHOT_PATHS == (DEFAULT_FIXTURE_PATH,)
    assert payload["phase"] == "BR-26"
    assert payload["module"] == "Read Only Data Snapshot Import Contract"
    assert payload["label"] == HUMAN_REVIEW_REQUIRED
    assert set(payload["schema"]["required_top_level_fields"]) == set(REQUIRED_TOP_LEVEL_FIELDS)
    assert set(payload["schema"]["required_provenance_fields"]) == set(REQUIRED_PROVENANCE_FIELDS)
    assert set(payload["schema"]["required_record_fields"]) == set(REQUIRED_RECORD_FIELDS)
    assert set(REDACTED_FIELDS).issubset(set(payload["redaction_rules"]))
    assert set(REJECTION_REASONS) == set(payload["rejection_reasons"])
    assert payload["metrics"]["accepted_snapshot_count"] == 1
    assert payload["metrics"]["rejected_snapshot_count"] == 0
    assert payload["accepted_snapshots"][0]["label"] == HUMAN_REVIEW_REQUIRED
    assert payload["accepted_snapshots"][0]["record_count"] == 2
    assert payload["accepted_snapshots"][0]["symbol_count"] == 2
    assert payload["readiness_state"]["file_based"] is True
    assert payload["readiness_state"]["offline_by_default"] is True
    assert payload["readiness_state"]["ready_for_live_trading"] is False
    assert all(payload["acceptance_criteria"].values())


def test_br26_rejects_unapproved_missing_and_malformed_snapshots() -> None:
    tmp_path = _tmp_dir("missing_malformed")
    unapproved = tmp_path / "unapproved.json"
    unapproved.write_text("{}", encoding="utf-8")
    missing = tmp_path / "missing.json"
    malformed = tmp_path / "malformed.json"
    malformed.write_text("{not json", encoding="utf-8")

    assert import_read_only_data_snapshot(unapproved).reasons == ("snapshot_file_not_approved",)
    assert import_read_only_data_snapshot(missing, approved_snapshot_paths=(missing,)).reasons == ("snapshot_file_missing",)
    assert import_read_only_data_snapshot(malformed, approved_snapshot_paths=(malformed,)).reasons == ("snapshot_json_malformed",)


def test_br26_rejects_stale_low_provenance_redaction_and_unsafe_snapshots() -> None:
    tmp_path = _tmp_dir("reject_variants")
    stale = import_read_only_data_snapshot(
        STALE_FIXTURE_PATH,
        approved_snapshot_paths=(STALE_FIXTURE_PATH,),
        as_of=datetime(2026, 7, 11, tzinfo=timezone.utc),
    )
    assert "snapshot_stale" in stale.reasons
    assert stale.label == BLOCKED_BY_SAFETY_GATE

    low_provenance_path = _write_variant(tmp_path, "low_provenance.json", {"provenance": {"quality_score": 0.1}})
    redaction_path = _write_variant(tmp_path, "redaction.json", {"api_key": "redacted-value"})
    unsafe_path = _write_variant(tmp_path, "unsafe.json", {"safety": {"live_trading_enabled": True}})

    low_provenance = import_read_only_data_snapshot(
        low_provenance_path,
        approved_snapshot_paths=(low_provenance_path,),
        as_of=datetime(2026, 7, 11, tzinfo=timezone.utc),
    )
    redaction = import_read_only_data_snapshot(
        redaction_path,
        approved_snapshot_paths=(redaction_path,),
        as_of=datetime(2026, 7, 11, tzinfo=timezone.utc),
    )
    unsafe = import_read_only_data_snapshot(
        unsafe_path,
        approved_snapshot_paths=(unsafe_path,),
        as_of=datetime(2026, 7, 11, tzinfo=timezone.utc),
    )

    assert "snapshot_low_provenance" in low_provenance.reasons
    assert "snapshot_contains_unredacted_sensitive_field" in redaction.reasons
    assert "snapshot_contains_unsafe_runtime_state" in unsafe.reasons
    assert all(decision.accepted is False for decision in (low_provenance, redaction, unsafe))


def test_br26_rejects_schema_and_checksum_failures() -> None:
    tmp_path = _tmp_dir("schema_checksum")
    missing_field_path = _write_variant(tmp_path, "missing_field.json", {}, remove_field="records")
    bad_record_path = _write_variant(tmp_path, "bad_record.json", {"records": [{"symbol": "SPY"}]})

    missing_field = import_read_only_data_snapshot(
        missing_field_path,
        approved_snapshot_paths=(missing_field_path,),
        as_of=datetime(2026, 7, 11, tzinfo=timezone.utc),
    )
    bad_record = import_read_only_data_snapshot(
        bad_record_path,
        approved_snapshot_paths=(bad_record_path,),
        as_of=datetime(2026, 7, 11, tzinfo=timezone.utc),
    )

    assert "snapshot_missing_required_field" in missing_field.reasons
    assert "snapshot_schema_malformed" in bad_record.reasons
    assert "snapshot_checksum_mismatch" in bad_record.reasons


def test_br26_runner_writes_json_and_markdown_reports() -> None:
    out_dir = Path(".codex_pytest_tmp/br26_snapshot_contract_test")
    if out_dir.exists():
        shutil.rmtree(out_dir)

    contract = run_read_only_data_snapshot_import_contract(
        out_dir=out_dir,
        as_of=datetime(2026, 7, 11, tzinfo=timezone.utc),
    )
    payload = read_only_data_snapshot_import_contract_payload(contract)

    assert payload["metrics"]["accepted_snapshot_count"] == 1
    assert (out_dir / JSON_REPORT_NAME).exists()
    assert (out_dir / MARKDOWN_REPORT_NAME).exists()
    assert DEFAULT_REPORT_DIR.name in str(DEFAULT_REPORT_DIR)

    shutil.rmtree(out_dir)


def test_br26_markdown_script_and_doc_record_required_sections() -> None:
    contract = build_read_only_data_snapshot_import_contract(
        as_of=datetime(2026, 7, 11, tzinfo=timezone.utc)
    )
    markdown = render_markdown_read_only_data_snapshot_import_contract(contract)
    doc_text = DOC_PATH.read_text(encoding="utf-8")
    script_text = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "BR-26 Read Only Data Snapshot Import Contract" in markdown
    assert "LIVE TRADING: DISABLED" in markdown
    assert "## Approved Files" in markdown
    assert "## Schema" in markdown
    assert "## Validation Rules" in markdown
    assert "## Import Decisions" in markdown
    assert "## Rejection Reasons" in markdown
    assert "## Redaction Rules" in markdown
    assert "does not read `.env`" in doc_text
    assert "does not call data providers" in doc_text
    assert "does not import accounts" in doc_text
    assert "does not create broker actions" in doc_text
    assert "does not create order paths" in doc_text
    assert "does not mutate paper state" in doc_text
    assert "does not mutate live state" in doc_text
    assert "does not authorize live trading" in doc_text
    assert "live_trading_enabled=false" in doc_text
    assert JSON_REPORT_NAME in doc_text
    assert MARKDOWN_REPORT_NAME in doc_text
    assert script_text.count("LIVE TRADING: DISABLED") == 1


def test_br26_validation_rejects_unsafe_contract_mutations() -> None:
    contract = build_read_only_data_snapshot_import_contract(
        as_of=datetime(2026, 7, 11, tzinfo=timezone.utc)
    )

    with pytest.raises(ValueError, match="cannot set live_trading_enabled"):
        replace(contract, safety={**contract.safety, "live_trading_enabled": True}).validate()

    with pytest.raises(ValueError, match="cannot set credential_loading_attempted"):
        replace(contract, safety={**contract.safety, "credential_loading_attempted": True}).validate()

    with pytest.raises(ValueError, match="cannot set data_provider_call_attempted"):
        replace(contract, safety={**contract.safety, "data_provider_call_attempted": True}).validate()

    with pytest.raises(ValueError, match="cannot set broker_order_call_performed"):
        replace(contract, safety={**contract.safety, "broker_order_call_performed": True}).validate()

    with pytest.raises(ValueError, match="cannot set order_path_created"):
        replace(contract, safety={**contract.safety, "order_path_created": True}).validate()

    with pytest.raises(ValueError, match="cannot allow account_imports_allowed"):
        replace(contract, safety={**contract.safety, "account_imports_allowed": True}).validate()

    with pytest.raises(ValueError, match="must keep LIVE TRADING disabled"):
        replace(contract, safety={**contract.safety, "LIVE TRADING": "ENABLED"}).validate()

    with pytest.raises(ValueError, match="must require human review"):
        replace(contract, label=MONITOR_ONLY).validate()


def test_br26_source_does_not_introduce_forbidden_execution_labels_or_broker_imports() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    disallowed = [
        "BUY" + "_NOW",
        "SELL" + "_NOW",
        "EXECUTE" + "_TRADE",
        "AUTO" + "_TRADE",
    ]

    for label in disallowed:
        assert label not in source
    assert "from broker" not in source
    assert "import broker" not in source


def _write_variant(
    tmp_path: Path,
    name: str,
    updates: dict[str, object],
    remove_field: str | None = None,
) -> Path:
    payload = json.loads(DEFAULT_FIXTURE_PATH.read_text(encoding="utf-8"))
    payload["provenance"]["source_file_name"] = name
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(payload.get(key), dict):
            payload[key].update(value)
        else:
            payload[key] = value
    if remove_field:
        payload.pop(remove_field, None)
    path = tmp_path / name
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _tmp_dir(name: str) -> Path:
    path = Path(".codex_pytest_tmp/br26_read_only_snapshot_tests") / name
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    return path
