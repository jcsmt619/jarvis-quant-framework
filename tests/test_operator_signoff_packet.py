from __future__ import annotations

import json
import shutil
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from core.operator_signoff_packet import (
    SIGNOFF_PACKET_BLOCKED_BY_SAFETY_GATE,
    SIGNOFF_PACKET_COMPLETE,
    SIGNOFF_PACKET_NEEDS_OPERATOR_REVIEW,
    OperatorSignoffPacketInput,
    build_default_operator_signoff_packet_input,
    build_operator_signoff_packet_payload,
    render_operator_signoff_packet_markdown,
    write_operator_signoff_packet,
)
from risk.policies import BLOCKED_BY_SAFETY_GATE, HUMAN_REVIEW_REQUIRED, MONITOR_ONLY


FIXED_NOW = datetime(2026, 7, 7, 22, 0, 0, tzinfo=UTC)


def _root() -> Path:
    return Path("reports/operator_signoff_packet_tests") / uuid.uuid4().hex


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
        "generated_at_utc": f"{day}T21:00:00+00:00",
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
            "completed_item_count": 0,
            "open_item_count": 0,
            "blocked_item_count": 0,
            "missing_artifact_count": 0,
            "stale_artifact_count": 0,
        },
    }


def _signoff_input(root: Path) -> OperatorSignoffPacketInput:
    return OperatorSignoffPacketInput(
        signoff_id="22B-OPERATOR-SIGNOFF-PACKET-2026-07-07",
        signoff_date="2026-07-07",
        generated_at_utc=FIXED_NOW.isoformat(),
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


def _ledger_payload(*, extra_entries: list[dict[str, object]] | None = None) -> dict[str, object]:
    entries: list[dict[str, object]] = [
        {
            "ledger_entry_id": "21B-review-readiness",
            "review_item_id": "review_readiness",
            "review_status": "ACKNOWLEDGED",
            "label": HUMAN_REVIEW_REQUIRED,
            "summary": "Readiness gate acknowledged for records.",
            "workflow_id": "review_readiness_gate",
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
            "ledger_entry_id": "21B-live-trading",
            "review_item_id": "live_trading",
            "review_status": "NOTED",
            "label": BLOCKED_BY_SAFETY_GATE,
            "summary": "Live trading remains disabled.",
            "workflow_id": "live_trading",
            "automatic_action_enabled": False,
            "acknowledgment_enables_live_trading": False,
        },
    ]
    if extra_entries:
        entries.extend(extra_entries)
    return {
        **_artifact_payload("21B", "Operator Acknowledgment Ledger", "ledger_date"),
        "ledger_id": "21B-OPERATOR-ACKNOWLEDGMENT-LEDGER-2026-07-07",
        "ledger_state": "OPEN_OPERATOR_ACKNOWLEDGMENT_LEDGER",
        "ledger_entries": entries,
        "blocked_workflow_references": [],
        "unmatched_acknowledgments": [],
    }


def _closeout_payload(*, state: str = "CLOSED_FOR_RECORDS_ONLY") -> dict[str, object]:
    return {
        **_artifact_payload("22A", "Human Review Closeout Gate", "closeout_date"),
        "closeout_id": "22A-HUMAN-REVIEW-CLOSEOUT-GATE-2026-07-07",
        "closeout_state": state,
        "source_artifacts": [],
        "completed_items": [],
        "unresolved_review_items": [],
        "rejected_items": [],
        "deferred_items": [],
        "unmatched_acknowledgments": [],
        "blocked_workflows": [
            {
                "workflow_id": "live_trading",
                "label": BLOCKED_BY_SAFETY_GATE,
                "status": "blocked",
                "summary": "Live trading remains disabled.",
            }
        ],
        "missing_artifacts": [],
        "stale_artifacts": [],
        "safety_findings": [],
        "required_next_human_review_actions": [],
    }


def _write_ready_inputs(root: Path) -> OperatorSignoffPacketInput:
    signoff_input = _signoff_input(root)
    payloads = {
        signoff_input.closeout_gate_path: _closeout_payload(),
        signoff_input.operator_acknowledgment_ledger_path: _ledger_payload(),
        signoff_input.human_review_queue_path: {
            **_artifact_payload("21A", "Human Review Queue", "review_date"),
            "queue_state": "OPEN_HUMAN_REVIEW_QUEUE",
            "next_operator_actions": [],
            "blocked_workflows": [],
        },
        signoff_input.readiness_gate_path: _artifact_payload("20A", "Research Cycle Readiness Gate", "gate_date"),
        signoff_input.retention_policy_path: {
            **_artifact_payload("20B", "Research Artifact Retention Policy", "retention_date"),
            "artifacts": [
                {
                    "artifact_id": "research_release_bundle",
                    "label": HUMAN_REVIEW_REQUIRED,
                    "retention_action": "keep",
                    "retention_reasons": ["protected report type"],
                    "automatic_delete_allowed": False,
                    "dry_run_only": True,
                }
            ],
            "dry_run_manifest": [],
        },
        signoff_input.audit_summary_path: _artifact_payload("19B", "Research Cycle Audit Summary", "audit_date"),
        signoff_input.manifest_path: _artifact_payload("19A", "Research Cycle Manifest", "cycle_date"),
        signoff_input.release_bundle_path: _artifact_payload("18B", "Research Release Bundle", "bundle_date"),
        signoff_input.operator_dashboard_snapshot_path: _artifact_payload(
            "17B",
            "Operator Dashboard Snapshot",
            "snapshot_date",
        ),
        signoff_input.report_index_path: _artifact_payload("17A", "Report Index", "index_date"),
        signoff_input.safe_workflow_catalog_path: {
            **_artifact_payload("18A", "Safe Workflow Catalog", "catalog_date", label=MONITOR_ONLY),
            "workflows": [{"workflow_id": "report_index"}],
        },
    }
    for path, payload in payloads.items():
        _write_json(path, payload)
    _write_json(
        signoff_input.queue_status_path,
        [
            {
                "phase": "22B",
                "title": "Operator Signoff Packet",
                "spec": "Build deterministic signoff packet.",
            }
        ],
    )
    return signoff_input


def test_22b_builds_deterministic_records_only_signoff_packet() -> None:
    root = _root()
    try:
        signoff_input = _write_ready_inputs(root)

        first = build_operator_signoff_packet_payload(signoff_input)
        second = build_operator_signoff_packet_payload(signoff_input)

        assert first == second
        assert first["phase"] == "22B"
        assert first["workflow"] == "Operator Signoff Packet"
        assert first["signoff_state"] == SIGNOFF_PACKET_COMPLETE
        assert first["summary"]["source_artifact_count"] == 11
        assert first["summary"]["missing_artifact_count"] == 0
        assert first["summary"]["stale_artifact_count"] == 0
        assert first["summary"]["rejected_item_count"] == 0
        assert first["summary"]["deferred_item_count"] == 0
        assert first["safety_boundary"]["signoff_records_only"] is True
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
        assert "records-only" in first["final_signoff_summary"]
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_22b_writes_json_and_markdown_signoff_packet() -> None:
    root = _root()
    out_dir = root / "out"
    try:
        json_path, markdown_path = write_operator_signoff_packet(
            _write_ready_inputs(root),
            out_dir=out_dir,
        )

        payload = json.loads(json_path.read_text(encoding="utf-8"))
        markdown = markdown_path.read_text(encoding="utf-8")

        assert json_path.name == "operator_signoff_packet.json"
        assert markdown_path.name == "operator_signoff_packet.md"
        assert payload["signoff_id"] == "22B-OPERATOR-SIGNOFF-PACKET-2026-07-07"
        assert "22B Operator Signoff Packet" in markdown
        assert "Final Research-Cycle Signoff Summary" in markdown
        assert "Completed Items" in markdown
        assert "Open Items" in markdown
        assert "Blocked Items" in markdown
        assert "Retention Items" in markdown
        assert "records-only and do not enable live trading" in markdown
        assert "LIVE TRADING: DISABLED" in markdown
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_22b_classifies_operator_review_for_open_rejected_deferred_stale_and_retention_items() -> None:
    root = _root()
    try:
        signoff_input = _write_ready_inputs(root)
        _write_json(
            signoff_input.operator_acknowledgment_ledger_path,
            _ledger_payload(
                extra_entries=[
                    {
                        "ledger_entry_id": "21B-pending",
                        "review_item_id": "pending_item",
                        "review_status": "PENDING_OPERATOR_REVIEW",
                        "label": HUMAN_REVIEW_REQUIRED,
                        "summary": "Pending operator item.",
                        "workflow_id": "pending_item",
                        "automatic_action_enabled": False,
                    },
                    {
                        "ledger_entry_id": "21B-rejected",
                        "review_item_id": "rejected_item",
                        "review_status": "REJECTED",
                        "label": HUMAN_REVIEW_REQUIRED,
                        "summary": "Rejected operator item.",
                        "workflow_id": "rejected_item",
                        "automatic_action_enabled": False,
                    },
                    {
                        "ledger_entry_id": "21B-deferred",
                        "review_item_id": "deferred_item",
                        "review_status": "DEFERRED",
                        "label": HUMAN_REVIEW_REQUIRED,
                        "summary": "Deferred operator item.",
                        "workflow_id": "deferred_item",
                        "automatic_action_enabled": False,
                    },
                ]
            ),
        )
        _write_json(
            signoff_input.retention_policy_path,
            {
                **_artifact_payload("20B", "Research Artifact Retention Policy", "retention_date"),
                "artifacts": [
                    {
                        "artifact_id": "old_research",
                        "label": HUMAN_REVIEW_REQUIRED,
                        "retention_action": "review",
                        "retention_reasons": ["human review required"],
                        "automatic_delete_allowed": False,
                        "dry_run_only": True,
                    }
                ],
            },
        )
        stale = _artifact_payload("19B", "Research Cycle Audit Summary", "audit_date", day="2026-07-01")
        _write_json(signoff_input.audit_summary_path, stale)

        payload = build_operator_signoff_packet_payload(signoff_input)
        markdown = render_operator_signoff_packet_markdown(payload)

        assert payload["signoff_state"] == SIGNOFF_PACKET_NEEDS_OPERATOR_REVIEW
        assert "open_pending_item" in {item["item_id"] for item in payload["open_items"]}
        assert "rejected_rejected_item" in {item["item_id"] for item in payload["rejected_items"]}
        assert "deferred_deferred_item" in {item["item_id"] for item in payload["deferred_items"]}
        assert "stale_audit_summary" in {item["workflow_id"] for item in payload["stale_artifacts"]}
        assert "retention_old_research" in {item["item_id"] for item in payload["retention_items"]}
        assert "SIGNOFF_PACKET_NEEDS_OPERATOR_REVIEW" in markdown
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_22b_classifies_blocked_for_missing_artifacts_and_safety_findings() -> None:
    root = _root()
    try:
        signoff_input = _write_ready_inputs(root)
        signoff_input.report_index_path.unlink()
        closeout = _closeout_payload(state=BLOCKED_BY_SAFETY_GATE)
        closeout["safety_findings"] = [
            {
                "finding_id": "blocked_fixture",
                "workflow_id": "safety_scanner",
                "label": BLOCKED_BY_SAFETY_GATE,
                "status": "failed",
                "summary": "Blocked fixture.",
            }
        ]
        _write_json(signoff_input.closeout_gate_path, closeout)

        payload = build_operator_signoff_packet_payload(signoff_input)

        assert payload["signoff_state"] == SIGNOFF_PACKET_BLOCKED_BY_SAFETY_GATE
        assert "report_index" in {item["artifact_id"] for item in payload["missing_artifacts"]}
        assert "blocked_fixture" in {
            item.get("finding_id") for item in payload["blocked_items"]
        }
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_22b_rejects_secret_paths_unsafe_labels_and_execution_flags() -> None:
    root = _root()
    try:
        with pytest.raises(ValueError, match="secret files"):
            OperatorSignoffPacketInput(
                signoff_id="22B-UNSAFE",
                signoff_date="2026-07-07",
                generated_at_utc=FIXED_NOW.isoformat(),
                closeout_gate_path=Path(".env"),
            ).validate()

        signoff_input = _write_ready_inputs(root)
        ledger = json.loads(signoff_input.operator_acknowledgment_ledger_path.read_text(encoding="utf-8"))
        ledger["ledger_entries"][0]["label"] = "AUTO" + "_TRADE"
        _write_json(signoff_input.operator_acknowledgment_ledger_path, ledger)
        with pytest.raises(ValueError, match="unsafe operator signoff packet label"):
            build_operator_signoff_packet_payload(signoff_input)

        ledger["ledger_entries"][0]["label"] = HUMAN_REVIEW_REQUIRED
        ledger["ledger_entries"][0]["broker_order_call_" + "performed"] = True
        _write_json(signoff_input.operator_acknowledgment_ledger_path, ledger)
        with pytest.raises(ValueError, match="broker_order_call_performed"):
            build_operator_signoff_packet_payload(signoff_input)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_22b_default_input_uses_phase_signoff_id() -> None:
    signoff_input = build_default_operator_signoff_packet_input(now=FIXED_NOW)

    assert signoff_input.signoff_id == "22B-OPERATOR-SIGNOFF-PACKET-2026-07-07"
    assert signoff_input.signoff_date == "2026-07-07"


def test_22b_cli_writes_operator_signoff_packet() -> None:
    root = _root()
    out_dir = root / "out"
    try:
        signoff_input = _write_ready_inputs(root)
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/run_operator_signoff_packet.py",
                "--out-dir",
                str(out_dir),
                "--signoff-date",
                "2026-07-07",
                "--closeout-gate-path",
                str(signoff_input.closeout_gate_path),
                "--operator-acknowledgment-ledger-path",
                str(signoff_input.operator_acknowledgment_ledger_path),
                "--human-review-queue-path",
                str(signoff_input.human_review_queue_path),
                "--readiness-gate-path",
                str(signoff_input.readiness_gate_path),
                "--retention-policy-path",
                str(signoff_input.retention_policy_path),
                "--audit-summary-path",
                str(signoff_input.audit_summary_path),
                "--manifest-path",
                str(signoff_input.manifest_path),
                "--release-bundle-path",
                str(signoff_input.release_bundle_path),
                "--operator-dashboard-snapshot-path",
                str(signoff_input.operator_dashboard_snapshot_path),
                "--report-index-path",
                str(signoff_input.report_index_path),
                "--safe-workflow-catalog-path",
                str(signoff_input.safe_workflow_catalog_path),
                "--queue-status-path",
                str(signoff_input.queue_status_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        assert completed.returncode == 0
        assert "JARVIS 22B OPERATOR SIGNOFF PACKET: COMPLETE" in completed.stdout
        assert "LIVE TRADING: DISABLED" in completed.stdout
        assert "Signoff is records-only" in completed.stdout
        assert "No secrets, credential files, broker routing, broker calls, live trading, or order execution are used" in completed.stdout
        assert (out_dir / "operator_signoff_packet.json").exists()
        assert (out_dir / "operator_signoff_packet.md").exists()
    finally:
        shutil.rmtree(root, ignore_errors=True)
