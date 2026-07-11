from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from engines.moonshot.deterministic.br26_read_only_data_snapshot_import_contract import (
    REDACTED_FIELDS,
    REQUIRED_DISABLED_FLAGS,
    REQUIRED_PROVENANCE_FIELDS,
    REQUIRED_RECORD_FIELDS,
    REQUIRED_TOP_LEVEL_FIELDS,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


PHASE_ID = "BR-27"
MODULE_NAME = "Approved Snapshot Intake Review Gate"
DEFAULT_REPORT_DIR = Path("reports/br27_approved_snapshot_intake_review_gate")
JSON_REPORT_NAME = "approved_snapshot_intake_review_gate.json"
MARKDOWN_REPORT_NAME = "approved_snapshot_intake_review_gate.md"
DEFAULT_BR26_REPORT_PATH = Path(
    "reports/br26_read_only_data_snapshot_import_contract/read_only_data_snapshot_import_contract.json"
)
DEFAULT_APPROVED_SNAPSHOT_PATH = Path(
    "engines/moonshot/deterministic/fixtures/br26_read_only_data_snapshot_valid.json"
)
DEFAULT_SOURCE_PATHS = {
    "BR-26 import contract": DEFAULT_BR26_REPORT_PATH,
    "approved offline snapshot": DEFAULT_APPROVED_SNAPSHOT_PATH,
}
REQUIRED_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
REVIEW_CHECKS = (
    "file_approval",
    "checksum",
    "schema",
    "provenance",
    "freshness",
    "redaction",
    "runtime_safety",
    "observation_timestamps",
)
REJECTION_REASONS = (
    "br26_report_missing",
    "br26_report_malformed",
    "br26_report_phase_mismatch",
    "br26_report_safety_disabled_flags_missing",
    "snapshot_file_not_approved_by_br26",
    "snapshot_file_missing",
    "snapshot_json_malformed",
    "snapshot_not_object",
    "snapshot_missing_required_field",
    "snapshot_schema_malformed",
    "snapshot_provenance_missing_or_low_quality",
    "snapshot_stale",
    "snapshot_contains_unredacted_sensitive_field",
    "snapshot_contains_unsafe_runtime_state",
    "snapshot_checksum_mismatch",
    "snapshot_observation_timestamp_invalid",
    "snapshot_accepted_without_separate_review_decision",
)


@dataclass(frozen=True)
class SnapshotIntakeReviewRecord:
    snapshot_path: str
    br26_report_path: str
    label: str
    accepted_as_research_evidence: bool
    advancement_allowed: bool
    separate_review_decision_required: bool
    checks: dict[str, bool]
    rejection_evidence: tuple[str, ...]
    unresolved_blockers: tuple[str, ...]
    required_human_review_actions: tuple[str, ...]
    observation_timestamps: dict[str, Any]
    source_evidence: dict[str, Any]
    snapshot_summary: dict[str, Any]

    def validate(self) -> None:
        if set(self.checks) != set(REVIEW_CHECKS):
            raise ValueError("BR-27 review record must include every deterministic check")
        if self.advancement_allowed:
            raise ValueError("BR-27 review record cannot allow advancement")
        if not self.separate_review_decision_required:
            raise ValueError("BR-27 review record must require a separate review decision")
        if self.accepted_as_research_evidence:
            if self.label != HUMAN_REVIEW_REQUIRED:
                raise ValueError("BR-27 accepted snapshots must remain human-review-required")
            if self.rejection_evidence or self.unresolved_blockers:
                raise ValueError("BR-27 accepted snapshots cannot include rejection evidence")
        else:
            if self.label != BLOCKED_BY_SAFETY_GATE:
                raise ValueError("BR-27 rejected snapshots must be blocked by safety gate")
            for reason in self.rejection_evidence:
                if reason not in REJECTION_REASONS:
                    raise ValueError("BR-27 rejection reason is not recognized")
        if not self.required_human_review_actions:
            raise ValueError("BR-27 review record requires human-review actions")


@dataclass(frozen=True)
class ApprovedSnapshotIntakeReviewGate:
    as_of: datetime
    source_paths: dict[str, str]
    review_records: tuple[SnapshotIntakeReviewRecord, ...]
    safety: dict[str, Any]
    label: str = HUMAN_REVIEW_REQUIRED

    def validate(self) -> None:
        if self.label != HUMAN_REVIEW_REQUIRED:
            raise ValueError("BR-27 review gate must require human review")
        if set(self.source_paths) != set(DEFAULT_SOURCE_PATHS):
            raise ValueError("BR-27 source paths must include BR-26 report and approved snapshot")
        if not self.review_records:
            raise ValueError("BR-27 review gate requires at least one review record")
        for record in self.review_records:
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
        "offline_only": True,
        "read_only": True,
        "report_only": True,
        "fixture_testable": True,
        "committed_br26_report_only": True,
        "approved_offline_snapshot_only": True,
        "immutable_source_evidence": True,
        "deterministic_review_gate_only": True,
        "accepted_snapshot_is_research_evidence_only": True,
        "separate_review_decision_required": True,
        "advancement_authorized": False,
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
        "paper_state_mutation_allowed": False,
        "live_trading_enabled": False,
        "LIVE TRADING": "DISABLED",
    }


def build_approved_snapshot_intake_review_gate(
    source_paths: dict[str, Path] | None = None,
    as_of: datetime | None = None,
    max_age: timedelta = timedelta(days=3),
) -> ApprovedSnapshotIntakeReviewGate:
    resolved_paths = source_paths or DEFAULT_SOURCE_PATHS
    resolved_as_of = as_of or datetime.now(timezone.utc).replace(microsecond=0)
    record = _build_review_record(
        br26_report_path=resolved_paths["BR-26 import contract"],
        snapshot_path=resolved_paths["approved offline snapshot"],
        as_of=resolved_as_of,
        max_age=max_age,
    )
    gate = ApprovedSnapshotIntakeReviewGate(
        as_of=resolved_as_of,
        source_paths={name: str(path) for name, path in resolved_paths.items()},
        review_records=(record,),
        safety=safety_manifest(),
    )
    gate.validate()
    return gate


def approved_snapshot_intake_review_gate_payload(
    gate: ApprovedSnapshotIntakeReviewGate,
) -> dict[str, Any]:
    gate.validate()
    records = tuple(_record_payload(record) for record in gate.review_records)
    accepted = tuple(record for record in records if record["accepted_as_research_evidence"])
    rejected = tuple(record for record in records if not record["accepted_as_research_evidence"])
    acceptance = _acceptance_criteria(gate)
    return {
        "phase": PHASE_ID,
        "module": MODULE_NAME,
        "as_of": gate.as_of.isoformat(),
        "label": gate.label,
        "source_paths": gate.source_paths,
        "review_checks": REVIEW_CHECKS,
        "rejection_reasons": REJECTION_REASONS,
        "safety": gate.safety,
        "review_records": records,
        "accepted_research_evidence": accepted,
        "rejected_snapshots": rejected,
        "metrics": {
            "source_path_count": len(gate.source_paths),
            "review_record_count": len(records),
            "accepted_research_evidence_count": len(accepted),
            "rejected_snapshot_count": len(rejected),
            "review_check_count": len(REVIEW_CHECKS),
            "rejection_reason_count": len(REJECTION_REASONS),
            "required_human_review_action_count": sum(
                len(record["required_human_review_actions"]) for record in records
            ),
            "acceptance_criteria_count": len(acceptance),
            "acceptance_criteria_passed_count": sum(1 for passed in acceptance.values() if passed),
        },
        "acceptance_criteria": acceptance,
        "readiness_state": {
            "state": "APPROVED_SNAPSHOT_INTAKE_REVIEW_GATE_ONLY",
            "accepted_snapshot_is_research_evidence_only": True,
            "manual_review_required": True,
            "separate_review_decision_required": True,
            "ready_for_candidate_adapter": False,
            "ready_for_live_trading": False,
            "paper_state_mutation_allowed": False,
            "live_state_mutation_allowed": False,
            "broker_actions_allowed": False,
            "order_paths_allowed": False,
            "data_provider_calls_allowed": False,
        },
    }


def render_markdown_approved_snapshot_intake_review_gate(
    gate: ApprovedSnapshotIntakeReviewGate,
) -> str:
    payload = approved_snapshot_intake_review_gate_payload(gate)
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

    lines.extend(["", "## Review Records"])
    for record in payload["review_records"]:
        reasons = ", ".join(record["rejection_evidence"]) if record["rejection_evidence"] else "accepted"
        lines.append(
            f"- {record['snapshot_path']}: accepted_as_research_evidence="
            f"{record['accepted_as_research_evidence']} label={record['label']} reasons={reasons}"
        )

    lines.extend(["", "## Checks"])
    for record in payload["review_records"]:
        lines.append(f"- snapshot: {record['snapshot_path']}")
        for check_name, passed in record["checks"].items():
            lines.append(f"- {check_name}: {passed}")

    lines.extend(["", "## Observation Timestamps"])
    for record in payload["review_records"]:
        timestamps = record["observation_timestamps"]
        lines.append(f"- generated_at: {timestamps.get('generated_at')}")
        lines.append(f"- freshness_as_of: {timestamps.get('freshness_as_of')}")
        lines.append(f"- collected_at: {timestamps.get('collected_at')}")
        for item in timestamps.get("record_timestamps", ()):
            lines.append(f"- record_timestamp: {item}")

    lines.extend(["", "## Rejection Evidence"])
    for reason in REJECTION_REASONS:
        lines.append(f"- {reason}")

    lines.extend(["", "## Required Human Review Actions"])
    for record in payload["review_records"]:
        for action in record["required_human_review_actions"]:
            lines.append(f"- {action}")

    lines.extend(["", "## Unresolved Blockers"])
    for record in payload["review_records"]:
        if record["unresolved_blockers"]:
            for blocker in record["unresolved_blockers"]:
                lines.append(f"- {blocker}")
        else:
            lines.append("- none for intake; separate review decision remains required")

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
            "- The review gate is offline, read-only, deterministic, report-only, and fixture-testable.",
            "- No .env reads, credential loading, secret requests, data-provider calls, broker connections, broker writes, external routing paths, paper state mutation, trading state mutation, or live trading authorization.",
            "- Accepted snapshots remain research evidence only and cannot advance without a separate human-review decision.",
        ]
    )
    return "\n".join(lines)


def write_approved_snapshot_intake_review_gate(
    gate: ApprovedSnapshotIntakeReviewGate,
    out_dir: Path = DEFAULT_REPORT_DIR,
) -> tuple[Path, Path]:
    gate.validate()
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_REPORT_NAME
    markdown_path = out_dir / MARKDOWN_REPORT_NAME
    json_path.write_text(
        json.dumps(approved_snapshot_intake_review_gate_payload(gate), indent=2, default=str),
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown_approved_snapshot_intake_review_gate(gate), encoding="utf-8")
    return json_path, markdown_path


def run_approved_snapshot_intake_review_gate(
    source_paths: dict[str, Path] | None = None,
    out_dir: Path = DEFAULT_REPORT_DIR,
    as_of: datetime | None = None,
) -> ApprovedSnapshotIntakeReviewGate:
    gate = build_approved_snapshot_intake_review_gate(source_paths=source_paths, as_of=as_of)
    write_approved_snapshot_intake_review_gate(gate, out_dir=out_dir)
    return gate


def _build_review_record(
    br26_report_path: Path,
    snapshot_path: Path,
    as_of: datetime,
    max_age: timedelta,
) -> SnapshotIntakeReviewRecord:
    rejection_evidence: list[str] = []
    br26_payload = _load_json_or_reason(br26_report_path, rejection_evidence, "br26_report_missing", "br26_report_malformed")
    snapshot_payload = _load_json_or_reason(
        snapshot_path,
        rejection_evidence,
        "snapshot_file_missing",
        "snapshot_json_malformed",
    )
    if br26_payload is not None and br26_payload.get("phase") != "BR-26":
        rejection_evidence.append("br26_report_phase_mismatch")
    if br26_payload is not None and not _source_safety_disabled(br26_payload.get("safety", {})):
        rejection_evidence.append("br26_report_safety_disabled_flags_missing")
    if snapshot_payload is not None and not isinstance(snapshot_payload, dict):
        rejection_evidence.append("snapshot_not_object")
        snapshot_payload = None

    checks = {
        "file_approval": _file_is_approved_by_br26(snapshot_path, br26_payload),
        "checksum": _checksum_matches(snapshot_payload, snapshot_path),
        "schema": _schema_is_well_formed(snapshot_payload),
        "provenance": _provenance_is_valid(snapshot_payload, snapshot_path),
        "freshness": not _snapshot_is_stale(snapshot_payload, as_of, max_age),
        "redaction": not _contains_sensitive_field(snapshot_payload),
        "runtime_safety": _snapshot_runtime_safety_is_disabled(snapshot_payload),
        "observation_timestamps": _observation_timestamps_are_valid(snapshot_payload),
    }
    if not checks["file_approval"]:
        rejection_evidence.append("snapshot_file_not_approved_by_br26")
    if not checks["checksum"]:
        rejection_evidence.append("snapshot_checksum_mismatch")
    if snapshot_payload is not None:
        if any(field_name not in snapshot_payload for field_name in REQUIRED_TOP_LEVEL_FIELDS):
            rejection_evidence.append("snapshot_missing_required_field")
        if not checks["schema"]:
            rejection_evidence.append("snapshot_schema_malformed")
        if not checks["provenance"]:
            rejection_evidence.append("snapshot_provenance_missing_or_low_quality")
        if not checks["freshness"]:
            rejection_evidence.append("snapshot_stale")
        if not checks["redaction"]:
            rejection_evidence.append("snapshot_contains_unredacted_sensitive_field")
        if not checks["runtime_safety"]:
            rejection_evidence.append("snapshot_contains_unsafe_runtime_state")
        if not checks["observation_timestamps"]:
            rejection_evidence.append("snapshot_observation_timestamp_invalid")

    rejection_reasons = tuple(dict.fromkeys(rejection_evidence))
    accepted = not rejection_reasons and all(checks.values())
    label = HUMAN_REVIEW_REQUIRED if accepted else BLOCKED_BY_SAFETY_GATE
    blockers = () if accepted else tuple(f"{reason}: deterministic intake check failed" for reason in rejection_reasons)
    actions = _human_review_actions(accepted)
    record = SnapshotIntakeReviewRecord(
        snapshot_path=str(snapshot_path),
        br26_report_path=str(br26_report_path),
        label=label,
        accepted_as_research_evidence=accepted,
        advancement_allowed=False,
        separate_review_decision_required=True,
        checks=checks,
        rejection_evidence=rejection_reasons,
        unresolved_blockers=blockers,
        required_human_review_actions=actions,
        observation_timestamps=_observation_timestamps(snapshot_payload),
        source_evidence=_source_evidence(br26_report_path, snapshot_path, br26_payload),
        snapshot_summary=_snapshot_summary(snapshot_payload),
    )
    record.validate()
    return record


def _load_json_or_reason(
    path: Path,
    rejection_evidence: list[str],
    missing_reason: str,
    malformed_reason: str,
) -> dict[str, Any] | None:
    if not path.exists():
        rejection_evidence.append(missing_reason)
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        rejection_evidence.append(malformed_reason)
        return None
    if not isinstance(payload, dict):
        rejection_evidence.append(malformed_reason)
        return None
    return payload


def _file_is_approved_by_br26(snapshot_path: Path, br26_payload: dict[str, Any] | None) -> bool:
    if br26_payload is None:
        return False
    approved_paths = br26_payload.get("approved_snapshot_paths")
    accepted_snapshots = br26_payload.get("accepted_snapshots", ())
    if not isinstance(approved_paths, list) or not isinstance(accepted_snapshots, list):
        return False
    resolved_snapshot = snapshot_path.resolve()
    approved = {Path(path).resolve() for path in approved_paths if isinstance(path, str)}
    accepted = {
        Path(item["path"]).resolve()
        for item in accepted_snapshots
        if isinstance(item, dict) and isinstance(item.get("path"), str) and item.get("accepted") is True
    }
    return resolved_snapshot in approved and resolved_snapshot in accepted


def _checksum_matches(snapshot_payload: dict[str, Any] | None, snapshot_path: Path) -> bool:
    if snapshot_payload is None or not snapshot_path.exists():
        return False
    provenance = snapshot_payload.get("provenance")
    if not isinstance(provenance, dict):
        return False
    expected = provenance.get("checksum_sha256")
    if not isinstance(expected, str) or len(expected) != 64:
        return False
    raw_payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    raw_payload["provenance"] = dict(raw_payload.get("provenance", {}))
    raw_payload["provenance"]["checksum_sha256"] = "0" * 64
    canonical_text = json.dumps(raw_payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_text.encode("utf-8")).hexdigest() == expected


def _schema_is_well_formed(payload: dict[str, Any] | None) -> bool:
    if payload is None:
        return False
    if any(field_name not in payload for field_name in REQUIRED_TOP_LEVEL_FIELDS):
        return False
    if payload.get("snapshot_version") != "1" or payload.get("source_kind") != "approved_offline_file":
        return False
    if not isinstance(payload.get("symbols"), list) or not payload["symbols"]:
        return False
    if not isinstance(payload.get("records"), list) or not payload["records"]:
        return False
    if not set(REQUIRED_LABELS).issubset(set(payload.get("labels", []))):
        return False
    for record in payload["records"]:
        if not isinstance(record, dict):
            return False
        if any(field_name not in record for field_name in REQUIRED_RECORD_FIELDS):
            return False
        if record["symbol"] not in payload["symbols"]:
            return False
    return True


def _provenance_is_valid(payload: dict[str, Any] | None, snapshot_path: Path) -> bool:
    if payload is None or not isinstance(payload.get("provenance"), dict):
        return False
    provenance = payload["provenance"]
    if any(field_name not in provenance for field_name in REQUIRED_PROVENANCE_FIELDS):
        return False
    if provenance.get("source_file_name") != snapshot_path.name:
        return False
    if provenance.get("acquisition_method") != "offline_file_export":
        return False
    quality_score = provenance.get("quality_score")
    if not isinstance(quality_score, (int, float)) or quality_score < 0.8:
        return False
    return all(provenance.get(field_name) not in ("", None) for field_name in REQUIRED_PROVENANCE_FIELDS)


def _snapshot_is_stale(payload: dict[str, Any] | None, as_of: datetime, max_age: timedelta) -> bool:
    if payload is None:
        return True
    freshness_at = _parse_datetime(payload.get("freshness_as_of"))
    if freshness_at is None:
        return True
    return as_of - freshness_at > max_age


def _contains_sensitive_field(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in REDACTED_FIELDS:
                return True
            if _contains_sensitive_field(child):
                return True
    if isinstance(value, list):
        return any(_contains_sensitive_field(item) for item in value)
    return False


def _snapshot_runtime_safety_is_disabled(payload: dict[str, Any] | None) -> bool:
    if payload is None or not isinstance(payload.get("safety"), dict):
        return False
    safety = payload["safety"]
    if safety.get("LIVE TRADING") != "DISABLED":
        return False
    return all(safety.get(field_name) is False for field_name in REQUIRED_DISABLED_FLAGS)


def _observation_timestamps_are_valid(payload: dict[str, Any] | None) -> bool:
    if payload is None:
        return False
    timestamps = [
        payload.get("generated_at"),
        payload.get("freshness_as_of"),
        payload.get("provenance", {}).get("collected_at") if isinstance(payload.get("provenance"), dict) else None,
    ]
    if any(_parse_datetime(value) is None for value in timestamps):
        return False
    records = payload.get("records")
    if not isinstance(records, list):
        return False
    return all(isinstance(record, dict) and _parse_datetime(record.get("timestamp")) is not None for record in records)


def _source_safety_disabled(safety: Any) -> bool:
    if not isinstance(safety, dict):
        return False
    if safety.get("LIVE TRADING") != "DISABLED":
        return False
    return all(safety.get(field_name) is False for field_name in REQUIRED_DISABLED_FLAGS if field_name in safety)


def _observation_timestamps(payload: dict[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        return {
            "generated_at": None,
            "freshness_as_of": None,
            "collected_at": None,
            "record_timestamps": (),
        }
    provenance = payload.get("provenance", {}) if isinstance(payload.get("provenance"), dict) else {}
    records = payload.get("records", ()) if isinstance(payload.get("records"), list) else ()
    return {
        "generated_at": payload.get("generated_at"),
        "freshness_as_of": payload.get("freshness_as_of"),
        "collected_at": provenance.get("collected_at"),
        "record_timestamps": tuple(
            record.get("timestamp") for record in records if isinstance(record, dict) and record.get("timestamp")
        ),
    }


def _source_evidence(
    br26_report_path: Path,
    snapshot_path: Path,
    br26_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "br26_report": {
            "path": str(br26_report_path),
            "exists": br26_report_path.exists(),
            "sha256": _file_sha256(br26_report_path) if br26_report_path.exists() else None,
            "phase": br26_payload.get("phase") if br26_payload else None,
            "module": br26_payload.get("module") if br26_payload else None,
        },
        "approved_snapshot": {
            "path": str(snapshot_path),
            "exists": snapshot_path.exists(),
            "sha256": _file_sha256(snapshot_path) if snapshot_path.exists() else None,
        },
    }


def _snapshot_summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        return {
            "snapshot_id": None,
            "data_domain": None,
            "symbol_count": 0,
            "record_count": 0,
            "checksum_sha256": None,
            "provenance_quality_score": None,
        }
    provenance = payload.get("provenance", {}) if isinstance(payload.get("provenance"), dict) else {}
    return {
        "snapshot_id": payload.get("snapshot_id"),
        "data_domain": payload.get("data_domain"),
        "symbol_count": len(payload.get("symbols", ())) if isinstance(payload.get("symbols"), list) else 0,
        "record_count": len(payload.get("records", ())) if isinstance(payload.get("records"), list) else 0,
        "checksum_sha256": provenance.get("checksum_sha256"),
        "provenance_quality_score": provenance.get("quality_score"),
    }


def _human_review_actions(accepted: bool) -> tuple[str, ...]:
    if accepted:
        return (
            "Confirm the approved snapshot may remain research evidence only.",
            "Record a separate human-review decision before any downstream adapter consumes the snapshot.",
            "Keep live trading disabled and do not create broker actions, order paths, or state mutations.",
        )
    return (
        "Review rejection evidence and keep the snapshot blocked until source evidence is corrected.",
        "Do not advance the snapshot to downstream adapters.",
        "Keep live trading disabled and do not create broker actions, order paths, or state mutations.",
    )


def _acceptance_criteria(gate: ApprovedSnapshotIntakeReviewGate) -> dict[str, bool]:
    return {
        "source_paths_include_br26_and_snapshot": set(gate.source_paths) == set(DEFAULT_SOURCE_PATHS),
        "all_review_records_validated": all(isinstance(record, SnapshotIntakeReviewRecord) for record in gate.review_records),
        "all_checks_recorded": all(set(record.checks) == set(REVIEW_CHECKS) for record in gate.review_records),
        "accepted_snapshots_remain_research_evidence_only": all(
            record.accepted_as_research_evidence and not record.advancement_allowed
            for record in gate.review_records
            if record.accepted_as_research_evidence
        ),
        "separate_review_decision_required": all(record.separate_review_decision_required for record in gate.review_records),
        "rejected_snapshots_blocked_by_safety_gate": all(
            record.label == BLOCKED_BY_SAFETY_GATE
            for record in gate.review_records
            if not record.accepted_as_research_evidence
        ),
        "no_credentials_or_secrets": all(
            gate.safety[field_name] is False
            for field_name in ("credential_loading_attempted", "env_file_read_attempted", "secret_request_attempted")
        ),
        "no_data_provider_or_network_calls": all(
            gate.safety[field_name] is False
            for field_name in ("data_provider_call_attempted", "external_network_call_attempted", "real_data_fetch_attempted")
        ),
        "no_broker_actions_order_paths_or_state_mutation": all(
            gate.safety[field_name] is False for field_name in REQUIRED_DISABLED_FLAGS
        ),
        "advancement_not_authorized": gate.safety["advancement_authorized"] is False,
        "live_trading_disabled": gate.safety["LIVE TRADING"] == "DISABLED",
        "human_review_required": gate.label == HUMAN_REVIEW_REQUIRED,
    }


def _record_payload(record: SnapshotIntakeReviewRecord) -> dict[str, Any]:
    return {
        "snapshot_path": record.snapshot_path,
        "br26_report_path": record.br26_report_path,
        "label": record.label,
        "accepted_as_research_evidence": record.accepted_as_research_evidence,
        "advancement_allowed": record.advancement_allowed,
        "separate_review_decision_required": record.separate_review_decision_required,
        "checks": record.checks,
        "rejection_evidence": record.rejection_evidence,
        "unresolved_blockers": record.unresolved_blockers,
        "required_human_review_actions": record.required_human_review_actions,
        "observation_timestamps": record.observation_timestamps,
        "source_evidence": record.source_evidence,
        "snapshot_summary": record.snapshot_summary,
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


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_disabled_safety(manifest: dict[str, Any]) -> None:
    for field_name in REQUIRED_DISABLED_FLAGS:
        if manifest.get(field_name) is not False:
            raise ValueError(f"BR-27 review gate cannot set {field_name}")
    for field_name in (
        "advancement_authorized",
        "live_state_mutation_allowed",
        "paper_state_mutation_allowed",
        "broker_state_mutation_allowed",
        "routing_state_mutation_allowed",
        "broker_write_operations_authorized",
        "external_routing_paths_authorized",
        "data_provider_calls_authorized",
    ):
        if manifest.get(field_name) is not False:
            raise ValueError(f"BR-27 review gate cannot allow {field_name}")
    if manifest.get("LIVE TRADING") != "DISABLED":
        raise ValueError("BR-27 review gate must keep LIVE TRADING disabled")
