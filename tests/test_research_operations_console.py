from __future__ import annotations

import json
import shutil
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from core.research_operations_console import (
    OPERATIONS_CONSOLE_BLOCKED_BY_SAFETY_GATE,
    OPERATIONS_CONSOLE_COMPLETE,
    OPERATIONS_CONSOLE_NEEDS_OPERATOR_REVIEW,
    ResearchOperationsConsoleInput,
    build_default_research_operations_console_input,
    build_research_operations_console_payload,
    render_research_operations_console_markdown,
    write_research_operations_console,
)
from risk.policies import BLOCKED_BY_SAFETY_GATE, HUMAN_REVIEW_REQUIRED, MONITOR_ONLY


FIXED_NOW = datetime(2026, 7, 7, 22, 0, 0, tzinfo=UTC)


def _root() -> Path:
    return Path("reports/research_operations_console_tests") / uuid.uuid4().hex


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


def _console_input(root: Path) -> ResearchOperationsConsoleInput:
    return ResearchOperationsConsoleInput(
        console_id="23A-RESEARCH-OPERATIONS-CONSOLE-2026-07-07",
        console_date="2026-07-07",
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
        safety_scanner_path=root / "safety_scanner" / "safety_scanner_status.json",
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


def _write_ready_inputs(root: Path) -> ResearchOperationsConsoleInput:
    console_input = _console_input(root)
    payloads = {
        console_input.closeout_gate_path: _closeout_payload(),
        console_input.operator_acknowledgment_ledger_path: _ledger_payload(),
        console_input.human_review_queue_path: {
            **_artifact_payload("21A", "Human Review Queue", "review_date"),
            "queue_state": "OPEN_HUMAN_REVIEW_QUEUE",
            "next_operator_actions": [],
            "blocked_workflows": [],
        },
        console_input.readiness_gate_path: _artifact_payload("20A", "Research Cycle Readiness Gate", "gate_date"),
        console_input.retention_policy_path: {
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
        console_input.audit_summary_path: _artifact_payload("19B", "Research Cycle Audit Summary", "audit_date"),
        console_input.manifest_path: _artifact_payload("19A", "Research Cycle Manifest", "cycle_date"),
        console_input.release_bundle_path: _artifact_payload("18B", "Research Release Bundle", "bundle_date"),
        console_input.operator_dashboard_snapshot_path: _artifact_payload(
            "17B",
            "Operator Dashboard Snapshot",
            "snapshot_date",
        ),
        console_input.report_index_path: _artifact_payload("17A", "Report Index", "index_date"),
        console_input.safe_workflow_catalog_path: {
            **_artifact_payload("18A", "Safe Workflow Catalog", "catalog_date", label=MONITOR_ONLY),
            "workflows": [{"workflow_id": "report_index"}],
        },
        console_input.safety_scanner_path: {
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
        console_input.queue_status_path,
        [
            {
                "phase": "23A",
                "title": "Research Operations Console",
                "spec": "Build deterministic operations console.",
            }
        ],
    )
    return console_input


def test_23a_builds_deterministic_records_only_operations_console() -> None:
    root = _root()
    try:
        console_input = _write_ready_inputs(root)

        first = build_research_operations_console_payload(console_input)
        second = build_research_operations_console_payload(console_input)

        assert first == second
        assert first["phase"] == "23A"
        assert first["workflow"] == "Research Operations Console"
        assert first["console_state"] == OPERATIONS_CONSOLE_COMPLETE
        assert first["summary"]["source_artifact_count"] == 12
        assert first["summary"]["missing_artifact_count"] == 0
        assert first["summary"]["stale_artifact_count"] == 0
        assert first["summary"]["rejected_item_count"] == 0
        assert first["summary"]["deferred_item_count"] == 0
        assert first["summary"]["safety_finding_count"] == 0
        assert first["summary"]["required_operator_action_count"] == 1
        assert first["safety_scanner_status"]["status"] == "passed"
        assert first["required_operator_actions"][0]["action_id"] == "23A-REVIEW-OPERATIONS-CONSOLE"
        assert first["safety_boundary"]["console_records_only"] is True
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
        assert "records-only" in first["final_console_summary"]
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_23a_writes_json_and_markdown_operations_console() -> None:
    root = _root()
    out_dir = root / "out"
    try:
        json_path, markdown_path = write_research_operations_console(
            _write_ready_inputs(root),
            out_dir=out_dir,
        )

        payload = json.loads(json_path.read_text(encoding="utf-8"))
        markdown = markdown_path.read_text(encoding="utf-8")

        assert json_path.name == "research_operations_console.json"
        assert markdown_path.name == "research_operations_console.md"
        assert payload["console_id"] == "23A-RESEARCH-OPERATIONS-CONSOLE-2026-07-07"
        assert "23A Research Operations Console" in markdown
        assert "Final Research-Cycle Console Summary" in markdown
        assert "Completed Items" in markdown
        assert "Open Items" in markdown
        assert "Blocked Items" in markdown
        assert "Retention Items" in markdown
        assert "Safety Scanner Status" in markdown
        assert "Required Operator Actions" in markdown
        assert "records-only and do not enable live trading" in markdown
        assert "LIVE TRADING: DISABLED" in markdown
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_23a_classifies_operator_review_for_open_rejected_deferred_stale_and_retention_items() -> None:
    root = _root()
    try:
        console_input = _write_ready_inputs(root)
        _write_json(
            console_input.operator_acknowledgment_ledger_path,
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
            console_input.retention_policy_path,
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
        _write_json(console_input.audit_summary_path, stale)

        payload = build_research_operations_console_payload(console_input)
        markdown = render_research_operations_console_markdown(payload)

        assert payload["console_state"] == OPERATIONS_CONSOLE_NEEDS_OPERATOR_REVIEW
        assert "open_pending_item" in {item["item_id"] for item in payload["open_items"]}
        assert "rejected_rejected_item" in {item["item_id"] for item in payload["rejected_items"]}
        assert "deferred_deferred_item" in {item["item_id"] for item in payload["deferred_items"]}
        assert "stale_audit_summary" in {item["workflow_id"] for item in payload["stale_artifacts"]}
        assert "retention_old_research" in {item["item_id"] for item in payload["retention_items"]}
        assert "23A-REVIEW-OPEN-ITEMS" in {item["action_id"] for item in payload["required_operator_actions"]}
        assert "23A-REVIEW-RETENTION-ITEMS" in {item["action_id"] for item in payload["required_operator_actions"]}
        assert "OPERATIONS_CONSOLE_NEEDS_OPERATOR_REVIEW" in markdown
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_23a_classifies_blocked_for_missing_artifacts_and_safety_findings() -> None:
    root = _root()
    try:
        console_input = _write_ready_inputs(root)
        console_input.report_index_path.unlink()
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
        _write_json(console_input.closeout_gate_path, closeout)
        _write_json(
            console_input.safety_scanner_path,
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

        payload = build_research_operations_console_payload(console_input)

        assert payload["console_state"] == OPERATIONS_CONSOLE_BLOCKED_BY_SAFETY_GATE
        assert "report_index" in {item["artifact_id"] for item in payload["missing_artifacts"]}
        assert "blocked_fixture" in {
            item.get("finding_id") for item in payload["blocked_items"]
        }
        assert "blocked_scanner_fixture" in {item["finding_id"] for item in payload["safety_findings"]}
        assert "23A-RESOLVE-SAFETY-FINDINGS" in {
            item["action_id"] for item in payload["required_operator_actions"]
        }
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_23a_rejects_secret_paths_unsafe_labels_and_execution_flags() -> None:
    root = _root()
    try:
        with pytest.raises(ValueError, match="secret files"):
            ResearchOperationsConsoleInput(
                console_id="23A-UNSAFE",
                console_date="2026-07-07",
                generated_at_utc=FIXED_NOW.isoformat(),
                closeout_gate_path=Path(".env"),
            ).validate()

        console_input = _write_ready_inputs(root)
        ledger = json.loads(console_input.operator_acknowledgment_ledger_path.read_text(encoding="utf-8"))
        ledger["ledger_entries"][0]["label"] = "AUTO" + "_TRADE"
        _write_json(console_input.operator_acknowledgment_ledger_path, ledger)
        with pytest.raises(ValueError, match="unsafe research operations console label"):
            build_research_operations_console_payload(console_input)

        ledger["ledger_entries"][0]["label"] = HUMAN_REVIEW_REQUIRED
        ledger["ledger_entries"][0]["broker_order_call_" + "performed"] = True
        _write_json(console_input.operator_acknowledgment_ledger_path, ledger)
        with pytest.raises(ValueError, match="broker_order_call_performed"):
            build_research_operations_console_payload(console_input)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_23a_default_input_uses_phase_console_id() -> None:
    console_input = build_default_research_operations_console_input(now=FIXED_NOW)

    assert console_input.console_id == "23A-RESEARCH-OPERATIONS-CONSOLE-2026-07-07"
    assert console_input.console_date == "2026-07-07"


def test_23a_cli_writes_research_operations_console() -> None:
    root = _root()
    out_dir = root / "out"
    try:
        console_input = _write_ready_inputs(root)
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/run_research_operations_console.py",
                "--out-dir",
                str(out_dir),
                "--console-date",
                "2026-07-07",
                "--closeout-gate-path",
                str(console_input.closeout_gate_path),
                "--operator-acknowledgment-ledger-path",
                str(console_input.operator_acknowledgment_ledger_path),
                "--human-review-queue-path",
                str(console_input.human_review_queue_path),
                "--readiness-gate-path",
                str(console_input.readiness_gate_path),
                "--retention-policy-path",
                str(console_input.retention_policy_path),
                "--audit-summary-path",
                str(console_input.audit_summary_path),
                "--manifest-path",
                str(console_input.manifest_path),
                "--release-bundle-path",
                str(console_input.release_bundle_path),
                "--operator-dashboard-snapshot-path",
                str(console_input.operator_dashboard_snapshot_path),
                "--report-index-path",
                str(console_input.report_index_path),
                "--safe-workflow-catalog-path",
                str(console_input.safe_workflow_catalog_path),
                "--queue-status-path",
                str(console_input.queue_status_path),
                "--safety-scanner-path",
                str(console_input.safety_scanner_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        assert completed.returncode == 0
        assert "JARVIS 23A RESEARCH OPERATIONS CONSOLE: COMPLETE" in completed.stdout
        assert "LIVE TRADING: DISABLED" in completed.stdout
        assert "Console is records-only" in completed.stdout
        assert "No secrets, credential files, broker routing, broker calls, live trading, or order execution are used" in completed.stdout
        assert (out_dir / "research_operations_console.json").exists()
        assert (out_dir / "research_operations_console.md").exists()
    finally:
        shutil.rmtree(root, ignore_errors=True)
