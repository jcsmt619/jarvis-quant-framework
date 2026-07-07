from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


DEFAULT_WEEKLY_REVIEW_DIR = Path("reports/weekly_review")
WEEKLY_REVIEW_JSON = "weekly_review.json"
WEEKLY_REVIEW_MARKDOWN = "weekly_review.md"

SAFE_WEEKLY_REVIEW_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
DISALLOWED_WEEKLY_REVIEW_LABELS = tuple(
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
    "real_paper_order_submitted",
    "secrets_required",
)
SORT_KEYS = (
    "experiment_id",
    "decision_id",
    "strategy_id",
    "challenger_strategy_id",
    "finding_id",
    "action_id",
    "id",
    "summary",
)


@dataclass(frozen=True)
class WeeklyReviewInput:
    review_id: str
    week_start: str
    week_end: str
    generated_at_utc: str
    wealth_research_results: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    moonshot_research_results: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    experiments: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    promotion_gates: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    champion_challenger_outcomes: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    safety_scanner_findings: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    blocked_decisions: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    next_review_actions: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    def validate(self) -> None:
        for field_name in ("review_id", "week_start", "week_end", "generated_at_utc"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"weekly review requires {field_name}")

        _parse_iso_datetime("generated_at_utc", self.generated_at_utc)
        _parse_iso_date("week_start", self.week_start)
        _parse_iso_date("week_end", self.week_end)
        if self.week_start > self.week_end:
            raise ValueError("week_start cannot be after week_end")

        for field_name in (
            "wealth_research_results",
            "moonshot_research_results",
            "experiments",
            "promotion_gates",
            "champion_challenger_outcomes",
            "safety_scanner_findings",
            "blocked_decisions",
            "next_review_actions",
        ):
            values = getattr(self, field_name)
            if not isinstance(values, tuple):
                raise ValueError(f"{field_name} must be a tuple")
            for item in values:
                _validate_review_item(field_name, item)


def build_weekly_review_payload(review_input: WeeklyReviewInput) -> dict[str, Any]:
    review_input.validate()

    wealth_results = _normalize_items(
        review_input.wealth_research_results,
        default_engine="wealth",
        default_label=RESEARCH_ONLY,
    )
    moonshot_results = _normalize_items(
        review_input.moonshot_research_results,
        default_engine="moonshot",
        default_label=MONITOR_ONLY,
    )
    experiments = _normalize_items(review_input.experiments, default_label=RESEARCH_ONLY)
    promotion_gates = _normalize_items(
        review_input.promotion_gates,
        default_label=HUMAN_REVIEW_REQUIRED,
    )
    champion_challenger_outcomes = _normalize_items(
        review_input.champion_challenger_outcomes,
        default_label=HUMAN_REVIEW_REQUIRED,
    )
    safety_findings = _normalize_items(
        review_input.safety_scanner_findings,
        default_label=BLOCKED_BY_SAFETY_GATE,
    )
    blocked_decisions = _normalize_items(
        (
            *review_input.blocked_decisions,
            *_blocked_promotion_gates(promotion_gates),
            *_blocked_champion_challenger_outcomes(champion_challenger_outcomes),
        ),
        default_label=BLOCKED_BY_SAFETY_GATE,
    )
    next_actions = _normalize_items(
        review_input.next_review_actions,
        default_label=HUMAN_REVIEW_REQUIRED,
    )

    all_research_results = (*wealth_results, *moonshot_results)

    payload = {
        "phase": "14B",
        "workflow": "Weekly Review",
        "review_id": review_input.review_id,
        "week_start": review_input.week_start,
        "week_end": review_input.week_end,
        "generated_at_utc": review_input.generated_at_utc,
        "safety_boundary": {
            "label": HUMAN_REVIEW_REQUIRED,
            "research_only": True,
            "paper_only": True,
            "monitor_only": True,
            "human_review_required": True,
            "live_trading_enabled": False,
            "broker_order_routing_enabled": False,
            "broker_order_call_performed": False,
            "real_paper_order_submitted": False,
            "secrets_required": False,
            "prohibited_trade_labels_present": False,
            "status": "LIVE TRADING: DISABLED",
        },
        "summary": {
            "wealth_research_result_count": len(wealth_results),
            "moonshot_research_result_count": len(moonshot_results),
            "experiment_count": len(experiments),
            "promotion_gate_count": len(promotion_gates),
            "champion_challenger_count": len(champion_challenger_outcomes),
            "safety_scanner_finding_count": len(safety_findings),
            "blocked_decision_count": len(blocked_decisions),
            "next_review_action_count": len(next_actions),
            "label_counts": _count_by(all_research_results, "label"),
            "experiment_counts_by_engine": _count_by(experiments, "engine"),
            "promotion_gate_counts_by_status": _count_by(promotion_gates, "promotion_status"),
            "champion_challenger_counts_by_status": _count_by(
                champion_challenger_outcomes,
                "challenger_status",
            ),
        },
        "wealth_research_results": wealth_results,
        "moonshot_research_results": moonshot_results,
        "experiments": experiments,
        "promotion_gates": promotion_gates,
        "champion_challenger_outcomes": champion_challenger_outcomes,
        "safety_scanner_findings": safety_findings,
        "blocked_decisions": blocked_decisions,
        "next_review_actions": next_actions,
    }
    _validate_review_item("weekly_review_payload", payload)
    return payload


def write_weekly_review(
    review_input: WeeklyReviewInput,
    *,
    out_dir: Path = DEFAULT_WEEKLY_REVIEW_DIR,
) -> tuple[Path, Path]:
    payload = build_weekly_review_payload(review_input)
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / WEEKLY_REVIEW_JSON
    markdown_path = out_dir / WEEKLY_REVIEW_MARKDOWN
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_weekly_review_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def render_weekly_review_markdown(payload: dict[str, Any]) -> str:
    _validate_review_item("weekly_review_payload", payload)
    lines = [
        "# 14B Weekly Review",
        "",
        f"Review ID: {payload['review_id']}",
        f"Window: {payload['week_start']} to {payload['week_end']}",
        f"Generated: {payload['generated_at_utc']}",
        "",
        "Status: HUMAN_REVIEW_REQUIRED. RESEARCH_ONLY / PAPER_ONLY / MONITOR_ONLY workflow.",
        "LIVE TRADING: DISABLED. No broker routing or order submission is enabled.",
        "",
        "## Summary",
        "",
        _summary_line("Wealth research results", payload["summary"]["wealth_research_result_count"]),
        _summary_line("Moonshot research results", payload["summary"]["moonshot_research_result_count"]),
        _summary_line("Experiments", payload["summary"]["experiment_count"]),
        _summary_line("Promotion gates", payload["summary"]["promotion_gate_count"]),
        _summary_line(
            "Champion/challenger outcomes",
            payload["summary"]["champion_challenger_count"],
        ),
        _summary_line("Safety scanner findings", payload["summary"]["safety_scanner_finding_count"]),
        _summary_line("Blocked decisions", payload["summary"]["blocked_decision_count"]),
        _summary_line("Next review actions", payload["summary"]["next_review_action_count"]),
        "",
    ]
    lines.extend(_section("Wealth Research Results", payload["wealth_research_results"]))
    lines.extend(_section("Moonshot Research Results", payload["moonshot_research_results"]))
    lines.extend(_section("Experiments", payload["experiments"]))
    lines.extend(_section("Promotion Gates", payload["promotion_gates"]))
    lines.extend(_section("Champion/Challenger Outcomes", payload["champion_challenger_outcomes"]))
    lines.extend(_section("Safety Scanner Findings", payload["safety_scanner_findings"]))
    lines.extend(_section("Blocked Decisions", payload["blocked_decisions"]))
    lines.extend(_section("Next Review Actions", payload["next_review_actions"]))
    lines.extend(
        [
            "## Safety Boundary",
            "",
            "- RESEARCH_ONLY outputs only.",
            "- PAPER_ONLY and MONITOR_ONLY states may be summarized, not executed.",
            "- HUMAN_REVIEW_REQUIRED before any trade-relevant decision.",
            "- BLOCKED_BY_SAFETY_GATE decisions remain blocked.",
            "- Live trading, broker routing, broker order calls, secrets, and real paper order submission are disabled.",
            "",
        ]
    )
    return "\n".join(lines)


def _section(title: str, items: list[dict[str, Any]]) -> list[str]:
    lines = [f"## {title}", ""]
    if not items:
        return [*lines, "- None recorded.", ""]
    for item in items:
        item_id = _first_present(item, SORT_KEYS) or "item"
        label = item.get("label", "n/a")
        status = (
            item.get("promotion_status")
            or item.get("challenger_status")
            or item.get("status")
            or "recorded"
        )
        summary = item.get("summary") or item.get("description") or item.get("reason") or "No summary."
        lines.append(f"- {item_id} | {label} | {status} | {summary}")
    lines.append("")
    return lines


def _summary_line(label: str, count: int) -> str:
    return f"- {label}: {count}"


def _normalize_items(
    items: tuple[dict[str, Any], ...],
    *,
    default_label: str,
    default_engine: str | None = None,
) -> list[dict[str, Any]]:
    normalized = []
    for item in items:
        value = dict(item)
        value.setdefault("label", default_label)
        if default_engine is not None:
            value.setdefault("engine", default_engine)
        _validate_review_item("weekly_review_item", value)
        normalized.append(_normalize_json_value(value))
    return sorted(normalized, key=_sort_key)


def _blocked_promotion_gates(items: list[dict[str, Any]]) -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "decision_id": item.get("decision_id")
            or item.get("strategy_id")
            or f"promotion_gate_{index}",
            "engine": item.get("engine", "unknown"),
            "label": BLOCKED_BY_SAFETY_GATE,
            "status": item.get("promotion_status", "blocked"),
            "summary": item.get("summary", "Promotion gate remains blocked."),
            "source": "promotion_gate",
        }
        for index, item in enumerate(items, start=1)
        if item.get("label") == BLOCKED_BY_SAFETY_GATE
        or item.get("promotion_status") == "blocked_by_safety_gate"
    )


def _blocked_champion_challenger_outcomes(items: list[dict[str, Any]]) -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "decision_id": item.get("decision_id")
            or item.get("challenger_strategy_id")
            or f"champion_challenger_{index}",
            "engine": item.get("engine", "unknown"),
            "label": BLOCKED_BY_SAFETY_GATE,
            "status": item.get("challenger_status", "blocked"),
            "summary": item.get("summary", "Champion/challenger outcome remains blocked."),
            "source": "champion_challenger",
        }
        for index, item in enumerate(items, start=1)
        if item.get("label") == BLOCKED_BY_SAFETY_GATE
        or item.get("challenger_status") == "challenger_blocked"
    )


def _count_by(items: tuple[dict[str, Any], ...] | list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(key, "unknown"))
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _sort_key(item: dict[str, Any]) -> tuple[str, str]:
    value = _first_present(item, SORT_KEYS)
    return (str(item.get("engine", "")), str(value or json.dumps(item, sort_keys=True)))


def _first_present(item: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return value
    return None


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


def _validate_review_item(field_name: str, value: Any) -> None:
    if isinstance(value, dict):
        label = value.get("label")
        if label is not None:
            if label not in SAFE_WEEKLY_REVIEW_LABELS:
                raise ValueError(f"unsafe weekly review label: {label}")
            if label in DISALLOWED_WEEKLY_REVIEW_LABELS:
                raise ValueError(f"disallowed weekly review label: {label}")
        for unsafe_field in UNSAFE_TRUE_FIELDS:
            if value.get(unsafe_field) is True:
                raise ValueError(f"weekly review cannot set {unsafe_field}")
        for key, item in value.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError(f"{field_name} keys must be non-empty strings")
            _validate_review_item(f"{field_name}.{key}", item)
        return
    if isinstance(value, (tuple, list)):
        for item in value:
            _validate_review_item(field_name, item)
        return
    if isinstance(value, str):
        if value in DISALLOWED_WEEKLY_REVIEW_LABELS:
            raise ValueError(f"disallowed weekly review text: {value}")
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
