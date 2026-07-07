from __future__ import annotations

import json
import shutil
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from core.research_cycle_rollover_gate import (
    BLOCKED_BY_SAFETY_GATE,
    NEEDS_OPERATOR_REVIEW,
    ROLLOVER_READY_FOR_HUMAN_REVIEW,
    ResearchCycleRolloverGateInput,
    build_default_research_cycle_rollover_gate_input,
    build_research_cycle_rollover_gate_payload,
    render_research_cycle_rollover_gate_markdown,
    write_research_cycle_rollover_gate,
)
from risk.policies import HUMAN_REVIEW_REQUIRED, MONITOR_ONLY, RESEARCH_ONLY


FIXED_NOW = datetime(2026, 7, 7, 23, 30, 0, tzinfo=UTC)


def _root() -> Path:
    return Path("reports/research_cycle_rollover_gate_tests") / uuid.uuid4().hex


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
        "generated_at_utc": f"{day}T23:00:00+00:00",
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


def _rollover_input(root: Path) -> ResearchCycleRolloverGateInput:
    return ResearchCycleRolloverGateInput(
        rollover_gate_id="24A-RESEARCH-CYCLE-ROLLOVER-GATE-2026-07-07",
        rollover_gate_date="2026-07-07",
        generated_at_utc=FIXED_NOW.isoformat(),
        archive_index_path=root / "research_cycle_archive_index" / "research_cycle_archive_index.json",
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
        report_index_path=root / "report_index" / "report_index.json",
        safe_workflow_catalog_path=root / "safe_workflow_catalog" / "safe_workflow_catalog.json",
        queue_status_path=root / "queue.json",
        safety_scanner_path=root / "safety_scanner" / "safety_scanner_status.json",
    )


def _archive_index_payload(*, state: str = "ARCHIVE_INDEX_COMPLETE_RECORDS_ONLY") -> dict[str, object]:
    return {
        **_artifact_payload("23B", "Research Cycle Archive Index", "archive_index_date"),
        "archive_index_state": state,
        "indexed_artifacts": [
            {
                "artifact_id": "report_index",
                "label": RESEARCH_ONLY,
                "artifact_status": "present",
                "retention_action": "keep",
                "archive_eligible": False,
                "blocked_delete": False,
                "summary": "Report index recorded.",
            }
        ],
        "dry_run_archive_manifest": [],
        "human_review_notes": [],
    }


def _write_ready_inputs(root: Path) -> ResearchCycleRolloverGateInput:
    rollover_input = _rollover_input(root)
    payloads = {
        rollover_input.archive_index_path: _archive_index_payload(),
        rollover_input.operations_console_path: {
            **_artifact_payload("23A", "Research Operations Console", "console_date"),
            "console_state": "OPERATIONS_CONSOLE_COMPLETE_RECORDS_ONLY",
            "required_operator_actions": [],
            "safety_findings": [],
        },
        rollover_input.operator_signoff_packet_path: {
            **_artifact_payload("22B", "Operator Signoff Packet", "signoff_date"),
            "signoff_state": "SIGNOFF_PACKET_COMPLETE_RECORDS_ONLY",
        },
        rollover_input.closeout_gate_path: {
            **_artifact_payload("22A", "Human Review Closeout Gate", "closeout_date"),
            "closeout_state": "CLOSED_FOR_RECORDS_ONLY",
            "required_next_human_review_actions": [],
        },
        rollover_input.operator_acknowledgment_ledger_path: {
            **_artifact_payload("21B", "Operator Acknowledgment Ledger", "ledger_date"),
            "ledger_state": "OPEN_OPERATOR_ACKNOWLEDGMENT_LEDGER",
            "ledger_entries": [],
        },
        rollover_input.human_review_queue_path: {
            **_artifact_payload("21A", "Human Review Queue", "review_date"),
            "queue_state": "OPEN_HUMAN_REVIEW_QUEUE",
            "next_operator_actions": [],
        },
        rollover_input.readiness_gate_path: _artifact_payload("20A", "Research Cycle Readiness Gate", "gate_date"),
        rollover_input.retention_policy_path: {
            **_artifact_payload("20B", "Research Artifact Retention Policy", "retention_date"),
            "artifacts": [
                {
                    "artifact_id": "report_index",
                    "label": RESEARCH_ONLY,
                    "retention_action": "keep",
                    "retention_reasons": ["protected report type"],
                    "automatic_delete_allowed": False,
                    "dry_run_only": True,
                }
            ],
            "dry_run_manifest": [],
        },
        rollover_input.audit_summary_path: _artifact_payload("19B", "Research Cycle Audit Summary", "audit_date"),
        rollover_input.manifest_path: _artifact_payload("19A", "Research Cycle Manifest", "cycle_date"),
        rollover_input.release_bundle_path: _artifact_payload("18B", "Research Release Bundle", "bundle_date"),
        rollover_input.report_index_path: _artifact_payload("17A", "Report Index", "index_date", label=RESEARCH_ONLY),
        rollover_input.safe_workflow_catalog_path: _artifact_payload(
            "18A",
            "Safe Workflow Catalog",
            "catalog_date",
            label=MONITOR_ONLY,
        ),
        rollover_input.safety_scanner_path: {
            "workflow_id": "safety_scanner",
            "label": HUMAN_REVIEW_REQUIRED,
            "status": "passed",
            "summary": "Safety scanner passed.",
            "passed": True,
            "finding_count": 0,
            "findings": [],
            "generated_at_utc": FIXED_NOW.isoformat(),
        },
    }
    for path, payload in payloads.items():
        _write_json(path, payload)
    _write_json(
        rollover_input.queue_status_path,
        [
            {
                "phase": "24A",
                "title": "Research Cycle Rollover Gate",
                "spec": "Build deterministic rollover gate.",
            }
        ],
    )
    return rollover_input


def test_24a_builds_deterministic_ready_rollover_gate() -> None:
    root = _root()
    try:
        rollover_input = _write_ready_inputs(root)

        first = build_research_cycle_rollover_gate_payload(rollover_input)
        second = build_research_cycle_rollover_gate_payload(rollover_input)

        assert first == second
        assert first["phase"] == "24A"
        assert first["workflow"] == "Research Cycle Rollover Gate"
        assert first["rollover_state"] == ROLLOVER_READY_FOR_HUMAN_REVIEW
        assert first["summary"]["source_artifact_count"] == 14
        assert first["summary"]["missing_artifact_count"] == 0
        assert first["summary"]["stale_artifact_count"] == 0
        assert first["summary"]["unresolved_item_count"] == 0
        assert first["summary"]["archive_index_finding_count"] == 0
        assert first["summary"]["retention_item_count"] == 0
        assert first["summary"]["required_operator_action_count"] == 1
        assert first["required_operator_actions"][0]["action_id"] == "24A-REVIEW-ROLLOVER-GATE"
        assert first["safety_boundary"]["rollover_gate_read_only"] is True
        assert first["safety_boundary"]["records_only"] is True
        assert first["safety_boundary"]["trade_instructions_created"] is False
        assert first["safety_boundary"]["broker_actions_created"] is False
        assert first["safety_boundary"]["execution_permissions_created"] is False
        assert first["safety_boundary"]["automatic_action_enabled"] is False
        assert first["safety_boundary"]["broker_order_call_performed"] is False
        assert first["safety_boundary"]["broker_order_routing_enabled"] is False
        assert first["safety_boundary"]["live_trading_enabled"] is False
        assert first["safety_boundary"]["status"] == "LIVE TRADING: DISABLED"
        assert all("payload" not in item for item in first["source_artifacts"])
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_24a_writes_json_and_markdown_rollover_gate() -> None:
    root = _root()
    out_dir = root / "out"
    try:
        json_path, markdown_path = write_research_cycle_rollover_gate(
            _write_ready_inputs(root),
            out_dir=out_dir,
        )

        payload = json.loads(json_path.read_text(encoding="utf-8"))
        markdown = markdown_path.read_text(encoding="utf-8")

        assert json_path.name == "research_cycle_rollover_gate.json"
        assert markdown_path.name == "research_cycle_rollover_gate.md"
        assert payload["rollover_gate_id"] == "24A-RESEARCH-CYCLE-ROLLOVER-GATE-2026-07-07"
        assert "24A Research Cycle Rollover Gate" in markdown
        assert "Required Operator Actions Before Next Cycle" in markdown
        assert "Archive-Index Findings" in markdown
        assert "read-only and records-only" in markdown
        assert "LIVE TRADING: DISABLED" in markdown
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_24a_classifies_operator_review_for_open_stale_archive_and_retention_items() -> None:
    root = _root()
    try:
        rollover_input = _write_ready_inputs(root)
        archive = _archive_index_payload(state="ARCHIVE_INDEX_NEEDS_HUMAN_REVIEW")
        archive["indexed_artifacts"] = [
            {
                "artifact_id": "old_report",
                "label": RESEARCH_ONLY,
                "artifact_status": "present",
                "retention_action": "archive_candidate",
                "archive_eligible": True,
                "blocked_delete": False,
                "summary": "Archive candidate.",
            }
        ]
        _write_json(rollover_input.archive_index_path, archive)
        console = json.loads(rollover_input.operations_console_path.read_text(encoding="utf-8"))
        console["open_items"] = [
            {
                "item_id": "pending_cycle_note",
                "label": HUMAN_REVIEW_REQUIRED,
                "status": "open_review_item",
                "summary": "Pending cycle note.",
            }
        ]
        _write_json(rollover_input.operations_console_path, console)
        stale = _artifact_payload("19B", "Research Cycle Audit Summary", "audit_date", day="2026-07-01")
        _write_json(rollover_input.audit_summary_path, stale)

        payload = build_research_cycle_rollover_gate_payload(rollover_input)
        markdown = render_research_cycle_rollover_gate_markdown(payload)

        assert payload["rollover_state"] == NEEDS_OPERATOR_REVIEW
        assert "pending_cycle_note" in {item["item_id"] for item in payload["unresolved_items"]}
        assert "audit_summary" in {item["artifact_id"] for item in payload["stale_artifacts"]}
        assert "archive_index_old_report" in {item["finding_id"] for item in payload["archive_index_findings"]}
        assert "retention_archive_index_old_report" in {item["item_id"] for item in payload["retention_items"]}
        assert "24A-REVIEW-ARCHIVE-INDEX-FINDINGS" in {
            item["action_id"] for item in payload["required_operator_actions"]
        }
        assert NEEDS_OPERATOR_REVIEW in markdown
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_24a_classifies_blocked_for_missing_artifacts_and_safety_findings() -> None:
    root = _root()
    try:
        rollover_input = _write_ready_inputs(root)
        rollover_input.report_index_path.unlink()
        _write_json(
            rollover_input.safety_scanner_path,
            {
                "workflow_id": "safety_scanner",
                "label": BLOCKED_BY_SAFETY_GATE,
                "status": "blocked",
                "summary": "Safety scanner found a blocked condition.",
                "passed": False,
                "finding_count": 1,
                "findings": [{"rule_id": "blocked_scanner_fixture", "summary": "Scanner fixture."}],
                "generated_at_utc": FIXED_NOW.isoformat(),
            },
        )

        payload = build_research_cycle_rollover_gate_payload(rollover_input)

        assert payload["rollover_state"] == BLOCKED_BY_SAFETY_GATE
        assert "report_index" in {item["artifact_id"] for item in payload["missing_artifacts"]}
        assert "blocked_scanner_fixture" in {item["finding_id"] for item in payload["safety_findings"]}
        assert "24A-RESOLVE-SAFETY-FINDINGS" in {
            item["action_id"] for item in payload["required_operator_actions"]
        }
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_24a_rejects_secret_paths_unsafe_labels_and_execution_flags() -> None:
    root = _root()
    try:
        with pytest.raises(ValueError, match="secret files"):
            ResearchCycleRolloverGateInput(
                rollover_gate_id="24A-UNSAFE",
                rollover_gate_date="2026-07-07",
                generated_at_utc=FIXED_NOW.isoformat(),
                archive_index_path=Path(".env"),
            ).validate()

        rollover_input = _write_ready_inputs(root)
        archive = json.loads(rollover_input.archive_index_path.read_text(encoding="utf-8"))
        archive["label"] = "AUTO" + "_TRADE"
        _write_json(rollover_input.archive_index_path, archive)
        with pytest.raises(ValueError, match="unsafe research cycle rollover gate label"):
            build_research_cycle_rollover_gate_payload(rollover_input)

        archive["label"] = HUMAN_REVIEW_REQUIRED
        archive["broker_order_call_" + "performed"] = True
        _write_json(rollover_input.archive_index_path, archive)
        with pytest.raises(ValueError, match="broker_order_call_performed"):
            build_research_cycle_rollover_gate_payload(rollover_input)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_24a_default_input_uses_phase_rollover_gate_id() -> None:
    rollover_input = build_default_research_cycle_rollover_gate_input(now=FIXED_NOW)

    assert rollover_input.rollover_gate_id == "24A-RESEARCH-CYCLE-ROLLOVER-GATE-2026-07-07"
    assert rollover_input.rollover_gate_date == "2026-07-07"


def test_24a_cli_writes_research_cycle_rollover_gate() -> None:
    root = _root()
    out_dir = root / "out"
    try:
        rollover_input = _write_ready_inputs(root)
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/run_research_cycle_rollover_gate.py",
                "--out-dir",
                str(out_dir),
                "--rollover-gate-date",
                "2026-07-07",
                "--archive-index-path",
                str(rollover_input.archive_index_path),
                "--operations-console-path",
                str(rollover_input.operations_console_path),
                "--operator-signoff-packet-path",
                str(rollover_input.operator_signoff_packet_path),
                "--closeout-gate-path",
                str(rollover_input.closeout_gate_path),
                "--operator-acknowledgment-ledger-path",
                str(rollover_input.operator_acknowledgment_ledger_path),
                "--human-review-queue-path",
                str(rollover_input.human_review_queue_path),
                "--readiness-gate-path",
                str(rollover_input.readiness_gate_path),
                "--retention-policy-path",
                str(rollover_input.retention_policy_path),
                "--audit-summary-path",
                str(rollover_input.audit_summary_path),
                "--manifest-path",
                str(rollover_input.manifest_path),
                "--release-bundle-path",
                str(rollover_input.release_bundle_path),
                "--report-index-path",
                str(rollover_input.report_index_path),
                "--safe-workflow-catalog-path",
                str(rollover_input.safe_workflow_catalog_path),
                "--queue-status-path",
                str(rollover_input.queue_status_path),
                "--safety-scanner-path",
                str(rollover_input.safety_scanner_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        assert completed.returncode == 0
        assert "JARVIS 24A RESEARCH CYCLE ROLLOVER GATE: COMPLETE" in completed.stdout
        assert "Rollover gate is read-only and records-only" in completed.stdout
        assert "No trade instructions, broker actions, live-trading approvals, automatic actions, or execution permissions are created" in completed.stdout
        assert "LIVE TRADING: DISABLED" in completed.stdout
        assert (out_dir / "research_cycle_rollover_gate.json").exists()
        assert (out_dir / "research_cycle_rollover_gate.md").exists()
    finally:
        shutil.rmtree(root, ignore_errors=True)
