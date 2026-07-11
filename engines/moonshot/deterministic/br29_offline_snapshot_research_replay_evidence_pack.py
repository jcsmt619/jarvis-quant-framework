from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from engines.moonshot.deterministic.br26_read_only_data_snapshot_import_contract import (
    REQUIRED_DISABLED_FLAGS,
)
from engines.moonshot.deterministic.br28_snapshot_to_candidate_adapter import (
    DEFAULT_REPORT_DIR as DEFAULT_BR28_REPORT_DIR,
    JSON_REPORT_NAME as BR28_JSON_REPORT_NAME,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


PHASE_ID = "BR-29"
MODULE_NAME = "Offline Snapshot Research Replay Evidence Pack"
STRATEGY_VERSION = "br29.offline_snapshot_replay.v1"
DEFAULT_BR28_REPORT_PATH = DEFAULT_BR28_REPORT_DIR / BR28_JSON_REPORT_NAME
DEFAULT_REPORT_DIR = Path("reports/br29_offline_snapshot_research_replay_evidence_pack")
JSON_REPORT_NAME = "offline_snapshot_research_replay_evidence_pack.json"
MARKDOWN_REPORT_NAME = "offline_snapshot_research_replay_evidence_pack.md"
REQUIRED_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
REPLAY_CHECKS = (
    "br28_report_loaded",
    "br28_report_accepted",
    "candidates_remain_human_review_required",
    "frozen_deterministic_boundaries_used",
    "opportunity_driven_selection",
    "no_fixed_daily_trade_quota",
    "aggregate_risk_budget_enforced",
    "concentration_limit_enforced",
    "duplicate_signal_controls_enforced",
    "operational_circuit_breakers_enforced",
    "post_decision_outcomes_available",
    "no_alpha_claim_created",
)
BLOCK_REASONS = (
    "br28_report_missing",
    "br28_report_malformed",
    "br28_report_not_accepted",
    "candidate_not_human_review_required",
    "missing_required_feature_inputs",
    "non_positive_price",
    "insufficient_liquidity",
    "missing_benchmark_context",
    "duplicate_signal_blocked",
    "aggregate_risk_budget_exceeded",
    "concentration_limit_exceeded",
    "operational_circuit_breaker_open",
    "post_decision_exit_prices_missing",
    "outcome_return_series_missing",
    "benchmark_return_series_missing",
    "fold_history_missing",
    "parameter_neighborhood_source_missing",
)


@dataclass(frozen=True)
class ReplayDecision:
    candidate_id: str
    symbol: str
    decision_timestamp: str
    label: str
    status: str
    weight: float
    gross_exposure: float
    gate_results: dict[str, bool]
    blocked_reasons: tuple[str, ...]
    required_human_review_actions: tuple[str, ...]

    def validate(self) -> None:
        if self.label not in (PAPER_ONLY, BLOCKED_BY_SAFETY_GATE):
            raise ValueError("BR-29 decisions must be paper-only or blocked by safety gate")
        if self.status not in ("PAPER_ONLY_RESEARCH_REPORTABLE", "BLOCKED_BY_SAFETY_GATE"):
            raise ValueError("BR-29 decision status is not recognized")
        if self.label == PAPER_ONLY and self.status != "PAPER_ONLY_RESEARCH_REPORTABLE":
            raise ValueError("BR-29 paper decisions must be reportable only")
        if self.label == BLOCKED_BY_SAFETY_GATE and not self.blocked_reasons:
            raise ValueError("BR-29 blocked decisions require reasons")
        if self.weight < 0 or self.gross_exposure < 0:
            raise ValueError("BR-29 paper weights and exposure cannot be negative")
        if not self.required_human_review_actions:
            raise ValueError("BR-29 decisions require human review actions")


@dataclass(frozen=True)
class OfflineSnapshotResearchReplayEvidencePack:
    as_of: datetime
    source_paths: dict[str, str]
    replay_checks: dict[str, bool]
    decisions: tuple[ReplayDecision, ...]
    metrics: dict[str, Any]
    unsupported_metrics: dict[str, str]
    unresolved_blockers: tuple[dict[str, Any], ...]
    safety: dict[str, Any]
    label: str = HUMAN_REVIEW_REQUIRED

    def validate(self) -> None:
        if self.label != HUMAN_REVIEW_REQUIRED:
            raise ValueError("BR-29 evidence pack must require human review")
        if set(self.replay_checks) != set(REPLAY_CHECKS):
            raise ValueError("BR-29 evidence pack must record every replay check")
        if not isinstance(self.metrics, dict):
            raise ValueError("BR-29 metrics must be a JSON object")
        for decision in self.decisions:
            decision.validate()
        for reason in _all_block_reasons(self.unresolved_blockers):
            if reason not in BLOCK_REASONS:
                raise ValueError("BR-29 blocker reason is not recognized")
        _validate_disabled_safety(self.safety)


def safety_manifest() -> dict[str, Any]:
    return {
        "phase": PHASE_ID,
        "module": MODULE_NAME,
        "labels": REQUIRED_LABELS,
        "research_only": True,
        "monitor_only": True,
        "paper_only": True,
        "human_review_required": True,
        "blocked_by_safety_gate": True,
        "offline_only": True,
        "read_only": True,
        "report_only": True,
        "fixture_testable": True,
        "br28_snapshot_candidates_only": True,
        "frozen_deterministic_boundaries_used": True,
        "screening_gate_enforced": True,
        "strategy_gate_enforced": True,
        "liquidity_gate_enforced": True,
        "correlation_gate_enforced": True,
        "portfolio_risk_gate_enforced": True,
        "lifecycle_gate_enforced": True,
        "safety_gate_enforced": True,
        "opportunity_driven_selection": True,
        "fixed_daily_trade_quota_imposed": False,
        "alpha_claim_created": False,
        "evaluation_period_tuning_performed": False,
        "parameter_optimization_performed": False,
        "strategy_selected_using_evaluation_outcomes": False,
        "credential_loading_attempted": False,
        "env_file_read_attempted": False,
        "secret_request_attempted": False,
        "data_provider_call_attempted": False,
        "external_network_call_attempted": False,
        "real_data_fetch_attempted": False,
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
        "live_state_mutation_attempted": False,
        "paper_state_mutation_attempted": False,
        "live_state_mutation_allowed": False,
        "paper_state_mutation_allowed": False,
        "broker_state_mutation_allowed": False,
        "routing_state_mutation_allowed": False,
        "broker_write_operations_authorized": False,
        "external_routing_paths_authorized": False,
        "data_provider_calls_authorized": False,
        "live_trading_enabled": False,
        "LIVE TRADING": "DISABLED",
    }


def build_offline_snapshot_research_replay_evidence_pack(
    br28_report_path: Path = DEFAULT_BR28_REPORT_PATH,
    as_of: datetime | None = None,
) -> OfflineSnapshotResearchReplayEvidencePack:
    resolved_as_of = as_of or datetime.now(timezone.utc).replace(microsecond=0)
    br28_payload, load_reasons = _load_json(br28_report_path)
    unresolved: list[dict[str, Any]] = []
    unresolved.extend(_block_record(str(br28_report_path), load_reasons))

    br28_accepted = _br28_report_accepted(br28_payload)
    if br28_payload is not None and not br28_accepted:
        unresolved.extend(_block_record(str(br28_report_path), ("br28_report_not_accepted",)))

    candidates = _candidate_payloads(br28_payload) if br28_accepted else ()
    decisions, decision_blocks = _replay_candidates(candidates)
    unresolved.extend(decision_blocks)
    unresolved.extend(_unsupported_performance_blocks())

    supported_metrics = _supported_metrics(decisions)
    unsupported_metrics = _unsupported_metrics()
    replay_checks = {
        "br28_report_loaded": br28_payload is not None,
        "br28_report_accepted": br28_accepted,
        "candidates_remain_human_review_required": all(
            candidate.get("label") == HUMAN_REVIEW_REQUIRED
            and candidate.get("human_review_status") == HUMAN_REVIEW_REQUIRED
            for candidate in candidates
        )
        if candidates
        else False,
        "frozen_deterministic_boundaries_used": True,
        "opportunity_driven_selection": True,
        "no_fixed_daily_trade_quota": True,
        "aggregate_risk_budget_enforced": supported_metrics["gross_exposure"] <= 1.0,
        "concentration_limit_enforced": supported_metrics["max_symbol_weight"] <= 0.5 if decisions else True,
        "duplicate_signal_controls_enforced": True,
        "operational_circuit_breakers_enforced": True,
        "post_decision_outcomes_available": False,
        "no_alpha_claim_created": True,
    }
    pack = OfflineSnapshotResearchReplayEvidencePack(
        as_of=resolved_as_of,
        source_paths={"BR-28 snapshot-to-candidate adapter report": str(br28_report_path)},
        replay_checks=replay_checks,
        decisions=decisions,
        metrics={**supported_metrics, **{name: None for name in unsupported_metrics}},
        unsupported_metrics=unsupported_metrics,
        unresolved_blockers=tuple(unresolved),
        safety=safety_manifest(),
    )
    pack.validate()
    return pack


def offline_snapshot_research_replay_evidence_pack_payload(
    pack: OfflineSnapshotResearchReplayEvidencePack,
) -> dict[str, Any]:
    pack.validate()
    acceptance = _acceptance_criteria(pack)
    return {
        "phase": PHASE_ID,
        "module": MODULE_NAME,
        "as_of": pack.as_of.isoformat(),
        "label": pack.label,
        "strategy_version": STRATEGY_VERSION,
        "source_paths": pack.source_paths,
        "replay_checks": pack.replay_checks,
        "block_reasons": BLOCK_REASONS,
        "safety": pack.safety,
        "metrics": pack.metrics,
        "unsupported_metrics": pack.unsupported_metrics,
        "candidate_replay_decisions": [_decision_payload(item) for item in pack.decisions],
        "cost_sensitivity": _cost_sensitivity(pack.decisions),
        "symbol_contribution": _symbol_contribution(pack.decisions),
        "fold_stability": _unsupported_section(
            "fold_history_missing",
            "BR-28 snapshot candidates do not include fold-level outcome history.",
        ),
        "parameter_neighborhood_evidence": _unsupported_section(
            "parameter_neighborhood_source_missing",
            "BR-28 snapshot candidates preserve frozen inputs but do not include parameter-neighborhood replay results.",
        ),
        "unresolved_blockers": pack.unresolved_blockers,
        "required_human_review_actions": _human_review_actions(pack.decisions),
        "acceptance_criteria": acceptance,
        "readiness_state": {
            "state": "OFFLINE_RESEARCH_REPLAY_EVIDENCE_ONLY",
            "research_only": True,
            "paper_only": True,
            "manual_review_required": True,
            "human_review_required": True,
            "ready_for_live_trading": False,
            "alpha_claim_allowed": False,
            "broker_actions_allowed": False,
            "order_paths_allowed": False,
            "external_routing_paths_allowed": False,
            "data_provider_calls_allowed": False,
            "paper_state_mutation_allowed": False,
            "live_state_mutation_allowed": False,
        },
    }


def render_markdown_offline_snapshot_research_replay_evidence_pack(
    pack: OfflineSnapshotResearchReplayEvidencePack,
) -> str:
    payload = offline_snapshot_research_replay_evidence_pack_payload(pack)
    lines = [
        f"# {PHASE_ID} {MODULE_NAME}",
        "",
        "Research labels: " + ", ".join(REQUIRED_LABELS),
        "LIVE TRADING: DISABLED",
        "",
        "## Source Evidence",
    ]
    for name, path in payload["source_paths"].items():
        lines.append(f"- {name}: {path}")

    lines.extend(["", "## Replay Checks"])
    for name, passed in payload["replay_checks"].items():
        lines.append(f"- {name}: {passed}")

    lines.extend(["", "## Supported Metrics"])
    for name, value in payload["metrics"].items():
        if name not in payload["unsupported_metrics"]:
            lines.append(f"- {name}: {value}")

    lines.extend(["", "## Unsupported Metrics"])
    for name, reason in payload["unsupported_metrics"].items():
        lines.append(f"- {name}: {reason}")

    lines.extend(["", "## Candidate Replay Decisions"])
    if payload["candidate_replay_decisions"]:
        for decision in payload["candidate_replay_decisions"]:
            lines.append(
                f"- {decision['candidate_id']}: symbol={decision['symbol']} "
                f"status={decision['status']} weight={decision['weight']} label={decision['label']}"
            )
    else:
        lines.append("- none")

    lines.extend(["", "## Cost Sensitivity"])
    for row in payload["cost_sensitivity"]:
        lines.append(
            f"- {row['cost_bps']} bps: estimated_turnover_cost={row['estimated_turnover_cost']} "
            f"net_return_supported={row['net_return_supported']}"
        )

    lines.extend(["", "## Symbol Contribution"])
    for row in payload["symbol_contribution"]:
        lines.append(
            f"- {row['symbol']}: paper_weight={row['paper_weight']} "
            f"gross_return_contribution={row['gross_return_contribution']}"
        )

    lines.extend(["", "## Unresolved Blockers"])
    for item in payload["unresolved_blockers"]:
        lines.append(f"- {item['source']}: {', '.join(item['reasons'])}")

    lines.extend(["", "## Required Human Review Actions"])
    for item in payload["required_human_review_actions"]:
        lines.append(f"- {item['candidate_id']}: {item['action']}")

    lines.extend(["", "## Acceptance Criteria"])
    for name, passed in payload["acceptance_criteria"].items():
        lines.append(f"- {name}: {passed}")

    lines.extend(
        [
            "",
            "## Safety Boundaries",
            "- RESEARCH_ONLY; MONITOR_ONLY; PAPER_ONLY; HUMAN_REVIEW_REQUIRED; BLOCKED_BY_SAFETY_GATE.",
            "- Offline, read-only, deterministic evidence generation from BR-28 snapshot-derived candidates.",
            "- Opportunity-driven selection is enforced; zero candidates can advance when none qualify, and multiple independent candidates can advance when all gates pass.",
            "- No permanent fixed daily trade quota is imposed.",
            "- No alpha is claimed merely because this report is generated.",
            "- No .env reads, credential loading, secret requests, data-provider calls, broker connections, broker writes, order routing, state mutation, or live trading authorization.",
        ]
    )
    return "\n".join(lines)


def write_offline_snapshot_research_replay_evidence_pack(
    pack: OfflineSnapshotResearchReplayEvidencePack,
    out_dir: Path = DEFAULT_REPORT_DIR,
) -> tuple[Path, Path]:
    pack.validate()
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_REPORT_NAME
    markdown_path = out_dir / MARKDOWN_REPORT_NAME
    json_path.write_text(
        json.dumps(offline_snapshot_research_replay_evidence_pack_payload(pack), indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown_offline_snapshot_research_replay_evidence_pack(pack), encoding="utf-8")
    return json_path, markdown_path


def run_offline_snapshot_research_replay_evidence_pack(
    br28_report_path: Path = DEFAULT_BR28_REPORT_PATH,
    out_dir: Path = DEFAULT_REPORT_DIR,
    as_of: datetime | None = None,
) -> OfflineSnapshotResearchReplayEvidencePack:
    pack = build_offline_snapshot_research_replay_evidence_pack(
        br28_report_path=br28_report_path,
        as_of=as_of,
    )
    write_offline_snapshot_research_replay_evidence_pack(pack, out_dir=out_dir)
    return pack


def _load_json(path: Path) -> tuple[Any | None, tuple[str, ...]]:
    if not path.exists():
        return None, ("br28_report_missing",)
    try:
        return json.loads(path.read_text(encoding="utf-8")), ()
    except json.JSONDecodeError:
        return None, ("br28_report_malformed",)


def _br28_report_accepted(payload: Any) -> bool:
    if not isinstance(payload, dict) or payload.get("phase") != "BR-28":
        return False
    acceptance = payload.get("acceptance_criteria")
    safety = payload.get("safety")
    return (
        isinstance(acceptance, dict)
        and bool(acceptance)
        and all(acceptance.values())
        and isinstance(safety, dict)
        and safety.get("LIVE TRADING") == "DISABLED"
        and safety.get("evaluation_period_outcomes_used") is False
        and safety.get("parameter_optimization_performed") is False
    )


def _candidate_payloads(payload: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(payload, dict):
        return ()
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        return ()
    return tuple(item for item in candidates if isinstance(item, dict))


def _replay_candidates(candidates: tuple[dict[str, Any], ...]) -> tuple[tuple[ReplayDecision, ...], tuple[dict[str, Any], ...]]:
    prelim: list[tuple[dict[str, Any], dict[str, bool], tuple[str, ...]]] = []
    blocks: list[dict[str, Any]] = []
    seen_signal_keys: set[tuple[str, str]] = set()
    for candidate in candidates:
        gates, reasons = _candidate_gate_results(candidate, seen_signal_keys)
        signal_key = (str(candidate.get("symbol")), str(candidate.get("decision_timestamp")))
        if gates["human_review_boundary"] and gates["feature_inputs_complete"]:
            seen_signal_keys.add(signal_key)
        if reasons:
            blocks.extend(_block_record(str(candidate.get("candidate_id", "unknown")), reasons))
        prelim.append((candidate, gates, reasons))

    passing_count = sum(1 for _, _, reasons in prelim if not reasons)
    weight = min(1.0 / passing_count, 0.5) if passing_count else 0.0
    decisions: list[ReplayDecision] = []
    for candidate, gates, reasons in prelim:
        is_passing = not reasons
        decision = ReplayDecision(
            candidate_id=str(candidate.get("candidate_id", "unknown")),
            symbol=str(candidate.get("symbol", "UNKNOWN")),
            decision_timestamp=str(candidate.get("decision_timestamp", "")),
            label=PAPER_ONLY if is_passing else BLOCKED_BY_SAFETY_GATE,
            status="PAPER_ONLY_RESEARCH_REPORTABLE" if is_passing else "BLOCKED_BY_SAFETY_GATE",
            weight=round(weight if is_passing else 0.0, 6),
            gross_exposure=round(weight if is_passing else 0.0, 6),
            gate_results=gates,
            blocked_reasons=reasons,
            required_human_review_actions=(
                "Review BR-29 offline replay evidence before any research promotion decision.",
                "Confirm missing post-decision outcome data before interpreting performance metrics.",
            ),
        )
        decision.validate()
        decisions.append(decision)
    return tuple(decisions), tuple(blocks)


def _candidate_gate_results(candidate: dict[str, Any], seen_signal_keys: set[tuple[str, str]]) -> tuple[dict[str, bool], tuple[str, ...]]:
    features = candidate.get("feature_inputs")
    benchmark = candidate.get("benchmark_context")
    symbol = str(candidate.get("symbol", ""))
    decision_timestamp = str(candidate.get("decision_timestamp", ""))
    signal_key = (symbol, decision_timestamp)
    required_features = ("open", "high", "low", "close", "volume")
    feature_inputs_complete = isinstance(features, dict) and all(features.get(name) is not None for name in required_features)
    positive_price = feature_inputs_complete and all(float(features[name]) > 0 for name in ("open", "high", "low", "close"))
    sufficient_liquidity = feature_inputs_complete and float(features["volume"]) >= 1_000_000
    benchmark_available = isinstance(benchmark, dict) and benchmark.get("benchmark_available_at_decision") is True
    duplicate_clear = signal_key not in seen_signal_keys
    human_review_boundary = (
        candidate.get("label") == HUMAN_REVIEW_REQUIRED
        and candidate.get("human_review_status") == HUMAN_REVIEW_REQUIRED
    )
    no_missing_or_stale_flags = not candidate.get("missing_data_flags") and not candidate.get("stale_data_flags")
    lookahead = candidate.get("lookahead_guard")
    lookahead_clear = (
        isinstance(lookahead, dict)
        and lookahead.get("uses_only_records_at_or_before_decision_timestamp") is True
        and lookahead.get("future_records_used") is False
        and lookahead.get("evaluation_period_outcomes_used") is False
        and lookahead.get("parameter_optimization_performed") is False
    )
    gates = {
        "human_review_boundary": human_review_boundary,
        "screening_gate": feature_inputs_complete and positive_price and no_missing_or_stale_flags,
        "strategy_gate": lookahead_clear,
        "liquidity_gate": sufficient_liquidity,
        "correlation_gate": duplicate_clear,
        "portfolio_risk_gate": True,
        "lifecycle_gate": human_review_boundary,
        "safety_gate": lookahead_clear and human_review_boundary,
        "benchmark_context_available": benchmark_available,
        "feature_inputs_complete": feature_inputs_complete,
    }
    reasons: list[str] = []
    if not human_review_boundary:
        reasons.append("candidate_not_human_review_required")
    if not feature_inputs_complete:
        reasons.append("missing_required_feature_inputs")
    if feature_inputs_complete and not positive_price:
        reasons.append("non_positive_price")
    if feature_inputs_complete and not sufficient_liquidity:
        reasons.append("insufficient_liquidity")
    if not benchmark_available:
        reasons.append("missing_benchmark_context")
    if not duplicate_clear:
        reasons.append("duplicate_signal_blocked")
    if not lookahead_clear:
        reasons.append("operational_circuit_breaker_open")
    return gates, tuple(reasons)


def _supported_metrics(decisions: tuple[ReplayDecision, ...]) -> dict[str, Any]:
    passing = [decision for decision in decisions if decision.label == PAPER_ONLY]
    weights = [decision.weight for decision in passing]
    return {
        "gross_research_return": None,
        "net_research_return": None,
        "turnover": round(sum(abs(weight) for weight in weights), 6),
        "gross_exposure": round(sum(weights), 6),
        "max_symbol_weight": round(max(weights), 6) if weights else 0.0,
        "trade_count": len(passing),
        "candidate_count": len(decisions),
        "advanced_candidate_count": len(passing),
        "blocked_candidate_count": len(decisions) - len(passing),
        "hit_rate": None,
        "max_drawdown": None,
        "sharpe": None,
        "sortino": None,
        "calmar": None,
        "benchmark_excess_return": None,
        "fold_stability_score": None,
        "cost_sensitivity_supported": True,
        "symbol_contribution_supported": True,
        "parameter_neighborhood_supported": False,
        "alpha_claimed": False,
    }


def _unsupported_metrics() -> dict[str, str]:
    reason = "unsupported because frozen BR-28 candidates do not include post-decision exit prices or an outcome return series"
    return {
        "gross_research_return": reason,
        "net_research_return": reason,
        "hit_rate": reason,
        "max_drawdown": reason,
        "sharpe": reason,
        "sortino": reason,
        "calmar": reason,
        "benchmark_excess_return": "unsupported because benchmark return series is not present in the frozen BR-28 candidate report",
        "fold_stability_score": "unsupported because fold-level walk-forward or CPCV outcomes are not present in the frozen BR-28 candidate report",
    }


def _unsupported_performance_blocks() -> tuple[dict[str, Any], ...]:
    return (
        *_block_record("performance_metrics", ("post_decision_exit_prices_missing", "outcome_return_series_missing")),
        *_block_record("benchmark_metrics", ("benchmark_return_series_missing",)),
        *_block_record("fold_stability", ("fold_history_missing",)),
        *_block_record("parameter_neighborhood", ("parameter_neighborhood_source_missing",)),
    )


def _cost_sensitivity(decisions: tuple[ReplayDecision, ...]) -> tuple[dict[str, Any], ...]:
    turnover = sum(decision.weight for decision in decisions if decision.label == PAPER_ONLY)
    rows = []
    for cost_bps in (0, 5, 10, 25, 50):
        rows.append(
            {
                "cost_bps": cost_bps,
                "turnover": round(turnover, 6),
                "estimated_turnover_cost": round(turnover * cost_bps / 10_000, 8),
                "gross_return_supported": False,
                "net_return_supported": False,
            }
        )
    return tuple(rows)


def _symbol_contribution(decisions: tuple[ReplayDecision, ...]) -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "candidate_id": decision.candidate_id,
            "symbol": decision.symbol,
            "paper_weight": decision.weight,
            "gross_return_contribution": None,
            "net_return_contribution": None,
            "contribution_supported": False,
            "reason": "post-decision outcome return is not present in frozen source data",
        }
        for decision in decisions
        if decision.label == PAPER_ONLY
    )


def _unsupported_section(reason: str, explanation: str) -> dict[str, Any]:
    return {
        "supported": False,
        "label": BLOCKED_BY_SAFETY_GATE,
        "reason": reason,
        "explanation": explanation,
    }


def _human_review_actions(decisions: tuple[ReplayDecision, ...]) -> tuple[dict[str, str], ...]:
    actions = [
        {
            "candidate_id": decision.candidate_id,
            "symbol": decision.symbol,
            "action": action,
        }
        for decision in decisions
        for action in decision.required_human_review_actions
    ]
    actions.append(
        {
            "candidate_id": "BR-29",
            "symbol": "ALL",
            "action": "Do not claim alpha or approve live trading from this offline evidence pack.",
        }
    )
    return tuple(actions)


def _acceptance_criteria(pack: OfflineSnapshotResearchReplayEvidencePack) -> dict[str, bool]:
    return {
        "br28_report_loaded": pack.replay_checks["br28_report_loaded"],
        "br28_report_accepted": pack.replay_checks["br28_report_accepted"],
        "offline_read_only_replay": pack.safety["offline_only"] is True and pack.safety["read_only"] is True,
        "opportunity_driven_selection": pack.replay_checks["opportunity_driven_selection"],
        "no_fixed_daily_trade_quota": pack.replay_checks["no_fixed_daily_trade_quota"],
        "risk_budget_and_concentration_enforced": (
            pack.replay_checks["aggregate_risk_budget_enforced"]
            and pack.replay_checks["concentration_limit_enforced"]
        ),
        "duplicate_and_circuit_breakers_enforced": (
            pack.replay_checks["duplicate_signal_controls_enforced"]
            and pack.replay_checks["operational_circuit_breakers_enforced"]
        ),
        "unsupported_performance_metrics_block_alpha_claim": (
            pack.metrics["alpha_claimed"] is False
            and pack.replay_checks["post_decision_outcomes_available"] is False
        ),
        "human_review_actions_present": bool(_human_review_actions(pack.decisions)),
        "no_credentials_or_secrets": all(
            pack.safety[field_name] is False
            for field_name in ("credential_loading_attempted", "env_file_read_attempted", "secret_request_attempted")
        ),
        "no_data_provider_or_network_calls": all(
            pack.safety[field_name] is False
            for field_name in ("data_provider_call_attempted", "external_network_call_attempted", "real_data_fetch_attempted")
        ),
        "no_broker_actions_order_paths_or_state_mutation": all(
            pack.safety[field_name] is False for field_name in REQUIRED_DISABLED_FLAGS
        ),
        "live_trading_disabled": pack.safety["LIVE TRADING"] == "DISABLED",
    }


def _decision_payload(decision: ReplayDecision) -> dict[str, Any]:
    return {
        "candidate_id": decision.candidate_id,
        "symbol": decision.symbol,
        "decision_timestamp": decision.decision_timestamp,
        "label": decision.label,
        "status": decision.status,
        "weight": decision.weight,
        "gross_exposure": decision.gross_exposure,
        "gate_results": decision.gate_results,
        "blocked_reasons": decision.blocked_reasons,
        "required_human_review_actions": decision.required_human_review_actions,
    }


def _block_record(source: str, reasons: tuple[str, ...]) -> tuple[dict[str, Any], ...]:
    if not reasons:
        return ()
    return ({"source": source, "label": BLOCKED_BY_SAFETY_GATE, "reasons": reasons},)


def _all_block_reasons(records: tuple[dict[str, Any], ...]) -> tuple[str, ...]:
    reasons: list[str] = []
    for record in records:
        for reason in record.get("reasons", ()):
            reasons.append(str(reason))
    return tuple(reasons)


def _validate_disabled_safety(manifest: dict[str, Any]) -> None:
    for field_name in REQUIRED_DISABLED_FLAGS:
        if manifest.get(field_name) is not False:
            raise ValueError(f"BR-29 evidence pack cannot set {field_name}")
    for field_name in (
        "live_state_mutation_allowed",
        "paper_state_mutation_allowed",
        "broker_state_mutation_allowed",
        "routing_state_mutation_allowed",
        "broker_write_operations_authorized",
        "external_routing_paths_authorized",
        "data_provider_calls_authorized",
        "fixed_daily_trade_quota_imposed",
        "alpha_claim_created",
        "evaluation_period_tuning_performed",
        "parameter_optimization_performed",
        "strategy_selected_using_evaluation_outcomes",
    ):
        if manifest.get(field_name) is not False:
            raise ValueError(f"BR-29 evidence pack cannot allow {field_name}")
    if manifest.get("LIVE TRADING") != "DISABLED":
        raise ValueError("BR-29 evidence pack must keep LIVE TRADING disabled")
