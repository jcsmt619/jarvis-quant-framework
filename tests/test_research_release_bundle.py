from __future__ import annotations

import json
import shutil
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from core.research_release_bundle import (
    ReleaseBundleArtifact,
    ResearchReleaseBundleInput,
    build_default_research_release_bundle_input,
    build_research_release_bundle_payload,
    render_research_release_bundle_markdown,
    write_research_release_bundle,
)
from risk.policies import BLOCKED_BY_SAFETY_GATE, HUMAN_REVIEW_REQUIRED, MONITOR_ONLY


FIXED_NOW = datetime(2026, 7, 7, 19, 0, 0, tzinfo=UTC)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path: Path, title: str = "Fixture") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# {title}\n\nLIVE TRADING: DISABLED.\n", encoding="utf-8")


def _artifact(root: Path, artifact_id: str, name: str | None = None) -> ReleaseBundleArtifact:
    return ReleaseBundleArtifact(
        artifact_id=artifact_id,
        name=name or artifact_id.replace("_", " ").title(),
        json_path=root / artifact_id / f"{artifact_id}.json",
        markdown_path=root / artifact_id / f"{artifact_id}.md",
        required_labels=(MONITOR_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE),
    )


def _bundle_input(root: Path) -> ResearchReleaseBundleInput:
    return ResearchReleaseBundleInput(
        bundle_id="18B-RESEARCH-RELEASE-BUNDLE-2026-07-07",
        bundle_date="2026-07-07",
        generated_at_utc=FIXED_NOW.isoformat(),
        artifacts=(
            _artifact(root, "report_index", "Report Index"),
            _artifact(root, "operator_dashboard_snapshot", "Operator Dashboard Snapshot"),
            _artifact(root, "research_evidence_pack", "Research Evidence Pack"),
            _artifact(root, "decision_journal", "Decision Journal"),
            _artifact(root, "operator_runbook", "Operator Runbook"),
            _artifact(root, "weekly_review", "Weekly Review"),
            _artifact(root, "daily_research_command_center", "Daily Research Command Center"),
            _artifact(root, "safe_workflow_catalog", "Safe Workflow Catalog"),
            _artifact(root, "safety_scanner_status", "Safety Scanner Status"),
        ),
        queue_path=root / "queue.json",
        safety_scanner_path=root / "safety_scanner_status" / "safety_scanner_status.json",
        safe_workflow_catalog_path=root / "safe_workflow_catalog" / "safe_workflow_catalog.json",
        operator_dashboard_snapshot_path=(
            root / "operator_dashboard_snapshot" / "operator_dashboard_snapshot.json"
        ),
    )


def _workflow_payload(phase: str, workflow: str, date_key: str = "report_date") -> dict[str, object]:
    return {
        "phase": phase,
        "workflow": workflow,
        date_key: "2026-07-07",
        "generated_at_utc": FIXED_NOW.isoformat(),
        "safety_boundary": {
            "label": HUMAN_REVIEW_REQUIRED,
            "live_trading_enabled": False,
            "broker_order_call_performed": False,
            "real_paper_order_submitted": False,
            "status": "LIVE TRADING: DISABLED",
        },
        "summary": {
            "artifact_count": 2,
            "blocked_workflow_count": 0,
            "safety_scanner_finding_count": 0,
        },
    }


def _write_fixture_bundle_inputs(root: Path) -> ResearchReleaseBundleInput:
    bundle_input = _bundle_input(root)
    payloads = {
        "report_index": _workflow_payload("17A", "Report Index", "index_date"),
        "operator_dashboard_snapshot": {
            **_workflow_payload("17B", "Operator Dashboard Snapshot", "snapshot_date"),
            "summary": {"blocked_workflow_count": 1},
            "blocked_workflows": [
                {
                    "workflow_id": "live_trading",
                    "label": BLOCKED_BY_SAFETY_GATE,
                    "status": "blocked",
                    "summary": "Live trading remains disabled.",
                }
            ],
        },
        "research_evidence_pack": _workflow_payload("16A", "Research Evidence Pack", "evidence_date"),
        "decision_journal": _workflow_payload("16B", "Decision Journal", "journal_date"),
        "operator_runbook": _workflow_payload("15B", "Operator Runbook", "runbook_date"),
        "weekly_review": _workflow_payload("14B", "Weekly Review", "week_end"),
        "daily_research_command_center": _workflow_payload("15A", "Daily Research Command Center"),
        "safe_workflow_catalog": {
            **_workflow_payload("18A", "Safe Workflow Catalog", "catalog_date"),
            "workflows": [{"workflow_id": "report_index"}],
            "blocked_behaviors": ["enable live trading", "submit broker orders"],
        },
        "safety_scanner_status": {
            "status": "passed",
            "label": HUMAN_REVIEW_REQUIRED,
            "passed": True,
            "finding_count": 0,
            "findings": [],
            "summary": "Safety scanner passed.",
        },
    }
    for artifact in bundle_input.artifacts:
        _write_json(artifact.json_path, payloads[artifact.artifact_id])
        _write_markdown(artifact.markdown_path, artifact.name)
    _write_json(
        bundle_input.queue_path,
        [
            {
                "phase": "18B",
                "title": "Research Release Bundle",
                "spec": "Build deterministic release bundle manifest.",
            }
        ],
    )
    return bundle_input


def test_18b_builds_deterministic_research_release_bundle_payload() -> None:
    root = Path("reports/research_release_bundle_tests") / uuid.uuid4().hex
    try:
        bundle_input = _write_fixture_bundle_inputs(root)

        first = build_research_release_bundle_payload(bundle_input)
        second = build_research_release_bundle_payload(bundle_input)

        assert first == second
        assert first["phase"] == "18B"
        assert first["workflow"] == "Research Release Bundle"
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
        assert first["summary"]["artifact_count"] == 9
        assert first["summary"]["present_artifact_count"] == 9
        assert first["summary"]["missing_artifact_count"] == 0
        assert first["summary"]["queue_item_count"] == 1
        assert first["summary"]["safe_workflow_count"] == 1
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_18b_records_missing_artifacts_as_blocked() -> None:
    root = Path("reports/research_release_bundle_tests") / uuid.uuid4().hex
    try:
        bundle_input = _write_fixture_bundle_inputs(root)
        missing_artifact = bundle_input.artifacts[2]
        missing_artifact.markdown_path.unlink()

        payload = build_research_release_bundle_payload(bundle_input)

        missing = payload["missing_artifacts"]
        blocked_ids = {item["workflow_id"] for item in payload["blocked_workflows"]}
        assert payload["summary"]["missing_artifact_count"] == 1
        assert missing[0]["artifact_id"] == "research_evidence_pack"
        assert missing[0]["label"] == BLOCKED_BY_SAFETY_GATE
        assert "missing_research_evidence_pack" in blocked_ids
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_18b_includes_queue_safety_catalog_and_dashboard_summaries() -> None:
    root = Path("reports/research_release_bundle_tests") / uuid.uuid4().hex
    try:
        payload = build_research_release_bundle_payload(_write_fixture_bundle_inputs(root))

        assert payload["queue_status"]["workflow_id"] == "master_plan_queue"
        assert payload["queue_status"]["next_phase"]["phase"] == "18B"
        assert payload["safety_scanner_status"]["status"] == "passed"
        assert payload["safety_scanner_status"]["finding_count"] == 0
        assert payload["safe_workflow_catalog_summary"]["workflow_count"] == 1
        assert payload["operator_dashboard_snapshot_summary"]["blocked_workflow_count"] == 1
        assert "live_trading" in {item["workflow_id"] for item in payload["blocked_workflows"]}
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_18b_writes_json_and_markdown_bundle() -> None:
    root = Path("reports/research_release_bundle_tests") / uuid.uuid4().hex
    out_dir = root / "out"
    try:
        json_path, markdown_path = write_research_release_bundle(
            _write_fixture_bundle_inputs(root),
            out_dir=out_dir,
        )

        payload = json.loads(json_path.read_text(encoding="utf-8"))
        markdown = markdown_path.read_text(encoding="utf-8")

        assert json_path.name == "research_release_bundle.json"
        assert markdown_path.name == "research_release_bundle.md"
        assert payload["bundle_id"] == "18B-RESEARCH-RELEASE-BUNDLE-2026-07-07"
        assert "18B Research Release Bundle" in markdown
        assert "Artifacts" in markdown
        assert "Queue Status" in markdown
        assert "Safety Scanner Status" in markdown
        assert "Blocked Workflows" in markdown
        assert "LIVE TRADING: DISABLED" in markdown
        assert "No secrets, credential files, broker routing, broker calls, or order execution are used." in markdown
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_18b_rejects_unsafe_labels_execution_flags_and_secret_paths() -> None:
    root = Path("reports/research_release_bundle_tests") / uuid.uuid4().hex
    try:
        bundle_input = _write_fixture_bundle_inputs(root)
        unsafe_artifact = bundle_input.artifacts[0]
        _write_json(
            unsafe_artifact.json_path,
            {
                "label": "AUTO" + "_TRADE",
                "summary": "Unsafe fixture.",
            },
        )

        with pytest.raises(ValueError, match="unsafe research release bundle label"):
            build_research_release_bundle_payload(bundle_input)

        _write_json(
            unsafe_artifact.json_path,
            {
                "label": HUMAN_REVIEW_REQUIRED,
                "live_trading_" + "enabled": True,
            },
        )
        with pytest.raises(ValueError, match="live_trading_enabled"):
            build_research_release_bundle_payload(bundle_input)

        with pytest.raises(ValueError, match="secret files"):
            build_research_release_bundle_payload(
                ResearchReleaseBundleInput(
                    bundle_id="18B-UNSAFE",
                    bundle_date="2026-07-07",
                    generated_at_utc=FIXED_NOW.isoformat(),
                    artifacts=(
                        ReleaseBundleArtifact(
                            artifact_id="unsafe",
                            name="Unsafe",
                            json_path=Path(".env"),
                            markdown_path=Path("reports/out.md"),
                        ),
                    ),
                )
            )
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_18b_markdown_lists_missing_sections() -> None:
    root = Path("reports/research_release_bundle_tests") / uuid.uuid4().hex
    payload = build_research_release_bundle_payload(_bundle_input(root))

    markdown = render_research_release_bundle_markdown(payload)

    assert "- Missing artifacts:" in markdown
    assert "missing_report_index" in markdown
    assert "BLOCKED_BY_SAFETY_GATE" in markdown
    assert "LIVE TRADING: DISABLED" in markdown


def test_18b_default_input_uses_phase_bundle_id() -> None:
    bundle_input = build_default_research_release_bundle_input(now=FIXED_NOW)

    assert bundle_input.bundle_id == "18B-RESEARCH-RELEASE-BUNDLE-2026-07-07"
    assert bundle_input.bundle_date == "2026-07-07"
    assert len(bundle_input.artifacts) == 9


def test_18b_runner_writes_bundle() -> None:
    out_dir = Path("reports/research_release_bundle_tests") / uuid.uuid4().hex
    try:
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/run_research_release_bundle.py",
                "--out-dir",
                str(out_dir),
                "--bundle-date",
                "2026-07-07",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        assert completed.returncode == 0
        assert "JARVIS 18B RESEARCH RELEASE BUNDLE: COMPLETE" in completed.stdout
        assert "LIVE TRADING: DISABLED" in completed.stdout
        assert "BLOCKED_BY_SAFETY_GATE missing artifacts and blocked workflows remain blocked" in completed.stdout
        assert (
            "No secrets, credential files, broker routing, broker calls, or order execution are used"
            in completed.stdout
        )
        assert (out_dir / "research_release_bundle.json").exists()
        assert (out_dir / "research_release_bundle.md").exists()
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)
