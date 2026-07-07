from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from core.operator_signoff_packet import (
    DEFAULT_OPERATOR_SIGNOFF_PACKET_DIR,
    OPERATOR_SIGNOFF_PACKET_JSON,
)
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


DEFAULT_RESEARCH_NEXT_CYCLE_PLAN_DIR = Path("reports/research_next_cycle_plan")
RESEARCH_NEXT_CYCLE_PLAN_JSON = "research_next_cycle_plan.json"
RESEARCH_NEXT_CYCLE_PLAN_MARKDOWN = "research_next_cycle_plan.md"

NEXT_CYCLE_PLAN_READY_FOR_HUMAN_REVIEW = "NEXT_CYCLE_PLAN_READY_FOR_HUMAN_REVIEW"
NEXT_CYCLE_PLAN_NEEDS_OPERATOR_REVIEW = "NEXT_CYCLE_PLAN_NEEDS_OPERATOR_REVIEW"

SAFE_NEXT_CYCLE_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
NEXT_CYCLE_PLAN_STATES = (
    NEXT_CYCLE_PLAN_READY_FOR_HUMAN_REVIEW,
    NEXT_CYCLE_PLAN_NEEDS_OPERATOR_REVIEW,
    BLOCKED_BY_SAFETY_GATE,
)
DISALLOWED_NEXT_CYCLE_LABELS = tuple(
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


@dataclass(frozen=True)
class ResearchNextCyclePlanInput:
    next_cycle_plan_id: str
    next_cycle_plan_date: str
    generated_at_utc: str
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
        for field_name in ("next_cycle_plan_id", "next_cycle_plan_date", "generated_at_utc"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"research next cycle plan requires {field_name}")
        _parse_iso_date("next_cycle_plan_date", self.next_cycle_plan_date)
        _parse_iso_datetime("generated_at_utc", self.generated_at_utc)
        if not isinstance(self.max_source_age_days, int) or self.max_source_age_days < 0:
            raise ValueError("max_source_age_days must be a non-negative integer")
        for path in (
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
            _validate_next_cycle_path(path)


def build_default_research_next_cycle_plan_input(
    *,
    next_cycle_plan_date: date | None = None,
    now: datetime | None = None,
) -> ResearchNextCyclePlanInput:
    generated = now or datetime.now(tz=UTC)
    day = next_cycle_plan_date or generated.date()
    return ResearchNextCyclePlanInput(
        next_cycle_plan_id=f"24B-RESEARCH-NEXT-CYCLE-PLAN-{day.isoformat()}",
        next_cycle_plan_date=day.isoformat(),
        generated_at_utc=generated.isoformat(),
    )


def build_research_next_cycle_plan_payload(plan_input: ResearchNextCyclePlanInput) -> dict[str, Any]:
    plan_input.validate()
    plan_day = datetime.strptime(plan_input.next_cycle_plan_date, "%Y-%m-%d").date()
    source_artifacts = _source_artifacts(plan_input)
    source_payloads = {
        item["artifact_id"]: item["payload"]
        for item in source_artifacts
        if item["status"] == "present" and isinstance(item.get("payload"), dict)
    }
    queue_status = _queue_status(plan_input.queue_status_path)
    safety_scanner_status = _safety_scanner_status(plan_input.safety_scanner_path)
    missing_artifacts = [item for item in source_artifacts if item["status"] != "present"]
    stale_artifacts = _stale_artifacts(source_artifacts, plan_day, plan_input.max_source_age_days)
    safety_findings = _safety_findings(source_payloads, safety_scanner_status)
    planned_workflows = _planned_workflows(queue_status)
    required_refreshed_artifacts = _required_refreshed_artifacts(missing_artifacts, stale_artifacts)
    blocked_prerequisites = _blocked_prerequisites(
        source_payloads=source_payloads,
        missing_artifacts=missing_artifacts,
        safety_findings=safety_findings,
        queue_status=queue_status,
        safety_scanner_status=safety_scanner_status,
    )
    operator_review_items = _operator_review_items(source_payloads)
    safety_preflight_items = _safety_preflight_items(safety_scanner_status, safety_findings)
    data_quality_checks = _data_quality_checks(source_artifacts, missing_artifacts, stale_artifacts)
    acceptance_criteria = _acceptance_criteria(
        blocked_prerequisites=blocked_prerequisites,
        operator_review_items=operator_review_items,
        safety_preflight_items=safety_preflight_items,
        data_quality_checks=data_quality_checks,
    )
    next_cycle_plan_state = _next_cycle_plan_state(
        missing_artifacts=missing_artifacts,
        stale_artifacts=stale_artifacts,
        safety_findings=safety_findings,
        blocked_prerequisites=blocked_prerequisites,
        operator_review_items=operator_review_items,
        queue_status=queue_status,
        safety_scanner_status=safety_scanner_status,
    )

    payload = {
        "phase": "24B",
        "workflow": "Next Research Cycle Plan",
        "next_cycle_plan_id": plan_input.next_cycle_plan_id,
        "next_cycle_plan_date": plan_input.next_cycle_plan_date,
        "generated_at_utc": plan_input.generated_at_utc,
        "next_cycle_plan_state": next_cycle_plan_state,
        "safety_boundary": _safety_boundary(),
        "required_labels": [*SAFE_NEXT_CYCLE_LABELS, "LIVE TRADING: DISABLED"],
        "summary": {
            "source_artifact_count": len(source_artifacts),
            "present_source_artifact_count": len([item for item in source_artifacts if item["status"] == "present"]),
            "missing_artifact_count": len(missing_artifacts),
            "stale_artifact_count": len(stale_artifacts),
            "planned_workflow_count": len(planned_workflows),
            "required_refreshed_artifact_count": len(required_refreshed_artifacts),
            "blocked_prerequisite_count": len(blocked_prerequisites),
            "operator_review_item_count": len(operator_review_items),
            "safety_preflight_item_count": len(safety_preflight_items),
            "data_quality_check_count": len(data_quality_checks),
            "acceptance_criteria_count": len(acceptance_criteria),
            "safety_finding_count": len(safety_findings),
            "queue_status": queue_status["status"],
            "safety_scanner_status": safety_scanner_status["status"],
            "label_counts": _count_by(
                [
                    *source_artifacts,
                    *missing_artifacts,
                    *stale_artifacts,
                    *planned_workflows,
                    *required_refreshed_artifacts,
                    *blocked_prerequisites,
                    *operator_review_items,
                    *safety_preflight_items,
                    *data_quality_checks,
                    *acceptance_criteria,
                    *safety_findings,
                    queue_status,
                    safety_scanner_status,
                ],
                "label",
            ),
        },
        "source_artifacts": [_without_payload(item) for item in source_artifacts],
        "planned_research_report_workflows": planned_workflows,
        "required_refreshed_artifacts": required_refreshed_artifacts,
        "blocked_prerequisites": blocked_prerequisites,
        "operator_review_items": operator_review_items,
        "safety_preflight_items": safety_preflight_items,
        "data_quality_checks": data_quality_checks,
        "next_cycle_acceptance_criteria": acceptance_criteria,
        "missing_artifacts": missing_artifacts,
        "stale_artifacts": stale_artifacts,
        "queue_status": queue_status,
        "safety_scanner_status": safety_scanner_status,
        "safety_findings": safety_findings,
        "final_next_cycle_plan_summary": _final_next_cycle_plan_summary(
            next_cycle_plan_state=next_cycle_plan_state,
            planned_workflows=planned_workflows,
            required_refreshed_artifacts=required_refreshed_artifacts,
            blocked_prerequisites=blocked_prerequisites,
            operator_review_items=operator_review_items,
            safety_preflight_items=safety_preflight_items,
            data_quality_checks=data_quality_checks,
            acceptance_criteria=acceptance_criteria,
        ),
    }
    _validate_json_value("research_next_cycle_plan_payload", payload)
    return _normalize_json_value(payload)


def write_research_next_cycle_plan(
    plan_input: ResearchNextCyclePlanInput,
    *,
    out_dir: Path = DEFAULT_RESEARCH_NEXT_CYCLE_PLAN_DIR,
) -> tuple[Path, Path]:
    payload = build_research_next_cycle_plan_payload(plan_input)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / RESEARCH_NEXT_CYCLE_PLAN_JSON
    markdown_path = out_dir / RESEARCH_NEXT_CYCLE_PLAN_MARKDOWN
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_research_next_cycle_plan_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def render_research_next_cycle_plan_markdown(payload: dict[str, Any]) -> str:
    _validate_json_value("research_next_cycle_plan_payload", payload)
    lines = [
        "# 24B Next Research Cycle Plan",
        "",
        f"Next Cycle Plan ID: {payload['next_cycle_plan_id']}",
        f"Next Cycle Plan Date: {payload['next_cycle_plan_date']}",
        f"Generated: {payload['generated_at_utc']}",
        f"Next Cycle Plan State: {payload['next_cycle_plan_state']}",
        "",
        "Status: RESEARCH_ONLY / MONITOR_ONLY / PAPER_ONLY / HUMAN_REVIEW_REQUIRED / BLOCKED_BY_SAFETY_GATE.",
        "Next-cycle planning reports are read-only and records-only.",
        "The next cycle is not started, artifacts are not mutated or deleted, and no execution permissions are created.",
        "LIVE TRADING: DISABLED. No secrets, credential files, broker routing, broker calls, live trading, or order execution are used.",
        "",
        "## Final Next-Cycle Plan Summary",
        "",
        payload["final_next_cycle_plan_summary"],
        "",
        "## Summary",
        "",
        _summary_line("Source artifacts", payload["summary"]["source_artifact_count"]),
        _summary_line("Present source artifacts", payload["summary"]["present_source_artifact_count"]),
        _summary_line("Missing artifacts", payload["summary"]["missing_artifact_count"]),
        _summary_line("Stale artifacts", payload["summary"]["stale_artifact_count"]),
        _summary_line("Planned workflows", payload["summary"]["planned_workflow_count"]),
        _summary_line("Required refreshed artifacts", payload["summary"]["required_refreshed_artifact_count"]),
        _summary_line("Blocked prerequisites", payload["summary"]["blocked_prerequisite_count"]),
        _summary_line("Operator review items", payload["summary"]["operator_review_item_count"]),
        _summary_line("Safety preflight items", payload["summary"]["safety_preflight_item_count"]),
        _summary_line("Data-quality checks", payload["summary"]["data_quality_check_count"]),
        _summary_line("Acceptance criteria", payload["summary"]["acceptance_criteria_count"]),
        "",
    ]
    lines.extend(_section("Planned Research and Report Workflows", payload["planned_research_report_workflows"]))
    lines.extend(_section("Required Refreshed Artifacts", payload["required_refreshed_artifacts"]))
    lines.extend(_section("Blocked Prerequisites", payload["blocked_prerequisites"]))
    lines.extend(_section("Operator Review Items", payload["operator_review_items"]))
    lines.extend(_section("Safety Preflight Items", payload["safety_preflight_items"]))
    lines.extend(_section("Data-Quality Checks", payload["data_quality_checks"]))
    lines.extend(_section("Next-Cycle Acceptance Criteria", payload["next_cycle_acceptance_criteria"]))
    lines.extend(_section("Queue Status", [payload["queue_status"]]))
    lines.extend(_section("Safety Scanner Status", [payload["safety_scanner_status"]]))
    lines.extend(
        [
            "## Safety Boundary",
            "",
            "- RESEARCH_ONLY next-cycle planning only.",
            "- MONITOR_ONLY and PAPER_ONLY workflows are planned, not executed.",
            "- HUMAN_REVIEW_REQUIRED items remain human-review records.",
            "- BLOCKED_BY_SAFETY_GATE prerequisites remain blocked.",
            "- Records-only plan; no next-cycle run, artifact mutation, artifact deletion, broker action, trade instruction, live-trading enablement, or execution permission is created.",
            "- LIVE TRADING: DISABLED.",
            "",
        ]
    )
    return "\n".join(lines)


def _source_artifacts(plan_input: ResearchNextCyclePlanInput) -> list[dict[str, Any]]:
    artifact_paths = (
        ("rollover_gate", "24A Research Cycle Rollover Gate", plan_input.rollover_gate_path),
        ("archive_index", "23B Research Cycle Archive Index", plan_input.archive_index_path),
        ("operations_console", "23A Research Operations Console", plan_input.operations_console_path),
        ("operator_signoff_packet", "22B Operator Signoff Packet", plan_input.operator_signoff_packet_path),
        ("readiness_gate", "20A Research Cycle Readiness Gate", plan_input.readiness_gate_path),
        ("retention_policy", "20B Research Artifact Retention Policy", plan_input.retention_policy_path),
        ("report_index", "Report Index", plan_input.report_index_path),
        ("safe_workflow_catalog", "Safe Workflow Catalog", plan_input.safe_workflow_catalog_path),
        ("safety_scanner_status", "Safety Scanner Status", plan_input.safety_scanner_path),
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


def _planned_workflows(queue_status: dict[str, Any]) -> list[dict[str, Any]]:
    items = queue_status.get("items", [])
    workflows = []
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict) or item.get("phase") == "24B":
                continue
            workflows.append(
                {
                    "workflow_id": f"planned_{item.get('phase', 'phase')}",
                    "phase": item.get("phase"),
                    "title": item.get("title", "Queued roadmap item"),
                    "label": HUMAN_REVIEW_REQUIRED,
                    "status": "planned_not_started",
                    "summary": item.get("summary", "Queued roadmap item recorded for next-cycle planning."),
                    "records_only": True,
                    "run_started": False,
                }
            )
    if not workflows:
        workflows.append(
            {
                "workflow_id": "planned_next_cycle_placeholder",
                "phase": None,
                "title": "Next research/report workflow selection",
                "label": HUMAN_REVIEW_REQUIRED,
                "status": "requires_operator_selection",
                "summary": "No queued post-24B workflow was available; operator must select records-only next-cycle research/report workflows.",
                "records_only": True,
                "run_started": False,
            }
        )
    return _dedupe_by_id(workflows, "workflow_id")


def _required_refreshed_artifacts(
    missing_artifacts: list[dict[str, Any]],
    stale_artifacts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    items = [
        _refresh("24B-REFRESH-SAFETY-SCANNER", "safety_scanner_status", "Run or attach a fresh safety scanner status before any next-cycle run."),
        _refresh("24B-REFRESH-REPORT-INDEX", "report_index", "Refresh the report index after operator review and before next-cycle acceptance."),
        _refresh("24B-REFRESH-SAFE-WORKFLOW-CATALOG", "safe_workflow_catalog", "Confirm the safe workflow catalog still lists only allowed records-only workflows."),
    ]
    for artifact in [*missing_artifacts, *stale_artifacts]:
        items.append(
            _refresh(
                f"24B-REFRESH-{artifact['artifact_id']}",
                artifact["artifact_id"],
                f"Refresh or explicitly accept {artifact['name']} before next-cycle acceptance.",
                BLOCKED_BY_SAFETY_GATE if artifact["status"] != "present" else HUMAN_REVIEW_REQUIRED,
            )
        )
    return _dedupe_by_id(items, "refresh_id")


def _blocked_prerequisites(
    *,
    source_payloads: dict[str, dict[str, Any]],
    missing_artifacts: list[dict[str, Any]],
    safety_findings: list[dict[str, Any]],
    queue_status: dict[str, Any],
    safety_scanner_status: dict[str, Any],
) -> list[dict[str, Any]]:
    items = []
    for artifact in missing_artifacts:
        items.append(_blocked(f"missing_{artifact['artifact_id']}", f"{artifact['name']} is missing or invalid."))
    for artifact_id, payload in source_payloads.items():
        for key in ("rollover_state", "archive_index_state", "console_state", "signoff_state", "readiness_state", "gate_state"):
            state = payload.get(key)
            if isinstance(state, str) and BLOCKED_BY_SAFETY_GATE in state:
                items.append(_blocked(f"{artifact_id}_{key}", f"{artifact_id} reports {state}."))
    if queue_status.get("label") == BLOCKED_BY_SAFETY_GATE:
        items.append(_blocked("master_plan_queue", queue_status.get("summary", "Master plan queue is blocked.")))
    if safety_scanner_status.get("passed") is False:
        items.append(_blocked("safety_scanner_status", safety_scanner_status.get("summary", "Safety scanner failed.")))
    for finding in safety_findings:
        items.append(_blocked(f"safety_finding_{finding['finding_id']}", finding["summary"]))
    return _dedupe_by_id(items, "prerequisite_id")


def _operator_review_items(source_payloads: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    items = [
        {
            "review_item_id": "24B-REVIEW-NEXT-CYCLE-PLAN",
            "label": HUMAN_REVIEW_REQUIRED,
            "status": "open_review_item",
            "summary": "Review this records-only next-cycle plan before any later cycle runner is invoked.",
            "source_artifact_id": "next_cycle_plan",
        }
    ]
    for artifact_id, payload in source_payloads.items():
        for key in (
            "required_operator_actions",
            "required_next_human_review_actions",
            "human_review_notes",
            "open_items",
            "blocked_items",
            "safety_findings",
        ):
            for item in _items_from_payload(payload, key):
                item_id = item.get("review_item_id") or item.get("action_id") or item.get("note_id") or item.get("item_id") or item.get("finding_id") or key
                items.append(
                    {
                        "review_item_id": f"{artifact_id}_{item_id}",
                        "label": item.get("label", HUMAN_REVIEW_REQUIRED),
                        "status": item.get("status") or item.get("review_status") or "recorded",
                        "summary": item.get("summary", "Source artifact review item recorded."),
                        "source_artifact_id": artifact_id,
                    }
                )
    return _dedupe_by_id(items, "review_item_id")


def _safety_preflight_items(
    safety_scanner_status: dict[str, Any],
    safety_findings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return _dedupe_by_id(
        [
            _preflight("24B-PREFLIGHT-LIVE-TRADING-DISABLED", "Confirm live_trading_enabled=false and LIVE TRADING: DISABLED."),
            _preflight("24B-PREFLIGHT-NO-BROKER-CALLS", "Confirm no broker routing, broker calls, or order execution are added."),
            _preflight("24B-PREFLIGHT-NO-SECRETS", "Confirm no secrets, credential files, OAuth tokens, private keys, or passwords are needed."),
            _preflight(
                "24B-PREFLIGHT-SAFETY-SCANNER",
                "Safety scanner must be fresh and passing before any later next-cycle run.",
                BLOCKED_BY_SAFETY_GATE if safety_scanner_status.get("passed") is False or safety_findings else HUMAN_REVIEW_REQUIRED,
            ),
        ],
        "preflight_id",
    )


def _data_quality_checks(
    source_artifacts: list[dict[str, Any]],
    missing_artifacts: list[dict[str, Any]],
    stale_artifacts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return _dedupe_by_id(
        [
            _check("24B-DQ-SOURCE-PRESENCE", "All required source planning artifacts are present.", BLOCKED_BY_SAFETY_GATE if missing_artifacts else HUMAN_REVIEW_REQUIRED),
            _check("24B-DQ-SOURCE-FRESHNESS", "Source planning artifacts are fresh or explicitly accepted by the operator.", HUMAN_REVIEW_REQUIRED if stale_artifacts else MONITOR_ONLY),
            _check("24B-DQ-DETERMINISTIC-JSON", "Generated JSON must be deterministic, sorted, and JSON-serializable.", RESEARCH_ONLY),
            _check("24B-DQ-SOURCE-COUNT", f"{len(source_artifacts)} source artifact slots were evaluated for planning context.", MONITOR_ONLY),
        ],
        "check_id",
    )


def _acceptance_criteria(
    *,
    blocked_prerequisites: list[dict[str, Any]],
    operator_review_items: list[dict[str, Any]],
    safety_preflight_items: list[dict[str, Any]],
    data_quality_checks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return _dedupe_by_id(
        [
            _criterion("24B-ACCEPT-RECORDS-ONLY", "24B produces JSON and Markdown records only and does not run the next cycle.", RESEARCH_ONLY),
            _criterion("24B-ACCEPT-SAFETY-BOUNDARY", "Required safety labels are present and LIVE TRADING: DISABLED is recorded.", HUMAN_REVIEW_REQUIRED),
            _criterion("24B-ACCEPT-NO-BLOCKED-PREREQS", f"Blocked prerequisite count is {len(blocked_prerequisites)} and must be reviewed before any next-cycle run.", BLOCKED_BY_SAFETY_GATE if blocked_prerequisites else HUMAN_REVIEW_REQUIRED),
            _criterion("24B-ACCEPT-OPERATOR-REVIEW", f"Operator review item count is {len(operator_review_items)} and remains human-review-required.", HUMAN_REVIEW_REQUIRED),
            _criterion("24B-ACCEPT-PREFLIGHTS", f"Safety preflight item count is {len(safety_preflight_items)} and must stay non-executing.", PAPER_ONLY),
            _criterion("24B-ACCEPT-DATA-QUALITY", f"Data-quality check count is {len(data_quality_checks)} and must be resolved or accepted.", MONITOR_ONLY),
        ],
        "criterion_id",
    )


def _next_cycle_plan_state(
    *,
    missing_artifacts: list[dict[str, Any]],
    stale_artifacts: list[dict[str, Any]],
    safety_findings: list[dict[str, Any]],
    blocked_prerequisites: list[dict[str, Any]],
    operator_review_items: list[dict[str, Any]],
    queue_status: dict[str, Any],
    safety_scanner_status: dict[str, Any],
) -> str:
    if (
        missing_artifacts
        or safety_findings
        or blocked_prerequisites
        or queue_status.get("label") == BLOCKED_BY_SAFETY_GATE
        or safety_scanner_status.get("passed") is False
    ):
        return BLOCKED_BY_SAFETY_GATE
    if stale_artifacts or operator_review_items:
        return NEXT_CYCLE_PLAN_NEEDS_OPERATOR_REVIEW
    return NEXT_CYCLE_PLAN_READY_FOR_HUMAN_REVIEW


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
        "summary": "Master plan queue read for 24B next-cycle planning context only.",
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
            "summary": "Safety scanner status was not supplied to 24B.",
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
        "summary": payload.get("summary", "Safety scanner status supplied to 24B."),
        "path": path.as_posix(),
        "finding_count": payload.get("finding_count", len(findings) if isinstance(findings, list) else 0),
        "passed": passed,
        "findings": findings if isinstance(findings, list) else [],
    }
    _validate_json_value("safety_scanner_status", value)
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
        if item.get("phase") == "24B":
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
        "next_cycle_plan_read_only": True,
        "next_cycle_started": False,
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


def _final_next_cycle_plan_summary(
    *,
    next_cycle_plan_state: str,
    planned_workflows: list[dict[str, Any]],
    required_refreshed_artifacts: list[dict[str, Any]],
    blocked_prerequisites: list[dict[str, Any]],
    operator_review_items: list[dict[str, Any]],
    safety_preflight_items: list[dict[str, Any]],
    data_quality_checks: list[dict[str, Any]],
    acceptance_criteria: list[dict[str, Any]],
) -> str:
    return (
        f"Next research-cycle plan state is {next_cycle_plan_state}. "
        f"Planned workflows: {len(planned_workflows)}. "
        f"Required refreshed artifacts: {len(required_refreshed_artifacts)}. "
        f"Blocked prerequisites: {len(blocked_prerequisites)}. "
        f"Operator review items: {len(operator_review_items)}. "
        f"Safety preflight items: {len(safety_preflight_items)}. "
        f"Data-quality checks: {len(data_quality_checks)}. "
        f"Acceptance criteria: {len(acceptance_criteria)}. "
        "Safety boundary confirmed: this is a records-only plan and does not run the next cycle, mutate artifacts, delete artifacts, create broker actions, create trade instructions, enable live trading, or grant execution permissions. "
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


def _criterion(criterion_id: str, summary: str, label: str) -> dict[str, Any]:
    return {
        "criterion_id": criterion_id,
        "label": label,
        "status": "acceptance_required",
        "summary": summary,
    }


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
    plan_day: date,
    max_source_age_days: int,
) -> list[dict[str, Any]]:
    stale = []
    for item in source_artifacts:
        if item["status"] != "present":
            continue
        age_days = _age_days(plan_day, item.get("generated_date"))
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
    _validate_next_cycle_path(path)
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


def _age_days(plan_day: date, generated_date: str | None) -> int | None:
    if generated_date is None:
        return None
    try:
        generated_day = datetime.strptime(generated_date, "%Y-%m-%d").date()
    except ValueError:
        return None
    return (plan_day - generated_day).days


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
            or item.get("criterion_id")
            or item.get("artifact_id")
            or item.get("finding_id")
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
            or item.get("criterion_id")
            or item.get("artifact_id")
            or item.get("finding_id")
            or item.get("phase")
            or item.get("status")
            or json.dumps(item, sort_keys=True)
        ),
    )


def _validate_next_cycle_path(path: Path) -> None:
    if path.name in SECRET_FILE_NAMES:
        raise ValueError("research next cycle plan cannot target secret files")
    lowered_parts = [part.lower() for part in path.parts]
    if any(marker in part for part in lowered_parts for marker in SECRET_PATH_MARKERS):
        raise ValueError("research next cycle plan cannot target credential or secret paths")
    if path.is_absolute():
        raise ValueError("research next cycle plan paths must be repo-relative")
    if ".." in path.parts:
        raise ValueError("research next cycle plan paths cannot traverse parent directories")


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
        if label is not None and label not in SAFE_NEXT_CYCLE_LABELS:
            raise ValueError(f"unsafe research next cycle plan label: {label}")
        plan_state = value.get("next_cycle_plan_state")
        if plan_state is not None and plan_state not in NEXT_CYCLE_PLAN_STATES:
            raise ValueError(f"invalid research next cycle plan state: {plan_state}")
        for unsafe_field in UNSAFE_TRUE_FIELDS:
            if value.get(unsafe_field) is True:
                raise ValueError(f"research next cycle plan cannot set {unsafe_field}")
        for mutation_field in ("artifact_delete_performed", "artifact_mutation_performed"):
            if value.get(mutation_field) is True:
                raise ValueError(f"research next cycle plan cannot set {mutation_field}")
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
        if value in DISALLOWED_NEXT_CYCLE_LABELS:
            raise ValueError(f"disallowed research next cycle plan text: {value}")
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
