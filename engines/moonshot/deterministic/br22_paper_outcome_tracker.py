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


PHASE_ID = "BR-22"
MODULE_NAME = "Paper Outcome Tracker"
DEFAULT_REPORT_DIR = Path("reports/br22_paper_outcome_tracker")
JSON_REPORT_NAME = "paper_outcome_tracker.json"
MARKDOWN_REPORT_NAME = "paper_outcome_tracker.md"
DEFAULT_SOURCE_PATHS = {
    "BR-20": Path("reports/br20_paper_research_decision_journal/paper_research_decision_journal.json"),
    "BR-21": Path("reports/br21_human_review_resolution_ledger/human_review_resolution_ledger.json"),
}
REQUIRED_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
OUTCOME_CLASSIFICATIONS = ("paper_held", "rejected", "sent_for_review")
REQUIRED_OUTCOME_FIELDS = (
    "source_evidence",
    "paper_only_entry_state",
    "hypothetical_mark_change",
    "monitoring_observations",
    "thesis_status",
    "risk_gate_status",
    "dashboard_state",
    "outcome_classification",
    "unresolved_review_items",
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
class PaperOutcomeRecord:
    outcome_id: str
    source_journal_id: str
    symbol: str
    label: str
    source_evidence: dict[str, Any]
    paper_only_entry_state: dict[str, Any]
    hypothetical_mark_change: dict[str, Any]
    monitoring_observations: dict[str, Any]
    thesis_status: dict[str, Any]
    risk_gate_status: dict[str, Any]
    dashboard_state: dict[str, Any]
    outcome_classification: str
    unresolved_review_items: tuple[str, ...]
    required_human_review_actions: tuple[str, ...]
    acceptance_criteria: dict[str, bool]

    def validate(self) -> None:
        for field_name, value in (
            ("outcome_id", self.outcome_id),
            ("source_journal_id", self.source_journal_id),
            ("symbol", self.symbol),
            ("outcome_classification", self.outcome_classification),
        ):
            _require_text(field_name, value)
        if self.outcome_classification not in OUTCOME_CLASSIFICATIONS:
            raise ValueError("BR-22 outcome classification must be paper_held, rejected, or sent_for_review")
        if self.label not in REQUIRED_LABELS:
            raise ValueError("BR-22 outcome label must be a required safety label")
        if self.source_evidence.get("label") != RESEARCH_ONLY:
            raise ValueError("BR-22 source evidence must be RESEARCH_ONLY")
        if self.paper_only_entry_state.get("label") != PAPER_ONLY:
            raise ValueError("BR-22 paper entry state must remain PAPER_ONLY")
        if self.hypothetical_mark_change.get("label") != MONITOR_ONLY:
            raise ValueError("BR-22 hypothetical mark changes must remain MONITOR_ONLY")
        if self.monitoring_observations.get("label") != MONITOR_ONLY:
            raise ValueError("BR-22 monitoring observations must remain MONITOR_ONLY")
        if not self.unresolved_review_items:
            raise ValueError("BR-22 outcome records require unresolved review items")
        if not self.required_human_review_actions:
            raise ValueError("BR-22 outcome records require human review actions")
        if not all(self.acceptance_criteria.values()):
            raise ValueError("BR-22 outcome acceptance criteria must pass")


@dataclass(frozen=True)
class PaperOutcomeTracker:
    as_of: datetime
    source_paths: dict[str, str]
    records: tuple[PaperOutcomeRecord, ...]
    safety: dict[str, Any]
    label: str = HUMAN_REVIEW_REQUIRED

    def validate(self) -> None:
        if self.label != HUMAN_REVIEW_REQUIRED:
            raise ValueError("BR-22 tracker must require human review")
        if not self.records:
            raise ValueError("BR-22 tracker requires outcome records")
        outcome_ids = {record.outcome_id for record in self.records}
        if len(outcome_ids) != len(self.records):
            raise ValueError("BR-22 outcome ids must be unique")
        classifications = {record.outcome_classification for record in self.records}
        if classifications != set(OUTCOME_CLASSIFICATIONS):
            raise ValueError("BR-22 tracker must include held, rejected, and sent-for-review outcomes")
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
        "source_evidence_read_only": True,
        "committed_report_inputs_only": True,
        "deterministic_outcome_records_only": True,
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


def build_paper_outcome_tracker(
    source_paths: dict[str, Path] | None = None,
    as_of: datetime | None = None,
) -> PaperOutcomeTracker:
    resolved_paths = source_paths or DEFAULT_SOURCE_PATHS
    source_payloads = {phase: _load_json(path) for phase, path in resolved_paths.items()}
    _validate_source_payloads(source_payloads)
    records = tuple(_build_outcome_records(source_payloads["BR-20"], source_payloads["BR-21"], resolved_paths))
    tracker = PaperOutcomeTracker(
        as_of=as_of or datetime.now(timezone.utc).replace(microsecond=0),
        source_paths={phase: str(path) for phase, path in resolved_paths.items()},
        records=records,
        safety=safety_manifest(),
    )
    tracker.validate()
    return tracker


def paper_outcome_tracker_payload(tracker: PaperOutcomeTracker) -> dict[str, Any]:
    tracker.validate()
    records = tuple(_record_payload(record) for record in tracker.records)
    return {
        "phase": PHASE_ID,
        "module": MODULE_NAME,
        "as_of": tracker.as_of.isoformat(),
        "label": tracker.label,
        "source_paths": tracker.source_paths,
        "outcome_classifications": OUTCOME_CLASSIFICATIONS,
        "required_outcome_fields": REQUIRED_OUTCOME_FIELDS,
        "safety": tracker.safety,
        "metrics": {
            "outcome_record_count": len(records),
            "paper_held_count": _classification_count(records, "paper_held"),
            "rejected_count": _classification_count(records, "rejected"),
            "sent_for_review_count": _classification_count(records, "sent_for_review"),
            "paper_entry_state_count": sum(1 for record in records if record["paper_only_entry_state"]["label"] == PAPER_ONLY),
            "hypothetical_mark_change_count": sum(1 for record in records if record["hypothetical_mark_change"]["label"] == MONITOR_ONLY),
            "monitoring_observation_count": sum(1 for record in records if record["monitoring_observations"]["label"] == MONITOR_ONLY),
            "unresolved_review_item_count": sum(len(record["unresolved_review_items"]) for record in records),
            "required_human_review_action_count": sum(len(record["required_human_review_actions"]) for record in records),
        },
        "source_evidence": _source_evidence_index(records),
        "records_by_outcome_classification": {
            classification: tuple(record for record in records if record["outcome_classification"] == classification)
            for classification in OUTCOME_CLASSIFICATIONS
        },
        "records": records,
        "acceptance_criteria": _tracker_acceptance_criteria(tracker),
        "required_human_review_actions": _tracker_human_review_actions(tracker.records),
        "readiness_state": {
            "state": "PAPER_OUTCOME_TRACKING_ONLY",
            "ready_for_live_trading": False,
            "broker_actions_allowed": False,
            "order_paths_allowed": False,
            "paper_state_mutation_allowed": False,
            "trading_state_mutation_allowed": False,
            "manual_review_required": True,
        },
    }


def render_markdown_paper_outcome_tracker(tracker: PaperOutcomeTracker) -> str:
    payload = paper_outcome_tracker_payload(tracker)
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

    lines.extend(["", "## Outcome Records"])
    for record in payload["records"]:
        lines.append(
            f"- {record['outcome_id']}: {record['outcome_classification']} "
            f"symbol={record['symbol']} journal={record['source_journal_id']} "
            f"paper_state={record['paper_only_entry_state']['entry_status']} "
            f"mark_change={record['hypothetical_mark_change']['change_amount']} "
            f"risk={record['risk_gate_status']['status']} "
            f"dashboard={record['dashboard_state']['status']}"
        )

    lines.extend(["", "## Classifications"])
    for classification, records in payload["records_by_outcome_classification"].items():
        lines.append(f"- {classification}: {len(records)}")

    lines.extend(["", "## Required Human Review Actions"])
    for item in payload["required_human_review_actions"]:
        lines.append(f"- {item['outcome_id']}: {item['action']}")

    lines.extend(["", "## Acceptance Criteria"])
    for name, passed in payload["acceptance_criteria"].items():
        lines.append(f"- {name}: {passed}")

    lines.extend(
        [
            "",
            "## Safety Boundaries",
            "- RESEARCH_ONLY; MONITOR_ONLY; PAPER_ONLY; HUMAN_REVIEW_REQUIRED; BLOCKED_BY_SAFETY_GATE.",
            "- Offline deterministic outcome records generated from committed BR-20 and BR-21 report evidence only.",
            "- Paper outcome tracking does not mutate paper state, trading state, broker state, order paths, or live-trading controls.",
            "- No credentials, .env reads, secrets, data-provider calls, broker connections, broker actions, order paths, live state mutation, or live trading enablement.",
        ]
    )
    return "\n".join(lines)


def write_paper_outcome_tracker(
    tracker: PaperOutcomeTracker,
    out_dir: Path = DEFAULT_REPORT_DIR,
) -> tuple[Path, Path]:
    tracker.validate()
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_REPORT_NAME
    markdown_path = out_dir / MARKDOWN_REPORT_NAME
    json_path.write_text(json.dumps(paper_outcome_tracker_payload(tracker), indent=2, default=str), encoding="utf-8")
    markdown_path.write_text(render_markdown_paper_outcome_tracker(tracker), encoding="utf-8")
    return json_path, markdown_path


def run_paper_outcome_tracker(
    source_paths: dict[str, Path] | None = None,
    out_dir: Path = DEFAULT_REPORT_DIR,
    as_of: datetime | None = None,
) -> PaperOutcomeTracker:
    tracker = build_paper_outcome_tracker(source_paths=source_paths, as_of=as_of)
    write_paper_outcome_tracker(tracker, out_dir=out_dir)
    return tracker


def _build_outcome_records(
    journal_payload: dict[str, Any],
    ledger_payload: dict[str, Any],
    source_paths: dict[str, Path],
) -> list[PaperOutcomeRecord]:
    ledger_items = _ledger_items_by_journal_id(ledger_payload)
    records: list[PaperOutcomeRecord] = []
    for index, journal_record in enumerate(journal_payload["records"], start=1):
        journal_id = str(journal_record["journal_id"])
        classification = _outcome_classification(journal_record["decision_category"])
        unresolved_items = _unresolved_review_items(journal_record, ledger_items.get(journal_id, ()))
        records.append(
            PaperOutcomeRecord(
                outcome_id=f"BR22-OUTCOME-{index:03d}",
                source_journal_id=journal_id,
                symbol=str(journal_record["symbol"]),
                label=_outcome_label(classification),
                source_evidence=_source_evidence(journal_record, source_paths),
                paper_only_entry_state=_paper_only_entry_state(journal_record),
                hypothetical_mark_change=_hypothetical_mark_change(journal_record),
                monitoring_observations=_monitoring_observations(journal_record),
                thesis_status=_thesis_status(journal_record),
                risk_gate_status=_risk_gate_status(journal_record),
                dashboard_state=_dashboard_state(journal_record),
                outcome_classification=classification,
                unresolved_review_items=unresolved_items,
                required_human_review_actions=tuple(journal_record["required_human_review_actions"]),
                acceptance_criteria=_record_acceptance_criteria(journal_record, unresolved_items),
            )
        )
    return records


def _ledger_items_by_journal_id(ledger_payload: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    grouped: dict[str, list[str]] = {}
    for record in ledger_payload.get("records", ()):
        review_item_id = str(record.get("review_item_id", ""))
        if not review_item_id.startswith("BR20-JOURNAL-"):
            continue
        journal_id = "-".join(review_item_id.split("-")[:3])
        grouped.setdefault(journal_id, []).append(
            f"{record['resolution_id']}:{record['reviewer_decision_category']}:{'; '.join(record['unresolved_blockers'])}"
        )
    return {journal_id: tuple(items) for journal_id, items in grouped.items()}


def _outcome_classification(decision_category: str) -> str:
    if decision_category == "held":
        return "paper_held"
    if decision_category == "rejected":
        return "rejected"
    return "sent_for_review"


def _outcome_label(classification: str) -> str:
    if classification == "paper_held":
        return PAPER_ONLY
    if classification == "rejected":
        return BLOCKED_BY_SAFETY_GATE
    return HUMAN_REVIEW_REQUIRED


def _source_evidence(journal_record: dict[str, Any], source_paths: dict[str, Path]) -> dict[str, Any]:
    return {
        "source_phase": "BR-20",
        "source_path": str(source_paths["BR-20"]),
        "source_journal_id": journal_record["journal_id"],
        "source_replay_id": journal_record["source_replay_id"],
        "source_sections": REQUIRED_OUTCOME_FIELDS,
        "resolution_source_phase": "BR-21",
        "resolution_source_path": str(source_paths["BR-21"]),
        "read_only": True,
        "label": RESEARCH_ONLY,
    }


def _paper_only_entry_state(journal_record: dict[str, Any]) -> dict[str, Any]:
    state = journal_record["paper_only_portfolio_state"]
    quantity_delta = int(state["quantity_delta"])
    premium_delta = float(state["premium_delta"])
    return {
        "entry_status": state["change"],
        "contract_id": state["contract_id"],
        "quantity_delta": quantity_delta,
        "premium_delta": premium_delta,
        "paper_position_open": quantity_delta > 0 or state["change"] == "hold_existing",
        "state_source": state["reason"],
        "label": PAPER_ONLY,
    }


def _hypothetical_mark_change(journal_record: dict[str, Any]) -> dict[str, Any]:
    entry_state = journal_record["paper_only_portfolio_state"]
    monitor = journal_record["monitor_outcomes"]
    contract_score = float(journal_record["contract_scores"]["score"])
    quantity_delta = int(entry_state["quantity_delta"])
    premium_delta = float(entry_state["premium_delta"])
    alert_count = int(monitor["alert_count"])
    score_adjustment = round((contract_score - 75.0) / 100.0, 4)
    alert_adjustment = round(alert_count * -0.05, 4)
    change_amount = round((premium_delta * score_adjustment) + (premium_delta * alert_adjustment), 2)
    if premium_delta == 0.0:
        change_amount = 0.0
    return {
        "method": "deterministic_fixture_proxy",
        "entry_premium": premium_delta,
        "quantity_delta": quantity_delta,
        "score_adjustment": score_adjustment,
        "alert_adjustment": alert_adjustment,
        "change_amount": change_amount,
        "change_percent": round((change_amount / premium_delta) * 100.0, 2) if premium_delta else 0.0,
        "source": "committed_report_fields_only",
        "label": MONITOR_ONLY,
    }


def _monitoring_observations(journal_record: dict[str, Any]) -> dict[str, Any]:
    monitor = journal_record["monitor_outcomes"]
    return {
        "status": monitor["status"],
        "alert_count": monitor["alert_count"],
        "observation": monitor["reason"],
        "dashboard_reference": monitor["dashboard_reference"],
        "label": MONITOR_ONLY,
    }


def _thesis_status(journal_record: dict[str, Any]) -> dict[str, Any]:
    thesis = journal_record["thesis_package_references"]
    return {
        "status": thesis["status"],
        "thesis_id": thesis["thesis_id"],
        "confidence": thesis["confidence"],
        "reason": thesis["reason"],
        "label": HUMAN_REVIEW_REQUIRED,
    }


def _risk_gate_status(journal_record: dict[str, Any]) -> dict[str, Any]:
    risk = journal_record["risk_gate_reasons"]
    return {
        "status": risk["status"],
        "score": risk["score"],
        "reason": risk["reason"],
        "label": risk["label"],
    }


def _dashboard_state(journal_record: dict[str, Any]) -> dict[str, Any]:
    monitor = journal_record["monitor_outcomes"]
    return {
        "status": _dashboard_status(journal_record["decision_category"], monitor["alert_count"]),
        "reference": monitor["dashboard_reference"],
        "monitor_label": MONITOR_ONLY,
        "live_trading_enabled": False,
        "LIVE TRADING": "DISABLED",
    }


def _dashboard_status(decision_category: str, alert_count: int) -> str:
    if decision_category == "rejected":
        return "blocked_alert_visible"
    if decision_category == "sent_for_review":
        return "review_required_visible"
    if alert_count:
        return "paper_hold_alert_visible"
    return "paper_hold_visible"


def _unresolved_review_items(journal_record: dict[str, Any], ledger_items: tuple[str, ...]) -> tuple[str, ...]:
    base_items = tuple(f"BR20_ACTION:{action}" for action in journal_record["required_human_review_actions"])
    return base_items + ledger_items


def _record_acceptance_criteria(journal_record: dict[str, Any], unresolved_items: tuple[str, ...]) -> dict[str, bool]:
    return {
        "source_evidence_recorded": bool(journal_record["journal_id"] and journal_record["source_replay_id"]),
        "paper_only_entry_state_recorded": journal_record["paper_only_portfolio_state"]["label"] == PAPER_ONLY,
        "hypothetical_mark_change_is_monitor_only": True,
        "monitoring_observations_are_monitor_only": journal_record["monitor_outcomes"]["label"] == MONITOR_ONLY,
        "thesis_status_requires_human_review": journal_record["thesis_package_references"]["label"] == HUMAN_REVIEW_REQUIRED,
        "risk_gate_status_recorded": bool(journal_record["risk_gate_reasons"]["status"]),
        "dashboard_state_records_disabled_live_trading": True,
        "outcome_classification_allowed": _outcome_classification(journal_record["decision_category"]) in OUTCOME_CLASSIFICATIONS,
        "unresolved_review_items_recorded": bool(unresolved_items),
        "required_human_review_actions_recorded": bool(journal_record["required_human_review_actions"]),
    }


def _tracker_acceptance_criteria(tracker: PaperOutcomeTracker) -> dict[str, bool]:
    records = tracker.records
    classifications = {record.outcome_classification for record in records}
    return {
        "source_paths_recorded": set(tracker.source_paths) == set(DEFAULT_SOURCE_PATHS),
        "all_outcome_classifications_present": classifications == set(OUTCOME_CLASSIFICATIONS),
        "all_records_have_required_fields": all(
            all(field_name in _record_payload(record) for field_name in REQUIRED_OUTCOME_FIELDS)
            for record in records
        ),
        "paper_entry_states_are_paper_only": all(record.paper_only_entry_state["label"] == PAPER_ONLY for record in records),
        "mark_changes_are_hypothetical_monitor_only": all(record.hypothetical_mark_change["label"] == MONITOR_ONLY for record in records),
        "monitoring_observations_are_monitor_only": all(record.monitoring_observations["label"] == MONITOR_ONLY for record in records),
        "human_review_actions_present": all(record.required_human_review_actions for record in records),
        "unresolved_review_items_present": all(record.unresolved_review_items for record in records),
        "no_credentials_or_secrets": all(
            tracker.safety[field_name] is False
            for field_name in ("credential_loading_attempted", "env_file_read_attempted", "secret_request_attempted")
        ),
        "no_data_provider_or_network_calls": all(
            tracker.safety[field_name] is False
            for field_name in ("data_provider_call_attempted", "external_network_call_attempted", "real_data_fetch_attempted")
        ),
        "no_broker_actions_order_paths_or_live_mutation": all(tracker.safety[field_name] is False for field_name in REQUIRED_DISABLED_FLAGS),
        "paper_state_not_mutated": tracker.safety["paper_state_mutation_allowed"] is False,
        "trading_state_not_mutated": tracker.safety["trading_state_mutation_allowed"] is False,
        "live_trading_disabled": tracker.safety["LIVE TRADING"] == "DISABLED",
        "human_review_required": tracker.label == HUMAN_REVIEW_REQUIRED,
    }


def _record_payload(record: PaperOutcomeRecord) -> dict[str, Any]:
    return {
        "outcome_id": record.outcome_id,
        "source_journal_id": record.source_journal_id,
        "symbol": record.symbol,
        "label": record.label,
        "source_evidence": record.source_evidence,
        "paper_only_entry_state": record.paper_only_entry_state,
        "hypothetical_mark_change": record.hypothetical_mark_change,
        "monitoring_observations": record.monitoring_observations,
        "thesis_status": record.thesis_status,
        "risk_gate_status": record.risk_gate_status,
        "dashboard_state": record.dashboard_state,
        "outcome_classification": record.outcome_classification,
        "unresolved_review_items": record.unresolved_review_items,
        "required_human_review_actions": record.required_human_review_actions,
        "acceptance_criteria": record.acceptance_criteria,
    }


def _source_evidence_index(records: tuple[dict[str, Any], ...]) -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "outcome_id": record["outcome_id"],
            "source_journal_id": record["source_journal_id"],
            "source_path": record["source_evidence"]["source_path"],
            "source_replay_id": record["source_evidence"]["source_replay_id"],
            "resolution_source_path": record["source_evidence"]["resolution_source_path"],
            "label": RESEARCH_ONLY,
        }
        for record in records
    )


def _tracker_human_review_actions(records: tuple[PaperOutcomeRecord, ...]) -> tuple[dict[str, str], ...]:
    return tuple(
        {"outcome_id": record.outcome_id, "source_journal_id": record.source_journal_id, "action": action}
        for record in records
        for action in record.required_human_review_actions
    )


def _classification_count(records: tuple[dict[str, Any], ...], classification: str) -> int:
    return sum(1 for record in records if record["outcome_classification"] == classification)


def _validate_source_payloads(payloads: dict[str, dict[str, Any]]) -> None:
    if set(payloads) != set(DEFAULT_SOURCE_PATHS):
        raise ValueError("BR-22 source payloads must include BR-20 and BR-21")
    if payloads["BR-20"].get("phase") != "BR-20":
        raise ValueError("BR-22 source payload phase mismatch for BR-20")
    if payloads["BR-21"].get("phase") != "BR-21":
        raise ValueError("BR-22 source payload phase mismatch for BR-21")
    for phase, payload in payloads.items():
        safety = payload.get("safety", {})
        if safety.get("LIVE TRADING") != "DISABLED":
            raise ValueError(f"BR-22 source payload {phase} must keep LIVE TRADING disabled")
        for field_name in REQUIRED_DISABLED_FLAGS:
            if field_name in safety and safety[field_name] is not False:
                raise ValueError(f"BR-22 source payload {phase} cannot set {field_name}")


def _validate_disabled_safety(manifest: dict[str, Any]) -> None:
    for field_name in REQUIRED_DISABLED_FLAGS:
        if manifest.get(field_name) is not False:
            raise ValueError(f"BR-22 outcome tracker cannot set {field_name}")
    if manifest.get("paper_state_mutation_allowed") is not False:
        raise ValueError("BR-22 outcome tracker cannot allow paper state mutation")
    if manifest.get("trading_state_mutation_allowed") is not False:
        raise ValueError("BR-22 outcome tracker cannot allow trading state mutation")
    if manifest.get("LIVE TRADING") != "DISABLED":
        raise ValueError("BR-22 outcome tracker must keep LIVE TRADING disabled")


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _require_text(field_name: str, value: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required")
