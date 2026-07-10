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


PHASE_ID = "BR-24"
MODULE_NAME = "Consolidated Research Dossier"
DEFAULT_REPORT_DIR = Path("reports/br24_consolidated_research_dossier")
JSON_REPORT_NAME = "consolidated_research_dossier.json"
MARKDOWN_REPORT_NAME = "consolidated_research_dossier.md"
DEFAULT_SOURCE_PATHS = {
    "BR-14": Path(
        "reports/br14_local_paper_research_session_runner/manual_20260709T194500/local_paper_research_session.json"
    ),
    "BR-15": Path("reports/br15_session_evidence_review_gate/session_evidence_review_gate.json"),
    "BR-16": Path("reports/br16_fixture_to_real_data_boundary/fixture_to_real_data_boundary.json"),
    "BR-17": Path("reports/br17_manual_report_review_packet/manual_report_review_packet.json"),
    "BR-18": Path("reports/br18_fixture_scenario_expansion_matrix/fixture_scenario_expansion_matrix.json"),
    "BR-19": Path("reports/br19_historical_replay_evidence_pack/historical_replay_evidence_pack.json"),
    "BR-20": Path("reports/br20_paper_research_decision_journal/paper_research_decision_journal.json"),
    "BR-21": Path("reports/br21_human_review_resolution_ledger/human_review_resolution_ledger.json"),
    "BR-22": Path("reports/br22_paper_outcome_tracker/paper_outcome_tracker.json"),
    "BR-23": Path("reports/br23_promotion_gate_evidence_checklist/promotion_gate_evidence_checklist.json"),
}
REQUIRED_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
DOSSIER_SECTIONS = (
    "source_evidence",
    "candidate_universe",
    "option_chain_quality",
    "contract_scoring",
    "thesis_package_context",
    "risk_gate_outcomes",
    "paper_only_portfolio_records",
    "monitor_observations",
    "manual_review_packet",
    "scenario_matrix",
    "replay_evidence",
    "paper_decision_journal",
    "human_review_resolution_ledger",
    "paper_outcome_tracker",
    "promotion_gate_checklist",
    "unresolved_blockers",
    "required_human_review_actions",
    "acceptance_criteria",
    "immutable_safety_boundaries",
)
REQUIRED_DISABLED_FLAGS = (
    "credential_loading_attempted",
    "env_file_read_attempted",
    "secret_request_attempted",
    "data_provider_call_attempted",
    "external_network_call_attempted",
    "real_data_fetch_attempted",
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
    "live_state_mutation_attempted",
    "live_trading_enabled",
)


@dataclass(frozen=True)
class ConsolidatedResearchDossier:
    as_of: datetime
    source_paths: dict[str, str]
    sections: dict[str, dict[str, Any]]
    unresolved_blockers: tuple[str, ...]
    required_human_review_actions: tuple[str, ...]
    safety: dict[str, Any]
    label: str = HUMAN_REVIEW_REQUIRED

    def validate(self) -> None:
        if self.label != HUMAN_REVIEW_REQUIRED:
            raise ValueError("BR-24 dossier must require human review")
        if set(self.source_paths) != set(DEFAULT_SOURCE_PATHS):
            raise ValueError("BR-24 dossier source paths must cover BR-14 through BR-23")
        if set(self.sections) != set(DOSSIER_SECTIONS):
            raise ValueError("BR-24 dossier must include every required section")
        if not self.unresolved_blockers:
            raise ValueError("BR-24 dossier must preserve unresolved blockers")
        if not self.required_human_review_actions:
            raise ValueError("BR-24 dossier must preserve required human review actions")
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
        "read_only": True,
        "offline_only": True,
        "committed_report_inputs_only": True,
        "deterministic_dossier_records_only": True,
        "source_evidence_read_only": True,
        "live_trading_authorized": False,
        "broker_actions_authorized": False,
        "order_paths_authorized": False,
        "data_provider_calls_authorized": False,
        "paper_state_mutation_allowed": False,
        "trading_state_mutation_allowed": False,
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
        "live_trading_enabled": False,
        "LIVE TRADING": "DISABLED",
    }


def build_consolidated_research_dossier(
    source_paths: dict[str, Path] | None = None,
    as_of: datetime | None = None,
) -> ConsolidatedResearchDossier:
    resolved_paths = source_paths or DEFAULT_SOURCE_PATHS
    source_payloads = {phase: _load_json(path) for phase, path in resolved_paths.items()}
    _validate_source_payloads(source_payloads)
    blockers = _collect_unresolved_blockers(source_payloads)
    actions = _collect_required_human_review_actions(source_payloads)
    dossier = ConsolidatedResearchDossier(
        as_of=as_of or datetime.now(timezone.utc).replace(microsecond=0),
        source_paths={phase: str(path) for phase, path in resolved_paths.items()},
        sections=_build_sections(source_payloads, resolved_paths, blockers, actions),
        unresolved_blockers=blockers,
        required_human_review_actions=actions,
        safety=safety_manifest(),
    )
    dossier.validate()
    return dossier


def consolidated_research_dossier_payload(dossier: ConsolidatedResearchDossier) -> dict[str, Any]:
    dossier.validate()
    acceptance = _dossier_acceptance_criteria(dossier)
    return {
        "phase": PHASE_ID,
        "module": MODULE_NAME,
        "as_of": dossier.as_of.isoformat(),
        "label": dossier.label,
        "source_paths": dossier.source_paths,
        "dossier_sections": DOSSIER_SECTIONS,
        "safety": dossier.safety,
        "metrics": {
            "source_phase_count": len(dossier.source_paths),
            "dossier_section_count": len(dossier.sections),
            "unresolved_blocker_count": len(dossier.unresolved_blockers),
            "required_human_review_action_count": len(dossier.required_human_review_actions),
            "acceptance_criteria_count": len(acceptance),
            "acceptance_criteria_passed_count": sum(1 for passed in acceptance.values() if passed),
        },
        "sections": dossier.sections,
        "unresolved_blockers": dossier.unresolved_blockers,
        "required_human_review_actions": dossier.required_human_review_actions,
        "acceptance_criteria": acceptance,
        "readiness_state": {
            "state": "CONSOLIDATED_RESEARCH_DOSSIER_ONLY",
            "operator_packet_ready": True,
            "manual_review_required": True,
            "ready_for_live_trading": False,
            "broker_actions_allowed": False,
            "order_paths_allowed": False,
            "data_provider_calls_allowed": False,
            "paper_state_mutation_allowed": False,
            "trading_state_mutation_allowed": False,
        },
    }


def render_markdown_consolidated_research_dossier(dossier: ConsolidatedResearchDossier) -> str:
    payload = consolidated_research_dossier_payload(dossier)
    lines = [
        f"# {PHASE_ID} {MODULE_NAME}",
        "",
        "Research labels: " + ", ".join(REQUIRED_LABELS),
        "LIVE TRADING: DISABLED",
        "",
        "## Source Evidence",
    ]
    for phase, path in payload["source_paths"].items():
        section = payload["sections"]["source_evidence"]["phases"][phase]
        lines.append(f"- {phase}: {section['module']} ({path})")

    lines.extend(["", "## Dossier Sections"])
    for section_name in DOSSIER_SECTIONS:
        section = payload["sections"][section_name]
        lines.append(f"- {section_name}: {section['summary']}")

    lines.extend(["", "## Metrics"])
    for name, value in payload["metrics"].items():
        lines.append(f"- {name}: {value}")

    lines.extend(["", "## Unresolved Blockers"])
    for blocker in payload["unresolved_blockers"]:
        lines.append(f"- {blocker}")

    lines.extend(["", "## Required Human Review Actions"])
    for action in payload["required_human_review_actions"]:
        lines.append(f"- {action}")

    lines.extend(["", "## Acceptance Criteria"])
    for name, passed in payload["acceptance_criteria"].items():
        lines.append(f"- {name}: {passed}")

    lines.extend(
        [
            "",
            "## Immutable Safety Boundaries",
            "- RESEARCH_ONLY; MONITOR_ONLY; PAPER_ONLY; HUMAN_REVIEW_REQUIRED; BLOCKED_BY_SAFETY_GATE.",
            "- The dossier is read-only, offline-only, deterministic, and operator-facing.",
            "- No credentials, .env reads, secrets, data-provider calls, broker connections, broker actions, order paths, live state mutation, or live trading enablement.",
            "- Human review is required before any later paper research process; live trading remains disabled.",
        ]
    )
    return "\n".join(lines)


def write_consolidated_research_dossier(
    dossier: ConsolidatedResearchDossier,
    out_dir: Path = DEFAULT_REPORT_DIR,
) -> tuple[Path, Path]:
    dossier.validate()
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_REPORT_NAME
    markdown_path = out_dir / MARKDOWN_REPORT_NAME
    json_path.write_text(
        json.dumps(consolidated_research_dossier_payload(dossier), indent=2, default=str),
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown_consolidated_research_dossier(dossier), encoding="utf-8")
    return json_path, markdown_path


def run_consolidated_research_dossier(
    source_paths: dict[str, Path] | None = None,
    out_dir: Path = DEFAULT_REPORT_DIR,
    as_of: datetime | None = None,
) -> ConsolidatedResearchDossier:
    dossier = build_consolidated_research_dossier(source_paths=source_paths, as_of=as_of)
    write_consolidated_research_dossier(dossier, out_dir=out_dir)
    return dossier


def _build_sections(
    payloads: dict[str, dict[str, Any]],
    source_paths: dict[str, Path],
    blockers: tuple[str, ...],
    actions: tuple[str, ...],
) -> dict[str, dict[str, Any]]:
    br14 = payloads["BR-14"]
    br17 = payloads["BR-17"]
    br18 = payloads["BR-18"]
    br19 = payloads["BR-19"]
    br20 = payloads["BR-20"]
    br21 = payloads["BR-21"]
    br22 = payloads["BR-22"]
    br23 = payloads["BR-23"]
    return {
        "source_evidence": {
            "summary": "BR-14 through BR-23 committed JSON evidence is loaded as read-only source material.",
            "phases": {
                phase: {
                    "module": payloads[phase]["module"],
                    "label": payloads[phase]["label"],
                    "source_path": str(source_paths[phase]),
                    "live_trading": payloads[phase].get("safety", {}).get("LIVE TRADING"),
                }
                for phase in DEFAULT_SOURCE_PATHS
            },
            "label": RESEARCH_ONLY,
        },
        "candidate_universe": {
            "summary": "Candidate universe is summarized from BR-17 manual packet and BR-14 session counts.",
            "source_phase": "BR-17",
            "candidate_count": br14["metrics"]["candidate_count"],
            "evidence": br17["candidate_universe_summary"],
            "label": RESEARCH_ONLY,
        },
        "option_chain_quality": {
            "summary": "Option chain quality evidence is carried forward without provider calls.",
            "source_phase": "BR-17",
            "chain_count": br14["metrics"]["chain_count"],
            "evidence": br17["options_chain_quality_summary"],
            "label": MONITOR_ONLY,
        },
        "contract_scoring": {
            "summary": "Contract scoring evidence is consolidated from the manual packet and replay pack.",
            "source_phase": "BR-19",
            "contract_count": br14["metrics"]["contract_count"],
            "manual_packet": br17["contract_scoring_summary"],
            "replay_pack": br19["contract_scoring"],
            "label": RESEARCH_ONLY,
        },
        "thesis_package_context": {
            "summary": "Thesis context remains research-only and human-review-required.",
            "source_phase": "BR-19",
            "manual_packet": br17["llm_thesis_package_summary"],
            "replay_pack": br19["thesis_context"],
            "label": HUMAN_REVIEW_REQUIRED,
        },
        "risk_gate_outcomes": {
            "summary": "Risk gate outcomes keep stale data, liquidity, and safety rejection evidence explicit.",
            "source_phase": "BR-19",
            "risk_gate_decision_count": br14["metrics"]["risk_gate_decision_count"],
            "replay_pack": br19["risk_gate_outcomes"],
            "journal_categories": br20["decision_categories"],
            "label": BLOCKED_BY_SAFETY_GATE,
        },
        "paper_only_portfolio_records": {
            "summary": "Paper-only portfolio records are retained as evidence and do not mutate state.",
            "source_phase": "BR-22",
            "simulated_paper_fill_count": br14["metrics"]["simulated_paper_fill_count"],
            "paper_position_count": br14["metrics"]["paper_position_count"],
            "manual_packet": br17["paper_portfolio_state"],
            "outcome_tracker": br22["records_by_outcome_classification"],
            "label": PAPER_ONLY,
        },
        "monitor_observations": {
            "summary": "Monitor observations remain monitor-only and offline.",
            "source_phase": "BR-19",
            "monitor_alert_count": br14["metrics"]["monitor_alert_count"],
            "manual_packet": br17["monitor_alert_summary"],
            "replay_pack": br19["monitor_observations"],
            "label": MONITOR_ONLY,
        },
        "manual_review_packet": {
            "summary": "Manual review questions and actions are preserved for operator review.",
            "source_phase": "BR-17",
            "review_questions": br17["review_questions"],
            "required_human_review_actions": br17["required_human_review_actions"],
            "readiness_state": br17["readiness_state"],
            "label": HUMAN_REVIEW_REQUIRED,
        },
        "scenario_matrix": {
            "summary": "Scenario matrix evidence covers fixture, stale-data, liquidity, hold, reject, and review cases.",
            "source_phase": "BR-18",
            "required_scenario_types": br18["required_scenario_types"],
            "metrics": br18["metrics"],
            "stage_status_counts": br18["stage_status_counts"],
            "label": MONITOR_ONLY,
        },
        "replay_evidence": {
            "summary": "Historical replay evidence remains deterministic and fixture-backed.",
            "source_phase": "BR-19",
            "replay_sections": br19["replay_sections"],
            "metrics": br19["metrics"],
            "records": br19["records"],
            "label": RESEARCH_ONLY,
        },
        "paper_decision_journal": {
            "summary": "Paper decision journal captures held, rejected, and review-required outcomes.",
            "source_phase": "BR-20",
            "journal_sections": br20["journal_sections"],
            "metrics": br20["metrics"],
            "records": br20["records"],
            "label": HUMAN_REVIEW_REQUIRED,
        },
        "human_review_resolution_ledger": {
            "summary": "Human review resolution ledger keeps unresolved review evidence visible.",
            "source_phase": "BR-21",
            "resolution_categories": br21["resolution_categories"],
            "metrics": br21["metrics"],
            "records_by_resolution_category": br21["records_by_resolution_category"],
            "label": HUMAN_REVIEW_REQUIRED,
        },
        "paper_outcome_tracker": {
            "summary": "Paper outcome tracker consolidates hypothetical paper outcomes without actions.",
            "source_phase": "BR-22",
            "outcome_classifications": br22["outcome_classifications"],
            "metrics": br22["metrics"],
            "records_by_outcome_classification": br22["records_by_outcome_classification"],
            "label": PAPER_ONLY,
        },
        "promotion_gate_checklist": {
            "summary": "Promotion gate checklist blocks live advancement and permits later review only.",
            "source_phase": "BR-23",
            "required_evidence_categories": br23["required_evidence_categories"],
            "metrics": br23["metrics"],
            "records_by_classification": br23["records_by_classification"],
            "label": BLOCKED_BY_SAFETY_GATE,
        },
        "unresolved_blockers": {
            "summary": "Unresolved blockers are deduplicated from BR-15 through BR-23.",
            "items": blockers,
            "label": BLOCKED_BY_SAFETY_GATE,
        },
        "required_human_review_actions": {
            "summary": "Required human review actions are deduplicated from source evidence.",
            "items": actions,
            "label": HUMAN_REVIEW_REQUIRED,
        },
        "acceptance_criteria": {
            "summary": "Acceptance criteria preserve source pass states and BR-24 dossier checks.",
            "source_acceptance": {
                phase: payloads[phase].get("acceptance_criteria", {}) for phase in DEFAULT_SOURCE_PATHS
            },
            "label": HUMAN_REVIEW_REQUIRED,
        },
        "immutable_safety_boundaries": {
            "summary": "All boundaries keep the dossier offline, read-only, paper-only, and disabled for live trading.",
            "source_safety": {phase: payloads[phase].get("safety", {}) for phase in DEFAULT_SOURCE_PATHS},
            "br24_safety": safety_manifest(),
            "label": BLOCKED_BY_SAFETY_GATE,
        },
    }


def _dossier_acceptance_criteria(dossier: ConsolidatedResearchDossier) -> dict[str, bool]:
    return {
        "source_paths_cover_br14_through_br23": set(dossier.source_paths) == set(DEFAULT_SOURCE_PATHS),
        "all_dossier_sections_present": set(dossier.sections) == set(DOSSIER_SECTIONS),
        "source_evidence_summarized": "source_evidence" in dossier.sections,
        "candidate_universe_summarized": "candidate_universe" in dossier.sections,
        "option_chain_quality_summarized": "option_chain_quality" in dossier.sections,
        "contract_scoring_summarized": "contract_scoring" in dossier.sections,
        "thesis_package_context_summarized": "thesis_package_context" in dossier.sections,
        "risk_gate_outcomes_summarized": "risk_gate_outcomes" in dossier.sections,
        "paper_only_portfolio_records_summarized": "paper_only_portfolio_records" in dossier.sections,
        "monitor_observations_summarized": "monitor_observations" in dossier.sections,
        "manual_review_packet_summarized": "manual_review_packet" in dossier.sections,
        "scenario_matrix_summarized": "scenario_matrix" in dossier.sections,
        "replay_evidence_summarized": "replay_evidence" in dossier.sections,
        "paper_decision_journal_summarized": "paper_decision_journal" in dossier.sections,
        "human_review_resolution_ledger_summarized": "human_review_resolution_ledger" in dossier.sections,
        "paper_outcome_tracker_summarized": "paper_outcome_tracker" in dossier.sections,
        "promotion_gate_checklist_summarized": "promotion_gate_checklist" in dossier.sections,
        "unresolved_blockers_preserved": bool(dossier.unresolved_blockers),
        "required_human_review_actions_preserved": bool(dossier.required_human_review_actions),
        "immutable_safety_boundaries_recorded": "immutable_safety_boundaries" in dossier.sections,
        "no_credentials_or_secrets": all(
            dossier.safety[field_name] is False
            for field_name in ("credential_loading_attempted", "env_file_read_attempted", "secret_request_attempted")
        ),
        "no_data_provider_or_network_calls": all(
            dossier.safety[field_name] is False
            for field_name in ("data_provider_call_attempted", "external_network_call_attempted", "real_data_fetch_attempted")
        ),
        "no_broker_actions_order_paths_or_live_mutation": all(
            dossier.safety[field_name] is False for field_name in REQUIRED_DISABLED_FLAGS
        ),
        "paper_state_not_mutated": dossier.safety["paper_state_mutation_allowed"] is False,
        "trading_state_not_mutated": dossier.safety["trading_state_mutation_allowed"] is False,
        "live_trading_disabled": dossier.safety["LIVE TRADING"] == "DISABLED",
        "human_review_required": dossier.label == HUMAN_REVIEW_REQUIRED,
    }


def _collect_unresolved_blockers(payloads: dict[str, dict[str, Any]]) -> tuple[str, ...]:
    blockers: list[str] = []
    for payload in payloads.values():
        blockers.extend(_as_text_items(payload.get("unresolved_review_items", ())))
        for record in payload.get("records", ()):
            if isinstance(record, dict):
                blockers.extend(_as_text_items(record.get("unresolved_review_items", ())))
                blockers.extend(_as_text_items(record.get("unresolved_blockers", ())))
    return _dedupe(blockers)


def _collect_required_human_review_actions(payloads: dict[str, dict[str, Any]]) -> tuple[str, ...]:
    actions: list[str] = []
    for payload in payloads.values():
        actions.extend(_as_text_items(payload.get("required_human_review_actions", ())))
        for record in payload.get("records", ()):
            if isinstance(record, dict):
                actions.extend(_as_text_items(record.get("required_human_review_actions", ())))
                actions.extend(_as_text_items(record.get("required_follow_up", ())))
    return _dedupe(actions)


def _validate_source_payloads(payloads: dict[str, dict[str, Any]]) -> None:
    if set(payloads) != set(DEFAULT_SOURCE_PATHS):
        raise ValueError("BR-24 source payloads must include BR-14 through BR-23")
    for phase in DEFAULT_SOURCE_PATHS:
        payload = payloads[phase]
        if payload.get("phase") != phase:
            raise ValueError(f"BR-24 source payload phase mismatch for {phase}")
        safety = payload.get("safety", {})
        if safety.get("LIVE TRADING") != "DISABLED":
            raise ValueError(f"BR-24 source payload {phase} must keep LIVE TRADING disabled")
        for field_name in REQUIRED_DISABLED_FLAGS:
            if field_name in safety and safety[field_name] is not False:
                raise ValueError(f"BR-24 source payload {phase} cannot set {field_name}")


def _validate_disabled_safety(manifest: dict[str, Any]) -> None:
    for field_name in REQUIRED_DISABLED_FLAGS:
        if manifest.get(field_name) is not False:
            raise ValueError(f"BR-24 dossier cannot set {field_name}")
    for field_name in (
        "live_trading_authorized",
        "broker_actions_authorized",
        "order_paths_authorized",
        "data_provider_calls_authorized",
        "paper_state_mutation_allowed",
        "trading_state_mutation_allowed",
    ):
        if manifest.get(field_name) is not False:
            raise ValueError(f"BR-24 dossier cannot allow {field_name}")
    if manifest.get("LIVE TRADING") != "DISABLED":
        raise ValueError("BR-24 dossier must keep LIVE TRADING disabled")


def _as_text_items(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [json.dumps(value, sort_keys=True)]
    if isinstance(value, list | tuple):
        return [item for item in (_text_item(item) for item in value) if item]
    return [str(value)]


def _text_item(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("item", "action", "blocker", "reason", "rationale", "description"):
            if key in value:
                return str(value[key])
        return json.dumps(value, sort_keys=True)
    return str(value)


def _dedupe(items: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        normalized = item.strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            deduped.append(normalized)
    return tuple(deduped)


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload
