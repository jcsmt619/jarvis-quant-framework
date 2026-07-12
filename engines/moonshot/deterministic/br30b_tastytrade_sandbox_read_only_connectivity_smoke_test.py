from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Protocol

from engines.moonshot.deterministic.br30_read_only_live_market_data_adapter import (
    ADAPTER_SCHEMA_NAME,
    APPROVED_FEEDS,
    MarketDataRequest,
)
from engines.moonshot.deterministic.br30a_secure_local_oauth_runtime_bridge import (
    ALLOWED_OAUTH_SCOPES,
    InMemoryAccessToken,
    OAuthBridgeRequest,
    ProviderResourceRequest,
    SecureLocalOAuthRuntimeBridge,
    authorize_provider_resource_request,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


PHASE_ID = "BR-30B"
MODULE_NAME = "Tastytrade Sandbox Read Only Connectivity Smoke Test"
DEFAULT_REPORT_DIR = Path("reports/br30b_tastytrade_sandbox_read_only_connectivity_smoke_test")
JSON_REPORT_NAME = "tastytrade_sandbox_read_only_connectivity_smoke_test.json"
MARKDOWN_REPORT_NAME = "tastytrade_sandbox_read_only_connectivity_smoke_test.md"
NORMALIZED_SNAPSHOT_NAME = "br30b_normalized_br26_snapshot.json"
SUPPORTED_MODES = ("offline", "sandbox_network")
APPROVED_SYMBOLS = ("SPY", "QQQ")
APPROVED_SANDBOX_HOSTS = ("api.cert.tastytrade.com", "api.cert.tastyworks.com")
MAX_QUOTE_AGE = timedelta(minutes=20)
MAX_CLOCK_SKEW = timedelta(seconds=90)
REQUIRED_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
REJECTION_REASONS = (
    "runtime_mode_not_allowed",
    "oauth_bridge_missing",
    "sandbox_client_missing",
    "access_token_unavailable",
    "token_expired",
    "unexpected_scope",
    "wrong_sandbox_host",
    "customer_discovery_failed",
    "quote_token_failed",
    "market_data_disconnect",
    "reconnect_boundary",
    "rate_limit",
    "malformed_payload",
    "missing_symbol",
    "duplicate_event",
    "stale_quote",
    "clock_skew",
    "redaction_failed",
    "normalization_failed",
)


class TastytradeSandboxReadOnlyClient(Protocol):
    provider_name: str
    sandbox_host: str

    def discover_customer_accounts(
        self,
        token: InMemoryAccessToken,
        as_of: datetime,
    ) -> "SandboxCustomerDiscovery":
        """Perform a read-only customer/account discovery call."""

    def obtain_quote_token(self, token: InMemoryAccessToken, as_of: datetime) -> "SandboxQuoteToken":
        """Return a sandbox quote token. Implementations must not log it."""

    def stream_delayed_market_data(
        self,
        quote_token: "SandboxQuoteToken",
        symbols: tuple[str, ...],
        as_of: datetime,
    ) -> "SandboxMarketDataSample":
        """Connect to delayed sandbox market data and return a small sample."""


class DisabledTastytradeSandboxReadOnlyClient:
    provider_name = "tastytrade"
    sandbox_host = "api.cert.tastytrade.com"

    def discover_customer_accounts(
        self,
        token: InMemoryAccessToken,
        as_of: datetime,
    ) -> "SandboxCustomerDiscovery":
        raise RuntimeError("BR-30B sandbox network client is disabled by default")

    def obtain_quote_token(self, token: InMemoryAccessToken, as_of: datetime) -> "SandboxQuoteToken":
        raise RuntimeError("BR-30B sandbox network client is disabled by default")

    def stream_delayed_market_data(
        self,
        quote_token: "SandboxQuoteToken",
        symbols: tuple[str, ...],
        as_of: datetime,
    ) -> "SandboxMarketDataSample":
        raise RuntimeError("BR-30B sandbox network client is disabled by default")


@dataclass(frozen=True)
class SandboxCustomerDiscovery:
    customer_id: str = field(repr=False)
    account_ids: tuple[str, ...] = field(repr=False)
    provider_timestamp: str
    acquisition_timestamp: str


@dataclass(frozen=True)
class SandboxQuoteToken:
    quote_token: str = field(repr=False)
    feed_identity: str
    provider_timestamp: str
    acquisition_timestamp: str


@dataclass(frozen=True)
class SandboxMarketDataEvent:
    event_id: str
    event_type: str
    symbol: str
    provider_timestamp: str
    exchange_timestamp: str
    acquisition_timestamp: str
    bid: float | None = None
    ask: float | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: int | None = None
    quality_flags: tuple[str, ...] = ("authorized", "sandbox_delayed")
    provenance_score: float = 0.95
    delay_minutes: int = 15
    connection_state: str = "steady"
    retry_count: int = 0
    rate_limit_remaining: int = 10


@dataclass(frozen=True)
class SandboxMarketDataSample:
    connected: bool
    disconnected: bool
    reconnect_count: int
    events: tuple[SandboxMarketDataEvent, ...]


@dataclass(frozen=True)
class SandboxSmokeTestRequest:
    symbols: tuple[str, ...] = APPROVED_SYMBOLS
    mode: str = "offline"
    as_of: datetime | None = None

    def validate(self) -> None:
        if self.mode not in SUPPORTED_MODES:
            raise ValueError("BR-30B runtime mode is not supported")
        if not self.symbols:
            raise ValueError("BR-30B requires at least one symbol")
        if any(symbol not in APPROVED_SYMBOLS for symbol in self.symbols):
            raise ValueError("BR-30B symbols must be from the approved sample allowlist")


@dataclass(frozen=True)
class SandboxSmokeTestResult:
    as_of: datetime
    label: str
    request_mode: str
    accepted_for_monitoring: bool
    rejection_reasons: tuple[str, ...]
    account_evidence: dict[str, Any]
    market_data_evidence: dict[str, Any]
    normalized_snapshot: dict[str, Any] | None
    checksums: dict[str, Any]
    safety: dict[str, Any]

    def validate(self) -> None:
        for reason in self.rejection_reasons:
            if reason not in REJECTION_REASONS:
                raise ValueError("BR-30B rejection reason is not recognized")
        if self.accepted_for_monitoring:
            if self.label != HUMAN_REVIEW_REQUIRED or self.rejection_reasons:
                raise ValueError("BR-30B accepted evidence must remain human-review-required")
            if self.normalized_snapshot is None:
                raise ValueError("BR-30B accepted evidence requires a normalized snapshot")
        else:
            if self.label != BLOCKED_BY_SAFETY_GATE or not self.rejection_reasons:
                raise ValueError("BR-30B rejected evidence must be blocked by safety gate")
        if not _account_evidence_is_redacted(self.account_evidence):
            raise ValueError("BR-30B account evidence must be redacted")
        _validate_safety(self.safety)


def build_tastytrade_sandbox_read_only_connectivity_smoke_test(
    request: SandboxSmokeTestRequest | None = None,
    oauth_bridge: SecureLocalOAuthRuntimeBridge | None = None,
    sandbox_client: TastytradeSandboxReadOnlyClient | None = None,
) -> SandboxSmokeTestResult:
    resolved = request or SandboxSmokeTestRequest()
    resolved.validate()
    as_of = resolved.as_of or datetime.now(timezone.utc).replace(microsecond=0)
    if resolved.mode == "offline":
        return _blocked_result(resolved, as_of, ("runtime_mode_not_allowed",), None, None, None, None)
    if oauth_bridge is None:
        return _blocked_result(resolved, as_of, ("oauth_bridge_missing",), None, None, None, None)
    if sandbox_client is None or isinstance(sandbox_client, DisabledTastytradeSandboxReadOnlyClient):
        return _blocked_result(resolved, as_of, ("sandbox_client_missing",), None, None, None, None)

    host_decision = _authorize_client_host(sandbox_client)
    if not host_decision.allowed:
        return _blocked_result(resolved, as_of, ("wrong_sandbox_host",), None, None, None, None)

    token_result, token = oauth_bridge.get_access_token_for_read_only_client(
        OAuthBridgeRequest(mode="local_runtime", scopes=ALLOWED_OAUTH_SCOPES, as_of=as_of)
    )
    if not token_result.access_token_ready or token is None:
        reasons = _token_reasons(token_result.rejection_reasons)
        return _blocked_result(resolved, as_of, reasons, None, None, None, None)
    token_reasons = _memory_token_rejection_reasons(token, as_of)
    if token_reasons:
        return _blocked_result(resolved, as_of, token_reasons, None, None, None, None)

    try:
        discovery = sandbox_client.discover_customer_accounts(token, as_of)
    except Exception:
        return _blocked_result(resolved, as_of, ("customer_discovery_failed",), None, None, None, None)
    account_evidence = _redacted_account_evidence(discovery)
    if not _account_evidence_is_redacted(account_evidence):
        return _blocked_result(resolved, as_of, ("redaction_failed",), account_evidence, None, None, None)

    try:
        quote_token = sandbox_client.obtain_quote_token(token, as_of)
    except Exception:
        return _blocked_result(resolved, as_of, ("quote_token_failed",), account_evidence, None, None, None)
    try:
        sample = sandbox_client.stream_delayed_market_data(quote_token, resolved.symbols, as_of)
    except Exception:
        return _blocked_result(resolved, as_of, ("market_data_disconnect",), account_evidence, None, None, None)

    raw_payload = _raw_market_data_payload(quote_token, sample)
    reasons = _sample_rejection_reasons(sample, resolved, as_of)
    if reasons:
        return _blocked_result(resolved, as_of, reasons, account_evidence, raw_payload, None, sample)

    # Reuse the BR-30 normalizer without file IO by invoking its provider through
    # the same validation path on an in-memory payload.
    adapter_result = _normalize_in_memory_br30(raw_payload, resolved, as_of)
    if not adapter_result.accepted_for_shadow_research or adapter_result.normalized_snapshot is None:
        return _blocked_result(resolved, as_of, ("normalization_failed",), account_evidence, raw_payload, None, sample)
    normalized_snapshot = _restamp_br30b_snapshot_artifact(adapter_result.normalized_snapshot)

    result = SandboxSmokeTestResult(
        as_of=as_of,
        label=HUMAN_REVIEW_REQUIRED,
        request_mode=resolved.mode,
        accepted_for_monitoring=True,
        rejection_reasons=(),
        account_evidence=account_evidence,
        market_data_evidence=_market_data_evidence(raw_payload, sample, as_of),
        normalized_snapshot=normalized_snapshot,
        checksums=_checksums(raw_payload, normalized_snapshot),
        safety=safety_manifest(resolved.mode, sandbox_network_attempted=True),
    )
    result.validate()
    return result


def safety_manifest(mode: str = "offline", sandbox_network_attempted: bool = False) -> dict[str, Any]:
    return {
        "phase": PHASE_ID,
        "module": MODULE_NAME,
        "labels": REQUIRED_LABELS,
        "research_only": True,
        "monitor_only": True,
        "paper_only": True,
        "human_review_required": True,
        "blocked_by_safety_gate": True,
        "default_runtime_mode": "offline",
        "current_runtime_mode": mode,
        "supported_modes": SUPPORTED_MODES,
        "offline_by_default": True,
        "fail_closed_by_default": True,
        "explicit_operator_invocation_required_for_sandbox_network": True,
        "sandbox_network_call_attempted": sandbox_network_attempted,
        "access_tokens_memory_only": True,
        "raw_account_identifiers_written": False,
        "account_fingerprints_only": True,
        "provider_neutral_br30_interface_used": True,
        "br26_normalized_snapshot_contract_used": True,
        "read_only_customer_discovery_only": True,
        "read_only_market_data_only": True,
        "account_mutation_methods_available": False,
        "execution_methods_available": False,
        "external_routing_paths_available": False,
        "position_change_methods_available": False,
        "live_trading_authorization_available": False,
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


def tastytrade_sandbox_read_only_connectivity_payload(result: SandboxSmokeTestResult) -> dict[str, Any]:
    result.validate()
    return {
        "phase": PHASE_ID,
        "module": MODULE_NAME,
        "as_of": result.as_of.isoformat(),
        "label": result.label,
        "request_mode": result.request_mode,
        "accepted_for_monitoring": result.accepted_for_monitoring,
        "approved_symbols": APPROVED_SYMBOLS,
        "rejection_reasons": result.rejection_reasons,
        "known_rejection_reasons": REJECTION_REASONS,
        "account_evidence": result.account_evidence,
        "market_data_evidence": result.market_data_evidence,
        "checksums": result.checksums,
        "normalized_snapshot": result.normalized_snapshot,
        "safety": result.safety,
        "readiness_state": {
            "state": "SANDBOX_READ_ONLY_CONNECTIVITY_EVIDENCE_ONLY",
            "manual_review_required": True,
            "ready_for_live_trading": False,
            "account_mutation_allowed": False,
            "execution_methods_available": False,
            "external_routing_paths_allowed": False,
            "position_changes_allowed": False,
            "live_trading_authorized": False,
        },
    }


def render_markdown_tastytrade_sandbox_read_only_connectivity(result: SandboxSmokeTestResult) -> str:
    payload = tastytrade_sandbox_read_only_connectivity_payload(result)
    lines = [
        f"# {PHASE_ID} {MODULE_NAME}",
        "",
        "Research labels: " + ", ".join(REQUIRED_LABELS),
        "LIVE TRADING: DISABLED",
        "",
        "## Runtime",
        f"- request_mode: {payload['request_mode']}",
        f"- accepted_for_monitoring: {payload['accepted_for_monitoring']}",
        "",
        "## Rejection Reasons",
    ]
    if payload["rejection_reasons"]:
        lines.extend(f"- {reason}" for reason in payload["rejection_reasons"])
    else:
        lines.append("- none")
    lines.extend(["", "## Redacted Account Evidence"])
    for key, value in payload["account_evidence"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Market Data Evidence"])
    for key, value in payload["market_data_evidence"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Checksums"])
    for key, value in payload["checksums"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(
        [
            "",
            "## Safety Boundaries",
            "- RESEARCH_ONLY; MONITOR_ONLY; PAPER_ONLY; HUMAN_REVIEW_REQUIRED; BLOCKED_BY_SAFETY_GATE.",
            "- Default execution is fixture-only/offline and fail closed.",
            "- Sandbox-network mode requires explicit operator invocation and an injected read-only sandbox client.",
            "- Access tokens remain memory-only and raw account identifiers are not written to reports.",
            "- No account mutation methods, execution methods, external routing, position changes, or live trading authorization are provided.",
        ]
    )
    return "\n".join(lines)


def write_tastytrade_sandbox_read_only_connectivity_evidence(
    result: SandboxSmokeTestResult,
    out_dir: Path = DEFAULT_REPORT_DIR,
) -> tuple[Path, Path, Path | None]:
    result.validate()
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_REPORT_NAME
    markdown_path = out_dir / MARKDOWN_REPORT_NAME
    snapshot_path = out_dir / NORMALIZED_SNAPSHOT_NAME if result.normalized_snapshot else None
    json_path.write_text(
        json.dumps(tastytrade_sandbox_read_only_connectivity_payload(result), indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown_tastytrade_sandbox_read_only_connectivity(result), encoding="utf-8")
    if snapshot_path:
        snapshot_path.write_text(json.dumps(result.normalized_snapshot, indent=2, sort_keys=True, default=str), encoding="utf-8")
    return json_path, markdown_path, snapshot_path


def run_tastytrade_sandbox_read_only_connectivity_smoke_test(
    request: SandboxSmokeTestRequest | None = None,
    out_dir: Path = DEFAULT_REPORT_DIR,
    oauth_bridge: SecureLocalOAuthRuntimeBridge | None = None,
    sandbox_client: TastytradeSandboxReadOnlyClient | None = None,
) -> SandboxSmokeTestResult:
    result = build_tastytrade_sandbox_read_only_connectivity_smoke_test(
        request=request,
        oauth_bridge=oauth_bridge,
        sandbox_client=sandbox_client,
    )
    write_tastytrade_sandbox_read_only_connectivity_evidence(result, out_dir=out_dir)
    return result


def _authorize_client_host(client: TastytradeSandboxReadOnlyClient):
    return authorize_provider_resource_request(
        ProviderResourceRequest("GET", f"https://{client.sandbox_host}/customers/me")
    )


def _token_reasons(reasons: tuple[str, ...]) -> tuple[str, ...]:
    if "token_expired" in reasons:
        return ("token_expired",)
    if "unexpected_scope" in reasons or "provider_scope_not_allowed" in reasons:
        return ("unexpected_scope",)
    return ("access_token_unavailable",)


def _memory_token_rejection_reasons(token: InMemoryAccessToken, as_of: datetime) -> tuple[str, ...]:
    reasons: list[str] = []
    if not token.is_valid(as_of):
        reasons.append("token_expired")
    if set(token.scopes) != set(ALLOWED_OAUTH_SCOPES):
        reasons.append("unexpected_scope")
    return tuple(dict.fromkeys(reasons))


def _raw_market_data_payload(quote_token: SandboxQuoteToken, sample: SandboxMarketDataSample) -> dict[str, Any]:
    return {
        "provider": "tastytrade",
        "feed": APPROVED_FEEDS[0],
        "metadata": {
            "schema_version": ADAPTER_SCHEMA_NAME,
            "snapshot_id": "br30b-sandbox-smoke",
            "environment": "sandbox",
            "feed_identity": quote_token.feed_identity,
            "read_only": True,
        },
        "capabilities": {
            "market_data_read": True,
            "account_mutation": False,
            "execution": False,
            "order_routing": False,
            "position_mutation": False,
            "external_routing": False,
            "live_trading": False,
        },
        "events": [_event_payload(event) for event in sample.events],
    }


def _event_payload(event: SandboxMarketDataEvent) -> dict[str, Any]:
    payload = {
        "event_id": event.event_id,
        "event_type": event.event_type,
        "symbol": event.symbol,
        "provider_timestamp": event.provider_timestamp,
        "exchange_timestamp": event.exchange_timestamp,
        "acquisition_timestamp": event.acquisition_timestamp,
        "quality_flags": event.quality_flags,
        "provenance_score": event.provenance_score,
        "connection_state": event.connection_state,
        "retry_count": event.retry_count,
        "rate_limit_remaining": event.rate_limit_remaining,
        "sandbox_reset": False,
        "delay_minutes": event.delay_minutes,
    }
    for key in ("bid", "ask", "open", "high", "low", "close", "volume"):
        value = getattr(event, key)
        if value is not None:
            payload[key] = value
    return payload


def _sample_rejection_reasons(
    sample: SandboxMarketDataSample,
    request: SandboxSmokeTestRequest,
    as_of: datetime,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not sample.connected or sample.disconnected:
        reasons.append("market_data_disconnect")
    if sample.reconnect_count:
        reasons.append("reconnect_boundary")
    seen: set[tuple[str, str, str]] = set()
    symbols = {event.symbol for event in sample.events if event.event_type in ("bar", "quote")}
    bar_symbols = {event.symbol for event in sample.events if event.event_type == "bar"}
    if set(request.symbols) - symbols or set(request.symbols) - bar_symbols:
        reasons.append("missing_symbol")
    for event in sample.events:
        if event.rate_limit_remaining < 0:
            reasons.append("rate_limit")
        key = (event.event_type, event.symbol, event.exchange_timestamp)
        if key in seen:
            reasons.append("duplicate_event")
        seen.add(key)
        provider_ts = _parse_datetime(event.provider_timestamp)
        exchange_ts = _parse_datetime(event.exchange_timestamp)
        acquisition_ts = _parse_datetime(event.acquisition_timestamp)
        if provider_ts is None or exchange_ts is None or acquisition_ts is None:
            reasons.append("malformed_payload")
            continue
        if abs(provider_ts - exchange_ts) > MAX_CLOCK_SKEW:
            reasons.append("clock_skew")
        if as_of - exchange_ts > MAX_QUOTE_AGE:
            reasons.append("stale_quote")
        if event.connection_state == "reconnect_open":
            reasons.append("reconnect_boundary")
        if event.event_type == "bar" and any(
            value is None for value in (event.open, event.high, event.low, event.close, event.volume)
        ):
            reasons.append("malformed_payload")
    return tuple(dict.fromkeys(reasons))


def _normalize_in_memory_br30(
    raw_payload: dict[str, Any],
    request: SandboxSmokeTestRequest,
    as_of: datetime,
):
    from engines.moonshot.deterministic import br30_read_only_live_market_data_adapter as br30

    reasons = br30._payload_rejection_reasons(  # type: ignore[attr-defined]
        raw_payload,
        MarketDataRequest(symbols=request.symbols, mode="recorded_response", as_of=as_of),
        as_of,
    )
    normalized = None if reasons else br30._normalize_to_br26_snapshot(  # type: ignore[attr-defined]
        raw_payload,
        MarketDataRequest(symbols=request.symbols, mode="recorded_response", as_of=as_of),
        as_of,
    )
    evidence = br30._evidence_from_payload(raw_payload, None, normalized)  # type: ignore[attr-defined]
    if reasons:
        return br30._blocked_result(  # type: ignore[attr-defined]
            MarketDataRequest(symbols=request.symbols, mode="recorded_response", as_of=as_of),
            as_of,
            reasons,
            raw_payload,
            None,
            evidence,
        )
    return br30.MarketDataAdapterResult(
        as_of=as_of,
        request_mode="recorded_response",
        provider_name="tastytrade",
        accepted_for_shadow_research=True,
        label=HUMAN_REVIEW_REQUIRED,
        adapter_checks=br30._adapter_checks(  # type: ignore[attr-defined]
            raw_payload,
            MarketDataRequest(symbols=request.symbols, mode="recorded_response", as_of=as_of),
            as_of,
            normalized,
            (),
        ),
        rejection_reasons=(),
        evidence=evidence,
        normalized_snapshot=normalized,
        raw_payload_summary=br30._raw_summary(raw_payload),  # type: ignore[attr-defined]
        boundary_evidence=br30._boundary_evidence(raw_payload),  # type: ignore[attr-defined]
        safety=br30.safety_manifest("recorded_response"),
    )


def _redacted_account_evidence(discovery: SandboxCustomerDiscovery) -> dict[str, Any]:
    return {
        "customer_fingerprint": _fingerprint(discovery.customer_id),
        "account_fingerprints": tuple(_fingerprint(account_id) for account_id in discovery.account_ids),
        "raw_account_identifiers_present": False,
        "redacted": True,
        "provider_timestamp": discovery.provider_timestamp,
        "acquisition_timestamp": discovery.acquisition_timestamp,
    }


def _restamp_br30b_snapshot_artifact(snapshot: dict[str, Any]) -> dict[str, Any]:
    from engines.moonshot.deterministic import br30_read_only_live_market_data_adapter as br30

    restamped = json.loads(json.dumps(snapshot, sort_keys=True, default=str))
    restamped["provenance"]["source_file_name"] = NORMALIZED_SNAPSHOT_NAME
    restamped["provenance"]["checksum_sha256"] = br30._canonical_checksum(restamped)  # type: ignore[attr-defined]
    return restamped


def _account_evidence_is_redacted(evidence: dict[str, Any]) -> bool:
    if not evidence:
        return True
    if evidence.get("redacted") is not True or evidence.get("raw_account_identifiers_present") is not False:
        return False
    values = (
        str(value).lower()
        for key, value in evidence.items()
        if key not in ("raw_account_identifiers_present", "redacted")
    )
    return not any(
        marker in value
        for value in values
        for marker in ("account_id", "account_number", "raw_customer", "raw_account")
    )


def _market_data_evidence(
    raw_payload: dict[str, Any],
    sample: SandboxMarketDataSample,
    as_of: datetime,
) -> dict[str, Any]:
    events = raw_payload.get("events", [])
    exchange_times = [_parse_datetime(event.get("exchange_timestamp")) for event in events if isinstance(event, dict)]
    valid_exchange_times = [value for value in exchange_times if value is not None]
    quote_age_seconds = max(int((as_of - value).total_seconds()) for value in valid_exchange_times) if valid_exchange_times else None
    return {
        "provider": raw_payload.get("provider"),
        "feed_identity": raw_payload.get("feed"),
        "schema_version": raw_payload.get("metadata", {}).get("schema_version"),
        "symbols": tuple(sorted({event.get("symbol") for event in events if isinstance(event, dict) and event.get("symbol")})),
        "provider_timestamps": tuple(event.get("provider_timestamp") for event in events if isinstance(event, dict)),
        "exchange_timestamps": tuple(event.get("exchange_timestamp") for event in events if isinstance(event, dict)),
        "acquisition_timestamps": tuple(event.get("acquisition_timestamp") for event in events if isinstance(event, dict)),
        "quote_age_seconds": quote_age_seconds,
        "delay_classification": "delayed_sandbox",
        "provenance_scores": tuple(event.get("provenance_score") for event in events if isinstance(event, dict)),
        "quality_flags": tuple(sorted({flag for event in events if isinstance(event, dict) for flag in event.get("quality_flags", ())})),
        "connected": sample.connected,
        "disconnected": sample.disconnected,
        "reconnect_count": sample.reconnect_count,
    }


def _checksums(raw_payload: dict[str, Any] | None, normalized_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "raw_checksum_sha256": _checksum(raw_payload) if raw_payload is not None else None,
        "normalized_checksum_sha256": _checksum(normalized_snapshot) if normalized_snapshot is not None else None,
        "raw_evidence_immutable": raw_payload is not None,
        "normalized_evidence_immutable": normalized_snapshot is not None,
    }


def _blocked_result(
    request: SandboxSmokeTestRequest,
    as_of: datetime,
    reasons: tuple[str, ...],
    account_evidence: dict[str, Any] | None,
    raw_payload: dict[str, Any] | None,
    normalized_snapshot: dict[str, Any] | None,
    sample: SandboxMarketDataSample | None,
) -> SandboxSmokeTestResult:
    result = SandboxSmokeTestResult(
        as_of=as_of,
        label=BLOCKED_BY_SAFETY_GATE,
        request_mode=request.mode,
        accepted_for_monitoring=False,
        rejection_reasons=tuple(dict.fromkeys(reasons)),
        account_evidence=account_evidence or {"redacted": True, "raw_account_identifiers_present": False},
        market_data_evidence=_market_data_evidence(raw_payload, sample, as_of) if raw_payload and sample else {},
        normalized_snapshot=normalized_snapshot,
        checksums=_checksums(raw_payload, normalized_snapshot),
        safety=safety_manifest(request.mode, sandbox_network_attempted=request.mode == "sandbox_network"),
    )
    result.validate()
    return result


def _fingerprint(value: str) -> str:
    return "fp_" + hashlib.sha256(f"br30b|{value}".encode("utf-8")).hexdigest()[:16]


def _checksum(value: dict[str, Any]) -> str:
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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


def _validate_safety(manifest: dict[str, Any]) -> None:
    for field_name in (
        "account_mutation_methods_available",
        "execution_methods_available",
        "external_routing_paths_available",
        "position_change_methods_available",
        "live_trading_authorization_available",
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
        "live_trading_enabled",
    ):
        if manifest.get(field_name) is not False:
            raise ValueError(f"BR-30B smoke test cannot allow {field_name}")
    if manifest.get("LIVE TRADING") != "DISABLED":
        raise ValueError("BR-30B smoke test must keep LIVE TRADING disabled")
