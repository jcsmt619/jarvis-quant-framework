from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from core.report_index import (
    DEFAULT_REPORT_INDEX_DIR,
    REPORT_INDEX_JSON,
    build_default_report_index_input,
    build_report_index_payload,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


DEFAULT_OPERATOR_DASHBOARD_SNAPSHOT_DIR = Path("reports/operator_dashboard_snapshot")
OPERATOR_DASHBOARD_SNAPSHOT_JSON = "operator_dashboard_snapshot.json"
OPERATOR_DASHBOARD_SNAPSHOT_MARKDOWN = "operator_dashboard_snapshot.md"

SAFE_OPERATOR_DASHBOARD_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
DISALLOWED_OPERATOR_DASHBOARD_LABELS = tuple(
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
SORT_KEYS = (
    "workflow_id",
    "report_id",
    "phase",
    "queue_id",
    "status",
    "summary",
)


@dataclass(frozen=True)
class OperatorDashboardSnapshotInput:
    snapshot_id: str
    snapshot_date: str
    generated_at_utc: str
    report_index_path: Path = DEFAULT_REPORT_INDEX_DIR / REPORT_INDEX_JSON
    queue_path: Path = Path("config/jarvis_master_plan_queue.json")
    daily_research_path: Path = Path(
        "reports/daily_research_command_center/daily_research_summary.json"
    )
    weekly_review_path: Path = Path("reports/weekly_review/weekly_review.json")
    evidence_pack_path: Path = Path("reports/research_evidence_pack/research_evidence_pack.json")
    decision_journal_path: Path = Path("reports/decision_journal/decision_journal.json")
    operator_runbook_path: Path = Path("reports/operator_runbook/operator_runbook.json")
    safety_scanner_path: Path = Path("reports/safety_scanner/safety_scanner_status.json")

    def validate(self) -> None:
        for field_name in ("snapshot_id", "snapshot_date", "generated_at_utc"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"operator dashboard snapshot requires {field_name}")
        _parse_iso_date("snapshot_date", self.snapshot_date)
        _parse_iso_datetime("generated_at_utc", self.generated_at_utc)
        for path in (
            self.report_index_path,
            self.queue_path,
            self.daily_research_path,
            self.weekly_review_path,
            self.evidence_pack_path,
            self.decision_journal_path,
            self.operator_runbook_path,
            self.safety_scanner_path,
        ):
            _validate_read_path(path)


def build_default_operator_dashboard_snapshot_input(
    *,
    snapshot_date: date | None = None,
    now: datetime | None = None,
) -> OperatorDashboardSnapshotInput:
    generated = now or datetime.now(tz=UTC)
    day = snapshot_date or generated.date()
    return OperatorDashboardSnapshotInput(
        snapshot_id=f"17B-OPERATOR-DASHBOARD-SNAPSHOT-{day.isoformat()}",
        snapshot_date=day.isoformat(),
        generated_at_utc=generated.isoformat(),
    )


def build_operator_dashboard_snapshot_payload(
    snapshot_input: OperatorDashboardSnapshotInput,
) -> dict[str, Any]:
    snapshot_input.validate()

    report_index = _report_index_payload(snapshot_input)
    daily_research = _workflow_status("daily_research", snapshot_input.daily_research_path)
    weekly_review = _workflow_status("weekly_review", snapshot_input.weekly_review_path)
    evidence_pack = _workflow_status("research_evidence_pack", snapshot_input.evidence_pack_path)
    decision_journal = _workflow_status("decision_journal", snapshot_input.decision_journal_path)
    operator_runbook = _workflow_status("operator_runbook", snapshot_input.operator_runbook_path)
    queue_status = _queue_status(snapshot_input.queue_path)
    safety_scanner = _safety_scanner_status(snapshot_input.safety_scanner_path, report_index)

    allowed_workflows = _allowed_human_review_workflows(operator_runbook, decision_journal)
    blocked_workflows = _blocked_workflows(operator_runbook, decision_journal, report_index)
    blocked_workflows = _dedupe_workflows(
        (
            *blocked_workflows,
            *_blocked_from_statuses(
                daily_research,
                weekly_review,
                evidence_pack,
                decision_journal,
                operator_runbook,
                queue_status,
                safety_scanner,
            ),
        )
    )

    system_state = {
        "status": "read_only_snapshot",
        "label": HUMAN_REVIEW_REQUIRED,
        "summary": "Operator dashboard snapshot generated from read-only report metadata.",
        "live_trading_enabled": False,
        "broker_order_routing_enabled": False,
        "broker_order_call_performed": False,
        "real_paper_order_submitted": False,
        "secrets_required": False,
        "credential_file_used": False,
        "status_text": "LIVE TRADING: DISABLED",
    }
    statuses = (
        daily_research,
        weekly_review,
        evidence_pack,
        decision_journal,
        operator_runbook,
        queue_status,
        safety_scanner,
    )
    payload = {
        "phase": "17B",
        "workflow": "Operator Dashboard Snapshot",
        "snapshot_id": snapshot_input.snapshot_id,
        "snapshot_date": snapshot_input.snapshot_date,
        "generated_at_utc": snapshot_input.generated_at_utc,
        "safety_boundary": _safety_boundary(),
        "required_labels": list(SAFE_OPERATOR_DASHBOARD_LABELS),
        "summary": {
            "latest_report_index_entry_count": len(report_index["latest_entries"]),
            "present_report_count": report_index["summary"]["present_report_count"],
            "missing_report_count": report_index["summary"]["missing_report_count"],
            "allowed_human_review_workflow_count": len(allowed_workflows),
            "blocked_workflow_count": len(blocked_workflows),
            "queue_item_count": queue_status["queue_item_count"],
            "safety_scanner_status": safety_scanner["status"],
            "safety_scanner_finding_count": safety_scanner["finding_count"],
            "label_counts": _count_by(
                [
                    system_state,
                    *report_index["latest_entries"],
                    *statuses,
                    *allowed_workflows,
                    *blocked_workflows,
                ],
                "label",
            ),
        },
        "system_state": system_state,
        "latest_report_index": report_index,
        "workflow_status": {
            "daily_research": daily_research,
            "weekly_review": weekly_review,
            "research_evidence_pack": evidence_pack,
            "decision_journal": decision_journal,
            "operator_runbook": operator_runbook,
            "queue": queue_status,
            "safety_scanner": safety_scanner,
        },
        "allowed_human_review_workflows": allowed_workflows,
        "blocked_workflows": blocked_workflows,
    }
    _validate_json_value("operator_dashboard_snapshot_payload", payload)
    return _normalize_json_value(payload)


def write_operator_dashboard_snapshot(
    snapshot_input: OperatorDashboardSnapshotInput,
    *,
    out_dir: Path = DEFAULT_OPERATOR_DASHBOARD_SNAPSHOT_DIR,
) -> tuple[Path, Path]:
    payload = build_operator_dashboard_snapshot_payload(snapshot_input)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / OPERATOR_DASHBOARD_SNAPSHOT_JSON
    markdown_path = out_dir / OPERATOR_DASHBOARD_SNAPSHOT_MARKDOWN
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_operator_dashboard_snapshot_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def render_operator_dashboard_snapshot_markdown(payload: dict[str, Any]) -> str:
    _validate_json_value("operator_dashboard_snapshot_payload", payload)
    status = payload["workflow_status"]
    lines = [
        "# 17B Operator Dashboard Snapshot",
        "",
        f"Snapshot ID: {payload['snapshot_id']}",
        f"Snapshot Date: {payload['snapshot_date']}",
        f"Generated: {payload['generated_at_utc']}",
        "",
        "Status: RESEARCH_ONLY / MONITOR_ONLY / PAPER_ONLY / HUMAN_REVIEW_REQUIRED.",
        "BLOCKED_BY_SAFETY_GATE workflows remain separated from allowed review workflows.",
        "LIVE TRADING: DISABLED. No secrets, credential files, broker routing, broker calls, or order execution are used.",
        "",
        "## Summary",
        "",
        _summary_line("Latest report index entries", payload["summary"]["latest_report_index_entry_count"]),
        _summary_line("Present reports", payload["summary"]["present_report_count"]),
        _summary_line("Missing reports", payload["summary"]["missing_report_count"]),
        _summary_line(
            "Allowed human-review workflows",
            payload["summary"]["allowed_human_review_workflow_count"],
        ),
        _summary_line("Blocked workflows", payload["summary"]["blocked_workflow_count"]),
        _summary_line("Queue items", payload["summary"]["queue_item_count"]),
        _summary_line("Safety scanner findings", payload["summary"]["safety_scanner_finding_count"]),
        "",
    ]
    lines.extend(_section("Current System State", [payload["system_state"]]))
    lines.extend(_section("Latest Report Index Entries", payload["latest_report_index"]["latest_entries"]))
    lines.extend(
        _section(
            "Workflow Status",
            [
                status["daily_research"],
                status["weekly_review"],
                status["research_evidence_pack"],
                status["decision_journal"],
                status["operator_runbook"],
                status["queue"],
                status["safety_scanner"],
            ],
        )
    )
    lines.extend(_section("Allowed Human-Review Workflows", payload["allowed_human_review_workflows"]))
    lines.extend(_section("Blocked Workflows", payload["blocked_workflows"]))
    lines.extend(
        [
            "## Safety Boundary",
            "",
            "- RESEARCH_ONLY dashboard snapshot only.",
            "- MONITOR_ONLY and PAPER_ONLY states are summarized, not executed.",
            "- HUMAN_REVIEW_REQUIRED workflows are review workflows only.",
            "- BLOCKED_BY_SAFETY_GATE workflows remain blocked.",
            "- LIVE TRADING: DISABLED.",
            "",
        ]
    )
    return "\n".join(lines)


def _report_index_payload(snapshot_input: OperatorDashboardSnapshotInput) -> dict[str, Any]:
    supplied = _read_json_object(snapshot_input.report_index_path)
    if supplied is None:
        supplied = build_report_index_payload(
            build_default_report_index_input(
                index_date=datetime.strptime(snapshot_input.snapshot_date, "%Y-%m-%d").date(),
                now=datetime.fromisoformat(snapshot_input.generated_at_utc),
            )
        )
    _validate_json_value("report_index_payload", supplied)
    reports = supplied.get("reports", [])
    if not isinstance(reports, list):
        reports = []
    entries = [_report_index_entry(item) for item in reports if isinstance(item, dict)]
    missing = [item for item in entries if item.get("status") == "missing"]
    present = [item for item in entries if item.get("status") == "present"]
    return {
        "status": supplied.get("safety_boundary", {}).get("status", "LIVE TRADING: DISABLED"),
        "label": supplied.get("safety_boundary", {}).get("label", HUMAN_REVIEW_REQUIRED),
        "index_id": supplied.get("index_id", "report_index"),
        "generated_at_utc": supplied.get("generated_at_utc"),
        "summary": {
            "target_report_count": len(entries),
            "present_report_count": len(present),
            "missing_report_count": len(missing),
        },
        "latest_entries": sorted(entries, key=_sort_key),
        "missing_reports": [
            {
                "workflow_id": item["report_id"],
                "label": BLOCKED_BY_SAFETY_GATE,
                "status": "blocked",
                "summary": f"Report metadata is missing: {item['report_type']}.",
                "source": "report_index",
            }
            for item in missing
        ],
    }


def _report_index_entry(item: dict[str, Any]) -> dict[str, Any]:
    value = {
        "report_id": str(item.get("report_id", "report")),
        "report_type": str(item.get("report_type", "Report")),
        "workflow": item.get("workflow") or item.get("report_type") or "Report",
        "phase": item.get("phase"),
        "label": item.get("label", HUMAN_REVIEW_REQUIRED),
        "status": item.get("status", "recorded"),
        "safety_status": item.get("safety_status", "LIVE TRADING: DISABLED"),
        "generated_date": item.get("generated_date"),
        "generated_at_utc": item.get("generated_at_utc"),
        "json_path": item.get("json_path"),
        "markdown_path": item.get("markdown_path"),
        "missing_paths": item.get("missing_paths", []),
    }
    _validate_json_value("report_index_entry", value)
    return value


def _workflow_status(workflow_id: str, path: Path) -> dict[str, Any]:
    payload = _read_json_object(path)
    if payload is None:
        return {
            "workflow_id": workflow_id,
            "label": BLOCKED_BY_SAFETY_GATE,
            "status": "missing",
            "summary": f"{workflow_id} report JSON was not found or could not be parsed.",
            "path": path.as_posix(),
        }
    _validate_json_value(workflow_id, payload)
    summary = payload.get("summary", {})
    return {
        "workflow_id": workflow_id,
        "phase": payload.get("phase"),
        "workflow": payload.get("workflow", workflow_id),
        "label": payload.get("safety_boundary", {}).get("label", payload.get("label", HUMAN_REVIEW_REQUIRED)),
        "status": payload.get("safety_boundary", {}).get("status", "LIVE TRADING: DISABLED"),
        "generated_at_utc": payload.get("generated_at_utc"),
        "generated_date": _generated_date(payload),
        "summary": _status_summary(payload.get("workflow", workflow_id), summary),
        "path": path.as_posix(),
    }


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
    next_item = items[0] if items else None
    return {
        "workflow_id": "master_plan_queue",
        "label": HUMAN_REVIEW_REQUIRED,
        "status": "read_only",
        "summary": "Master plan queue read for operator context only.",
        "path": path.as_posix(),
        "queue_item_count": len(items),
        "next_phase": next_item,
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


def _safety_scanner_status(path: Path, report_index: dict[str, Any]) -> dict[str, Any]:
    payload = _read_json_object(path)
    if payload is None:
        indexed = [
            item
            for item in report_index["latest_entries"]
            if item.get("report_id") == "safety_scanner_status"
        ]
        if indexed:
            item = indexed[0]
            return {
                "workflow_id": "safety_scanner",
                "label": item.get("label", HUMAN_REVIEW_REQUIRED),
                "status": item.get("safety_status", "LIVE TRADING: DISABLED"),
                "summary": "Safety scanner status summarized from report index metadata.",
                "path": item.get("json_path", path.as_posix()),
                "finding_count": 0,
                "passed": None,
            }
        return {
            "workflow_id": "safety_scanner",
            "label": HUMAN_REVIEW_REQUIRED,
            "status": "not_run",
            "summary": "Safety scanner status was not supplied to the dashboard snapshot.",
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
        "summary": payload.get("summary", "Safety scanner status supplied to dashboard snapshot."),
        "path": path.as_posix(),
        "finding_count": finding_count,
        "passed": passed,
    }


def _allowed_human_review_workflows(
    operator_runbook: dict[str, Any],
    decision_journal: dict[str, Any],
) -> list[dict[str, Any]]:
    items = [
        {
            "workflow_id": "review_dashboard_snapshot",
            "label": HUMAN_REVIEW_REQUIRED,
            "status": "allowed_review_only",
            "summary": "Human operator may review this read-only dashboard snapshot.",
        },
        {
            "workflow_id": "review_report_index_entries",
            "label": HUMAN_REVIEW_REQUIRED,
            "status": "allowed_review_only",
            "summary": "Human operator may review report index metadata without changing execution state.",
        },
        {
            "workflow_id": "review_queue_status",
            "label": HUMAN_REVIEW_REQUIRED,
            "status": "allowed_review_only",
            "summary": "Human operator may review queued roadmap phases for planning only.",
        },
        *_extract_workflows(operator_runbook, "allowed_human_review_workflows", HUMAN_REVIEW_REQUIRED),
        *_extract_workflows(decision_journal, "allowed_review_workflows", HUMAN_REVIEW_REQUIRED),
    ]
    return _dedupe_workflows(items)


def _blocked_workflows(
    operator_runbook: dict[str, Any],
    decision_journal: dict[str, Any],
    report_index: dict[str, Any],
) -> list[dict[str, Any]]:
    return _dedupe_workflows(
        (
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
                "summary": "Broker routing is outside the 17B dashboard snapshot.",
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
            *_extract_workflows(operator_runbook, "blocked_workflows", BLOCKED_BY_SAFETY_GATE),
            *_extract_workflows(decision_journal, "blocked_workflows", BLOCKED_BY_SAFETY_GATE),
            *report_index["missing_reports"],
        )
    )


def _extract_workflows(
    status: dict[str, Any],
    key: str,
    default_label: str,
) -> list[dict[str, Any]]:
    payload = _read_json_object(Path(status.get("path", "")))
    if payload is None:
        return []
    workflows = payload.get(key, [])
    if not isinstance(workflows, list):
        return []
    extracted = []
    for item in workflows:
        if not isinstance(item, dict):
            continue
        value = {
            "workflow_id": item.get("workflow_id", "workflow"),
            "label": item.get("label", default_label),
            "status": item.get("status", "recorded"),
            "summary": item.get("summary", "Workflow recorded."),
            "source": status.get("workflow_id"),
        }
        _validate_json_value("extracted_workflow", value)
        extracted.append(value)
    return extracted


def _blocked_from_statuses(*items: dict[str, Any]) -> list[dict[str, Any]]:
    blocked = []
    for item in items:
        if item.get("label") == BLOCKED_BY_SAFETY_GATE or item.get("status") in {
            "missing",
            "invalid",
            "blocked",
        }:
            workflow_id = str(item.get("workflow_id", "workflow"))
            blocked.append(
                {
                    "workflow_id": workflow_id,
                    "label": BLOCKED_BY_SAFETY_GATE,
                    "status": "blocked",
                    "summary": item.get("summary", f"{workflow_id} is blocked or incomplete."),
                    "source": "dashboard_status",
                }
            )
    return blocked


def _dedupe_workflows(items: tuple[dict[str, Any], ...] | list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for item in items:
        workflow_id = str(item.get("workflow_id", "workflow"))
        value = dict(item)
        value.setdefault("workflow_id", workflow_id)
        value.setdefault("label", HUMAN_REVIEW_REQUIRED)
        value.setdefault("status", "recorded")
        value.setdefault("summary", "Workflow recorded.")
        _validate_json_value("workflow", value)
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
    _validate_read_path(path)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def _generated_date(payload: dict[str, Any]) -> str | None:
    for key in (
        "report_date",
        "week_end",
        "runbook_date",
        "evidence_date",
        "journal_date",
        "index_date",
        "snapshot_date",
    ):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    generated_at = payload.get("generated_at_utc")
    if isinstance(generated_at, str) and len(generated_at) >= 10:
        return generated_at[:10]
    return None


def _status_summary(workflow: str, summary: Any) -> str:
    if not isinstance(summary, dict):
        return f"{workflow} metadata recorded."
    counts = [
        f"{key}={summary[key]}"
        for key in sorted(summary)
        if key.endswith("_count") and isinstance(summary[key], int)
    ]
    return f"{workflow} status: {', '.join(counts[:4]) if counts else 'metadata recorded'}."


def _section(title: str, items: list[dict[str, Any]]) -> list[str]:
    lines = [f"## {title}", ""]
    if not items:
        return [*lines, "- None recorded.", ""]
    for item in items:
        item_id = (
            item.get("workflow_id")
            or item.get("report_id")
            or item.get("phase")
            or item.get("status")
            or "item"
        )
        label = item.get("label", "n/a")
        status = item.get("status") or item.get("safety_status") or "recorded"
        summary = item.get("summary") or item.get("report_type") or item.get("status_text") or "Recorded."
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
            item.get("workflow_id")
            or item.get("report_id")
            or item.get("phase")
            or item.get("queue_id")
            or item.get("status")
            or json.dumps(item, sort_keys=True)
        ),
    )


def _validate_read_path(path: Path) -> None:
    if path.name in SECRET_FILE_NAMES:
        raise ValueError("operator dashboard snapshot cannot target secret files")
    lowered_parts = [part.lower() for part in path.parts]
    if any(marker in part for part in lowered_parts for marker in SECRET_PATH_MARKERS):
        raise ValueError("operator dashboard snapshot cannot target credential or secret paths")
    if path.is_absolute():
        raise ValueError("operator dashboard snapshot paths must be repo-relative")
    if ".." in path.parts:
        raise ValueError("operator dashboard snapshot paths cannot traverse parent directories")


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
        if label is not None and label not in SAFE_OPERATOR_DASHBOARD_LABELS:
            raise ValueError(f"unsafe operator dashboard label: {label}")
        if label in DISALLOWED_OPERATOR_DASHBOARD_LABELS:
            raise ValueError(f"disallowed operator dashboard label: {label}")
        for unsafe_field in UNSAFE_TRUE_FIELDS:
            if value.get(unsafe_field) is True:
                raise ValueError(f"operator dashboard snapshot cannot set {unsafe_field}")
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
        if value in DISALLOWED_OPERATOR_DASHBOARD_LABELS:
            raise ValueError(f"disallowed operator dashboard text: {value}")
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
