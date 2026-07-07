from __future__ import annotations

import json
import shutil
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from core.research_artifact_retention_policy import (
    ARCHIVE_CANDIDATE,
    BLOCKED_DELETE,
    KEEP,
    REVIEW,
    ResearchArtifactRetentionPolicyInput,
    RetentionArtifactTarget,
    build_default_research_artifact_retention_policy_input,
    build_research_artifact_retention_policy_payload,
    render_research_artifact_retention_policy_markdown,
    write_research_artifact_retention_policy,
)
from risk.policies import BLOCKED_BY_SAFETY_GATE, HUMAN_REVIEW_REQUIRED, MONITOR_ONLY, RESEARCH_ONLY


FIXED_NOW = datetime(2026, 7, 7, 19, 0, 0, tzinfo=UTC)


def _root() -> Path:
    return Path("reports/research_artifact_retention_policy_tests") / uuid.uuid4().hex


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path: Path, title: str = "Fixture") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# {title}\n\nLIVE TRADING: DISABLED.\n", encoding="utf-8")


def _payload(
    *,
    workflow: str,
    generated_at: str,
    label: str,
    date_key: str = "report_date",
) -> dict[str, object]:
    return {
        "phase": "20B-FIXTURE",
        "workflow": workflow,
        date_key: generated_at[:10],
        "generated_at_utc": generated_at,
        "safety_boundary": {
            "label": label,
            "live_trading_enabled": False,
            "broker_order_call_performed": False,
            "real_paper_order_submitted": False,
            "status": "LIVE TRADING: DISABLED",
        },
        "summary": {"artifact_count": 1},
    }


def _target(root: Path, artifact_id: str, report_type: str, label: str) -> RetentionArtifactTarget:
    return RetentionArtifactTarget(
        artifact_id=artifact_id,
        report_type=report_type,
        json_path=root / artifact_id / f"{artifact_id}.json",
        markdown_path=root / artifact_id / f"{artifact_id}.md",
        directory_path=root / artifact_id,
        expected_label=label,
    )


def _write_artifact(
    root: Path,
    artifact_id: str,
    *,
    report_type: str,
    generated_date: str,
    label: str,
) -> RetentionArtifactTarget:
    target = _target(root, artifact_id, report_type, label)
    _write_json(
        target.json_path or Path("missing"),
        _payload(
            workflow=report_type,
            generated_at=f"{generated_date}T12:00:00+00:00",
            label=label,
            date_key="bundle_date" if "Bundle" in report_type else "report_date",
        ),
    )
    _write_markdown(target.markdown_path or Path("missing"), report_type)
    return target


def _policy_input(root: Path) -> ResearchArtifactRetentionPolicyInput:
    referenced = _write_artifact(
        root,
        "referenced_report",
        report_type="Report Index",
        generated_date="2026-07-01",
        label=HUMAN_REVIEW_REQUIRED,
    )
    protected = _write_artifact(
        root,
        "release_bundle",
        report_type="Research Release Bundle",
        generated_date="2026-03-01",
        label=HUMAN_REVIEW_REQUIRED,
    )
    old_research = _write_artifact(
        root,
        "old_research",
        report_type="Daily Research Command Center",
        generated_date="2026-03-01",
        label=RESEARCH_ONLY,
    )
    review_needed = _write_artifact(
        root,
        "review_needed",
        report_type="Weekly Review",
        generated_date="2026-05-20",
        label=HUMAN_REVIEW_REQUIRED,
    )
    missing = _target(root, "missing_report", "Safety Scanner Status", MONITOR_ONLY)
    _write_json(
        root / "research_release_bundle" / "research_release_bundle.json",
        {
            "phase": "18B",
            "workflow": "Research Release Bundle",
            "artifacts": [
                {
                    "artifact_id": "referenced_report",
                    "json_path": (referenced.json_path or Path("missing")).as_posix(),
                    "markdown_path": (referenced.markdown_path or Path("missing")).as_posix(),
                }
            ],
            "safety_boundary": {"label": HUMAN_REVIEW_REQUIRED, "status": "LIVE TRADING: DISABLED"},
        },
    )
    return ResearchArtifactRetentionPolicyInput(
        policy_id="20B-RESEARCH-ARTIFACT-RETENTION-POLICY-2026-07-07",
        retention_date="2026-07-07",
        generated_at_utc=FIXED_NOW.isoformat(),
        artifacts=(referenced, protected, old_research, review_needed, missing),
        reference_sources=(root / "research_release_bundle" / "research_release_bundle.json",),
        keep_days=14,
        archive_after_days=60,
    )


def test_20b_builds_deterministic_retention_policy_payload() -> None:
    root = _root()
    try:
        policy_input = _policy_input(root)

        first = build_research_artifact_retention_policy_payload(policy_input)
        second = build_research_artifact_retention_policy_payload(policy_input)

        by_id = {item["artifact_id"]: item for item in first["artifacts"]}
        assert first == second
        assert first["phase"] == "20B"
        assert first["workflow"] == "Research Artifact Retention Policy"
        assert first["policy_rules"]["dry_run_only"] is True
        assert first["policy_rules"]["delete_files_automatically"] is False
        assert first["summary"]["artifact_count"] == 5
        assert first["summary"]["referenced_artifact_count"] == 1
        assert by_id["referenced_report"]["retention_action"] == KEEP
        assert by_id["release_bundle"]["retention_action"] == KEEP
        assert by_id["old_research"]["retention_action"] == ARCHIVE_CANDIDATE
        assert by_id["review_needed"]["retention_action"] == REVIEW
        assert by_id["missing_report"]["retention_action"] == BLOCKED_DELETE
        assert by_id["old_research"]["automatic_delete_allowed"] is False
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
        assert first["safety_boundary"]["automatic_file_deletion_enabled"] is False
        assert first["safety_boundary"]["status"] == "LIVE TRADING: DISABLED"
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_20b_writes_json_and_markdown_policy() -> None:
    root = _root()
    out_dir = root / "out"
    try:
        json_path, markdown_path = write_research_artifact_retention_policy(
            _policy_input(root),
            out_dir=out_dir,
        )

        payload = json.loads(json_path.read_text(encoding="utf-8"))
        markdown = markdown_path.read_text(encoding="utf-8")

        assert json_path.name == "research_artifact_retention_policy.json"
        assert markdown_path.name == "research_artifact_retention_policy.md"
        assert payload["policy_id"] == "20B-RESEARCH-ARTIFACT-RETENTION-POLICY-2026-07-07"
        assert "20B Research Artifact Retention Policy" in markdown
        assert "Dry-Run Manifest" in markdown
        assert "archive_candidate" in markdown
        assert "blocked_delete" in markdown
        assert "LIVE TRADING: DISABLED" in markdown
        assert "automatic file deletion" in markdown
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_20b_rejects_secret_paths_unsafe_labels_and_execution_flags() -> None:
    root = _root()
    try:
        with pytest.raises(ValueError, match="secret files"):
            ResearchArtifactRetentionPolicyInput(
                policy_id="20B-UNSAFE",
                retention_date="2026-07-07",
                generated_at_utc=FIXED_NOW.isoformat(),
                artifacts=(
                    RetentionArtifactTarget(
                        artifact_id="unsafe",
                        report_type="Unsafe",
                        json_path=Path(".env"),
                    ),
                ),
            ).validate()

        target = _write_artifact(
            root,
            "unsafe",
            report_type="Unsafe",
            generated_date="2026-07-01",
            label=HUMAN_REVIEW_REQUIRED,
        )
        _write_json(target.json_path or Path("missing"), {"label": "AUTO" + "_TRADE"})
        with pytest.raises(ValueError, match="unsafe research artifact retention label"):
            build_research_artifact_retention_policy_payload(
                ResearchArtifactRetentionPolicyInput(
                    policy_id="20B-UNSAFE",
                    retention_date="2026-07-07",
                    generated_at_utc=FIXED_NOW.isoformat(),
                    artifacts=(target,),
                )
            )

        _write_json(
            target.json_path or Path("missing"),
            {"label": HUMAN_REVIEW_REQUIRED, "live_trading_" + "enabled": True},
        )
        with pytest.raises(ValueError, match="live_trading_enabled"):
            build_research_artifact_retention_policy_payload(
                ResearchArtifactRetentionPolicyInput(
                    policy_id="20B-UNSAFE",
                    retention_date="2026-07-07",
                    generated_at_utc=FIXED_NOW.isoformat(),
                    artifacts=(target,),
                )
            )
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_20b_markdown_lists_missing_artifact_as_blocked_delete() -> None:
    root = _root()
    try:
        payload = build_research_artifact_retention_policy_payload(
            ResearchArtifactRetentionPolicyInput(
                policy_id="20B-RETENTION-MISSING",
                retention_date="2026-07-07",
                generated_at_utc=FIXED_NOW.isoformat(),
                artifacts=(_target(root, "missing_report", "Report Index", HUMAN_REVIEW_REQUIRED),),
            )
        )

        markdown = render_research_artifact_retention_policy_markdown(payload)

        assert payload["artifacts"][0]["retention_action"] == BLOCKED_DELETE
        assert "missing_report" in markdown
        assert "blocked_delete" in markdown
        assert "LIVE TRADING: DISABLED" in markdown
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_20b_default_input_uses_phase_policy_id() -> None:
    policy_input = build_default_research_artifact_retention_policy_input(now=FIXED_NOW)

    assert policy_input.policy_id == "20B-RESEARCH-ARTIFACT-RETENTION-POLICY-2026-07-07"
    assert policy_input.retention_date == "2026-07-07"
    assert len(policy_input.artifacts) >= 6
    assert len(policy_input.reference_sources) >= 6


def test_20b_cli_writes_retention_policy() -> None:
    out_dir = _root()
    try:
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/run_research_artifact_retention_policy.py",
                "--out-dir",
                str(out_dir),
                "--retention-date",
                "2026-07-07",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        assert completed.returncode == 0
        assert "JARVIS 20B RESEARCH ARTIFACT RETENTION POLICY: COMPLETE" in completed.stdout
        assert "LIVE TRADING: DISABLED" in completed.stdout
        assert "automatic deletion is disabled" in completed.stdout
        assert "No secrets, credential files, broker routing, broker calls, order execution, or automatic file deletion are used" in completed.stdout
        assert (out_dir / "research_artifact_retention_policy.json").exists()
        assert (out_dir / "research_artifact_retention_policy.md").exists()
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)
