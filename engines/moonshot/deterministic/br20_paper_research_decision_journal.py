from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from engines.moonshot.deterministic.br19_historical_replay_evidence_pack import (
    DEFAULT_FIXTURE_PATH as DEFAULT_SOURCE_EVIDENCE_PATH,
    REPLAY_SECTIONS,
    HistoricalReplayEvidencePack,
    ReplayRecord,
    build_historical_replay_evidence_pack,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


PHASE_ID = "BR-20"
MODULE_NAME = "Paper Research Decision Journal"
DEFAULT_REPORT_DIR = Path("reports/br20_paper_research_decision_journal")
JSON_REPORT_NAME = "paper_research_decision_journal.json"
MARKDOWN_REPORT_NAME = "paper_research_decision_journal.md"
REQUIRED_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
SAFE_ACTION_LABELS = REQUIRED_LABELS
DECISION_CATEGORIES = ("held", "rejected", "sent_for_review")
REQUIRED_JOURNAL_SECTIONS = (
    "source_evidence",
    "scenario_context",
    "candidate_scores",
    "option_chain_quality",
    "contract_scores",
    "thesis_package_references",
    "risk_gate_reasons",
    "paper_only_portfolio_state",
    "monitor_outcomes",
    "operator_notes",
    "acceptance_criteria",
    "required_human_review_actions",
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
class PaperResearchDecisionRecord:
    journal_id: str
    source_replay_id: str
    decision_category: str
    symbol: str
    label: str
    source_evidence: dict[str, Any]
    scenario_context: dict[str, Any]
    candidate_scores: dict[str, Any]
    option_chain_quality: dict[str, Any]
    contract_scores: dict[str, Any]
    thesis_package_references: dict[str, Any]
    risk_gate_reasons: dict[str, Any]
    paper_only_portfolio_state: dict[str, Any]
    monitor_outcomes: dict[str, Any]
    operator_notes: tuple[str, ...]
    acceptance_criteria: dict[str, bool]
    required_human_review_actions: tuple[str, ...]

    def validate(self) -> None:
        for field_name, value in (
            ("journal_id", self.journal_id),
            ("source_replay_id", self.source_replay_id),
            ("decision_category", self.decision_category),
            ("symbol", self.symbol),
        ):
            _require_text(field_name, value)
        if self.decision_category not in DECISION_CATEGORIES:
            raise ValueError("BR-20 decision category must be held, rejected, or sent_for_review")
        _require_safe_label(self.label)
        if not self.operator_notes:
            raise ValueError("BR-20 journal records require operator notes")
        if not self.required_human_review_actions:
            raise ValueError("BR-20 journal records require human-review actions")
        for section_name in REQUIRED_JOURNAL_SECTIONS:
            section = getattr(self, section_name)
            if section_name in ("operator_notes", "required_human_review_actions"):
                continue
            if not isinstance(section, dict):
                raise ValueError(f"{section_name} must be a JSON object")
        if not all(self.acceptance_criteria.values()):
            raise ValueError("BR-20 journal record acceptance criteria must pass")
        if self.paper_only_portfolio_state.get("label") != PAPER_ONLY:
            raise ValueError("BR-20 portfolio state must remain paper-only")
        if self.monitor_outcomes.get("label") != MONITOR_ONLY:
            raise ValueError("BR-20 monitor outcomes must remain monitor-only")


@dataclass(frozen=True)
class PaperResearchDecisionJournal:
    as_of: datetime
    source_evidence_path: str
    records: tuple[PaperResearchDecisionRecord, ...]
    safety: dict[str, Any]
    label: str = HUMAN_REVIEW_REQUIRED

    def validate(self) -> None:
        if self.label != HUMAN_REVIEW_REQUIRED:
            raise ValueError("BR-20 decision journal must require human review")
        if not self.records:
            raise ValueError("BR-20 decision journal requires records")
        journal_ids = {record.journal_id for record in self.records}
        if len(journal_ids) != len(self.records):
            raise ValueError("BR-20 journal ids must be unique")
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
        "read_only_paper_records": True,
        "source_evidence_read_only": True,
        "deterministic_journal_records_only": True,
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


def build_paper_research_decision_journal(
    source_evidence_path: Path = DEFAULT_SOURCE_EVIDENCE_PATH,
    as_of: datetime | None = None,
) -> PaperResearchDecisionJournal:
    source_pack = build_historical_replay_evidence_pack(fixture_path=source_evidence_path, as_of=as_of)
    return build_paper_research_decision_journal_from_pack(
        source_pack,
        source_evidence_path=source_evidence_path,
        as_of=as_of,
    )


def build_paper_research_decision_journal_from_pack(
    source_pack: HistoricalReplayEvidencePack,
    *,
    source_evidence_path: Path = DEFAULT_SOURCE_EVIDENCE_PATH,
    as_of: datetime | None = None,
) -> PaperResearchDecisionJournal:
    source_pack.validate()
    journal = PaperResearchDecisionJournal(
        as_of=as_of or datetime.now(timezone.utc).replace(microsecond=0),
        source_evidence_path=str(source_evidence_path),
        records=tuple(
            _journal_record_from_replay_record(index, record, source_evidence_path)
            for index, record in enumerate(source_pack.records, start=1)
        ),
        safety=safety_manifest(),
    )
    journal.validate()
    return journal


def paper_research_decision_journal_payload(journal: PaperResearchDecisionJournal) -> dict[str, Any]:
    journal.validate()
    records = tuple(_record_payload(record) for record in journal.records)
    return {
        "phase": PHASE_ID,
        "module": MODULE_NAME,
        "as_of": journal.as_of.isoformat(),
        "label": journal.label,
        "source_evidence_path": journal.source_evidence_path,
        "journal_sections": REQUIRED_JOURNAL_SECTIONS,
        "decision_categories": DECISION_CATEGORIES,
        "safety": journal.safety,
        "metrics": {
            "journal_record_count": len(records),
            "held_count": sum(1 for record in records if record["decision_category"] == "held"),
            "rejected_count": sum(1 for record in records if record["decision_category"] == "rejected"),
            "sent_for_review_count": sum(1 for record in records if record["decision_category"] == "sent_for_review"),
            "paper_only_portfolio_state_count": sum(1 for record in records if record["paper_only_portfolio_state"]["label"] == PAPER_ONLY),
            "monitor_outcome_count": sum(1 for record in records if record["monitor_outcomes"]["label"] == MONITOR_ONLY),
            "human_review_action_count": sum(len(record["required_human_review_actions"]) for record in records),
            "operator_note_count": sum(len(record["operator_notes"]) for record in records),
            "blocked_risk_gate_count": sum(1 for record in records if record["risk_gate_reasons"]["label"] == BLOCKED_BY_SAFETY_GATE),
        },
        "source_evidence": _source_evidence_index(records),
        "held_records": tuple(record for record in records if record["decision_category"] == "held"),
        "rejected_records": tuple(record for record in records if record["decision_category"] == "rejected"),
        "sent_for_review_records": tuple(record for record in records if record["decision_category"] == "sent_for_review"),
        "records": records,
        "acceptance_criteria": _journal_acceptance_criteria(journal),
        "required_human_review_actions": _journal_human_review_actions(journal.records),
        "readiness_state": {
            "state": "HUMAN_REVIEW_REQUIRED_RECORDS_ONLY",
            "ready_for_live_trading": False,
            "broker_actions_allowed": False,
            "manual_review_required": True,
        },
    }


def render_markdown_paper_research_decision_journal(journal: PaperResearchDecisionJournal) -> str:
    payload = paper_research_decision_journal_payload(journal)
    lines = [
        f"# {PHASE_ID} {MODULE_NAME}",
        "",
        "Research labels: " + ", ".join(REQUIRED_LABELS),
        "LIVE TRADING: DISABLED",
        "",
        f"Source evidence: {payload['source_evidence_path']}",
        "",
        "## Metrics",
    ]
    for name, value in payload["metrics"].items():
        lines.append(f"- {name}: {value}")

    lines.extend(["", "## Decision Records"])
    for record in payload["records"]:
        lines.append(
            f"- {record['journal_id']}: {record['decision_category']} symbol={record['symbol']} "
            f"candidate_score={record['candidate_scores']['score']} "
            f"chain_quality={record['option_chain_quality']['chain_quality_score']} "
            f"contract_score={record['contract_scores']['score']} "
            f"risk={record['risk_gate_reasons']['status']}:{record['risk_gate_reasons']['label']} "
            f"monitor={record['monitor_outcomes']['status']}"
        )

    lines.extend(["", "## Held"])
    _extend_category_lines(lines, payload["held_records"])
    lines.extend(["", "## Rejected"])
    _extend_category_lines(lines, payload["rejected_records"])
    lines.extend(["", "## Sent For Review"])
    _extend_category_lines(lines, payload["sent_for_review_records"])

    lines.extend(["", "## Source Evidence"])
    for item in payload["source_evidence"]:
        lines.append(f"- {item['journal_id']}: {item['source_path']}#{item['source_replay_id']} sections={','.join(item['sections'])}")

    lines.extend(["", "## Required Human Review Actions"])
    for item in payload["required_human_review_actions"]:
        lines.append(f"- {item['journal_id']}: {item['action']}")

    lines.extend(["", "## Acceptance Criteria"])
    for name, passed in payload["acceptance_criteria"].items():
        lines.append(f"- {name}: {passed}")

    lines.extend(
        [
            "",
            "## Safety Boundaries",
            "- RESEARCH_ONLY; MONITOR_ONLY; PAPER_ONLY; HUMAN_REVIEW_REQUIRED; BLOCKED_BY_SAFETY_GATE.",
            "- Read-only paper research journal records generated from committed source evidence.",
            "- No credentials, .env reads, secrets, data-provider calls, broker connections, broker actions, order paths, live state mutation, or live trading enablement.",
            "- Paper-only portfolio state is journal evidence and never routed externally.",
        ]
    )
    return "\n".join(lines)


def write_paper_research_decision_journal(
    journal: PaperResearchDecisionJournal,
    out_dir: Path = DEFAULT_REPORT_DIR,
) -> tuple[Path, Path]:
    journal.validate()
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_REPORT_NAME
    markdown_path = out_dir / MARKDOWN_REPORT_NAME
    json_path.write_text(json.dumps(paper_research_decision_journal_payload(journal), indent=2, default=str), encoding="utf-8")
    markdown_path.write_text(render_markdown_paper_research_decision_journal(journal), encoding="utf-8")
    return json_path, markdown_path


def run_paper_research_decision_journal(
    source_evidence_path: Path = DEFAULT_SOURCE_EVIDENCE_PATH,
    out_dir: Path = DEFAULT_REPORT_DIR,
    as_of: datetime | None = None,
) -> PaperResearchDecisionJournal:
    journal = build_paper_research_decision_journal(source_evidence_path=source_evidence_path, as_of=as_of)
    write_paper_research_decision_journal(journal, out_dir=out_dir)
    return journal


def _journal_record_from_replay_record(
    index: int,
    record: ReplayRecord,
    source_evidence_path: Path,
) -> PaperResearchDecisionRecord:
    decision_category = _decision_category(record)
    return PaperResearchDecisionRecord(
        journal_id=f"BR20-JOURNAL-{index:03d}",
        source_replay_id=record.replay_id,
        decision_category=decision_category,
        symbol=record.symbol,
        label=_decision_label(decision_category),
        source_evidence={
            "source_path": str(source_evidence_path),
            "source_phase": "BR-19",
            "source_replay_id": record.replay_id,
            "source_window_id": record.window_id,
            "source_sections": REPLAY_SECTIONS,
            "label": RESEARCH_ONLY,
        },
        scenario_context={
            "scenario_id": record.scenario_id,
            "scenario_type": record.scenario_type,
            "symbol": record.symbol,
            "window_id": record.window_id,
            "label": RESEARCH_ONLY,
        },
        candidate_scores={
            "status": record.candidate_decision["status"],
            "score": record.candidate_decision["score"],
            "reason": record.candidate_decision["reason"],
            "label": record.candidate_decision["label"],
        },
        option_chain_quality={
            "status": record.option_chain_state["status"],
            "chain_quality_score": record.option_chain_state["chain_quality_score"],
            "contract_count": record.option_chain_state["contract_count"],
            "reason": record.option_chain_state["reason"],
            "label": record.option_chain_state["label"],
        },
        contract_scores={
            "status": record.contract_scoring["status"],
            "contract_id": record.contract_scoring["contract_id"],
            "score": record.contract_scoring["score"],
            "reason": record.contract_scoring["reason"],
            "label": record.contract_scoring["label"],
        },
        thesis_package_references={
            "status": record.thesis_context["status"],
            "thesis_id": record.thesis_context["thesis_id"],
            "confidence": record.thesis_context["confidence"],
            "reason": record.thesis_context["reason"],
            "label": record.thesis_context["label"],
        },
        risk_gate_reasons={
            "status": record.risk_gate_outcome["status"],
            "score": record.risk_gate_outcome["score"],
            "reason": record.risk_gate_outcome["reason"],
            "label": record.risk_gate_outcome["label"],
        },
        paper_only_portfolio_state={
            "change": record.paper_portfolio_change["change"],
            "contract_id": record.paper_portfolio_change["contract_id"],
            "quantity_delta": record.paper_portfolio_change["quantity_delta"],
            "premium_delta": record.paper_portfolio_change["premium_delta"],
            "reason": record.paper_portfolio_change["reason"],
            "label": record.paper_portfolio_change["label"],
        },
        monitor_outcomes={
            "status": record.monitor_observation["status"],
            "alert_count": record.monitor_observation["alert_count"],
            "reason": record.monitor_observation["reason"],
            "dashboard_reference": record.dashboard_reference["reference"],
            "label": record.monitor_observation["label"],
        },
        operator_notes=_operator_notes(decision_category, record),
        acceptance_criteria=_record_acceptance_criteria(record),
        required_human_review_actions=tuple(record.human_review_actions),
    )


def _decision_category(record: ReplayRecord) -> str:
    if record.risk_gate_outcome["label"] == PAPER_ONLY:
        return "held"
    if record.risk_gate_outcome["label"] == BLOCKED_BY_SAFETY_GATE:
        return "rejected"
    return "sent_for_review"


def _decision_label(decision_category: str) -> str:
    if decision_category == "held":
        return PAPER_ONLY
    if decision_category == "rejected":
        return BLOCKED_BY_SAFETY_GATE
    return HUMAN_REVIEW_REQUIRED


def _operator_notes(decision_category: str, record: ReplayRecord) -> tuple[str, ...]:
    if decision_category == "held":
        return (
            f"{record.symbol} retained as PAPER_ONLY journal evidence because the risk gate status is {record.risk_gate_outcome['status']}.",
            "Operator must confirm the paper state remains monitor-only and records-only.",
        )
    if decision_category == "rejected":
        return (
            f"{record.symbol} rejected because the risk gate reason is {record.risk_gate_outcome['reason']}.",
            "Operator must keep the blocked record closed unless future approved data-boundary work changes the evidence.",
        )
    return (
        f"{record.symbol} sent for human review because the risk gate status is {record.risk_gate_outcome['status']}.",
        "Operator must close the thesis and evidence questions before any workflow status change.",
    )


def _record_acceptance_criteria(record: ReplayRecord) -> dict[str, bool]:
    return {
        "source_evidence_linked": bool(record.replay_id and record.window_id),
        "scenario_context_present": bool(record.scenario_id and record.scenario_type),
        "candidate_score_present": "score" in record.candidate_decision,
        "option_chain_quality_present": "chain_quality_score" in record.option_chain_state,
        "contract_score_present": "score" in record.contract_scoring,
        "thesis_reference_present": bool(record.thesis_context.get("thesis_id")),
        "risk_gate_reason_present": bool(record.risk_gate_outcome.get("reason")),
        "paper_portfolio_state_is_paper_only": record.paper_portfolio_change.get("label") == PAPER_ONLY,
        "monitor_outcome_is_monitor_only": record.monitor_observation.get("label") == MONITOR_ONLY,
        "human_review_actions_present": bool(record.human_review_actions),
    }


def _journal_acceptance_criteria(journal: PaperResearchDecisionJournal) -> dict[str, bool]:
    return {
        "source_evidence_path_recorded": bool(journal.source_evidence_path),
        "read_only_paper_records": journal.safety["read_only_paper_records"] is True,
        "all_records_have_required_sections": all(
            all(section_name in _record_payload(record) for section_name in REQUIRED_JOURNAL_SECTIONS)
            for record in journal.records
        ),
        "held_rejected_review_categories_present": all(
            any(record.decision_category == category for record in journal.records)
            for category in DECISION_CATEGORIES
        ),
        "paper_portfolio_state_is_paper_only": all(
            record.paper_only_portfolio_state["label"] == PAPER_ONLY
            for record in journal.records
        ),
        "monitor_outcomes_are_monitor_only": all(
            record.monitor_outcomes["label"] == MONITOR_ONLY
            for record in journal.records
        ),
        "human_review_actions_present": all(record.required_human_review_actions for record in journal.records),
        "no_credentials_or_secrets": all(
            journal.safety[field_name] is False
            for field_name in ("credential_loading_attempted", "env_file_read_attempted", "secret_request_attempted")
        ),
        "no_data_provider_or_network_calls": all(
            journal.safety[field_name] is False
            for field_name in ("data_provider_call_attempted", "external_network_call_attempted", "real_data_fetch_attempted")
        ),
        "no_broker_actions_order_paths_or_live_mutation": all(journal.safety[field_name] is False for field_name in REQUIRED_DISABLED_FLAGS),
        "live_trading_disabled": journal.safety["LIVE TRADING"] == "DISABLED",
        "human_review_required": journal.label == HUMAN_REVIEW_REQUIRED,
    }


def _record_payload(record: PaperResearchDecisionRecord) -> dict[str, Any]:
    return {
        "journal_id": record.journal_id,
        "source_replay_id": record.source_replay_id,
        "decision_category": record.decision_category,
        "symbol": record.symbol,
        "label": record.label,
        "source_evidence": record.source_evidence,
        "scenario_context": record.scenario_context,
        "candidate_scores": record.candidate_scores,
        "option_chain_quality": record.option_chain_quality,
        "contract_scores": record.contract_scores,
        "thesis_package_references": record.thesis_package_references,
        "risk_gate_reasons": record.risk_gate_reasons,
        "paper_only_portfolio_state": record.paper_only_portfolio_state,
        "monitor_outcomes": record.monitor_outcomes,
        "operator_notes": record.operator_notes,
        "acceptance_criteria": record.acceptance_criteria,
        "required_human_review_actions": record.required_human_review_actions,
    }


def _source_evidence_index(records: tuple[dict[str, Any], ...]) -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "journal_id": record["journal_id"],
            "source_path": record["source_evidence"]["source_path"],
            "source_replay_id": record["source_replay_id"],
            "sections": record["source_evidence"]["source_sections"],
            "label": RESEARCH_ONLY,
        }
        for record in records
    )


def _journal_human_review_actions(records: tuple[PaperResearchDecisionRecord, ...]) -> tuple[dict[str, str], ...]:
    return tuple(
        {"journal_id": record.journal_id, "action": action}
        for record in records
        for action in record.required_human_review_actions
    )


def _extend_category_lines(lines: list[str], records: tuple[dict[str, Any], ...]) -> None:
    if not records:
        lines.append("- none")
        return
    for record in records:
        lines.append(
            f"- {record['journal_id']}: {record['symbol']} "
            f"contract={record['contract_scores']['contract_id']} "
            f"reason={record['risk_gate_reasons']['reason']}"
        )


def _validate_disabled_safety(manifest: dict[str, Any]) -> None:
    for field_name in REQUIRED_DISABLED_FLAGS:
        if manifest.get(field_name) is not False:
            raise ValueError(f"BR-20 decision journal cannot set {field_name}")
    if manifest.get("LIVE TRADING") != "DISABLED":
        raise ValueError("BR-20 decision journal must keep LIVE TRADING disabled")


def _require_text(field_name: str, value: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required")


def _require_safe_label(label: str) -> None:
    if label not in SAFE_ACTION_LABELS:
        raise ValueError("label must be a safe research, monitor, paper, review, or blocked label")
