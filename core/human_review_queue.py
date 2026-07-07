from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from core.operator_dashboard_snapshot import OPERATOR_DASHBOARD_SNAPSHOT_JSON
from core.report_index import REPORT_INDEX_JSON
from core.research_artifact_retention_policy import (
    DEFAULT_RESEARCH_ARTIFACT_RETENTION_POLICY_DIR,
    RESEARCH_ARTIFACT_RETENTION_POLICY_JSON,
)
from core.research_cycle_audit_summary import (
    DEFAULT_RESEARCH_CYCLE_AUDIT_SUMMARY_DIR,
    RESEARCH_CYCLE_AUDIT_SUMMARY_JSON,
)
from core.research_cycle_readiness_gate import (
    DEFAULT_RESEARCH_CYCLE_READINESS_GATE_DIR,
    RESEARCH_CYCLE_READINESS_GATE_JSON,
)
from core.research_cycle_runner import (
    DEFAULT_RESEARCH_CYCLE_RUNNER_DIR,
    RESEARCH_CYCLE_MANIFEST_JSON,
)
from core.research_release_bundle import (
    DEFAULT_RESEARCH_RELEASE_BUNDLE_DIR,
    RESEARCH_RELEASE_BUNDLE_JSON,
)
from core.safe_workflow_catalog import SAFE_WORKFLOW_CATALOG_JSON
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


DEFAULT_HUMAN_REVIEW_QUEUE_DIR = Path("reports/human_review_queue")
HUMAN_REVIEW_QUEUE_JSON = "human_review_queue.json"
HUMAN_REVIEW_QUEUE_MARKDOWN = "human_review_queue.md"

OPEN_HUMAN_REVIEW_QUEUE = "OPEN_HUMAN_REVIEW_QUEUE"
BLOCKED_HUMAN_REVIEW_QUEUE = "BLOCKED_HUMAN_REVIEW_QUEUE"
SAFE_HUMAN_REVIEW_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
DISALLOWED_HUMAN_REVIEW_LABELS = tuple(
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
    "broker_order_call_requested",
    "broker_order_routing_requested",
    "live_trading_approval_granted",
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
BASELINE_BLOCKED_WORKFLOWS = (
    "broker_order_call",
    "broker_order_routing",
    "live_trading",
    "order_execution",
    "secret_or_credential_access",
)
DATE_KEYS = (
    "review_date",
    "gate_date",
    "retention_date",
    "audit_date",
    "cycle_date",
    "bundle_date",
    "snapshot_date",
    "index_date",
    "catalog_date",
    "evidence_date",
    "journal_date",
    "runbook_date",
    "week_end",
    "report_date",
)


@dataclass(frozen=True)
class HumanReviewQueueInput:
    queue_id: str
    review_date: str
    generated_at_utc: str
    readiness_gate_path: Path = (
        DEFAULT_RESEARCH_CYCLE_READINESS_GATE_DIR / RESEARCH_CYCLE_READINESS_GATE_JSON
    )
    retention_policy_path: Path = (
        DEFAULT_RESEARCH_ARTIFACT_RETENTION_POLICY_DIR / RESEARCH_ARTIFACT_RETENTION_POLICY_JSON
    )
    audit_summary_path: Path = (
        DEFAULT_RESEARCH_CYCLE_AUDIT_SUMMARY_DIR / RESEARCH_CYCLE_AUDIT_SUMMARY_JSON
    )
    manifest_path: Path = DEFAULT_RESEARCH_CYCLE_RUNNER_DIR / RESEARCH_CYCLE_MANIFEST_JSON
    release_bundle_path: Path = DEFAULT_RESEARCH_RELEASE_BUNDLE_DIR / RESEARCH_RELEASE_BUNDLE_JSON
    operator_dashboard_snapshot_path: Path = Path(
        "reports/operator_dashboard_snapshot"
    ) / OPERATOR_DASHBOARD_SNAPSHOT_JSON
    report_index_path: Path = Path("reports/report_index") / REPORT_INDEX_JSON
    safe_workflow_catalog_path: Path = (
        Path("reports/safe_workflow_catalog") / SAFE_WORKFLOW_CATALOG_JSON
    )
    queue_status_path: Path = Path("config/jarvis_master_plan_queue.json")
    safety_scanner_path: Path = Path("reports/safety_scanner/safety_scanner_status.json")
    max_source_age_days: int = 1

    def validate(self) -> None:
        for field_name in ("queue_id", "review_date", "generated_at_utc"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"human review queue requires {field_name}")
        _parse_iso_date("review_date", self.review_date)
        _parse_iso_datetime("generated_at_utc", self.generated_at_utc)
        if not isinstance(self.max_source_age_days, int) or self.max_source_age_days < 0:
            raise ValueError("max_source_age_days must be a non-negative integer")
        for path in (
            self.readiness_gate_path,
            self.retention_policy_path,
            self.audit_summary_path,
            self.manifest_path,
            self.release_bundle_path,
            self.operator_dashboard_snapshot_path,
            self.report_index_path,
            self.safe_workflow_catalog_path,
            self.queue_status_path,
            self.safety_scanner_path,
        ):
            _validate_review_path(path)


def build_default_human_review_queue_input(
    *,
    review_date: date | None = None,
    now: datetime | None = None,
) -> HumanReviewQueueInput:
    generated = now or datetime.now(tz=UTC)
    day = review_date or generated.date()
    return HumanReviewQueueInput(
        queue_id=f"21A-HUMAN-REVIEW-QUEUE-{day.isoformat()}",
        review_date=day.isoformat(),
        generated_at_utc=generated.isoformat(),
    )


def build_human_review_queue_payload(review_input: HumanReviewQueueInput) -> dict[str, Any]:
    review_input.validate()
    review_day = datetime.strptime(review_input.review_date, "%Y-%m-%d").date()
    source_artifacts = _source_artifacts(review_input)
    source_payloads = {
        item["artifact_id"]: item["payload"]
        for item in source_artifacts
        if item["status"] == "present" and isinstance(item.get("payload"), dict)
    }

    missing_artifacts = _missing_artifacts(source_artifacts, source_payloads)
    stale_artifacts = _stale_artifacts(source_artifacts, source_payloads, review_day, review_input.max_source_age_days)
    skipped_steps = _collect_payload_items(source_payloads, "skipped_steps", "step_id", HUMAN_REVIEW_REQUIRED)
    blocked_workflows = _blocked_workflows(source_payloads)
    safety_findings = _safety_findings(source_payloads, review_input.safety_scanner_path)
    retention_review_items = _retention_review_items(source_payloads.get("retention_policy", {}))
    required_human_review_items = _required_human_review_items(source_payloads)
    queue_status = _queue_status(review_input.queue_status_path)
    safety_scanner_status = _safety_scanner_status(review_input.safety_scanner_path)
    next_operator_actions = _next_operator_actions(
        missing_artifacts=missing_artifacts,
        stale_artifacts=stale_artifacts,
        skipped_steps=skipped_steps,
        blocked_workflows=blocked_workflows,
        safety_findings=safety_findings,
        retention_review_items=retention_review_items,
        required_human_review_items=required_human_review_items,
        queue_status=queue_status,
        safety_scanner_status=safety_scanner_status,
    )
    queue_state = (
        BLOCKED_HUMAN_REVIEW_QUEUE
        if missing_artifacts or safety_findings or queue_status["label"] == BLOCKED_BY_SAFETY_GATE
        else OPEN_HUMAN_REVIEW_QUEUE
    )

    payload = {
        "phase": "21A",
        "workflow": "Human Review Queue",
        "queue_id": review_input.queue_id,
        "review_date": review_input.review_date,
        "generated_at_utc": review_input.generated_at_utc,
        "queue_state": queue_state,
        "safety_boundary": _safety_boundary(),
        "required_labels": list(SAFE_HUMAN_REVIEW_LABELS),
        "summary": {
            "source_artifact_count": len(source_artifacts),
            "present_source_artifact_count": len([item for item in source_artifacts if item["status"] == "present"]),
            "missing_artifact_count": len(missing_artifacts),
            "stale_artifact_count": len(stale_artifacts),
            "skipped_step_count": len(skipped_steps),
            "blocked_workflow_count": len(blocked_workflows),
            "safety_finding_count": len(safety_findings),
            "retention_review_item_count": len(retention_review_items),
            "required_human_review_item_count": len(required_human_review_items),
            "next_operator_action_count": len(next_operator_actions),
            "queue_status": queue_status["status"],
            "safety_scanner_status": safety_scanner_status["status"],
            "label_counts": _count_by(
                [
                    *source_artifacts,
                    *missing_artifacts,
                    *stale_artifacts,
                    *skipped_steps,
                    *blocked_workflows,
                    *safety_findings,
                    *retention_review_items,
                    *required_human_review_items,
                    *next_operator_actions,
                    queue_status,
                    safety_scanner_status,
                ],
                "label",
            ),
        },
        "source_artifacts": [_without_payload(item) for item in source_artifacts],
        "missing_artifacts": missing_artifacts,
        "stale_artifacts": stale_artifacts,
        "skipped_steps": skipped_steps,
        "blocked_workflows": blocked_workflows,
        "safety_findings": safety_findings,
        "retention_review_items": retention_review_items,
        "required_human_review_items": required_human_review_items,
        "queue_status": queue_status,
        "safety_scanner_status": safety_scanner_status,
        "next_operator_actions": next_operator_actions,
    }
    _validate_json_value("human_review_queue_payload", payload)
    return _normalize_json_value(payload)


def write_human_review_queue(
    review_input: HumanReviewQueueInput,
    *,
    out_dir: Path = DEFAULT_HUMAN_REVIEW_QUEUE_DIR,
) -> tuple[Path, Path]:
    payload = build_human_review_queue_payload(review_input)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / HUMAN_REVIEW_QUEUE_JSON
    markdown_path = out_dir / HUMAN_REVIEW_QUEUE_MARKDOWN
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_human_review_queue_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def render_human_review_queue_markdown(payload: dict[str, Any]) -> str:
    _validate_json_value("human_review_queue_payload", payload)
    lines = [
        "# 21A Human Review Queue",
        "",
        f"Queue ID: {payload['queue_id']}",
        f"Review Date: {payload['review_date']}",
        f"Generated: {payload['generated_at_utc']}",
        f"Queue State: {payload['queue_state']}",
        "",
        "Status: RESEARCH_ONLY / MONITOR_ONLY / PAPER_ONLY / HUMAN_REVIEW_REQUIRED.",
        "Review items are not trade instructions, execution instructions, broker actions, or live-trading approvals.",
        "BLOCKED_BY_SAFETY_GATE workflows remain blocked.",
        "LIVE TRADING: DISABLED. No secrets, credential files, broker routing, broker calls, or order execution are used.",
        "",
        "## Summary",
        "",
        _summary_line("Source artifacts", payload["summary"]["source_artifact_count"]),
        _summary_line("Present source artifacts", payload["summary"]["present_source_artifact_count"]),
        _summary_line("Missing artifacts", payload["summary"]["missing_artifact_count"]),
        _summary_line("Stale artifacts", payload["summary"]["stale_artifact_count"]),
        _summary_line("Skipped steps", payload["summary"]["skipped_step_count"]),
        _summary_line("Blocked workflows", payload["summary"]["blocked_workflow_count"]),
        _summary_line("Safety findings", payload["summary"]["safety_finding_count"]),
        _summary_line("Retention review items", payload["summary"]["retention_review_item_count"]),
        _summary_line(
            "Required human-review items",
            payload["summary"]["required_human_review_item_count"],
        ),
        _summary_line("Next operator actions", payload["summary"]["next_operator_action_count"]),
        "",
    ]
    lines.extend(_section("Source Artifacts", payload["source_artifacts"]))
    lines.extend(_section("Required Human-Review Items", payload["required_human_review_items"]))
    lines.extend(_section("Missing Artifacts", payload["missing_artifacts"]))
    lines.extend(_section("Stale Artifacts", payload["stale_artifacts"]))
    lines.extend(_section("Skipped Steps", payload["skipped_steps"]))
    lines.extend(_section("Blocked Workflows", payload["blocked_workflows"]))
    lines.extend(_section("Safety Findings", payload["safety_findings"]))
    lines.extend(_section("Retention Review Items", payload["retention_review_items"]))
    lines.extend(_section("Queue Status", [payload["queue_status"]]))
    lines.extend(_section("Safety Scanner Status", [payload["safety_scanner_status"]]))
    lines.extend(_section("Next Operator Actions", payload["next_operator_actions"]))
    lines.extend(
        [
            "## Safety Boundary",
            "",
            "- RESEARCH_ONLY human review queue generation only.",
            "- MONITOR_ONLY and PAPER_ONLY artifacts are summarized, not executed.",
            "- HUMAN_REVIEW_REQUIRED items require human interpretation before any future workflow.",
            "- BLOCKED_BY_SAFETY_GATE workflows remain blocked.",
            "- LIVE TRADING: DISABLED.",
            "",
        ]
    )
    return "\n".join(lines)


def _source_artifacts(review_input: HumanReviewQueueInput) -> list[dict[str, Any]]:
    artifact_paths = (
        ("readiness_gate", "20A Research Cycle Readiness Gate", review_input.readiness_gate_path),
        ("retention_policy", "20B Research Artifact Retention Policy", review_input.retention_policy_path),
        ("audit_summary", "19B Research Cycle Audit Summary", review_input.audit_summary_path),
        ("research_cycle_manifest", "19A Research Cycle Manifest", review_input.manifest_path),
        ("release_bundle", "18B Research Release Bundle", review_input.release_bundle_path),
        (
            "operator_dashboard_snapshot",
            "17B Operator Dashboard Snapshot",
            review_input.operator_dashboard_snapshot_path,
        ),
        ("report_index", "Report Index", review_input.report_index_path),
        ("safe_workflow_catalog", "Safe Workflow Catalog", review_input.safe_workflow_catalog_path),
        ("safety_scanner_status", "Safety Scanner Status", review_input.safety_scanner_path),
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
                "label": payload.get("safety_boundary", {}).get(
                    "label",
                    payload.get("label", HUMAN_REVIEW_REQUIRED),
                ),
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


def _missing_artifacts(
    source_artifacts: list[dict[str, Any]],
    source_payloads: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    items = [
        {
            "artifact_id": artifact["artifact_id"],
            "workflow_id": f"missing_{artifact['artifact_id']}",
            "label": BLOCKED_BY_SAFETY_GATE,
            "status": "missing",
            "path": artifact["path"],
            "summary": artifact["summary"],
            "source_artifact_id": "21a_source_artifacts",
        }
        for artifact in source_artifacts
        if artifact["status"] != "present"
    ]
    for item in _collect_payload_items(source_payloads, "missing_artifacts", "artifact_id", BLOCKED_BY_SAFETY_GATE):
        item.setdefault("workflow_id", f"missing_{item.get('artifact_id', 'artifact')}")
        items.append(item)
    return _dedupe_by_id(items, "workflow_id")


def _stale_artifacts(
    source_artifacts: list[dict[str, Any]],
    source_payloads: dict[str, dict[str, Any]],
    review_day: date,
    max_source_age_days: int,
) -> list[dict[str, Any]]:
    items = []
    for artifact in source_artifacts:
        if artifact["status"] != "present":
            continue
        generated_date = artifact.get("generated_date")
        if not isinstance(generated_date, str):
            items.append(_stale_item(artifact, "unknown", "Source artifact generated date was not present."))
            continue
        try:
            artifact_day = datetime.strptime(generated_date[:10], "%Y-%m-%d").date()
        except ValueError:
            items.append(_stale_item(artifact, generated_date, "Source artifact generated date was invalid."))
            continue
        age_days = (review_day - artifact_day).days
        if age_days > max_source_age_days:
            items.append(
                _stale_item(
                    artifact,
                    generated_date,
                    f"Source artifact is {age_days} days old; maximum allowed age is {max_source_age_days} days.",
                )
            )
    for item in _collect_payload_items(source_payloads, "stale_reports", "workflow_id", HUMAN_REVIEW_REQUIRED):
        item.setdefault("artifact_id", item.get("workflow_id", "stale_artifact"))
        items.append(item)
    return _dedupe_by_id(items, "workflow_id")


def _stale_item(artifact: dict[str, Any], generated_date: str, summary: str) -> dict[str, Any]:
    value = {
        "artifact_id": artifact["artifact_id"],
        "workflow_id": f"stale_{artifact['artifact_id']}",
        "label": HUMAN_REVIEW_REQUIRED,
        "status": "stale",
        "path": artifact["path"],
        "generated_date": generated_date,
        "summary": summary,
        "source_artifact_id": "21a_source_artifacts",
    }
    _validate_json_value("stale_artifact", value)
    return _normalize_json_value(value)


def _blocked_workflows(source_payloads: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    items = [
        {
            "workflow_id": workflow_id,
            "label": BLOCKED_BY_SAFETY_GATE,
            "status": "blocked",
            "summary": "Workflow remains blocked by 21A safety boundary.",
            "source_artifact_id": "21a_safety_boundary",
        }
        for workflow_id in BASELINE_BLOCKED_WORKFLOWS
    ]
    items.extend(_collect_payload_items(source_payloads, "blocked_workflows", "workflow_id", BLOCKED_BY_SAFETY_GATE))
    return _dedupe_by_id(items, "workflow_id")


def _safety_findings(
    source_payloads: dict[str, dict[str, Any]],
    safety_scanner_path: Path,
) -> list[dict[str, Any]]:
    items = []
    for item in _collect_payload_items(source_payloads, "failed_safety_findings", "finding_id", BLOCKED_BY_SAFETY_GATE):
        items.append(item)
    scanner = _safety_scanner_status(safety_scanner_path)
    if scanner.get("passed") is False or scanner.get("label") == BLOCKED_BY_SAFETY_GATE:
        items.append(
            {
                "finding_id": "safety_scanner_status",
                "workflow_id": "safety_scanner",
                "label": BLOCKED_BY_SAFETY_GATE,
                "status": "failed",
                "summary": scanner.get("summary", "Safety scanner status requires review."),
                "source_artifact_id": "safety_scanner_status",
            }
        )
    for finding in scanner.get("findings", []):
        if not isinstance(finding, dict):
            continue
        value = {
            "finding_id": finding.get("rule_id") or finding.get("finding_id") or "safety_finding",
            "workflow_id": "safety_scanner",
            "label": BLOCKED_BY_SAFETY_GATE,
            "status": "failed",
            "summary": finding.get("summary") or finding.get("message") or "Safety scanner finding recorded.",
            "source_artifact_id": "safety_scanner_status",
        }
        _validate_json_value("safety_finding", value)
        items.append(value)
    return _dedupe_by_id(items, "finding_id")


def _retention_review_items(retention_payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = []
    artifacts = retention_payload.get("artifacts", [])
    if not isinstance(artifacts, list):
        artifacts = []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        action = artifact.get("retention_action")
        if action in {"review", "archive_candidate", "blocked_delete"}:
            value = {
                "review_item_id": f"retention_{artifact.get('artifact_id', 'artifact')}",
                "artifact_id": artifact.get("artifact_id", "artifact"),
                "label": HUMAN_REVIEW_REQUIRED,
                "status": "open_review_item",
                "retention_action": action,
                "automatic_delete_allowed": False,
                "summary": "; ".join(artifact.get("retention_reasons", []))
                if isinstance(artifact.get("retention_reasons"), list)
                else "Retention policy item requires human review.",
                "source_artifact_id": "retention_policy",
            }
            _validate_json_value("retention_review_item", value)
            items.append(value)
    return _dedupe_by_id(items, "review_item_id")


def _required_human_review_items(source_payloads: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    items = []
    mapping = (
        ("readiness_gate", "required_human_review_actions", "action_id"),
        ("audit_summary", "human_review_notes", "note_id"),
        ("audit_summary", "allowed_human_review_workflows", "workflow_id"),
        ("operator_dashboard_snapshot", "allowed_human_review_workflows", "workflow_id"),
    )
    for artifact_id, key, id_key in mapping:
        payload = source_payloads.get(artifact_id, {})
        for item in _items_from_payload(payload, key):
            value = dict(item)
            value.setdefault("review_item_id", value.get(id_key) or value.get("workflow_id") or "review_item")
            value.setdefault("label", HUMAN_REVIEW_REQUIRED)
            value.setdefault("status", "open_review_item")
            value.setdefault("summary", "Human review item recorded.")
            value["source_artifact_id"] = artifact_id
            _validate_json_value("required_human_review_item", value)
            items.append(_normalize_json_value(value))
    return _dedupe_by_id(items, "review_item_id")


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
        }
    items = [_queue_item(item) for item in payload if isinstance(item, dict)]
    value = {
        "workflow_id": "master_plan_queue",
        "label": HUMAN_REVIEW_REQUIRED,
        "status": "read_only",
        "summary": "Master plan queue read for 21A human review context only.",
        "path": path.as_posix(),
        "queue_item_count": len(items),
        "next_phase": _next_phase(items),
        "items": items,
    }
    _validate_json_value("queue_status", value)
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
        if item.get("phase") == "21A":
            return item
    return items[0] if items else None


def _safety_scanner_status(path: Path) -> dict[str, Any]:
    payload = _read_json_object(path)
    if payload is None:
        return {
            "workflow_id": "safety_scanner",
            "label": HUMAN_REVIEW_REQUIRED,
            "status": "not_run",
            "summary": "Safety scanner status was not supplied to 21A.",
            "path": path.as_posix(),
            "finding_count": 0,
            "passed": None,
            "findings": [],
        }
    findings = payload.get("findings", [])
    finding_count = payload.get("finding_count", len(findings) if isinstance(findings, list) else 0)
    passed = payload.get("passed")
    value = {
        "workflow_id": "safety_scanner",
        "label": payload.get("label", HUMAN_REVIEW_REQUIRED if passed is not False else BLOCKED_BY_SAFETY_GATE),
        "status": payload.get("status", "passed" if passed else "not_run"),
        "summary": payload.get("summary", "Safety scanner status supplied to 21A."),
        "path": path.as_posix(),
        "finding_count": finding_count,
        "passed": passed,
        "findings": findings if isinstance(findings, list) else [],
    }
    _validate_json_value("safety_scanner_status", value)
    return _normalize_json_value(value)


def _next_operator_actions(
    *,
    missing_artifacts: list[dict[str, Any]],
    stale_artifacts: list[dict[str, Any]],
    skipped_steps: list[dict[str, Any]],
    blocked_workflows: list[dict[str, Any]],
    safety_findings: list[dict[str, Any]],
    retention_review_items: list[dict[str, Any]],
    required_human_review_items: list[dict[str, Any]],
    queue_status: dict[str, Any],
    safety_scanner_status: dict[str, Any],
) -> list[dict[str, Any]]:
    actions = [
        {
            "action_id": "21A-REVIEW-HUMAN-REVIEW-QUEUE",
            "label": HUMAN_REVIEW_REQUIRED,
            "status": "open_review_item",
            "summary": "Review this 21A queue as a research-only, monitor-only, paper-only artifact.",
        }
    ]
    if required_human_review_items:
        actions.append(_action("21A-COMPLETE-REQUIRED-HUMAN-REVIEW-ITEMS", "Review required human-review items from source artifacts."))
    if missing_artifacts:
        actions.append(_action("21A-RESOLVE-MISSING-ARTIFACTS", "Resolve or explicitly accept missing source artifacts."))
    if stale_artifacts:
        actions.append(_action("21A-REFRESH-STALE-ARTIFACTS", "Refresh stale artifacts or record human acceptance."))
    if skipped_steps:
        actions.append(_action("21A-REVIEW-SKIPPED-STEPS", "Review skipped workflow steps before planning the next phase."))
    if blocked_workflows:
        actions.append(_action("21A-CONFIRM-BLOCKED-WORKFLOWS", "Confirm blocked workflows remain blocked and resolve only non-baseline issues."))
    if safety_findings or safety_scanner_status.get("passed") is False:
        actions.append(_action("21A-RESOLVE-SAFETY-FINDINGS", "Resolve safety findings before any future workflow."))
    if retention_review_items:
        actions.append(_action("21A-REVIEW-RETENTION-DRY-RUN", "Review retention policy dry-run items without deleting files automatically."))
    if queue_status.get("label") == BLOCKED_BY_SAFETY_GATE:
        actions.append(_action("21A-REVIEW-QUEUE-STATUS", "Review missing or invalid master plan queue status."))
    return _dedupe_by_id(actions, "action_id")


def _action(action_id: str, summary: str) -> dict[str, Any]:
    return {
        "action_id": action_id,
        "label": HUMAN_REVIEW_REQUIRED,
        "status": "open_review_item",
        "summary": summary,
    }


def _collect_payload_items(
    source_payloads: dict[str, dict[str, Any]],
    key: str,
    id_key: str,
    default_label: str,
) -> list[dict[str, Any]]:
    items = []
    for artifact_id, payload in source_payloads.items():
        for item in _items_from_payload(payload, key):
            value = dict(item)
            value.setdefault(id_key, value.get("workflow_id") or value.get("artifact_id") or "item")
            value.setdefault("workflow_id", value.get(id_key))
            value.setdefault("label", default_label)
            value.setdefault("status", "recorded")
            value.setdefault("summary", "Recorded by source artifact.")
            value["source_artifact_id"] = artifact_id
            _validate_json_value(key, value)
            items.append(_normalize_json_value(value))
    return _dedupe_by_id(items, id_key)


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


def _safety_boundary() -> dict[str, Any]:
    return {
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
    }


def _read_json_object(path: Path) -> dict[str, Any] | None:
    value = _read_json_value(path)
    return value if isinstance(value, dict) else None


def _read_json_value(path: Path) -> Any:
    _validate_review_path(path)
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


def _section(title: str, items: list[dict[str, Any]]) -> list[str]:
    lines = [f"## {title}", ""]
    if not items:
        return [*lines, "- None recorded.", ""]
    for item in items:
        item_id = (
            item.get("review_item_id")
            or item.get("action_id")
            or item.get("artifact_id")
            or item.get("workflow_id")
            or item.get("step_id")
            or item.get("finding_id")
            or item.get("status")
            or "item"
        )
        label = item.get("label", "n/a")
        status = item.get("retention_action") or item.get("status") or "recorded"
        summary = item.get("summary") or item.get("workflow") or item.get("name") or "Recorded."
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
            item.get("review_item_id")
            or item.get("action_id")
            or item.get("artifact_id")
            or item.get("workflow_id")
            or item.get("step_id")
            or item.get("finding_id")
            or item.get("phase")
            or item.get("status")
            or json.dumps(item, sort_keys=True)
        ),
    )


def _validate_review_path(path: Path) -> None:
    if path.name in SECRET_FILE_NAMES:
        raise ValueError("human review queue cannot target secret files")
    lowered_parts = [part.lower() for part in path.parts]
    if any(marker in part for part in lowered_parts for marker in SECRET_PATH_MARKERS):
        raise ValueError("human review queue cannot target credential or secret paths")
    if path.is_absolute():
        raise ValueError("human review queue paths must be repo-relative")
    if ".." in path.parts:
        raise ValueError("human review queue paths cannot traverse parent directories")


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
        if label is not None and label not in SAFE_HUMAN_REVIEW_LABELS:
            raise ValueError(f"unsafe human review queue label: {label}")
        if label in DISALLOWED_HUMAN_REVIEW_LABELS:
            raise ValueError(f"disallowed human review queue label: {label}")
        for unsafe_field in UNSAFE_TRUE_FIELDS:
            if value.get(unsafe_field) is True:
                raise ValueError(f"human review queue cannot set {unsafe_field}")
        if value.get("automatic_delete_allowed") is True:
            raise ValueError("human review queue cannot allow automatic deletion")
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
        if value in DISALLOWED_HUMAN_REVIEW_LABELS:
            raise ValueError(f"disallowed human review queue text: {value}")
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
