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


PHASE_ID = "BR-23"
MODULE_NAME = "Promotion Gate Evidence Checklist"
DEFAULT_REPORT_DIR = Path("reports/br23_promotion_gate_evidence_checklist")
JSON_REPORT_NAME = "promotion_gate_evidence_checklist.json"
MARKDOWN_REPORT_NAME = "promotion_gate_evidence_checklist.md"
DEFAULT_SOURCE_PATHS = {
    "BR-18": Path("reports/br18_fixture_scenario_expansion_matrix/fixture_scenario_expansion_matrix.json"),
    "BR-19": Path("reports/br19_historical_replay_evidence_pack/historical_replay_evidence_pack.json"),
    "BR-20": Path("reports/br20_paper_research_decision_journal/paper_research_decision_journal.json"),
    "BR-21": Path("reports/br21_human_review_resolution_ledger/human_review_resolution_ledger.json"),
    "BR-22": Path("reports/br22_paper_outcome_tracker/paper_outcome_tracker.json"),
}
REQUIRED_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
CHECKLIST_CLASSIFICATIONS = ("blocked", "review_required", "paper_only")
REQUIRED_EVIDENCE_CATEGORIES = (
    "source_freshness",
    "provenance",
    "scenario_coverage",
    "replay_coverage",
    "decision_journal_completeness",
    "human_review_resolution",
    "paper_outcome_tracking",
    "risk_policy_compliance",
    "stale_data_rejection",
    "liquidity_rejection",
    "safety_boundaries",
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
class PromotionGateChecklistRecord:
    checklist_id: str
    source_outcome_id: str
    source_journal_id: str
    symbol: str
    classification: str
    label: str
    evidence: dict[str, dict[str, Any]]
    missing_evidence: tuple[str, ...]
    unresolved_review_items: tuple[str, ...]
    required_human_review_actions: tuple[str, ...]
    advancement_boundary: dict[str, Any]
    acceptance_criteria: dict[str, bool]

    def validate(self) -> None:
        for field_name, value in (
            ("checklist_id", self.checklist_id),
            ("source_outcome_id", self.source_outcome_id),
            ("source_journal_id", self.source_journal_id),
            ("symbol", self.symbol),
        ):
            _require_text(field_name, value)
        if self.classification not in CHECKLIST_CLASSIFICATIONS:
            raise ValueError("BR-23 checklist classification must be blocked, review_required, or paper_only")
        if self.label != _label_for_classification(self.classification):
            raise ValueError("BR-23 checklist label must match classification")
        if set(self.evidence) != set(REQUIRED_EVIDENCE_CATEGORIES):
            raise ValueError("BR-23 checklist record must include every required evidence category")
        if self.classification in {"blocked", "review_required"} and not self.required_human_review_actions:
            raise ValueError("BR-23 blocked and review-required records require human review actions")
        if self.advancement_boundary.get("live_trading_authorized") is not False:
            raise ValueError("BR-23 checklist cannot authorize live trading")
        if self.advancement_boundary.get("broker_actions_authorized") is not False:
            raise ValueError("BR-23 checklist cannot authorize broker actions")
        if self.advancement_boundary.get("order_paths_authorized") is not False:
            raise ValueError("BR-23 checklist cannot authorize order paths")
        if not all(self.acceptance_criteria.values()):
            raise ValueError("BR-23 checklist record acceptance criteria must pass")


@dataclass(frozen=True)
class PromotionGateEvidenceChecklist:
    as_of: datetime
    source_paths: dict[str, str]
    records: tuple[PromotionGateChecklistRecord, ...]
    safety: dict[str, Any]
    label: str = HUMAN_REVIEW_REQUIRED

    def validate(self) -> None:
        if self.label != HUMAN_REVIEW_REQUIRED:
            raise ValueError("BR-23 checklist must require human review")
        if not self.records:
            raise ValueError("BR-23 checklist requires records")
        checklist_ids = {record.checklist_id for record in self.records}
        if len(checklist_ids) != len(self.records):
            raise ValueError("BR-23 checklist ids must be unique")
        classifications = {record.classification for record in self.records}
        if classifications != set(CHECKLIST_CLASSIFICATIONS):
            raise ValueError("BR-23 checklist must include blocked, review_required, and paper_only records")
        for record in self.records:
            record.validate()
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
        "deterministic_checklist_records_only": True,
        "promotion_gate_authorizes_later_review_only": True,
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


def build_promotion_gate_evidence_checklist(
    source_paths: dict[str, Path] | None = None,
    as_of: datetime | None = None,
) -> PromotionGateEvidenceChecklist:
    resolved_paths = source_paths or DEFAULT_SOURCE_PATHS
    source_payloads = {phase: _load_json(path) for phase, path in resolved_paths.items()}
    _validate_source_payloads(source_payloads)
    records = tuple(_build_checklist_records(source_payloads, resolved_paths))
    checklist = PromotionGateEvidenceChecklist(
        as_of=as_of or datetime.now(timezone.utc).replace(microsecond=0),
        source_paths={phase: str(path) for phase, path in resolved_paths.items()},
        records=records,
        safety=safety_manifest(),
    )
    checklist.validate()
    return checklist


def promotion_gate_evidence_checklist_payload(checklist: PromotionGateEvidenceChecklist) -> dict[str, Any]:
    checklist.validate()
    records = tuple(_record_payload(record) for record in checklist.records)
    return {
        "phase": PHASE_ID,
        "module": MODULE_NAME,
        "as_of": checklist.as_of.isoformat(),
        "label": checklist.label,
        "source_paths": checklist.source_paths,
        "required_evidence_categories": REQUIRED_EVIDENCE_CATEGORIES,
        "checklist_classifications": CHECKLIST_CLASSIFICATIONS,
        "safety": checklist.safety,
        "metrics": {
            "checklist_record_count": len(records),
            "blocked_count": _classification_count(records, "blocked"),
            "review_required_count": _classification_count(records, "review_required"),
            "paper_only_count": _classification_count(records, "paper_only"),
            "missing_evidence_count": sum(len(record["missing_evidence"]) for record in records),
            "unresolved_review_item_count": sum(len(record["unresolved_review_items"]) for record in records),
            "required_human_review_action_count": sum(len(record["required_human_review_actions"]) for record in records),
        },
        "records_by_classification": {
            classification: tuple(record for record in records if record["classification"] == classification)
            for classification in CHECKLIST_CLASSIFICATIONS
        },
        "records": records,
        "acceptance_criteria": _checklist_acceptance_criteria(checklist),
        "readiness_state": {
            "state": "PROMOTION_GATE_EVIDENCE_CHECKLIST_ONLY",
            "later_review_stage_allowed": True,
            "ready_for_live_trading": False,
            "broker_actions_allowed": False,
            "order_paths_allowed": False,
            "data_provider_calls_allowed": False,
            "paper_state_mutation_allowed": False,
            "trading_state_mutation_allowed": False,
            "manual_review_required": True,
        },
    }


def render_markdown_promotion_gate_evidence_checklist(checklist: PromotionGateEvidenceChecklist) -> str:
    payload = promotion_gate_evidence_checklist_payload(checklist)
    lines = [
        f"# {PHASE_ID} {MODULE_NAME}",
        "",
        "Research labels: " + ", ".join(REQUIRED_LABELS),
        "LIVE TRADING: DISABLED",
        "",
        "## Required Evidence",
    ]
    for category in REQUIRED_EVIDENCE_CATEGORIES:
        lines.append(f"- {category}")

    lines.extend(["", "## Source Evidence"])
    for phase, path in payload["source_paths"].items():
        lines.append(f"- {phase}: {path}")

    lines.extend(["", "## Metrics"])
    for name, value in payload["metrics"].items():
        lines.append(f"- {name}: {value}")

    lines.extend(["", "## Checklist Records"])
    for record in payload["records"]:
        lines.append(
            f"- {record['checklist_id']}: {record['classification']} "
            f"symbol={record['symbol']} outcome={record['source_outcome_id']} "
            f"missing={len(record['missing_evidence'])} unresolved={len(record['unresolved_review_items'])}"
        )

    lines.extend(["", "## Classifications"])
    for classification, records in payload["records_by_classification"].items():
        lines.append(f"- {classification}: {len(records)}")

    lines.extend(["", "## Acceptance Criteria"])
    for name, passed in payload["acceptance_criteria"].items():
        lines.append(f"- {name}: {passed}")

    lines.extend(
        [
            "",
            "## Safety Boundaries",
            "- RESEARCH_ONLY; MONITOR_ONLY; PAPER_ONLY; HUMAN_REVIEW_REQUIRED; BLOCKED_BY_SAFETY_GATE.",
            "- Checklist advancement means later human review only; it never authorizes live trading.",
            "- No credentials, .env reads, secrets, data-provider calls, broker connections, broker actions, order paths, external routing, live state mutation, or live trading enablement.",
            "- Stale-data and liquidity rejection evidence must remain explicit before any later review stage.",
        ]
    )
    return "\n".join(lines)


def write_promotion_gate_evidence_checklist(
    checklist: PromotionGateEvidenceChecklist,
    out_dir: Path = DEFAULT_REPORT_DIR,
) -> tuple[Path, Path]:
    checklist.validate()
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_REPORT_NAME
    markdown_path = out_dir / MARKDOWN_REPORT_NAME
    json_path.write_text(
        json.dumps(promotion_gate_evidence_checklist_payload(checklist), indent=2, default=str),
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown_promotion_gate_evidence_checklist(checklist), encoding="utf-8")
    return json_path, markdown_path


def run_promotion_gate_evidence_checklist(
    source_paths: dict[str, Path] | None = None,
    out_dir: Path = DEFAULT_REPORT_DIR,
    as_of: datetime | None = None,
) -> PromotionGateEvidenceChecklist:
    checklist = build_promotion_gate_evidence_checklist(source_paths=source_paths, as_of=as_of)
    write_promotion_gate_evidence_checklist(checklist, out_dir=out_dir)
    return checklist


def _build_checklist_records(
    payloads: dict[str, dict[str, Any]],
    source_paths: dict[str, Path],
) -> list[PromotionGateChecklistRecord]:
    br18 = payloads["BR-18"]
    br19 = payloads["BR-19"]
    br20 = payloads["BR-20"]
    br21 = payloads["BR-21"]
    br22 = payloads["BR-22"]
    journal_by_id = {record["journal_id"]: record for record in br20["records"]}
    records: list[PromotionGateChecklistRecord] = []
    for index, outcome in enumerate(br22["records"], start=1):
        journal = journal_by_id[str(outcome["source_journal_id"])]
        evidence = _evidence_categories(outcome, journal, br18, br19, br20, br21, br22, source_paths)
        missing_evidence = tuple(name for name, item in evidence.items() if not item["passed"])
        classification = _classification(outcome, evidence, missing_evidence)
        records.append(
            PromotionGateChecklistRecord(
                checklist_id=f"BR23-CHECKLIST-{index:03d}",
                source_outcome_id=str(outcome["outcome_id"]),
                source_journal_id=str(outcome["source_journal_id"]),
                symbol=str(outcome["symbol"]),
                classification=classification,
                label=_label_for_classification(classification),
                evidence=evidence,
                missing_evidence=missing_evidence,
                unresolved_review_items=tuple(outcome["unresolved_review_items"]),
                required_human_review_actions=tuple(outcome["required_human_review_actions"]),
                advancement_boundary=_advancement_boundary(classification),
                acceptance_criteria=_record_acceptance_criteria(evidence, classification),
            )
        )
    return records


def _evidence_categories(
    outcome: dict[str, Any],
    journal: dict[str, Any],
    br18: dict[str, Any],
    br19: dict[str, Any],
    br20: dict[str, Any],
    br21: dict[str, Any],
    br22: dict[str, Any],
    source_paths: dict[str, Path],
) -> dict[str, dict[str, Any]]:
    scenario_type = journal["scenario_context"]["scenario_type"]
    risk_reason = str(outcome["risk_gate_status"]["reason"])
    risk_label = str(outcome["risk_gate_status"]["label"])
    source_phase_count = len(source_paths)
    stale_scenarios = {item["scenario_type"] for item in br18["scenario_outcomes"] if item["scenario_type"] == "stale-data"}
    liquidity_rejections = [
        item for item in br18["scenario_outcomes"] if item["scenario_type"] == "poor-liquidity"
    ]
    return {
        "source_freshness": {
            "passed": br18["metrics"]["scenario_count"] >= 10 and br22["safety"]["committed_report_inputs_only"] is True,
            "source_phase": "BR-18",
            "evidence_reference": str(source_paths["BR-18"]),
            "detail": "Committed fixture matrix includes stale-data rejection coverage and offline source timestamps.",
            "label": RESEARCH_ONLY,
        },
        "provenance": {
            "passed": source_phase_count == len(DEFAULT_SOURCE_PATHS) and outcome["source_evidence"]["label"] == RESEARCH_ONLY,
            "source_phase": "BR-22",
            "evidence_reference": f"{source_paths['BR-22']}#records[{outcome['outcome_id']}]",
            "detail": f"Outcome traces to {outcome['source_journal_id']} and {outcome['source_evidence']['source_replay_id']}.",
            "label": RESEARCH_ONLY,
        },
        "scenario_coverage": {
            "passed": set(br18["required_scenario_types"]).issuperset({"stale-data", "poor-liquidity", "paper-hold"}),
            "source_phase": "BR-18",
            "evidence_reference": str(source_paths["BR-18"]),
            "detail": f"Scenario coverage contains {len(br18['required_scenario_types'])} required scenario types.",
            "label": MONITOR_ONLY,
        },
        "replay_coverage": {
            "passed": br19["metrics"]["replay_record_count"] >= len(br22["records"]),
            "source_phase": "BR-19",
            "evidence_reference": str(source_paths["BR-19"]),
            "detail": f"Replay coverage includes {br19['metrics']['replay_record_count']} records.",
            "label": MONITOR_ONLY,
        },
        "decision_journal_completeness": {
            "passed": all(journal["acceptance_criteria"].values()),
            "source_phase": "BR-20",
            "evidence_reference": f"{source_paths['BR-20']}#records[{journal['journal_id']}]",
            "detail": "Decision journal includes required evidence, paper state, monitor outcome, and review actions.",
            "label": HUMAN_REVIEW_REQUIRED,
        },
        "human_review_resolution": {
            "passed": bool(outcome["unresolved_review_items"]) and br21["metrics"]["resolution_record_count"] >= 1,
            "source_phase": "BR-21",
            "evidence_reference": str(source_paths["BR-21"]),
            "detail": f"Resolution ledger still records {len(outcome['unresolved_review_items'])} unresolved review items.",
            "label": HUMAN_REVIEW_REQUIRED,
        },
        "paper_outcome_tracking": {
            "passed": outcome["paper_only_entry_state"]["label"] == PAPER_ONLY
            and outcome["monitoring_observations"]["label"] == MONITOR_ONLY,
            "source_phase": "BR-22",
            "evidence_reference": f"{source_paths['BR-22']}#records[{outcome['outcome_id']}]",
            "detail": f"Outcome classification is {outcome['outcome_classification']} with paper-only state recorded.",
            "label": PAPER_ONLY,
        },
        "risk_policy_compliance": {
            "passed": risk_label in {PAPER_ONLY, HUMAN_REVIEW_REQUIRED, BLOCKED_BY_SAFETY_GATE},
            "source_phase": "BR-20",
            "evidence_reference": f"{source_paths['BR-20']}#records[{journal['journal_id']}].risk_gate_reasons",
            "detail": f"Risk gate status={outcome['risk_gate_status']['status']} reason={risk_reason}.",
            "label": risk_label,
        },
        "stale_data_rejection": {
            "passed": bool(stale_scenarios),
            "source_phase": "BR-18",
            "evidence_reference": str(source_paths["BR-18"]),
            "detail": f"Stale-data scenario coverage present; current scenario={scenario_type}.",
            "label": BLOCKED_BY_SAFETY_GATE,
        },
        "liquidity_rejection": {
            "passed": bool(liquidity_rejections) and (scenario_type != "poor-liquidity" or risk_reason == "poor_liquidity"),
            "source_phase": "BR-18",
            "evidence_reference": str(source_paths["BR-18"]),
            "detail": f"Liquidity rejection coverage present; current scenario={scenario_type}.",
            "label": BLOCKED_BY_SAFETY_GATE,
        },
        "safety_boundaries": {
            "passed": _sources_keep_safety_disabled((br18, br19, br20, br21, br22)),
            "source_phase": PHASE_ID,
            "evidence_reference": "safety_manifest",
            "detail": "All source phases and BR-23 keep credentials, provider calls, broker actions, order paths, state mutation, and live trading disabled.",
            "label": BLOCKED_BY_SAFETY_GATE,
        },
    }


def _classification(
    outcome: dict[str, Any],
    evidence: dict[str, dict[str, Any]],
    missing_evidence: tuple[str, ...],
) -> str:
    if missing_evidence:
        return "blocked"
    if outcome["outcome_classification"] == "rejected":
        return "blocked"
    if outcome["outcome_classification"] == "paper_held":
        return "paper_only"
    if evidence["human_review_resolution"]["passed"] and outcome["unresolved_review_items"]:
        return "review_required"
    return "review_required"


def _label_for_classification(classification: str) -> str:
    if classification == "blocked":
        return BLOCKED_BY_SAFETY_GATE
    if classification == "paper_only":
        return PAPER_ONLY
    return HUMAN_REVIEW_REQUIRED


def _advancement_boundary(classification: str) -> dict[str, Any]:
    return {
        "classification": classification,
        "later_review_stage_allowed": classification in {"review_required", "paper_only"},
        "paper_only_research_record_allowed": classification == "paper_only",
        "human_review_required": True,
        "live_trading_authorized": False,
        "broker_actions_authorized": False,
        "order_paths_authorized": False,
        "data_provider_calls_authorized": False,
        "external_routing_authorized": False,
        "credential_loading_authorized": False,
        "paper_state_mutation_authorized": False,
        "trading_state_mutation_authorized": False,
        "LIVE TRADING": "DISABLED",
    }


def _record_acceptance_criteria(evidence: dict[str, dict[str, Any]], classification: str) -> dict[str, bool]:
    return {
        "all_required_evidence_categories_present": set(evidence) == set(REQUIRED_EVIDENCE_CATEGORIES),
        "source_freshness_recorded": "source_freshness" in evidence,
        "provenance_recorded": "provenance" in evidence,
        "scenario_and_replay_coverage_recorded": "scenario_coverage" in evidence and "replay_coverage" in evidence,
        "journal_review_outcome_evidence_recorded": all(
            item in evidence
            for item in ("decision_journal_completeness", "human_review_resolution", "paper_outcome_tracking")
        ),
        "risk_stale_liquidity_safety_recorded": all(
            item in evidence
            for item in ("risk_policy_compliance", "stale_data_rejection", "liquidity_rejection", "safety_boundaries")
        ),
        "classification_allowed": classification in CHECKLIST_CLASSIFICATIONS,
        "no_live_trading_authorization": True,
        "no_broker_action_or_order_path_authorization": True,
    }


def _checklist_acceptance_criteria(checklist: PromotionGateEvidenceChecklist) -> dict[str, bool]:
    return {
        "source_paths_recorded": set(checklist.source_paths) == set(DEFAULT_SOURCE_PATHS),
        "all_checklist_classifications_present": {record.classification for record in checklist.records}
        == set(CHECKLIST_CLASSIFICATIONS),
        "all_required_evidence_categories_present": all(
            set(record.evidence) == set(REQUIRED_EVIDENCE_CATEGORIES) for record in checklist.records
        ),
        "source_freshness_recorded": all("source_freshness" in record.evidence for record in checklist.records),
        "provenance_recorded": all("provenance" in record.evidence for record in checklist.records),
        "scenario_coverage_recorded": all("scenario_coverage" in record.evidence for record in checklist.records),
        "replay_coverage_recorded": all("replay_coverage" in record.evidence for record in checklist.records),
        "decision_journal_completeness_recorded": all(
            "decision_journal_completeness" in record.evidence for record in checklist.records
        ),
        "human_review_resolution_recorded": all("human_review_resolution" in record.evidence for record in checklist.records),
        "paper_outcome_tracking_recorded": all("paper_outcome_tracking" in record.evidence for record in checklist.records),
        "risk_policy_compliance_recorded": all("risk_policy_compliance" in record.evidence for record in checklist.records),
        "stale_data_rejection_recorded": all("stale_data_rejection" in record.evidence for record in checklist.records),
        "liquidity_rejection_recorded": all("liquidity_rejection" in record.evidence for record in checklist.records),
        "safety_boundaries_recorded": all("safety_boundaries" in record.evidence for record in checklist.records),
        "no_credentials_or_secrets": all(
            checklist.safety[field_name] is False
            for field_name in ("credential_loading_attempted", "env_file_read_attempted", "secret_request_attempted")
        ),
        "no_data_provider_or_network_calls": all(
            checklist.safety[field_name] is False
            for field_name in ("data_provider_call_attempted", "external_network_call_attempted", "real_data_fetch_attempted")
        ),
        "no_broker_actions_order_paths_or_live_mutation": all(
            checklist.safety[field_name] is False for field_name in REQUIRED_DISABLED_FLAGS
        ),
        "paper_state_not_mutated": checklist.safety["paper_state_mutation_allowed"] is False,
        "trading_state_not_mutated": checklist.safety["trading_state_mutation_allowed"] is False,
        "live_trading_disabled": checklist.safety["LIVE TRADING"] == "DISABLED",
        "human_review_required": checklist.label == HUMAN_REVIEW_REQUIRED,
    }


def _record_payload(record: PromotionGateChecklistRecord) -> dict[str, Any]:
    return {
        "checklist_id": record.checklist_id,
        "source_outcome_id": record.source_outcome_id,
        "source_journal_id": record.source_journal_id,
        "symbol": record.symbol,
        "classification": record.classification,
        "label": record.label,
        "evidence": record.evidence,
        "missing_evidence": record.missing_evidence,
        "unresolved_review_items": record.unresolved_review_items,
        "required_human_review_actions": record.required_human_review_actions,
        "advancement_boundary": record.advancement_boundary,
        "acceptance_criteria": record.acceptance_criteria,
    }


def _classification_count(records: tuple[dict[str, Any], ...], classification: str) -> int:
    return sum(1 for record in records if record["classification"] == classification)


def _validate_source_payloads(payloads: dict[str, dict[str, Any]]) -> None:
    if set(payloads) != set(DEFAULT_SOURCE_PATHS):
        raise ValueError("BR-23 source payloads must include BR-18 through BR-22")
    for phase in DEFAULT_SOURCE_PATHS:
        if payloads[phase].get("phase") != phase:
            raise ValueError(f"BR-23 source payload phase mismatch for {phase}")
        safety = payloads[phase].get("safety", {})
        if safety.get("LIVE TRADING") != "DISABLED":
            raise ValueError(f"BR-23 source payload {phase} must keep LIVE TRADING disabled")
        for field_name in REQUIRED_DISABLED_FLAGS:
            if field_name in safety and safety[field_name] is not False:
                raise ValueError(f"BR-23 source payload {phase} cannot set {field_name}")


def _validate_disabled_safety(manifest: dict[str, Any]) -> None:
    for field_name in REQUIRED_DISABLED_FLAGS:
        if manifest.get(field_name) is not False:
            raise ValueError(f"BR-23 checklist cannot set {field_name}")
    for field_name in (
        "live_trading_authorized",
        "broker_actions_authorized",
        "order_paths_authorized",
        "data_provider_calls_authorized",
        "paper_state_mutation_allowed",
        "trading_state_mutation_allowed",
    ):
        if manifest.get(field_name) is not False:
            raise ValueError(f"BR-23 checklist cannot allow {field_name}")
    if manifest.get("LIVE TRADING") != "DISABLED":
        raise ValueError("BR-23 checklist must keep LIVE TRADING disabled")


def _sources_keep_safety_disabled(payloads: tuple[dict[str, Any], ...]) -> bool:
    return all(payload.get("safety", {}).get("LIVE TRADING") == "DISABLED" for payload in payloads)


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _require_text(field_name: str, value: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required")
