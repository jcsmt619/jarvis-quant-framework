from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


DEFAULT_RESEARCH_RELEASE_BUNDLE_DIR = Path("reports/research_release_bundle")
RESEARCH_RELEASE_BUNDLE_JSON = "research_release_bundle.json"
RESEARCH_RELEASE_BUNDLE_MARKDOWN = "research_release_bundle.md"

SAFE_RELEASE_BUNDLE_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
DISALLOWED_RELEASE_BUNDLE_LABELS = tuple(
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


@dataclass(frozen=True)
class ReleaseBundleArtifact:
    artifact_id: str
    name: str
    json_path: Path
    markdown_path: Path
    required_labels: tuple[str, ...] = (HUMAN_REVIEW_REQUIRED,)

    def validate(self) -> None:
        for field_name in ("artifact_id", "name"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"research release bundle artifact requires {field_name}")
        if not isinstance(self.required_labels, tuple) or not self.required_labels:
            raise ValueError("required_labels must be a non-empty tuple")
        for label in self.required_labels:
            if label not in SAFE_RELEASE_BUNDLE_LABELS:
                raise ValueError(f"unsafe research release bundle label: {label}")
        for path in (self.json_path, self.markdown_path):
            _validate_bundle_path(path)


@dataclass(frozen=True)
class ResearchReleaseBundleInput:
    bundle_id: str
    bundle_date: str
    generated_at_utc: str
    artifacts: tuple[ReleaseBundleArtifact, ...] = field(default_factory=tuple)
    queue_path: Path = Path("config/jarvis_master_plan_queue.json")
    safety_scanner_path: Path = Path("reports/safety_scanner/safety_scanner_status.json")
    safe_workflow_catalog_path: Path = Path("reports/safe_workflow_catalog/safe_workflow_catalog.json")
    operator_dashboard_snapshot_path: Path = Path(
        "reports/operator_dashboard_snapshot/operator_dashboard_snapshot.json"
    )

    def validate(self) -> None:
        for field_name in ("bundle_id", "bundle_date", "generated_at_utc"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"research release bundle requires {field_name}")
        _parse_iso_date("bundle_date", self.bundle_date)
        _parse_iso_datetime("generated_at_utc", self.generated_at_utc)
        if not isinstance(self.artifacts, tuple) or not self.artifacts:
            raise ValueError("artifacts must be a non-empty tuple")
        for artifact in self.artifacts:
            artifact.validate()
        for path in (
            self.queue_path,
            self.safety_scanner_path,
            self.safe_workflow_catalog_path,
            self.operator_dashboard_snapshot_path,
        ):
            _validate_bundle_path(path)


def build_default_research_release_bundle_input(
    *,
    bundle_date: date | None = None,
    now: datetime | None = None,
) -> ResearchReleaseBundleInput:
    generated = now or datetime.now(tz=UTC)
    day = bundle_date or generated.date()
    return ResearchReleaseBundleInput(
        bundle_id=f"18B-RESEARCH-RELEASE-BUNDLE-{day.isoformat()}",
        bundle_date=day.isoformat(),
        generated_at_utc=generated.isoformat(),
        artifacts=default_release_bundle_artifacts(),
    )


def default_release_bundle_artifacts() -> tuple[ReleaseBundleArtifact, ...]:
    return (
        _artifact(
            "report_index",
            "Report Index",
            "reports/report_index/report_index.json",
            "reports/report_index/report_index.md",
        ),
        _artifact(
            "operator_dashboard_snapshot",
            "Operator Dashboard Snapshot",
            "reports/operator_dashboard_snapshot/operator_dashboard_snapshot.json",
            "reports/operator_dashboard_snapshot/operator_dashboard_snapshot.md",
            (MONITOR_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE),
        ),
        _artifact(
            "research_evidence_pack",
            "Research Evidence Pack",
            "reports/research_evidence_pack/research_evidence_pack.json",
            "reports/research_evidence_pack/research_evidence_pack.md",
        ),
        _artifact(
            "decision_journal",
            "Decision Journal",
            "reports/decision_journal/decision_journal.json",
            "reports/decision_journal/decision_journal.md",
        ),
        _artifact(
            "operator_runbook",
            "Operator Runbook",
            "reports/operator_runbook/operator_runbook.json",
            "reports/operator_runbook/operator_runbook.md",
        ),
        _artifact(
            "weekly_review",
            "Weekly Review",
            "reports/weekly_review/weekly_review.json",
            "reports/weekly_review/weekly_review.md",
        ),
        _artifact(
            "daily_research_command_center",
            "Daily Research Command Center",
            "reports/daily_research_command_center/daily_research_summary.json",
            "reports/daily_research_command_center/daily_research_summary.md",
        ),
        _artifact(
            "safe_workflow_catalog",
            "Safe Workflow Catalog",
            "reports/safe_workflow_catalog/safe_workflow_catalog.json",
            "reports/safe_workflow_catalog/safe_workflow_catalog.md",
            (MONITOR_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE),
        ),
        _artifact(
            "safety_scanner_status",
            "Safety Scanner Status",
            "reports/safety_scanner/safety_scanner_status.json",
            "reports/safety_scanner/safety_scanner_status.md",
            (MONITOR_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE),
        ),
    )


def build_research_release_bundle_payload(
    bundle_input: ResearchReleaseBundleInput,
) -> dict[str, Any]:
    bundle_input.validate()

    artifacts = [_artifact_status(artifact) for artifact in bundle_input.artifacts]
    missing_artifacts = [item for item in artifacts if item["status"] != "present"]
    blocked_artifacts = [item for item in artifacts if item["label"] == BLOCKED_BY_SAFETY_GATE]
    queue_status = _queue_status(bundle_input.queue_path)
    safety_scanner_status = _safety_scanner_status(bundle_input.safety_scanner_path)
    workflow_catalog_summary = _workflow_catalog_summary(bundle_input.safe_workflow_catalog_path)
    dashboard_summary = _dashboard_summary(bundle_input.operator_dashboard_snapshot_path)
    blocked_workflows = _blocked_workflows(
        artifacts,
        queue_status,
        safety_scanner_status,
        workflow_catalog_summary,
        dashboard_summary,
    )

    payload = {
        "phase": "18B",
        "workflow": "Research Release Bundle",
        "bundle_id": bundle_input.bundle_id,
        "bundle_date": bundle_input.bundle_date,
        "generated_at_utc": bundle_input.generated_at_utc,
        "safety_boundary": _safety_boundary(),
        "required_labels": list(SAFE_RELEASE_BUNDLE_LABELS),
        "summary": {
            "artifact_count": len(artifacts),
            "present_artifact_count": len(artifacts) - len(missing_artifacts),
            "missing_artifact_count": len(missing_artifacts),
            "blocked_artifact_count": len(blocked_artifacts),
            "blocked_workflow_count": len(blocked_workflows),
            "queue_item_count": queue_status["queue_item_count"],
            "safety_scanner_status": safety_scanner_status["status"],
            "safety_scanner_finding_count": safety_scanner_status["finding_count"],
            "safe_workflow_count": workflow_catalog_summary["workflow_count"],
            "label_counts": _count_by([*artifacts, *blocked_workflows], "label"),
            "status_counts": _count_by(artifacts, "status"),
        },
        "artifacts": artifacts,
        "missing_artifacts": missing_artifacts,
        "queue_status": queue_status,
        "safety_scanner_status": safety_scanner_status,
        "safe_workflow_catalog_summary": workflow_catalog_summary,
        "operator_dashboard_snapshot_summary": dashboard_summary,
        "blocked_workflows": blocked_workflows,
    }
    _validate_json_value("research_release_bundle_payload", payload)
    return _normalize_json_value(payload)


def write_research_release_bundle(
    bundle_input: ResearchReleaseBundleInput,
    *,
    out_dir: Path = DEFAULT_RESEARCH_RELEASE_BUNDLE_DIR,
) -> tuple[Path, Path]:
    payload = build_research_release_bundle_payload(bundle_input)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / RESEARCH_RELEASE_BUNDLE_JSON
    markdown_path = out_dir / RESEARCH_RELEASE_BUNDLE_MARKDOWN
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_research_release_bundle_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def render_research_release_bundle_markdown(payload: dict[str, Any]) -> str:
    _validate_json_value("research_release_bundle_payload", payload)
    lines = [
        "# 18B Research Release Bundle",
        "",
        f"Bundle ID: {payload['bundle_id']}",
        f"Bundle Date: {payload['bundle_date']}",
        f"Generated: {payload['generated_at_utc']}",
        "",
        "Status: RESEARCH_ONLY / MONITOR_ONLY / PAPER_ONLY / HUMAN_REVIEW_REQUIRED.",
        "BLOCKED_BY_SAFETY_GATE missing artifacts and blocked workflows remain blocked.",
        "LIVE TRADING: DISABLED. No secrets, credential files, broker routing, broker calls, or order execution are used.",
        "",
        "## Summary",
        "",
        _summary_line("Artifacts", payload["summary"]["artifact_count"]),
        _summary_line("Present artifacts", payload["summary"]["present_artifact_count"]),
        _summary_line("Missing artifacts", payload["summary"]["missing_artifact_count"]),
        _summary_line("Blocked artifacts", payload["summary"]["blocked_artifact_count"]),
        _summary_line("Blocked workflows", payload["summary"]["blocked_workflow_count"]),
        _summary_line("Queue items", payload["summary"]["queue_item_count"]),
        _summary_line("Safety scanner findings", payload["summary"]["safety_scanner_finding_count"]),
        _summary_line("Safe workflows", payload["summary"]["safe_workflow_count"]),
        "",
    ]
    lines.extend(_artifact_section("Artifacts", payload["artifacts"]))
    lines.extend(_artifact_section("Missing Artifacts", payload["missing_artifacts"]))
    lines.extend(_workflow_section("Queue Status", [payload["queue_status"]]))
    lines.extend(_workflow_section("Safety Scanner Status", [payload["safety_scanner_status"]]))
    lines.extend(_workflow_section("Safe Workflow Catalog Summary", [payload["safe_workflow_catalog_summary"]]))
    lines.extend(
        _workflow_section(
            "Operator Dashboard Snapshot Summary",
            [payload["operator_dashboard_snapshot_summary"]],
        )
    )
    lines.extend(_workflow_section("Blocked Workflows", payload["blocked_workflows"]))
    lines.extend(
        [
            "## Safety Boundary",
            "",
            "- RESEARCH_ONLY release packaging only.",
            "- MONITOR_ONLY and PAPER_ONLY source artifacts are summarized, not executed.",
            "- HUMAN_REVIEW_REQUIRED remains attached to trade-relevant interpretation.",
            "- BLOCKED_BY_SAFETY_GATE missing artifacts and blocked workflows remain blocked.",
            "- LIVE TRADING: DISABLED.",
            "",
        ]
    )
    return "\n".join(lines)


def _artifact(
    artifact_id: str,
    name: str,
    json_path: str,
    markdown_path: str,
    required_labels: tuple[str, ...] = (
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
        json_path=Path(json_path),
        markdown_path=Path(markdown_path),
        required_labels=required_labels,
    )


def _artifact_status(artifact: ReleaseBundleArtifact) -> dict[str, Any]:
    artifact.validate()
    json_exists = artifact.json_path.is_file()
    markdown_exists = artifact.markdown_path.is_file()
    missing_paths = [
        path.as_posix()
        for path, exists in (
            (artifact.json_path, json_exists),
            (artifact.markdown_path, markdown_exists),
        )
        if not exists
    ]
    metadata = _read_json_object(artifact.json_path) if json_exists else {}
    if metadata:
        _validate_json_value(artifact.artifact_id, metadata)
    label = _metadata_label(metadata, artifact.required_labels, missing_paths)
    status = "present" if json_exists and markdown_exists else "missing"
    item = {
        "artifact_id": artifact.artifact_id,
        "name": artifact.name,
        "json_path": artifact.json_path.as_posix(),
        "markdown_path": artifact.markdown_path.as_posix(),
        "status": status,
        "label": label,
        "required_labels": list(artifact.required_labels),
        "safety_status": _metadata_safety_status(metadata, missing_paths),
        "generated_at_utc": metadata.get("generated_at_utc"),
        "generated_date": _generated_date(metadata),
        "phase": metadata.get("phase"),
        "workflow": metadata.get("workflow", artifact.name),
        "missing_paths": missing_paths,
    }
    _validate_json_value("artifact_status", item)
    return item


def _metadata_label(
    metadata: dict[str, Any],
    required_labels: tuple[str, ...],
    missing_paths: list[str],
) -> str:
    if missing_paths:
        return BLOCKED_BY_SAFETY_GATE
    label = metadata.get("label") or metadata.get("safety_boundary", {}).get("label")
    if label is None:
        return HUMAN_REVIEW_REQUIRED
    if label not in required_labels or label not in SAFE_RELEASE_BUNDLE_LABELS:
        raise ValueError(f"unsafe research release bundle label: {label}")
    return str(label)


def _metadata_safety_status(metadata: dict[str, Any], missing_paths: list[str]) -> str:
    if missing_paths:
        return "missing_artifact"
    return str(
        metadata.get("safety_status")
        or metadata.get("safety_boundary", {}).get("status")
        or metadata.get("status")
        or "LIVE TRADING: DISABLED"
    )


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
    return {
        "workflow_id": "master_plan_queue",
        "label": HUMAN_REVIEW_REQUIRED,
        "status": "read_only",
        "summary": "Master plan queue read for release context only.",
        "path": path.as_posix(),
        "queue_item_count": len(items),
        "next_phase": items[0] if items else None,
        "items": items,
    }


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


def _safety_scanner_status(path: Path) -> dict[str, Any]:
    payload = _read_json_object(path)
    if payload is None:
        return {
            "workflow_id": "safety_scanner",
            "label": HUMAN_REVIEW_REQUIRED,
            "status": "not_run",
            "summary": "Safety scanner status was not supplied to the release bundle.",
            "path": path.as_posix(),
            "finding_count": 0,
            "passed": None,
        }
    _validate_json_value("safety_scanner_status", payload)
    findings = payload.get("findings", [])
    finding_count = payload.get("finding_count", len(findings) if isinstance(findings, list) else 0)
    passed = payload.get("passed")
    return {
        "workflow_id": "safety_scanner",
        "label": payload.get("label", HUMAN_REVIEW_REQUIRED if passed is not False else BLOCKED_BY_SAFETY_GATE),
        "status": payload.get("status", "passed" if passed else "not_run"),
        "summary": payload.get("summary", "Safety scanner status supplied to release bundle."),
        "path": path.as_posix(),
        "finding_count": finding_count,
        "passed": passed,
    }


def _workflow_catalog_summary(path: Path) -> dict[str, Any]:
    payload = _read_json_object(path)
    if payload is None:
        return {
            "workflow_id": "safe_workflow_catalog",
            "label": BLOCKED_BY_SAFETY_GATE,
            "status": "missing",
            "summary": "Safe workflow catalog JSON was not found or could not be parsed.",
            "path": path.as_posix(),
            "workflow_count": 0,
            "blocked_behavior_count": 0,
            "blocked_behaviors": [],
        }
    _validate_json_value("safe_workflow_catalog", payload)
    workflows = payload.get("workflows", [])
    blocked_behaviors = payload.get("blocked_behaviors", [])
    return {
        "workflow_id": "safe_workflow_catalog",
        "label": payload.get("safety_boundary", {}).get("label", HUMAN_REVIEW_REQUIRED),
        "status": payload.get("safety_boundary", {}).get("status", "LIVE TRADING: DISABLED"),
        "summary": "Safe workflow catalog summarized for release packaging.",
        "path": path.as_posix(),
        "workflow_count": len(workflows) if isinstance(workflows, list) else 0,
        "blocked_behavior_count": len(blocked_behaviors) if isinstance(blocked_behaviors, list) else 0,
        "blocked_behaviors": blocked_behaviors if isinstance(blocked_behaviors, list) else [],
    }


def _dashboard_summary(path: Path) -> dict[str, Any]:
    payload = _read_json_object(path)
    if payload is None:
        return {
            "workflow_id": "operator_dashboard_snapshot",
            "label": BLOCKED_BY_SAFETY_GATE,
            "status": "missing",
            "summary": "Operator dashboard snapshot JSON was not found or could not be parsed.",
            "path": path.as_posix(),
            "blocked_workflow_count": 0,
            "blocked_workflows": [],
        }
    _validate_json_value("operator_dashboard_snapshot", payload)
    blocked_workflows = payload.get("blocked_workflows", [])
    summary = payload.get("summary", {})
    return {
        "workflow_id": "operator_dashboard_snapshot",
        "label": payload.get("safety_boundary", {}).get("label", HUMAN_REVIEW_REQUIRED),
        "status": payload.get("safety_boundary", {}).get("status", "LIVE TRADING: DISABLED"),
        "summary": "Operator dashboard snapshot summarized for release packaging.",
        "path": path.as_posix(),
        "blocked_workflow_count": summary.get(
            "blocked_workflow_count",
            len(blocked_workflows) if isinstance(blocked_workflows, list) else 0,
        ),
        "blocked_workflows": blocked_workflows if isinstance(blocked_workflows, list) else [],
    }


def _blocked_workflows(
    artifacts: list[dict[str, Any]],
    queue_status: dict[str, Any],
    safety_scanner_status: dict[str, Any],
    workflow_catalog_summary: dict[str, Any],
    dashboard_summary: dict[str, Any],
) -> list[dict[str, Any]]:
    blocked: list[dict[str, Any]] = [
        {
            "workflow_id": "live_trading",
            "label": BLOCKED_BY_SAFETY_GATE,
            "status": "blocked",
            "summary": "Live trading remains disabled.",
            "source": "release_bundle_safety_boundary",
        },
        {
            "workflow_id": "broker_order_routing",
            "label": BLOCKED_BY_SAFETY_GATE,
            "status": "blocked",
            "summary": "Broker routing is outside the 18B research release bundle.",
            "source": "release_bundle_safety_boundary",
        },
        {
            "workflow_id": "broker_order_call",
            "label": BLOCKED_BY_SAFETY_GATE,
            "status": "blocked",
            "summary": "Broker order calls are not allowed.",
            "source": "release_bundle_safety_boundary",
        },
        {
            "workflow_id": "order_execution",
            "label": BLOCKED_BY_SAFETY_GATE,
            "status": "blocked",
            "summary": "Order execution is not part of this workflow.",
            "source": "release_bundle_safety_boundary",
        },
        {
            "workflow_id": "secret_or_credential_access",
            "label": BLOCKED_BY_SAFETY_GATE,
            "status": "blocked",
            "summary": "Secrets and credential files are not required and must not be opened.",
            "source": "release_bundle_safety_boundary",
        },
    ]
    for artifact in artifacts:
        if artifact["status"] != "present":
            blocked.append(
                {
                    "workflow_id": f"missing_{artifact['artifact_id']}",
                    "label": BLOCKED_BY_SAFETY_GATE,
                    "status": "blocked",
                    "summary": f"{artifact['name']} is missing: {', '.join(artifact['missing_paths'])}.",
                    "source": "artifact_status",
                }
            )
    for item in (queue_status, safety_scanner_status, workflow_catalog_summary, dashboard_summary):
        if item.get("label") == BLOCKED_BY_SAFETY_GATE or item.get("status") in {"missing", "invalid", "blocked"}:
            blocked.append(
                {
                    "workflow_id": item.get("workflow_id", "workflow"),
                    "label": BLOCKED_BY_SAFETY_GATE,
                    "status": "blocked",
                    "summary": item.get("summary", "Workflow is blocked or incomplete."),
                    "source": "release_bundle_status",
                }
            )
    for item in dashboard_summary.get("blocked_workflows", []):
        if isinstance(item, dict):
            blocked.append(
                {
                    "workflow_id": item.get("workflow_id", "workflow"),
                    "label": BLOCKED_BY_SAFETY_GATE,
                    "status": "blocked",
                    "summary": item.get("summary", "Dashboard workflow remains blocked."),
                    "source": "operator_dashboard_snapshot",
                }
            )
    return _dedupe_workflows(blocked)


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
    return sorted(by_id.values(), key=_sort_key)


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


def _read_json_object(path: Path) -> dict[str, Any] | None:
    value = _read_json_value(path)
    return value if isinstance(value, dict) else None


def _read_json_value(path: Path) -> Any:
    _validate_bundle_path(path)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def _generated_date(payload: dict[str, Any]) -> str | None:
    for key in (
        "bundle_date",
        "index_date",
        "snapshot_date",
        "evidence_date",
        "journal_date",
        "runbook_date",
        "week_end",
        "report_date",
        "catalog_date",
    ):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    generated_at = payload.get("generated_at_utc")
    if isinstance(generated_at, str) and len(generated_at) >= 10:
        return generated_at[:10]
    return None


def _artifact_section(title: str, items: list[dict[str, Any]]) -> list[str]:
    lines = [f"## {title}", ""]
    if not items:
        return [*lines, "- None recorded.", ""]
    for item in items:
        missing = ""
        if item.get("missing_paths"):
            missing = f" | missing: {', '.join(item['missing_paths'])}"
        lines.append(
            f"- {item['artifact_id']} | {item['label']} | {item['status']} | "
            f"{item['safety_status']} | {item['json_path']} | {item['markdown_path']}{missing}"
        )
    lines.append("")
    return lines


def _workflow_section(title: str, items: list[dict[str, Any]]) -> list[str]:
    lines = [f"## {title}", ""]
    if not items:
        return [*lines, "- None recorded.", ""]
    for item in items:
        item_id = item.get("workflow_id") or item.get("artifact_id") or item.get("status") or "item"
        label = item.get("label", "n/a")
        status = item.get("status") or item.get("safety_status") or "recorded"
        summary = item.get("summary", "Recorded.")
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


def _sort_key(item: dict[str, Any]) -> tuple[str, str]:
    return (
        str(item.get("source", "")),
        str(item.get("workflow_id") or item.get("artifact_id") or json.dumps(item, sort_keys=True)),
    )


def _validate_bundle_path(path: Path) -> None:
    if path.name in SECRET_FILE_NAMES:
        raise ValueError("research release bundle cannot target secret files")
    lowered_parts = [part.lower() for part in path.parts]
    if any(marker in part for part in lowered_parts for marker in SECRET_PATH_MARKERS):
        raise ValueError("research release bundle cannot target credential or secret paths")
    if path.is_absolute():
        raise ValueError("research release bundle paths must be repo-relative")
    if ".." in path.parts:
        raise ValueError("research release bundle paths cannot traverse parent directories")


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
        if label is not None and label not in SAFE_RELEASE_BUNDLE_LABELS:
            raise ValueError(f"unsafe research release bundle label: {label}")
        if label in DISALLOWED_RELEASE_BUNDLE_LABELS:
            raise ValueError(f"disallowed research release bundle label: {label}")
        for unsafe_field in UNSAFE_TRUE_FIELDS:
            if value.get(unsafe_field) is True:
                raise ValueError(f"research release bundle cannot set {unsafe_field}")
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
        if value in DISALLOWED_RELEASE_BUNDLE_LABELS:
            raise ValueError(f"disallowed research release bundle text: {value}")
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
