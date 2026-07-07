from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from core.operator_signoff_packet import DEFAULT_OPERATOR_SIGNOFF_PACKET_DIR, OPERATOR_SIGNOFF_PACKET_JSON
from core.report_index import REPORT_INDEX_JSON
from core.research_artifact_retention_policy import (
    DEFAULT_RESEARCH_ARTIFACT_RETENTION_POLICY_DIR,
    RESEARCH_ARTIFACT_RETENTION_POLICY_JSON,
)
from core.research_cycle_archive_index import (
    DEFAULT_RESEARCH_CYCLE_ARCHIVE_INDEX_DIR,
    RESEARCH_CYCLE_ARCHIVE_INDEX_JSON,
)
from core.research_cycle_readiness_gate import (
    DEFAULT_RESEARCH_CYCLE_READINESS_GATE_DIR,
    RESEARCH_CYCLE_READINESS_GATE_JSON,
)
from core.research_cycle_rollover_gate import (
    DEFAULT_RESEARCH_CYCLE_ROLLOVER_GATE_DIR,
    RESEARCH_CYCLE_ROLLOVER_GATE_JSON,
)
from core.research_next_cycle_plan import (
    DEFAULT_RESEARCH_NEXT_CYCLE_PLAN_DIR,
    RESEARCH_NEXT_CYCLE_PLAN_JSON,
)
from core.research_operations_console import (
    DEFAULT_RESEARCH_OPERATIONS_CONSOLE_DIR,
    RESEARCH_OPERATIONS_CONSOLE_JSON,
)
from core.safe_workflow_catalog import SAFE_WORKFLOW_CATALOG_JSON
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


DEFAULT_RESEARCH_NEXT_CYCLE_SAFETY_PREFLIGHT_DIR = Path("reports/research_next_cycle_safety_preflight")
RESEARCH_NEXT_CYCLE_SAFETY_PREFLIGHT_JSON = "research_next_cycle_safety_preflight.json"
RESEARCH_NEXT_CYCLE_SAFETY_PREFLIGHT_MARKDOWN = "research_next_cycle_safety_preflight.md"

PREFLIGHT_READY_FOR_HUMAN_REVIEW = "PREFLIGHT_READY_FOR_HUMAN_REVIEW"
NEEDS_OPERATOR_REVIEW = "NEEDS_OPERATOR_REVIEW"

SAFE_PREFLIGHT_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
PREFLIGHT_STATES = (
    PREFLIGHT_READY_FOR_HUMAN_REVIEW,
    NEEDS_OPERATOR_REVIEW,
    BLOCKED_BY_SAFETY_GATE,
)
DISALLOWED_PREFLIGHT_LABELS = tuple(
    verb + suffix
    for verb, suffix in (
        ("BUY", "_NOW"),
        ("SELL", "_NOW"),
        ("EXECUTE", "_TRADE"),
        ("AUTO", "_TRADE"),
    )
)
UNSAFE_TRUE_FIELDS = (
    "automatic_action_enabled",
    "broker_actions_created",
    "broker_call_used",
    "broker_order_call_performed",
    "broker_order_routing_enabled",
    "broker_routing_used",
    "credential_file_used",
    "execution_permissions_created",
    "live_trading_approval_granted",
    "live_trading_enabled",
    "next_cycle_started",
    "order_execution_used",
    "real_paper_order_submitted",
    "real_paper_wrapper_attempted",
    "real_paper_wrapper_connected",
    "research_workflow_run_started",
    "secrets_required",
    "trade_instructions_created",
)
SECRET_FILE_NAMES = {".env"}
SECRET_PATH_MARKERS = (
    "credential",
    "credentials",
    "oauth",
    "password",
    "private_key",
    "secret",
    "secrets",
    "token",
)
DATE_KEYS = (
    "preflight_date",
    "next_cycle_plan_date",
    "rollover_gate_date",
    "archive_index_date",
    "console_date",
    "signoff_date",
    "gate_date",
    "retention_date",
    "index_date",
    "catalog_date",
    "report_date",
)
OPERATOR_REVIEW_KEYS = (
    "operator_review_items",
    "unresolved_operator_review_items",
    "required_operator_actions",
    "required_next_human_review_actions",
    "open_items",
    "human_review_notes",
    "safety_preflight_items",
)


@dataclass(frozen=True)
class ResearchNextCycleSafetyPreflightInput:
    preflight_id: str
    preflight_date: str
    generated_at_utc: str
    next_cycle_plan_path: Path = DEFAULT_RESEARCH_NEXT_CYCLE_PLAN_DIR / RESEARCH_NEXT_CYCLE_PLAN_JSON
    rollover_gate_path: Path = DEFAULT_RESEARCH_CYCLE_ROLLOVER_GATE_DIR / RESEARCH_CYCLE_ROLLOVER_GATE_JSON
    archive_index_path: Path = DEFAULT_RESEARCH_CYCLE_ARCHIVE_INDEX_DIR / RESEARCH_CYCLE_ARCHIVE_INDEX_JSON
    operations_console_path: Path = DEFAULT_RESEARCH_OPERATIONS_CONSOLE_DIR / RESEARCH_OPERATIONS_CONSOLE_JSON
    operator_signoff_packet_path: Path = DEFAULT_OPERATOR_SIGNOFF_PACKET_DIR / OPERATOR_SIGNOFF_PACKET_JSON
    readiness_gate_path: Path = DEFAULT_RESEARCH_CYCLE_READINESS_GATE_DIR / RESEARCH_CYCLE_READINESS_GATE_JSON
    retention_policy_path: Path = (
        DEFAULT_RESEARCH_ARTIFACT_RETENTION_POLICY_DIR / RESEARCH_ARTIFACT_RETENTION_POLICY_JSON
    )
    report_index_path: Path = Path("reports/report_index") / REPORT_INDEX_JSON
    safe_workflow_catalog_path: Path = Path("reports/safe_workflow_catalog") / SAFE_WORKFLOW_CATALOG_JSON
    queue_status_path: Path = Path("config/jarvis_master_plan_queue.json")
    safety_scanner_path: Path = Path("reports/safety_scanner/safety_scanner_status.json")
    max_source_age_days: int = 1

    def validate(self) -> None:
        for field_name in ("preflight_id", "preflight_date", "generated_at_utc"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"research next cycle safety preflight requires {field_name}")
        _parse_iso_date("preflight_date", self.preflight_date)
        _parse_iso_datetime("generated_at_utc", self.generated_at_utc)
        if not isinstance(self.max_source_age_days, int) or self.max_source_age_days < 0:
            raise ValueError("max_source_age_days must be a non-negative integer")
        for path in (
            self.next_cycle_plan_path,
            self.rollover_gate_path,
            self.archive_index_path,
            self.operations_console_path,
            self.operator_signoff_packet_path,
            self.readiness_gate_path,
            self.retention_policy_path,
            self.report_index_path,
            self.safe_workflow_catalog_path,
            self.queue_status_path,
            self.safety_scanner_path,
        ):
            _validate_preflight_path(path)


def build_default_research_next_cycle_safety_preflight_input(
    *,
    preflight_date: date | None = None,
    now: datetime | None = None,
) -> ResearchNextCycleSafetyPreflightInput:
    generated = now or datetime.now(tz=UTC)
    day = preflight_date or generated.date()
    return ResearchNextCycleSafetyPreflightInput(
        preflight_id=f"25A-RESEARCH-NEXT-CYCLE-SAFETY-PREFLIGHT-{day.isoformat()}",
        preflight_date=day.isoformat(),
        generated_at_utc=generated.isoformat(),
    )


def build_research_next_cycle_safety_preflight_payload(
    preflight_input: ResearchNextCycleSafetyPreflightInput,
) -> dict[str, Any]:
    preflight_input.validate()
    preflight_day = datetime.strptime(preflight_input.preflight_date, "%Y-%m-%d").date()
    source_artifacts = _source_artifacts(preflight_input)
    source_payloads = {
        item["artifact_id"]: item["payload"]
        for item in source_artifacts
        if item["status"] == "present" and isinstance(item.get("payload"), dict)
    }
    next_cycle_plan_payload = source_payloads.get("next_cycle_plan", {})
    queue_status = _queue_status(preflight_input.queue_status_path)
    safety_scanner_status = _safety_scanner_status(preflight_input.safety_scanner_path)
    queue_next_phase = _queue_next_phase(queue_status, next_cycle_plan_payload)
    missing_artifacts = [item for item in source_artifacts if item["status"] != "present"]
    stale_artifacts = _stale_artifacts(source_artifacts, preflight_day, preflight_input.max_source_age_days)
    required_refreshed_artifacts = _required_refreshed_artifacts(missing_artifacts, stale_artifacts)
    safety_findings = _safety_findings(source_payloads, safety_scanner_status)
    blocked_prerequisites = _blocked_prerequisites(
        source_payloads=source_payloads,
        missing_artifacts=missing_artifacts,
        safety_findings=safety_findings,
        queue_status=queue_status,
        safety_scanner_status=safety_scanner_status,
    )
    unresolved_operator_review_items = _unresolved_operator_review_items(source_payloads)
    safety_preflight_items = _safety_preflight_items(
        source_payloads=source_payloads,
        safety_findings=safety_findings,
        safety_scanner_status=safety_scanner_status,
        queue_next_phase=queue_next_phase,
    )
    data_quality_checks = _data_quality_checks(source_artifacts, missing_artifacts, stale_artifacts)
    required_operator_actions = _required_operator_actions(
        blocked_prerequisites=blocked_prerequisites,
        required_refreshed_artifacts=required_refreshed_artifacts,
        unresolved_operator_review_items=unresolved_operator_review_items,
        safety_preflight_items=safety_preflight_items,
        data_quality_checks=data_quality_checks,
        queue_status=queue_status,
        safety_scanner_status=safety_scanner_status,
    )
    preflight_state = _preflight_state(
        missing_artifacts=missing_artifacts,
        stale_artifacts=stale_artifacts,
        blocked_prerequisites=blocked_prerequisites,
        unresolved_operator_review_items=unresolved_operator_review_items,
        safety_findings=safety_findings,
        queue_status=queue_status,
        safety_scanner_status=safety_scanner_status,
    )

    payload = {
        "phase": "25A",
        "workflow": "Next Cycle Safety Preflight",
        "preflight_id": preflight_input.preflight_id,
        "preflight_date": preflight_input.preflight_date,
        "generated_at_utc": preflight_input.generated_at_utc,
        "preflight_state": preflight_state,
        "safety_boundary": _safety_boundary(),
        "required_labels": [*SAFE_PREFLIGHT_LABELS, "LIVE TRADING: DISABLED"],
        "summary": {
            "source_artifact_count": len(source_artifacts),
            "present_source_artifact_count": len([item for item in source_artifacts if item["status"] == "present"]),
            "missing_artifact_count": len(missing_artifacts),
            "stale_artifact_count": len(stale_artifacts),
            "required_refreshed_artifact_count": len(required_refreshed_artifacts),
            "blocked_prerequisite_count": len(blocked_prerequisites),
            "unresolved_operator_review_item_count": len(unresolved_operator_review_items),
            "safety_preflight_item_count": len(safety_preflight_items),
            "data_quality_check_count": len(data_quality_checks),
            "safety_finding_count": len(safety_findings),
            "required_operator_action_count": len(required_operator_actions),
            "queue_status": queue_status["status"],
            "queue_next_phase": queue_next_phase.get("phase"),
            "safety_scanner_status": safety_scanner_status["status"],
            "label_counts": _count_by(
                [
                    *source_artifacts,
                    *missing_artifacts,
                    *stale_artifacts,
                    *required_refreshed_artifacts,
                    *blocked_prerequisites,
                    *unresolved_operator_review_items,
                    *safety_preflight_items,
                    *data_quality_checks,
                    *safety_findings,
                    *required_operator_actions,
                    queue_status,
                    safety_scanner_status,
                    queue_next_phase,
                ],
                "label",
            ),
        },
        "source_artifacts": [_without_payload(item) for item in source_artifacts],
        "blocked_prerequisites": blocked_prerequisites,
        "required_refreshed_artifacts": required_refreshed_artifacts,
        "unresolved_operator_review_items": unresolved_operator_review_items,
        "safety_preflight_items": safety_preflight_items,
        "data_quality_checks": data_quality_checks,
        "missing_artifacts": missing_artifacts,
        "stale_artifacts": stale_artifacts,
        "queue_next_phase": queue_next_phase,
        "queue_status": queue_status,
        "safety_scanner_status": safety_scanner_status,
        "safety_findings": safety_findings,
        "required_operator_actions": required_operator_actions,
        "final_preflight_summary": _final_preflight_summary(
            preflight_state=preflight_state,
            blocked_prerequisites=blocked_prerequisites,
            required_refreshed_artifacts=required_refreshed_artifacts,
            unresolved_operator_review_items=unresolved_operator_review_items,
            safety_preflight_items=safety_preflight_items,
            data_quality_checks=data_quality_checks,
            required_operator_actions=required_operator_actions,
        ),
    }
    _validate_json_value("research_next_cycle_safety_preflight_payload", payload)
    return _normalize_json_value(payload)


def write_research_next_cycle_safety_preflight(
    preflight_input: ResearchNextCycleSafetyPreflightInput,
    *,
    out_dir: Path = DEFAULT_RESEARCH_NEXT_CYCLE_SAFETY_PREFLIGHT_DIR,
) -> tuple[Path, Path]:
    payload = build_research_next_cycle_safety_preflight_payload(preflight_input)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / RESEARCH_NEXT_CYCLE_SAFETY_PREFLIGHT_JSON
    markdown_path = out_dir / RESEARCH_NEXT_CYCLE_SAFETY_PREFLIGHT_MARKDOWN
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_research_next_cycle_safety_preflight_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def render_research_next_cycle_safety_preflight_markdown(payload: dict[str, Any]) -> str:
    _validate_json_value("research_next_cycle_safety_preflight_payload", payload)
    lines = [
        "# 25A Next Cycle Safety Preflight",
        "",
        f"Preflight ID: {payload['preflight_id']}",
        f"Preflight Date: {payload['preflight_date']}",
        f"Generated: {payload['generated_at_utc']}",
        f"Preflight State: {payload['preflight_state']}",
        "",
        "Status: RESEARCH_ONLY / MONITOR_ONLY / PAPER_ONLY / HUMAN_REVIEW_REQUIRED / BLOCKED_BY_SAFETY_GATE.",
        "Next-cycle safety preflight reports are read-only and records-only.",
        "The next cycle is not started, artifacts are not mutated or deleted, and no research workflows are run.",
        "LIVE TRADING: DISABLED. No secrets, credential files, broker routing, broker calls, live trading, or order execution are used.",
        "",
        "## Final Preflight Summary",
        "",
        payload["final_preflight_summary"],
        "",
        "## Summary",
        "",
        _summary_line("Source artifacts", payload["summary"]["source_artifact_count"]),
        _summary_line("Present source artifacts", payload["summary"]["present_source_artifact_count"]),
        _summary_line("Missing artifacts", payload["summary"]["missing_artifact_count"]),
        _summary_line("Stale artifacts", payload["summary"]["stale_artifact_count"]),
        _summary_line("Required refreshed artifacts", payload["summary"]["required_refreshed_artifact_count"]),
        _summary_line("Blocked prerequisites", payload["summary"]["blocked_prerequisite_count"]),
        _summary_line("Unresolved operator review items", payload["summary"]["unresolved_operator_review_item_count"]),
        _summary_line("Safety preflight items", payload["summary"]["safety_preflight_item_count"]),
        _summary_line("Data-quality checks", payload["summary"]["data_quality_check_count"]),
        _summary_line("Required operator actions", payload["summary"]["required_operator_action_count"]),
        "",
    ]
    lines.extend(_section("Blocked Prerequisites", payload["blocked_prerequisites"]))
    lines.extend(_section("Required Refreshed Artifacts", payload["required_refreshed_artifacts"]))
    lines.extend(_section("Unresolved Operator Review Items", payload["unresolved_operator_review_items"]))
    lines.extend(_section("Safety Preflight Items", payload["safety_preflight_items"]))
    lines.extend(_section("Data-Quality Checks", payload["data_quality_checks"]))
    lines.extend(_section("Missing Artifacts", payload["missing_artifacts"]))
    lines.extend(_section("Stale Artifacts", payload["stale_artifacts"]))
    lines.extend(_section("Queue Next Phase", [payload["queue_next_phase"]]))
    lines.extend(_section("Queue Status", [payload["queue_status"]]))
    lines.extend(_section("Safety Scanner Status", [payload["safety_scanner_status"]]))
    lines.extend(_section("Required Operator Actions", payload["required_operator_actions"]))
    lines.extend(
        [
            "## Safety Boundary",
            "",
            "- RESEARCH_ONLY preflight generation only.",
            "- MONITOR_ONLY and PAPER_ONLY source artifacts are summarized, not executed.",
            "- HUMAN_REVIEW_REQUIRED items remain human-review records.",
            "- BLOCKED_BY_SAFETY_GATE prerequisites remain blocked.",
            "- Records-only preflight; no next-cycle start, artifact mutation, artifact deletion, broker action, trade instruction, execution permission, live-trading enablement, or research workflow run is created.",
            "- LIVE TRADING: DISABLED.",
            "",
        ]
    )
    return "\n".join(lines)


def _source_artifacts(preflight_input: ResearchNextCycleSafetyPreflightInput) -> list[dict[str, Any]]:
    artifact_paths = (
        ("next_cycle_plan", "24B Next Research Cycle Plan", preflight_input.next_cycle_plan_path),
        ("rollover_gate", "24A Research Cycle Rollover Gate", preflight_input.rollover_gate_path),
        ("archive_index", "23B Research Cycle Archive Index", preflight_input.archive_index_path),
        ("operations_console", "23A Research Operations Console", preflight_input.operations_console_path),
        ("operator_signoff_packet", "22B Operator Signoff Packet", preflight_input.operator_signoff_packet_path),
        ("readiness_gate", "20A Research Cycle Readiness Gate", preflight_input.readiness_gate_path),
        ("retention_policy", "20B Research Artifact Retention Policy", preflight_input.retention_policy_path),
        ("report_index", "Report Index", preflight_input.report_index_path),
        ("safe_workflow_catalog", "Safe Workflow Catalog", preflight_input.safe_workflow_catalog_path),
        ("safety_scanner_status", "Safety Scanner Status", preflight_input.safety_scanner_path),
    )
    statuses = []
    for artifact_id, name, path in artifact_paths:
        payload = _read_json_object(path)
        if payload is None:
            statuses.append(
                {
                    "artifact_id": artifact_id,
                    "name": name,
                    "label": BLOCKED_BY_SAFETY_GATE,
                    "status": "missing",
                    "summary": f"{name} JSON was not found or could not be parsed.",
                    "path": path.as_posix(),
                    "generated_date": None,
                    "generated_at_utc": None,
                    "phase": None,
                    "workflow": None,
                    "payload": {},
                }
            )
            continue
        _validate_json_value(artifact_id, payload)
        statuses.append(
            {
                "artifact_id": artifact_id,
                "name": name,
                "label": payload.get("safety_boundary", {}).get("label", payload.get("label", HUMAN_REVIEW_REQUIRED)),
                "status": "present",
                "summary": _artifact_summary(payload, f"{name} is present."),
                "path": path.as_posix(),
                "generated_date": _generated_date(payload),
                "generated_at_utc": payload.get("generated_at_utc"),
                "phase": payload.get("phase"),
                "workflow": payload.get("workflow", name),
                "payload": payload,
            }
        )
    return [_normalize_json_value(item) for item in statuses]


def _blocked_prerequisites(
    *,
    source_payloads: dict[str, dict[str, Any]],
    missing_artifacts: list[dict[str, Any]],
    safety_findings: list[dict[str, Any]],
    queue_status: dict[str, Any],
    safety_scanner_status: dict[str, Any],
) -> list[dict[str, Any]]:
    items = [
        _blocked(f"missing_{item['artifact_id']}", f"{item['name']} must be present before next-cycle preflight can pass.")
        for item in missing_artifacts
    ]
    if safety_findings or safety_scanner_status.get("passed") is False:
        items.append(_blocked("safety_findings_unresolved", "Safety findings must be resolved while live trading remains disabled."))
    if queue_status.get("label") == BLOCKED_BY_SAFETY_GATE:
        items.append(_blocked("queue_status_unavailable", "Master plan queue must be readable before next-cycle preflight can pass."))
    state_expectations = {
        "next_cycle_plan": ("next_cycle_plan_state", {"NEXT_CYCLE_PLAN_READY_FOR_HUMAN_REVIEW", "NEXT_CYCLE_PLAN_NEEDS_OPERATOR_REVIEW"}),
        "rollover_gate": ("rollover_state", {"ROLLOVER_READY_FOR_HUMAN_REVIEW", "NEEDS_OPERATOR_REVIEW"}),
        "archive_index": ("archive_index_state", {"ARCHIVE_INDEX_COMPLETE_RECORDS_ONLY", "ARCHIVE_INDEX_NEEDS_HUMAN_REVIEW"}),
        "operations_console": ("console_state", {"OPERATIONS_CONSOLE_COMPLETE_RECORDS_ONLY", "OPERATIONS_CONSOLE_NEEDS_OPERATOR_REVIEW"}),
        "operator_signoff_packet": ("signoff_state", {"SIGNOFF_PACKET_COMPLETE_RECORDS_ONLY", "SIGNOFF_PACKET_NEEDS_OPERATOR_REVIEW"}),
    }
    for artifact_id, (state_key, allowed_states) in state_expectations.items():
        payload = source_payloads.get(artifact_id, {})
        state = payload.get(state_key)
        if state == BLOCKED_BY_SAFETY_GATE or (isinstance(state, str) and state.endswith("BLOCKED_BY_SAFETY_GATE")):
            items.append(_blocked(f"{artifact_id}_blocked_state", f"{artifact_id} reports blocked state {state}."))
        elif state is not None and state not in allowed_states:
            items.append(_blocked(f"{artifact_id}_unexpected_state", f"{artifact_id} reports unexpected state {state}."))
    return _dedupe_by_id(items, "prerequisite_id")


def _required_refreshed_artifacts(
    missing_artifacts: list[dict[str, Any]],
    stale_artifacts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    items = []
    for item in missing_artifacts:
        items.append(_refresh(f"25A-REFRESH-MISSING-{item['artifact_id']}", item["artifact_id"], item["summary"], BLOCKED_BY_SAFETY_GATE))
    for item in stale_artifacts:
        items.append(_refresh(f"25A-REFRESH-STALE-{item['artifact_id']}", item["artifact_id"], item["summary"]))
    return _dedupe_by_id(items, "refresh_id")


def _unresolved_operator_review_items(source_payloads: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    items = []
    for artifact_id, payload in source_payloads.items():
        for key in OPERATOR_REVIEW_KEYS:
            for item in _items_from_payload(payload, key):
                status = str(item.get("status") or item.get("review_status") or "open_review_item")
                if status in {"acknowledged", "noted", "complete", "completed"}:
                    continue
                value = _item(item, "review_item_id", key)
                value["review_item_id"] = str(value.get("review_item_id") or value.get("action_id") or value.get("workflow_id") or key)
                value["review_item_id"] = f"{artifact_id}_{value['review_item_id']}"
                value["label"] = value.get("label", HUMAN_REVIEW_REQUIRED)
                value["status"] = status
                value["source_artifact_id"] = artifact_id
                items.append(value)
    return _dedupe_by_id(items, "review_item_id")


def _safety_preflight_items(
    *,
    source_payloads: dict[str, dict[str, Any]],
    safety_findings: list[dict[str, Any]],
    safety_scanner_status: dict[str, Any],
    queue_next_phase: dict[str, Any],
) -> list[dict[str, Any]]:
    items = [
        _preflight("25A-PREFLIGHT-RECORDS-ONLY", "Confirm 25A is records-only and does not start the next cycle.", RESEARCH_ONLY),
        _preflight("25A-PREFLIGHT-LIVE-TRADING-DISABLED", "Confirm LIVE TRADING: DISABLED and no broker action can be created.", HUMAN_REVIEW_REQUIRED),
        _preflight("25A-PREFLIGHT-QUEUE-NEXT-PHASE", f"Queue next phase recorded as {queue_next_phase.get('phase')}.", HUMAN_REVIEW_REQUIRED),
        _preflight("25A-PREFLIGHT-SAFETY-SCANNER", safety_scanner_status.get("summary", "Safety scanner status recorded."), BLOCKED_BY_SAFETY_GATE if safety_findings or safety_scanner_status.get("passed") is False else HUMAN_REVIEW_REQUIRED),
    ]
    plan_payload = source_payloads.get("next_cycle_plan", {})
    for item in _items_from_payload(plan_payload, "safety_preflight_items"):
        value = _item(item, "preflight_id", "24b_safety_preflight")
        value["preflight_id"] = f"24B-{value.get('preflight_id', 'PREFLIGHT')}"
        value["source_artifact_id"] = "next_cycle_plan"
        items.append(value)
    return _dedupe_by_id(items, "preflight_id")


def _data_quality_checks(
    source_artifacts: list[dict[str, Any]],
    missing_artifacts: list[dict[str, Any]],
    stale_artifacts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return _dedupe_by_id(
        [
            _check("25A-DQ-SOURCE-ARTIFACTS-PRESENT", f"Present source artifacts: {len([item for item in source_artifacts if item['status'] == 'present'])}/{len(source_artifacts)}.", BLOCKED_BY_SAFETY_GATE if missing_artifacts else MONITOR_ONLY),
            _check("25A-DQ-SOURCE-ARTIFACTS-FRESH", f"Stale or unknown-date artifacts: {len(stale_artifacts)}.", HUMAN_REVIEW_REQUIRED if stale_artifacts else MONITOR_ONLY),
            _check("25A-DQ-JSON-DETERMINISM", "Payload is normalized and sorted before write.", RESEARCH_ONLY),
            _check("25A-DQ-SOURCE-PAYLOADS-OMITTED", "Embedded source payloads are omitted from source_artifacts in output.", RESEARCH_ONLY),
        ],
        "check_id",
    )


def _required_operator_actions(
    *,
    blocked_prerequisites: list[dict[str, Any]],
    required_refreshed_artifacts: list[dict[str, Any]],
    unresolved_operator_review_items: list[dict[str, Any]],
    safety_preflight_items: list[dict[str, Any]],
    data_quality_checks: list[dict[str, Any]],
    queue_status: dict[str, Any],
    safety_scanner_status: dict[str, Any],
) -> list[dict[str, Any]]:
    actions = [_action("25A-REVIEW-SAFETY-PREFLIGHT", "Review 25A before starting any next-cycle work.")]
    if blocked_prerequisites:
        actions.append(_action("25A-RESOLVE-BLOCKED-PREREQUISITES", "Resolve blocked prerequisites while keeping safety gates active."))
    if required_refreshed_artifacts:
        actions.append(_action("25A-REFRESH-REQUIRED-ARTIFACTS", "Refresh or explicitly accept required source artifacts."))
    if unresolved_operator_review_items:
        actions.append(_action("25A-RESOLVE-OPERATOR-REVIEW", "Resolve unresolved operator review items."))
    if any(item.get("label") == BLOCKED_BY_SAFETY_GATE for item in safety_preflight_items) or safety_scanner_status.get("passed") is False:
        actions.append(_action("25A-RESOLVE-SAFETY-PREFLIGHT", "Resolve safety preflight items while live trading remains disabled."))
    if any(item.get("label") == BLOCKED_BY_SAFETY_GATE for item in data_quality_checks):
        actions.append(_action("25A-RESOLVE-DATA-QUALITY", "Resolve blocked data-quality checks."))
    if queue_status.get("label") == BLOCKED_BY_SAFETY_GATE:
        actions.append(_action("25A-REVIEW-QUEUE-STATUS", "Review missing or invalid master plan queue status."))
    return _dedupe_by_id(actions, "action_id")


def _preflight_state(
    *,
    missing_artifacts: list[dict[str, Any]],
    stale_artifacts: list[dict[str, Any]],
    blocked_prerequisites: list[dict[str, Any]],
    unresolved_operator_review_items: list[dict[str, Any]],
    safety_findings: list[dict[str, Any]],
    queue_status: dict[str, Any],
    safety_scanner_status: dict[str, Any],
) -> str:
    if (
        missing_artifacts
        or blocked_prerequisites
        or safety_findings
        or queue_status.get("label") == BLOCKED_BY_SAFETY_GATE
        or safety_scanner_status.get("passed") is False
    ):
        return BLOCKED_BY_SAFETY_GATE
    if stale_artifacts or unresolved_operator_review_items:
        return NEEDS_OPERATOR_REVIEW
    return PREFLIGHT_READY_FOR_HUMAN_REVIEW


def _safety_findings(
    source_payloads: dict[str, dict[str, Any]],
    safety_scanner_status: dict[str, Any],
) -> list[dict[str, Any]]:
    items = []
    for artifact_id, payload in source_payloads.items():
        for item in _items_from_payload(payload, "safety_findings"):
            value = {
                "finding_id": item.get("finding_id") or item.get("rule_id") or item.get("workflow_id") or "safety_finding",
                "workflow_id": item.get("workflow_id", artifact_id),
                "label": BLOCKED_BY_SAFETY_GATE,
                "status": item.get("status", "failed"),
                "summary": item.get("summary", "Safety finding recorded by source artifact."),
                "source_artifact_id": artifact_id,
            }
            _validate_json_value("safety_finding", value)
            items.append(value)
    if safety_scanner_status.get("passed") is False or safety_scanner_status.get("label") == BLOCKED_BY_SAFETY_GATE:
        items.append(
            {
                "finding_id": "safety_scanner_status",
                "workflow_id": "safety_scanner",
                "label": BLOCKED_BY_SAFETY_GATE,
                "status": safety_scanner_status.get("status", "failed"),
                "summary": safety_scanner_status.get("summary", "Safety scanner status requires review."),
                "source_artifact_id": "safety_scanner_status",
            }
        )
    for finding in safety_scanner_status.get("findings", []):
        if not isinstance(finding, dict):
            continue
        items.append(
            {
                "finding_id": finding.get("rule_id") or finding.get("finding_id") or "safety_finding",
                "workflow_id": "safety_scanner",
                "label": BLOCKED_BY_SAFETY_GATE,
                "status": "failed",
                "summary": finding.get("summary") or finding.get("message") or "Safety scanner finding recorded.",
                "source_artifact_id": "safety_scanner_status",
            }
        )
    return _dedupe_by_id(items, "finding_id")


def _queue_status(path: Path) -> dict[str, Any]:
    payload = _read_json_value(path)
    if payload is None:
        return {
            "workflow_id": "master_plan_queue",
            "label": BLOCKED_BY_SAFETY_GATE,
            "status": "missing",
            "summary": "Master plan queue JSON was not found or could not be parsed.",
            "path": path.as_posix(),
            "queue_item_count": 0,
            "next_phase": None,
            "items": [],
        }
    if not isinstance(payload, list):
        return {
            "workflow_id": "master_plan_queue",
            "label": BLOCKED_BY_SAFETY_GATE,
            "status": "invalid",
            "summary": "Master plan queue root is not a list.",
            "path": path.as_posix(),
            "queue_item_count": 0,
            "next_phase": None,
            "items": [],
        }
    items = [_queue_item(item) for item in payload if isinstance(item, dict)]
    value = {
        "workflow_id": "master_plan_queue",
        "label": HUMAN_REVIEW_REQUIRED,
        "status": "read_only",
        "summary": "Master plan queue read for 25A next-cycle safety preflight context only.",
        "path": path.as_posix(),
        "queue_item_count": len(items),
        "next_phase": _next_phase(items),
        "items": items,
    }
    _validate_json_value("queue_status", value)
    return _normalize_json_value(value)


def _safety_scanner_status(path: Path) -> dict[str, Any]:
    payload = _read_json_object(path)
    if payload is None:
        return {
            "workflow_id": "safety_scanner",
            "label": HUMAN_REVIEW_REQUIRED,
            "status": "not_run",
            "summary": "Safety scanner status was not supplied to 25A.",
            "path": path.as_posix(),
            "finding_count": 0,
            "passed": None,
            "findings": [],
        }
    findings = payload.get("findings", [])
    passed = payload.get("passed")
    value = {
        "workflow_id": "safety_scanner",
        "label": payload.get("label", HUMAN_REVIEW_REQUIRED if passed is not False else BLOCKED_BY_SAFETY_GATE),
        "status": payload.get("status", "passed" if passed else "not_run"),
        "summary": payload.get("summary", "Safety scanner status supplied to 25A."),
        "path": path.as_posix(),
        "finding_count": payload.get("finding_count", len(findings) if isinstance(findings, list) else 0),
        "passed": passed,
        "findings": findings if isinstance(findings, list) else [],
    }
    _validate_json_value("safety_scanner_status", value)
    return _normalize_json_value(value)


def _queue_next_phase(queue_status: dict[str, Any], next_cycle_plan_payload: dict[str, Any]) -> dict[str, Any]:
    next_phase = queue_status.get("next_phase")
    planned = next_cycle_plan_payload.get("planned_research_report_workflows", [])
    if isinstance(planned, list):
        for item in planned:
            if isinstance(item, dict) and item.get("phase"):
                next_phase = item
                break
    if not isinstance(next_phase, dict):
        return {
            "workflow_id": "queue_next_phase",
            "label": HUMAN_REVIEW_REQUIRED,
            "status": "requires_operator_review",
            "phase": None,
            "title": "Next phase not selected",
            "summary": "No queue next phase was available for 25A.",
            "run_started": False,
        }
    value = {
        "workflow_id": "queue_next_phase",
        "label": HUMAN_REVIEW_REQUIRED,
        "status": "planned_not_started",
        "phase": next_phase.get("phase"),
        "title": next_phase.get("title"),
        "summary": next_phase.get("summary") or next_phase.get("spec") or "Queue next phase recorded.",
        "run_started": False,
    }
    _validate_json_value("queue_next_phase", value)
    return _normalize_json_value(value)


def _queue_item(item: dict[str, Any]) -> dict[str, Any]:
    value = {
        "phase": item.get("phase"),
        "title": item.get("title"),
        "label": HUMAN_REVIEW_REQUIRED,
        "status": "queued",
        "summary": item.get("spec", "Queued roadmap item."),
    }
    _validate_json_value("queue_item", value)
    return _normalize_json_value(value)


def _next_phase(items: list[dict[str, Any]]) -> dict[str, Any] | None:
    for item in items:
        if item.get("phase") == "25A":
            return item
    return items[0] if items else None


def _safety_boundary() -> dict[str, Any]:
    return {
        "label": HUMAN_REVIEW_REQUIRED,
        "research_only": True,
        "monitor_only": True,
        "paper_only": True,
        "human_review_required": True,
        "records_only": True,
        "read_only": True,
        "next_cycle_started": False,
        "research_workflow_run_started": False,
        "artifact_delete_performed": False,
        "artifact_mutation_performed": False,
        "trade_instructions_created": False,
        "broker_actions_created": False,
        "execution_permissions_created": False,
        "automatic_action_enabled": False,
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
    }


def _final_preflight_summary(
    *,
    preflight_state: str,
    blocked_prerequisites: list[dict[str, Any]],
    required_refreshed_artifacts: list[dict[str, Any]],
    unresolved_operator_review_items: list[dict[str, Any]],
    safety_preflight_items: list[dict[str, Any]],
    data_quality_checks: list[dict[str, Any]],
    required_operator_actions: list[dict[str, Any]],
) -> str:
    return (
        f"Next-cycle safety preflight state is {preflight_state}. "
        f"Blocked prerequisites: {len(blocked_prerequisites)}. "
        f"Required refreshed artifacts: {len(required_refreshed_artifacts)}. "
        f"Unresolved operator review items: {len(unresolved_operator_review_items)}. "
        f"Safety preflight items: {len(safety_preflight_items)}. "
        f"Data-quality checks: {len(data_quality_checks)}. "
        f"Required operator actions: {len(required_operator_actions)}. "
        "Safety boundary confirmed: 25A is read-only and records-only and does not start the next cycle, mutate artifacts, delete artifacts, create broker actions, create trade instructions, enable live trading, grant execution permissions, or run research workflows. "
        "LIVE TRADING: DISABLED."
    )


def _refresh(refresh_id: str, artifact_id: str, summary: str, label: str = HUMAN_REVIEW_REQUIRED) -> dict[str, Any]:
    return {
        "refresh_id": refresh_id,
        "artifact_id": artifact_id,
        "label": label,
        "status": "required_before_next_cycle",
        "summary": summary,
    }


def _blocked(prerequisite_id: str, summary: str) -> dict[str, Any]:
    return {
        "prerequisite_id": prerequisite_id,
        "label": BLOCKED_BY_SAFETY_GATE,
        "status": "blocked",
        "summary": summary,
    }


def _preflight(preflight_id: str, summary: str, label: str = HUMAN_REVIEW_REQUIRED) -> dict[str, Any]:
    return {
        "preflight_id": preflight_id,
        "label": label,
        "status": "required_before_next_cycle",
        "summary": summary,
    }


def _check(check_id: str, summary: str, label: str) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "label": label,
        "status": "required_before_next_cycle",
        "summary": summary,
    }


def _action(action_id: str, summary: str) -> dict[str, Any]:
    return {
        "action_id": action_id,
        "workflow_id": action_id.lower().replace("-", "_"),
        "label": HUMAN_REVIEW_REQUIRED,
        "status": "open_review_item",
        "summary": summary,
    }


def _item(item: dict[str, Any], id_key: str, fallback_id: str) -> dict[str, Any]:
    value = dict(item)
    value.setdefault(id_key, value.get("workflow_id") or value.get("action_id") or value.get("artifact_id") or fallback_id)
    value.setdefault("label", HUMAN_REVIEW_REQUIRED)
    value.setdefault("summary", "25A preflight item recorded.")
    _validate_json_value("preflight_item", value)
    return _normalize_json_value(value)


def _items_from_payload(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    values = payload.get(key, [])
    if not isinstance(values, list):
        return []
    return [item for item in values if isinstance(item, dict)]


def _without_payload(item: dict[str, Any]) -> dict[str, Any]:
    value = {key: field for key, field in item.items() if key != "payload"}
    _validate_json_value("source_artifact_without_payload", value)
    return _normalize_json_value(value)


def _artifact_summary(payload: dict[str, Any], fallback: str) -> str:
    summary = payload.get("summary") if isinstance(payload, dict) else None
    if not isinstance(summary, dict):
        return fallback
    counts = [
        f"{key}={summary[key]}"
        for key in sorted(summary)
        if key.endswith("_count") and isinstance(summary[key], int)
    ]
    workflow = payload.get("workflow", "Artifact")
    return f"{workflow} status: {', '.join(counts[:4]) if counts else 'metadata recorded'}."


def _stale_artifacts(
    source_artifacts: list[dict[str, Any]],
    preflight_day: date,
    max_source_age_days: int,
) -> list[dict[str, Any]]:
    stale = []
    for item in source_artifacts:
        if item["status"] != "present":
            continue
        age_days = _age_days(preflight_day, item.get("generated_date"))
        if age_days is None or age_days > max_source_age_days:
            value = {
                "artifact_id": item["artifact_id"],
                "name": item["name"],
                "label": HUMAN_REVIEW_REQUIRED,
                "status": "stale_or_unknown_date",
                "summary": f"{item['name']} is stale or has no recognized generated date.",
                "path": item["path"],
                "generated_date": item.get("generated_date"),
                "age_days": age_days,
            }
            _validate_json_value("stale_artifact", value)
            stale.append(value)
    return _dedupe_by_id(stale, "artifact_id")


def _read_json_object(path: Path) -> dict[str, Any] | None:
    value = _read_json_value(path)
    return value if isinstance(value, dict) else None


def _read_json_value(path: Path) -> Any:
    _validate_preflight_path(path)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def _generated_date(payload: dict[str, Any]) -> str | None:
    for key in DATE_KEYS:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value[:10]
    generated_at = payload.get("generated_at_utc")
    if isinstance(generated_at, str) and len(generated_at) >= 10:
        return generated_at[:10]
    return None


def _age_days(preflight_day: date, generated_date: str | None) -> int | None:
    if generated_date is None:
        return None
    try:
        generated_day = datetime.strptime(generated_date, "%Y-%m-%d").date()
    except ValueError:
        return None
    return (preflight_day - generated_day).days


def _section(title: str, items: list[dict[str, Any]]) -> list[str]:
    lines = [f"## {title}", ""]
    if not items:
        return [*lines, "- None recorded.", ""]
    for item in items:
        item_id = (
            item.get("workflow_id")
            or item.get("refresh_id")
            or item.get("prerequisite_id")
            or item.get("review_item_id")
            or item.get("preflight_id")
            or item.get("check_id")
            or item.get("action_id")
            or item.get("artifact_id")
            or item.get("finding_id")
            or item.get("phase")
            or item.get("status")
            or "item"
        )
        label = item.get("label", "n/a")
        status = item.get("status", "recorded")
        summary = item.get("summary") or item.get("title") or item.get("name") or "Recorded."
        lines.append(f"- {item_id} | {label} | {status} | {summary}")
    lines.append("")
    return lines


def _summary_line(label: str, count: int) -> str:
    return f"- {label}: {count}"


def _count_by(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(key, "unknown"))
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _dedupe_by_id(items: list[dict[str, Any]], id_key: str) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for item in items:
        value = dict(item)
        value.setdefault(id_key, "item")
        _validate_json_value(id_key, value)
        by_id[str(value[id_key])] = _normalize_json_value(value)
    return sorted(by_id.values(), key=_sort_key)


def _sort_key(item: dict[str, Any]) -> tuple[str, str]:
    return (
        str(item.get("source_artifact_id", item.get("source", ""))),
        str(
            item.get("workflow_id")
            or item.get("refresh_id")
            or item.get("prerequisite_id")
            or item.get("review_item_id")
            or item.get("preflight_id")
            or item.get("check_id")
            or item.get("action_id")
            or item.get("artifact_id")
            or item.get("finding_id")
            or item.get("phase")
            or item.get("status")
            or json.dumps(item, sort_keys=True)
        ),
    )


def _validate_preflight_path(path: Path) -> None:
    if path.name in SECRET_FILE_NAMES:
        raise ValueError("research next cycle safety preflight cannot target secret files")
    lowered_parts = [part.lower() for part in path.parts]
    if any(marker in part for part in lowered_parts for marker in SECRET_PATH_MARKERS):
        raise ValueError("research next cycle safety preflight cannot target credential or secret paths")
    if path.is_absolute():
        raise ValueError("research next cycle safety preflight paths must be repo-relative")
    if ".." in path.parts:
        raise ValueError("research next cycle safety preflight paths cannot traverse parent directories")


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
        if label is not None and label not in SAFE_PREFLIGHT_LABELS:
            raise ValueError(f"unsafe research next cycle safety preflight label: {label}")
        preflight_state = value.get("preflight_state")
        if preflight_state is not None and preflight_state not in PREFLIGHT_STATES:
            raise ValueError(f"invalid research next cycle safety preflight state: {preflight_state}")
        for unsafe_field in UNSAFE_TRUE_FIELDS:
            if value.get(unsafe_field) is True:
                raise ValueError(f"research next cycle safety preflight cannot set {unsafe_field}")
        for mutation_field in ("artifact_delete_performed", "artifact_mutation_performed"):
            if value.get(mutation_field) is True:
                raise ValueError(f"research next cycle safety preflight cannot set {mutation_field}")
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
        if value in DISALLOWED_PREFLIGHT_LABELS:
            raise ValueError(f"disallowed research next cycle safety preflight text: {value}")
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
