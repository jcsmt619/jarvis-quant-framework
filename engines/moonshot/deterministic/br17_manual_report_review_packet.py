from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


PHASE_ID = "BR-17"
MODULE_NAME = "BR-14 Manual Report Review Packet"
SOURCE_PHASE_ID = "BR-14"
DEFAULT_EVIDENCE_DIR = Path("reports/br14_local_paper_research_session_runner/manual_20260709T194500")
DEFAULT_REPORT_DIR = Path("reports/br17_manual_report_review_packet")
JSON_REPORT_NAME = "manual_report_review_packet.json"
MARKDOWN_REPORT_NAME = "manual_report_review_packet.md"
REQUIRED_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
REQUIRED_DISABLED_FLAGS = (
    "credential_loading_attempted",
    "data_provider_call_attempted",
    "broker_connection_attempted",
    "broker_read_call_performed",
    "real_paper_wrapper_connected",
    "real_paper_wrapper_attempted",
    "real_paper_order_submitted",
    "broker_order_call_performed",
    "broker_order_submitted",
    "broker_order_routing_enabled",
    "trade_instruction_created",
    "broker_action_created",
    "order_path_created",
    "live_trading_enabled",
)
EVIDENCE_ARTIFACTS = {
    "session": "local_paper_research_session.json",
    "candidate_universe": "br02_candidate_universe/candidate_universe.json",
    "options_chain_quality": "br03_options_chain_quality/options_chain_quality.json",
    "contract_scoring": "br04_contract_scoring/options_contract_scoring.json",
    "llm_thesis_package": "br05_analyst_thesis/llm_analyst_thesis_generator.json",
    "risk_gate_decisions": "br06_risk_gate/trade_score_risk_gate.json",
    "paper_portfolio_state": "br07_paper_portfolio/paper_options_portfolio.json",
    "monitor_alerts": "br08_position_monitor/daily_position_monitor_alerts.json",
    "operator_dashboard": "br09_operator_dashboard/local_operator_dashboard.json",
}


@dataclass(frozen=True)
class ManualReportReviewPacket:
    as_of: datetime
    evidence_dir: str
    evidence: dict[str, dict[str, Any]]
    safety: dict[str, Any]
    label: str = HUMAN_REVIEW_REQUIRED

    def validate(self) -> None:
        if self.label != HUMAN_REVIEW_REQUIRED:
            raise ValueError("BR-17 manual review packet must require human review")
        if set(EVIDENCE_ARTIFACTS) - set(self.evidence):
            raise ValueError("BR-17 manual review packet requires all configured evidence artifacts")
        for name, payload in self.evidence.items():
            if not isinstance(payload, dict):
                raise ValueError(f"{name} evidence must be a JSON object")
        if self.evidence["session"].get("phase") != SOURCE_PHASE_ID:
            raise ValueError("BR-17 source session must be BR-14")
        _validate_disabled_safety(self.safety)


def safety_manifest() -> dict[str, Any]:
    return {
        "phase": PHASE_ID,
        "module": MODULE_NAME,
        "source_phase": SOURCE_PHASE_ID,
        "labels": REQUIRED_LABELS,
        "research_only": True,
        "monitor_only": True,
        "paper_only": True,
        "human_review_required": True,
        "blocked_by_safety_gate": True,
        "read_only": True,
        "manual_review_packet_only": True,
        "session_rerun_attempted": False,
        "evidence_mutation_attempted": False,
        "artifact_deletion_attempted": False,
        "credential_loading_attempted": False,
        "data_provider_call_attempted": False,
        "broker_connection_attempted": False,
        "broker_read_call_performed": False,
        "real_paper_wrapper_connected": False,
        "real_paper_wrapper_attempted": False,
        "real_paper_order_submitted": False,
        "broker_order_call_performed": False,
        "broker_order_submitted": False,
        "broker_order_routing_enabled": False,
        "trade_instruction_created": False,
        "broker_action_created": False,
        "order_path_created": False,
        "live_trading_enabled": False,
        "LIVE TRADING": "DISABLED",
    }


def build_manual_report_review_packet(
    evidence_dir: Path = DEFAULT_EVIDENCE_DIR,
    as_of: datetime | None = None,
) -> ManualReportReviewPacket:
    evidence_dir = Path(evidence_dir)
    evidence = {name: _load_json(evidence_dir / relative_path) for name, relative_path in EVIDENCE_ARTIFACTS.items()}
    packet = ManualReportReviewPacket(
        as_of=as_of or datetime.now(timezone.utc).replace(microsecond=0),
        evidence_dir=str(evidence_dir),
        evidence=evidence,
        safety=safety_manifest(),
    )
    packet.validate()
    return packet


def manual_report_review_packet_payload(packet: ManualReportReviewPacket) -> dict[str, Any]:
    packet.validate()
    evidence = packet.evidence
    session = evidence["session"]
    risk_gate = evidence["risk_gate_decisions"]
    category_summary = _hold_reject_review_categories(risk_gate.get("decisions", ()))
    return {
        "phase": PHASE_ID,
        "module": MODULE_NAME,
        "source_phase": SOURCE_PHASE_ID,
        "as_of": packet.as_of.isoformat(),
        "label": packet.label,
        "evidence_dir": packet.evidence_dir,
        "safety": packet.safety,
        "evidence_artifacts": _evidence_artifact_references(Path(packet.evidence_dir)),
        "source_session_summary": {
            "as_of": session.get("as_of"),
            "label": session.get("label"),
            "metrics": session.get("metrics", {}),
            "session_flow": tuple(session.get("session_flow", ())),
            "paper_contract_ids": tuple(session.get("paper_contract_ids", ())),
            "monitor_alert_ids": tuple(session.get("monitor_alert_ids", ())),
        },
        "candidate_universe_summary": _candidate_universe_summary(evidence["candidate_universe"]),
        "options_chain_quality_summary": _options_chain_quality_summary(evidence["options_chain_quality"]),
        "contract_scoring_summary": _contract_scoring_summary(evidence["contract_scoring"]),
        "llm_thesis_package_summary": _llm_thesis_summary(evidence["llm_thesis_package"]),
        "deterministic_risk_gate_summary": _risk_gate_summary(risk_gate),
        "simulated_paper_contracts": _simulated_paper_contracts(evidence["paper_portfolio_state"]),
        "paper_portfolio_state": _paper_portfolio_summary(evidence["paper_portfolio_state"]),
        "monitor_alert_summary": _monitor_alert_summary(evidence["monitor_alerts"]),
        "operator_dashboard_references": _operator_dashboard_summary(evidence["operator_dashboard"]),
        "hold_reject_review_categories": category_summary,
        "review_questions": _review_questions(category_summary),
        "required_human_review_actions": _required_human_review_actions(),
        "acceptance_criteria": _acceptance_criteria(packet, category_summary),
        "readiness_state": {
            "state": "BLOCKED_BY_SAFETY_GATE_HUMAN_REVIEW_REQUIRED",
            "ready_for_live_trading": False,
            "broker_actions_allowed": False,
            "manual_review_required": True,
        },
    }


def render_markdown_manual_report_review_packet(packet: ManualReportReviewPacket) -> str:
    payload = manual_report_review_packet_payload(packet)
    lines = [
        f"# {PHASE_ID} {MODULE_NAME}",
        "",
        "Research labels: " + ", ".join(REQUIRED_LABELS),
        "LIVE TRADING: DISABLED",
        "",
        "## Source Session",
    ]
    source = payload["source_session_summary"]
    lines.append(f"- source_as_of: {source['as_of']}")
    lines.append(f"- label: {source['label']}")
    for name, value in source["metrics"].items():
        lines.append(f"- {name}: {value}")

    lines.extend(["", "## Candidate Universe"])
    for item in payload["candidate_universe_summary"]["included_candidates"]:
        lines.append(f"- review: {item['symbol']} score={item['score']} label={item['label']}")
    for item in payload["candidate_universe_summary"]["blocked_candidates"]:
        lines.append(f"- reject: {item['symbol']} score={item['score']} reasons={', '.join(item['reasons'])}")

    lines.extend(["", "## Options Chain Quality"])
    chain_quality = payload["options_chain_quality_summary"]
    lines.append(f"- passed_chain_count: {chain_quality['metrics'].get('passed_chain_count')}")
    lines.append(f"- blocked_chain_count: {chain_quality['metrics'].get('blocked_chain_count')}")
    for item in chain_quality["passed_chains"]:
        lines.append(f"- hold/review: {item['underlying_symbol']} score={item['score']} contracts={item['contract_count']}")
    for item in chain_quality["blocked_chains"]:
        lines.append(f"- reject: {item['underlying_symbol']} reasons={', '.join(item['reasons'])}")

    lines.extend(["", "## Contract Scoring"])
    for item in payload["contract_scoring_summary"]["suitable_contracts"]:
        lines.append(f"- review: {item['contract_id']} total_score={item['total_score']} label={item['label']}")
    for item in payload["contract_scoring_summary"]["blocked_contracts"]:
        lines.append(f"- reject: {item['contract_id']} total_score={item['total_score']} reasons={', '.join(item['reasons'])}")

    lines.extend(["", "## LLM Thesis Package"])
    for item in payload["llm_thesis_package_summary"]["thesis_records"]:
        lines.append(f"- {item['thesis_id']}: symbol={item['symbol']} confidence={item['confidence']} label={item['label']}")

    lines.extend(["", "## Deterministic Risk Gate Decisions"])
    for item in payload["deterministic_risk_gate_summary"]["decisions"]:
        lines.append(f"- {item['category']}: {item['contract_id']} score={item['score']} label={item['label']}")

    lines.extend(["", "## Simulated Paper Contracts"])
    for item in payload["simulated_paper_contracts"]:
        lines.append(f"- {item['contract_id']}: fill_id={item['fill_id']} premium={item['premium']} label={item['label']}")

    lines.extend(["", "## Paper Portfolio State"])
    portfolio = payload["paper_portfolio_state"]
    lines.append(f"- cash: {portfolio['cash']}")
    lines.append(f"- total_pnl: {portfolio['total_pnl']}")
    lines.append(f"- net_liquidation_value: {portfolio['net_liquidation_value']}")
    lines.append(f"- premium_at_risk_pct: {portfolio['premium_at_risk_pct']}")

    lines.extend(["", "## Monitor Alerts"])
    alerts = payload["monitor_alert_summary"]
    lines.append(f"- alert_count: {alerts['metrics'].get('alert_count')}")
    for item in alerts["alerts"] or ("no_monitor_alerts",):
        lines.append(f"- {item if isinstance(item, str) else item.get('alert_id', 'alert')}")

    lines.extend(["", "## Operator Dashboard References"])
    dashboard = payload["operator_dashboard_references"]
    lines.append(f"- candidate_count: {dashboard['metrics'].get('candidate_count')}")
    lines.append(f"- paper_position_count: {dashboard['metrics'].get('paper_position_count')}")
    for item in dashboard["candidates"]:
        lines.append(f"- {item['symbol']}: label={item['label']} review_required={item['human_review_required']}")

    lines.extend(["", "## Hold Reject Review Categories"])
    categories = payload["hold_reject_review_categories"]
    for name in ("hold", "review", "reject"):
        values = categories[name]
        lines.append(f"- {name}: {', '.join(values) if values else 'none'}")

    lines.extend(["", "## Review Questions"])
    for question in payload["review_questions"]:
        lines.append(f"- {question}")

    lines.extend(["", "## Required Human Review Actions"])
    for action in payload["required_human_review_actions"]:
        lines.append(f"- {action}")

    lines.extend(["", "## Acceptance Criteria"])
    for name, passed in payload["acceptance_criteria"].items():
        lines.append(f"- {name}: {passed}")

    lines.extend(
        [
            "",
            "## Safety Boundaries",
            "- RESEARCH_ONLY; MONITOR_ONLY; PAPER_ONLY; HUMAN_REVIEW_REQUIRED; BLOCKED_BY_SAFETY_GATE.",
            "- Read-only packet generation from committed BR-14 evidence.",
            "- No session rerun, evidence edit, credential loading, data-provider call, broker connection, broker action, order path, or live trading enablement.",
        ]
    )
    return "\n".join(lines)


def write_manual_report_review_packet(
    packet: ManualReportReviewPacket,
    out_dir: Path = DEFAULT_REPORT_DIR,
) -> tuple[Path, Path]:
    packet.validate()
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_REPORT_NAME
    markdown_path = out_dir / MARKDOWN_REPORT_NAME
    json_path.write_text(json.dumps(manual_report_review_packet_payload(packet), indent=2, default=str), encoding="utf-8")
    markdown_path.write_text(render_markdown_manual_report_review_packet(packet), encoding="utf-8")
    return json_path, markdown_path


def run_manual_report_review_packet(
    evidence_dir: Path = DEFAULT_EVIDENCE_DIR,
    out_dir: Path = DEFAULT_REPORT_DIR,
    as_of: datetime | None = None,
) -> ManualReportReviewPacket:
    packet = build_manual_report_review_packet(evidence_dir=evidence_dir, as_of=as_of)
    write_manual_report_review_packet(packet, out_dir=out_dir)
    return packet


def _candidate_universe_summary(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "metrics": payload.get("metrics", {}),
        "watchlists": payload.get("watchlists", {}),
        "included_candidates": [
            _pick(item, ("symbol", "name", "sector", "score", "label", "human_review_required"))
            for item in payload.get("included_candidates", ())
        ],
        "blocked_candidates": [
            _pick(item, ("symbol", "name", "sector", "score", "label", "reasons", "human_review_required"))
            for item in payload.get("blocked_candidates", ())
        ],
    }


def _options_chain_quality_summary(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "metrics": payload.get("metrics", {}),
        "passed_chains": [
            {
                "underlying_symbol": item.get("underlying_symbol"),
                "score": item.get("score"),
                "label": item.get("label"),
                "contract_count": len(item.get("contracts", ())),
                "contract_ids": tuple(contract.get("contract_id") for contract in item.get("contracts", ())),
            }
            for item in payload.get("passed_chains", ())
        ],
        "blocked_chains": [
            {
                "underlying_symbol": item.get("underlying_symbol"),
                "score": item.get("score"),
                "label": item.get("label"),
                "reasons": tuple(item.get("reasons", ())),
                "contract_ids": tuple(contract.get("contract_id") for contract in item.get("contracts", ())),
            }
            for item in payload.get("blocked_chains", ())
        ],
    }


def _contract_scoring_summary(payload: dict[str, Any]) -> dict[str, Any]:
    fields = ("contract_id", "underlying_symbol", "strike", "expiration", "dte", "total_score", "label", "reasons")
    return {
        "metrics": payload.get("metrics", {}),
        "suitable_contracts": [_pick(item, fields) for item in payload.get("suitable_contracts", ())],
        "blocked_contracts": [_pick(item, fields) for item in payload.get("blocked_contracts", ())],
    }


def _llm_thesis_summary(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "metrics": payload.get("metrics", {}),
        "prompt_packages": [
            _pick(item, ("prompt_id", "symbol", "contract_ids", "label"))
            for item in payload.get("prompt_packages", ())
        ],
        "thesis_records": [
            _pick(
                item,
                (
                    "thesis_id",
                    "prompt_id",
                    "symbol",
                    "thesis_summary",
                    "confidence",
                    "source_citations",
                    "risk_notes",
                    "label",
                    "human_review_required",
                ),
            )
            for item in payload.get("thesis_records", ())
        ],
    }


def _risk_gate_summary(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "metrics": payload.get("metrics", {}),
        "decisions": [
            {
                **_pick(
                    item,
                    (
                        "contract_id",
                        "symbol",
                        "score",
                        "label",
                        "hard_block_reasons",
                        "review_reasons",
                        "chain_quality_score",
                        "contract_total_score",
                        "human_review_required",
                    ),
                ),
                "category": _decision_category(item),
            }
            for item in payload.get("decisions", ())
        ],
    }


def _simulated_paper_contracts(payload: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    return tuple(
        _pick(item, ("fill_id", "contract_id", "symbol", "underlying_symbol", "contracts", "fill_price", "premium", "label", "simulated_fill"))
        for item in payload.get("fills", ())
    )


def _paper_portfolio_summary(payload: dict[str, Any]) -> dict[str, Any]:
    exposure = payload.get("exposure", {})
    return {
        "metrics": payload.get("metrics", {}),
        "cash": payload.get("cash"),
        "realized_pnl": payload.get("realized_pnl"),
        "unrealized_pnl": payload.get("unrealized_pnl"),
        "total_pnl": payload.get("total_pnl"),
        "net_liquidation_value": exposure.get("net_liquidation_value"),
        "premium_at_risk": exposure.get("premium_at_risk"),
        "premium_at_risk_pct": exposure.get("premium_at_risk_pct"),
        "warnings": tuple(payload.get("warnings", ())),
        "positions": [
            _pick(
                item,
                (
                    "contract_id",
                    "underlying_symbol",
                    "contracts",
                    "average_price",
                    "mark_price",
                    "market_value",
                    "unrealized_pnl",
                    "unrealized_pnl_pct",
                    "label",
                    "human_review_required",
                ),
            )
            for item in payload.get("positions", ())
        ],
    }


def _monitor_alert_summary(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "metrics": payload.get("metrics", {}),
        "alerts": tuple(payload.get("alerts", ())),
        "warnings": tuple(payload.get("warnings", ())),
        "snapshots": [
            _pick(
                item,
                (
                    "contract_id",
                    "observed_at",
                    "underlying_price_move_pct",
                    "spread_change_pct",
                    "implied_volatility_change_pct",
                    "thesis_valid",
                    "current_risk_gate_label",
                    "label",
                ),
            )
            for item in payload.get("snapshots", ())
        ],
    }


def _operator_dashboard_summary(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "metrics": payload.get("metrics", {}),
        "candidates": [
            _pick(
                item,
                (
                    "symbol",
                    "candidate_score",
                    "risk_score",
                    "risk_label",
                    "paper_position_count",
                    "paper_market_value",
                    "alert_count",
                    "thesis_id",
                    "label",
                    "human_review_required",
                ),
            )
            for item in payload.get("candidates", ())
        ],
        "paper_positions": [
            _pick(item, ("contract_id", "underlying_symbol", "contracts", "market_value", "unrealized_pnl", "label"))
            for item in payload.get("paper_positions", ())
        ],
        "thesis_notes": [
            _pick(item, ("thesis_id", "symbol", "confidence", "label", "human_review_required"))
            for item in payload.get("thesis_notes", ())
        ],
    }


def _hold_reject_review_categories(decisions: Any) -> dict[str, tuple[str, ...]]:
    hold: list[str] = []
    review: list[str] = []
    reject: list[str] = []
    for item in decisions:
        category = _decision_category(item)
        contract_id = item.get("contract_id", "unknown_contract")
        if category == "hold":
            hold.append(contract_id)
        elif category == "reject":
            reject.append(contract_id)
        else:
            review.append(contract_id)
    return {"hold": tuple(hold), "review": tuple(review), "reject": tuple(reject)}


def _decision_category(item: dict[str, Any]) -> str:
    if item.get("hard_block_reasons") or item.get("label") == BLOCKED_BY_SAFETY_GATE:
        return "reject"
    if item.get("label") == PAPER_ONLY:
        return "hold"
    return "review"


def _review_questions(categories: dict[str, tuple[str, ...]]) -> tuple[str, ...]:
    return (
        "Do BR-14 candidate inclusion and exclusion reasons match the committed evidence?",
        "Do passed option chains and scored contracts remain source-grounded and complete enough for human review?",
        "Do thesis records cite only supplied evidence and remain labeled HUMAN_REVIEW_REQUIRED?",
        f"Should hold-category paper contracts remain paper-only monitored items: {', '.join(categories['hold']) or 'none'}?",
        f"Should review-category contracts remain blocked pending manual decision: {', '.join(categories['review']) or 'none'}?",
        f"Are reject-category contracts correctly blocked by deterministic safety gates: {', '.join(categories['reject']) or 'none'}?",
        "Are all broker, order-path, credential, and live-trading controls still disabled?",
    )


def _required_human_review_actions() -> tuple[str, ...]:
    return (
        "Human reviewer must compare this BR-17 packet against committed BR-14 evidence artifacts.",
        "Human reviewer must verify every trade-relevant item remains HUMAN_REVIEW_REQUIRED.",
        "Human reviewer must verify PAPER_ONLY items are simulated paper records, not broker actions.",
        "Human reviewer must reject any item whose source evidence is stale, missing, or inconsistent.",
        "Human reviewer must keep live trading disabled and broker order paths inactive.",
    )


def _acceptance_criteria(packet: ManualReportReviewPacket, categories: dict[str, tuple[str, ...]]) -> dict[str, bool]:
    source_safety = packet.evidence["session"].get("safety", {})
    return {
        "source_phase_is_br14": packet.evidence["session"].get("phase") == SOURCE_PHASE_ID,
        "all_evidence_artifacts_loaded": set(packet.evidence) == set(EVIDENCE_ARTIFACTS),
        "packet_is_read_only": packet.safety["read_only"] is True,
        "session_not_rerun": packet.safety["session_rerun_attempted"] is False,
        "evidence_not_mutated": packet.safety["evidence_mutation_attempted"] is False,
        "no_credentials_or_provider_calls": packet.safety["credential_loading_attempted"] is False
        and packet.safety["data_provider_call_attempted"] is False,
        "no_broker_or_order_paths": all(packet.safety[field_name] is False for field_name in REQUIRED_DISABLED_FLAGS),
        "source_live_trading_disabled": source_safety.get("LIVE TRADING") == "DISABLED",
        "packet_live_trading_disabled": packet.safety["LIVE TRADING"] == "DISABLED",
        "hold_review_reject_categories_present": all(name in categories for name in ("hold", "review", "reject")),
        "human_review_required": packet.label == HUMAN_REVIEW_REQUIRED,
    }


def _evidence_artifact_references(evidence_dir: Path) -> dict[str, dict[str, Any]]:
    return {
        name: {
            "json_path": str(evidence_dir / relative_path),
            "present": (evidence_dir / relative_path).exists(),
            "read_only_source": True,
        }
        for name, relative_path in EVIDENCE_ARTIFACTS.items()
    }


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _pick(payload: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    return {field_name: payload.get(field_name) for field_name in fields}


def _validate_disabled_safety(manifest: dict[str, Any]) -> None:
    for field_name in ("session_rerun_attempted", "evidence_mutation_attempted", "artifact_deletion_attempted", *REQUIRED_DISABLED_FLAGS):
        if manifest.get(field_name) is not False:
            raise ValueError(f"BR-17 manual review packet cannot set {field_name}")
    if manifest.get("LIVE TRADING") != "DISABLED":
        raise ValueError("BR-17 manual review packet must keep LIVE TRADING disabled")
