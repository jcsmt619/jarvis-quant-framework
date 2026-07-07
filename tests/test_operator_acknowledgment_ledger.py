from __future__ import annotations

import json
import shutil
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from core.operator_acknowledgment_ledger import (
    ACKNOWLEDGED,
    DEFERRED,
    LEDGER_NEEDS_OPERATOR_REVIEW,
    NOTED,
    PENDING_OPERATOR_REVIEW,
    REJECTED,
    OperatorAcknowledgmentLedgerInput,
    build_default_operator_acknowledgment_ledger_input,
    build_operator_acknowledgment_ledger_payload,
    render_operator_acknowledgment_ledger_markdown,
    write_operator_acknowledgment_ledger,
)
from risk.policies import BLOCKED_BY_SAFETY_GATE, HUMAN_REVIEW_REQUIRED


FIXED_NOW = datetime(2026, 7, 7, 20, 0, 0, tzinfo=UTC)


def _root() -> Path:
    return Path("reports/operator_acknowledgment_ledger_tests") / uuid.uuid4().hex


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _queue_payload() -> dict[str, object]:
    return {
        "phase": "21A",
        "workflow": "Human Review Queue",
        "queue_id": "21A-HUMAN-REVIEW-QUEUE-2026-07-07",
        "review_date": "2026-07-07",
        "generated_at_utc": "2026-07-07T19:00:00+00:00",
        "queue_state": "OPEN_HUMAN_REVIEW_QUEUE",
        "safety_boundary": {
            "label": HUMAN_REVIEW_REQUIRED,
            "research_only": True,
            "monitor_only": True,
            "paper_only": True,
            "human_review_required": True,
            "review_items_only": True,
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
        "required_human_review_items": [
            {
                "review_item_id": "20A-REVIEW-READINESS-GATE",
                "workflow_id": "review_readiness_gate",
                "label": HUMAN_REVIEW_REQUIRED,
                "status": "open_review_item",
                "summary": "Review 20A readiness gate.",
            }
        ],
        "missing_artifacts": [
            {
                "artifact_id": "report_index",
                "workflow_id": "missing_report_index",
                "label": BLOCKED_BY_SAFETY_GATE,
                "status": "missing",
                "summary": "Report index was missing.",
            }
        ],
        "stale_artifacts": [
            {
                "workflow_id": "stale_dashboard",
                "artifact_id": "operator_dashboard_snapshot",
                "label": HUMAN_REVIEW_REQUIRED,
                "status": "stale",
                "summary": "Dashboard snapshot is stale.",
            }
        ],
        "skipped_steps": [
            {
                "step_id": "weekly_review",
                "label": HUMAN_REVIEW_REQUIRED,
                "status": "skipped",
                "summary": "Weekly review was skipped.",
            }
        ],
        "blocked_workflows": [
            {
                "workflow_id": "live_trading",
                "label": BLOCKED_BY_SAFETY_GATE,
                "status": "blocked",
                "summary": "Live trading remains disabled.",
            }
        ],
        "safety_findings": [
            {
                "finding_id": "safety_scanner_status",
                "workflow_id": "safety_scanner",
                "label": BLOCKED_BY_SAFETY_GATE,
                "status": "failed",
                "summary": "Safety scanner requires review.",
            }
        ],
        "retention_review_items": [
            {
                "review_item_id": "retention_review_needed",
                "artifact_id": "review_needed",
                "label": HUMAN_REVIEW_REQUIRED,
                "status": "open_review_item",
                "summary": "Retention review required.",
                "automatic_delete_allowed": False,
            }
        ],
        "next_operator_actions": [
            {
                "action_id": "21A-REVIEW-HUMAN-REVIEW-QUEUE",
                "label": HUMAN_REVIEW_REQUIRED,
                "status": "open_review_item",
                "summary": "Review this queue.",
            }
        ],
    }


def _ledger_input(root: Path) -> OperatorAcknowledgmentLedgerInput:
    return OperatorAcknowledgmentLedgerInput(
        ledger_id="21B-OPERATOR-ACKNOWLEDGMENT-LEDGER-2026-07-07",
        ledger_date="2026-07-07",
        generated_at_utc=FIXED_NOW.isoformat(),
        human_review_queue_path=root / "human_review_queue.json",
        operator_acknowledgments_path=root / "operator_acknowledgments.json",
    )


def _write_ready_inputs(root: Path) -> OperatorAcknowledgmentLedgerInput:
    ledger_input = _ledger_input(root)
    _write_json(ledger_input.human_review_queue_path, _queue_payload())
    _write_json(
        ledger_input.operator_acknowledgments_path or root / "operator_acknowledgments.json",
        {
            "acknowledgments": [
                {
                    "review_item_id": "20A-REVIEW-READINESS-GATE",
                    "review_status": ACKNOWLEDGED,
                    "acknowledged_at_utc": "2026-07-07T20:01:00+00:00",
                    "operator_note": "Reviewed readiness record.",
                    "operator_id": "operator",
                },
                {
                    "review_item_id": "missing_report_index",
                    "review_status": REJECTED,
                    "acknowledged_at_utc": "2026-07-07T20:02:00+00:00",
                    "operator_note": "Rejected proceeding until report index is regenerated.",
                    "operator_id": "operator",
                },
                {
                    "review_item_id": "stale_dashboard",
                    "review_status": DEFERRED,
                    "acknowledged_at_utc": "2026-07-07T20:03:00+00:00",
                    "operator_note": "Deferred until next dashboard refresh.",
                    "operator_id": "operator",
                },
                {
                    "review_item_id": "weekly_review",
                    "review_status": NOTED,
                    "acknowledged_at_utc": "2026-07-07T20:04:00+00:00",
                    "operator_note": "Noted skipped weekly review.",
                    "operator_id": "operator",
                },
            ]
        },
    )
    return ledger_input


def test_21b_builds_deterministic_operator_acknowledgment_ledger() -> None:
    root = _root()
    try:
        ledger_input = _write_ready_inputs(root)

        first = build_operator_acknowledgment_ledger_payload(ledger_input)
        second = build_operator_acknowledgment_ledger_payload(ledger_input)

        assert first == second
        assert first["phase"] == "21B"
        assert first["workflow"] == "Operator Acknowledgment Ledger"
        assert first["ledger_state"] == LEDGER_NEEDS_OPERATOR_REVIEW
        assert first["summary"]["source_review_item_count"] == 8
        assert first["summary"]["acknowledged_count"] == 1
        assert first["summary"]["rejected_count"] == 1
        assert first["summary"]["deferred_count"] == 1
        assert first["summary"]["noted_count"] == 1
        assert first["summary"]["pending_operator_review_count"] == 4
        by_id = {item["review_item_id"]: item for item in first["ledger_entries"]}
        assert by_id["20A-REVIEW-READINESS-GATE"]["review_status"] == ACKNOWLEDGED
        assert by_id["missing_report_index"]["review_status"] == REJECTED
        assert by_id["live_trading"]["blocked_workflow_reference"] == "live_trading"
        assert by_id["live_trading"]["review_status"] == PENDING_OPERATOR_REVIEW
        assert first["safety_boundary"]["operator_acknowledgments_are_records_only"] is True
        assert first["safety_boundary"]["acknowledgment_enables_live_trading"] is False
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


def test_21b_writes_json_and_markdown_ledger() -> None:
    root = _root()
    out_dir = root / "out"
    try:
        json_path, markdown_path = write_operator_acknowledgment_ledger(
            _write_ready_inputs(root),
            out_dir=out_dir,
        )

        payload = json.loads(json_path.read_text(encoding="utf-8"))
        markdown = markdown_path.read_text(encoding="utf-8")

        assert json_path.name == "operator_acknowledgment_ledger.json"
        assert markdown_path.name == "operator_acknowledgment_ledger.md"
        assert payload["ledger_id"] == "21B-OPERATOR-ACKNOWLEDGMENT-LEDGER-2026-07-07"
        assert "21B Operator Acknowledgment Ledger" in markdown
        assert "Ledger Entries" in markdown
        assert "Blocked Workflow References" in markdown
        assert "Acknowledgments do not enable live trading" in markdown
        assert "LIVE TRADING: DISABLED" in markdown
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_21b_rejects_secret_paths_unsafe_labels_and_execution_flags() -> None:
    root = _root()
    try:
        with pytest.raises(ValueError, match="secret files"):
            OperatorAcknowledgmentLedgerInput(
                ledger_id="21B-UNSAFE",
                ledger_date="2026-07-07",
                generated_at_utc=FIXED_NOW.isoformat(),
                human_review_queue_path=Path(".env"),
            ).validate()

        ledger_input = _write_ready_inputs(root)
        ack_path = ledger_input.operator_acknowledgments_path
        assert ack_path is not None
        unsafe = json.loads(ack_path.read_text(encoding="utf-8"))
        unsafe["acknowledgments"][0]["label"] = "AUTO" + "_TRADE"
        _write_json(ack_path, unsafe)
        with pytest.raises(ValueError, match="unsafe operator acknowledgment ledger label"):
            build_operator_acknowledgment_ledger_payload(ledger_input)

        unsafe["acknowledgments"][0]["label"] = HUMAN_REVIEW_REQUIRED
        unsafe["acknowledgments"][0]["live_trading_" + "enabled"] = True
        _write_json(ack_path, unsafe)
        with pytest.raises(ValueError, match="live_trading_enabled"):
            build_operator_acknowledgment_ledger_payload(ledger_input)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_21b_tracks_unmatched_acknowledgments_without_action() -> None:
    root = _root()
    try:
        ledger_input = _write_ready_inputs(root)
        ack_path = ledger_input.operator_acknowledgments_path
        assert ack_path is not None
        acknowledgments = json.loads(ack_path.read_text(encoding="utf-8"))
        acknowledgments["acknowledgments"].append(
            {
                "review_item_id": "unknown_review_item",
                "review_status": NOTED,
                "acknowledged_at_utc": "2026-07-07T20:05:00+00:00",
                "operator_note": "This source item was not present in 21A.",
                "operator_id": "operator",
            }
        )
        _write_json(ack_path, acknowledgments)

        payload = build_operator_acknowledgment_ledger_payload(ledger_input)
        markdown = render_operator_acknowledgment_ledger_markdown(payload)

        assert payload["summary"]["unmatched_acknowledgment_count"] == 1
        assert payload["unmatched_acknowledgments"][0]["review_item_id"] == "unknown_review_item"
        assert payload["unmatched_acknowledgments"][0]["automatic_action_enabled"] is False
        assert "Unmatched Acknowledgments" in markdown
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_21b_default_input_uses_phase_ledger_id() -> None:
    ledger_input = build_default_operator_acknowledgment_ledger_input(now=FIXED_NOW)

    assert ledger_input.ledger_id == "21B-OPERATOR-ACKNOWLEDGMENT-LEDGER-2026-07-07"
    assert ledger_input.ledger_date == "2026-07-07"


def test_21b_cli_writes_operator_acknowledgment_ledger() -> None:
    root = _root()
    out_dir = root / "out"
    try:
        ledger_input = _write_ready_inputs(root)
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/run_operator_acknowledgment_ledger.py",
                "--out-dir",
                str(out_dir),
                "--ledger-date",
                "2026-07-07",
                "--human-review-queue-path",
                str(ledger_input.human_review_queue_path),
                "--operator-acknowledgments-path",
                str(ledger_input.operator_acknowledgments_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        assert completed.returncode == 0
        assert "JARVIS 21B OPERATOR ACKNOWLEDGMENT LEDGER: COMPLETE" in completed.stdout
        assert "LIVE TRADING: DISABLED" in completed.stdout
        assert "Acknowledgments are records only" in completed.stdout
        assert "No secrets, credential files, broker routing, broker calls, or order execution are used" in completed.stdout
        assert (out_dir / "operator_acknowledgment_ledger.json").exists()
        assert (out_dir / "operator_acknowledgment_ledger.md").exists()
    finally:
        shutil.rmtree(root, ignore_errors=True)
