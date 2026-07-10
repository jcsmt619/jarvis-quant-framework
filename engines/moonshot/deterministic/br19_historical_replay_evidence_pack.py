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


PHASE_ID = "BR-19"
MODULE_NAME = "Historical Replay Evidence Pack"
DEFAULT_FIXTURE_PATH = Path("engines/moonshot/deterministic/fixtures/br19_historical_replay_evidence_pack.json")
DEFAULT_REPORT_DIR = Path("reports/br19_historical_replay_evidence_pack")
JSON_REPORT_NAME = "historical_replay_evidence_pack.json"
MARKDOWN_REPORT_NAME = "historical_replay_evidence_pack.md"
REQUIRED_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
SAFE_ACTION_LABELS = REQUIRED_LABELS
REPLAY_SECTIONS = (
    "candidate_decision",
    "option_chain_state",
    "contract_scoring",
    "thesis_context",
    "risk_gate_outcome",
    "paper_portfolio_change",
    "monitor_observation",
    "dashboard_reference",
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
class ReplayWindow:
    window_id: str
    replay_date: str
    start: str
    end: str
    market_regime: str
    source_fixture: str

    def validate(self) -> None:
        for field_name, value in (
            ("window_id", self.window_id),
            ("replay_date", self.replay_date),
            ("start", self.start),
            ("end", self.end),
            ("market_regime", self.market_regime),
            ("source_fixture", self.source_fixture),
        ):
            _require_text(field_name, value)


@dataclass(frozen=True)
class ReplayRecord:
    replay_id: str
    window_id: str
    scenario_id: str
    scenario_type: str
    symbol: str
    candidate_decision: dict[str, Any]
    option_chain_state: dict[str, Any]
    contract_scoring: dict[str, Any]
    thesis_context: dict[str, Any]
    risk_gate_outcome: dict[str, Any]
    paper_portfolio_change: dict[str, Any]
    monitor_observation: dict[str, Any]
    dashboard_reference: dict[str, Any]
    unresolved_review_items: tuple[str, ...]
    human_review_actions: tuple[str, ...]

    def validate(self) -> None:
        for field_name, value in (
            ("replay_id", self.replay_id),
            ("window_id", self.window_id),
            ("scenario_id", self.scenario_id),
            ("scenario_type", self.scenario_type),
            ("symbol", self.symbol),
        ):
            _require_text(field_name, value)
        for section_name in REPLAY_SECTIONS:
            section = getattr(self, section_name)
            if not isinstance(section, dict):
                raise ValueError(f"{section_name} must be a JSON object")
            _require_safe_label(str(section.get("label", "")))
        if self.thesis_context.get("label") != HUMAN_REVIEW_REQUIRED:
            raise ValueError("BR-19 thesis context must require human review")
        if self.paper_portfolio_change.get("label") != PAPER_ONLY:
            raise ValueError("BR-19 portfolio changes must be paper-only")
        if self.monitor_observation.get("label") != MONITOR_ONLY:
            raise ValueError("BR-19 monitor observations must be monitor-only")
        if not self.human_review_actions:
            raise ValueError("BR-19 records require human review actions")


@dataclass(frozen=True)
class HistoricalReplayEvidencePack:
    as_of: datetime
    replay_windows: tuple[ReplayWindow, ...]
    records: tuple[ReplayRecord, ...]
    safety: dict[str, Any]
    label: str = HUMAN_REVIEW_REQUIRED

    def validate(self) -> None:
        if self.label != HUMAN_REVIEW_REQUIRED:
            raise ValueError("BR-19 evidence pack must require human review")
        if not self.replay_windows:
            raise ValueError("BR-19 evidence pack requires replay windows")
        if not self.records:
            raise ValueError("BR-19 evidence pack requires replay records")
        window_ids = {window.window_id for window in self.replay_windows}
        if len(window_ids) != len(self.replay_windows):
            raise ValueError("BR-19 replay window ids must be unique")
        replay_ids = {record.replay_id for record in self.records}
        if len(replay_ids) != len(self.records):
            raise ValueError("BR-19 replay ids must be unique")
        for window in self.replay_windows:
            window.validate()
        for record in self.records:
            record.validate()
            if record.window_id not in window_ids:
                raise ValueError(f"BR-19 record references unknown window: {record.window_id}")
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
        "offline_replay_only": True,
        "fixture_only": True,
        "deterministic_replay_records_only": True,
        "historical_style_inputs_committed": True,
        "paper_portfolio_updates_simulated": True,
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


def load_historical_replay_fixture(path: Path = DEFAULT_FIXTURE_PATH) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("BR-19 replay fixture must be a JSON object")
    return payload


def build_historical_replay_evidence_pack(
    fixture_path: Path = DEFAULT_FIXTURE_PATH,
    as_of: datetime | None = None,
) -> HistoricalReplayEvidencePack:
    payload = load_historical_replay_fixture(fixture_path)
    pack = HistoricalReplayEvidencePack(
        as_of=as_of or datetime.now(timezone.utc).replace(microsecond=0),
        replay_windows=tuple(_window_from_payload(item) for item in payload["replay_windows"]),
        records=tuple(_record_from_payload(item) for item in payload["records"]),
        safety=safety_manifest(),
    )
    pack.validate()
    return pack


def historical_replay_evidence_pack_payload(pack: HistoricalReplayEvidencePack) -> dict[str, Any]:
    pack.validate()
    records = tuple(_record_payload(item) for item in pack.records)
    return {
        "phase": PHASE_ID,
        "module": MODULE_NAME,
        "as_of": pack.as_of.isoformat(),
        "label": pack.label,
        "safety": pack.safety,
        "replay_sections": REPLAY_SECTIONS,
        "metrics": {
            "replay_window_count": len(pack.replay_windows),
            "replay_record_count": len(pack.records),
            "paper_only_change_count": sum(1 for item in pack.records if item.paper_portfolio_change.get("change") != "none"),
            "blocked_risk_gate_count": sum(1 for item in pack.records if item.risk_gate_outcome.get("label") == BLOCKED_BY_SAFETY_GATE),
            "human_review_risk_gate_count": sum(1 for item in pack.records if item.risk_gate_outcome.get("label") == HUMAN_REVIEW_REQUIRED),
            "paper_only_risk_gate_count": sum(1 for item in pack.records if item.risk_gate_outcome.get("label") == PAPER_ONLY),
            "monitor_observation_count": len(pack.records),
            "unresolved_review_item_count": sum(len(item.unresolved_review_items) for item in pack.records),
            "human_review_action_count": sum(len(item.human_review_actions) for item in pack.records),
        },
        "replay_windows": [_window_payload(item) for item in pack.replay_windows],
        "scenario_provenance": _scenario_provenance(records),
        "candidate_decisions": [_section_summary(item, "candidate_decision") for item in records],
        "option_chain_state": [_section_summary(item, "option_chain_state") for item in records],
        "contract_scoring": [_section_summary(item, "contract_scoring") for item in records],
        "thesis_context": [_section_summary(item, "thesis_context") for item in records],
        "risk_gate_outcomes": [_section_summary(item, "risk_gate_outcome") for item in records],
        "paper_only_portfolio_changes": [_section_summary(item, "paper_portfolio_change") for item in records],
        "monitor_observations": [_section_summary(item, "monitor_observation") for item in records],
        "dashboard_references": [_section_summary(item, "dashboard_reference") for item in records],
        "records": records,
        "unresolved_review_items": _review_items(pack.records),
        "required_human_review_actions": _human_review_actions(pack.records),
        "acceptance_criteria": _acceptance_criteria(pack),
        "readiness_state": {
            "state": "BLOCKED_BY_SAFETY_GATE_HUMAN_REVIEW_REQUIRED",
            "ready_for_live_trading": False,
            "broker_actions_allowed": False,
            "manual_review_required": True,
        },
    }


def render_markdown_historical_replay_evidence_pack(pack: HistoricalReplayEvidencePack) -> str:
    payload = historical_replay_evidence_pack_payload(pack)
    lines = [
        f"# {PHASE_ID} {MODULE_NAME}",
        "",
        "Research labels: " + ", ".join(REQUIRED_LABELS),
        "LIVE TRADING: DISABLED",
        "",
        "## Replay Windows",
    ]
    for window in payload["replay_windows"]:
        lines.append(
            f"- {window['window_id']}: {window['replay_date']} {window['start']} to {window['end']} "
            f"regime={window['market_regime']} source={window['source_fixture']}"
        )

    lines.extend(["", "## Metrics"])
    for name, value in payload["metrics"].items():
        lines.append(f"- {name}: {value}")

    lines.extend(["", "## Replay Records"])
    for record in payload["records"]:
        lines.append(
            f"- {record['replay_id']}: scenario={record['scenario_type']} symbol={record['symbol']} "
            f"candidate={record['candidate_decision']['status']} "
            f"chain={record['option_chain_state']['status']} "
            f"score={record['contract_scoring']['score']} "
            f"risk={record['risk_gate_outcome']['status']}:{record['risk_gate_outcome']['label']} "
            f"paper_change={record['paper_portfolio_change']['change']} "
            f"monitor={record['monitor_observation']['status']}"
        )

    lines.extend(["", "## Unresolved Review Items"])
    for item in payload["unresolved_review_items"]:
        lines.append(f"- {item['replay_id']}: {item['item']}")

    lines.extend(["", "## Required Human Review Actions"])
    for item in payload["required_human_review_actions"]:
        lines.append(f"- {item['replay_id']}: {item['action']}")

    lines.extend(["", "## Dashboard References"])
    for item in payload["dashboard_references"]:
        lines.append(f"- {item['replay_id']}: {item['reference']} label={item['label']}")

    lines.extend(["", "## Acceptance Criteria"])
    for name, passed in payload["acceptance_criteria"].items():
        lines.append(f"- {name}: {passed}")

    lines.extend(
        [
            "",
            "## Safety Boundaries",
            "- RESEARCH_ONLY; MONITOR_ONLY; PAPER_ONLY; HUMAN_REVIEW_REQUIRED; BLOCKED_BY_SAFETY_GATE.",
            "- Offline replay-only evidence generation from committed fixture inputs.",
            "- No credentials, .env reads, secrets, data-provider calls, broker connections, broker actions, order paths, live state mutation, or live trading enablement.",
            "- Paper-only portfolio changes are simulated evidence records and never routed externally.",
        ]
    )
    return "\n".join(lines)


def write_historical_replay_evidence_pack(
    pack: HistoricalReplayEvidencePack,
    out_dir: Path = DEFAULT_REPORT_DIR,
) -> tuple[Path, Path]:
    pack.validate()
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_REPORT_NAME
    markdown_path = out_dir / MARKDOWN_REPORT_NAME
    json_path.write_text(json.dumps(historical_replay_evidence_pack_payload(pack), indent=2, default=str), encoding="utf-8")
    markdown_path.write_text(render_markdown_historical_replay_evidence_pack(pack), encoding="utf-8")
    return json_path, markdown_path


def run_historical_replay_evidence_pack(
    fixture_path: Path = DEFAULT_FIXTURE_PATH,
    out_dir: Path = DEFAULT_REPORT_DIR,
    as_of: datetime | None = None,
) -> HistoricalReplayEvidencePack:
    pack = build_historical_replay_evidence_pack(fixture_path=fixture_path, as_of=as_of)
    write_historical_replay_evidence_pack(pack, out_dir=out_dir)
    return pack


def _window_from_payload(payload: dict[str, Any]) -> ReplayWindow:
    return ReplayWindow(
        window_id=payload["window_id"],
        replay_date=payload["replay_date"],
        start=payload["start"],
        end=payload["end"],
        market_regime=payload["market_regime"],
        source_fixture=payload["source_fixture"],
    )


def _record_from_payload(payload: dict[str, Any]) -> ReplayRecord:
    return ReplayRecord(
        replay_id=payload["replay_id"],
        window_id=payload["window_id"],
        scenario_id=payload["scenario_id"],
        scenario_type=payload["scenario_type"],
        symbol=payload["symbol"],
        candidate_decision=payload["candidate_decision"],
        option_chain_state=payload["option_chain_state"],
        contract_scoring=payload["contract_scoring"],
        thesis_context=payload["thesis_context"],
        risk_gate_outcome=payload["risk_gate_outcome"],
        paper_portfolio_change=payload["paper_portfolio_change"],
        monitor_observation=payload["monitor_observation"],
        dashboard_reference=payload["dashboard_reference"],
        unresolved_review_items=tuple(payload.get("unresolved_review_items", ())),
        human_review_actions=tuple(payload.get("human_review_actions", ())),
    )


def _window_payload(window: ReplayWindow) -> dict[str, Any]:
    return {
        "window_id": window.window_id,
        "replay_date": window.replay_date,
        "start": window.start,
        "end": window.end,
        "market_regime": window.market_regime,
        "source_fixture": window.source_fixture,
    }


def _record_payload(record: ReplayRecord) -> dict[str, Any]:
    return {
        "replay_id": record.replay_id,
        "window_id": record.window_id,
        "scenario_id": record.scenario_id,
        "scenario_type": record.scenario_type,
        "symbol": record.symbol,
        "candidate_decision": record.candidate_decision,
        "option_chain_state": record.option_chain_state,
        "contract_scoring": record.contract_scoring,
        "thesis_context": record.thesis_context,
        "risk_gate_outcome": record.risk_gate_outcome,
        "paper_portfolio_change": record.paper_portfolio_change,
        "monitor_observation": record.monitor_observation,
        "dashboard_reference": record.dashboard_reference,
        "unresolved_review_items": record.unresolved_review_items,
        "human_review_actions": record.human_review_actions,
    }


def _scenario_provenance(records: tuple[dict[str, Any], ...]) -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "replay_id": item["replay_id"],
            "window_id": item["window_id"],
            "scenario_id": item["scenario_id"],
            "scenario_type": item["scenario_type"],
            "symbol": item["symbol"],
        }
        for item in records
    )


def _section_summary(record: dict[str, Any], section_name: str) -> dict[str, Any]:
    section = record[section_name]
    return {
        "replay_id": record["replay_id"],
        "scenario_id": record["scenario_id"],
        "symbol": record["symbol"],
        **section,
    }


def _review_items(records: tuple[ReplayRecord, ...]) -> tuple[dict[str, str], ...]:
    return tuple(
        {"replay_id": record.replay_id, "item": item}
        for record in records
        for item in record.unresolved_review_items
    )


def _human_review_actions(records: tuple[ReplayRecord, ...]) -> tuple[dict[str, str], ...]:
    return tuple(
        {"replay_id": record.replay_id, "action": action}
        for record in records
        for action in record.human_review_actions
    )


def _acceptance_criteria(pack: HistoricalReplayEvidencePack) -> dict[str, bool]:
    return {
        "fixture_input_exists": DEFAULT_FIXTURE_PATH.exists(),
        "offline_replay_only": pack.safety["offline_replay_only"] is True,
        "all_replay_windows_have_records": all(
            any(record.window_id == window.window_id for record in pack.records)
            for window in pack.replay_windows
        ),
        "all_records_have_required_sections": all(
            all(isinstance(getattr(record, section_name), dict) for section_name in REPLAY_SECTIONS)
            for record in pack.records
        ),
        "portfolio_changes_are_paper_only": all(record.paper_portfolio_change["label"] == PAPER_ONLY for record in pack.records),
        "thesis_context_requires_human_review": all(record.thesis_context["label"] == HUMAN_REVIEW_REQUIRED for record in pack.records),
        "monitoring_is_monitor_only": all(record.monitor_observation["label"] == MONITOR_ONLY for record in pack.records),
        "human_review_actions_present": all(record.human_review_actions for record in pack.records),
        "no_credentials_or_secrets": all(
            pack.safety[field_name] is False
            for field_name in ("credential_loading_attempted", "env_file_read_attempted", "secret_request_attempted")
        ),
        "no_data_provider_or_network_calls": all(
            pack.safety[field_name] is False
            for field_name in ("data_provider_call_attempted", "external_network_call_attempted", "real_data_fetch_attempted")
        ),
        "no_broker_or_order_paths": all(pack.safety[field_name] is False for field_name in REQUIRED_DISABLED_FLAGS),
        "live_trading_disabled": pack.safety["LIVE TRADING"] == "DISABLED",
        "human_review_required": pack.label == HUMAN_REVIEW_REQUIRED,
    }


def _validate_disabled_safety(manifest: dict[str, Any]) -> None:
    for field_name in REQUIRED_DISABLED_FLAGS:
        if manifest.get(field_name) is not False:
            raise ValueError(f"BR-19 evidence pack cannot set {field_name}")
    if manifest.get("LIVE TRADING") != "DISABLED":
        raise ValueError("BR-19 evidence pack must keep LIVE TRADING disabled")


def _require_text(field_name: str, value: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required")


def _require_safe_label(label: str) -> None:
    if label not in SAFE_ACTION_LABELS:
        raise ValueError("label must be a safe research, monitor, paper, review, or blocked label")
