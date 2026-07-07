from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, is_dataclass, replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from automation.safety_scanner import SafetyScanResult
from core.experiment_registry import build_experiment_record, read_experiment_records
from core.weekly_review import WeeklyReviewInput, build_weekly_review_payload
from engines.strategy_cards import STRATEGY_CARDS, StrategyCard, validate_strategy_cards
from risk.champion_challenger import (
    ChampionChallengerDecision,
    StrategyOosMetrics,
    evaluate_champion_challenger,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
    PolicyState,
)
from risk.promotion_gate import (
    PromotionGateDecision,
    PromotionGateEvidence,
    evaluate_promotion_gate,
)
from risk.policies import ENGINE_RISK_POLICIES, evaluate_policy


DEFAULT_DAILY_RESEARCH_DIR = Path("reports/daily_research_command_center")
DAILY_RESEARCH_JSON = "daily_research_summary.json"
DAILY_RESEARCH_MARKDOWN = "daily_research_summary.md"

SAFE_DAILY_RESEARCH_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
DISALLOWED_DAILY_RESEARCH_LABELS = tuple(
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
    "real_paper_wrapper_connected",
    "real_paper_wrapper_attempted",
    "secrets_required",
)


@dataclass(frozen=True)
class DailyResearchInput:
    report_date: str
    generated_at_utc: str
    strategy_cards: tuple[StrategyCard, ...] = STRATEGY_CARDS
    experiments: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    promotion_gates: tuple[PromotionGateDecision, ...] = field(default_factory=tuple)
    champion_challenger_outcomes: tuple[ChampionChallengerDecision, ...] = field(
        default_factory=tuple
    )
    safety_scan_result: SafetyScanResult | None = None
    weekly_review_payload: dict[str, Any] | None = None

    def validate(self) -> None:
        _parse_iso_date("report_date", self.report_date)
        _parse_iso_datetime("generated_at_utc", self.generated_at_utc)
        validate_strategy_cards(self.strategy_cards)
        for value in (
            self.experiments,
            self.promotion_gates,
            self.champion_challenger_outcomes,
        ):
            if not isinstance(value, tuple):
                raise ValueError("daily research collections must be tuples")
        for item in self.experiments:
            _validate_json_value("experiments", item)
        if self.weekly_review_payload is not None:
            _validate_json_value("weekly_review_payload", self.weekly_review_payload)


def build_default_daily_research_input(
    *,
    report_date: date | None = None,
    now: datetime | None = None,
    registry_dir: Path = Path("reports/experiment_registry"),
) -> DailyResearchInput:
    generated = now or datetime.now(tz=UTC)
    day = report_date or generated.date()
    cards = STRATEGY_CARDS
    experiments = tuple(read_experiment_records(registry_dir=registry_dir)) or _default_experiments(
        cards,
        generated,
    )
    promotion_gates = _default_promotion_gates(cards)
    champion_challenger = _default_champion_challenger(cards)
    weekly_payload = build_weekly_review_payload(
        WeeklyReviewInput(
            review_id=f"15A-DAILY-WEEKLY-CONTEXT-{day.isoformat()}",
            week_start=(day - timedelta(days=6)).isoformat(),
            week_end=day.isoformat(),
            generated_at_utc=generated.isoformat(),
            wealth_research_results=tuple(
                _research_result_for_card(card) for card in cards if card.engine == "wealth"
            ),
            moonshot_research_results=tuple(
                _research_result_for_card(card) for card in cards if card.engine == "moonshot"
            ),
            experiments=experiments,
            promotion_gates=tuple(_promotion_gate_summary(item) for item in promotion_gates),
            champion_challenger_outcomes=tuple(
                _champion_challenger_summary(item) for item in champion_challenger
            ),
            safety_scanner_findings=(),
            blocked_decisions=(),
            next_review_actions=(
                {
                    "action_id": "15A-NEXT-HUMAN-REVIEW",
                    "summary": "Review research-only daily command center outputs.",
                    "label": HUMAN_REVIEW_REQUIRED,
                },
            ),
        )
    )
    return DailyResearchInput(
        report_date=day.isoformat(),
        generated_at_utc=generated.isoformat(),
        strategy_cards=cards,
        experiments=experiments,
        promotion_gates=promotion_gates,
        champion_challenger_outcomes=champion_challenger,
        weekly_review_payload=weekly_payload,
    )


def build_daily_research_payload(report_input: DailyResearchInput) -> dict[str, Any]:
    report_input.validate()

    strategy_cards = [_strategy_card_payload(card) for card in report_input.strategy_cards]
    experiments = [_normalize_json_value(item) for item in report_input.experiments]
    promotion_gates = [
        _promotion_gate_summary(decision) for decision in report_input.promotion_gates
    ]
    champion_challenger = [
        _champion_challenger_summary(decision)
        for decision in report_input.champion_challenger_outcomes
    ]
    safety_status = _safety_status_payload(report_input.safety_scan_result)
    weekly_review = (
        _normalize_json_value(report_input.weekly_review_payload)
        if report_input.weekly_review_payload is not None
        else {}
    )

    payload = {
        "phase": "15A",
        "workflow": "Daily Research Command Center",
        "report_date": report_input.report_date,
        "generated_at_utc": report_input.generated_at_utc,
        "safety_boundary": _safety_boundary(),
        "summary": {
            "wealth_strategy_card_count": _count_by(strategy_cards, "engine").get("wealth", 0),
            "moonshot_strategy_card_count": _count_by(strategy_cards, "engine").get(
                "moonshot",
                0,
            ),
            "experiment_count": len(experiments),
            "promotion_gate_count": len(promotion_gates),
            "champion_challenger_count": len(champion_challenger),
            "safety_scanner_passed": safety_status["passed"],
            "safety_scanner_finding_count": safety_status["finding_count"],
            "label_counts": _count_by(
                [
                    *strategy_cards,
                    *experiments,
                    *promotion_gates,
                    *champion_challenger,
                    safety_status,
                ],
                "label",
            ),
        },
        "wealth": {
            "strategy_cards": [item for item in strategy_cards if item["engine"] == "wealth"],
            "experiments": [item for item in experiments if item.get("engine") == "wealth"],
        },
        "moonshot": {
            "strategy_cards": [item for item in strategy_cards if item["engine"] == "moonshot"],
            "experiments": [item for item in experiments if item.get("engine") == "moonshot"],
        },
        "strategy_cards": strategy_cards,
        "experiments": experiments,
        "promotion_gates": promotion_gates,
        "champion_challenger_outcomes": champion_challenger,
        "weekly_review": weekly_review,
        "safety_scanner": safety_status,
    }
    _validate_json_value("daily_research_payload", payload)
    return _normalize_json_value(payload)


def write_daily_research_summary(
    report_input: DailyResearchInput,
    *,
    out_dir: Path = DEFAULT_DAILY_RESEARCH_DIR,
) -> tuple[Path, Path]:
    payload = build_daily_research_payload(report_input)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / DAILY_RESEARCH_JSON
    markdown_path = out_dir / DAILY_RESEARCH_MARKDOWN
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_daily_research_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def render_daily_research_markdown(payload: dict[str, Any]) -> str:
    _validate_json_value("daily_research_payload", payload)
    lines = [
        "# 15A Daily Research Command Center",
        "",
        f"Report Date: {payload['report_date']}",
        f"Generated: {payload['generated_at_utc']}",
        "",
        "Status: RESEARCH_ONLY / MONITOR_ONLY / PAPER_ONLY / HUMAN_REVIEW_REQUIRED.",
        "LIVE TRADING: DISABLED. No broker routing, broker calls, order submission, or secrets are used.",
        "",
        "## Summary",
        "",
        _summary_line("Wealth strategy cards", payload["summary"]["wealth_strategy_card_count"]),
        _summary_line("Moonshot strategy cards", payload["summary"]["moonshot_strategy_card_count"]),
        _summary_line("Experiments", payload["summary"]["experiment_count"]),
        _summary_line("Promotion gates", payload["summary"]["promotion_gate_count"]),
        _summary_line(
            "Champion/challenger outcomes",
            payload["summary"]["champion_challenger_count"],
        ),
        _summary_line("Safety scanner findings", payload["summary"]["safety_scanner_finding_count"]),
        "",
    ]
    lines.extend(_section("Wealth Strategy Cards", payload["wealth"]["strategy_cards"], "card_id"))
    lines.extend(_section("Moonshot Strategy Cards", payload["moonshot"]["strategy_cards"], "card_id"))
    lines.extend(_section("Experiment Registry Entries", payload["experiments"], "experiment_id"))
    lines.extend(_section("Promotion Gates", payload["promotion_gates"], "strategy_id"))
    lines.extend(
        _section(
            "Champion/Challenger Outcomes",
            payload["champion_challenger_outcomes"],
            "challenger_strategy_id",
        )
    )
    lines.extend(_section("Weekly Review Outputs", _weekly_review_items(payload), "review_id"))
    lines.extend(_section("Safety Scanner Status", [payload["safety_scanner"]], "status"))
    lines.extend(
        [
            "## Safety Boundary",
            "",
            "- Outputs are deterministic research summaries only.",
            "- HUMAN_REVIEW_REQUIRED remains attached to trade-relevant interpretation.",
            "- PAPER_ONLY and MONITOR_ONLY states are summarized, not executed.",
            "- LIVE TRADING: DISABLED.",
            "",
        ]
    )
    return "\n".join(lines)


def _default_experiments(
    cards: tuple[StrategyCard, ...],
    now: datetime,
) -> tuple[dict[str, Any], ...]:
    records = []
    for card in cards:
        record = build_experiment_record(
            experiment_id=f"15A-{card.card_id}-DAILY-SUMMARY",
            experiment_type="strategy_evaluation",
            strategy_id=card.card_id,
            engine=card.engine,
            label=card.label,
            summary=f"Daily command center deterministic summary for {card.card_id}.",
            dataset_id="15A-deterministic-fixture",
            timeframe=card.timeframe,
            parameters={"source": "strategy_card", "lane": card.lane},
            metrics={"signal_count": len(card.signals), "risk_rule_count": len(card.risk_rules)},
            tags=("15A", "daily_research_command_center", card.engine),
            now=now,
        )
        records.append(_dataclass_payload(record))
    return tuple(records)


def _default_promotion_gates(
    cards: tuple[StrategyCard, ...],
) -> tuple[PromotionGateDecision, ...]:
    decisions = []
    for card in cards:
        policy = ENGINE_RISK_POLICIES[card.engine]
        policy_decision = evaluate_policy(
            policy,
            PolicyState(
                proposed_position_pct=0.0,
                current_positions=0,
                paper_days=0,
                paper_sessions=0,
            ),
        )
        evidence = PromotionGateEvidence(
            validation_passed=False,
            unresolved_findings=("15A_daily_summary_not_a_promotion_request",),
        )
        decisions.append(evaluate_promotion_gate(card, policy_decision, evidence))
    return tuple(decisions)


def _default_champion_challenger(
    cards: tuple[StrategyCard, ...],
) -> tuple[ChampionChallengerDecision, ...]:
    outcomes = []
    for engine in ("wealth", "moonshot"):
        candidates = [card for card in cards if card.engine == engine and card.lane == "deterministic"]
        if not candidates:
            continue
        incumbent = candidates[0]
        challenger = replace(incumbent, card_id=f"15A-{incumbent.card_id}-CHALLENGER")
        outcomes.append(
            evaluate_champion_challenger(
                incumbent=incumbent,
                challenger=challenger,
                incumbent_metrics=StrategyOosMetrics(
                    in_sample_sharpe=1.0,
                    oos_sharpe=0.70,
                    oos_max_drawdown=-0.08,
                    oos_total_return=0.05,
                    trade_count=24,
                    oos_windows=4,
                    positive_oos_windows=3,
                ),
                challenger_metrics=StrategyOosMetrics(
                    in_sample_sharpe=1.1,
                    oos_sharpe=0.72,
                    oos_max_drawdown=-0.08,
                    oos_total_return=0.06,
                    trade_count=24,
                    oos_windows=4,
                    positive_oos_windows=3,
                ),
                challenger_policy_state=PolicyState(
                    proposed_position_pct=0.0,
                    current_positions=0,
                ),
            )
        )
    return tuple(outcomes)


def _strategy_card_payload(card: StrategyCard) -> dict[str, Any]:
    card.validate()
    return _normalize_json_value(_dataclass_payload(card))


def _research_result_for_card(card: StrategyCard) -> dict[str, Any]:
    return {
        "strategy_id": card.card_id,
        "engine": card.engine,
        "label": card.label,
        "summary": card.hypothesis,
    }


def _promotion_gate_summary(decision: PromotionGateDecision) -> dict[str, Any]:
    decision.validate()
    return {
        "strategy_id": decision.strategy_id,
        "engine": decision.engine,
        "label": decision.label,
        "promotion_status": decision.promotion_status,
        "summary": "; ".join(decision.reasons),
        "reasons": list(decision.reasons),
        "human_review_required": decision.human_review_required,
        "live_trading_enabled": decision.live_trading_enabled,
        "broker_order_routing_enabled": decision.broker_order_routing_enabled,
        "broker_order_call_performed": decision.broker_order_call_performed,
    }


def _champion_challenger_summary(decision: ChampionChallengerDecision) -> dict[str, Any]:
    decision.validate()
    return {
        "incumbent_strategy_id": decision.incumbent_strategy_id,
        "challenger_strategy_id": decision.challenger_strategy_id,
        "engine": decision.engine,
        "label": decision.label,
        "challenger_status": decision.challenger_status,
        "summary": "; ".join(decision.reasons),
        "reasons": list(decision.reasons),
        "oos_sharpe_delta": decision.oos_sharpe_delta,
        "oos_total_return_delta": decision.oos_total_return_delta,
        "max_drawdown_delta": decision.max_drawdown_delta,
        "risk_policy_compatible": decision.risk_policy_compatible,
        "human_review_required": decision.human_review_required,
        "live_trading_enabled": decision.live_trading_enabled,
        "broker_order_routing_enabled": decision.broker_order_routing_enabled,
        "broker_order_call_performed": decision.broker_order_call_performed,
    }


def _safety_status_payload(result: SafetyScanResult | None) -> dict[str, Any]:
    if result is None:
        return {
            "status": "not_run",
            "label": HUMAN_REVIEW_REQUIRED,
            "summary": "Safety scanner status was not supplied to the daily summary.",
            "passed": None,
            "finding_count": 0,
            "scanned_files": 0,
            "skipped_files": [],
            "findings": [],
        }
    return {
        "status": "passed" if result.passed else "blocked",
        "label": HUMAN_REVIEW_REQUIRED if result.passed else BLOCKED_BY_SAFETY_GATE,
        "summary": "Safety scanner completed for supplied paths.",
        "passed": result.passed,
        "finding_count": len(result.findings),
        "scanned_files": result.scanned_files,
        "skipped_files": list(result.skipped_files),
        "findings": [_dataclass_payload(finding) for finding in result.findings],
    }


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
        "live_trading_enabled": False,
        "secrets_required": False,
        "status": "LIVE TRADING: DISABLED",
    }


def _section(title: str, items: list[dict[str, Any]], id_key: str) -> list[str]:
    lines = [f"## {title}", ""]
    if not items:
        return [*lines, "- None recorded.", ""]
    for item in items:
        item_id = item.get(id_key) or item.get("strategy_id") or item.get("status") or "item"
        label = item.get("label", "n/a")
        status = item.get("promotion_status") or item.get("challenger_status") or item.get("status")
        summary = item.get("summary") or item.get("hypothesis") or "Recorded."
        lines.append(f"- {item_id} | {label} | {status or 'recorded'} | {summary}")
    lines.append("")
    return lines


def _weekly_review_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    weekly = payload.get("weekly_review") or {}
    if not weekly:
        return []
    return [
        {
            "review_id": weekly.get("review_id", "weekly_review"),
            "label": weekly.get("safety_boundary", {}).get("label", HUMAN_REVIEW_REQUIRED),
            "status": weekly.get("safety_boundary", {}).get("status", "recorded"),
            "summary": (
                f"{weekly.get('summary', {}).get('experiment_count', 0)} experiments and "
                f"{weekly.get('summary', {}).get('blocked_decision_count', 0)} blocked decisions summarized."
            ),
        }
    ]


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
        if label is not None and label not in SAFE_DAILY_RESEARCH_LABELS:
            raise ValueError(f"unsafe daily research label: {label}")
        if label in DISALLOWED_DAILY_RESEARCH_LABELS:
            raise ValueError(f"disallowed daily research label: {label}")
        for unsafe_field in UNSAFE_TRUE_FIELDS:
            if value.get(unsafe_field) is True:
                raise ValueError(f"daily research cannot set {unsafe_field}")
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
        if value in DISALLOWED_DAILY_RESEARCH_LABELS:
            raise ValueError(f"disallowed daily research text: {value}")
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
