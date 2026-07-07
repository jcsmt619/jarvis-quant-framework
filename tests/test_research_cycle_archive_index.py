from __future__ import annotations

import json
import shutil
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from core.research_cycle_archive_index import (
    ARCHIVE_INDEX_BLOCKED_BY_SAFETY_GATE,
    ARCHIVE_INDEX_NEEDS_HUMAN_REVIEW,
    ResearchCycleArchiveIndexInput,
    build_default_research_cycle_archive_index_input,
    build_research_cycle_archive_index_payload,
    render_research_cycle_archive_index_markdown,
    write_research_cycle_archive_index,
)
from risk.policies import BLOCKED_BY_SAFETY_GATE, HUMAN_REVIEW_REQUIRED, MONITOR_ONLY, RESEARCH_ONLY


FIXED_NOW = datetime(2026, 7, 7, 23, 0, 0, tzinfo=UTC)


def _root() -> Path:
    return Path("reports/research_cycle_archive_index_tests") / uuid.uuid4().hex


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _artifact_payload(
    phase: str,
    workflow: str,
    date_key: str,
    *,
    day: str = "2026-07-07",
    label: str = HUMAN_REVIEW_REQUIRED,
) -> dict[str, object]:
    return {
        "phase": phase,
        "workflow": workflow,
        date_key: day,
        "generated_at_utc": f"{day}T22:00:00+00:00",
        "safety_boundary": {
            "label": label,
            "research_only": True,
            "monitor_only": True,
            "paper_only": True,
            "human_review_required": True,
            "real_paper_wrapper_connected": False,
            "real_paper_wrapper_attempted": False,
            "real_paper_order_submitted": False,
            "broker_order_call_performed": False,
            "broker_order_routing_enabled": False,
            "broker_routing_used": False,
            "broker_call_used": False,
            "order_execution_used": False,
            "live_trading_enabled": False,
            "live_trading_approval_granted": False,
            "secrets_required": False,
            "credential_file_used": False,
            "prohibited_trade_labels_present": False,
            "status": "LIVE TRADING: DISABLED",
        },
        "summary": {
            "artifact_count": 0,
            "completed_item_count": 0,
            "open_item_count": 0,
            "blocked_item_count": 0,
            "missing_artifact_count": 0,
        },
    }


def _archive_input(root: Path) -> ResearchCycleArchiveIndexInput:
    return ResearchCycleArchiveIndexInput(
        archive_index_id="23B-RESEARCH-CYCLE-ARCHIVE-INDEX-2026-07-07",
        archive_index_date="2026-07-07",
        generated_at_utc=FIXED_NOW.isoformat(),
        operations_console_path=root / "research_operations_console" / "research_operations_console.json",
        operator_signoff_packet_path=root / "operator_signoff_packet" / "operator_signoff_packet.json",
        closeout_gate_path=root / "human_review_closeout_gate" / "human_review_closeout_gate.json",
        operator_acknowledgment_ledger_path=root / "operator_acknowledgment_ledger" / "operator_acknowledgment_ledger.json",
        human_review_queue_path=root / "human_review_queue" / "human_review_queue.json",
        readiness_gate_path=root / "research_cycle_readiness_gate" / "research_cycle_readiness_gate.json",
        retention_policy_path=root / "research_artifact_retention_policy" / "research_artifact_retention_policy.json",
        audit_summary_path=root / "research_cycle_audit_summary" / "research_cycle_audit_summary.json",
        manifest_path=root / "research_cycle_runner" / "research_cycle_manifest.json",
        release_bundle_path=root / "research_release_bundle" / "research_release_bundle.json",
        operator_dashboard_snapshot_path=root / "operator_dashboard_snapshot" / "operator_dashboard_snapshot.json",
        report_index_path=root / "report_index" / "report_index.json",
        safe_workflow_catalog_path=root / "safe_workflow_catalog" / "safe_workflow_catalog.json",
        queue_status_path=root / "queue.json",
    )


def _write_ready_inputs(root: Path) -> ResearchCycleArchiveIndexInput:
    archive_input = _archive_input(root)
    payloads = {
        archive_input.operations_console_path: {
            **_artifact_payload("23A", "Research Operations Console", "console_date"),
            "console_state": "OPERATIONS_CONSOLE_COMPLETE_RECORDS_ONLY",
            "final_console_summary": "Research operations console complete.",
            "required_operator_actions": [
                {
                    "action_id": "23A-REVIEW-OPERATIONS-CONSOLE",
                    "label": HUMAN_REVIEW_REQUIRED,
                    "status": "open_review_item",
                    "summary": "Review console.",
                }
            ],
        },
        archive_input.operator_signoff_packet_path: {
            **_artifact_payload("22B", "Operator Signoff Packet", "signoff_date"),
            "signoff_state": "SIGNOFF_PACKET_COMPLETE_RECORDS_ONLY",
            "final_signoff_summary": "Operator signoff packet complete.",
        },
        archive_input.closeout_gate_path: {
            **_artifact_payload("22A", "Human Review Closeout Gate", "closeout_date"),
            "closeout_state": "CLOSED_FOR_RECORDS_ONLY",
            "required_next_human_review_actions": [],
        },
        archive_input.operator_acknowledgment_ledger_path: {
            **_artifact_payload("21B", "Operator Acknowledgment Ledger", "ledger_date"),
            "ledger_state": "OPEN_OPERATOR_ACKNOWLEDGMENT_LEDGER",
            "ledger_entries": [],
        },
        archive_input.human_review_queue_path: {
            **_artifact_payload("21A", "Human Review Queue", "review_date"),
            "queue_state": "OPEN_HUMAN_REVIEW_QUEUE",
            "next_operator_actions": [],
        },
        archive_input.readiness_gate_path: _artifact_payload("20A", "Research Cycle Readiness Gate", "gate_date"),
        archive_input.retention_policy_path: {
            **_artifact_payload("20B", "Research Artifact Retention Policy", "retention_date"),
            "artifacts": [
                {
                    "artifact_id": "report_index",
                    "label": RESEARCH_ONLY,
                    "retention_action": "archive_candidate",
                    "retention_reasons": ["artifact age exceeds threshold"],
                    "automatic_delete_allowed": False,
                    "dry_run_only": True,
                },
                {
                    "artifact_id": "safe_workflow_catalog",
                    "label": BLOCKED_BY_SAFETY_GATE,
                    "retention_action": "blocked_delete",
                    "retention_reasons": ["blocked safety label"],
                    "automatic_delete_allowed": False,
                    "dry_run_only": True,
                },
            ],
            "dry_run_manifest": [],
        },
        archive_input.audit_summary_path: _artifact_payload("19B", "Research Cycle Audit Summary", "audit_date"),
        archive_input.manifest_path: _artifact_payload("19A", "Research Cycle Manifest", "cycle_date"),
        archive_input.release_bundle_path: _artifact_payload("18B", "Research Release Bundle", "bundle_date"),
        archive_input.operator_dashboard_snapshot_path: _artifact_payload(
            "17B",
            "Operator Dashboard Snapshot",
            "snapshot_date",
            label=MONITOR_ONLY,
        ),
        archive_input.report_index_path: _artifact_payload("17A", "Report Index", "index_date", label=RESEARCH_ONLY),
        archive_input.safe_workflow_catalog_path: _artifact_payload(
            "18A",
            "Safe Workflow Catalog",
            "catalog_date",
            label=MONITOR_ONLY,
        ),
    }
    for path, payload in payloads.items():
        _write_json(path, payload)
    _write_json(
        archive_input.queue_status_path,
        [
            {
                "phase": "23B",
                "title": "Research Cycle Archive Index",
                "spec": "Build deterministic archive index.",
            }
        ],
    )
    return archive_input


def test_23b_builds_deterministic_read_only_archive_index() -> None:
    root = _root()
    try:
        archive_input = _write_ready_inputs(root)

        first = build_research_cycle_archive_index_payload(archive_input)
        second = build_research_cycle_archive_index_payload(archive_input)

        assert first == second
        assert first["phase"] == "23B"
        assert first["workflow"] == "Research Cycle Archive Index"
        assert first["archive_index_state"] == ARCHIVE_INDEX_NEEDS_HUMAN_REVIEW
        assert first["summary"]["source_artifact_count"] == 13
        assert first["summary"]["present_source_artifact_count"] == 13
        assert first["summary"]["archive_eligible_count"] == 1
        assert first["summary"]["blocked_delete_count"] == 1
        assert first["summary"]["dry_run_archive_manifest_count"] == 2
        assert first["safety_boundary"]["archive_index_read_only"] is True
        assert first["safety_boundary"]["dry_run_only"] is True
        assert first["safety_boundary"]["artifact_delete_performed"] is False
        assert first["safety_boundary"]["artifact_move_performed"] is False
        assert first["safety_boundary"]["artifact_rename_performed"] is False
        assert first["safety_boundary"]["artifact_compression_performed"] is False
        assert first["safety_boundary"]["artifact_mutation_performed"] is False
        assert first["safety_boundary"]["broker_order_call_performed"] is False
        assert first["safety_boundary"]["broker_order_routing_enabled"] is False
        assert first["safety_boundary"]["live_trading_enabled"] is False
        assert first["safety_boundary"]["status"] == "LIVE TRADING: DISABLED"
        by_id = {item["artifact_id"]: item for item in first["indexed_artifacts"]}
        assert by_id["report_index"]["archive_eligible"] is True
        assert by_id["safe_workflow_catalog"]["blocked_delete"] is True
        required_index_fields = {
            "artifact_id",
            "artifact_name",
            "source_artifact_path",
            "artifact_status",
            "label",
            "generated_date",
            "generated_at_utc",
            "signoff_state",
            "retention_action",
            "archive_eligible",
            "blocked_delete",
            "human_review_notes",
        }
        assert all(required_index_fields <= set(item) for item in first["indexed_artifacts"])
        assert all("payload" not in item for item in first["source_artifacts"])
        assert all(item["dry_run_only"] is True for item in first["dry_run_archive_manifest"])
        assert all(item["automatic_delete_allowed"] is False for item in first["dry_run_archive_manifest"])
        assert {
            item["artifact_id"] for item in first["dry_run_archive_manifest"]
        } == {"report_index", "safe_workflow_catalog"}
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_23b_writes_json_and_markdown_archive_index() -> None:
    root = _root()
    out_dir = root / "out"
    try:
        json_path, markdown_path = write_research_cycle_archive_index(
            _write_ready_inputs(root),
            out_dir=out_dir,
        )

        payload = json.loads(json_path.read_text(encoding="utf-8"))
        markdown = markdown_path.read_text(encoding="utf-8")

        assert json_path.name == "research_cycle_archive_index.json"
        assert markdown_path.name == "research_cycle_archive_index.md"
        assert payload["archive_index_id"] == "23B-RESEARCH-CYCLE-ARCHIVE-INDEX-2026-07-07"
        assert "23B Research Cycle Archive Index" in markdown
        assert "Dry-Run Archive Manifest" in markdown
        assert "Human-Review Notes" in markdown
        assert "No artifacts are deleted, moved, renamed, compressed, or mutated" in markdown
        assert "LIVE TRADING: DISABLED" in markdown
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_23b_classifies_missing_artifacts_as_blocked_delete() -> None:
    root = _root()
    try:
        archive_input = _write_ready_inputs(root)
        archive_input.report_index_path.unlink()

        payload = build_research_cycle_archive_index_payload(archive_input)

        assert payload["archive_index_state"] == ARCHIVE_INDEX_BLOCKED_BY_SAFETY_GATE
        report_index = {
            item["artifact_id"]: item
            for item in payload["indexed_artifacts"]
        }["report_index"]
        assert report_index["artifact_status"] == "missing"
        assert report_index["retention_action"] == "blocked_delete"
        assert report_index["blocked_delete"] is True
        assert "23B-BLOCKED-DELETE-report_index" in {
            item["note_id"] for item in payload["human_review_notes"]
        }
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_23b_rejects_secret_paths_unsafe_labels_and_execution_flags() -> None:
    root = _root()
    try:
        with pytest.raises(ValueError, match="secret files"):
            ResearchCycleArchiveIndexInput(
                archive_index_id="23B-UNSAFE",
                archive_index_date="2026-07-07",
                generated_at_utc=FIXED_NOW.isoformat(),
                operations_console_path=Path(".env"),
            ).validate()

        archive_input = _write_ready_inputs(root)
        console = json.loads(archive_input.operations_console_path.read_text(encoding="utf-8"))
        console["label"] = "AUTO" + "_TRADE"
        _write_json(archive_input.operations_console_path, console)
        with pytest.raises(ValueError, match="unsafe research cycle archive index label"):
            build_research_cycle_archive_index_payload(archive_input)

        console["label"] = HUMAN_REVIEW_REQUIRED
        console["broker_order_call_" + "performed"] = True
        _write_json(archive_input.operations_console_path, console)
        with pytest.raises(ValueError, match="broker_order_call_performed"):
            build_research_cycle_archive_index_payload(archive_input)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_23b_default_input_uses_phase_archive_index_id() -> None:
    archive_input = build_default_research_cycle_archive_index_input(now=FIXED_NOW)

    assert archive_input.archive_index_id == "23B-RESEARCH-CYCLE-ARCHIVE-INDEX-2026-07-07"
    assert archive_input.archive_index_date == "2026-07-07"


def test_23b_cli_writes_research_cycle_archive_index() -> None:
    root = _root()
    out_dir = root / "out"
    try:
        archive_input = _write_ready_inputs(root)
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/run_research_cycle_archive_index.py",
                "--out-dir",
                str(out_dir),
                "--archive-index-date",
                "2026-07-07",
                "--operations-console-path",
                str(archive_input.operations_console_path),
                "--operator-signoff-packet-path",
                str(archive_input.operator_signoff_packet_path),
                "--closeout-gate-path",
                str(archive_input.closeout_gate_path),
                "--operator-acknowledgment-ledger-path",
                str(archive_input.operator_acknowledgment_ledger_path),
                "--human-review-queue-path",
                str(archive_input.human_review_queue_path),
                "--readiness-gate-path",
                str(archive_input.readiness_gate_path),
                "--retention-policy-path",
                str(archive_input.retention_policy_path),
                "--audit-summary-path",
                str(archive_input.audit_summary_path),
                "--manifest-path",
                str(archive_input.manifest_path),
                "--release-bundle-path",
                str(archive_input.release_bundle_path),
                "--operator-dashboard-snapshot-path",
                str(archive_input.operator_dashboard_snapshot_path),
                "--report-index-path",
                str(archive_input.report_index_path),
                "--safe-workflow-catalog-path",
                str(archive_input.safe_workflow_catalog_path),
                "--queue-status-path",
                str(archive_input.queue_status_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        assert completed.returncode == 0
        assert "JARVIS 23B RESEARCH CYCLE ARCHIVE INDEX: COMPLETE" in completed.stdout
        assert "Archive index is read-only and dry-run only" in completed.stdout
        assert "No artifacts are deleted, moved, renamed, compressed, or mutated" in completed.stdout
        assert "LIVE TRADING: DISABLED" in completed.stdout
        assert (out_dir / "research_cycle_archive_index.json").exists()
        assert (out_dir / "research_cycle_archive_index.md").exists()
    finally:
        shutil.rmtree(root, ignore_errors=True)
