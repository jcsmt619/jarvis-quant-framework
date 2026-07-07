from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from automation.safety_scanner import SafetyScanResult, scan_paths
from core.daily_research_command_center import (
    DAILY_RESEARCH_JSON,
    DAILY_RESEARCH_MARKDOWN,
    build_daily_research_payload,
    build_default_daily_research_input,
    write_daily_research_summary,
)
from core.decision_journal import (
    DECISION_JOURNAL_JSON,
    DECISION_JOURNAL_MARKDOWN,
    DecisionJournalInput,
    write_decision_journal,
)
from core.operator_dashboard_snapshot import (
    OPERATOR_DASHBOARD_SNAPSHOT_JSON,
    OPERATOR_DASHBOARD_SNAPSHOT_MARKDOWN,
    OperatorDashboardSnapshotInput,
    write_operator_dashboard_snapshot,
)
from core.operator_runbook import (
    OPERATOR_RUNBOOK_JSON,
    OPERATOR_RUNBOOK_MARKDOWN,
    OperatorRunbookInput,
    build_operator_runbook_payload,
    write_operator_runbook,
)
from core.report_index import (
    REPORT_INDEX_JSON,
    REPORT_INDEX_MARKDOWN,
    ReportIndexInput,
    ReportIndexTarget,
    write_report_index,
)
from core.research_evidence_pack import (
    RESEARCH_EVIDENCE_PACK_JSON,
    RESEARCH_EVIDENCE_PACK_MARKDOWN,
    ResearchEvidencePackInput,
    write_research_evidence_pack,
)
from core.research_release_bundle import (
    RESEARCH_RELEASE_BUNDLE_JSON,
    RESEARCH_RELEASE_BUNDLE_MARKDOWN,
    ReleaseBundleArtifact,
    ResearchReleaseBundleInput,
    write_research_release_bundle,
)
from core.safe_workflow_catalog import (
    SAFE_WORKFLOW_CATALOG_JSON,
    SAFE_WORKFLOW_CATALOG_MARKDOWN,
    build_default_safe_workflow_catalog_input,
    write_safe_workflow_catalog,
)
from core.weekly_review import (
    WEEKLY_REVIEW_JSON,
    WEEKLY_REVIEW_MARKDOWN,
    WeeklyReviewInput,
    build_weekly_review_payload,
    write_weekly_review,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


DEFAULT_RESEARCH_CYCLE_RUNNER_DIR = Path("reports/research_cycle_runner")
RESEARCH_CYCLE_MANIFEST_JSON = "research_cycle_manifest.json"
RESEARCH_CYCLE_MANIFEST_MARKDOWN = "research_cycle_manifest.md"

SAFE_RESEARCH_CYCLE_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
DISALLOWED_RESEARCH_CYCLE_LABELS = tuple(
    verb + suffix
    for verb, suffix in (
        ("BUY", "_NOW"),
        ("SELL", "_NOW"),
        ("EXECUTE", "_TRADE"),
        ("AUTO", "_TRADE"),
    )
)
UNSAFE_TRUE_FIELDS = (
    "live_trading_enabled",
    "broker_order_routing_enabled",
    "broker_order_call_performed",
    "real_paper_wrapper_connected",
    "real_paper_wrapper_attempted",
    "real_paper_order_submitted",
    "broker_routing_used",
    "broker_call_used",
    "order_execution_used",
    "secrets_required",
    "credential_file_used",
    "prohibited_trade_labels_present",
)


@dataclass(frozen=True)
class ResearchCycleRunnerInput:
    cycle_id: str
    cycle_date: str
    generated_at_utc: str
    report_root: Path = Path("reports")
    manifest_dir: Path = DEFAULT_RESEARCH_CYCLE_RUNNER_DIR
    queue_path: Path = Path("config/jarvis_master_plan_queue.json")
    include_weekly_review: bool = False
    safety_scan_paths: tuple[Path, ...] = (
        Path("core/research_cycle_runner.py"),
        Path("scripts/run_research_cycle_runner.py"),
    )

    def validate(self) -> None:
        for field_name in ("cycle_id", "cycle_date", "generated_at_utc"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"research cycle runner requires {field_name}")
        _parse_iso_date("cycle_date", self.cycle_date)
        _parse_iso_datetime("generated_at_utc", self.generated_at_utc)
        for path in (
            self.report_root,
            self.manifest_dir,
            self.queue_path,
            *self.safety_scan_paths,
        ):
            _validate_cycle_path(path)


@dataclass(frozen=True)
class CyclePaths:
    report_root: Path
    daily_dir: Path
    weekly_dir: Path
    runbook_dir: Path
    evidence_dir: Path
    journal_dir: Path
    report_index_dir: Path
    dashboard_dir: Path
    workflow_catalog_dir: Path
    release_bundle_dir: Path
    safety_scanner_dir: Path
    manifest_dir: Path


def build_default_research_cycle_runner_input(
    *,
    cycle_date: date | None = None,
    now: datetime | None = None,
    report_root: Path = Path("reports"),
    manifest_dir: Path = DEFAULT_RESEARCH_CYCLE_RUNNER_DIR,
    include_weekly_review: bool = False,
) -> ResearchCycleRunnerInput:
    generated = now or datetime.now(tz=UTC)
    day = cycle_date or generated.date()
    return ResearchCycleRunnerInput(
        cycle_id=f"19A-RESEARCH-CYCLE-RUNNER-{day.isoformat()}",
        cycle_date=day.isoformat(),
        generated_at_utc=generated.isoformat(),
        report_root=report_root,
        manifest_dir=manifest_dir,
        include_weekly_review=include_weekly_review,
    )


def run_research_cycle(
    cycle_input: ResearchCycleRunnerInput,
    *,
    safety_scanner: Callable[[list[Path]], SafetyScanResult] | None = None,
) -> tuple[dict[str, Any], Path, Path]:
    cycle_input.validate()
    paths = _cycle_paths(cycle_input)
    day = datetime.strptime(cycle_input.cycle_date, "%Y-%m-%d").date()
    generated = datetime.fromisoformat(cycle_input.generated_at_utc)

    outcomes: list[dict[str, Any]] = []
    artifact_paths: list[str] = []
    skipped_steps: list[dict[str, Any]] = []
    payloads: dict[str, dict[str, Any]] = {}

    daily_input = build_default_daily_research_input(report_date=day, now=generated)
    daily_json, daily_md = _run_step(
        outcomes,
        step_id="daily_research_command_center",
        command="python scripts/run_daily_research_command_center.py",
        action=lambda: write_daily_research_summary(daily_input, out_dir=paths.daily_dir),
    )
    artifact_paths.extend(_existing_paths(daily_json, daily_md))
    payloads["daily"] = build_daily_research_payload(daily_input)

    if cycle_input.include_weekly_review:
        weekly_payload = payloads["daily"].get("weekly_review") or {}
        weekly_input = _weekly_input_from_daily(weekly_payload, day, generated)
        weekly_json, weekly_md = _run_step(
            outcomes,
            step_id="weekly_review",
            command="python scripts/run_weekly_review.py --requested",
            action=lambda: write_weekly_review(weekly_input, out_dir=paths.weekly_dir),
        )
        artifact_paths.extend(_existing_paths(weekly_json, weekly_md))
        payloads["weekly"] = build_weekly_review_payload(weekly_input)
    else:
        skipped = _skipped_step("weekly_review", "Weekly review not requested for this cycle.")
        outcomes.append(skipped)
        skipped_steps.append(skipped)
        payloads["weekly"] = payloads["daily"].get("weekly_review") or {}

    runbook_input = OperatorRunbookInput(
        runbook_id=f"15B-OPERATOR-RUNBOOK-{day.isoformat()}",
        runbook_date=day.isoformat(),
        generated_at_utc=generated.isoformat(),
        daily_research_payload=payloads["daily"],
        weekly_review_payload=payloads["weekly"],
        experiment_review_items=tuple(payloads["daily"].get("experiments", ())),
        promotion_review_items=tuple(payloads["daily"].get("promotion_gates", ())),
        safety_findings=tuple(payloads["daily"].get("safety_scanner", {}).get("findings", ())),
        operator_notes=(
            {
                "note_id": "19A-RUNBOOK-CYCLE-NOTE",
                "label": HUMAN_REVIEW_REQUIRED,
                "summary": "19A cycle runner generated this runbook for review only.",
            },
        ),
    )
    runbook_json, runbook_md = _run_step(
        outcomes,
        step_id="operator_runbook",
        command="python scripts/run_operator_runbook.py",
        action=lambda: write_operator_runbook(runbook_input, out_dir=paths.runbook_dir),
    )
    artifact_paths.extend(_existing_paths(runbook_json, runbook_md))
    payloads["runbook"] = build_operator_runbook_payload(runbook_input)

    evidence_input = ResearchEvidencePackInput(
        pack_id=f"16A-RESEARCH-EVIDENCE-PACK-{day.isoformat()}",
        evidence_date=day.isoformat(),
        generated_at_utc=generated.isoformat(),
        strategy_cards=daily_input.strategy_cards,
        experiments=tuple(payloads["daily"].get("experiments", ())),
        promotion_gates=tuple(payloads["daily"].get("promotion_gates", ())),
        champion_challenger_outcomes=tuple(
            payloads["daily"].get("champion_challenger_outcomes", ())
        ),
        weekly_review_payload=payloads["weekly"],
        daily_research_payload=payloads["daily"],
        operator_runbook_payload=payloads["runbook"],
        operator_notes=(
            {
                "note_id": "19A-EVIDENCE-CYCLE-NOTE",
                "label": HUMAN_REVIEW_REQUIRED,
                "summary": "Evidence pack assembled by 19A without execution state changes.",
            },
        ),
    )
    evidence_json, evidence_md = _run_step(
        outcomes,
        step_id="research_evidence_pack",
        command="python scripts/run_research_evidence_pack.py",
        action=lambda: write_research_evidence_pack(evidence_input, out_dir=paths.evidence_dir),
    )
    artifact_paths.extend(_existing_paths(evidence_json, evidence_md))

    safety_result = (safety_scanner or scan_paths)(list(cycle_input.safety_scan_paths))
    safety_json, safety_md = _write_safety_scanner_status(safety_result, paths.safety_scanner_dir)
    artifact_paths.extend(_existing_paths(safety_json, safety_md))
    safety_status = _safety_status_payload(safety_result)

    journal_input = DecisionJournalInput(
        journal_id=f"16B-DECISION-JOURNAL-{day.isoformat()}",
        journal_date=day.isoformat(),
        generated_at_utc=generated.isoformat(),
        decision_records=(
            {
                "decision_id": "19A-CYCLE-REVIEW-RECORD",
                "label": HUMAN_REVIEW_REQUIRED,
                "status": "recorded_for_review",
                "workflow_id": "research_cycle_runner",
                "summary": "19A recorded the research cycle outcome for human review only.",
                "evidence_reference_id": f"16A-RESEARCH-EVIDENCE-PACK-{day.isoformat()}",
            },
        ),
        blocked_outcomes=_blocked_outcomes(safety_result),
        follow_up_actions=(
            {
                "action_id": "19A-NEXT-REVIEW",
                "label": HUMAN_REVIEW_REQUIRED,
                "status": "open_review_item",
                "summary": "Review the cycle manifest and missing artifacts before the next phase.",
            },
        ),
        evidence_pack_references=(
            {
                "reference_id": f"16A-RESEARCH-EVIDENCE-PACK-{day.isoformat()}",
                "label": HUMAN_REVIEW_REQUIRED,
                "status": "referenced",
                "path_hint": evidence_json.as_posix(),
                "summary": "19A research evidence pack reference.",
            },
        ),
        safety_scan_result=safety_result,
        operator_notes=(
            {
                "note_id": "19A-JOURNAL-CYCLE-NOTE",
                "label": HUMAN_REVIEW_REQUIRED,
                "summary": "Cycle remains research-only, monitor-only, and paper-only.",
            },
        ),
    )
    journal_json, journal_md = _run_step(
        outcomes,
        step_id="decision_journal",
        command="python scripts/run_decision_journal.py",
        action=lambda: write_decision_journal(journal_input, out_dir=paths.journal_dir),
    )
    artifact_paths.extend(_existing_paths(journal_json, journal_md))

    index_input = ReportIndexInput(
        index_id=f"17A-REPORT-INDEX-{day.isoformat()}",
        index_date=day.isoformat(),
        generated_at_utc=generated.isoformat(),
        targets=_report_index_targets(paths),
    )
    index_json, index_md = _run_step(
        outcomes,
        step_id="report_index",
        command="python scripts/run_report_index.py",
        action=lambda: write_report_index(index_input, out_dir=paths.report_index_dir),
    )
    artifact_paths.extend(_existing_paths(index_json, index_md))

    dashboard_input = OperatorDashboardSnapshotInput(
        snapshot_id=f"17B-OPERATOR-DASHBOARD-SNAPSHOT-{day.isoformat()}",
        snapshot_date=day.isoformat(),
        generated_at_utc=generated.isoformat(),
        report_index_path=paths.report_index_dir / REPORT_INDEX_JSON,
        queue_path=cycle_input.queue_path,
        daily_research_path=paths.daily_dir / DAILY_RESEARCH_JSON,
        weekly_review_path=paths.weekly_dir / WEEKLY_REVIEW_JSON,
        evidence_pack_path=paths.evidence_dir / RESEARCH_EVIDENCE_PACK_JSON,
        decision_journal_path=paths.journal_dir / DECISION_JOURNAL_JSON,
        operator_runbook_path=paths.runbook_dir / OPERATOR_RUNBOOK_JSON,
        safety_scanner_path=paths.safety_scanner_dir / "safety_scanner_status.json",
    )
    dashboard_json, dashboard_md = _run_step(
        outcomes,
        step_id="operator_dashboard_snapshot",
        command="python scripts/run_operator_dashboard_snapshot.py",
        action=lambda: write_operator_dashboard_snapshot(dashboard_input, out_dir=paths.dashboard_dir),
    )
    artifact_paths.extend(_existing_paths(dashboard_json, dashboard_md))

    catalog_input = build_default_safe_workflow_catalog_input(catalog_date=day, now=generated)
    catalog_json, catalog_md = _run_step(
        outcomes,
        step_id="safe_workflow_catalog",
        command="python scripts/run_safe_workflow_catalog.py",
        action=lambda: write_safe_workflow_catalog(catalog_input, out_dir=paths.workflow_catalog_dir),
    )
    artifact_paths.extend(_existing_paths(catalog_json, catalog_md))

    bundle_input = ResearchReleaseBundleInput(
        bundle_id=f"18B-RESEARCH-RELEASE-BUNDLE-{day.isoformat()}",
        bundle_date=day.isoformat(),
        generated_at_utc=generated.isoformat(),
        artifacts=_release_bundle_artifacts(paths),
        queue_path=cycle_input.queue_path,
        safety_scanner_path=paths.safety_scanner_dir / "safety_scanner_status.json",
        safe_workflow_catalog_path=paths.workflow_catalog_dir / SAFE_WORKFLOW_CATALOG_JSON,
        operator_dashboard_snapshot_path=paths.dashboard_dir / OPERATOR_DASHBOARD_SNAPSHOT_JSON,
    )
    bundle_json, bundle_md = _run_step(
        outcomes,
        step_id="research_release_bundle",
        command="python scripts/run_research_release_bundle.py",
        action=lambda: write_research_release_bundle(bundle_input, out_dir=paths.release_bundle_dir),
    )
    artifact_paths.extend(_existing_paths(bundle_json, bundle_md))

    manifest = build_research_cycle_manifest(
        cycle_input,
        outcomes=outcomes,
        artifact_paths=artifact_paths,
        skipped_steps=skipped_steps,
        safety_scanner_status=safety_status,
        paths=paths,
    )
    json_path, markdown_path = write_research_cycle_manifest(
        manifest,
        out_dir=paths.manifest_dir,
    )
    return manifest, json_path, markdown_path


def build_research_cycle_manifest(
    cycle_input: ResearchCycleRunnerInput,
    *,
    outcomes: list[dict[str, Any]],
    artifact_paths: list[str],
    skipped_steps: list[dict[str, Any]],
    safety_scanner_status: dict[str, Any],
    paths: CyclePaths,
) -> dict[str, Any]:
    missing_artifacts = _missing_artifacts(paths)
    blocked_workflows = _blocked_workflows(outcomes, missing_artifacts, safety_scanner_status)
    manifest = {
        "phase": "19A",
        "workflow": "Research Cycle Runner",
        "cycle_id": cycle_input.cycle_id,
        "cycle_date": cycle_input.cycle_date,
        "generated_at_utc": cycle_input.generated_at_utc,
        "safety_boundary": _safety_boundary(),
        "required_labels": list(SAFE_RESEARCH_CYCLE_LABELS),
        "summary": {
            "command_count": len(outcomes),
            "completed_command_count": sum(1 for item in outcomes if item["status"] == "completed"),
            "skipped_step_count": len(skipped_steps),
            "missing_artifact_count": len(missing_artifacts),
            "blocked_workflow_count": len(blocked_workflows),
            "safety_scanner_status": safety_scanner_status["status"],
            "safety_scanner_finding_count": safety_scanner_status["finding_count"],
            "artifact_path_count": len(sorted(set(artifact_paths))),
        },
        "command_outcomes": outcomes,
        "artifact_paths": sorted(set(artifact_paths)),
        "skipped_steps": skipped_steps,
        "missing_artifacts": missing_artifacts,
        "blocked_workflows": blocked_workflows,
        "safety_scanner_status": safety_scanner_status,
    }
    _validate_json_value("research_cycle_manifest", manifest)
    return _normalize_json_value(manifest)


def write_research_cycle_manifest(
    manifest: dict[str, Any],
    *,
    out_dir: Path = DEFAULT_RESEARCH_CYCLE_RUNNER_DIR,
) -> tuple[Path, Path]:
    _validate_json_value("research_cycle_manifest", manifest)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / RESEARCH_CYCLE_MANIFEST_JSON
    markdown_path = out_dir / RESEARCH_CYCLE_MANIFEST_MARKDOWN
    json_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_research_cycle_manifest_markdown(manifest), encoding="utf-8")
    return json_path, markdown_path


def render_research_cycle_manifest_markdown(payload: dict[str, Any]) -> str:
    _validate_json_value("research_cycle_manifest", payload)
    lines = [
        "# 19A Research Cycle Runner",
        "",
        f"Cycle ID: {payload['cycle_id']}",
        f"Cycle Date: {payload['cycle_date']}",
        f"Generated: {payload['generated_at_utc']}",
        "",
        "Status: RESEARCH_ONLY / MONITOR_ONLY / PAPER_ONLY / HUMAN_REVIEW_REQUIRED.",
        "BLOCKED_BY_SAFETY_GATE workflows remain blocked.",
        "LIVE TRADING: DISABLED. No secrets, credential files, broker routing, broker calls, or order execution are used.",
        "",
        "## Summary",
        "",
        _summary_line("Commands", payload["summary"]["command_count"]),
        _summary_line("Completed commands", payload["summary"]["completed_command_count"]),
        _summary_line("Skipped steps", payload["summary"]["skipped_step_count"]),
        _summary_line("Missing artifacts", payload["summary"]["missing_artifact_count"]),
        _summary_line("Blocked workflows", payload["summary"]["blocked_workflow_count"]),
        _summary_line("Safety scanner findings", payload["summary"]["safety_scanner_finding_count"]),
        "",
    ]
    lines.extend(_section("Command Outcomes", payload["command_outcomes"], "step_id"))
    lines.extend(_path_section("Artifact Paths", payload["artifact_paths"]))
    lines.extend(_section("Skipped Steps", payload["skipped_steps"], "step_id"))
    lines.extend(_section("Missing Artifacts", payload["missing_artifacts"], "artifact_id"))
    lines.extend(_section("Blocked Workflows", payload["blocked_workflows"], "workflow_id"))
    lines.extend(_section("Safety Scanner Status", [payload["safety_scanner_status"]], "workflow_id"))
    lines.extend(
        [
            "## Safety Boundary",
            "",
            "- RESEARCH_ONLY cycle coordination only.",
            "- MONITOR_ONLY and PAPER_ONLY artifacts are generated or summarized, not executed.",
            "- HUMAN_REVIEW_REQUIRED remains attached to trade-relevant interpretation.",
            "- BLOCKED_BY_SAFETY_GATE workflows remain blocked.",
            "- LIVE TRADING: DISABLED.",
            "",
        ]
    )
    return "\n".join(lines)


def _cycle_paths(cycle_input: ResearchCycleRunnerInput) -> CyclePaths:
    root = cycle_input.report_root
    return CyclePaths(
        report_root=root,
        daily_dir=root / "daily_research_command_center",
        weekly_dir=root / "weekly_review",
        runbook_dir=root / "operator_runbook",
        evidence_dir=root / "research_evidence_pack",
        journal_dir=root / "decision_journal",
        report_index_dir=root / "report_index",
        dashboard_dir=root / "operator_dashboard_snapshot",
        workflow_catalog_dir=root / "safe_workflow_catalog",
        release_bundle_dir=root / "research_release_bundle",
        safety_scanner_dir=root / "safety_scanner",
        manifest_dir=cycle_input.manifest_dir,
    )


def _run_step(
    outcomes: list[dict[str, Any]],
    *,
    step_id: str,
    command: str,
    action: Callable[[], tuple[Path, Path]],
) -> tuple[Path, Path]:
    try:
        json_path, markdown_path = action()
        outcome = {
            "step_id": step_id,
            "command": command,
            "return_code": 0,
            "status": "completed",
            "label": HUMAN_REVIEW_REQUIRED,
            "json_path": json_path.as_posix(),
            "markdown_path": markdown_path.as_posix(),
            "summary": "Step completed deterministically without broker routing or order execution.",
        }
    except Exception as exc:
        outcome = {
            "step_id": step_id,
            "command": command,
            "return_code": 1,
            "status": "blocked",
            "label": BLOCKED_BY_SAFETY_GATE,
            "json_path": None,
            "markdown_path": None,
            "summary": f"Step blocked: {type(exc).__name__}: {exc}",
        }
        outcomes.append(outcome)
        raise
    outcomes.append(outcome)
    return json_path, markdown_path


def _skipped_step(step_id: str, reason: str) -> dict[str, Any]:
    return {
        "step_id": step_id,
        "command": "stubbed",
        "return_code": 0,
        "status": "skipped",
        "label": HUMAN_REVIEW_REQUIRED,
        "json_path": None,
        "markdown_path": None,
        "summary": reason,
    }


def _weekly_input_from_daily(
    weekly_payload: dict[str, Any],
    day: date,
    generated: datetime,
) -> WeeklyReviewInput:
    if weekly_payload:
        return WeeklyReviewInput(
            review_id=str(weekly_payload.get("review_id") or f"14B-WEEKLY-{day.isoformat()}"),
            week_start=str(weekly_payload.get("week_start") or (day - timedelta(days=6)).isoformat()),
            week_end=str(weekly_payload.get("week_end") or day.isoformat()),
            generated_at_utc=str(weekly_payload.get("generated_at_utc") or generated.isoformat()),
            wealth_research_results=tuple(weekly_payload.get("wealth_research_results", ())),
            moonshot_research_results=tuple(weekly_payload.get("moonshot_research_results", ())),
            experiments=tuple(weekly_payload.get("experiments", ())),
            promotion_gates=tuple(weekly_payload.get("promotion_gates", ())),
            champion_challenger_outcomes=tuple(
                weekly_payload.get("champion_challenger_outcomes", ())
            ),
            safety_scanner_findings=tuple(weekly_payload.get("safety_scanner_findings", ())),
            blocked_decisions=tuple(weekly_payload.get("blocked_decisions", ())),
            next_review_actions=tuple(weekly_payload.get("next_review_actions", ())),
        )
    return WeeklyReviewInput(
        review_id=f"14B-WEEKLY-{day.isoformat()}",
        week_start=(day - timedelta(days=6)).isoformat(),
        week_end=day.isoformat(),
        generated_at_utc=generated.isoformat(),
    )


def _report_index_targets(paths: CyclePaths) -> tuple[ReportIndexTarget, ...]:
    return (
        ReportIndexTarget(
            "daily_research_command_center",
            "Daily Research Command Center",
            paths.daily_dir / DAILY_RESEARCH_JSON,
            paths.daily_dir / DAILY_RESEARCH_MARKDOWN,
        ),
        ReportIndexTarget(
            "weekly_review",
            "Weekly Review",
            paths.weekly_dir / WEEKLY_REVIEW_JSON,
            paths.weekly_dir / WEEKLY_REVIEW_MARKDOWN,
        ),
        ReportIndexTarget(
            "operator_runbook",
            "Operator Runbook",
            paths.runbook_dir / OPERATOR_RUNBOOK_JSON,
            paths.runbook_dir / OPERATOR_RUNBOOK_MARKDOWN,
        ),
        ReportIndexTarget(
            "research_evidence_pack",
            "Research Evidence Pack",
            paths.evidence_dir / RESEARCH_EVIDENCE_PACK_JSON,
            paths.evidence_dir / RESEARCH_EVIDENCE_PACK_MARKDOWN,
        ),
        ReportIndexTarget(
            "decision_journal",
            "Decision Journal",
            paths.journal_dir / DECISION_JOURNAL_JSON,
            paths.journal_dir / DECISION_JOURNAL_MARKDOWN,
        ),
        ReportIndexTarget(
            "safety_scanner_status",
            "Safety Scanner Status",
            paths.safety_scanner_dir / "safety_scanner_status.json",
            paths.safety_scanner_dir / "safety_scanner_status.md",
        ),
    )


def _release_bundle_artifacts(paths: CyclePaths) -> tuple[ReleaseBundleArtifact, ...]:
    return (
        _bundle_artifact("report_index", "Report Index", paths.report_index_dir, REPORT_INDEX_JSON, REPORT_INDEX_MARKDOWN),
        _bundle_artifact(
            "operator_dashboard_snapshot",
            "Operator Dashboard Snapshot",
            paths.dashboard_dir,
            OPERATOR_DASHBOARD_SNAPSHOT_JSON,
            OPERATOR_DASHBOARD_SNAPSHOT_MARKDOWN,
            (MONITOR_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE),
        ),
        _bundle_artifact(
            "research_evidence_pack",
            "Research Evidence Pack",
            paths.evidence_dir,
            RESEARCH_EVIDENCE_PACK_JSON,
            RESEARCH_EVIDENCE_PACK_MARKDOWN,
        ),
        _bundle_artifact("decision_journal", "Decision Journal", paths.journal_dir, DECISION_JOURNAL_JSON, DECISION_JOURNAL_MARKDOWN),
        _bundle_artifact("operator_runbook", "Operator Runbook", paths.runbook_dir, OPERATOR_RUNBOOK_JSON, OPERATOR_RUNBOOK_MARKDOWN),
        _bundle_artifact("weekly_review", "Weekly Review", paths.weekly_dir, WEEKLY_REVIEW_JSON, WEEKLY_REVIEW_MARKDOWN),
        _bundle_artifact(
            "daily_research_command_center",
            "Daily Research Command Center",
            paths.daily_dir,
            DAILY_RESEARCH_JSON,
            DAILY_RESEARCH_MARKDOWN,
        ),
        _bundle_artifact(
            "safe_workflow_catalog",
            "Safe Workflow Catalog",
            paths.workflow_catalog_dir,
            SAFE_WORKFLOW_CATALOG_JSON,
            SAFE_WORKFLOW_CATALOG_MARKDOWN,
            (MONITOR_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE),
        ),
        _bundle_artifact(
            "safety_scanner_status",
            "Safety Scanner Status",
            paths.safety_scanner_dir,
            "safety_scanner_status.json",
            "safety_scanner_status.md",
            (MONITOR_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE),
        ),
    )


def _bundle_artifact(
    artifact_id: str,
    name: str,
    out_dir: Path,
    json_name: str,
    markdown_name: str,
    labels: tuple[str, ...] = (
        RESEARCH_ONLY,
        MONITOR_ONLY,
        PAPER_ONLY,
        HUMAN_REVIEW_REQUIRED,
        BLOCKED_BY_SAFETY_GATE,
    ),
) -> ReleaseBundleArtifact:
    return ReleaseBundleArtifact(
        artifact_id=artifact_id,
        name=name,
        json_path=out_dir / json_name,
        markdown_path=out_dir / markdown_name,
        required_labels=labels,
    )


def _write_safety_scanner_status(
    result: SafetyScanResult,
    out_dir: Path,
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = _safety_status_payload(result)
    json_path = out_dir / "safety_scanner_status.json"
    markdown_path = out_dir / "safety_scanner_status.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(_render_safety_status_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def _safety_status_payload(result: SafetyScanResult) -> dict[str, Any]:
    payload = {
        "phase": "19A",
        "workflow": "Safety Scanner Status",
        "workflow_id": "safety_scanner",
        "label": HUMAN_REVIEW_REQUIRED if result.passed else BLOCKED_BY_SAFETY_GATE,
        "status": "passed" if result.passed else "blocked",
        "summary": "Safety scanner status recorded by the 19A research cycle runner.",
        "passed": result.passed,
        "finding_count": len(result.findings),
        "scanned_files": result.scanned_files,
        "skipped_files": list(result.skipped_files),
        "findings": [_dataclass_payload(finding) for finding in result.findings],
        "safety_boundary": _safety_boundary(),
    }
    _validate_json_value("safety_scanner_status", payload)
    return _normalize_json_value(payload)


def _render_safety_status_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# 19A Safety Scanner Status",
        "",
        f"Status: {payload['status']}",
        f"Findings: {payload['finding_count']}",
        "",
        "RESEARCH_ONLY / MONITOR_ONLY / PAPER_ONLY / HUMAN_REVIEW_REQUIRED.",
        "BLOCKED_BY_SAFETY_GATE findings remain blocked.",
        "LIVE TRADING: DISABLED.",
        "",
    ]
    lines.extend(_section("Findings", payload["findings"], "rule_id"))
    return "\n".join(lines)


def _missing_artifacts(paths: CyclePaths) -> list[dict[str, Any]]:
    expected = (
        ("daily_research_command_center", paths.daily_dir / DAILY_RESEARCH_JSON, paths.daily_dir / DAILY_RESEARCH_MARKDOWN),
        ("weekly_review", paths.weekly_dir / WEEKLY_REVIEW_JSON, paths.weekly_dir / WEEKLY_REVIEW_MARKDOWN),
        ("operator_runbook", paths.runbook_dir / OPERATOR_RUNBOOK_JSON, paths.runbook_dir / OPERATOR_RUNBOOK_MARKDOWN),
        ("research_evidence_pack", paths.evidence_dir / RESEARCH_EVIDENCE_PACK_JSON, paths.evidence_dir / RESEARCH_EVIDENCE_PACK_MARKDOWN),
        ("decision_journal", paths.journal_dir / DECISION_JOURNAL_JSON, paths.journal_dir / DECISION_JOURNAL_MARKDOWN),
        ("report_index", paths.report_index_dir / REPORT_INDEX_JSON, paths.report_index_dir / REPORT_INDEX_MARKDOWN),
        ("operator_dashboard_snapshot", paths.dashboard_dir / OPERATOR_DASHBOARD_SNAPSHOT_JSON, paths.dashboard_dir / OPERATOR_DASHBOARD_SNAPSHOT_MARKDOWN),
        ("safe_workflow_catalog", paths.workflow_catalog_dir / SAFE_WORKFLOW_CATALOG_JSON, paths.workflow_catalog_dir / SAFE_WORKFLOW_CATALOG_MARKDOWN),
        ("research_release_bundle", paths.release_bundle_dir / RESEARCH_RELEASE_BUNDLE_JSON, paths.release_bundle_dir / RESEARCH_RELEASE_BUNDLE_MARKDOWN),
        ("safety_scanner_status", paths.safety_scanner_dir / "safety_scanner_status.json", paths.safety_scanner_dir / "safety_scanner_status.md"),
    )
    missing = []
    for artifact_id, json_path, markdown_path in expected:
        missing_paths = [path.as_posix() for path in (json_path, markdown_path) if not path.is_file()]
        if missing_paths:
            missing.append(
                {
                    "artifact_id": artifact_id,
                    "label": BLOCKED_BY_SAFETY_GATE,
                    "status": "missing",
                    "missing_paths": missing_paths,
                    "summary": f"{artifact_id} has missing cycle artifacts.",
                }
            )
    return missing


def _blocked_workflows(
    outcomes: list[dict[str, Any]],
    missing_artifacts: list[dict[str, Any]],
    safety_status: dict[str, Any],
) -> list[dict[str, Any]]:
    blocked = [
        {
            "workflow_id": "live_trading",
            "label": BLOCKED_BY_SAFETY_GATE,
            "status": "blocked",
            "summary": "Live trading remains disabled.",
        },
        {
            "workflow_id": "broker_order_routing",
            "label": BLOCKED_BY_SAFETY_GATE,
            "status": "blocked",
            "summary": "Broker routing is outside the 19A research cycle runner.",
        },
        {
            "workflow_id": "broker_order_call",
            "label": BLOCKED_BY_SAFETY_GATE,
            "status": "blocked",
            "summary": "Broker order calls are not allowed.",
        },
        {
            "workflow_id": "order_execution",
            "label": BLOCKED_BY_SAFETY_GATE,
            "status": "blocked",
            "summary": "Order execution is not part of this workflow.",
        },
        {
            "workflow_id": "secret_or_credential_access",
            "label": BLOCKED_BY_SAFETY_GATE,
            "status": "blocked",
            "summary": "Secrets and credential files are not required and must not be opened.",
        },
    ]
    for outcome in outcomes:
        if outcome["status"] == "blocked":
            blocked.append(
                {
                    "workflow_id": outcome["step_id"],
                    "label": BLOCKED_BY_SAFETY_GATE,
                    "status": "blocked",
                    "summary": outcome["summary"],
                }
            )
    for artifact in missing_artifacts:
        blocked.append(
            {
                "workflow_id": f"missing_{artifact['artifact_id']}",
                "label": BLOCKED_BY_SAFETY_GATE,
                "status": "blocked",
                "summary": artifact["summary"],
            }
        )
    if safety_status["status"] == "blocked":
        blocked.append(
            {
                "workflow_id": "safety_scanner",
                "label": BLOCKED_BY_SAFETY_GATE,
                "status": "blocked",
                "summary": "Safety scanner findings remain blocked.",
            }
        )
    return _dedupe_workflows(blocked)


def _blocked_outcomes(result: SafetyScanResult) -> tuple[dict[str, Any], ...]:
    outcomes = [
        {
            "decision_id": "19A-LIVE-TRADING-BLOCK",
            "label": BLOCKED_BY_SAFETY_GATE,
            "status": "blocked",
            "workflow_id": "live_trading",
            "summary": "Live trading remains disabled and cannot be enabled by this cycle.",
        }
    ]
    if not result.passed:
        outcomes.append(
            {
                "decision_id": "19A-SAFETY-SCANNER-BLOCK",
                "label": BLOCKED_BY_SAFETY_GATE,
                "status": "blocked",
                "workflow_id": "safety_scanner",
                "summary": "Safety scanner findings block cycle release interpretation.",
            }
        )
    return tuple(outcomes)


def _dedupe_workflows(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for item in items:
        workflow_id = str(item.get("workflow_id", "workflow"))
        value = dict(item)
        value.setdefault("workflow_id", workflow_id)
        value.setdefault("label", BLOCKED_BY_SAFETY_GATE)
        value.setdefault("status", "blocked")
        value.setdefault("summary", "Workflow remains blocked.")
        _validate_json_value("blocked_workflow", value)
        by_id[workflow_id] = _normalize_json_value(value)
    return sorted(by_id.values(), key=lambda item: item["workflow_id"])


def _existing_paths(*paths: Path | None) -> list[str]:
    return [path.as_posix() for path in paths if path is not None and path.is_file()]


def _safety_boundary() -> dict[str, Any]:
    return {
        "label": HUMAN_REVIEW_REQUIRED,
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
    }


def _section(title: str, items: list[dict[str, Any]], id_key: str) -> list[str]:
    lines = [f"## {title}", ""]
    if not items:
        return [*lines, "- None recorded.", ""]
    for item in items:
        item_id = item.get(id_key) or item.get("step_id") or item.get("status") or "item"
        label = item.get("label", "n/a")
        status = item.get("status") or "recorded"
        summary = item.get("summary") or item.get("description") or "Recorded."
        lines.append(f"- {item_id} | {label} | {status} | {summary}")
    lines.append("")
    return lines


def _path_section(title: str, paths: list[str]) -> list[str]:
    lines = [f"## {title}", ""]
    if not paths:
        return [*lines, "- None recorded.", ""]
    lines.extend(f"- {path}" for path in paths)
    lines.append("")
    return lines


def _summary_line(label: str, count: int) -> str:
    return f"- {label}: {count}"


def _dataclass_payload(value: Any) -> dict[str, Any]:
    if not is_dataclass(value):
        raise ValueError("expected dataclass payload")
    return asdict(value)


def _validate_cycle_path(path: Path) -> None:
    if path.name == ".env":
        raise ValueError("research cycle runner cannot target secret files")
    lowered_parts = [part.lower() for part in path.parts]
    markers = ("credential", "credentials", "oauth", "password", "private_key", "secret", "secrets", "token")
    if any(marker in part for part in lowered_parts for marker in markers):
        raise ValueError("research cycle runner cannot target credential or secret paths")
    if path.is_absolute():
        raise ValueError("research cycle runner paths must be repo-relative")
    if ".." in path.parts:
        raise ValueError("research cycle runner paths cannot traverse parent directories")


def _parse_iso_datetime(field_name: str, value: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field_name} must include timezone information")


def _parse_iso_date(field_name: str, value: str) -> None:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"{field_name} must be YYYY-MM-DD") from exc


def _validate_json_value(field_name: str, value: Any) -> None:
    if isinstance(value, dict):
        label = value.get("label")
        if label is not None and label not in SAFE_RESEARCH_CYCLE_LABELS:
            raise ValueError(f"unsafe research cycle label: {label}")
        if label in DISALLOWED_RESEARCH_CYCLE_LABELS:
            raise ValueError(f"disallowed research cycle label: {label}")
        for unsafe_field in UNSAFE_TRUE_FIELDS:
            if value.get(unsafe_field) is True:
                raise ValueError(f"research cycle runner cannot set {unsafe_field}")
        for key, item in value.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError(f"{field_name} keys must be non-empty strings")
            _validate_json_value(f"{field_name}.{key}", item)
        return
    if isinstance(value, (tuple, list)):
        for item in value:
            _validate_json_value(field_name, item)
        return
    if isinstance(value, str):
        if value in DISALLOWED_RESEARCH_CYCLE_LABELS:
            raise ValueError(f"disallowed research cycle text: {value}")
        return
    if isinstance(value, (int, float, bool, type(None))):
        return
    raise ValueError(f"{field_name} must contain JSON-serializable values")


def _normalize_json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _normalize_json_value(value[key]) for key in sorted(value)}
    if isinstance(value, tuple):
        return [_normalize_json_value(item) for item in value]
    if isinstance(value, list):
        return [_normalize_json_value(item) for item in value]
    return value
