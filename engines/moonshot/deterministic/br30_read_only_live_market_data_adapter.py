from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Protocol

from engines.moonshot.deterministic.br26_read_only_data_snapshot_import_contract import (
    REDACTED_FIELDS,
    REQUIRED_DISABLED_FLAGS,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


PHASE_ID = "BR-30"
MODULE_NAME = "Read Only Live Market Data Adapter"
SNAPSHOT_SCHEMA_NAME = "br26.read_only_data_snapshot.v1"
ADAPTER_SCHEMA_NAME = "br30.read_only_market_data_adapter.v1"
DEFAULT_REPORT_DIR = Path("reports/br30_read_only_live_market_data_adapter")
JSON_REPORT_NAME = "read_only_live_market_data_adapter.json"
MARKDOWN_REPORT_NAME = "read_only_live_market_data_adapter.md"
NORMALIZED_SNAPSHOT_NAME = "br30_normalized_br26_snapshot.json"
DEFAULT_RECORDED_RESPONSE_PATH = Path(
    "engines/moonshot/deterministic/fixtures/br30_tastytrade_recorded_response_valid.json"
)
REQUIRED_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
SUPPORTED_MODES = ("offline", "fixture", "recorded_response")
ADAPTER_CHECKS = (
    "offline_default_fail_closed",
    "provider_interface_declared",
    "runtime_config_external_required",
    "secret_material_absent",
    "raw_evidence_preserved",
    "normalized_snapshot_created",
    "br26_snapshot_schema_compatible",
    "feed_identity_approved",
    "provider_timestamp_valid",
    "exchange_timestamp_valid",
    "acquisition_timestamp_valid",
    "clock_skew_within_limit",
    "quality_flags_accepted",
    "duplicates_rejected",
    "missing_bars_rejected",
    "malformed_payload_rejected",
    "unsafe_capabilities_absent",
)
REJECTION_REASONS = (
    "runtime_mode_not_allowed",
    "runtime_config_missing",
    "runtime_config_inside_repository",
    "runtime_config_contains_secret_material",
    "raw_payload_missing",
    "raw_payload_malformed",
    "provider_identity_mismatch",
    "feed_not_approved",
    "feed_mismatch",
    "schema_version_unsupported",
    "provider_timestamp_invalid",
    "exchange_timestamp_invalid",
    "acquisition_timestamp_invalid",
    "clock_skew_exceeded",
    "stale_data",
    "delayed_feed",
    "low_provenance",
    "low_quality_flag",
    "duplicate_event",
    "missing_bar",
    "incomplete_record",
    "timezone_invalid",
    "reconnect_boundary_open",
    "retry_boundary_exceeded",
    "rate_limit_boundary_exceeded",
    "sandbox_reset_detected",
    "unsafe_capability_present",
    "secret_material_detected",
)
APPROVED_FEEDS = ("tastytrade.market-data.read-only",)
APPROVED_PROVIDER = "tastytrade"
MAX_CLOCK_SKEW = timedelta(seconds=90)
MAX_DATA_AGE = timedelta(minutes=20)
MIN_PROVENANCE_SCORE = 0.85


class ReadOnlyMarketDataProvider(Protocol):
    provider_name: str

    def acquire_snapshot(self, request: "MarketDataRequest") -> "MarketDataAdapterResult":
        """Return read-only market data evidence without account or execution capabilities."""


@dataclass(frozen=True)
class MarketDataRequest:
    symbols: tuple[str, ...]
    mode: str = "offline"
    recorded_response_path: Path | None = None
    runtime_config_path: Path | None = None
    approved_feeds: tuple[str, ...] = APPROVED_FEEDS
    as_of: datetime | None = None

    def validate(self) -> None:
        if self.mode not in SUPPORTED_MODES:
            raise ValueError("BR-30 request mode is not supported")
        if not self.symbols:
            raise ValueError("BR-30 request requires at least one symbol")
        if self.mode == "offline" and (self.recorded_response_path or self.runtime_config_path):
            raise ValueError("BR-30 offline mode cannot include provider paths")


@dataclass(frozen=True)
class MarketDataEvidence:
    provider_name: str
    feed_identity: str
    raw_path: str | None
    raw_checksum_sha256: str | None
    normalized_checksum_sha256: str | None
    provider_timestamp: str | None
    exchange_timestamp: str | None
    acquisition_timestamp: str | None
    schema_version: str | None
    quality_flags: tuple[str, ...]
    provenance_score: float


@dataclass(frozen=True)
class MarketDataAdapterResult:
    as_of: datetime
    request_mode: str
    provider_name: str
    accepted_for_shadow_research: bool
    label: str
    adapter_checks: dict[str, bool]
    rejection_reasons: tuple[str, ...]
    evidence: MarketDataEvidence
    normalized_snapshot: dict[str, Any] | None
    raw_payload_summary: dict[str, Any]
    boundary_evidence: dict[str, Any]
    safety: dict[str, Any]

    def validate(self) -> None:
        if set(self.adapter_checks) != set(ADAPTER_CHECKS):
            raise ValueError("BR-30 result must record every adapter check")
        if self.accepted_for_shadow_research:
            if self.label != HUMAN_REVIEW_REQUIRED:
                raise ValueError("BR-30 accepted data must remain human-review-required")
            if self.rejection_reasons:
                raise ValueError("BR-30 accepted data cannot carry rejection reasons")
            if self.normalized_snapshot is None:
                raise ValueError("BR-30 accepted data requires a normalized snapshot")
        else:
            if self.label != BLOCKED_BY_SAFETY_GATE:
                raise ValueError("BR-30 rejected data must be blocked by safety gate")
            if not self.rejection_reasons:
                raise ValueError("BR-30 rejected data requires deterministic reasons")
        for reason in self.rejection_reasons:
            if reason not in REJECTION_REASONS:
                raise ValueError("BR-30 rejection reason is not recognized")
        _validate_disabled_safety(self.safety)


class TastytradeReadOnlyMarketDataAdapter:
    provider_name = APPROVED_PROVIDER

    def acquire_snapshot(self, request: MarketDataRequest) -> MarketDataAdapterResult:
        request.validate()
        as_of = request.as_of or datetime.now(timezone.utc).replace(microsecond=0)
        if request.mode == "offline":
            return _blocked_result(
                request=request,
                as_of=as_of,
                reasons=("runtime_mode_not_allowed", "runtime_config_missing"),
                raw_payload=None,
                normalized_snapshot=None,
                evidence=_empty_evidence(),
            )
        config_reasons = _runtime_config_rejection_reasons(request.runtime_config_path)
        if config_reasons:
            return _blocked_result(
                request=request,
                as_of=as_of,
                reasons=config_reasons,
                raw_payload=None,
                normalized_snapshot=None,
                evidence=_empty_evidence(),
            )
        raw_payload, load_reasons = _load_recorded_payload(request.recorded_response_path)
        if load_reasons or raw_payload is None:
            return _blocked_result(
                request=request,
                as_of=as_of,
                reasons=load_reasons or ("raw_payload_missing",),
                raw_payload=raw_payload,
                normalized_snapshot=None,
                evidence=_evidence_from_payload(raw_payload, request.recorded_response_path, None),
            )
        reasons = _payload_rejection_reasons(raw_payload, request, as_of)
        normalized_snapshot = None if reasons else _normalize_to_br26_snapshot(raw_payload, request, as_of)
        evidence = _evidence_from_payload(raw_payload, request.recorded_response_path, normalized_snapshot)
        if reasons:
            return _blocked_result(
                request=request,
                as_of=as_of,
                reasons=reasons,
                raw_payload=raw_payload,
                normalized_snapshot=None,
                evidence=evidence,
            )
        result = MarketDataAdapterResult(
            as_of=as_of,
            request_mode=request.mode,
            provider_name=self.provider_name,
            accepted_for_shadow_research=True,
            label=HUMAN_REVIEW_REQUIRED,
            adapter_checks=_adapter_checks(raw_payload, request, as_of, normalized_snapshot, ()),
            rejection_reasons=(),
            evidence=evidence,
            normalized_snapshot=normalized_snapshot,
            raw_payload_summary=_raw_summary(raw_payload),
            boundary_evidence=_boundary_evidence(raw_payload),
            safety=safety_manifest(request.mode),
        )
        result.validate()
        return result


def safety_manifest(mode: str = "offline") -> dict[str, Any]:
    return {
        "phase": PHASE_ID,
        "module": MODULE_NAME,
        "labels": REQUIRED_LABELS,
        "research_only": True,
        "monitor_only": True,
        "paper_only": True,
        "human_review_required": True,
        "blocked_by_safety_gate": True,
        "provider_independent_interface": True,
        "tastytrade_compatible_adapter": True,
        "read_only_market_data_only": True,
        "fixture_testable": True,
        "recorded_response_testable": True,
        "default_runtime_mode": "offline",
        "current_runtime_mode": mode,
        "offline_by_default": True,
        "fail_closed_by_default": True,
        "raw_evidence_immutable": True,
        "normalized_evidence_immutable": True,
        "br26_snapshot_contract_target": True,
        "shadow_research_only": True,
        "local_secret_storage_required_for_real_provider": True,
        "separate_runtime_config_required": True,
        "account_capabilities_available": False,
        "execution_capabilities_available": False,
        "position_mutation_capabilities_available": False,
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
        "live_state_mutation_allowed": False,
        "paper_state_mutation_allowed": False,
        "broker_state_mutation_allowed": False,
        "routing_state_mutation_allowed": False,
        "live_trading_enabled": False,
        "LIVE TRADING": "DISABLED",
    }


def build_read_only_live_market_data_adapter_evidence(
    request: MarketDataRequest | None = None,
) -> MarketDataAdapterResult:
    resolved_request = request or MarketDataRequest(symbols=("SPY",), mode="offline")
    return TastytradeReadOnlyMarketDataAdapter().acquire_snapshot(resolved_request)


def read_only_live_market_data_adapter_payload(result: MarketDataAdapterResult) -> dict[str, Any]:
    result.validate()
    acceptance = _acceptance_criteria(result)
    return {
        "phase": PHASE_ID,
        "module": MODULE_NAME,
        "as_of": result.as_of.isoformat(),
        "label": result.label,
        "request_mode": result.request_mode,
        "provider_name": result.provider_name,
        "accepted_for_shadow_research": result.accepted_for_shadow_research,
        "adapter_schema_name": ADAPTER_SCHEMA_NAME,
        "target_snapshot_schema_name": SNAPSHOT_SCHEMA_NAME,
        "supported_modes": SUPPORTED_MODES,
        "approved_feeds": APPROVED_FEEDS,
        "adapter_checks": result.adapter_checks,
        "rejection_reasons": result.rejection_reasons,
        "known_rejection_reasons": REJECTION_REASONS,
        "evidence": _evidence_payload(result.evidence),
        "raw_payload_summary": result.raw_payload_summary,
        "boundary_evidence": result.boundary_evidence,
        "normalized_snapshot": result.normalized_snapshot,
        "safety": result.safety,
        "metrics": {
            "adapter_check_count": len(ADAPTER_CHECKS),
            "adapter_check_passed_count": sum(1 for passed in result.adapter_checks.values() if passed),
            "rejection_reason_count": len(result.rejection_reasons),
            "normalized_record_count": len(result.normalized_snapshot.get("records", ()))
            if isinstance(result.normalized_snapshot, dict)
            else 0,
            "normalized_symbol_count": len(result.normalized_snapshot.get("symbols", ()))
            if isinstance(result.normalized_snapshot, dict)
            else 0,
            "acceptance_criteria_count": len(acceptance),
            "acceptance_criteria_passed_count": sum(1 for passed in acceptance.values() if passed),
        },
        "acceptance_criteria": acceptance,
        "readiness_state": {
            "state": "READ_ONLY_MARKET_DATA_EVIDENCE_ONLY",
            "suitable_for_later_shadow_research": result.accepted_for_shadow_research,
            "manual_review_required": True,
            "human_review_required": True,
            "ready_for_live_trading": False,
            "account_mutation_allowed": False,
            "execution_methods_available": False,
            "broker_actions_allowed": False,
            "order_paths_allowed": False,
            "external_routing_paths_allowed": False,
            "paper_state_mutation_allowed": False,
            "live_state_mutation_allowed": False,
        },
    }


def render_markdown_read_only_live_market_data_adapter(result: MarketDataAdapterResult) -> str:
    payload = read_only_live_market_data_adapter_payload(result)
    lines = [
        f"# {PHASE_ID} {MODULE_NAME}",
        "",
        "Research labels: " + ", ".join(REQUIRED_LABELS),
        "LIVE TRADING: DISABLED",
        "",
        "## Provider",
        f"- provider_name: {payload['provider_name']}",
        f"- request_mode: {payload['request_mode']}",
        f"- accepted_for_shadow_research: {payload['accepted_for_shadow_research']}",
        f"- feed_identity: {payload['evidence']['feed_identity']}",
        f"- schema_version: {payload['evidence']['schema_version']}",
        "",
        "## Evidence Checks",
    ]
    for name, passed in payload["adapter_checks"].items():
        lines.append(f"- {name}: {passed}")
    lines.extend(["", "## Rejection Reasons"])
    if payload["rejection_reasons"]:
        for reason in payload["rejection_reasons"]:
            lines.append(f"- {reason}")
    else:
        lines.append("- none")
    lines.extend(["", "## Checksums"])
    lines.append(f"- raw_checksum_sha256: {payload['evidence']['raw_checksum_sha256']}")
    lines.append(f"- normalized_checksum_sha256: {payload['evidence']['normalized_checksum_sha256']}")
    lines.extend(["", "## Boundary Evidence"])
    for name, value in payload["boundary_evidence"].items():
        lines.append(f"- {name}: {value}")
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
            "- Default runtime remains offline and fail closed.",
            "- Real provider access requires a separate explicit read-only runtime configuration outside this repository.",
            "- Authentication material must stay in local secret storage and must not appear in source files, reports, logs, fixtures, Git history, or UI surfaces.",
            "- No account mutation capabilities, execution methods, external routing paths, state mutation, or live trading authorization are created.",
        ]
    )
    return "\n".join(lines)


def write_read_only_live_market_data_adapter_evidence(
    result: MarketDataAdapterResult,
    out_dir: Path = DEFAULT_REPORT_DIR,
) -> tuple[Path, Path, Path | None]:
    result.validate()
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_REPORT_NAME
    markdown_path = out_dir / MARKDOWN_REPORT_NAME
    snapshot_path = out_dir / NORMALIZED_SNAPSHOT_NAME if result.normalized_snapshot else None
    json_path.write_text(
        json.dumps(read_only_live_market_data_adapter_payload(result), indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown_read_only_live_market_data_adapter(result), encoding="utf-8")
    if snapshot_path is not None:
        snapshot_path.write_text(
            json.dumps(result.normalized_snapshot, indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )
    return json_path, markdown_path, snapshot_path


def run_read_only_live_market_data_adapter(
    request: MarketDataRequest | None = None,
    out_dir: Path = DEFAULT_REPORT_DIR,
) -> MarketDataAdapterResult:
    result = build_read_only_live_market_data_adapter_evidence(request=request)
    write_read_only_live_market_data_adapter_evidence(result, out_dir=out_dir)
    return result


def _runtime_config_rejection_reasons(path: Path | None) -> tuple[str, ...]:
    if path is None:
        return ()
    repo_root = Path.cwd().resolve()
    resolved = path.resolve()
    reasons: list[str] = []
    try:
        resolved.relative_to(repo_root)
        reasons.append("runtime_config_inside_repository")
    except ValueError:
        pass
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
        if _contains_sensitive_field(payload):
            reasons.append("runtime_config_contains_secret_material")
    return tuple(reasons)


def _load_recorded_payload(path: Path | None) -> tuple[dict[str, Any] | None, tuple[str, ...]]:
    if path is None or not path.exists():
        return None, ("raw_payload_missing",)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None, ("raw_payload_malformed",)
    if not isinstance(payload, dict):
        return None, ("raw_payload_malformed",)
    return payload, ()


def _payload_rejection_reasons(
    payload: dict[str, Any],
    request: MarketDataRequest,
    as_of: datetime,
) -> tuple[str, ...]:
    reasons: list[str] = []
    provider = payload.get("provider")
    feed = payload.get("feed")
    metadata = payload.get("metadata")
    events = payload.get("events")
    if provider != APPROVED_PROVIDER:
        reasons.append("provider_identity_mismatch")
    if feed not in request.approved_feeds:
        reasons.append("feed_not_approved")
    if feed != APPROVED_FEEDS[0]:
        reasons.append("feed_mismatch")
    if not isinstance(metadata, dict) or metadata.get("schema_version") != ADAPTER_SCHEMA_NAME:
        reasons.append("schema_version_unsupported")
    if _contains_sensitive_field(payload):
        reasons.append("secret_material_detected")
    if _unsafe_capability_present(payload):
        reasons.append("unsafe_capability_present")
    if not isinstance(events, list) or not events:
        reasons.append("raw_payload_malformed")
        return tuple(dict.fromkeys(reasons))

    seen: set[tuple[str, str, str]] = set()
    requested = set(request.symbols)
    bar_symbols: set[str] = set()
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            reasons.append("raw_payload_malformed")
            continue
        event_type = str(event.get("event_type", ""))
        symbol = str(event.get("symbol", ""))
        timestamp = str(event.get("exchange_timestamp", ""))
        event_id = str(event.get("event_id", f"event-{index}"))
        key = (event_type, symbol, timestamp)
        if key in seen or event.get("duplicate") is True:
            reasons.append("duplicate_event")
        seen.add(key)
        if event_type == "bar":
            bar_symbols.add(symbol)
            for field_name in ("open", "high", "low", "close", "volume"):
                if event.get(field_name) is None:
                    reasons.append("missing_bar")
                    reasons.append("incomplete_record")
        event_underlying = str(event.get("underlying", ""))
        requested_identity = event_underlying if event_type == "option_chain_metadata" else symbol
        if requested_identity and requested_identity not in requested:
            reasons.append("feed_mismatch")
        provider_timestamp = _parse_datetime(event.get("provider_timestamp"))
        exchange_timestamp = _parse_datetime(event.get("exchange_timestamp"))
        acquisition_timestamp = _parse_datetime(event.get("acquisition_timestamp"))
        if provider_timestamp is None:
            reasons.append("provider_timestamp_invalid")
        if exchange_timestamp is None:
            reasons.append("exchange_timestamp_invalid")
        if acquisition_timestamp is None:
            reasons.append("acquisition_timestamp_invalid")
        if not _timezone_is_valid(event.get("provider_timestamp")) or not _timezone_is_valid(event.get("exchange_timestamp")):
            reasons.append("timezone_invalid")
        if provider_timestamp and exchange_timestamp and abs(provider_timestamp - exchange_timestamp) > MAX_CLOCK_SKEW:
            reasons.append("clock_skew_exceeded")
        if as_of and exchange_timestamp and as_of - exchange_timestamp > MAX_DATA_AGE:
            reasons.append("stale_data")
        quality_flags = tuple(str(flag) for flag in event.get("quality_flags", ()) if isinstance(flag, str))
        if "delayed" in quality_flags:
            reasons.append("delayed_feed")
        if any(flag in quality_flags for flag in ("low_provenance", "bad_tick", "unapproved")):
            reasons.append("low_quality_flag")
        if event.get("provenance_score", 0) < MIN_PROVENANCE_SCORE:
            reasons.append("low_provenance")
        if event.get("connection_state") == "reconnect_open":
            reasons.append("reconnect_boundary_open")
        if int(event.get("retry_count", 0)) > 3:
            reasons.append("retry_boundary_exceeded")
        if int(event.get("rate_limit_remaining", 1)) < 0 or event.get("rate_limited") is True:
            reasons.append("rate_limit_boundary_exceeded")
        if event.get("sandbox_reset") is True:
            reasons.append("sandbox_reset_detected")
        if event_id == "":
            reasons.append("incomplete_record")
    if requested - bar_symbols:
        reasons.append("missing_bar")
    return tuple(dict.fromkeys(reasons))


def _normalize_to_br26_snapshot(
    payload: dict[str, Any],
    request: MarketDataRequest,
    as_of: datetime,
) -> dict[str, Any]:
    bar_events = [
        event for event in payload["events"] if isinstance(event, dict) and event.get("event_type") == "bar"
    ]
    records = [
        {
            "symbol": str(event["symbol"]),
            "timestamp": _parse_datetime(event["exchange_timestamp"]).isoformat(),
            "open": float(event["open"]),
            "high": float(event["high"]),
            "low": float(event["low"]),
            "close": float(event["close"]),
            "volume": int(event["volume"]),
        }
        for event in sorted(bar_events, key=lambda item: (str(item.get("exchange_timestamp")), str(item.get("symbol"))))
    ]
    snapshot = {
        "snapshot_version": "1",
        "snapshot_id": _snapshot_id(payload),
        "generated_at": as_of.isoformat(),
        "freshness_as_of": max(record["timestamp"] for record in records),
        "source_kind": "approved_offline_file",
        "data_domain": "daily_ohlcv",
        "provenance": {
            "provider_name": payload["provider"],
            "provider_dataset": payload["feed"],
            "source_file_name": NORMALIZED_SNAPSHOT_NAME,
            "acquisition_method": "offline_file_export",
            "collector": "br30_read_only_market_data_adapter",
            "collected_at": as_of.isoformat(),
            "checksum_sha256": "0" * 64,
            "schema_name": SNAPSHOT_SCHEMA_NAME,
            "quality_score": min(float(event.get("provenance_score", 0.0)) for event in payload["events"]),
        },
        "symbols": tuple(sorted({record["symbol"] for record in records})),
        "records": records,
        "provider_metadata": _provider_metadata(payload),
        "safety": _snapshot_safety(),
        "redaction": {"redacted": True, "redacted_fields": REDACTED_FIELDS},
        "labels": REQUIRED_LABELS,
    }
    snapshot["provenance"]["checksum_sha256"] = _canonical_checksum(snapshot)
    return snapshot


def _provider_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    events = payload.get("events", ())
    quotes = [
        {
            "symbol": event.get("symbol"),
            "bid": event.get("bid"),
            "ask": event.get("ask"),
            "provider_timestamp": event.get("provider_timestamp"),
            "exchange_timestamp": event.get("exchange_timestamp"),
            "quality_flags": tuple(event.get("quality_flags", ())),
        }
        for event in events
        if isinstance(event, dict) and event.get("event_type") == "quote"
    ]
    option_chain = [
        {
            "symbol": event.get("symbol"),
            "underlying": event.get("underlying"),
            "expiration": event.get("expiration"),
            "strike_count": event.get("strike_count"),
            "provider_timestamp": event.get("provider_timestamp"),
            "quality_flags": tuple(event.get("quality_flags", ())),
        }
        for event in events
        if isinstance(event, dict) and event.get("event_type") == "option_chain_metadata"
    ]
    return {
        "feed_identity": payload.get("feed"),
        "schema_version": payload.get("metadata", {}).get("schema_version")
        if isinstance(payload.get("metadata"), dict)
        else None,
        "snapshot_metadata": payload.get("metadata", {}),
        "raw_source_file_name": payload.get("metadata", {}).get("source_file_name")
        if isinstance(payload.get("metadata"), dict)
        else None,
        "quote_metadata": tuple(quotes),
        "option_chain_metadata": tuple(option_chain),
    }


def _adapter_checks(
    payload: dict[str, Any] | None,
    request: MarketDataRequest,
    as_of: datetime,
    normalized_snapshot: dict[str, Any] | None,
    reasons: tuple[str, ...],
) -> dict[str, bool]:
    return {
        "offline_default_fail_closed": request.mode != "offline" or "runtime_mode_not_allowed" in reasons,
        "provider_interface_declared": True,
        "runtime_config_external_required": request.runtime_config_path is None
        or "runtime_config_inside_repository" not in reasons,
        "secret_material_absent": not _contains_sensitive_field(payload),
        "raw_evidence_preserved": payload is not None,
        "normalized_snapshot_created": normalized_snapshot is not None,
        "br26_snapshot_schema_compatible": _snapshot_schema_compatible(normalized_snapshot),
        "feed_identity_approved": payload is not None and payload.get("feed") in APPROVED_FEEDS,
        "provider_timestamp_valid": "provider_timestamp_invalid" not in reasons,
        "exchange_timestamp_valid": "exchange_timestamp_invalid" not in reasons,
        "acquisition_timestamp_valid": "acquisition_timestamp_invalid" not in reasons,
        "clock_skew_within_limit": "clock_skew_exceeded" not in reasons,
        "quality_flags_accepted": not any(reason in reasons for reason in ("delayed_feed", "low_quality_flag")),
        "duplicates_rejected": "duplicate_event" in reasons or _no_duplicates(payload),
        "missing_bars_rejected": "missing_bar" in reasons or _all_requested_bars_present(payload, request.symbols),
        "malformed_payload_rejected": "raw_payload_malformed" in reasons or payload is not None,
        "unsafe_capabilities_absent": not _unsafe_capability_present(payload),
    }


def _blocked_result(
    request: MarketDataRequest,
    as_of: datetime,
    reasons: tuple[str, ...],
    raw_payload: dict[str, Any] | None,
    normalized_snapshot: dict[str, Any] | None,
    evidence: MarketDataEvidence,
) -> MarketDataAdapterResult:
    result = MarketDataAdapterResult(
        as_of=as_of,
        request_mode=request.mode,
        provider_name=APPROVED_PROVIDER,
        accepted_for_shadow_research=False,
        label=BLOCKED_BY_SAFETY_GATE,
        adapter_checks=_adapter_checks(raw_payload, request, as_of, normalized_snapshot, reasons),
        rejection_reasons=tuple(dict.fromkeys(reasons)),
        evidence=evidence,
        normalized_snapshot=normalized_snapshot,
        raw_payload_summary=_raw_summary(raw_payload),
        boundary_evidence=_boundary_evidence(raw_payload),
        safety=safety_manifest(request.mode),
    )
    result.validate()
    return result


def _evidence_from_payload(
    payload: dict[str, Any] | None,
    raw_path: Path | None,
    normalized_snapshot: dict[str, Any] | None,
) -> MarketDataEvidence:
    metadata = payload.get("metadata", {}) if isinstance(payload, dict) and isinstance(payload.get("metadata"), dict) else {}
    events = payload.get("events", ()) if isinstance(payload, dict) and isinstance(payload.get("events"), list) else ()
    first_event = next((event for event in events if isinstance(event, dict)), {})
    raw_checksum = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest() if payload is not None else None
    return MarketDataEvidence(
        provider_name=str(payload.get("provider")) if isinstance(payload, dict) and payload.get("provider") else APPROVED_PROVIDER,
        feed_identity=str(payload.get("feed")) if isinstance(payload, dict) and payload.get("feed") else "",
        raw_path=str(raw_path) if raw_path else None,
        raw_checksum_sha256=raw_checksum,
        normalized_checksum_sha256=_canonical_checksum(normalized_snapshot) if normalized_snapshot else None,
        provider_timestamp=first_event.get("provider_timestamp") if isinstance(first_event, dict) else None,
        exchange_timestamp=first_event.get("exchange_timestamp") if isinstance(first_event, dict) else None,
        acquisition_timestamp=first_event.get("acquisition_timestamp") if isinstance(first_event, dict) else None,
        schema_version=str(metadata.get("schema_version")) if metadata.get("schema_version") else None,
        quality_flags=tuple(first_event.get("quality_flags", ())) if isinstance(first_event, dict) else (),
        provenance_score=float(first_event.get("provenance_score", 0.0)) if isinstance(first_event, dict) else 0.0,
    )


def _empty_evidence() -> MarketDataEvidence:
    return MarketDataEvidence(APPROVED_PROVIDER, "", None, None, None, None, None, None, None, (), 0.0)


def _raw_summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        return {"event_count": 0, "symbols": (), "event_types": ()}
    events = payload.get("events", ()) if isinstance(payload.get("events"), list) else ()
    return {
        "provider": payload.get("provider"),
        "feed": payload.get("feed"),
        "event_count": len(events),
        "symbols": tuple(sorted({str(event.get("symbol")) for event in events if isinstance(event, dict) and event.get("symbol")})),
        "event_types": tuple(sorted({str(event.get("event_type")) for event in events if isinstance(event, dict)})),
    }


def _boundary_evidence(payload: dict[str, Any] | None) -> dict[str, Any]:
    events = payload.get("events", ()) if isinstance(payload, dict) and isinstance(payload.get("events"), list) else ()
    return {
        "reconnect_boundary_events": sum(1 for event in events if isinstance(event, dict) and event.get("connection_state") == "reconnect_open"),
        "max_retry_count": max((int(event.get("retry_count", 0)) for event in events if isinstance(event, dict)), default=0),
        "min_rate_limit_remaining": min((int(event.get("rate_limit_remaining", 999999)) for event in events if isinstance(event, dict)), default=None),
        "duplicate_events": sum(1 for event in events if isinstance(event, dict) and event.get("duplicate") is True),
        "delayed_feed_events": sum(1 for event in events if isinstance(event, dict) and "delayed" in event.get("quality_flags", ())),
        "sandbox_reset_events": sum(1 for event in events if isinstance(event, dict) and event.get("sandbox_reset") is True),
    }


def _snapshot_safety() -> dict[str, Any]:
    return {
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


def _snapshot_schema_compatible(snapshot: dict[str, Any] | None) -> bool:
    if not isinstance(snapshot, dict):
        return False
    required = {
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
    }
    return required.issubset(snapshot) and snapshot.get("snapshot_version") == "1"


def _all_requested_bars_present(payload: dict[str, Any] | None, symbols: tuple[str, ...]) -> bool:
    if payload is None or not isinstance(payload.get("events"), list):
        return False
    bar_symbols = {event.get("symbol") for event in payload["events"] if isinstance(event, dict) and event.get("event_type") == "bar"}
    return set(symbols).issubset(bar_symbols)


def _no_duplicates(payload: dict[str, Any] | None) -> bool:
    if payload is None or not isinstance(payload.get("events"), list):
        return False
    seen: set[tuple[str, str, str]] = set()
    for event in payload["events"]:
        if not isinstance(event, dict):
            return False
        key = (str(event.get("event_type")), str(event.get("symbol")), str(event.get("exchange_timestamp")))
        if key in seen or event.get("duplicate") is True:
            return False
        seen.add(key)
    return True


def _unsafe_capability_present(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    capabilities = payload.get("capabilities", {})
    if not isinstance(capabilities, dict):
        return True
    unsafe = (
        "account_mutation",
        "execution",
        "order_routing",
        "position_mutation",
        "external_routing",
        "live_trading",
    )
    return any(capabilities.get(name) is True for name in unsafe)


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


def _timezone_is_valid(value: Any) -> bool:
    return isinstance(value, str) and ("+" in value[10:] or value.endswith("Z"))


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _snapshot_id(payload: dict[str, Any]) -> str:
    raw = f"{payload.get('provider')}|{payload.get('feed')}|{payload.get('metadata', {}).get('snapshot_id')}"
    return "br30-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _canonical_checksum(payload: dict[str, Any]) -> str:
    canonical_payload = json.loads(json.dumps(payload, sort_keys=True, default=str))
    if isinstance(canonical_payload.get("provenance"), dict):
        canonical_payload["provenance"]["checksum_sha256"] = "0" * 64
    canonical_text = json.dumps(canonical_payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_text.encode("utf-8")).hexdigest()


def _evidence_payload(evidence: MarketDataEvidence) -> dict[str, Any]:
    return {
        "provider_name": evidence.provider_name,
        "feed_identity": evidence.feed_identity,
        "raw_path": evidence.raw_path,
        "raw_checksum_sha256": evidence.raw_checksum_sha256,
        "normalized_checksum_sha256": evidence.normalized_checksum_sha256,
        "provider_timestamp": evidence.provider_timestamp,
        "exchange_timestamp": evidence.exchange_timestamp,
        "acquisition_timestamp": evidence.acquisition_timestamp,
        "schema_version": evidence.schema_version,
        "quality_flags": evidence.quality_flags,
        "provenance_score": evidence.provenance_score,
    }


def _acceptance_criteria(result: MarketDataAdapterResult) -> dict[str, bool]:
    return {
        "provider_interface_declared": result.adapter_checks["provider_interface_declared"],
        "default_offline_fail_closed": result.safety["offline_by_default"] is True
        and result.safety["fail_closed_by_default"] is True,
        "accepted_data_remains_human_review_required": (
            not result.accepted_for_shadow_research or result.label == HUMAN_REVIEW_REQUIRED
        ),
        "raw_and_normalized_checksums_present_when_accepted": (
            not result.accepted_for_shadow_research
            or (
                result.evidence.raw_checksum_sha256 is not None
                and result.evidence.normalized_checksum_sha256 is not None
            )
        ),
        "br26_snapshot_schema_compatible": (
            not result.accepted_for_shadow_research or result.adapter_checks["br26_snapshot_schema_compatible"]
        ),
        "all_quality_boundaries_enforced": all(
            result.adapter_checks[name]
            for name in (
                "feed_identity_approved",
                "provider_timestamp_valid",
                "exchange_timestamp_valid",
                "acquisition_timestamp_valid",
                "clock_skew_within_limit",
                "quality_flags_accepted",
                "duplicates_rejected",
                "missing_bars_rejected",
                "unsafe_capabilities_absent",
            )
        ),
        "no_credentials_or_secrets": all(
            result.safety[field_name] is False
            for field_name in ("credential_loading_attempted", "env_file_read_attempted", "secret_request_attempted")
        ),
        "no_external_network_or_real_fetch": all(
            result.safety[field_name] is False
            for field_name in ("data_provider_call_attempted", "external_network_call_attempted", "real_data_fetch_attempted")
        ),
        "no_account_execution_or_state_mutation": all(
            result.safety[field_name] is False for field_name in REQUIRED_DISABLED_FLAGS
        ),
        "live_trading_disabled": result.safety["LIVE TRADING"] == "DISABLED",
    }


def _validate_disabled_safety(manifest: dict[str, Any]) -> None:
    for field_name in REQUIRED_DISABLED_FLAGS:
        if manifest.get(field_name) is not False:
            raise ValueError(f"BR-30 adapter cannot set {field_name}")
    for field_name in (
        "account_capabilities_available",
        "execution_capabilities_available",
        "position_mutation_capabilities_available",
        "broker_write_operations_authorized",
        "external_routing_paths_authorized",
        "data_provider_calls_authorized",
        "live_state_mutation_allowed",
        "paper_state_mutation_allowed",
        "broker_state_mutation_allowed",
        "routing_state_mutation_allowed",
    ):
        if manifest.get(field_name) is not False:
            raise ValueError(f"BR-30 adapter cannot allow {field_name}")
    if manifest.get("LIVE TRADING") != "DISABLED":
        raise ValueError("BR-30 adapter must keep LIVE TRADING disabled")
