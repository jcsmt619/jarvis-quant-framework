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


DEFAULT_REPORT_INDEX_DIR = Path("reports/report_index")
REPORT_INDEX_JSON = "report_index.json"
REPORT_INDEX_MARKDOWN = "report_index.md"

SAFE_REPORT_INDEX_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
DISALLOWED_REPORT_INDEX_LABELS = tuple(
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
class ReportIndexTarget:
    report_id: str
    report_type: str
    json_path: Path
    markdown_path: Path
    label: str = HUMAN_REVIEW_REQUIRED

    def validate(self) -> None:
        for field_name in ("report_id", "report_type"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"report index target requires {field_name}")
        if self.label not in SAFE_REPORT_INDEX_LABELS:
            raise ValueError(f"unsafe report index label: {self.label}")
        for path in (self.json_path, self.markdown_path):
            _validate_report_path(path)


@dataclass(frozen=True)
class ReportIndexInput:
    index_id: str
    index_date: str
    generated_at_utc: str
    targets: tuple[ReportIndexTarget, ...] = field(default_factory=tuple)

    def validate(self) -> None:
        for field_name in ("index_id", "index_date", "generated_at_utc"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"report index requires {field_name}")
        _parse_iso_date("index_date", self.index_date)
        _parse_iso_datetime("generated_at_utc", self.generated_at_utc)
        if not isinstance(self.targets, tuple):
            raise ValueError("targets must be a tuple")
        for target in self.targets:
            target.validate()


def build_default_report_index_input(
    *,
    index_date: date | None = None,
    now: datetime | None = None,
) -> ReportIndexInput:
    generated = now or datetime.now(tz=UTC)
    day = index_date or generated.date()
    return ReportIndexInput(
        index_id=f"17A-REPORT-INDEX-{day.isoformat()}",
        index_date=day.isoformat(),
        generated_at_utc=generated.isoformat(),
        targets=default_report_index_targets(),
    )


def default_report_index_targets() -> tuple[ReportIndexTarget, ...]:
    return (
        ReportIndexTarget(
            report_id="daily_research_command_center",
            report_type="Daily Research Command Center",
            json_path=Path("reports/daily_research_command_center/daily_research_summary.json"),
            markdown_path=Path("reports/daily_research_command_center/daily_research_summary.md"),
        ),
        ReportIndexTarget(
            report_id="weekly_review",
            report_type="Weekly Review",
            json_path=Path("reports/weekly_review/weekly_review.json"),
            markdown_path=Path("reports/weekly_review/weekly_review.md"),
        ),
        ReportIndexTarget(
            report_id="operator_runbook",
            report_type="Operator Runbook",
            json_path=Path("reports/operator_runbook/operator_runbook.json"),
            markdown_path=Path("reports/operator_runbook/operator_runbook.md"),
        ),
        ReportIndexTarget(
            report_id="research_evidence_pack",
            report_type="Research Evidence Pack",
            json_path=Path("reports/research_evidence_pack/research_evidence_pack.json"),
            markdown_path=Path("reports/research_evidence_pack/research_evidence_pack.md"),
        ),
        ReportIndexTarget(
            report_id="decision_journal",
            report_type="Decision Journal",
            json_path=Path("reports/decision_journal/decision_journal.json"),
            markdown_path=Path("reports/decision_journal/decision_journal.md"),
        ),
        ReportIndexTarget(
            report_id="promotion_gate_outputs",
            report_type="Promotion Gate Outputs",
            json_path=Path("reports/promotion_gate/promotion_gate.json"),
            markdown_path=Path("reports/promotion_gate/promotion_gate.md"),
        ),
        ReportIndexTarget(
            report_id="champion_challenger_outcomes",
            report_type="Champion Challenger Outcomes",
            json_path=Path("reports/champion_challenger/champion_challenger.json"),
            markdown_path=Path("reports/champion_challenger/champion_challenger.md"),
        ),
        ReportIndexTarget(
            report_id="safety_scanner_status",
            report_type="Safety Scanner Status",
            json_path=Path("reports/safety_scanner/safety_scanner_status.json"),
            markdown_path=Path("reports/safety_scanner/safety_scanner_status.md"),
        ),
    )


def build_report_index_payload(index_input: ReportIndexInput) -> dict[str, Any]:
    index_input.validate()

    reports = [_report_entry(target) for target in index_input.targets]
    missing_reports = [item for item in reports if item["status"] == "missing"]
    present_reports = [item for item in reports if item["status"] == "present"]
    blocked_reports = [item for item in reports if item["label"] == BLOCKED_BY_SAFETY_GATE]

    payload = {
        "phase": "17A",
        "workflow": "Report Index",
        "index_id": index_input.index_id,
        "index_date": index_input.index_date,
        "generated_at_utc": index_input.generated_at_utc,
        "safety_boundary": _safety_boundary(),
        "summary": {
            "target_report_count": len(reports),
            "present_report_count": len(present_reports),
            "missing_report_count": len(missing_reports),
            "blocked_report_count": len(blocked_reports),
            "label_counts": _count_by(reports, "label"),
            "safety_status_counts": _count_by(reports, "safety_status"),
        },
        "reports": reports,
        "missing_reports": [
            {
                "report_id": item["report_id"],
                "report_type": item["report_type"],
                "missing_paths": item["missing_paths"],
                "label": item["label"],
                "safety_status": item["safety_status"],
            }
            for item in missing_reports
        ],
    }
    _validate_json_value("report_index_payload", payload)
    return _normalize_json_value(payload)


def write_report_index(
    index_input: ReportIndexInput,
    *,
    out_dir: Path = DEFAULT_REPORT_INDEX_DIR,
) -> tuple[Path, Path]:
    payload = build_report_index_payload(index_input)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / REPORT_INDEX_JSON
    markdown_path = out_dir / REPORT_INDEX_MARKDOWN
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_report_index_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def render_report_index_markdown(payload: dict[str, Any]) -> str:
    _validate_json_value("report_index_payload", payload)
    lines = [
        "# 17A Report Index",
        "",
        f"Index ID: {payload['index_id']}",
        f"Index Date: {payload['index_date']}",
        f"Generated: {payload['generated_at_utc']}",
        "",
        "Status: RESEARCH_ONLY / MONITOR_ONLY / PAPER_ONLY / HUMAN_REVIEW_REQUIRED.",
        "BLOCKED_BY_SAFETY_GATE missing or unsafe report metadata remains blocked.",
        "LIVE TRADING: DISABLED. No secrets, credential files, broker routing, broker calls, or order execution are used.",
        "",
        "## Summary",
        "",
        _summary_line("Target reports", payload["summary"]["target_report_count"]),
        _summary_line("Present reports", payload["summary"]["present_report_count"]),
        _summary_line("Missing reports", payload["summary"]["missing_report_count"]),
        _summary_line("Blocked reports", payload["summary"]["blocked_report_count"]),
        "",
    ]
    lines.extend(_section("Reports", payload["reports"]))
    lines.extend(_section("Missing Reports", payload["missing_reports"]))
    lines.extend(
        [
            "## Safety Boundary",
            "",
            "- RESEARCH_ONLY report indexing only.",
            "- MONITOR_ONLY and PAPER_ONLY report states are summarized, not executed.",
            "- HUMAN_REVIEW_REQUIRED remains attached to trade-relevant report interpretation.",
            "- BLOCKED_BY_SAFETY_GATE report gaps remain blocked.",
            "- LIVE TRADING: DISABLED.",
            "",
        ]
    )
    return "\n".join(lines)


def _report_entry(target: ReportIndexTarget) -> dict[str, Any]:
    target.validate()
    json_exists = target.json_path.is_file()
    markdown_exists = target.markdown_path.is_file()
    missing_paths = [
        str(path.as_posix())
        for path, exists in (
            (target.json_path, json_exists),
            (target.markdown_path, markdown_exists),
        )
        if not exists
    ]
    metadata = _read_json_metadata(target.json_path) if json_exists else {}
    label = _metadata_label(metadata, target.label, missing_paths)
    safety_status = _metadata_safety_status(metadata, missing_paths)
    generated_date = _metadata_generated_date(metadata)
    status = "present" if json_exists and markdown_exists else "missing"
    entry = {
        "report_id": target.report_id,
        "report_type": target.report_type,
        "json_path": target.json_path.as_posix(),
        "markdown_path": target.markdown_path.as_posix(),
        "status": status,
        "label": label,
        "safety_status": safety_status,
        "generated_date": generated_date,
        "generated_at_utc": metadata.get("generated_at_utc"),
        "workflow": metadata.get("workflow", target.report_type),
        "phase": metadata.get("phase"),
        "missing_paths": missing_paths,
    }
    _validate_json_value("report_index_entry", entry)
    return entry


def _read_json_metadata(path: Path) -> dict[str, Any]:
    _validate_report_path(path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {
            "label": BLOCKED_BY_SAFETY_GATE,
            "safety_status": "invalid_json",
            "summary": "Report JSON could not be parsed for index metadata.",
        }
    if not isinstance(value, dict):
        return {
            "label": BLOCKED_BY_SAFETY_GATE,
            "safety_status": "invalid_json",
            "summary": "Report JSON root is not an object.",
        }
    _validate_json_value("indexed_report_payload", value)
    return value


def _metadata_label(
    metadata: dict[str, Any],
    default_label: str,
    missing_paths: list[str],
) -> str:
    if missing_paths:
        return BLOCKED_BY_SAFETY_GATE
    label = metadata.get("label") or metadata.get("safety_boundary", {}).get("label") or default_label
    if label not in SAFE_REPORT_INDEX_LABELS:
        raise ValueError(f"unsafe report index label: {label}")
    return label


def _metadata_safety_status(metadata: dict[str, Any], missing_paths: list[str]) -> str:
    if missing_paths:
        return "missing_report"
    if metadata.get("safety_status"):
        return str(metadata["safety_status"])
    boundary_status = metadata.get("safety_boundary", {}).get("status")
    if boundary_status:
        return str(boundary_status)
    return "LIVE TRADING: DISABLED"


def _metadata_generated_date(metadata: dict[str, Any]) -> str | None:
    for key in (
        "report_date",
        "week_end",
        "runbook_date",
        "evidence_date",
        "journal_date",
        "index_date",
    ):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value
    generated_at = metadata.get("generated_at_utc")
    if isinstance(generated_at, str) and len(generated_at) >= 10:
        return generated_at[:10]
    return None


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


def _section(title: str, items: list[dict[str, Any]]) -> list[str]:
    lines = [f"## {title}", ""]
    if not items:
        return [*lines, "- None recorded.", ""]
    for item in items:
        item_id = item.get("report_id") or "report"
        label = item.get("label", "n/a")
        status = item.get("safety_status") or item.get("status") or "recorded"
        summary = item.get("report_type", "Report")
        if item.get("missing_paths"):
            summary = f"{summary}; missing: {', '.join(item['missing_paths'])}"
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


def _validate_report_path(path: Path) -> None:
    if path.name in SECRET_FILE_NAMES:
        raise ValueError("report index cannot target secret files")
    lowered_parts = [part.lower() for part in path.parts]
    if any(marker in part for part in lowered_parts for marker in SECRET_PATH_MARKERS):
        raise ValueError("report index cannot target credential or secret paths")
    if path.is_absolute():
        raise ValueError("report index paths must be repo-relative")
    if ".." in path.parts:
        raise ValueError("report index paths cannot traverse parent directories")


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
        if label is not None and label not in SAFE_REPORT_INDEX_LABELS:
            raise ValueError(f"unsafe report index label: {label}")
        if label in DISALLOWED_REPORT_INDEX_LABELS:
            raise ValueError(f"disallowed report index label: {label}")
        for unsafe_field in UNSAFE_TRUE_FIELDS:
            if value.get(unsafe_field) is True:
                raise ValueError(f"report index cannot set {unsafe_field}")
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
        if value in DISALLOWED_REPORT_INDEX_LABELS:
            raise ValueError(f"disallowed report index text: {value}")
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
