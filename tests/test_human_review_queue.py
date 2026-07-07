from __future__ import annotations

import json
import shutil
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from core.human_review_queue import (
    BLOCKED_HUMAN_REVIEW_QUEUE,
    OPEN_HUMAN_REVIEW_QUEUE,
    HumanReviewQueueInput,
    build_default_human_review_queue_input,
    build_human_review_queue_payload,
    render_human_review_queue_markdown,
    write_human_review_queue,
)
from risk.policies import BLOCKED_BY_SAFETY_GATE, HUMAN_REVIEW_REQUIRED, MONITOR_ONLY


FIXED_NOW = datetime(2026, 7, 7, 19, 0, 0, tzinfo=UTC)


def _root() -> Path:
    return Path("reports/human_review_queue_tests") / uuid.uuid4().hex


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
        "generated_at_utc": f"{day}T19:00:00+00:00",
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
            "secrets_required": False,
            "credential_file_used": False,
            "prohibited_trade_labels_present": False,
            "status": "LIVE TRADING: DISABLED",
        },
        "summary": {
            "missing_artifact_count": 0,
            "skipped_step_count": 0,
            "blocked_workflow_count": 0,
            "safety_finding_count": 0,
            "retention_review_item_count": 0,
        },
    }


def _review_input(root: Path) -> HumanReviewQueueInput:
    return HumanReviewQueueInput(
        queue_id="21A-HUMAN-REVIEW-QUEUE-2026-07-07",
        review_date="2026-07-07",
        generated_at_utc=FIXED_NOW.isoformat(),
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


def _write_ready_inputs(root: Path) -> HumanReviewQueueInput:
    review_input = _review_input(root)
    readiness = {
        **_artifact_payload("20A", "Research Cycle Readiness Gate", "gate_date"),
        "decision": "READY_FOR_HUMAN_REVIEW",
        "required_human_review_actions": [
            {
                "action_id": "20A-REVIEW-READINESS-GATE",
                "workflow_id": "review_readiness_gate",
                "label": HUMAN_REVIEW_REQUIRED,
                "status": "open_review_item",
                "summary": "Review 20A readiness before planning.",
            }
        ],
        "missing_artifacts": [],
        "skipped_steps": [],
        "stale_reports": [],
        "blocked_workflows": [
            {
                "workflow_id": "live_trading",
                "label": BLOCKED_BY_SAFETY_GATE,
                "status": "blocked",
                "summary": "Live trading remains disabled.",
            }
        ],
        "failed_safety_findings": [],
    }
    retention = {
        **_artifact_payload("20B", "Research Artifact Retention Policy", "retention_date"),
        "artifacts": [
            {
                "artifact_id": "review_needed",
                "label": HUMAN_REVIEW_REQUIRED,
                "status": "present",
                "retention_action": "review",
                "retention_reasons": ["human-review-required label requires review before archival"],
                "automatic_delete_allowed": False,
            },
            {
                "artifact_id": "kept_report",
                "label": MONITOR_ONLY,
                "status": "present",
                "retention_action": "keep",
                "retention_reasons": ["protected report type"],
                "automatic_delete_allowed": False,
            },
        ],
    }
    audit = {
        **_artifact_payload("19B", "Research Cycle Audit Summary", "audit_date"),
        "human_review_notes": [
            {
                "note_id": "19B-CYCLE-MANIFEST-REVIEW",
                "workflow_id": "review_cycle_manifest",
                "label": HUMAN_REVIEW_REQUIRED,
                "status": "open_review_item",
                "summary": "Review 19A manifest.",
            }
        ],
        "allowed_human_review_workflows": [],
        "blocked_workflows": [],
        "missing_artifacts": [],
        "skipped_steps": [],
    }
    manifest = {
        **_artifact_payload("19A", "Research Cycle Runner", "cycle_date"),
        "missing_artifacts": [],
        "skipped_steps": [],
        "blocked_workflows": [],
    }
    payloads = {
        review_input.readiness_gate_path: readiness,
        review_input.retention_policy_path: retention,
        review_input.audit_summary_path: audit,
        review_input.manifest_path: manifest,
        review_input.release_bundle_path: _artifact_payload("18B", "Research Release Bundle", "bundle_date"),
        review_input.operator_dashboard_snapshot_path: _artifact_payload(
            "17B",
            "Operator Dashboard Snapshot",
            "snapshot_date",
        ),
        review_input.report_index_path: _artifact_payload("17A", "Report Index", "index_date"),
        review_input.safe_workflow_catalog_path: {
            **_artifact_payload("18A", "Safe Workflow Catalog", "catalog_date", label=MONITOR_ONLY),
            "workflows": [{"workflow_id": "report_index"}],
            "blocked_behaviors": ["enable live trading"],
        },
        review_input.safety_scanner_path: {
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
        review_input.queue_status_path,
        [
            {
                "phase": "21A",
                "title": "Human Review Queue",
                "spec": "Build deterministic review queue.",
            }
        ],
    )
    return review_input


def test_21a_builds_deterministic_human_review_queue() -> None:
    root = _root()
    try:
        review_input = _write_ready_inputs(root)

        first = build_human_review_queue_payload(review_input)
        second = build_human_review_queue_payload(review_input)

        assert first == second
        assert first["phase"] == "21A"
        assert first["workflow"] == "Human Review Queue"
        assert first["queue_state"] == OPEN_HUMAN_REVIEW_QUEUE
        assert first["summary"]["source_artifact_count"] == 9
        assert first["summary"]["missing_artifact_count"] == 0
        assert first["summary"]["retention_review_item_count"] == 1
        assert "20A-REVIEW-READINESS-GATE" in {
            item["review_item_id"] for item in first["required_human_review_items"]
        }
        assert first["queue_status"]["next_phase"]["phase"] == "21A"
        assert first["safety_boundary"]["review_items_only"] is True
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


def test_21a_writes_json_and_markdown_queue() -> None:
    root = _root()
    out_dir = root / "out"
    try:
        json_path, markdown_path = write_human_review_queue(
            _write_ready_inputs(root),
            out_dir=out_dir,
        )

        payload = json.loads(json_path.read_text(encoding="utf-8"))
        markdown = markdown_path.read_text(encoding="utf-8")

        assert json_path.name == "human_review_queue.json"
        assert markdown_path.name == "human_review_queue.md"
        assert payload["queue_id"] == "21A-HUMAN-REVIEW-QUEUE-2026-07-07"
        assert "21A Human Review Queue" in markdown
        assert "Required Human-Review Items" in markdown
        assert "Missing Artifacts" in markdown
        assert "Retention Review Items" in markdown
        assert "Next Operator Actions" in markdown
        assert "Review items are not trade instructions" in markdown
        assert "LIVE TRADING: DISABLED" in markdown
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_21a_lists_missing_stale_skipped_blocked_and_safety_items() -> None:
    root = _root()
    try:
        review_input = _write_ready_inputs(root)
        review_input.report_index_path.unlink()
        readiness = json.loads(review_input.readiness_gate_path.read_text(encoding="utf-8"))
        readiness["skipped_steps"] = [
            {
                "step_id": "weekly_review",
                "label": HUMAN_REVIEW_REQUIRED,
                "status": "skipped",
                "summary": "Weekly review was skipped.",
            }
        ]
        readiness["stale_reports"] = [
            {
                "workflow_id": "stale_operator_dashboard_snapshot",
                "artifact_id": "operator_dashboard_snapshot",
                "label": HUMAN_REVIEW_REQUIRED,
                "status": "stale",
                "summary": "Dashboard snapshot is stale.",
            }
        ]
        readiness["blocked_workflows"].append(
            {
                "workflow_id": "manual_repair_required",
                "label": BLOCKED_BY_SAFETY_GATE,
                "status": "blocked",
                "summary": "Manual repair required.",
            }
        )
        _write_json(review_input.readiness_gate_path, readiness)
        _write_json(
            review_input.safety_scanner_path,
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

        payload = build_human_review_queue_payload(review_input)
        markdown = render_human_review_queue_markdown(payload)

        assert payload["queue_state"] == BLOCKED_HUMAN_REVIEW_QUEUE
        assert "report_index" in {item["artifact_id"] for item in payload["missing_artifacts"]}
        assert "weekly_review" in {item["step_id"] for item in payload["skipped_steps"]}
        assert "stale_operator_dashboard_snapshot" in {
            item["workflow_id"] for item in payload["stale_artifacts"]
        }
        assert "manual_repair_required" in {
            item["workflow_id"] for item in payload["blocked_workflows"]
        }
        assert "blocked_fixture" in {item["finding_id"] for item in payload["safety_findings"]}
        assert "21A-RESOLVE-SAFETY-FINDINGS" in {
            item["action_id"] for item in payload["next_operator_actions"]
        }
        assert "BLOCKED_BY_SAFETY_GATE" in markdown
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_21a_rejects_secret_paths_unsafe_labels_and_execution_flags() -> None:
    root = _root()
    try:
        with pytest.raises(ValueError, match="secret files"):
            HumanReviewQueueInput(
                queue_id="21A-UNSAFE",
                review_date="2026-07-07",
                generated_at_utc=FIXED_NOW.isoformat(),
                readiness_gate_path=Path(".env"),
            ).validate()

        review_input = _write_ready_inputs(root)
        readiness = json.loads(review_input.readiness_gate_path.read_text(encoding="utf-8"))
        readiness["label"] = "AUTO" + "_TRADE"
        _write_json(review_input.readiness_gate_path, readiness)
        with pytest.raises(ValueError, match="unsafe human review queue label"):
            build_human_review_queue_payload(review_input)

        readiness["label"] = HUMAN_REVIEW_REQUIRED
        readiness["broker_order_call_" + "performed"] = True
        _write_json(review_input.readiness_gate_path, readiness)
        with pytest.raises(ValueError, match="broker_order_call_performed"):
            build_human_review_queue_payload(review_input)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_21a_default_input_uses_phase_queue_id() -> None:
    review_input = build_default_human_review_queue_input(now=FIXED_NOW)

    assert review_input.queue_id == "21A-HUMAN-REVIEW-QUEUE-2026-07-07"
    assert review_input.review_date == "2026-07-07"


def test_21a_cli_writes_human_review_queue() -> None:
    root = _root()
    out_dir = root / "out"
    try:
        review_input = _write_ready_inputs(root)
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/run_human_review_queue.py",
                "--out-dir",
                str(out_dir),
                "--review-date",
                "2026-07-07",
                "--readiness-gate-path",
                str(review_input.readiness_gate_path),
                "--retention-policy-path",
                str(review_input.retention_policy_path),
                "--audit-summary-path",
                str(review_input.audit_summary_path),
                "--manifest-path",
                str(review_input.manifest_path),
                "--release-bundle-path",
                str(review_input.release_bundle_path),
                "--operator-dashboard-snapshot-path",
                str(review_input.operator_dashboard_snapshot_path),
                "--report-index-path",
                str(review_input.report_index_path),
                "--safe-workflow-catalog-path",
                str(review_input.safe_workflow_catalog_path),
                "--queue-status-path",
                str(review_input.queue_status_path),
                "--safety-scanner-path",
                str(review_input.safety_scanner_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        assert completed.returncode == 0
        assert "JARVIS 21A HUMAN REVIEW QUEUE: COMPLETE" in completed.stdout
        assert "LIVE TRADING: DISABLED" in completed.stdout
        assert "Review items only" in completed.stdout
        assert "No secrets, credential files, broker routing, broker calls, or order execution are used" in completed.stdout
        assert (out_dir / "human_review_queue.json").exists()
        assert (out_dir / "human_review_queue.md").exists()
    finally:
        shutil.rmtree(root, ignore_errors=True)
