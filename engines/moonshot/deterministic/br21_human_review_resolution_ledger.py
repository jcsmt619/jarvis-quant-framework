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


PHASE_ID = "BR-21"
MODULE_NAME = "Human Review Resolution Ledger"
DEFAULT_REPORT_DIR = Path("reports/br21_human_review_resolution_ledger")
JSON_REPORT_NAME = "human_review_resolution_ledger.json"
MARKDOWN_REPORT_NAME = "human_review_resolution_ledger.md"
DEFAULT_SOURCE_PATHS = {
    "BR-17": Path("reports/br17_manual_report_review_packet/manual_report_review_packet.json"),
    "BR-18": Path("reports/br18_fixture_scenario_expansion_matrix/fixture_scenario_expansion_matrix.json"),
    "BR-19": Path("reports/br19_historical_replay_evidence_pack/historical_replay_evidence_pack.json"),
    "BR-20": Path("reports/br20_paper_research_decision_journal/paper_research_decision_journal.json"),
}
REQUIRED_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
RESOLUTION_CATEGORIES = (
    "keep_blocked",
    "keep_review_required",
    "keep_paper_only",
    "needs_more_evidence",
    "stale_evidence",
    "duplicate_review_item",
)
REQUIRED_LEDGER_FIELDS = (
    "source_evidence",
    "review_item_id",
    "reviewer_decision_category",
    "rationale",
    "evidence_references",
    "unresolved_blockers",
    "required_follow_up",
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
class ReviewResolutionRecord:
    resolution_id: str
    source_phase: str
    source_item_type: str
    review_item_id: str
    reviewer_decision_category: str
    source_evidence: dict[str, Any]
    rationale: str
    evidence_references: tuple[str, ...]
    unresolved_blockers: tuple[str, ...]
    required_follow_up: tuple[str, ...]
    acceptance_criteria: dict[str, bool]
    immutable_safety_boundaries: dict[str, Any]
    label: str = HUMAN_REVIEW_REQUIRED

    def validate(self) -> None:
        for field_name, value in (
            ("resolution_id", self.resolution_id),
            ("source_phase", self.source_phase),
            ("source_item_type", self.source_item_type),
            ("review_item_id", self.review_item_id),
            ("rationale", self.rationale),
        ):
            _require_text(field_name, value)
        if self.source_phase not in DEFAULT_SOURCE_PATHS:
            raise ValueError("BR-21 resolution source phase must be BR-17, BR-18, BR-19, or BR-20")
        if self.reviewer_decision_category not in RESOLUTION_CATEGORIES:
            raise ValueError("BR-21 reviewer decision category is not allowed")
        if self.label != HUMAN_REVIEW_REQUIRED:
            raise ValueError("BR-21 resolution records must remain HUMAN_REVIEW_REQUIRED")
        if not self.evidence_references:
            raise ValueError("BR-21 resolution records require evidence references")
        if not self.unresolved_blockers:
            raise ValueError("BR-21 resolution records require unresolved blockers")
        if not self.required_follow_up:
            raise ValueError("BR-21 resolution records require follow-up")
        if not all(self.acceptance_criteria.values()):
            raise ValueError("BR-21 resolution record acceptance criteria must pass")
        if not self.immutable_safety_boundaries.get("live_trading_disabled"):
            raise ValueError("BR-21 immutable safety boundaries must disable live trading")
        if self.source_evidence.get("label") != RESEARCH_ONLY:
            raise ValueError("BR-21 source evidence must be research-only")


@dataclass(frozen=True)
class HumanReviewResolutionLedger:
    as_of: datetime
    source_paths: dict[str, str]
    records: tuple[ReviewResolutionRecord, ...]
    safety: dict[str, Any]
    label: str = HUMAN_REVIEW_REQUIRED

    def validate(self) -> None:
        if self.label != HUMAN_REVIEW_REQUIRED:
            raise ValueError("BR-21 ledger must require human review")
        if not self.records:
            raise ValueError("BR-21 ledger requires records")
        resolution_ids = {record.resolution_id for record in self.records}
        if len(resolution_ids) != len(self.records):
            raise ValueError("BR-21 resolution ids must be unique")
        source_phases = {record.source_phase for record in self.records}
        if source_phases != set(DEFAULT_SOURCE_PATHS):
            raise ValueError("BR-21 ledger must include BR-17, BR-18, BR-19, and BR-20 source evidence")
        categories = {record.reviewer_decision_category for record in self.records}
        if categories != set(RESOLUTION_CATEGORIES):
            raise ValueError("BR-21 ledger must cover every allowed resolution category")
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
        "deterministic_ledger_records_only": True,
        "source_evidence_read_only": True,
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


def build_human_review_resolution_ledger(
    source_paths: dict[str, Path] | None = None,
    as_of: datetime | None = None,
) -> HumanReviewResolutionLedger:
    resolved_paths = source_paths or DEFAULT_SOURCE_PATHS
    source_payloads = {phase: _load_json(path) for phase, path in resolved_paths.items()}
    _validate_source_payloads(source_payloads)
    records = tuple(_build_records(source_payloads, resolved_paths))
    ledger = HumanReviewResolutionLedger(
        as_of=as_of or datetime.now(timezone.utc).replace(microsecond=0),
        source_paths={phase: str(path) for phase, path in resolved_paths.items()},
        records=records,
        safety=safety_manifest(),
    )
    ledger.validate()
    return ledger


def human_review_resolution_ledger_payload(ledger: HumanReviewResolutionLedger) -> dict[str, Any]:
    ledger.validate()
    records = tuple(_record_payload(record) for record in ledger.records)
    return {
        "phase": PHASE_ID,
        "module": MODULE_NAME,
        "as_of": ledger.as_of.isoformat(),
        "label": ledger.label,
        "source_paths": ledger.source_paths,
        "resolution_categories": RESOLUTION_CATEGORIES,
        "required_ledger_fields": REQUIRED_LEDGER_FIELDS,
        "safety": ledger.safety,
        "metrics": {
            "resolution_record_count": len(records),
            "source_phase_count": len({record["source_phase"] for record in records}),
            "keep_blocked_count": _category_count(records, "keep_blocked"),
            "keep_review_required_count": _category_count(records, "keep_review_required"),
            "keep_paper_only_count": _category_count(records, "keep_paper_only"),
            "needs_more_evidence_count": _category_count(records, "needs_more_evidence"),
            "stale_evidence_count": _category_count(records, "stale_evidence"),
            "duplicate_review_item_count": _category_count(records, "duplicate_review_item"),
            "unresolved_blocker_count": sum(len(record["unresolved_blockers"]) for record in records),
            "required_follow_up_count": sum(len(record["required_follow_up"]) for record in records),
        },
        "source_evidence": _source_evidence_index(records),
        "records_by_resolution_category": {
            category: tuple(record for record in records if record["reviewer_decision_category"] == category)
            for category in RESOLUTION_CATEGORIES
        },
        "records": records,
        "acceptance_criteria": _ledger_acceptance_criteria(ledger),
        "readiness_state": {
            "state": "HUMAN_REVIEW_REQUIRED_LEDGER_ONLY",
            "ready_for_live_trading": False,
            "broker_actions_allowed": False,
            "trading_state_mutation_allowed": False,
            "manual_review_required": True,
        },
    }


def render_markdown_human_review_resolution_ledger(ledger: HumanReviewResolutionLedger) -> str:
    payload = human_review_resolution_ledger_payload(ledger)
    lines = [
        f"# {PHASE_ID} {MODULE_NAME}",
        "",
        "Research labels: " + ", ".join(REQUIRED_LABELS),
        "LIVE TRADING: DISABLED",
        "",
        "## Source Evidence",
    ]
    for phase, path in payload["source_paths"].items():
        lines.append(f"- {phase}: {path}")

    lines.extend(["", "## Metrics"])
    for name, value in payload["metrics"].items():
        lines.append(f"- {name}: {value}")

    lines.extend(["", "## Resolution Records"])
    for record in payload["records"]:
        lines.append(
            f"- {record['resolution_id']}: {record['reviewer_decision_category']} "
            f"{record['source_phase']}#{record['review_item_id']} "
            f"type={record['source_item_type']} label={record['label']}"
        )

    lines.extend(["", "## Categories"])
    for category, records in payload["records_by_resolution_category"].items():
        lines.append(f"- {category}: {len(records)}")

    lines.extend(["", "## Required Follow-Up"])
    for record in payload["records"]:
        for follow_up in record["required_follow_up"]:
            lines.append(f"- {record['resolution_id']}: {follow_up}")

    lines.extend(["", "## Acceptance Criteria"])
    for name, passed in payload["acceptance_criteria"].items():
        lines.append(f"- {name}: {passed}")

    lines.extend(
        [
            "",
            "## Safety Boundaries",
            "- RESEARCH_ONLY; MONITOR_ONLY; PAPER_ONLY; HUMAN_REVIEW_REQUIRED; BLOCKED_BY_SAFETY_GATE.",
            "- Read-only, offline, deterministic ledger records generated from BR-17 through BR-20 report evidence.",
            "- Ledger resolutions do not change trading state, paper state, monitor state, broker state, order paths, or live-trading controls.",
            "- No credentials, .env reads, secrets, data-provider calls, broker connections, broker actions, order paths, live state mutation, or live trading enablement.",
        ]
    )
    return "\n".join(lines)


def write_human_review_resolution_ledger(
    ledger: HumanReviewResolutionLedger,
    out_dir: Path = DEFAULT_REPORT_DIR,
) -> tuple[Path, Path]:
    ledger.validate()
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_REPORT_NAME
    markdown_path = out_dir / MARKDOWN_REPORT_NAME
    json_path.write_text(json.dumps(human_review_resolution_ledger_payload(ledger), indent=2, default=str), encoding="utf-8")
    markdown_path.write_text(render_markdown_human_review_resolution_ledger(ledger), encoding="utf-8")
    return json_path, markdown_path


def run_human_review_resolution_ledger(
    source_paths: dict[str, Path] | None = None,
    out_dir: Path = DEFAULT_REPORT_DIR,
    as_of: datetime | None = None,
) -> HumanReviewResolutionLedger:
    ledger = build_human_review_resolution_ledger(source_paths=source_paths, as_of=as_of)
    write_human_review_resolution_ledger(ledger, out_dir=out_dir)
    return ledger


def _build_records(
    source_payloads: dict[str, dict[str, Any]],
    source_paths: dict[str, Path],
) -> list[ReviewResolutionRecord]:
    records: list[ReviewResolutionRecord] = []
    records.extend(_records_from_br17(source_payloads["BR-17"], source_paths["BR-17"]))
    records.extend(_records_from_br18(source_payloads["BR-18"], source_paths["BR-18"]))
    records.extend(_records_from_br19(source_payloads["BR-19"], source_paths["BR-19"]))
    records.extend(_records_from_br20(source_payloads["BR-20"], source_paths["BR-20"]))
    return [
        ReviewResolutionRecord(
            resolution_id=f"BR21-RESOLUTION-{index:03d}",
            **record,
        )
        for index, record in enumerate(records, start=1)
    ]


def _records_from_br17(payload: dict[str, Any], path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, question in enumerate(payload.get("review_questions", ()), start=1):
        category = _category_from_text(question)
        records.append(
            _record_kwargs(
                source_phase="BR-17",
                source_item_type="review_question",
                review_item_id=f"BR17-QUESTION-{index:03d}",
                category=category,
                source_path=path,
                source_sections=("review_questions", "hold_reject_review_categories", "acceptance_criteria"),
                rationale=f"Close BR-17 review question as {category} using the manual packet evidence without changing state.",
                evidence_references=(f"{path}#review_questions[{index - 1}]", f"{path}#hold_reject_review_categories"),
                blockers=_blockers_for_category(category),
                follow_up=_follow_up_for_category(category),
            )
        )
    return records


def _records_from_br18(payload: dict[str, Any], path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for scenario in payload.get("scenario_outcomes", ()):
        scenario_id = str(scenario.get("scenario_id", "UNKNOWN"))
        scenario_type = str(scenario.get("scenario_type", "unknown"))
        category = _category_from_scenario(scenario)
        records.append(
            _record_kwargs(
                source_phase="BR-18",
                source_item_type="scenario_outcome",
                review_item_id=scenario_id,
                category=category,
                source_path=path,
                source_sections=("scenario_outcomes", "scenarios", "stage_status_counts"),
                rationale=f"Resolve BR-18 {scenario_type} scenario as {category} while preserving fixture-only evidence.",
                evidence_references=(f"{path}#scenario_outcomes[{scenario_id}]", f"{path}#stage_status_counts"),
                blockers=_blockers_for_category(category),
                follow_up=_follow_up_for_category(category),
            )
        )
    return records


def _records_from_br19(payload: dict[str, Any], path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen_replay_ids: set[str] = set()
    for index, item in enumerate(payload.get("unresolved_review_items", ()), start=1):
        replay_id = str(item.get("replay_id", f"BR19-UNKNOWN-{index:03d}"))
        text = str(item.get("item", "unresolved review item"))
        category = "duplicate_review_item" if replay_id in seen_replay_ids else _category_from_text(text)
        seen_replay_ids.add(replay_id)
        records.append(
            _record_kwargs(
                source_phase="BR-19",
                source_item_type="unresolved_review_item",
                review_item_id=f"{replay_id}-ITEM-{index:03d}",
                category=category,
                source_path=path,
                source_sections=("unresolved_review_items", "records", "required_human_review_actions"),
                rationale=f"Resolve BR-19 replay item as {category}; ledger closure is records-only and cannot promote workflow state.",
                evidence_references=(f"{path}#unresolved_review_items[{index - 1}]", f"{path}#records[{replay_id}]"),
                blockers=_blockers_for_category(category),
                follow_up=_follow_up_for_category(category),
            )
        )
    return records


def _records_from_br20(payload: dict[str, Any], path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, item in enumerate(payload.get("required_human_review_actions", ()), start=1):
        journal_id = str(item.get("journal_id", f"BR20-JOURNAL-UNKNOWN-{index:03d}"))
        action = str(item.get("action", "required human review action"))
        category = _category_from_text(action)
        records.append(
            _record_kwargs(
                source_phase="BR-20",
                source_item_type="required_human_review_action",
                review_item_id=f"{journal_id}-ACTION-{index:03d}",
                category=category,
                source_path=path,
                source_sections=("required_human_review_actions", "records", "acceptance_criteria"),
                rationale=f"Close BR-20 required action as {category}; no journal resolution can alter paper or trading state.",
                evidence_references=(f"{path}#required_human_review_actions[{index - 1}]", f"{path}#records[{journal_id}]"),
                blockers=_blockers_for_category(category),
                follow_up=_follow_up_for_category(category),
            )
        )
    return records


def _record_kwargs(
    *,
    source_phase: str,
    source_item_type: str,
    review_item_id: str,
    category: str,
    source_path: Path,
    source_sections: tuple[str, ...],
    rationale: str,
    evidence_references: tuple[str, ...],
    blockers: tuple[str, ...],
    follow_up: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "source_phase": source_phase,
        "source_item_type": source_item_type,
        "review_item_id": review_item_id,
        "reviewer_decision_category": category,
        "source_evidence": {
            "source_phase": source_phase,
            "source_path": str(source_path),
            "source_sections": source_sections,
            "read_only": True,
            "label": RESEARCH_ONLY,
        },
        "rationale": rationale,
        "evidence_references": evidence_references,
        "unresolved_blockers": blockers,
        "required_follow_up": follow_up,
        "acceptance_criteria": {
            "source_evidence_recorded": True,
            "review_item_id_recorded": bool(review_item_id),
            "decision_category_allowed": category in RESOLUTION_CATEGORIES,
            "rationale_recorded": bool(rationale),
            "evidence_references_present": bool(evidence_references),
            "unresolved_blockers_recorded": bool(blockers),
            "required_follow_up_recorded": bool(follow_up),
            "immutable_safety_boundaries_recorded": True,
            "does_not_change_trading_state": True,
        },
        "immutable_safety_boundaries": _immutable_safety_boundaries(),
    }


def _category_from_scenario(scenario: dict[str, Any]) -> str:
    scenario_type = str(scenario.get("scenario_type", ""))
    risk_label = str(scenario.get("risk_gate_label", ""))
    risk_status = str(scenario.get("risk_gate_status", ""))
    if scenario_type == "stale-data":
        return "stale_evidence"
    if scenario_type in {"no-candidate", "thesis-missing"}:
        return "needs_more_evidence"
    if risk_label == PAPER_ONLY or risk_status == "paper_hold":
        return "keep_paper_only"
    if risk_label == BLOCKED_BY_SAFETY_GATE:
        return "keep_blocked"
    return "keep_review_required"


def _category_from_text(text: str) -> str:
    normalized = text.lower()
    if "stale" in normalized:
        return "stale_evidence"
    if "missing" in normalized or "fresh approved data" in normalized or "source fixture" in normalized:
        return "needs_more_evidence"
    if "duplicate" in normalized:
        return "duplicate_review_item"
    if "paper" in normalized or "hold" in normalized:
        return "keep_paper_only"
    if "reject" in normalized or "blocked" in normalized or "disabled" in normalized or "live state" in normalized:
        return "keep_blocked"
    return "keep_review_required"


def _blockers_for_category(category: str) -> tuple[str, ...]:
    return {
        "keep_blocked": ("deterministic safety gate remains unresolved", "no reviewer resolution may promote the item"),
        "keep_review_required": ("trade-relevant evidence still requires human review",),
        "keep_paper_only": ("paper-only status cannot become broker-routed",),
        "needs_more_evidence": ("source evidence is incomplete for final closure",),
        "stale_evidence": ("source evidence is stale and cannot support promotion",),
        "duplicate_review_item": ("duplicate item must reference the primary review record",),
    }[category]


def _follow_up_for_category(category: str) -> tuple[str, ...]:
    return {
        "keep_blocked": ("Record closure as blocked; require new approved evidence before reconsideration.",),
        "keep_review_required": ("Keep item in human-review-required state until a reviewer records a separate evidence-backed decision.",),
        "keep_paper_only": ("Keep paper-only ledger evidence monitor-only and never route it externally.",),
        "needs_more_evidence": ("Collect approved offline evidence in a future phase before changing resolution.",),
        "stale_evidence": ("Refresh evidence only through an approved data-boundary phase; keep current item blocked.",),
        "duplicate_review_item": ("Link duplicate to the primary item and do not create a second workflow action.",),
    }[category]


def _immutable_safety_boundaries() -> dict[str, Any]:
    return {
        "labels": REQUIRED_LABELS,
        "research_only": True,
        "monitor_only": True,
        "paper_only": True,
        "human_review_required": True,
        "blocked_by_safety_gate": True,
        "read_only": True,
        "offline_only": True,
        "trading_state_mutation_allowed": False,
        "broker_actions_allowed": False,
        "order_paths_allowed": False,
        "live_trading_disabled": True,
        "LIVE TRADING": "DISABLED",
    }


def _ledger_acceptance_criteria(ledger: HumanReviewResolutionLedger) -> dict[str, bool]:
    records = ledger.records
    categories = {record.reviewer_decision_category for record in records}
    return {
        "source_paths_recorded": set(ledger.source_paths) == set(DEFAULT_SOURCE_PATHS),
        "all_required_source_phases_present": {record.source_phase for record in records} == set(DEFAULT_SOURCE_PATHS),
        "all_allowed_categories_present": categories == set(RESOLUTION_CATEGORIES),
        "all_records_have_required_fields": all(
            all(field_name in _record_payload(record) for field_name in REQUIRED_LEDGER_FIELDS)
            for record in records
        ),
        "source_evidence_is_read_only": all(record.source_evidence["read_only"] is True for record in records),
        "all_records_require_human_review": all(record.label == HUMAN_REVIEW_REQUIRED for record in records),
        "no_credentials_or_secrets": all(
            ledger.safety[field_name] is False
            for field_name in ("credential_loading_attempted", "env_file_read_attempted", "secret_request_attempted")
        ),
        "no_data_provider_or_network_calls": all(
            ledger.safety[field_name] is False
            for field_name in ("data_provider_call_attempted", "external_network_call_attempted", "real_data_fetch_attempted")
        ),
        "no_broker_actions_order_paths_or_live_mutation": all(ledger.safety[field_name] is False for field_name in REQUIRED_DISABLED_FLAGS),
        "live_trading_disabled": ledger.safety["LIVE TRADING"] == "DISABLED",
        "trading_state_not_mutated": ledger.safety["trading_state_mutation_allowed"] is False,
        "human_review_required": ledger.label == HUMAN_REVIEW_REQUIRED,
    }


def _record_payload(record: ReviewResolutionRecord) -> dict[str, Any]:
    return {
        "resolution_id": record.resolution_id,
        "source_phase": record.source_phase,
        "source_item_type": record.source_item_type,
        "source_evidence": record.source_evidence,
        "review_item_id": record.review_item_id,
        "reviewer_decision_category": record.reviewer_decision_category,
        "rationale": record.rationale,
        "evidence_references": record.evidence_references,
        "unresolved_blockers": record.unresolved_blockers,
        "required_follow_up": record.required_follow_up,
        "acceptance_criteria": record.acceptance_criteria,
        "immutable_safety_boundaries": record.immutable_safety_boundaries,
        "label": record.label,
    }


def _source_evidence_index(records: tuple[dict[str, Any], ...]) -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "resolution_id": record["resolution_id"],
            "source_phase": record["source_phase"],
            "source_path": record["source_evidence"]["source_path"],
            "source_sections": record["source_evidence"]["source_sections"],
            "review_item_id": record["review_item_id"],
            "label": RESEARCH_ONLY,
        }
        for record in records
    )


def _category_count(records: tuple[dict[str, Any], ...], category: str) -> int:
    return sum(1 for record in records if record["reviewer_decision_category"] == category)


def _validate_source_payloads(payloads: dict[str, dict[str, Any]]) -> None:
    if set(payloads) != set(DEFAULT_SOURCE_PATHS):
        raise ValueError("BR-21 source payloads must include BR-17, BR-18, BR-19, and BR-20")
    for phase, payload in payloads.items():
        if payload.get("phase") != phase:
            raise ValueError(f"BR-21 source payload phase mismatch for {phase}")
        safety = payload.get("safety", {})
        if safety.get("LIVE TRADING") != "DISABLED":
            raise ValueError(f"BR-21 source payload {phase} must keep LIVE TRADING disabled")
        for field_name in REQUIRED_DISABLED_FLAGS:
            if field_name in safety and safety[field_name] is not False:
                raise ValueError(f"BR-21 source payload {phase} cannot set {field_name}")


def _validate_disabled_safety(manifest: dict[str, Any]) -> None:
    for field_name in REQUIRED_DISABLED_FLAGS:
        if manifest.get(field_name) is not False:
            raise ValueError(f"BR-21 resolution ledger cannot set {field_name}")
    if manifest.get("trading_state_mutation_allowed") is not False:
        raise ValueError("BR-21 resolution ledger cannot allow trading state mutation")
    if manifest.get("LIVE TRADING") != "DISABLED":
        raise ValueError("BR-21 resolution ledger must keep LIVE TRADING disabled")


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _require_text(field_name: str, value: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required")
