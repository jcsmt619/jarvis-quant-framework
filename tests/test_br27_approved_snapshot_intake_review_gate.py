from __future__ import annotations

import json
import shutil
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from engines.moonshot.deterministic.br27_approved_snapshot_intake_review_gate import (
    DEFAULT_APPROVED_SNAPSHOT_PATH,
    DEFAULT_BR26_REPORT_PATH,
    DEFAULT_REPORT_DIR,
    JSON_REPORT_NAME,
    MARKDOWN_REPORT_NAME,
    MODULE_NAME,
    PHASE_ID,
    REJECTION_REASONS,
    REQUIRED_LABELS,
    REVIEW_CHECKS,
    approved_snapshot_intake_review_gate_payload,
    build_approved_snapshot_intake_review_gate,
    render_markdown_approved_snapshot_intake_review_gate,
    run_approved_snapshot_intake_review_gate,
    safety_manifest,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


MODULE_PATH = Path("engines/moonshot/deterministic/br27_approved_snapshot_intake_review_gate.py")
SCRIPT_PATH = Path("scripts/run_br27_approved_snapshot_intake_review_gate.py")
DOC_PATH = Path("docs/brendan_strategy/br27_approved_snapshot_intake_review_gate.md")


def test_br27_safety_manifest_is_offline_read_only_and_disabled() -> None:
    manifest = safety_manifest()

    assert manifest["phase"] == PHASE_ID
    assert manifest["module"] == MODULE_NAME
    assert manifest["labels"] == REQUIRED_LABELS
    assert manifest["labels"] == (
        RESEARCH_ONLY,
        MONITOR_ONLY,
        PAPER_ONLY,
        HUMAN_REVIEW_REQUIRED,
        BLOCKED_BY_SAFETY_GATE,
    )
    assert manifest["offline_only"] is True
    assert manifest["read_only"] is True
    assert manifest["report_only"] is True
    assert manifest["committed_br26_report_only"] is True
    assert manifest["approved_offline_snapshot_only"] is True
    assert manifest["accepted_snapshot_is_research_evidence_only"] is True
    assert manifest["separate_review_decision_required"] is True
    assert manifest["advancement_authorized"] is False
    assert manifest["broker_write_operations_authorized"] is False
    assert manifest["external_routing_paths_authorized"] is False
    assert manifest["data_provider_calls_authorized"] is False
    assert manifest["LIVE TRADING"] == "DISABLED"


def test_br27_accepts_default_snapshot_as_research_evidence_only() -> None:
    gate = build_approved_snapshot_intake_review_gate(as_of=datetime(2026, 7, 11, tzinfo=timezone.utc))
    payload = approved_snapshot_intake_review_gate_payload(gate)

    assert DEFAULT_BR26_REPORT_PATH.exists()
    assert DEFAULT_APPROVED_SNAPSHOT_PATH.exists()
    assert payload["phase"] == "BR-27"
    assert payload["module"] == "Approved Snapshot Intake Review Gate"
    assert payload["label"] == HUMAN_REVIEW_REQUIRED
    assert set(payload["review_checks"]) == set(REVIEW_CHECKS)
    assert set(payload["rejection_reasons"]) == set(REJECTION_REASONS)
    assert payload["metrics"]["accepted_research_evidence_count"] == 1
    assert payload["metrics"]["rejected_snapshot_count"] == 0
    record = payload["review_records"][0]
    assert record["accepted_as_research_evidence"] is True
    assert record["advancement_allowed"] is False
    assert record["separate_review_decision_required"] is True
    assert record["label"] == HUMAN_REVIEW_REQUIRED
    assert all(record["checks"].values())
    assert record["rejection_evidence"] == ()
    assert record["unresolved_blockers"] == ()
    assert record["snapshot_summary"]["snapshot_id"] == "br26-fixture-daily-ohlcv-001"
    assert record["snapshot_summary"]["record_count"] == 2
    assert record["observation_timestamps"]["freshness_as_of"] == "2026-07-10T20:00:00+00:00"
    assert payload["readiness_state"]["accepted_snapshot_is_research_evidence_only"] is True
    assert payload["readiness_state"]["ready_for_candidate_adapter"] is False
    assert payload["readiness_state"]["ready_for_live_trading"] is False
    assert all(payload["acceptance_criteria"].values())


def test_br27_rejects_unapproved_and_stale_snapshot_evidence() -> None:
    tmp_path = _tmp_dir("unapproved_stale")
    unapproved_snapshot = tmp_path / "unapproved.json"
    shutil.copyfile(DEFAULT_APPROVED_SNAPSHOT_PATH, unapproved_snapshot)
    stale_snapshot = Path("engines/moonshot/deterministic/fixtures/br26_read_only_data_snapshot_stale.json")

    unapproved_gate = build_approved_snapshot_intake_review_gate(
        source_paths={
            "BR-26 import contract": DEFAULT_BR26_REPORT_PATH,
            "approved offline snapshot": unapproved_snapshot,
        },
        as_of=datetime(2026, 7, 11, tzinfo=timezone.utc),
    )
    stale_gate = build_approved_snapshot_intake_review_gate(
        source_paths={
            "BR-26 import contract": DEFAULT_BR26_REPORT_PATH,
            "approved offline snapshot": stale_snapshot,
        },
        as_of=datetime(2026, 7, 11, tzinfo=timezone.utc),
    )

    unapproved_record = approved_snapshot_intake_review_gate_payload(unapproved_gate)["review_records"][0]
    stale_record = approved_snapshot_intake_review_gate_payload(stale_gate)["review_records"][0]

    assert unapproved_record["label"] == BLOCKED_BY_SAFETY_GATE
    assert unapproved_record["accepted_as_research_evidence"] is False
    assert "snapshot_file_not_approved_by_br26" in unapproved_record["rejection_evidence"]
    assert "snapshot_provenance_missing_or_low_quality" in unapproved_record["rejection_evidence"]
    assert stale_record["label"] == BLOCKED_BY_SAFETY_GATE
    assert "snapshot_file_not_approved_by_br26" in stale_record["rejection_evidence"]
    assert "snapshot_stale" in stale_record["rejection_evidence"]


def test_br27_rejects_checksum_schema_redaction_runtime_and_timestamp_failures() -> None:
    tmp_path = _tmp_dir("variants")
    checksum_path = _write_variant(tmp_path, "checksum.json", {"records": []})
    schema_path = _write_variant(tmp_path, "schema.json", {}, remove_field="records")
    redaction_path = _write_variant(tmp_path, "redaction.json", {"secret": "redacted-value"})
    runtime_path = _write_variant(tmp_path, "runtime.json", {"safety": {"live_trading_enabled": True}})
    timestamp_path = _write_variant(tmp_path, "timestamp.json", {"freshness_as_of": "not-a-date"})

    records = [
        _review_record_for(checksum_path),
        _review_record_for(schema_path),
        _review_record_for(redaction_path),
        _review_record_for(runtime_path),
        _review_record_for(timestamp_path),
    ]

    assert "snapshot_checksum_mismatch" in records[0]["rejection_evidence"]
    assert "snapshot_schema_malformed" in records[1]["rejection_evidence"]
    assert "snapshot_missing_required_field" in records[1]["rejection_evidence"]
    assert "snapshot_contains_unredacted_sensitive_field" in records[2]["rejection_evidence"]
    assert "snapshot_contains_unsafe_runtime_state" in records[3]["rejection_evidence"]
    assert "snapshot_observation_timestamp_invalid" in records[4]["rejection_evidence"]
    assert all(record["accepted_as_research_evidence"] is False for record in records)
    assert all(record["advancement_allowed"] is False for record in records)


def test_br27_runner_writes_json_and_markdown_reports() -> None:
    out_dir = Path(".codex_pytest_tmp/br27_snapshot_review_test")
    if out_dir.exists():
        shutil.rmtree(out_dir)

    gate = run_approved_snapshot_intake_review_gate(
        out_dir=out_dir,
        as_of=datetime(2026, 7, 11, tzinfo=timezone.utc),
    )
    payload = approved_snapshot_intake_review_gate_payload(gate)

    assert payload["metrics"]["accepted_research_evidence_count"] == 1
    assert (out_dir / JSON_REPORT_NAME).exists()
    assert (out_dir / MARKDOWN_REPORT_NAME).exists()
    assert DEFAULT_REPORT_DIR.name in str(DEFAULT_REPORT_DIR)

    shutil.rmtree(out_dir)


def test_br27_markdown_script_and_doc_record_required_sections() -> None:
    gate = build_approved_snapshot_intake_review_gate(as_of=datetime(2026, 7, 11, tzinfo=timezone.utc))
    markdown = render_markdown_approved_snapshot_intake_review_gate(gate)
    doc_text = DOC_PATH.read_text(encoding="utf-8")
    script_text = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "BR-27 Approved Snapshot Intake Review Gate" in markdown
    assert "LIVE TRADING: DISABLED" in markdown
    assert "## Source Evidence" in markdown
    assert "## Review Records" in markdown
    assert "## Checks" in markdown
    assert "## Observation Timestamps" in markdown
    assert "## Rejection Evidence" in markdown
    assert "## Required Human Review Actions" in markdown
    assert "does not read `.env`" in doc_text
    assert "does not call data providers" in doc_text
    assert "does not perform broker write operations" in doc_text
    assert "does not create external routing paths" in doc_text
    assert "does not mutate paper state" in doc_text
    assert "does not mutate live state" in doc_text
    assert "does not authorize live trading" in doc_text
    assert "live_trading_enabled=false" in doc_text
    assert JSON_REPORT_NAME in doc_text
    assert MARKDOWN_REPORT_NAME in doc_text
    assert script_text.count("LIVE TRADING: DISABLED") == 1


def test_br27_validation_rejects_unsafe_gate_mutations() -> None:
    gate = build_approved_snapshot_intake_review_gate(as_of=datetime(2026, 7, 11, tzinfo=timezone.utc))
    record = gate.review_records[0]

    with pytest.raises(ValueError, match="cannot set live_trading_enabled"):
        replace(gate, safety={**gate.safety, "live_trading_enabled": True}).validate()

    with pytest.raises(ValueError, match="cannot set credential_loading_attempted"):
        replace(gate, safety={**gate.safety, "credential_loading_attempted": True}).validate()

    with pytest.raises(ValueError, match="cannot set data_provider_call_attempted"):
        replace(gate, safety={**gate.safety, "data_provider_call_attempted": True}).validate()

    with pytest.raises(ValueError, match="cannot set broker_order_call_performed"):
        replace(gate, safety={**gate.safety, "broker_order_call_performed": True}).validate()

    with pytest.raises(ValueError, match="cannot allow advancement_authorized"):
        replace(gate, safety={**gate.safety, "advancement_authorized": True}).validate()

    with pytest.raises(ValueError, match="must keep LIVE TRADING disabled"):
        replace(gate, safety={**gate.safety, "LIVE TRADING": "ENABLED"}).validate()

    with pytest.raises(ValueError, match="must require human review"):
        replace(gate, label=MONITOR_ONLY).validate()

    with pytest.raises(ValueError, match="cannot allow advancement"):
        replace(record, advancement_allowed=True).validate()

    with pytest.raises(ValueError, match="must require a separate review decision"):
        replace(record, separate_review_decision_required=False).validate()


def test_br27_source_does_not_introduce_forbidden_execution_labels_or_broker_imports() -> None:
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


def _review_record_for(snapshot_path: Path) -> dict[str, object]:
    gate = build_approved_snapshot_intake_review_gate(
        source_paths={
            "BR-26 import contract": DEFAULT_BR26_REPORT_PATH,
            "approved offline snapshot": snapshot_path,
        },
        as_of=datetime(2026, 7, 11, tzinfo=timezone.utc),
    )
    return approved_snapshot_intake_review_gate_payload(gate)["review_records"][0]


def _write_variant(
    tmp_path: Path,
    name: str,
    updates: dict[str, object],
    remove_field: str | None = None,
) -> Path:
    payload = json.loads(DEFAULT_APPROVED_SNAPSHOT_PATH.read_text(encoding="utf-8"))
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
    path = Path(".codex_pytest_tmp/br27_approved_snapshot_review_tests") / name
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    return path
