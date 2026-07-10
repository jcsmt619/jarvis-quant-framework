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


PHASE_ID = "BR-16"
MODULE_NAME = "Fixture to Real Data Boundary Design"
DEFAULT_FIXTURE_PATH = Path("engines/moonshot/deterministic/fixtures/br16_fixture_to_real_data_boundary.json")
DEFAULT_REPORT_DIR = Path("reports/br16_fixture_to_real_data_boundary")
REQUIRED_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
SAFE_ACTION_LABELS = REQUIRED_LABELS
REQUIRED_DISABLED_FLAGS = (
    "credential_loading_attempted",
    "env_file_read_attempted",
    "secret_request_attempted",
    "external_network_call_attempted",
    "broker_connection_attempted",
    "broker_read_call_performed",
    "real_data_fetch_attempted",
    "real_paper_wrapper_connected",
    "real_paper_wrapper_attempted",
    "real_paper_order_submitted",
    "broker_order_call_performed",
    "broker_order_submitted",
    "broker_order_routing_enabled",
    "live_trading_enabled",
)
REDACTED_FIELDS = (
    "api_key",
    "secret",
    "token",
    "password",
    "oauth",
    "private_key",
    "account_id",
)


@dataclass(frozen=True)
class BoundaryInterface:
    name: str
    purpose: str
    mode: str
    allowed_inputs: tuple[str, ...]
    prohibited_inputs: tuple[str, ...]
    output_schema: str
    label: str = MONITOR_ONLY

    def validate(self) -> None:
        _require_text("interface name", self.name)
        _require_text("interface purpose", self.purpose)
        if self.mode not in {"fixture_default", "read_only_real_data_design"}:
            raise ValueError("boundary interface mode must be fixture_default or read_only_real_data_design")
        if not self.allowed_inputs:
            raise ValueError("boundary interface requires allowed inputs")
        if not self.prohibited_inputs:
            raise ValueError("boundary interface requires prohibited inputs")
        if not {"credentials", "env_file"}.issubset(set(self.prohibited_inputs)):
            raise ValueError("boundary interface must prohibit credentials and env_file inputs")
        if not any("broker" in item for item in self.prohibited_inputs):
            raise ValueError("boundary interface must prohibit broker inputs")
        if not any("order" in item for item in self.prohibited_inputs):
            raise ValueError("boundary interface must prohibit order inputs")
        if not self.output_schema:
            raise ValueError("boundary interface requires output schema")
        _require_safe_label(self.label)


@dataclass(frozen=True)
class BoundaryValidationRule:
    rule_id: str
    field: str
    check: str
    failure_label: str = BLOCKED_BY_SAFETY_GATE
    human_review_required: bool = True

    def validate(self) -> None:
        _require_text("rule_id", self.rule_id)
        _require_text("field", self.field)
        _require_text("check", self.check)
        if self.failure_label != BLOCKED_BY_SAFETY_GATE:
            raise ValueError("validation failures must be blocked by safety gate")
        if not self.human_review_required:
            raise ValueError("validation rules must require human review")


@dataclass(frozen=True)
class BoundarySchema:
    name: str
    required_fields: tuple[str, ...]
    optional_fields: tuple[str, ...]
    redacted_fields: tuple[str, ...]
    version: str

    def validate(self) -> None:
        _require_text("schema name", self.name)
        _require_text("schema version", self.version)
        if not self.required_fields:
            raise ValueError("boundary schema requires fields")
        if not set(self.redacted_fields).issubset(set(REDACTED_FIELDS)):
            raise ValueError("boundary schema redacted fields must use approved redaction names")


@dataclass(frozen=True)
class BoundaryStalenessRule:
    data_type: str
    max_age_seconds: int
    fallback_on_stale: str
    failure_label: str = BLOCKED_BY_SAFETY_GATE

    def validate(self) -> None:
        _require_text("data_type", self.data_type)
        if self.max_age_seconds <= 0:
            raise ValueError("staleness max_age_seconds must be positive")
        if self.fallback_on_stale not in {"use_fixture_snapshot", "block_record", "skip_symbol"}:
            raise ValueError("unsupported stale-data fallback")
        if self.failure_label != BLOCKED_BY_SAFETY_GATE:
            raise ValueError("stale data must be blocked by safety gate")


@dataclass(frozen=True)
class BoundaryProvenanceRecord:
    source_type: str
    source_name: str
    capture_method: str
    credential_required: bool
    read_only: bool
    recorded_fields: tuple[str, ...]

    def validate(self) -> None:
        if self.source_type not in {"fixture", "real_data_design"}:
            raise ValueError("provenance source_type must be fixture or real_data_design")
        _require_text("source_name", self.source_name)
        _require_text("capture_method", self.capture_method)
        if self.credential_required:
            raise ValueError("BR-16 default provenance cannot require credentials")
        if not self.read_only:
            raise ValueError("BR-16 provenance must be read-only")
        if not self.recorded_fields:
            raise ValueError("provenance requires recorded fields")


@dataclass(frozen=True)
class BoundaryCachePolicy:
    cache_name: str
    write_scope: str
    read_scope: str
    ttl_seconds: int
    fallback_behavior: str

    def validate(self) -> None:
        _require_text("cache_name", self.cache_name)
        if self.write_scope != "local_artifact_only":
            raise ValueError("BR-16 cache writes must be local artifacts only")
        if self.read_scope != "offline_tests_and_read_only_inputs":
            raise ValueError("BR-16 cache reads must be offline tests and read-only inputs")
        if self.ttl_seconds <= 0:
            raise ValueError("cache ttl_seconds must be positive")
        if self.fallback_behavior != "preserve_last_valid_fixture":
            raise ValueError("cache fallback must preserve last valid fixture")


@dataclass(frozen=True)
class FixtureRealDataBoundaryReport:
    as_of: datetime
    interfaces: tuple[BoundaryInterface, ...]
    validation_rules: tuple[BoundaryValidationRule, ...]
    schemas: tuple[BoundarySchema, ...]
    staleness_rules: tuple[BoundaryStalenessRule, ...]
    provenance_records: tuple[BoundaryProvenanceRecord, ...]
    cache_policies: tuple[BoundaryCachePolicy, ...]
    fallback_behaviors: tuple[str, ...]
    redaction_rules: tuple[str, ...]
    test_fixtures: tuple[str, ...]
    safety: dict[str, Any]
    label: str = HUMAN_REVIEW_REQUIRED

    def validate(self) -> None:
        if self.label != HUMAN_REVIEW_REQUIRED:
            raise ValueError("BR-16 boundary design must require human review")
        for collection_name, collection in (
            ("interfaces", self.interfaces),
            ("validation_rules", self.validation_rules),
            ("schemas", self.schemas),
            ("staleness_rules", self.staleness_rules),
            ("provenance_records", self.provenance_records),
            ("cache_policies", self.cache_policies),
            ("fallback_behaviors", self.fallback_behaviors),
            ("redaction_rules", self.redaction_rules),
            ("test_fixtures", self.test_fixtures),
        ):
            if not collection:
                raise ValueError(f"BR-16 requires {collection_name}")
        for item in self.interfaces:
            item.validate()
        for item in self.validation_rules:
            item.validate()
        for item in self.schemas:
            item.validate()
        for item in self.staleness_rules:
            item.validate()
        for item in self.provenance_records:
            item.validate()
        for item in self.cache_policies:
            item.validate()
        if not set(REDACTED_FIELDS).issubset(set(self.redaction_rules)):
            raise ValueError("BR-16 redaction rules must include all approved sensitive fields")
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
        "fixture_data_default": True,
        "offline_tests_preserved": True,
        "read_only_real_data_design_only": True,
        "credential_loading_attempted": False,
        "env_file_read_attempted": False,
        "secret_request_attempted": False,
        "external_network_call_attempted": False,
        "broker_connection_attempted": False,
        "broker_read_call_performed": False,
        "real_data_fetch_attempted": False,
        "real_paper_wrapper_connected": False,
        "real_paper_wrapper_attempted": False,
        "real_paper_order_submitted": False,
        "broker_order_call_performed": False,
        "broker_order_submitted": False,
        "broker_order_routing_enabled": False,
        "live_trading_enabled": False,
        "LIVE TRADING": "DISABLED",
    }


def load_boundary_fixture(path: Path = DEFAULT_FIXTURE_PATH) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("BR-16 fixture must be a JSON object")
    return payload


def build_fixture_to_real_data_boundary_report(
    fixture_path: Path = DEFAULT_FIXTURE_PATH,
    as_of: datetime | None = None,
) -> FixtureRealDataBoundaryReport:
    payload = load_boundary_fixture(fixture_path)
    report = FixtureRealDataBoundaryReport(
        as_of=as_of or datetime.now(timezone.utc).replace(microsecond=0),
        interfaces=tuple(_interface_from_payload(item) for item in payload["interfaces"]),
        validation_rules=tuple(_validation_rule_from_payload(item) for item in payload["validation_rules"]),
        schemas=tuple(_schema_from_payload(item) for item in payload["schemas"]),
        staleness_rules=tuple(_staleness_rule_from_payload(item) for item in payload["staleness_rules"]),
        provenance_records=tuple(_provenance_from_payload(item) for item in payload["provenance_records"]),
        cache_policies=tuple(_cache_policy_from_payload(item) for item in payload["cache_policies"]),
        fallback_behaviors=tuple(payload["fallback_behaviors"]),
        redaction_rules=tuple(payload["redaction_rules"]),
        test_fixtures=tuple(payload["test_fixtures"]),
        safety=safety_manifest(),
    )
    report.validate()
    return report


def fixture_to_real_data_boundary_payload(report: FixtureRealDataBoundaryReport) -> dict[str, Any]:
    report.validate()
    return {
        "phase": PHASE_ID,
        "module": MODULE_NAME,
        "as_of": report.as_of.isoformat(),
        "label": report.label,
        "safety": report.safety,
        "metrics": {
            "interface_count": len(report.interfaces),
            "validation_rule_count": len(report.validation_rules),
            "schema_count": len(report.schemas),
            "staleness_rule_count": len(report.staleness_rules),
            "provenance_record_count": len(report.provenance_records),
            "cache_policy_count": len(report.cache_policies),
            "fallback_behavior_count": len(report.fallback_behaviors),
            "redaction_rule_count": len(report.redaction_rules),
            "test_fixture_count": len(report.test_fixtures),
        },
        "interfaces": [_interface_payload(item) for item in report.interfaces],
        "validation_rules": [_validation_rule_payload(item) for item in report.validation_rules],
        "schemas": [_schema_payload(item) for item in report.schemas],
        "staleness_rules": [_staleness_rule_payload(item) for item in report.staleness_rules],
        "provenance_records": [_provenance_payload(item) for item in report.provenance_records],
        "cache_policies": [_cache_policy_payload(item) for item in report.cache_policies],
        "fallback_behaviors": report.fallback_behaviors,
        "redaction_rules": report.redaction_rules,
        "test_fixtures": report.test_fixtures,
        "acceptance_criteria": {
            "fixture_data_remains_default": report.safety["fixture_data_default"] is True,
            "offline_tests_preserved": report.safety["offline_tests_preserved"] is True,
            "read_only_real_data_design_only": report.safety["read_only_real_data_design_only"] is True,
            "no_credentials_or_env_files": all(
                report.safety[field_name] is False
                for field_name in ("credential_loading_attempted", "env_file_read_attempted", "secret_request_attempted")
            ),
            "no_network_or_real_fetch": all(
                report.safety[field_name] is False
                for field_name in ("external_network_call_attempted", "real_data_fetch_attempted")
            ),
            "no_broker_or_order_paths": all(
                report.safety[field_name] is False
                for field_name in (
                    "broker_connection_attempted",
                    "broker_read_call_performed",
                    "broker_order_call_performed",
                    "broker_order_submitted",
                    "broker_order_routing_enabled",
                )
            ),
            "live_trading_disabled": report.safety["LIVE TRADING"] == "DISABLED",
            "human_review_required": report.label == HUMAN_REVIEW_REQUIRED,
        },
    }


def render_markdown_fixture_to_real_data_boundary(report: FixtureRealDataBoundaryReport) -> str:
    payload = fixture_to_real_data_boundary_payload(report)
    lines = [
        f"# {PHASE_ID} {MODULE_NAME}",
        "",
        "Research labels: " + ", ".join(REQUIRED_LABELS),
        "LIVE TRADING: DISABLED",
        "",
        "## Purpose",
        "BR-16 defines the deterministic boundary for eventually replacing fixture/sample market data with read-only market data inputs while preserving offline tests and requiring no credentials by default.",
        "",
        "## Metrics",
    ]
    for name, value in payload["metrics"].items():
        lines.append(f"- {name}: {value}")

    lines.extend(["", "## Interfaces"])
    for item in payload["interfaces"]:
        lines.append(f"- {item['name']}: mode={item['mode']}, schema={item['output_schema']}, label={item['label']}")

    lines.extend(["", "## Validation Rules"])
    for item in payload["validation_rules"]:
        lines.append(f"- {item['rule_id']}: field={item['field']}, check={item['check']}")

    lines.extend(["", "## Schemas"])
    for item in payload["schemas"]:
        lines.append(
            f"- {item['name']}@{item['version']}: required={', '.join(item['required_fields'])}"
        )

    lines.extend(["", "## Staleness Checks"])
    for item in payload["staleness_rules"]:
        lines.append(
            f"- {item['data_type']}: max_age_seconds={item['max_age_seconds']}, fallback={item['fallback_on_stale']}"
        )

    lines.extend(["", "## Provenance Records"])
    for item in payload["provenance_records"]:
        lines.append(
            f"- {item['source_name']}: source_type={item['source_type']}, read_only={item['read_only']}, credential_required={item['credential_required']}"
        )

    lines.extend(["", "## Cache Boundaries"])
    for item in payload["cache_policies"]:
        lines.append(
            f"- {item['cache_name']}: write_scope={item['write_scope']}, read_scope={item['read_scope']}, fallback={item['fallback_behavior']}"
        )

    lines.extend(["", "## Fallback Behavior"])
    for item in payload["fallback_behaviors"]:
        lines.append(f"- {item}")

    lines.extend(["", "## Redaction Rules"])
    for item in payload["redaction_rules"]:
        lines.append(f"- {item}")

    lines.extend(["", "## Test Fixtures"])
    for item in payload["test_fixtures"]:
        lines.append(f"- {item}")

    lines.extend(["", "## Acceptance Criteria"])
    for name, passed in payload["acceptance_criteria"].items():
        lines.append(f"- {name}: {passed}")

    lines.extend(
        [
            "",
            "## Safety Boundaries",
            "- RESEARCH_ONLY; MONITOR_ONLY; PAPER_ONLY; HUMAN_REVIEW_REQUIRED; BLOCKED_BY_SAFETY_GATE.",
            "- Fixture/sample data remains the default input for tests.",
            "- Read-only real-data support is design-only in BR-16.",
            "- No credentials, env file reads, secrets, broker connections, broker calls, order paths, network fetches, or live trading enablement.",
        ]
    )
    return "\n".join(lines)


def write_fixture_to_real_data_boundary_report(
    report: FixtureRealDataBoundaryReport,
    out_dir: Path = DEFAULT_REPORT_DIR,
) -> tuple[Path, Path]:
    report.validate()
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "fixture_to_real_data_boundary.json"
    markdown_path = out_dir / "fixture_to_real_data_boundary.md"
    json_path.write_text(json.dumps(fixture_to_real_data_boundary_payload(report), indent=2, default=str), encoding="utf-8")
    markdown_path.write_text(render_markdown_fixture_to_real_data_boundary(report), encoding="utf-8")
    return json_path, markdown_path


def run_fixture_to_real_data_boundary(
    fixture_path: Path = DEFAULT_FIXTURE_PATH,
    out_dir: Path = DEFAULT_REPORT_DIR,
    as_of: datetime | None = None,
) -> FixtureRealDataBoundaryReport:
    report = build_fixture_to_real_data_boundary_report(fixture_path=fixture_path, as_of=as_of)
    write_fixture_to_real_data_boundary_report(report, out_dir=out_dir)
    return report


def _interface_from_payload(payload: dict[str, Any]) -> BoundaryInterface:
    return BoundaryInterface(
        name=payload["name"],
        purpose=payload["purpose"],
        mode=payload["mode"],
        allowed_inputs=tuple(payload["allowed_inputs"]),
        prohibited_inputs=tuple(payload["prohibited_inputs"]),
        output_schema=payload["output_schema"],
        label=payload.get("label", MONITOR_ONLY),
    )


def _validation_rule_from_payload(payload: dict[str, Any]) -> BoundaryValidationRule:
    return BoundaryValidationRule(
        rule_id=payload["rule_id"],
        field=payload["field"],
        check=payload["check"],
        failure_label=payload.get("failure_label", BLOCKED_BY_SAFETY_GATE),
        human_review_required=bool(payload.get("human_review_required", True)),
    )


def _schema_from_payload(payload: dict[str, Any]) -> BoundarySchema:
    return BoundarySchema(
        name=payload["name"],
        required_fields=tuple(payload["required_fields"]),
        optional_fields=tuple(payload.get("optional_fields", ())),
        redacted_fields=tuple(payload.get("redacted_fields", ())),
        version=payload["version"],
    )


def _staleness_rule_from_payload(payload: dict[str, Any]) -> BoundaryStalenessRule:
    return BoundaryStalenessRule(
        data_type=payload["data_type"],
        max_age_seconds=int(payload["max_age_seconds"]),
        fallback_on_stale=payload["fallback_on_stale"],
        failure_label=payload.get("failure_label", BLOCKED_BY_SAFETY_GATE),
    )


def _provenance_from_payload(payload: dict[str, Any]) -> BoundaryProvenanceRecord:
    return BoundaryProvenanceRecord(
        source_type=payload["source_type"],
        source_name=payload["source_name"],
        capture_method=payload["capture_method"],
        credential_required=bool(payload["credential_required"]),
        read_only=bool(payload["read_only"]),
        recorded_fields=tuple(payload["recorded_fields"]),
    )


def _cache_policy_from_payload(payload: dict[str, Any]) -> BoundaryCachePolicy:
    return BoundaryCachePolicy(
        cache_name=payload["cache_name"],
        write_scope=payload["write_scope"],
        read_scope=payload["read_scope"],
        ttl_seconds=int(payload["ttl_seconds"]),
        fallback_behavior=payload["fallback_behavior"],
    )


def _interface_payload(item: BoundaryInterface) -> dict[str, Any]:
    return {
        "name": item.name,
        "purpose": item.purpose,
        "mode": item.mode,
        "allowed_inputs": item.allowed_inputs,
        "prohibited_inputs": item.prohibited_inputs,
        "output_schema": item.output_schema,
        "label": item.label,
    }


def _validation_rule_payload(item: BoundaryValidationRule) -> dict[str, Any]:
    return {
        "rule_id": item.rule_id,
        "field": item.field,
        "check": item.check,
        "failure_label": item.failure_label,
        "human_review_required": item.human_review_required,
    }


def _schema_payload(item: BoundarySchema) -> dict[str, Any]:
    return {
        "name": item.name,
        "required_fields": item.required_fields,
        "optional_fields": item.optional_fields,
        "redacted_fields": item.redacted_fields,
        "version": item.version,
    }


def _staleness_rule_payload(item: BoundaryStalenessRule) -> dict[str, Any]:
    return {
        "data_type": item.data_type,
        "max_age_seconds": item.max_age_seconds,
        "fallback_on_stale": item.fallback_on_stale,
        "failure_label": item.failure_label,
    }


def _provenance_payload(item: BoundaryProvenanceRecord) -> dict[str, Any]:
    return {
        "source_type": item.source_type,
        "source_name": item.source_name,
        "capture_method": item.capture_method,
        "credential_required": item.credential_required,
        "read_only": item.read_only,
        "recorded_fields": item.recorded_fields,
    }


def _cache_policy_payload(item: BoundaryCachePolicy) -> dict[str, Any]:
    return {
        "cache_name": item.cache_name,
        "write_scope": item.write_scope,
        "read_scope": item.read_scope,
        "ttl_seconds": item.ttl_seconds,
        "fallback_behavior": item.fallback_behavior,
    }


def _validate_disabled_safety(manifest: dict[str, Any]) -> None:
    for field_name in REQUIRED_DISABLED_FLAGS:
        if manifest.get(field_name) is not False:
            raise ValueError(f"BR-16 boundary design cannot set {field_name}")
    if manifest.get("LIVE TRADING") != "DISABLED":
        raise ValueError("BR-16 boundary design must keep LIVE TRADING disabled")


def _require_text(field_name: str, value: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required")


def _require_safe_label(label: str) -> None:
    if label not in SAFE_ACTION_LABELS:
        raise ValueError("label must be a safe research, monitor, paper, review, or blocked label")
