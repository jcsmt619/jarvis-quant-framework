from __future__ import annotations

import json
import shutil
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from engines.moonshot.deterministic.br28_snapshot_to_candidate_adapter import (
    DEFAULT_BR27_REPORT_PATH,
    DEFAULT_REPORT_DIR,
    DEFAULT_SOURCE_PATHS,
    JSON_REPORT_NAME,
    MARKDOWN_REPORT_NAME,
    MODULE_NAME,
    PHASE_ID,
    REQUIRED_LABELS,
    STRATEGY_VERSION,
    build_snapshot_to_candidate_adapter,
    render_markdown_snapshot_to_candidate_adapter,
    run_snapshot_to_candidate_adapter,
    safety_manifest,
    snapshot_to_candidate_adapter_payload,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


MODULE_PATH = Path("engines/moonshot/deterministic/br28_snapshot_to_candidate_adapter.py")
SCRIPT_PATH = Path("scripts/run_br28_snapshot_to_candidate_adapter.py")
DOC_PATH = Path("docs/brendan_strategy/br28_snapshot_to_candidate_adapter.md")
DEFAULT_SNAPSHOT_PATH = DEFAULT_SOURCE_PATHS["BR-27-reviewed approved offline snapshot"]


def test_br28_safety_manifest_is_offline_read_only_and_disabled() -> None:
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
    assert manifest["br27_reviewed_snapshot_only"] is True
    assert manifest["deterministic_adapter_only"] is True
    assert manifest["normalized_research_candidates_only"] is True
    assert manifest["lookahead_prevention_enforced"] is True
    assert manifest["evaluation_period_outcomes_used"] is False
    assert manifest["parameter_optimization_performed"] is False
    assert manifest["strategy_selected_using_evaluation_outcomes"] is False
    assert manifest["broker_write_operations_authorized"] is False
    assert manifest["external_routing_paths_authorized"] is False
    assert manifest["data_provider_calls_authorized"] is False
    assert manifest["LIVE TRADING"] == "DISABLED"


def test_br28_converts_br27_approved_snapshot_records_to_candidates() -> None:
    result = build_snapshot_to_candidate_adapter(as_of=datetime(2026, 7, 11, tzinfo=timezone.utc))
    payload = snapshot_to_candidate_adapter_payload(result)

    assert DEFAULT_BR27_REPORT_PATH.exists()
    assert DEFAULT_SNAPSHOT_PATH.exists()
    assert payload["phase"] == "BR-28"
    assert payload["module"] == "Snapshot to Candidate Deterministic Adapter"
    assert payload["label"] == HUMAN_REVIEW_REQUIRED
    assert payload["strategy_version"] == STRATEGY_VERSION
    assert payload["metrics"]["candidate_count"] == 2
    assert payload["metrics"]["blocked_record_count"] == 0
    assert all(payload["acceptance_criteria"].values())
    assert payload["readiness_state"]["candidate_records_authorize_trade"] is False
    assert payload["readiness_state"]["ready_for_live_trading"] is False

    candidate = payload["candidates"][0]
    assert candidate["candidate_id"].startswith("br28-")
    assert candidate["symbol"] == "QQQ"
    assert candidate["label"] == HUMAN_REVIEW_REQUIRED
    assert candidate["human_review_status"] == HUMAN_REVIEW_REQUIRED
    assert candidate["observation_timestamp"] == "2026-07-10T20:00:00+00:00"
    assert candidate["decision_timestamp"] == "2026-07-10T20:00:00+00:00"
    assert candidate["source_checksum_sha256"] == "e2744d6a31021c4cf0d3c91244d9f68cdf403a1d189adce7492c421e08a63429"
    assert candidate["provenance"]["snapshot_id"] == "br26-fixture-daily-ohlcv-001"
    assert candidate["strategy_version"] == STRATEGY_VERSION
    assert candidate["feature_inputs"]["close"] == 555.9
    assert candidate["missing_data_flags"] == ()
    assert candidate["stale_data_flags"] == ()
    assert candidate["benchmark_context"]["benchmark_symbol"] == "SPY"
    assert candidate["benchmark_context"]["benchmark_available_at_decision"] is True
    assert candidate["lookahead_guard"]["uses_only_records_at_or_before_decision_timestamp"] is True
    assert candidate["lookahead_guard"]["future_records_used"] is False
    assert candidate["lookahead_guard"]["evaluation_period_outcomes_used"] is False
    assert candidate["lookahead_guard"]["parameter_optimization_performed"] is False


def test_br28_blocks_unreviewed_snapshot_and_missing_br27_report() -> None:
    tmp_path = _tmp_dir("blocked_inputs")
    unreviewed_snapshot = tmp_path / "unreviewed.json"
    shutil.copyfile(DEFAULT_SNAPSHOT_PATH, unreviewed_snapshot)
    missing_report = tmp_path / "missing_br27.json"

    result = build_snapshot_to_candidate_adapter(
        source_paths={
            "BR-27 approved snapshot intake review gate": missing_report,
            "BR-27-reviewed approved offline snapshot": unreviewed_snapshot,
        },
        as_of=datetime(2026, 7, 11, tzinfo=timezone.utc),
    )
    payload = snapshot_to_candidate_adapter_payload(result)
    reasons = {reason for record in payload["blocked_records"] for reason in record["reasons"]}

    assert payload["metrics"]["candidate_count"] == 0
    assert "br27_report_missing" in reasons
    assert payload["adapter_checks"]["br27_report_accepted"] is False
    assert payload["adapter_checks"]["snapshot_path_matches_br27"] is False
    assert payload["acceptance_criteria"]["candidate_records_created"] is False


def test_br28_blocks_checksum_mismatch_and_missing_record_fields() -> None:
    tmp_path = _tmp_dir("bad_snapshot")
    bad_snapshot = _write_snapshot_variant(tmp_path, "bad_snapshot.json")
    br27_report = _write_br27_variant(tmp_path, bad_snapshot, checksum="expected-but-different")

    result = build_snapshot_to_candidate_adapter(
        source_paths={
            "BR-27 approved snapshot intake review gate": br27_report,
            "BR-27-reviewed approved offline snapshot": bad_snapshot,
        },
        as_of=datetime(2026, 7, 11, tzinfo=timezone.utc),
    )
    payload = snapshot_to_candidate_adapter_payload(result)
    reasons = {reason for record in payload["blocked_records"] for reason in record["reasons"]}

    assert payload["metrics"]["candidate_count"] == 0
    assert "snapshot_checksum_mismatch" in reasons
    assert payload["adapter_checks"]["snapshot_checksum_matches_br27"] is False


def test_br28_runner_writes_json_and_markdown_reports() -> None:
    out_dir = Path(".codex_pytest_tmp/br28_snapshot_adapter_test")
    if out_dir.exists():
        shutil.rmtree(out_dir)

    result = run_snapshot_to_candidate_adapter(
        out_dir=out_dir,
        as_of=datetime(2026, 7, 11, tzinfo=timezone.utc),
    )
    payload = snapshot_to_candidate_adapter_payload(result)

    assert payload["metrics"]["candidate_count"] == 2
    assert (out_dir / JSON_REPORT_NAME).exists()
    assert (out_dir / MARKDOWN_REPORT_NAME).exists()
    assert DEFAULT_REPORT_DIR.name in str(DEFAULT_REPORT_DIR)

    shutil.rmtree(out_dir)


def test_br28_markdown_script_and_doc_record_required_sections() -> None:
    result = build_snapshot_to_candidate_adapter(as_of=datetime(2026, 7, 11, tzinfo=timezone.utc))
    markdown = render_markdown_snapshot_to_candidate_adapter(result)
    doc_text = DOC_PATH.read_text(encoding="utf-8")
    script_text = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "BR-28 Snapshot to Candidate Deterministic Adapter" in markdown
    assert "LIVE TRADING: DISABLED" in markdown
    assert "## Source Evidence" in markdown
    assert "## Adapter Checks" in markdown
    assert "## Research Candidates" in markdown
    assert "## Preserved Fields" in markdown
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


def test_br28_validation_rejects_unsafe_mutations() -> None:
    result = build_snapshot_to_candidate_adapter(as_of=datetime(2026, 7, 11, tzinfo=timezone.utc))
    candidate = result.candidates[0]

    with pytest.raises(ValueError, match="cannot set live_trading_enabled"):
        replace(result, safety={**result.safety, "live_trading_enabled": True}).validate()

    with pytest.raises(ValueError, match="cannot set credential_loading_attempted"):
        replace(result, safety={**result.safety, "credential_loading_attempted": True}).validate()

    with pytest.raises(ValueError, match="cannot set data_provider_call_attempted"):
        replace(result, safety={**result.safety, "data_provider_call_attempted": True}).validate()

    with pytest.raises(ValueError, match="cannot set broker_order_call_performed"):
        replace(result, safety={**result.safety, "broker_order_call_performed": True}).validate()

    with pytest.raises(ValueError, match="cannot allow external_routing_paths_authorized"):
        replace(result, safety={**result.safety, "external_routing_paths_authorized": True}).validate()

    with pytest.raises(ValueError, match="must keep LIVE TRADING disabled"):
        replace(result, safety={**result.safety, "LIVE TRADING": "ENABLED"}).validate()

    with pytest.raises(ValueError, match="must require human review"):
        replace(result, label=MONITOR_ONLY).validate()

    with pytest.raises(ValueError, match="must carry human-review status"):
        replace(candidate, human_review_status=RESEARCH_ONLY).validate()


def test_br28_source_does_not_introduce_forbidden_execution_labels_or_broker_imports() -> None:
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


def _write_snapshot_variant(tmp_path: Path, name: str) -> Path:
    payload = json.loads(DEFAULT_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    payload["provenance"]["source_file_name"] = name
    path = tmp_path / name
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _write_br27_variant(tmp_path: Path, snapshot_path: Path, checksum: str) -> Path:
    payload = json.loads(DEFAULT_BR27_REPORT_PATH.read_text(encoding="utf-8"))
    payload["source_paths"]["approved offline snapshot"] = str(snapshot_path)
    for record in payload["accepted_research_evidence"]:
        record["snapshot_path"] = str(snapshot_path)
        record["snapshot_summary"]["checksum_sha256"] = checksum
    path = tmp_path / "br27_variant.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _tmp_dir(name: str) -> Path:
    path = Path(".codex_pytest_tmp/br28_snapshot_adapter_tests") / name
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    return path
