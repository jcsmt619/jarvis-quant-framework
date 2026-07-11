from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


PHASE_ID = "BR-26"
MODULE_NAME = "Read Only Data Snapshot Import Contract"
DEFAULT_REPORT_DIR = Path("reports/br26_read_only_data_snapshot_import_contract")
JSON_REPORT_NAME = "read_only_data_snapshot_import_contract.json"
MARKDOWN_REPORT_NAME = "read_only_data_snapshot_import_contract.md"
DEFAULT_FIXTURE_PATH = Path("engines/moonshot/deterministic/fixtures/br26_read_only_data_snapshot_valid.json")
DEFAULT_APPROVED_SNAPSHOT_PATHS = (DEFAULT_FIXTURE_PATH,)
REQUIRED_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
REQUIRED_TOP_LEVEL_FIELDS = (
    "snapshot_version",
    "snapshot_id",
    "generated_at",
    "freshness_as_of",
    "source_kind",
    "data_domain",
    "provenance",
    "symbols",
    "records",
    "safety",
    "redaction",
    "labels",
)
REQUIRED_PROVENANCE_FIELDS = (
    "provider_name",
    "provider_dataset",
    "source_file_name",
    "acquisition_method",
    "collector",
    "collected_at",
    "checksum_sha256",
    "schema_name",
    "quality_score",
)
REQUIRED_RECORD_FIELDS = (
    "symbol",
    "timestamp",
    "open",
    "high",
    "low",
    "close",
    "volume",
)
REDACTED_FIELDS = (
    "api_key",
    "oauth_token",
    "password",
    "private_key",
    "secret",
    "broker_credentials",
    "account_id",
    "account_number",
)
REJECTION_REASONS = (
    "snapshot_file_not_approved",
    "snapshot_file_missing",
    "snapshot_json_malformed",
    "snapshot_not_object",
    "snapshot_missing_required_field",
    "snapshot_schema_malformed",
    "snapshot_stale",
    "snapshot_low_provenance",
    "snapshot_contains_unredacted_sensitive_field",
    "snapshot_contains_unsafe_runtime_state",
    "snapshot_checksum_mismatch",
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
    "paper_state_mutation_attempted",
    "paper_state_mutation_allowed",
    "live_trading_enabled",
)


@dataclass(frozen=True)
class SnapshotValidationRule:
    name: str
    description: str
    failure_reason: str
    failure_label: str = BLOCKED_BY_SAFETY_GATE

    def validate(self) -> None:
        if self.failure_reason not in REJECTION_REASONS:
            raise ValueError("BR-26 validation rule must use a known rejection reason")
        if self.failure_label != BLOCKED_BY_SAFETY_GATE:
            raise ValueError("BR-26 validation rule failures must be blocked by safety gate")


@dataclass(frozen=True)
class SnapshotImportDecision:
    path: str
    approved: bool
    accepted: bool
    label: str
    reasons: tuple[str, ...]
    snapshot_id: str | None = None
    data_domain: str | None = None
    symbol_count: int = 0
    record_count: int = 0
    freshness_as_of: str | None = None
    provenance_quality_score: float | None = None
    checksum_sha256: str | None = None

    def validate(self) -> None:
        if self.accepted:
            if not self.approved or self.reasons:
                raise ValueError("BR-26 accepted snapshots cannot include rejection reasons")
            if self.label != HUMAN_REVIEW_REQUIRED:
                raise ValueError("BR-26 accepted snapshots must remain human-review-required")
        else:
            if self.label != BLOCKED_BY_SAFETY_GATE:
                raise ValueError("BR-26 rejected snapshots must be blocked by safety gate")
            for reason in self.reasons:
                if reason not in REJECTION_REASONS:
                    raise ValueError("BR-26 rejection reason is not recognized")


@dataclass(frozen=True)
class ReadOnlyDataSnapshotImportContract:
    as_of: datetime
    approved_snapshot_paths: tuple[str, ...]
    validation_rules: tuple[SnapshotValidationRule, ...]
    import_decisions: tuple[SnapshotImportDecision, ...]
    schema: dict[str, Any]
    redaction_rules: tuple[str, ...]
    rejection_reasons: tuple[str, ...]
    safety: dict[str, Any]
    label: str = HUMAN_REVIEW_REQUIRED

    def validate(self) -> None:
        if self.label != HUMAN_REVIEW_REQUIRED:
            raise ValueError("BR-26 import contract must require human review")
        if not self.approved_snapshot_paths:
            raise ValueError("BR-26 import contract requires at least one approved file path")
        if self.redaction_rules != REDACTED_FIELDS:
            raise ValueError("BR-26 redaction rules must remain deterministic")
        if self.rejection_reasons != REJECTION_REASONS:
            raise ValueError("BR-26 rejection reasons must remain deterministic")
        if set(self.schema["required_top_level_fields"]) != set(REQUIRED_TOP_LEVEL_FIELDS):
            raise ValueError("BR-26 schema must include every top-level field")
        for rule in self.validation_rules:
            rule.validate()
        for decision in self.import_decisions:
            decision.validate()
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
        "file_based": True,
        "offline_by_default": True,
        "read_only_import_contract": True,
        "fixture_testable": True,
        "approved_files_only": True,
        "deterministic_validation_only": True,
        "report_artifacts_only": True,
        "live_state_mutation_allowed": False,
        "paper_state_mutation_allowed": False,
        "broker_state_mutation_allowed": False,
        "routing_state_mutation_allowed": False,
        "account_imports_allowed": False,
        "broker_actions_authorized": False,
        "order_paths_authorized": False,
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


def import_read_only_data_snapshot(
    snapshot_path: Path,
    approved_snapshot_paths: tuple[Path, ...] = DEFAULT_APPROVED_SNAPSHOT_PATHS,
    as_of: datetime | None = None,
    max_age: timedelta = timedelta(days=3),
    min_quality_score: float = 0.8,
) -> SnapshotImportDecision:
    approved = _path_is_approved(snapshot_path, approved_snapshot_paths)
    if not approved:
        return _reject(snapshot_path, approved, ("snapshot_file_not_approved",))
    if not snapshot_path.exists():
        return _reject(snapshot_path, approved, ("snapshot_file_missing",))

    try:
        raw_text = snapshot_path.read_text(encoding="utf-8")
        payload = json.loads(raw_text)
    except json.JSONDecodeError:
        return _reject(snapshot_path, approved, ("snapshot_json_malformed",))
    if not isinstance(payload, dict):
        return _reject(snapshot_path, approved, ("snapshot_not_object",))

    reasons = _snapshot_rejection_reasons(payload, snapshot_path, raw_text, as_of, max_age, min_quality_score)
    if reasons:
        return _reject(snapshot_path, approved, reasons, payload)

    provenance = payload["provenance"]
    decision = SnapshotImportDecision(
        path=str(snapshot_path),
        approved=True,
        accepted=True,
        label=HUMAN_REVIEW_REQUIRED,
        reasons=(),
        snapshot_id=str(payload["snapshot_id"]),
        data_domain=str(payload["data_domain"]),
        symbol_count=len(payload["symbols"]),
        record_count=len(payload["records"]),
        freshness_as_of=str(payload["freshness_as_of"]),
        provenance_quality_score=float(provenance["quality_score"]),
        checksum_sha256=str(provenance["checksum_sha256"]),
    )
    decision.validate()
    return decision


def build_read_only_data_snapshot_import_contract(
    snapshot_paths: tuple[Path, ...] = DEFAULT_APPROVED_SNAPSHOT_PATHS,
    approved_snapshot_paths: tuple[Path, ...] = DEFAULT_APPROVED_SNAPSHOT_PATHS,
    as_of: datetime | None = None,
) -> ReadOnlyDataSnapshotImportContract:
    resolved_as_of = as_of or datetime.now(timezone.utc).replace(microsecond=0)
    decisions = tuple(
        import_read_only_data_snapshot(path, approved_snapshot_paths, as_of=resolved_as_of)
        for path in snapshot_paths
    )
    contract = ReadOnlyDataSnapshotImportContract(
        as_of=resolved_as_of,
        approved_snapshot_paths=tuple(str(path) for path in approved_snapshot_paths),
        validation_rules=_validation_rules(),
        import_decisions=decisions,
        schema=_schema_contract(),
        redaction_rules=REDACTED_FIELDS,
        rejection_reasons=REJECTION_REASONS,
        safety=safety_manifest(),
    )
    contract.validate()
    return contract


def read_only_data_snapshot_import_contract_payload(
    contract: ReadOnlyDataSnapshotImportContract,
) -> dict[str, Any]:
    contract.validate()
    decisions = tuple(_decision_payload(decision) for decision in contract.import_decisions)
    accepted = tuple(decision for decision in decisions if decision["accepted"])
    rejected = tuple(decision for decision in decisions if not decision["accepted"])
    acceptance = _acceptance_criteria(contract)
    return {
        "phase": PHASE_ID,
        "module": MODULE_NAME,
        "as_of": contract.as_of.isoformat(),
        "label": contract.label,
        "approved_snapshot_paths": contract.approved_snapshot_paths,
        "schema": contract.schema,
        "validation_rules": tuple(_rule_payload(rule) for rule in contract.validation_rules),
        "redaction_rules": contract.redaction_rules,
        "rejection_reasons": contract.rejection_reasons,
        "safety": contract.safety,
        "import_decisions": decisions,
        "accepted_snapshots": accepted,
        "rejected_snapshots": rejected,
        "metrics": {
            "approved_file_count": len(contract.approved_snapshot_paths),
            "validation_rule_count": len(contract.validation_rules),
            "redaction_rule_count": len(contract.redaction_rules),
            "rejection_reason_count": len(contract.rejection_reasons),
            "import_decision_count": len(decisions),
            "accepted_snapshot_count": len(accepted),
            "rejected_snapshot_count": len(rejected),
            "acceptance_criteria_count": len(acceptance),
            "acceptance_criteria_passed_count": sum(1 for passed in acceptance.values() if passed),
        },
        "acceptance_criteria": acceptance,
        "readiness_state": {
            "state": "READ_ONLY_DATA_SNAPSHOT_IMPORT_CONTRACT_ONLY",
            "future_snapshot_import_contract_defined": True,
            "file_based": True,
            "offline_by_default": True,
            "deterministic_validation_only": True,
            "fixture_testable": True,
            "manual_review_required": True,
            "ready_for_live_trading": False,
            "account_imports_allowed": False,
            "broker_actions_allowed": False,
            "order_paths_allowed": False,
            "data_provider_calls_allowed": False,
        },
    }


def render_markdown_read_only_data_snapshot_import_contract(
    contract: ReadOnlyDataSnapshotImportContract,
) -> str:
    payload = read_only_data_snapshot_import_contract_payload(contract)
    lines = [
        f"# {PHASE_ID} {MODULE_NAME}",
        "",
        "Research labels: " + ", ".join(REQUIRED_LABELS),
        "LIVE TRADING: DISABLED",
        "",
        "## Approved Files",
    ]
    for path in payload["approved_snapshot_paths"]:
        lines.append(f"- {path}")

    lines.extend(["", "## Schema"])
    lines.append("- required_top_level_fields: " + ", ".join(payload["schema"]["required_top_level_fields"]))
    lines.append("- required_provenance_fields: " + ", ".join(payload["schema"]["required_provenance_fields"]))
    lines.append("- required_record_fields: " + ", ".join(payload["schema"]["required_record_fields"]))

    lines.extend(["", "## Validation Rules"])
    for rule in payload["validation_rules"]:
        lines.append(f"- {rule['name']}: {rule['failure_reason']}")

    lines.extend(["", "## Import Decisions"])
    for decision in payload["import_decisions"]:
        reason_text = ", ".join(decision["reasons"]) if decision["reasons"] else "accepted"
        lines.append(f"- {decision['path']}: accepted={decision['accepted']} label={decision['label']} reasons={reason_text}")

    lines.extend(["", "## Rejection Reasons"])
    for reason in REJECTION_REASONS:
        lines.append(f"- {reason}")

    lines.extend(["", "## Redaction Rules"])
    for field_name in REDACTED_FIELDS:
        lines.append(f"- {field_name}")

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
            "- The contract is file-based, offline by default, deterministic, fixture-testable, and report-only.",
            "- No .env reads, credentials, secrets, data-provider calls, broker connections, account imports, broker actions, order paths, state mutation, or live trading enablement.",
            "- Imported snapshots remain research evidence only and require human review before any downstream use.",
        ]
    )
    return "\n".join(lines)


def write_read_only_data_snapshot_import_contract(
    contract: ReadOnlyDataSnapshotImportContract,
    out_dir: Path = DEFAULT_REPORT_DIR,
) -> tuple[Path, Path]:
    contract.validate()
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_REPORT_NAME
    markdown_path = out_dir / MARKDOWN_REPORT_NAME
    json_path.write_text(
        json.dumps(read_only_data_snapshot_import_contract_payload(contract), indent=2, default=str),
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown_read_only_data_snapshot_import_contract(contract), encoding="utf-8")
    return json_path, markdown_path


def run_read_only_data_snapshot_import_contract(
    snapshot_paths: tuple[Path, ...] = DEFAULT_APPROVED_SNAPSHOT_PATHS,
    approved_snapshot_paths: tuple[Path, ...] = DEFAULT_APPROVED_SNAPSHOT_PATHS,
    out_dir: Path = DEFAULT_REPORT_DIR,
    as_of: datetime | None = None,
) -> ReadOnlyDataSnapshotImportContract:
    contract = build_read_only_data_snapshot_import_contract(
        snapshot_paths=snapshot_paths,
        approved_snapshot_paths=approved_snapshot_paths,
        as_of=as_of,
    )
    write_read_only_data_snapshot_import_contract(contract, out_dir=out_dir)
    return contract


def _validation_rules() -> tuple[SnapshotValidationRule, ...]:
    return (
        SnapshotValidationRule("approved_file", "Snapshot path must be explicitly approved.", "snapshot_file_not_approved"),
        SnapshotValidationRule("file_exists", "Snapshot file must exist locally.", "snapshot_file_missing"),
        SnapshotValidationRule("json_object", "Snapshot must be a JSON object.", "snapshot_not_object"),
        SnapshotValidationRule("required_fields", "Snapshot must include every required schema field.", "snapshot_missing_required_field"),
        SnapshotValidationRule("record_schema", "Snapshot records must use deterministic OHLCV fields.", "snapshot_schema_malformed"),
        SnapshotValidationRule("freshness", "Snapshot freshness timestamp must be within the max age window.", "snapshot_stale"),
        SnapshotValidationRule("provenance", "Snapshot provenance must be complete and high quality.", "snapshot_low_provenance"),
        SnapshotValidationRule("redaction", "Snapshot must not contain unredacted sensitive fields.", "snapshot_contains_unredacted_sensitive_field"),
        SnapshotValidationRule("runtime_safety", "Snapshot must not contain unsafe runtime state.", "snapshot_contains_unsafe_runtime_state"),
        SnapshotValidationRule("checksum", "Snapshot checksum must match the canonical content hash.", "snapshot_checksum_mismatch"),
    )


def _schema_contract() -> dict[str, Any]:
    return {
        "format": "json",
        "snapshot_version": "1",
        "required_top_level_fields": REQUIRED_TOP_LEVEL_FIELDS,
        "required_provenance_fields": REQUIRED_PROVENANCE_FIELDS,
        "required_record_fields": REQUIRED_RECORD_FIELDS,
        "allowed_source_kind": "approved_offline_file",
        "allowed_data_domains": ("daily_ohlcv", "options_chain_summary", "macro_series_snapshot"),
        "freshness_max_age_days": 3,
        "min_provenance_quality_score": 0.8,
    }


def _snapshot_rejection_reasons(
    payload: dict[str, Any],
    path: Path,
    raw_text: str,
    as_of: datetime | None,
    max_age: timedelta,
    min_quality_score: float,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if any(field_name not in payload for field_name in REQUIRED_TOP_LEVEL_FIELDS):
        reasons.append("snapshot_missing_required_field")
    if not _schema_is_well_formed(payload):
        reasons.append("snapshot_schema_malformed")
    if _snapshot_is_stale(payload, as_of, max_age):
        reasons.append("snapshot_stale")
    if _provenance_is_low_quality(payload, path, min_quality_score):
        reasons.append("snapshot_low_provenance")
    if _contains_sensitive_field(payload):
        reasons.append("snapshot_contains_unredacted_sensitive_field")
    if _contains_unsafe_runtime_state(payload):
        reasons.append("snapshot_contains_unsafe_runtime_state")
    if not _checksum_matches(payload, raw_text):
        reasons.append("snapshot_checksum_mismatch")
    return tuple(dict.fromkeys(reasons))


def _schema_is_well_formed(payload: dict[str, Any]) -> bool:
    if payload.get("snapshot_version") != "1":
        return False
    if payload.get("source_kind") != "approved_offline_file":
        return False
    if not isinstance(payload.get("symbols"), list) or not payload.get("symbols"):
        return False
    if not isinstance(payload.get("records"), list) or not payload.get("records"):
        return False
    if not isinstance(payload.get("provenance"), dict):
        return False
    if not isinstance(payload.get("safety"), dict):
        return False
    if not isinstance(payload.get("redaction"), dict):
        return False
    if not isinstance(payload.get("labels"), list):
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
        for numeric_field in ("open", "high", "low", "close"):
            if not isinstance(record[numeric_field], (int, float)) or record[numeric_field] <= 0:
                return False
        if not isinstance(record["volume"], int) or record["volume"] < 0:
            return False
    return True


def _snapshot_is_stale(payload: dict[str, Any], as_of: datetime | None, max_age: timedelta) -> bool:
    freshness_text = payload.get("freshness_as_of")
    if not isinstance(freshness_text, str):
        return True
    freshness_at = _parse_datetime(freshness_text)
    if freshness_at is None:
        return True
    reference_time = as_of or datetime.now(timezone.utc).replace(microsecond=0)
    return reference_time - freshness_at > max_age


def _provenance_is_low_quality(payload: dict[str, Any], path: Path, min_quality_score: float) -> bool:
    provenance = payload.get("provenance")
    if not isinstance(provenance, dict):
        return True
    if any(field_name not in provenance for field_name in REQUIRED_PROVENANCE_FIELDS):
        return True
    if provenance.get("acquisition_method") != "offline_file_export":
        return True
    if provenance.get("source_file_name") != path.name:
        return True
    quality_score = provenance.get("quality_score")
    if not isinstance(quality_score, (int, float)) or float(quality_score) < min_quality_score:
        return True
    for field_name in REQUIRED_PROVENANCE_FIELDS:
        if provenance.get(field_name) in ("", None):
            return True
    return False


def _contains_sensitive_field(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).lower()
            if normalized in REDACTED_FIELDS:
                return True
            if _contains_sensitive_field(child):
                return True
    elif isinstance(value, list):
        return any(_contains_sensitive_field(item) for item in value)
    return False


def _contains_unsafe_runtime_state(payload: dict[str, Any]) -> bool:
    safety = payload.get("safety")
    if not isinstance(safety, dict):
        return True
    if safety.get("LIVE TRADING") != "DISABLED":
        return True
    for field_name in REQUIRED_DISABLED_FLAGS:
        if safety.get(field_name) is not False:
            return True
    unsafe_sections = ("account", "account_import", "broker_connection", "broker_action", "order_path", "live_state")
    return any(section in payload for section in unsafe_sections)


def _checksum_matches(payload: dict[str, Any], raw_text: str) -> bool:
    provenance = payload.get("provenance")
    if not isinstance(provenance, dict):
        return False
    expected = provenance.get("checksum_sha256")
    if not isinstance(expected, str) or len(expected) != 64:
        return False
    canonical_payload = json.loads(raw_text)
    canonical_payload["provenance"] = dict(canonical_payload.get("provenance", {}))
    canonical_payload["provenance"]["checksum_sha256"] = "0" * 64
    canonical_text = json.dumps(canonical_payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_text.encode("utf-8")).hexdigest() == expected


def _path_is_approved(path: Path, approved_paths: tuple[Path, ...]) -> bool:
    return path.resolve() in {approved_path.resolve() for approved_path in approved_paths}


def _reject(
    path: Path,
    approved: bool,
    reasons: tuple[str, ...],
    payload: dict[str, Any] | None = None,
) -> SnapshotImportDecision:
    provenance = payload.get("provenance", {}) if isinstance(payload, dict) else {}
    decision = SnapshotImportDecision(
        path=str(path),
        approved=approved,
        accepted=False,
        label=BLOCKED_BY_SAFETY_GATE,
        reasons=reasons,
        snapshot_id=str(payload.get("snapshot_id")) if isinstance(payload, dict) and payload.get("snapshot_id") else None,
        data_domain=str(payload.get("data_domain")) if isinstance(payload, dict) and payload.get("data_domain") else None,
        symbol_count=len(payload.get("symbols", [])) if isinstance(payload, dict) and isinstance(payload.get("symbols"), list) else 0,
        record_count=len(payload.get("records", [])) if isinstance(payload, dict) and isinstance(payload.get("records"), list) else 0,
        freshness_as_of=str(payload.get("freshness_as_of")) if isinstance(payload, dict) and payload.get("freshness_as_of") else None,
        provenance_quality_score=float(provenance["quality_score"])
        if isinstance(provenance, dict) and isinstance(provenance.get("quality_score"), (int, float))
        else None,
        checksum_sha256=str(provenance.get("checksum_sha256"))
        if isinstance(provenance, dict) and provenance.get("checksum_sha256")
        else None,
    )
    decision.validate()
    return decision


def _acceptance_criteria(contract: ReadOnlyDataSnapshotImportContract) -> dict[str, bool]:
    return {
        "approved_files_declared": bool(contract.approved_snapshot_paths),
        "schema_fields_declared": set(contract.schema["required_top_level_fields"]) == set(REQUIRED_TOP_LEVEL_FIELDS),
        "validation_rules_cover_rejections": {rule.failure_reason for rule in contract.validation_rules}.issubset(REJECTION_REASONS),
        "redaction_rules_declared": set(REDACTED_FIELDS).issubset(set(contract.redaction_rules)),
        "all_decisions_validated": all(isinstance(decision, SnapshotImportDecision) for decision in contract.import_decisions),
        "accepted_snapshots_remain_human_review_required": all(
            decision.label == HUMAN_REVIEW_REQUIRED for decision in contract.import_decisions if decision.accepted
        ),
        "rejected_snapshots_blocked_by_safety_gate": all(
            decision.label == BLOCKED_BY_SAFETY_GATE for decision in contract.import_decisions if not decision.accepted
        ),
        "no_credentials_or_secrets": all(
            contract.safety[field_name] is False
            for field_name in ("credential_loading_attempted", "env_file_read_attempted", "secret_request_attempted")
        ),
        "no_data_provider_or_network_calls": all(
            contract.safety[field_name] is False
            for field_name in ("data_provider_call_attempted", "external_network_call_attempted", "real_data_fetch_attempted")
        ),
        "no_broker_actions_order_paths_or_state_mutation": all(
            contract.safety[field_name] is False for field_name in REQUIRED_DISABLED_FLAGS
        ),
        "account_imports_blocked": contract.safety["account_imports_allowed"] is False,
        "live_trading_disabled": contract.safety["LIVE TRADING"] == "DISABLED",
    }


def _rule_payload(rule: SnapshotValidationRule) -> dict[str, Any]:
    return {
        "name": rule.name,
        "description": rule.description,
        "failure_reason": rule.failure_reason,
        "failure_label": rule.failure_label,
    }


def _decision_payload(decision: SnapshotImportDecision) -> dict[str, Any]:
    return {
        "path": decision.path,
        "approved": decision.approved,
        "accepted": decision.accepted,
        "label": decision.label,
        "reasons": decision.reasons,
        "snapshot_id": decision.snapshot_id,
        "data_domain": decision.data_domain,
        "symbol_count": decision.symbol_count,
        "record_count": decision.record_count,
        "freshness_as_of": decision.freshness_as_of,
        "provenance_quality_score": decision.provenance_quality_score,
        "checksum_sha256": decision.checksum_sha256,
    }


def _parse_datetime(value: str) -> datetime | None:
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
            raise ValueError(f"BR-26 import contract cannot set {field_name}")
    for field_name in (
        "live_state_mutation_allowed",
        "broker_state_mutation_allowed",
        "routing_state_mutation_allowed",
        "account_imports_allowed",
        "broker_actions_authorized",
        "order_paths_authorized",
        "data_provider_calls_authorized",
    ):
        if manifest.get(field_name) is not False:
            raise ValueError(f"BR-26 import contract cannot allow {field_name}")
    if manifest.get("LIVE TRADING") != "DISABLED":
        raise ValueError("BR-26 import contract must keep LIVE TRADING disabled")
