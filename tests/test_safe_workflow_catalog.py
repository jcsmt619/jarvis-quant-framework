from __future__ import annotations

import json
import shutil
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from core.safe_workflow_catalog import (
    SafeWorkflow,
    SafeWorkflowCatalogInput,
    build_default_safe_workflow_catalog_input,
    build_safe_workflow_catalog_payload,
    render_safe_workflow_catalog_markdown,
    write_safe_workflow_catalog,
)
from risk.policies import BLOCKED_BY_SAFETY_GATE, HUMAN_REVIEW_REQUIRED, MONITOR_ONLY, RESEARCH_ONLY


FIXED_NOW = datetime(2026, 7, 7, 19, 0, 0, tzinfo=UTC)


def _catalog_input(*workflows: SafeWorkflow) -> SafeWorkflowCatalogInput:
    return SafeWorkflowCatalogInput(
        catalog_id="18A-SAFE-WORKFLOW-CATALOG-2026-07-07",
        catalog_date="2026-07-07",
        generated_at_utc=FIXED_NOW.isoformat(),
        workflows=workflows,
    )


def _workflow(
    *,
    labels: tuple[str, ...] = (RESEARCH_ONLY, HUMAN_REVIEW_REQUIRED),
    input_paths: tuple[Path, ...] = (Path("reports/source/"),),
    output_paths: tuple[Path, ...] = (Path("reports/out/catalog.json"),),
) -> SafeWorkflow:
    return SafeWorkflow(
        workflow_id="test_workflow",
        name="Test Workflow",
        category="report_generators",
        command_hints=("python scripts/run_test_workflow.py",),
        input_paths=input_paths,
        output_paths=output_paths,
        required_labels=labels,
        safety_status="LIVE TRADING: DISABLED",
        allowed_human_review_behavior=("review generated research artifacts",),
        blocked_behavior=("enable live trading",),
        description="Test workflow fixture.",
    )


def test_18a_builds_deterministic_safe_workflow_catalog_payload() -> None:
    catalog_input = build_default_safe_workflow_catalog_input(now=FIXED_NOW)

    first = build_safe_workflow_catalog_payload(catalog_input)
    second = build_safe_workflow_catalog_payload(catalog_input)

    assert first == second
    assert first["phase"] == "18A"
    assert first["workflow"] == "Safe Workflow Catalog"
    assert first["safety_boundary"]["real_paper_wrapper_connected"] is False
    assert first["safety_boundary"]["real_paper_wrapper_attempted"] is False
    assert first["safety_boundary"]["real_paper_order_submitted"] is False
    assert first["safety_boundary"]["broker_order_call_performed"] is False
    assert first["safety_boundary"]["broker_order_routing_enabled"] is False
    assert first["safety_boundary"]["broker_routing_used"] is False
    assert first["safety_boundary"]["broker_call_used"] is False
    assert first["safety_boundary"]["order_execution_used"] is False
    assert first["safety_boundary"]["live_trading_enabled"] is False
    assert first["safety_boundary"]["secrets_required"] is False
    assert first["safety_boundary"]["credential_file_used"] is False
    assert first["safety_boundary"]["prohibited_trade_labels_present"] is False
    assert first["safety_boundary"]["status"] == "LIVE TRADING: DISABLED"
    assert first["summary"]["workflow_count"] >= 10


def test_18a_default_catalog_covers_required_workflow_categories() -> None:
    payload = build_safe_workflow_catalog_payload(
        build_default_safe_workflow_catalog_input(now=FIXED_NOW)
    )
    categories = {item["category"] for item in payload["workflows"]}
    workflow_ids = {item["workflow_id"] for item in payload["workflows"]}

    assert {
        "report_generators",
        "operator_dashboards",
        "evidence_packs",
        "decision_journals",
        "weekly_reviews",
        "daily_research_summaries",
        "safety_scanners",
        "queue_readers",
    } <= categories
    assert {
        "report_index",
        "operator_dashboard_snapshot",
        "research_evidence_pack",
        "decision_journal",
        "weekly_review",
        "daily_research_summary",
        "safety_scanner",
        "orchestrator_audit_reader",
    } <= workflow_ids


def test_18a_workflows_record_required_fields_and_blocked_behavior() -> None:
    payload = build_safe_workflow_catalog_payload(
        build_default_safe_workflow_catalog_input(now=FIXED_NOW)
    )

    for workflow in payload["workflows"]:
        assert workflow["command_hints"]
        assert workflow["input_paths"]
        assert workflow["output_paths"]
        assert workflow["required_labels"]
        assert workflow["safety_status"] == "LIVE TRADING: DISABLED"
        assert workflow["allowed_human_review_behavior"]
        assert workflow["blocked_behavior"]
        assert workflow["research_only"] is True
        assert workflow["monitor_only"] is True
        assert workflow["paper_only"] is True
        assert workflow["human_review_required"] is True
        assert workflow["live_trading_enabled"] is False
        assert workflow["broker_order_routing_enabled"] is False
        assert workflow["broker_order_call_performed"] is False
        assert workflow["real_paper_order_submitted"] is False
        assert workflow["secrets_required"] is False
        assert workflow["credential_file_used"] is False

    blocked_text = " ".join(payload["blocked_behaviors"])
    assert "submit broker orders" in blocked_text
    assert "open secrets or credential files" in blocked_text


def test_18a_writes_json_and_markdown_catalog() -> None:
    out_dir = Path("reports/safe_workflow_catalog_tests") / uuid.uuid4().hex
    try:
        json_path, markdown_path = write_safe_workflow_catalog(
            build_default_safe_workflow_catalog_input(now=FIXED_NOW),
            out_dir=out_dir,
        )

        payload = json.loads(json_path.read_text(encoding="utf-8"))
        markdown = markdown_path.read_text(encoding="utf-8")

        assert json_path.name == "safe_workflow_catalog.json"
        assert markdown_path.name == "safe_workflow_catalog.md"
        assert payload["catalog_id"] == "18A-SAFE-WORKFLOW-CATALOG-2026-07-07"
        assert "18A Safe Workflow Catalog" in markdown
        assert "Allowed Human-Review Behaviors" in markdown
        assert "Blocked Behaviors" in markdown
        assert "LIVE TRADING: DISABLED" in markdown
        assert "No secrets, credential files, broker routing, broker calls, or order execution are used." in markdown
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def test_18a_rejects_unsafe_labels_execution_flags_and_secret_paths() -> None:
    unsafe_label = "SELL" + "_NOW"

    with pytest.raises(ValueError, match="unsafe workflow label"):
        build_safe_workflow_catalog_payload(_catalog_input(_workflow(labels=(unsafe_label,))))

    payload = build_safe_workflow_catalog_payload(_catalog_input(_workflow()))
    payload["workflows"][0]["live_trading_enabled"] = True
    with pytest.raises(ValueError, match="live_trading_enabled"):
        render_safe_workflow_catalog_markdown(payload)

    with pytest.raises(ValueError, match="secret files"):
        build_safe_workflow_catalog_payload(
            _catalog_input(_workflow(input_paths=(Path(".env"),)))
        )

    with pytest.raises(ValueError, match="credential or secret paths"):
        build_safe_workflow_catalog_payload(
            _catalog_input(_workflow(output_paths=(Path("reports/secrets/catalog.json"),)))
        )


def test_18a_custom_catalog_counts_labels_and_categories() -> None:
    payload = build_safe_workflow_catalog_payload(
        _catalog_input(
            _workflow(labels=(RESEARCH_ONLY, HUMAN_REVIEW_REQUIRED)),
            SafeWorkflow(
                workflow_id="scanner",
                name="Scanner",
                category="safety_scanners",
                command_hints=("python scripts/check_jarvis_safety_scanner.py",),
                input_paths=(Path("automation/"),),
                output_paths=(Path("reports/safety_scanner/status.json"),),
                required_labels=(MONITOR_ONLY, BLOCKED_BY_SAFETY_GATE),
                safety_status="LIVE TRADING: DISABLED",
                allowed_human_review_behavior=("record blocked outcomes",),
                blocked_behavior=("perform broker order calls",),
                description="Scanner fixture.",
            ),
        )
    )

    assert payload["summary"]["workflow_count"] == 2
    assert payload["summary"]["category_counts"] == {
        "report_generators": 1,
        "safety_scanners": 1,
    }
    assert payload["summary"]["label_counts"]["RESEARCH_ONLY"] == 1
    assert payload["summary"]["label_counts"]["MONITOR_ONLY"] == 1
    assert payload["summary"]["label_counts"]["BLOCKED_BY_SAFETY_GATE"] == 1


def test_18a_runner_writes_catalog() -> None:
    out_dir = Path("reports/safe_workflow_catalog_tests") / uuid.uuid4().hex
    try:
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/run_safe_workflow_catalog.py",
                "--out-dir",
                str(out_dir),
                "--catalog-date",
                "2026-07-07",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        assert completed.returncode == 0
        assert "JARVIS 18A SAFE WORKFLOW CATALOG: COMPLETE" in completed.stdout
        assert "LIVE TRADING: DISABLED" in completed.stdout
        assert "BLOCKED_BY_SAFETY_GATE behaviors remain blocked" in completed.stdout
        assert (
            "No secrets, credential files, broker routing, broker calls, or order execution are used"
            in completed.stdout
        )
        assert (out_dir / "safe_workflow_catalog.json").exists()
        assert (out_dir / "safe_workflow_catalog.md").exists()
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)
