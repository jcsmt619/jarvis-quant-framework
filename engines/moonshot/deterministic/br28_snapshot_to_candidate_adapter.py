from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from engines.moonshot.deterministic.br26_read_only_data_snapshot_import_contract import (
    REQUIRED_DISABLED_FLAGS,
)
from engines.moonshot.deterministic.br27_approved_snapshot_intake_review_gate import (
    DEFAULT_APPROVED_SNAPSHOT_PATH,
    DEFAULT_REPORT_DIR as DEFAULT_BR27_REPORT_DIR,
    JSON_REPORT_NAME as BR27_JSON_REPORT_NAME,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


PHASE_ID = "BR-28"
MODULE_NAME = "Snapshot to Candidate Deterministic Adapter"
STRATEGY_VERSION = "br28.snapshot_to_candidate.v1"
DEFAULT_REPORT_DIR = Path("reports/br28_snapshot_to_candidate_adapter")
JSON_REPORT_NAME = "snapshot_to_candidate_adapter.json"
MARKDOWN_REPORT_NAME = "snapshot_to_candidate_adapter.md"
DEFAULT_BR27_REPORT_PATH = DEFAULT_BR27_REPORT_DIR / BR27_JSON_REPORT_NAME
DEFAULT_SOURCE_PATHS = {
    "BR-27 approved snapshot intake review gate": DEFAULT_BR27_REPORT_PATH,
    "BR-27-reviewed approved offline snapshot": DEFAULT_APPROVED_SNAPSHOT_PATH,
}
REQUIRED_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
ADAPTER_CHECKS = (
    "br27_report_accepted",
    "snapshot_path_matches_br27",
    "snapshot_checksum_matches_br27",
    "offline_snapshot_loaded",
    "records_are_point_in_time",
    "decision_timestamps_not_before_observations",
    "candidate_fields_normalized",
    "no_evaluation_outcomes_used",
    "no_parameter_optimization",
)
BLOCK_REASONS = (
    "br27_report_missing",
    "br27_report_malformed",
    "br27_report_not_accepted",
    "snapshot_path_not_reviewed_by_br27",
    "snapshot_file_missing",
    "snapshot_json_malformed",
    "snapshot_not_object",
    "snapshot_checksum_mismatch",
    "snapshot_records_missing",
    "record_timestamp_invalid",
    "decision_timestamp_before_observation",
    "candidate_normalization_failed",
)


@dataclass(frozen=True)
class ResearchCandidateRecord:
    candidate_id: str
    symbol: str
    label: str
    human_review_status: str
    observation_timestamp: str
    decision_timestamp: str
    source_checksum_sha256: str
    provenance: dict[str, Any]
    strategy_version: str
    feature_inputs: dict[str, Any]
    missing_data_flags: tuple[str, ...]
    stale_data_flags: tuple[str, ...]
    benchmark_context: dict[str, Any]
    lookahead_guard: dict[str, Any]

    def validate(self) -> None:
        if self.label != HUMAN_REVIEW_REQUIRED:
            raise ValueError("BR-28 candidates must remain human-review-required")
        if self.human_review_status != HUMAN_REVIEW_REQUIRED:
            raise ValueError("BR-28 candidates must carry human-review status")
        observation = _parse_datetime(self.observation_timestamp)
        decision = _parse_datetime(self.decision_timestamp)
        if observation is None or decision is None:
            raise ValueError("BR-28 candidate timestamps must be valid")
        if decision < observation:
            raise ValueError("BR-28 decision timestamp cannot precede observation timestamp")
        if self.strategy_version != STRATEGY_VERSION:
            raise ValueError("BR-28 candidate strategy version mismatch")
        if not self.source_checksum_sha256 or len(self.source_checksum_sha256) != 64:
            raise ValueError("BR-28 candidates must preserve source checksum")
        if self.lookahead_guard.get("uses_only_records_at_or_before_decision_timestamp") is not True:
            raise ValueError("BR-28 candidates must prove look-ahead prevention")
        if self.lookahead_guard.get("evaluation_period_outcomes_used") is not False:
            raise ValueError("BR-28 candidates cannot use evaluation-period outcomes")
        if self.lookahead_guard.get("parameter_optimization_performed") is not False:
            raise ValueError("BR-28 candidates cannot optimize parameters")


@dataclass(frozen=True)
class SnapshotToCandidateAdapterResult:
    as_of: datetime
    source_paths: dict[str, str]
    candidates: tuple[ResearchCandidateRecord, ...]
    blocked_records: tuple[dict[str, Any], ...]
    adapter_checks: dict[str, bool]
    safety: dict[str, Any]
    label: str = HUMAN_REVIEW_REQUIRED

    def validate(self) -> None:
        if self.label != HUMAN_REVIEW_REQUIRED:
            raise ValueError("BR-28 adapter must require human review")
        if set(self.source_paths) != set(DEFAULT_SOURCE_PATHS):
            raise ValueError("BR-28 source paths must include BR-27 report and reviewed snapshot")
        for candidate in self.candidates:
            candidate.validate()
        for reason in _all_block_reasons(self.blocked_records):
            if reason not in BLOCK_REASONS:
                raise ValueError("BR-28 block reason is not recognized")
        if set(self.adapter_checks) != set(ADAPTER_CHECKS):
            raise ValueError("BR-28 adapter must record every deterministic check")
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
        "br27_reviewed_snapshot_only": True,
        "deterministic_adapter_only": True,
        "normalized_research_candidates_only": True,
        "point_in_time_records_only": True,
        "preserve_observation_timestamps": True,
        "preserve_decision_timestamps": True,
        "preserve_source_checksum": True,
        "preserve_provenance": True,
        "preserve_strategy_version": True,
        "preserve_feature_inputs": True,
        "preserve_missing_data_flags": True,
        "preserve_stale_data_flags": True,
        "preserve_benchmark_context": True,
        "preserve_human_review_status": True,
        "lookahead_prevention_enforced": True,
        "evaluation_period_outcomes_used": False,
        "parameter_optimization_performed": False,
        "strategy_selected_using_evaluation_outcomes": False,
        "candidate_records_authorize_trade": False,
        "live_state_mutation_allowed": False,
        "paper_state_mutation_allowed": False,
        "broker_state_mutation_allowed": False,
        "routing_state_mutation_allowed": False,
        "broker_write_operations_authorized": False,
        "external_routing_paths_authorized": False,
        "data_provider_calls_authorized": False,
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
        "live_trading_enabled": False,
        "LIVE TRADING": "DISABLED",
    }


def build_snapshot_to_candidate_adapter(
    source_paths: dict[str, Path] | None = None,
    as_of: datetime | None = None,
) -> SnapshotToCandidateAdapterResult:
    resolved_paths = source_paths or DEFAULT_SOURCE_PATHS
    resolved_as_of = as_of or datetime.now(timezone.utc).replace(microsecond=0)
    br27_path = resolved_paths["BR-27 approved snapshot intake review gate"]
    snapshot_path = resolved_paths["BR-27-reviewed approved offline snapshot"]
    br27_payload, br27_reasons = _load_json(br27_path, "br27_report_missing", "br27_report_malformed")
    snapshot_payload, snapshot_reasons = _load_json(snapshot_path, "snapshot_file_missing", "snapshot_json_malformed")
    blocked_records: list[dict[str, Any]] = []
    blocked_records.extend(_block_record(str(br27_path), br27_reasons))
    blocked_records.extend(_block_record(str(snapshot_path), snapshot_reasons))
    if snapshot_payload is not None and not isinstance(snapshot_payload, dict):
        blocked_records.extend(_block_record(str(snapshot_path), ("snapshot_not_object",)))
        snapshot_payload = None

    br27_accepted = _br27_accepts_snapshot(br27_payload, snapshot_path)
    path_matches = _snapshot_path_matches_br27(br27_payload, snapshot_path)
    checksum_matches = _snapshot_checksum_matches_br27(br27_payload, snapshot_payload)
    if br27_payload is not None and not br27_accepted:
        blocked_records.extend(_block_record(str(br27_path), ("br27_report_not_accepted",)))
    if br27_payload is not None and not path_matches:
        blocked_records.extend(_block_record(str(snapshot_path), ("snapshot_path_not_reviewed_by_br27",)))
    if snapshot_payload is not None and not checksum_matches:
        blocked_records.extend(_block_record(str(snapshot_path), ("snapshot_checksum_mismatch",)))

    candidates: tuple[ResearchCandidateRecord, ...] = ()
    if snapshot_payload is not None and br27_accepted and path_matches and checksum_matches:
        candidates, normalization_blocks = _normalize_candidates(snapshot_payload)
        blocked_records.extend(normalization_blocks)

    checks = {
        "br27_report_accepted": br27_accepted,
        "snapshot_path_matches_br27": path_matches,
        "snapshot_checksum_matches_br27": checksum_matches,
        "offline_snapshot_loaded": snapshot_payload is not None,
        "records_are_point_in_time": bool(candidates) and not any(candidate.missing_data_flags for candidate in candidates),
        "decision_timestamps_not_before_observations": all(
            _parse_datetime(candidate.decision_timestamp) >= _parse_datetime(candidate.observation_timestamp)
            for candidate in candidates
        )
        if candidates
        else False,
        "candidate_fields_normalized": bool(candidates) and not blocked_records,
        "no_evaluation_outcomes_used": True,
        "no_parameter_optimization": True,
    }
    result = SnapshotToCandidateAdapterResult(
        as_of=resolved_as_of,
        source_paths={name: str(path) for name, path in resolved_paths.items()},
        candidates=candidates,
        blocked_records=tuple(blocked_records),
        adapter_checks=checks,
        safety=safety_manifest(),
    )
    result.validate()
    return result


def snapshot_to_candidate_adapter_payload(result: SnapshotToCandidateAdapterResult) -> dict[str, Any]:
    result.validate()
    candidates = tuple(_candidate_payload(candidate) for candidate in result.candidates)
    acceptance = _acceptance_criteria(result)
    return {
        "phase": PHASE_ID,
        "module": MODULE_NAME,
        "as_of": result.as_of.isoformat(),
        "label": result.label,
        "strategy_version": STRATEGY_VERSION,
        "source_paths": result.source_paths,
        "adapter_checks": result.adapter_checks,
        "block_reasons": BLOCK_REASONS,
        "safety": result.safety,
        "candidates": candidates,
        "blocked_records": result.blocked_records,
        "metrics": {
            "candidate_count": len(candidates),
            "blocked_record_count": len(result.blocked_records),
            "adapter_check_count": len(ADAPTER_CHECKS),
            "adapter_check_passed_count": sum(1 for passed in result.adapter_checks.values() if passed),
            "acceptance_criteria_count": len(acceptance),
            "acceptance_criteria_passed_count": sum(1 for passed in acceptance.values() if passed),
        },
        "acceptance_criteria": acceptance,
        "readiness_state": {
            "state": "SNAPSHOT_TO_CANDIDATE_ADAPTER_RESEARCH_ONLY",
            "research_candidates_created": bool(candidates),
            "manual_review_required": True,
            "human_review_required": True,
            "ready_for_live_trading": False,
            "candidate_records_authorize_trade": False,
            "broker_actions_allowed": False,
            "order_paths_allowed": False,
            "external_routing_paths_allowed": False,
            "data_provider_calls_allowed": False,
            "paper_state_mutation_allowed": False,
            "live_state_mutation_allowed": False,
        },
    }


def render_markdown_snapshot_to_candidate_adapter(result: SnapshotToCandidateAdapterResult) -> str:
    payload = snapshot_to_candidate_adapter_payload(result)
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

    lines.extend(["", "## Adapter Checks"])
    for name, passed in payload["adapter_checks"].items():
        lines.append(f"- {name}: {passed}")

    lines.extend(["", "## Research Candidates"])
    for candidate in payload["candidates"]:
        lines.append(
            f"- {candidate['candidate_id']}: symbol={candidate['symbol']} "
            f"observation={candidate['observation_timestamp']} decision={candidate['decision_timestamp']} "
            f"label={candidate['label']} human_review_status={candidate['human_review_status']}"
        )

    lines.extend(["", "## Preserved Fields"])
    lines.append("- observation_timestamp")
    lines.append("- decision_timestamp")
    lines.append("- source_checksum_sha256")
    lines.append("- provenance")
    lines.append("- strategy_version")
    lines.append("- feature_inputs")
    lines.append("- missing_data_flags")
    lines.append("- stale_data_flags")
    lines.append("- benchmark_context")
    lines.append("- human_review_status")

    lines.extend(["", "## Blocked Records"])
    if payload["blocked_records"]:
        for record in payload["blocked_records"]:
            lines.append(f"- {record['source']}: {', '.join(record['reasons'])}")
    else:
        lines.append("- none")

    lines.extend(["", "## Metrics"])
    for name, value in payload["metrics"].items():
        lines.append(f"- {name}: {value}")

    lines.extend(["", "## Acceptance Criteria"])
    for name, passed in payload["acceptance_criteria"].items():
        lines.append(f"- {name}: {passed}")

    lines.extend(
        [
            "",
            "## Safety Boundaries",
            "- RESEARCH_ONLY; MONITOR_ONLY; PAPER_ONLY; HUMAN_REVIEW_REQUIRED; BLOCKED_BY_SAFETY_GATE.",
            "- The adapter is offline, read-only for source evidence, deterministic, report-only, fixture-testable, research-only, and human-review-required.",
            "- It consumes only a BR-27-reviewed approved offline snapshot.",
            "- It prevents look-ahead by using only records available at or before each decision timestamp.",
            "- It does not optimize parameters or select a strategy using evaluation-period outcomes.",
            "- No .env reads, credential loading, secret requests, data-provider calls, broker connections, broker writes, external routing paths, state mutation, or live trading authorization.",
        ]
    )
    return "\n".join(lines)


def write_snapshot_to_candidate_adapter(
    result: SnapshotToCandidateAdapterResult,
    out_dir: Path = DEFAULT_REPORT_DIR,
) -> tuple[Path, Path]:
    result.validate()
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_REPORT_NAME
    markdown_path = out_dir / MARKDOWN_REPORT_NAME
    json_path.write_text(
        json.dumps(snapshot_to_candidate_adapter_payload(result), indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown_snapshot_to_candidate_adapter(result), encoding="utf-8")
    return json_path, markdown_path


def run_snapshot_to_candidate_adapter(
    source_paths: dict[str, Path] | None = None,
    out_dir: Path = DEFAULT_REPORT_DIR,
    as_of: datetime | None = None,
) -> SnapshotToCandidateAdapterResult:
    result = build_snapshot_to_candidate_adapter(source_paths=source_paths, as_of=as_of)
    write_snapshot_to_candidate_adapter(result, out_dir=out_dir)
    return result


def _normalize_candidates(payload: dict[str, Any]) -> tuple[tuple[ResearchCandidateRecord, ...], tuple[dict[str, Any], ...]]:
    records = payload.get("records")
    if not isinstance(records, list) or not records:
        return (), tuple(_block_record(str(payload.get("snapshot_id")), ("snapshot_records_missing",)))

    provenance = payload.get("provenance", {}) if isinstance(payload.get("provenance"), dict) else {}
    checksum = str(provenance.get("checksum_sha256", ""))
    benchmark_by_timestamp = _benchmark_context_by_timestamp(records)
    candidates: list[ResearchCandidateRecord] = []
    blocked: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            blocked.extend(_block_record(f"record[{index}]", ("candidate_normalization_failed",)))
            continue
        timestamp = record.get("timestamp")
        parsed_timestamp = _parse_datetime(timestamp)
        if parsed_timestamp is None:
            blocked.extend(_block_record(str(record.get("symbol", f"record[{index}]")), ("record_timestamp_invalid",)))
            continue
        decision_timestamp = parsed_timestamp.isoformat()
        observation_timestamp = parsed_timestamp.isoformat()
        if _parse_datetime(decision_timestamp) < _parse_datetime(observation_timestamp):
            blocked.extend(_block_record(str(record.get("symbol", f"record[{index}]")), ("decision_timestamp_before_observation",)))
            continue
        missing_flags = _missing_data_flags(record)
        stale_flags = _stale_data_flags(record, parsed_timestamp)
        feature_inputs = {
            "open": record.get("open"),
            "high": record.get("high"),
            "low": record.get("low"),
            "close": record.get("close"),
            "volume": record.get("volume"),
        }
        symbol = str(record.get("symbol", "UNKNOWN"))
        candidate = ResearchCandidateRecord(
            candidate_id=_candidate_id(str(payload.get("snapshot_id")), symbol, decision_timestamp),
            symbol=symbol,
            label=HUMAN_REVIEW_REQUIRED,
            human_review_status=HUMAN_REVIEW_REQUIRED,
            observation_timestamp=observation_timestamp,
            decision_timestamp=decision_timestamp,
            source_checksum_sha256=checksum,
            provenance={
                "snapshot_id": payload.get("snapshot_id"),
                "source_kind": payload.get("source_kind"),
                "data_domain": payload.get("data_domain"),
                "provider_name": provenance.get("provider_name"),
                "provider_dataset": provenance.get("provider_dataset"),
                "source_file_name": provenance.get("source_file_name"),
                "acquisition_method": provenance.get("acquisition_method"),
                "collector": provenance.get("collector"),
                "collected_at": provenance.get("collected_at"),
                "schema_name": provenance.get("schema_name"),
                "quality_score": provenance.get("quality_score"),
            },
            strategy_version=STRATEGY_VERSION,
            feature_inputs=feature_inputs,
            missing_data_flags=missing_flags,
            stale_data_flags=stale_flags,
            benchmark_context=benchmark_by_timestamp.get(decision_timestamp, _empty_benchmark_context()),
            lookahead_guard={
                "observation_timestamp": observation_timestamp,
                "decision_timestamp": decision_timestamp,
                "uses_only_records_at_or_before_decision_timestamp": True,
                "future_records_used": False,
                "evaluation_period_outcomes_used": False,
                "parameter_optimization_performed": False,
                "strategy_selected_using_evaluation_outcomes": False,
            },
        )
        candidate.validate()
        candidates.append(candidate)
    return tuple(sorted(candidates, key=lambda item: (item.decision_timestamp, item.symbol))), tuple(blocked)


def _benchmark_context_by_timestamp(records: list[Any]) -> dict[str, dict[str, Any]]:
    context: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict) or record.get("symbol") != "SPY":
            continue
        parsed = _parse_datetime(record.get("timestamp"))
        if parsed is None:
            continue
        key = parsed.isoformat()
        context[key] = {
            "benchmark_symbol": "SPY",
            "benchmark_close": record.get("close"),
            "benchmark_timestamp": key,
            "benchmark_available_at_decision": True,
        }
    return context


def _empty_benchmark_context() -> dict[str, Any]:
    return {
        "benchmark_symbol": None,
        "benchmark_close": None,
        "benchmark_timestamp": None,
        "benchmark_available_at_decision": False,
    }


def _missing_data_flags(record: dict[str, Any]) -> tuple[str, ...]:
    flags = []
    for field_name in ("symbol", "timestamp", "open", "high", "low", "close", "volume"):
        if record.get(field_name) in (None, ""):
            flags.append(f"missing_{field_name}")
    return tuple(flags)


def _stale_data_flags(record: dict[str, Any], decision_timestamp: datetime) -> tuple[str, ...]:
    observation_timestamp = _parse_datetime(record.get("timestamp"))
    if observation_timestamp is None:
        return ("stale_timestamp_unparseable",)
    if observation_timestamp > decision_timestamp:
        return ("future_observation_blocked",)
    return ()


def _load_json(path: Path, missing_reason: str, malformed_reason: str) -> tuple[Any | None, tuple[str, ...]]:
    if not path.exists():
        return None, (missing_reason,)
    try:
        return json.loads(path.read_text(encoding="utf-8")), ()
    except json.JSONDecodeError:
        return None, (malformed_reason,)


def _br27_accepts_snapshot(payload: Any, snapshot_path: Path) -> bool:
    if not isinstance(payload, dict) or payload.get("phase") != "BR-27":
        return False
    records = payload.get("accepted_research_evidence")
    if not isinstance(records, list) or not records:
        return False
    resolved_snapshot = snapshot_path.resolve()
    for record in records:
        if not isinstance(record, dict):
            continue
        if Path(str(record.get("snapshot_path"))).resolve() != resolved_snapshot:
            continue
        if record.get("accepted_as_research_evidence") is not True:
            continue
        if record.get("label") != HUMAN_REVIEW_REQUIRED:
            continue
        checks = record.get("checks")
        if isinstance(checks, dict) and all(checks.values()):
            return True
    return False


def _snapshot_path_matches_br27(payload: Any, snapshot_path: Path) -> bool:
    if not isinstance(payload, dict):
        return False
    source_paths = payload.get("source_paths")
    if not isinstance(source_paths, dict):
        return False
    reviewed_path = source_paths.get("approved offline snapshot")
    return isinstance(reviewed_path, str) and Path(reviewed_path).resolve() == snapshot_path.resolve()


def _snapshot_checksum_matches_br27(br27_payload: Any, snapshot_payload: Any) -> bool:
    if not isinstance(br27_payload, dict) or not isinstance(snapshot_payload, dict):
        return False
    accepted = br27_payload.get("accepted_research_evidence")
    provenance = snapshot_payload.get("provenance")
    if not isinstance(accepted, list) or not isinstance(provenance, dict):
        return False
    checksum = provenance.get("checksum_sha256")
    for record in accepted:
        summary = record.get("snapshot_summary") if isinstance(record, dict) else None
        if isinstance(summary, dict) and summary.get("checksum_sha256") == checksum:
            return True
    return False


def _candidate_id(snapshot_id: str, symbol: str, decision_timestamp: str) -> str:
    raw = f"{snapshot_id}|{symbol}|{decision_timestamp}|{STRATEGY_VERSION}"
    return "br28-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


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


def _candidate_payload(candidate: ResearchCandidateRecord) -> dict[str, Any]:
    return {
        "candidate_id": candidate.candidate_id,
        "symbol": candidate.symbol,
        "label": candidate.label,
        "human_review_status": candidate.human_review_status,
        "observation_timestamp": candidate.observation_timestamp,
        "decision_timestamp": candidate.decision_timestamp,
        "source_checksum_sha256": candidate.source_checksum_sha256,
        "provenance": candidate.provenance,
        "strategy_version": candidate.strategy_version,
        "feature_inputs": candidate.feature_inputs,
        "missing_data_flags": candidate.missing_data_flags,
        "stale_data_flags": candidate.stale_data_flags,
        "benchmark_context": candidate.benchmark_context,
        "lookahead_guard": candidate.lookahead_guard,
    }


def _acceptance_criteria(result: SnapshotToCandidateAdapterResult) -> dict[str, bool]:
    return {
        "source_paths_include_br27_and_snapshot": set(result.source_paths) == set(DEFAULT_SOURCE_PATHS),
        "br27_report_accepted": result.adapter_checks["br27_report_accepted"],
        "snapshot_path_matches_br27": result.adapter_checks["snapshot_path_matches_br27"],
        "snapshot_checksum_matches_br27": result.adapter_checks["snapshot_checksum_matches_br27"],
        "candidate_records_created": bool(result.candidates),
        "candidate_records_remain_human_review_required": all(
            candidate.human_review_status == HUMAN_REVIEW_REQUIRED and candidate.label == HUMAN_REVIEW_REQUIRED
            for candidate in result.candidates
        ),
        "lookahead_prevention_enforced": all(
            candidate.lookahead_guard["uses_only_records_at_or_before_decision_timestamp"] is True
            and candidate.lookahead_guard["future_records_used"] is False
            for candidate in result.candidates
        ),
        "no_evaluation_outcomes_or_parameter_optimization": (
            result.safety["evaluation_period_outcomes_used"] is False
            and result.safety["parameter_optimization_performed"] is False
            and result.safety["strategy_selected_using_evaluation_outcomes"] is False
        ),
        "no_credentials_or_secrets": all(
            result.safety[field_name] is False
            for field_name in ("credential_loading_attempted", "env_file_read_attempted", "secret_request_attempted")
        ),
        "no_data_provider_or_network_calls": all(
            result.safety[field_name] is False
            for field_name in ("data_provider_call_attempted", "external_network_call_attempted", "real_data_fetch_attempted")
        ),
        "no_broker_actions_order_paths_or_state_mutation": all(
            result.safety[field_name] is False for field_name in REQUIRED_DISABLED_FLAGS
        ),
        "live_trading_disabled": result.safety["LIVE TRADING"] == "DISABLED",
    }


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _validate_disabled_safety(manifest: dict[str, Any]) -> None:
    for field_name in REQUIRED_DISABLED_FLAGS:
        if manifest.get(field_name) is not False:
            raise ValueError(f"BR-28 adapter cannot set {field_name}")
    for field_name in (
        "candidate_records_authorize_trade",
        "live_state_mutation_allowed",
        "paper_state_mutation_allowed",
        "broker_state_mutation_allowed",
        "routing_state_mutation_allowed",
        "broker_write_operations_authorized",
        "external_routing_paths_authorized",
        "data_provider_calls_authorized",
        "evaluation_period_outcomes_used",
        "parameter_optimization_performed",
        "strategy_selected_using_evaluation_outcomes",
    ):
        if manifest.get(field_name) is not False:
            raise ValueError(f"BR-28 adapter cannot allow {field_name}")
    if manifest.get("LIVE TRADING") != "DISABLED":
        raise ValueError("BR-28 adapter must keep LIVE TRADING disabled")
