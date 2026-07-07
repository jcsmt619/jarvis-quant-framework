from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from automation.safety_scanner import SafetyScanResult
from core.daily_research_command_center import (
    build_daily_research_payload,
    build_default_daily_research_input,
)
from core.operator_runbook import (
    OperatorRunbookInput,
    build_operator_runbook_payload,
)
from engines.strategy_cards import STRATEGY_CARDS, StrategyCard, validate_strategy_cards
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


DEFAULT_RESEARCH_EVIDENCE_PACK_DIR = Path("reports/research_evidence_pack")
RESEARCH_EVIDENCE_PACK_JSON = "research_evidence_pack.json"
RESEARCH_EVIDENCE_PACK_MARKDOWN = "research_evidence_pack.md"

SAFE_RESEARCH_EVIDENCE_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
DISALLOWED_RESEARCH_EVIDENCE_LABELS = tuple(
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
class ResearchEvidencePackInput:
    pack_id: str
    evidence_date: str
    generated_at_utc: str
    strategy_cards: tuple[StrategyCard, ...] = STRATEGY_CARDS
    experiments: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    promotion_gates: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    champion_challenger_outcomes: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    weekly_review_payload: dict[str, Any] | None = None
    daily_research_payload: dict[str, Any] | None = None
    operator_runbook_payload: dict[str, Any] | None = None
    safety_scan_result: SafetyScanResult | None = None
    operator_notes: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    def validate(self) -> None:
        for field_name in ("pack_id", "evidence_date", "generated_at_utc"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"research evidence pack requires {field_name}")
        _parse_iso_date("evidence_date", self.evidence_date)
        _parse_iso_datetime("generated_at_utc", self.generated_at_utc)
        validate_strategy_cards(self.strategy_cards)
        for field_name in (
            "experiments",
            "promotion_gates",
            "champion_challenger_outcomes",
            "operator_notes",
        ):
            values = getattr(self, field_name)
            if not isinstance(values, tuple):
                raise ValueError(f"{field_name} must be a tuple")
            for item in values:
                _validate_json_value(field_name, item)
        for field_name in (
            "weekly_review_payload",
            "daily_research_payload",
            "operator_runbook_payload",
        ):
            value = getattr(self, field_name)
            if value is not None:
                _validate_json_value(field_name, value)


def build_default_research_evidence_pack_input(
    *,
    evidence_date: date | None = None,
    now: datetime | None = None,
) -> ResearchEvidencePackInput:
    generated = now or datetime.now(tz=UTC)
    day = evidence_date or generated.date()
    daily_input = build_default_daily_research_input(report_date=day, now=generated)
    daily_payload = build_daily_research_payload(daily_input)
    weekly_payload = daily_payload.get("weekly_review") or None
    operator_payload = build_operator_runbook_payload(
        OperatorRunbookInput(
            runbook_id=f"16A-OPERATOR-CONTEXT-{day.isoformat()}",
            runbook_date=day.isoformat(),
            generated_at_utc=generated.isoformat(),
            daily_research_payload=daily_payload,
            weekly_review_payload=weekly_payload,
            experiment_review_items=tuple(daily_payload["experiments"]),
            promotion_review_items=tuple(daily_payload["promotion_gates"]),
            safety_findings=tuple(daily_payload["safety_scanner"].get("findings", ())),
            operator_notes=(
                {
                    "note_id": "16A-EVIDENCE-PACK-NOTE",
                    "label": HUMAN_REVIEW_REQUIRED,
                    "summary": "Evidence pack is for human review only.",
                },
            ),
        )
    )
    return ResearchEvidencePackInput(
        pack_id=f"16A-RESEARCH-EVIDENCE-PACK-{day.isoformat()}",
        evidence_date=day.isoformat(),
        generated_at_utc=generated.isoformat(),
        strategy_cards=daily_input.strategy_cards,
        experiments=tuple(daily_payload["experiments"]),
        promotion_gates=tuple(daily_payload["promotion_gates"]),
        champion_challenger_outcomes=tuple(daily_payload["champion_challenger_outcomes"]),
        weekly_review_payload=weekly_payload,
        daily_research_payload=daily_payload,
        operator_runbook_payload=operator_payload,
        safety_scan_result=daily_input.safety_scan_result,
        operator_notes=(
            {
                "note_id": "16A-DEFAULT-HUMAN-REVIEW",
                "label": HUMAN_REVIEW_REQUIRED,
                "summary": "Review bundled evidence before any future phase decision.",
            },
        ),
    )


def build_research_evidence_pack_payload(
    pack_input: ResearchEvidencePackInput,
) -> dict[str, Any]:
    pack_input.validate()

    strategy_cards = [_normalize_json_value(_dataclass_payload(card)) for card in pack_input.strategy_cards]
    experiments = _normalize_items(pack_input.experiments, default_label=RESEARCH_ONLY)
    promotion_gates = _normalize_items(pack_input.promotion_gates, default_label=HUMAN_REVIEW_REQUIRED)
    champion_challenger = _normalize_items(
        pack_input.champion_challenger_outcomes,
        default_label=HUMAN_REVIEW_REQUIRED,
    )
    weekly_review = _normalize_json_value(pack_input.weekly_review_payload or {})
    daily_research = _normalize_json_value(pack_input.daily_research_payload or {})
    operator_runbook = _normalize_json_value(pack_input.operator_runbook_payload or {})
    safety_scanner = _safety_scan_payload(pack_input.safety_scan_result, daily_research)
    operator_notes = _normalize_items(pack_input.operator_notes, default_label=HUMAN_REVIEW_REQUIRED)

    payload = {
        "phase": "16A",
        "workflow": "Research Evidence Pack",
        "pack_id": pack_input.pack_id,
        "evidence_date": pack_input.evidence_date,
        "generated_at_utc": pack_input.generated_at_utc,
        "safety_boundary": _safety_boundary(),
        "summary": {
            "strategy_card_count": len(strategy_cards),
            "experiment_count": len(experiments),
            "promotion_gate_count": len(promotion_gates),
            "champion_challenger_count": len(champion_challenger),
            "weekly_review_included": bool(weekly_review),
            "daily_research_included": bool(daily_research),
            "operator_runbook_included": bool(operator_runbook),
            "safety_scanner_status": safety_scanner["status"],
            "safety_scanner_finding_count": safety_scanner["finding_count"],
            "operator_note_count": len(operator_notes),
            "label_counts": _count_by(
                [
                    *strategy_cards,
                    *experiments,
                    *promotion_gates,
                    *champion_challenger,
                    safety_scanner,
                    *operator_notes,
                ],
                "label",
            ),
        },
        "evidence": {
            "strategy_cards": strategy_cards,
            "experiment_registry_entries": experiments,
            "promotion_gate_results": promotion_gates,
            "champion_challenger_outcomes": champion_challenger,
            "weekly_review_output": weekly_review,
            "daily_research_command_center": daily_research,
            "operator_runbook_status": operator_runbook,
            "safety_scanner_status": safety_scanner,
            "operator_notes": operator_notes,
        },
    }
    _validate_json_value("research_evidence_pack_payload", payload)
    return _normalize_json_value(payload)


def write_research_evidence_pack(
    pack_input: ResearchEvidencePackInput,
    *,
    out_dir: Path = DEFAULT_RESEARCH_EVIDENCE_PACK_DIR,
) -> tuple[Path, Path]:
    payload = build_research_evidence_pack_payload(pack_input)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / RESEARCH_EVIDENCE_PACK_JSON
    markdown_path = out_dir / RESEARCH_EVIDENCE_PACK_MARKDOWN
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_research_evidence_pack_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def render_research_evidence_pack_markdown(payload: dict[str, Any]) -> str:
    _validate_json_value("research_evidence_pack_payload", payload)
    evidence = payload["evidence"]
    lines = [
        "# 16A Research Evidence Pack",
        "",
        f"Pack ID: {payload['pack_id']}",
        f"Evidence Date: {payload['evidence_date']}",
        f"Generated: {payload['generated_at_utc']}",
        "",
        "Status: RESEARCH_ONLY / MONITOR_ONLY / PAPER_ONLY / HUMAN_REVIEW_REQUIRED.",
        "BLOCKED_BY_SAFETY_GATE findings remain blocked.",
        "LIVE TRADING: DISABLED. No secrets, broker routing, broker calls, or order execution are used.",
        "",
        "## Summary",
        "",
        _summary_line("Strategy cards", payload["summary"]["strategy_card_count"]),
        _summary_line("Experiment registry entries", payload["summary"]["experiment_count"]),
        _summary_line("Promotion gate results", payload["summary"]["promotion_gate_count"]),
        _summary_line(
            "Champion/challenger outcomes",
            payload["summary"]["champion_challenger_count"],
        ),
        _summary_line("Safety scanner findings", payload["summary"]["safety_scanner_finding_count"]),
        _summary_line("Operator notes", payload["summary"]["operator_note_count"]),
        "",
    ]
    lines.extend(_section("Strategy Cards", evidence["strategy_cards"], "card_id"))
    lines.extend(_section("Experiment Registry Entries", evidence["experiment_registry_entries"], "experiment_id"))
    lines.extend(_section("Promotion Gate Results", evidence["promotion_gate_results"], "strategy_id"))
    lines.extend(
        _section(
            "Champion/Challenger Outcomes",
            evidence["champion_challenger_outcomes"],
            "challenger_strategy_id",
        )
    )
    lines.extend(_source_section("Weekly Review Output", evidence["weekly_review_output"], "review_id"))
    lines.extend(
        _source_section(
            "Daily Research Command Center",
            evidence["daily_research_command_center"],
            "report_date",
        )
    )
    lines.extend(_source_section("Operator Runbook Status", evidence["operator_runbook_status"], "runbook_id"))
    lines.extend(_section("Safety Scanner Status", [evidence["safety_scanner_status"]], "status"))
    lines.extend(_section("Operator Notes", evidence["operator_notes"], "note_id"))
    lines.extend(
        [
            "## Safety Boundary",
            "",
            "- RESEARCH_ONLY outputs only.",
            "- MONITOR_ONLY and PAPER_ONLY states are evidence states, not execution instructions.",
            "- HUMAN_REVIEW_REQUIRED remains attached to trade-relevant interpretation.",
            "- BLOCKED_BY_SAFETY_GATE decisions remain blocked.",
            "- LIVE TRADING: DISABLED.",
            "",
        ]
    )
    return "\n".join(lines)


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


def _safety_scan_payload(
    result: SafetyScanResult | None,
    daily_research_payload: dict[str, Any],
) -> dict[str, Any]:
    if result is not None:
        return {
            "status": "passed" if result.passed else "blocked",
            "label": HUMAN_REVIEW_REQUIRED if result.passed else BLOCKED_BY_SAFETY_GATE,
            "summary": "Safety scanner result supplied to evidence pack.",
            "passed": result.passed,
            "finding_count": len(result.findings),
            "scanned_files": result.scanned_files,
            "skipped_files": list(result.skipped_files),
            "findings": [_dataclass_payload(finding) for finding in result.findings],
        }

    supplied = daily_research_payload.get("safety_scanner") if daily_research_payload else None
    if isinstance(supplied, dict):
        value = dict(supplied)
        value.setdefault("label", HUMAN_REVIEW_REQUIRED)
        value.setdefault("finding_count", len(value.get("findings", ())))
        value.setdefault("summary", "Safety scanner status carried from daily research.")
        _validate_json_value("safety_scanner_status", value)
        return _normalize_json_value(value)

    return {
        "status": "not_run",
        "label": HUMAN_REVIEW_REQUIRED,
        "summary": "Safety scanner status was not supplied to the evidence pack.",
        "passed": None,
        "finding_count": 0,
        "scanned_files": 0,
        "skipped_files": [],
        "findings": [],
    }


def _section(title: str, items: list[dict[str, Any]], id_key: str) -> list[str]:
    lines = [f"## {title}", ""]
    if not items:
        return [*lines, "- None recorded.", ""]
    for item in items:
        item_id = (
            item.get(id_key)
            or item.get("strategy_id")
            or item.get("experiment_id")
            or item.get("note_id")
            or item.get("status")
            or "item"
        )
        label = item.get("label", "n/a")
        status = item.get("promotion_status") or item.get("challenger_status") or item.get("status")
        summary = item.get("summary") or item.get("hypothesis") or "Recorded."
        lines.append(f"- {item_id} | {label} | {status or 'recorded'} | {summary}")
    lines.append("")
    return lines


def _source_section(title: str, payload: dict[str, Any], id_key: str) -> list[str]:
    if not payload:
        return [f"## {title}", "", "- None recorded.", ""]
    summary = payload.get("summary", {})
    item = {
        id_key: payload.get(id_key) or payload.get("pack_id") or title,
        "label": payload.get("safety_boundary", {}).get("label", HUMAN_REVIEW_REQUIRED),
        "status": payload.get("safety_boundary", {}).get("status", "recorded"),
        "summary": (
            f"{payload.get('workflow', title)} included with "
            f"{summary.get('experiment_count', 0)} experiments and "
            f"{summary.get('blocked_decision_count', summary.get('safety_scanner_finding_count', 0))} blocked or safety items."
        ),
    }
    return _section(title, [item], id_key)


def _normalize_items(
    items: tuple[dict[str, Any], ...],
    *,
    default_label: str,
) -> list[dict[str, Any]]:
    normalized = []
    for item in items:
        value = dict(item)
        value.setdefault("label", default_label)
        _validate_json_value("research_evidence_item", value)
        normalized.append(_normalize_json_value(value))
    return sorted(normalized, key=_sort_key)


def _sort_key(item: dict[str, Any]) -> tuple[str, str]:
    return (
        str(item.get("engine", "")),
        str(
            item.get("card_id")
            or item.get("experiment_id")
            or item.get("strategy_id")
            or item.get("challenger_strategy_id")
            or item.get("note_id")
            or item.get("status")
            or json.dumps(item, sort_keys=True)
        ),
    )


def _summary_line(label: str, count: int) -> str:
    return f"- {label}: {count}"


def _dataclass_payload(value: Any) -> dict[str, Any]:
    if not is_dataclass(value):
        raise ValueError("expected dataclass payload")
    return asdict(value)


def _count_by(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(key, "unknown"))
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


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
        if label is not None and label not in SAFE_RESEARCH_EVIDENCE_LABELS:
            raise ValueError(f"unsafe research evidence label: {label}")
        if label in DISALLOWED_RESEARCH_EVIDENCE_LABELS:
            raise ValueError(f"disallowed research evidence label: {label}")
        for unsafe_field in UNSAFE_TRUE_FIELDS:
            if value.get(unsafe_field) is True:
                raise ValueError(f"research evidence pack cannot set {unsafe_field}")
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
        if value in DISALLOWED_RESEARCH_EVIDENCE_LABELS:
            raise ValueError(f"disallowed research evidence text: {value}")
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
