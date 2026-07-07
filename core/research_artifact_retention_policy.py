from __future__ import annotations

import json
import re
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


DEFAULT_RESEARCH_ARTIFACT_RETENTION_POLICY_DIR = Path("reports/research_artifact_retention_policy")
RESEARCH_ARTIFACT_RETENTION_POLICY_JSON = "research_artifact_retention_policy.json"
RESEARCH_ARTIFACT_RETENTION_POLICY_MARKDOWN = "research_artifact_retention_policy.md"

KEEP = "keep"
REVIEW = "review"
ARCHIVE_CANDIDATE = "archive_candidate"
BLOCKED_DELETE = "blocked_delete"

SAFE_RETENTION_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
RETENTION_ACTIONS = (KEEP, REVIEW, ARCHIVE_CANDIDATE, BLOCKED_DELETE)
DISALLOWED_RETENTION_LABELS = tuple(
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
PROTECTED_REPORT_TYPES = {
    "Decision Journal",
    "Operator Dashboard Snapshot",
    "Operator Runbook",
    "Research Cycle Audit Summary",
    "Research Evidence Pack",
    "Research Release Bundle",
}
DATE_KEYS = (
    "retention_date",
    "cycle_date",
    "audit_date",
    "bundle_date",
    "snapshot_date",
    "index_date",
    "evidence_date",
    "journal_date",
    "runbook_date",
    "week_end",
    "report_date",
    "catalog_date",
)
REFERENCE_PATTERN = re.compile(r"[\w./\\-]+(?:\.json|\.md|/|\\)")


@dataclass(frozen=True)
class RetentionArtifactTarget:
    artifact_id: str
    report_type: str
    json_path: Path | None = None
    markdown_path: Path | None = None
    directory_path: Path | None = None
    expected_label: str = HUMAN_REVIEW_REQUIRED

    def validate(self) -> None:
        for field_name in ("artifact_id", "report_type"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"research artifact retention target requires {field_name}")
        if self.expected_label not in SAFE_RETENTION_LABELS:
            raise ValueError(f"unsafe research artifact retention label: {self.expected_label}")
        paths = (self.json_path, self.markdown_path, self.directory_path)
        if not any(path is not None for path in paths):
            raise ValueError("retention target requires at least one path")
        for path in paths:
            if path is not None:
                _validate_retention_path(path)


@dataclass(frozen=True)
class ResearchArtifactRetentionPolicyInput:
    policy_id: str
    retention_date: str
    generated_at_utc: str
    artifacts: tuple[RetentionArtifactTarget, ...] = field(default_factory=tuple)
    reference_sources: tuple[Path, ...] = field(default_factory=tuple)
    keep_days: int = 14
    archive_after_days: int = 60

    def validate(self) -> None:
        for field_name in ("policy_id", "retention_date", "generated_at_utc"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"research artifact retention policy requires {field_name}")
        _parse_iso_date("retention_date", self.retention_date)
        _parse_iso_datetime("generated_at_utc", self.generated_at_utc)
        if not isinstance(self.artifacts, tuple) or not self.artifacts:
            raise ValueError("artifacts must be a non-empty tuple")
        if self.keep_days < 0:
            raise ValueError("keep_days must be non-negative")
        if self.archive_after_days <= self.keep_days:
            raise ValueError("archive_after_days must be greater than keep_days")
        for artifact in self.artifacts:
            artifact.validate()
        for path in self.reference_sources:
            _validate_retention_path(path)


def build_default_research_artifact_retention_policy_input(
    *,
    retention_date: date | None = None,
    now: datetime | None = None,
) -> ResearchArtifactRetentionPolicyInput:
    generated = now or datetime.now(tz=UTC)
    day = retention_date or generated.date()
    return ResearchArtifactRetentionPolicyInput(
        policy_id=f"20B-RESEARCH-ARTIFACT-RETENTION-POLICY-{day.isoformat()}",
        retention_date=day.isoformat(),
        generated_at_utc=generated.isoformat(),
        artifacts=default_retention_artifacts(),
        reference_sources=default_reference_sources(),
    )


def default_retention_artifacts() -> tuple[RetentionArtifactTarget, ...]:
    return (
        _artifact(
            "research_release_bundle",
            "Research Release Bundle",
            "reports/research_release_bundle/research_release_bundle.json",
            "reports/research_release_bundle/research_release_bundle.md",
            "reports/research_release_bundle",
        ),
        _artifact(
            "research_cycle_audit_summary",
            "Research Cycle Audit Summary",
            "reports/research_cycle_audit_summary/research_cycle_audit_summary.json",
            "reports/research_cycle_audit_summary/research_cycle_audit_summary.md",
            "reports/research_cycle_audit_summary",
        ),
        _artifact(
            "operator_dashboard_snapshot",
            "Operator Dashboard Snapshot",
            "reports/operator_dashboard_snapshot/operator_dashboard_snapshot.json",
            "reports/operator_dashboard_snapshot/operator_dashboard_snapshot.md",
            "reports/operator_dashboard_snapshot",
            MONITOR_ONLY,
        ),
        _artifact(
            "research_evidence_pack",
            "Research Evidence Pack",
            "reports/research_evidence_pack/research_evidence_pack.json",
            "reports/research_evidence_pack/research_evidence_pack.md",
            "reports/research_evidence_pack",
        ),
        _artifact(
            "decision_journal",
            "Decision Journal",
            "reports/decision_journal/decision_journal.json",
            "reports/decision_journal/decision_journal.md",
            "reports/decision_journal",
        ),
        _artifact(
            "operator_runbook",
            "Operator Runbook",
            "reports/operator_runbook/operator_runbook.json",
            "reports/operator_runbook/operator_runbook.md",
            "reports/operator_runbook",
        ),
        _artifact(
            "report_index",
            "Report Index",
            "reports/report_index/report_index.json",
            "reports/report_index/report_index.md",
            "reports/report_index",
        ),
        _artifact(
            "daily_research_command_center",
            "Daily Research Command Center",
            "reports/daily_research_command_center/daily_research_summary.json",
            "reports/daily_research_command_center/daily_research_summary.md",
            "reports/daily_research_command_center",
            RESEARCH_ONLY,
        ),
        _artifact(
            "weekly_review",
            "Weekly Review",
            "reports/weekly_review/weekly_review.json",
            "reports/weekly_review/weekly_review.md",
            "reports/weekly_review",
        ),
        _artifact(
            "safe_workflow_catalog",
            "Safe Workflow Catalog",
            "reports/safe_workflow_catalog/safe_workflow_catalog.json",
            "reports/safe_workflow_catalog/safe_workflow_catalog.md",
            "reports/safe_workflow_catalog",
            MONITOR_ONLY,
        ),
    )


def default_reference_sources() -> tuple[Path, ...]:
    return (
        Path("reports/research_release_bundle/research_release_bundle.json"),
        Path("reports/research_cycle_audit_summary/research_cycle_audit_summary.json"),
        Path("reports/operator_dashboard_snapshot/operator_dashboard_snapshot.json"),
        Path("reports/research_evidence_pack/research_evidence_pack.json"),
        Path("reports/decision_journal/decision_journal.json"),
        Path("reports/operator_runbook/operator_runbook.json"),
    )


def build_research_artifact_retention_policy_payload(
    policy_input: ResearchArtifactRetentionPolicyInput,
) -> dict[str, Any]:
    policy_input.validate()
    retention_day = datetime.strptime(policy_input.retention_date, "%Y-%m-%d").date()
    reference_index = _reference_index(policy_input.reference_sources)
    artifacts = [
        _artifact_entry(
            artifact,
            retention_day=retention_day,
            keep_days=policy_input.keep_days,
            archive_after_days=policy_input.archive_after_days,
            reference_index=reference_index,
        )
        for artifact in policy_input.artifacts
    ]
    dry_run_manifest = [_dry_run_item(item) for item in artifacts if item["retention_action"] != KEEP]

    payload = {
        "phase": "20B",
        "workflow": "Research Artifact Retention Policy",
        "policy_id": policy_input.policy_id,
        "retention_date": policy_input.retention_date,
        "generated_at_utc": policy_input.generated_at_utc,
        "safety_boundary": _safety_boundary(),
        "required_labels": list(SAFE_RETENTION_LABELS),
        "allowed_retention_actions": list(RETENTION_ACTIONS),
        "policy_rules": {
            "keep_days": policy_input.keep_days,
            "archive_after_days": policy_input.archive_after_days,
            "delete_files_automatically": False,
            "dry_run_only": True,
            "referenced_artifacts_are_kept": True,
            "missing_or_unsafe_artifacts_are_blocked_delete": True,
        },
        "summary": {
            "artifact_count": len(artifacts),
            "reference_source_count": len(policy_input.reference_sources),
            "dry_run_manifest_count": len(dry_run_manifest),
            "missing_artifact_count": len([item for item in artifacts if item["status"] == "missing"]),
            "referenced_artifact_count": len([item for item in artifacts if item["referenced_by"]]),
            "retention_action_counts": _count_by(artifacts, "retention_action"),
            "label_counts": _count_by(artifacts, "label"),
        },
        "reference_sources": reference_index["sources"],
        "artifacts": artifacts,
        "dry_run_manifest": dry_run_manifest,
        "blocked_workflows": _blocked_workflows(),
    }
    _validate_json_value("research_artifact_retention_policy_payload", payload)
    return _normalize_json_value(payload)


def write_research_artifact_retention_policy(
    policy_input: ResearchArtifactRetentionPolicyInput,
    *,
    out_dir: Path = DEFAULT_RESEARCH_ARTIFACT_RETENTION_POLICY_DIR,
) -> tuple[Path, Path]:
    payload = build_research_artifact_retention_policy_payload(policy_input)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / RESEARCH_ARTIFACT_RETENTION_POLICY_JSON
    markdown_path = out_dir / RESEARCH_ARTIFACT_RETENTION_POLICY_MARKDOWN
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_research_artifact_retention_policy_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def render_research_artifact_retention_policy_markdown(payload: dict[str, Any]) -> str:
    _validate_json_value("research_artifact_retention_policy_payload", payload)
    lines = [
        "# 20B Research Artifact Retention Policy",
        "",
        f"Policy ID: {payload['policy_id']}",
        f"Retention Date: {payload['retention_date']}",
        f"Generated: {payload['generated_at_utc']}",
        "",
        "Status: RESEARCH_ONLY / MONITOR_ONLY / PAPER_ONLY / HUMAN_REVIEW_REQUIRED.",
        "Retention actions are dry-run only: keep, review, archive_candidate, or blocked_delete.",
        "LIVE TRADING: DISABLED. No secrets, credential files, broker routing, broker calls, order execution, or automatic file deletion are used.",
        "",
        "## Summary",
        "",
        _summary_line("Artifacts", payload["summary"]["artifact_count"]),
        _summary_line("Referenced artifacts", payload["summary"]["referenced_artifact_count"]),
        _summary_line("Missing artifacts", payload["summary"]["missing_artifact_count"]),
        _summary_line("Dry-run manifest items", payload["summary"]["dry_run_manifest_count"]),
        "",
    ]
    lines.extend(_section("Artifacts", payload["artifacts"]))
    lines.extend(_section("Dry-Run Manifest", payload["dry_run_manifest"]))
    lines.extend(_section("Reference Sources", payload["reference_sources"]))
    lines.extend(_section("Blocked Workflows", payload["blocked_workflows"]))
    lines.extend(
        [
            "## Safety Boundary",
            "",
            "- RESEARCH_ONLY retention policy generation only.",
            "- MONITOR_ONLY and PAPER_ONLY artifacts are classified, not executed.",
            "- HUMAN_REVIEW_REQUIRED artifacts require review before any future retention action.",
            "- BLOCKED_BY_SAFETY_GATE artifacts cannot be deleted by this policy.",
            "- LIVE TRADING: DISABLED.",
            "- Automatic deletion: disabled.",
            "",
        ]
    )
    return "\n".join(lines)


def _artifact(
    artifact_id: str,
    report_type: str,
    json_path: str,
    markdown_path: str,
    directory_path: str,
    expected_label: str = HUMAN_REVIEW_REQUIRED,
) -> RetentionArtifactTarget:
    return RetentionArtifactTarget(
        artifact_id=artifact_id,
        report_type=report_type,
        json_path=Path(json_path),
        markdown_path=Path(markdown_path),
        directory_path=Path(directory_path),
        expected_label=expected_label,
    )


def _artifact_entry(
    artifact: RetentionArtifactTarget,
    *,
    retention_day: date,
    keep_days: int,
    archive_after_days: int,
    reference_index: dict[str, Any],
) -> dict[str, Any]:
    artifact.validate()
    paths = [path for path in (artifact.json_path, artifact.markdown_path, artifact.directory_path) if path is not None]
    missing_paths = [path.as_posix() for path in paths if not path.exists()]
    metadata = _read_json_object(artifact.json_path) if artifact.json_path is not None and artifact.json_path.is_file() else {}
    if metadata:
        _validate_json_value("artifact_metadata", metadata)
    label = _metadata_label(metadata, artifact.expected_label, missing_paths)
    generated_date = _generated_date(metadata)
    referenced_by = _referenced_by(paths, reference_index)
    age_days = _age_days(retention_day, generated_date)
    status = "missing" if missing_paths else "present"
    retention_action, reasons = _classify(
        artifact,
        status=status,
        label=label,
        generated_date=generated_date,
        age_days=age_days,
        referenced_by=referenced_by,
        keep_days=keep_days,
        archive_after_days=archive_after_days,
        metadata=metadata,
    )
    item = {
        "artifact_id": artifact.artifact_id,
        "report_type": artifact.report_type,
        "json_path": artifact.json_path.as_posix() if artifact.json_path else None,
        "markdown_path": artifact.markdown_path.as_posix() if artifact.markdown_path else None,
        "directory_path": artifact.directory_path.as_posix() if artifact.directory_path else None,
        "status": status,
        "label": label,
        "safety_status": _metadata_safety_status(metadata, missing_paths),
        "generated_date": generated_date,
        "generated_at_utc": metadata.get("generated_at_utc"),
        "age_days": age_days,
        "phase": metadata.get("phase"),
        "workflow": metadata.get("workflow", artifact.report_type),
        "missing_paths": missing_paths,
        "referenced_by": referenced_by,
        "retention_action": retention_action,
        "retention_reasons": reasons,
        "automatic_delete_allowed": False,
        "dry_run_only": True,
    }
    _validate_json_value("retention_artifact_entry", item)
    return _normalize_json_value(item)


def _classify(
    artifact: RetentionArtifactTarget,
    *,
    status: str,
    label: str,
    generated_date: str | None,
    age_days: int | None,
    referenced_by: list[str],
    keep_days: int,
    archive_after_days: int,
    metadata: dict[str, Any],
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if status == "missing":
        return BLOCKED_DELETE, ["missing artifact path cannot be deleted by policy"]
    if _unsafe_metadata(metadata):
        return BLOCKED_DELETE, ["unsafe execution or credential metadata blocks deletion"]
    if label == BLOCKED_BY_SAFETY_GATE:
        return BLOCKED_DELETE, ["blocked safety-gate label prevents deletion"]
    if referenced_by:
        return KEEP, [f"referenced by {', '.join(referenced_by)}"]
    if artifact.report_type in PROTECTED_REPORT_TYPES:
        return KEEP, ["protected report type"]
    if generated_date is None or age_days is None:
        return REVIEW, ["missing generated date requires human review"]
    if age_days <= keep_days:
        return KEEP, [f"artifact age {age_days} days is within keep window"]
    if label == HUMAN_REVIEW_REQUIRED:
        return REVIEW, ["human-review-required label requires review before archival"]
    if age_days >= archive_after_days and label in {RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY}:
        return ARCHIVE_CANDIDATE, [f"artifact age {age_days} days exceeds archive threshold"]
    reasons.append(f"artifact age {age_days} days requires review before archival")
    return REVIEW, reasons


def _dry_run_item(item: dict[str, Any]) -> dict[str, Any]:
    value = {
        "artifact_id": item["artifact_id"],
        "report_type": item["report_type"],
        "retention_action": item["retention_action"],
        "label": item["label"],
        "status": item["status"],
        "json_path": item["json_path"],
        "markdown_path": item["markdown_path"],
        "directory_path": item["directory_path"],
        "referenced_by": item["referenced_by"],
        "retention_reasons": item["retention_reasons"],
        "automatic_delete_allowed": False,
        "dry_run_only": True,
    }
    _validate_json_value("dry_run_manifest_item", value)
    return _normalize_json_value(value)


def _reference_index(reference_sources: tuple[Path, ...]) -> dict[str, Any]:
    referenced_paths: dict[str, set[str]] = {}
    sources = []
    for source in reference_sources:
        _validate_retention_path(source)
        source_key = source.as_posix()
        status = "missing"
        count = 0
        if source.is_file():
            status = "present"
            referenced = _extract_references(source)
            referenced.add(source_key)
            count = len(referenced)
            for path in referenced:
                referenced_paths.setdefault(_normalize_path_string(path), set()).add(source_key)
        source_item = {
            "source_id": source.stem,
            "path": source_key,
            "label": HUMAN_REVIEW_REQUIRED if status == "present" else BLOCKED_BY_SAFETY_GATE,
            "status": status,
            "summary": f"Reference source {status}; {count} candidate path references recorded.",
            "reference_count": count,
        }
        _validate_json_value("reference_source", source_item)
        sources.append(_normalize_json_value(source_item))
    return {
        "paths": referenced_paths,
        "sources": sorted(sources, key=_sort_key),
    }


def _extract_references(path: Path) -> set[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return set()
    references = {
        _normalize_path_string(match.group(0).rstrip(".,);]\"'"))
        for match in REFERENCE_PATTERN.finditer(text)
        if _looks_like_report_path(match.group(0))
    }
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return references
    references.update(_json_path_strings(payload))
    return {_normalize_path_string(item) for item in references if item}


def _json_path_strings(value: Any) -> set[str]:
    if isinstance(value, dict):
        found = set()
        for item in value.values():
            found.update(_json_path_strings(item))
        return found
    if isinstance(value, list):
        found = set()
        for item in value:
            found.update(_json_path_strings(item))
        return found
    if isinstance(value, str) and _looks_like_report_path(value):
        return {_normalize_path_string(value)}
    return set()


def _looks_like_report_path(value: str) -> bool:
    normalized = _normalize_path_string(value.rstrip(".,);]\"'"))
    return normalized.startswith("reports/") and (
        normalized.endswith(".json") or normalized.endswith(".md") or "/" in normalized
    )


def _referenced_by(paths: list[Path], reference_index: dict[str, Any]) -> list[str]:
    referenced = set()
    path_index: dict[str, set[str]] = reference_index["paths"]
    for path in paths:
        normalized = _normalize_path_string(path.as_posix())
        referenced.update(path_index.get(normalized, set()))
        prefix = normalized.rstrip("/") + "/"
        for candidate, sources in path_index.items():
            if candidate.startswith(prefix):
                referenced.update(sources)
    return sorted(referenced)


def _metadata_label(metadata: dict[str, Any], default_label: str, missing_paths: list[str]) -> str:
    if missing_paths:
        return BLOCKED_BY_SAFETY_GATE
    label = metadata.get("label") or metadata.get("safety_boundary", {}).get("label") or default_label
    if label not in SAFE_RETENTION_LABELS:
        raise ValueError(f"unsafe research artifact retention label: {label}")
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


def _unsafe_metadata(metadata: dict[str, Any]) -> bool:
    return any(metadata.get(field) is True for field in UNSAFE_TRUE_FIELDS)


def _read_json_object(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    _validate_retention_path(path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _generated_date(payload: dict[str, Any]) -> str | None:
    for key in DATE_KEYS:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value[:10]
    generated_at = payload.get("generated_at_utc")
    if isinstance(generated_at, str) and len(generated_at) >= 10:
        return generated_at[:10]
    return None


def _age_days(retention_day: date, generated_date: str | None) -> int | None:
    if generated_date is None:
        return None
    try:
        generated_day = datetime.strptime(generated_date, "%Y-%m-%d").date()
    except ValueError:
        return None
    return (retention_day - generated_day).days


def _blocked_workflows() -> list[dict[str, Any]]:
    return [
        {
            "workflow_id": "automatic_file_deletion",
            "label": BLOCKED_BY_SAFETY_GATE,
            "status": "blocked",
            "summary": "20B may only produce a reviewable dry-run retention manifest.",
        },
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
            "summary": "Broker routing is outside the 20B retention policy.",
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
        "automatic_file_deletion_enabled": False,
        "dry_run_only": True,
        "status": "LIVE TRADING: DISABLED",
    }


def _section(title: str, items: list[dict[str, Any]]) -> list[str]:
    lines = [f"## {title}", ""]
    if not items:
        return [*lines, "- None recorded.", ""]
    for item in items:
        item_id = (
            item.get("artifact_id")
            or item.get("workflow_id")
            or item.get("source_id")
            or item.get("path")
            or "item"
        )
        label = item.get("label", "n/a")
        status = item.get("retention_action") or item.get("status") or "recorded"
        summary = item.get("summary") or item.get("report_type") or ", ".join(item.get("retention_reasons", []))
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
        str(
            item.get("artifact_id")
            or item.get("workflow_id")
            or item.get("source_id")
            or item.get("path")
            or json.dumps(item, sort_keys=True)
        ),
    )


def _validate_retention_path(path: Path) -> None:
    if path.name in SECRET_FILE_NAMES:
        raise ValueError("research artifact retention policy cannot target secret files")
    lowered_parts = [part.lower() for part in path.parts]
    if any(marker in part for part in lowered_parts for marker in SECRET_PATH_MARKERS):
        raise ValueError("research artifact retention policy cannot target credential or secret paths")
    if path.is_absolute():
        raise ValueError("research artifact retention policy paths must be repo-relative")
    if ".." in path.parts:
        raise ValueError("research artifact retention policy paths cannot traverse parent directories")


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
        if label is not None and label not in SAFE_RETENTION_LABELS:
            raise ValueError(f"unsafe research artifact retention label: {label}")
        if label in DISALLOWED_RETENTION_LABELS:
            raise ValueError(f"disallowed research artifact retention label: {label}")
        action = value.get("retention_action")
        if action is not None and action not in RETENTION_ACTIONS:
            raise ValueError(f"invalid research artifact retention action: {action}")
        for unsafe_field in UNSAFE_TRUE_FIELDS:
            if value.get(unsafe_field) is True:
                raise ValueError(f"research artifact retention policy cannot set {unsafe_field}")
        if value.get("automatic_delete_allowed") is True:
            raise ValueError("research artifact retention policy cannot allow automatic deletion")
        if value.get("automatic_file_deletion_enabled") is True:
            raise ValueError("research artifact retention policy cannot enable automatic deletion")
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
        if value in DISALLOWED_RETENTION_LABELS:
            raise ValueError(f"disallowed research artifact retention text: {value}")
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


def _normalize_path_string(value: str) -> str:
    return value.replace("\\", "/").strip().lstrip("./")
