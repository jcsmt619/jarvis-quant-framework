from __future__ import annotations

import json
import shutil
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from core.human_review_closeout_gate import (
    CLOSED_FOR_RECORDS_ONLY,
    NEEDS_OPERATOR_REVIEW,
    HumanReviewCloseoutGateInput,
    build_default_human_review_closeout_gate_input,
    build_human_review_closeout_gate_payload,
    render_human_review_closeout_gate_markdown,
    write_human_review_closeout_gate,
)
from risk.policies import BLOCKED_BY_SAFETY_GATE, HUMAN_REVIEW_REQUIRED, MONITOR_ONLY


FIXED_NOW = datetime(2026, 7, 7, 21, 0, 0, tzinfo=UTC)


def _root() -> Path:
    return Path("reports/human_review_closeout_gate_tests") / uuid.uuid4().hex


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
        "generated_at_utc": f"{day}T20:00:00+00:00",
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
            "missing_artifact_count": 0,
            "stale_artifact_count": 0,
            "blocked_workflow_count": 0,
            "safety_finding_count": 0,
        },
    }


def _closeout_input(root: Path) -> HumanReviewCloseoutGateInput:
    return HumanReviewCloseoutGateInput(
        closeout_id="22A-HUMAN-REVIEW-CLOSEOUT-GATE-2026-07-07",
        closeout_date="2026-07-07",
        generated_at_utc=FIXED_NOW.isoformat(),
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
        safety_scanner_path=root / "safety_scanner" / "safety_scanner_status.json",
    )


def _queue_payload() -> dict[str, object]:
    return {
        **_artifact_payload("21A", "Human Review Queue", "review_date"),
        "queue_id": "21A-HUMAN-REVIEW-QUEUE-2026-07-07",
        "queue_state": "OPEN_HUMAN_REVIEW_QUEUE",
        "required_human_review_items": [
            {
                "review_item_id": "20A-REVIEW-READINESS-GATE",
                "workflow_id": "review_readiness_gate",
                "label": HUMAN_REVIEW_REQUIRED,
                "status": "open_review_item",
                "summary": "Review 20A readiness gate.",
            }
        ],
        "missing_artifacts": [],
        "stale_artifacts": [],
        "skipped_steps": [],
        "blocked_workflows": [
            {
                "workflow_id": "live_trading",
                "label": BLOCKED_BY_SAFETY_GATE,
                "status": "blocked",
                "summary": "Live trading remains disabled.",
            }
        ],
        "safety_findings": [],
        "retention_review_items": [],
        "next_operator_actions": [],
    }


def _ledger_payload(*, extra_entry: dict[str, object] | None = None) -> dict[str, object]:
    entries = [
        {
            "ledger_entry_id": "21B-20A-REVIEW-READINESS-GATE",
            "review_item_id": "20A-REVIEW-READINESS-GATE",
            "review_status": "ACKNOWLEDGED",
            "label": HUMAN_REVIEW_REQUIRED,
            "source_section": "required_human_review_items",
            "summary": "Review 20A readiness gate.",
            "workflow_id": "review_readiness_gate",
            "acknowledged_at_utc": "2026-07-07T20:30:00+00:00",
            "automatic_action_enabled": False,
            "acknowledgment_enables_live_trading": False,
            "broker_order_call_performed": False,
            "broker_order_routing_enabled": False,
            "broker_routing_used": False,
            "broker_call_used": False,
            "order_execution_used": False,
            "live_trading_enabled": False,
            "live_trading_approval_granted": False,
        },
        {
            "ledger_entry_id": "21B-live_trading",
            "review_item_id": "live_trading",
            "review_status": "NOTED",
            "label": BLOCKED_BY_SAFETY_GATE,
            "source_section": "blocked_workflows",
            "summary": "Live trading remains disabled.",
            "workflow_id": "live_trading",
            "blocked_workflow_reference": "live_trading",
            "acknowledged_at_utc": "2026-07-07T20:31:00+00:00",
            "automatic_action_enabled": False,
            "acknowledgment_enables_live_trading": False,
            "broker_order_call_performed": False,
            "broker_order_routing_enabled": False,
            "broker_routing_used": False,
            "broker_call_used": False,
            "order_execution_used": False,
            "live_trading_enabled": False,
            "live_trading_approval_granted": False,
        },
    ]
    if extra_entry is not None:
        entries.append(extra_entry)
    return {
        **_artifact_payload("21B", "Operator Acknowledgment Ledger", "ledger_date"),
        "ledger_id": "21B-OPERATOR-ACKNOWLEDGMENT-LEDGER-2026-07-07",
        "ledger_state": "OPEN_OPERATOR_ACKNOWLEDGMENT_LEDGER",
        "ledger_entries": entries,
        "blocked_workflow_references": [
            {
                "review_item_id": "live_trading",
                "workflow_id": "live_trading",
                "label": BLOCKED_BY_SAFETY_GATE,
                "review_status": "NOTED",
                "status": "blocked",
                "summary": "Blocked workflow remains blocked.",
                "automatic_action_enabled": False,
            }
        ],
        "unmatched_acknowledgments": [],
    }


def _write_ready_inputs(root: Path) -> HumanReviewCloseoutGateInput:
    closeout_input = _closeout_input(root)
    payloads = {
        closeout_input.operator_acknowledgment_ledger_path: _ledger_payload(),
        closeout_input.human_review_queue_path: _queue_payload(),
        closeout_input.readiness_gate_path: {
            **_artifact_payload("20A", "Research Cycle Readiness Gate", "gate_date"),
            "decision": "READY_FOR_HUMAN_REVIEW",
            "missing_artifacts": [],
            "stale_reports": [],
            "blocked_workflows": [],
            "failed_safety_findings": [],
        },
        closeout_input.retention_policy_path: {
            **_artifact_payload("20B", "Research Artifact Retention Policy", "retention_date"),
            "artifacts": [],
            "blocked_workflows": [],
        },
        closeout_input.audit_summary_path: {
            **_artifact_payload("19B", "Research Cycle Audit Summary", "audit_date"),
            "human_review_notes": [],
            "blocked_workflows": [],
            "missing_artifacts": [],
            "skipped_steps": [],
        },
        closeout_input.manifest_path: {
            **_artifact_payload("19A", "Research Cycle Runner", "cycle_date"),
            "missing_artifacts": [],
            "skipped_steps": [],
            "blocked_workflows": [],
        },
        closeout_input.release_bundle_path: _artifact_payload("18B", "Research Release Bundle", "bundle_date"),
        closeout_input.operator_dashboard_snapshot_path: _artifact_payload(
            "17B",
            "Operator Dashboard Snapshot",
            "snapshot_date",
        ),
        closeout_input.report_index_path: _artifact_payload("17A", "Report Index", "index_date"),
        closeout_input.safe_workflow_catalog_path: {
            **_artifact_payload("18A", "Safe Workflow Catalog", "catalog_date", label=MONITOR_ONLY),
            "workflows": [{"workflow_id": "report_index"}],
            "blocked_behaviors": ["enable live trading"],
        },
        closeout_input.safety_scanner_path: {
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
        closeout_input.queue_status_path,
        [
            {
                "phase": "22A",
                "title": "Human Review Closeout Gate",
                "spec": "Build deterministic closeout gate.",
            }
        ],
    )
    return closeout_input


def test_22a_builds_closed_records_only_closeout_gate() -> None:
    root = _root()
    try:
        closeout_input = _write_ready_inputs(root)

        first = build_human_review_closeout_gate_payload(closeout_input)
        second = build_human_review_closeout_gate_payload(closeout_input)

        assert first == second
        assert first["phase"] == "22A"
        assert first["workflow"] == "Human Review Closeout Gate"
        assert first["closeout_state"] == CLOSED_FOR_RECORDS_ONLY
        assert first["summary"]["source_artifact_count"] == 11
        assert first["summary"]["missing_artifact_count"] == 0
        assert first["summary"]["unresolved_review_item_count"] == 0
        assert first["summary"]["rejected_item_count"] == 0
        assert first["summary"]["deferred_item_count"] == 0
        assert first["summary"]["unmatched_acknowledgment_count"] == 0
        assert first["summary"]["non_baseline_blocked_workflow_count"] == 0
        assert first["safety_boundary"]["closeout_records_only"] is True
        assert first["safety_boundary"]["trade_instructions_created"] is False
        assert first["safety_boundary"]["broker_actions_created"] is False
        assert first["safety_boundary"]["execution_permissions_created"] is False
        assert first["safety_boundary"]["automatic_action_enabled"] is False
        assert first["safety_boundary"]["real_paper_wrapper_connected"] is False
        assert first["safety_boundary"]["real_paper_wrapper_attempted"] is False
        assert first["safety_boundary"]["real_paper_order_submitted"] is False
        assert first["safety_boundary"]["broker_order_call_performed"] is False
        assert first["safety_boundary"]["broker_order_routing_enabled"] is False
        assert first["safety_boundary"]["broker_routing_used"] is False
        assert first["safety_boundary"]["broker_call_used"] is False
        assert first["safety_boundary"]["order_execution_used"] is False
        assert first["safety_boundary"]["live_trading_enabled"] is False
        assert first["safety_boundary"]["live_trading_approval_granted"] is False
        assert first["safety_boundary"]["secrets_required"] is False
        assert first["safety_boundary"]["credential_file_used"] is False
        assert first["safety_boundary"]["prohibited_trade_labels_present"] is False
        assert first["safety_boundary"]["status"] == "LIVE TRADING: DISABLED"
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_22a_writes_json_and_markdown_closeout_gate() -> None:
    root = _root()
    out_dir = root / "out"
    try:
        json_path, markdown_path = write_human_review_closeout_gate(
            _write_ready_inputs(root),
            out_dir=out_dir,
        )

        payload = json.loads(json_path.read_text(encoding="utf-8"))
        markdown = markdown_path.read_text(encoding="utf-8")

        assert json_path.name == "human_review_closeout_gate.json"
        assert markdown_path.name == "human_review_closeout_gate.md"
        assert payload["closeout_id"] == "22A-HUMAN-REVIEW-CLOSEOUT-GATE-2026-07-07"
        assert "22A Human Review Closeout Gate" in markdown
        assert "Unresolved Review Items" in markdown
        assert "Required Next Human-Review Actions" in markdown
        assert "not trade instructions, broker actions" in markdown
        assert "LIVE TRADING: DISABLED" in markdown
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_22a_classifies_needs_operator_review_for_pending_rejected_deferred_and_unmatched() -> None:
    root = _root()
    try:
        closeout_input = _write_ready_inputs(root)
        ledger = _ledger_payload(
            extra_entry={
                "ledger_entry_id": "21B-retention_review",
                "review_item_id": "retention_review",
                "review_status": "DEFERRED",
                "label": HUMAN_REVIEW_REQUIRED,
                "source_section": "retention_review_items",
                "summary": "Retention review deferred.",
                "workflow_id": "retention_review",
                "automatic_action_enabled": False,
                "acknowledgment_enables_live_trading": False,
            }
        )
        ledger["ledger_state"] = NEEDS_OPERATOR_REVIEW
        ledger["ledger_entries"].append(
            {
                "ledger_entry_id": "21B-rejected_item",
                "review_item_id": "rejected_item",
                "review_status": "REJECTED",
                "label": HUMAN_REVIEW_REQUIRED,
                "source_section": "required_human_review_items",
                "summary": "Rejected review item.",
                "workflow_id": "rejected_item",
                "automatic_action_enabled": False,
                "acknowledgment_enables_live_trading": False,
            }
        )
        ledger["ledger_entries"].append(
            {
                "ledger_entry_id": "21B-pending_item",
                "review_item_id": "pending_item",
                "review_status": "PENDING_OPERATOR_REVIEW",
                "label": HUMAN_REVIEW_REQUIRED,
                "source_section": "required_human_review_items",
                "summary": "Pending review item.",
                "workflow_id": "pending_item",
                "automatic_action_enabled": False,
                "acknowledgment_enables_live_trading": False,
            }
        )
        ledger["unmatched_acknowledgments"] = [
            {
                "review_item_id": "unmatched_note",
                "review_status": "NOTED",
                "label": HUMAN_REVIEW_REQUIRED,
                "summary": "Unmatched acknowledgment.",
                "automatic_action_enabled": False,
                "acknowledgment_enables_live_trading": False,
            }
        ]
        _write_json(closeout_input.operator_acknowledgment_ledger_path, ledger)

        payload = build_human_review_closeout_gate_payload(closeout_input)
        markdown = render_human_review_closeout_gate_markdown(payload)

        assert payload["closeout_state"] == NEEDS_OPERATOR_REVIEW
        assert "pending_item" in {item["review_item_id"] for item in payload["unresolved_review_items"]}
        assert "rejected_item" in {item["review_item_id"] for item in payload["rejected_items"]}
        assert "retention_review" in {item["review_item_id"] for item in payload["deferred_items"]}
        assert "unmatched_note" in {item["review_item_id"] for item in payload["unmatched_acknowledgments"]}
        assert "22A-RESOLVE-UNRESOLVED-REVIEW-ITEMS" in {
            item["action_id"] for item in payload["required_next_human_review_actions"]
        }
        assert "NEEDS_OPERATOR_REVIEW" in markdown
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_22a_classifies_blocked_for_missing_artifacts_and_safety_findings() -> None:
    root = _root()
    try:
        closeout_input = _write_ready_inputs(root)
        closeout_input.report_index_path.unlink()
        _write_json(
            closeout_input.safety_scanner_path,
            {
                "workflow_id": "safety_scanner",
                "label": BLOCKED_BY_SAFETY_GATE,
                "status": "blocked",
                "summary": "Safety scanner found a blocked condition.",
                "passed": False,
                "finding_count": 1,
                "findings": [{"rule_id": "blocked_fixture", "summary": "Blocked fixture."}],
                "generated_at_utc": FIXED_NOW.isoformat(),
            },
        )

        payload = build_human_review_closeout_gate_payload(closeout_input)

        assert payload["closeout_state"] == BLOCKED_BY_SAFETY_GATE
        assert "report_index" in {item["artifact_id"] for item in payload["missing_artifacts"]}
        assert "blocked_fixture" in {item["finding_id"] for item in payload["safety_findings"]}
        assert "22A-RESOLVE-SAFETY-FINDINGS" in {
            item["action_id"] for item in payload["required_next_human_review_actions"]
        }
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_22a_rejects_secret_paths_unsafe_labels_and_execution_flags() -> None:
    root = _root()
    try:
        with pytest.raises(ValueError, match="secret files"):
            HumanReviewCloseoutGateInput(
                closeout_id="22A-UNSAFE",
                closeout_date="2026-07-07",
                generated_at_utc=FIXED_NOW.isoformat(),
                operator_acknowledgment_ledger_path=Path(".env"),
            ).validate()

        closeout_input = _write_ready_inputs(root)
        ledger = json.loads(closeout_input.operator_acknowledgment_ledger_path.read_text(encoding="utf-8"))
        ledger["ledger_entries"][0]["label"] = "AUTO" + "_TRADE"
        _write_json(closeout_input.operator_acknowledgment_ledger_path, ledger)
        with pytest.raises(ValueError, match="unsafe human review closeout gate label"):
            build_human_review_closeout_gate_payload(closeout_input)

        ledger["ledger_entries"][0]["label"] = HUMAN_REVIEW_REQUIRED
        ledger["ledger_entries"][0]["broker_order_call_" + "performed"] = True
        _write_json(closeout_input.operator_acknowledgment_ledger_path, ledger)
        with pytest.raises(ValueError, match="broker_order_call_performed"):
            build_human_review_closeout_gate_payload(closeout_input)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_22a_default_input_uses_phase_closeout_id() -> None:
    closeout_input = build_default_human_review_closeout_gate_input(now=FIXED_NOW)

    assert closeout_input.closeout_id == "22A-HUMAN-REVIEW-CLOSEOUT-GATE-2026-07-07"
    assert closeout_input.closeout_date == "2026-07-07"


def test_22a_cli_writes_human_review_closeout_gate() -> None:
    root = _root()
    out_dir = root / "out"
    try:
        closeout_input = _write_ready_inputs(root)
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/run_human_review_closeout_gate.py",
                "--out-dir",
                str(out_dir),
                "--closeout-date",
                "2026-07-07",
                "--operator-acknowledgment-ledger-path",
                str(closeout_input.operator_acknowledgment_ledger_path),
                "--human-review-queue-path",
                str(closeout_input.human_review_queue_path),
                "--readiness-gate-path",
                str(closeout_input.readiness_gate_path),
                "--retention-policy-path",
                str(closeout_input.retention_policy_path),
                "--audit-summary-path",
                str(closeout_input.audit_summary_path),
                "--manifest-path",
                str(closeout_input.manifest_path),
                "--release-bundle-path",
                str(closeout_input.release_bundle_path),
                "--operator-dashboard-snapshot-path",
                str(closeout_input.operator_dashboard_snapshot_path),
                "--report-index-path",
                str(closeout_input.report_index_path),
                "--safe-workflow-catalog-path",
                str(closeout_input.safe_workflow_catalog_path),
                "--queue-status-path",
                str(closeout_input.queue_status_path),
                "--safety-scanner-path",
                str(closeout_input.safety_scanner_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        assert completed.returncode == 0
        assert "JARVIS 22A HUMAN REVIEW CLOSEOUT GATE: COMPLETE" in completed.stdout
        assert "LIVE TRADING: DISABLED" in completed.stdout
        assert "Closeout records only" in completed.stdout
        assert "No secrets, credential files, broker routing, broker calls, live trading, or order execution are used" in completed.stdout
        assert (out_dir / "human_review_closeout_gate.json").exists()
        assert (out_dir / "human_review_closeout_gate.md").exists()
    finally:
        shutil.rmtree(root, ignore_errors=True)
