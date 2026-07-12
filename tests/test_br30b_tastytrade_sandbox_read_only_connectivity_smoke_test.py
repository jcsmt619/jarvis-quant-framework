from __future__ import annotations

import shutil
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from engines.moonshot.deterministic.br26_read_only_data_snapshot_import_contract import (
    import_read_only_data_snapshot,
)
from engines.moonshot.deterministic.br30a_secure_local_oauth_runtime_bridge import (
    InMemoryAccessToken,
    MissingSecretError,
    OAuthRuntimeCredentials,
    OAuthTokenResponse,
    SecureLocalOAuthRuntimeBridge,
    VaultUnavailableError,
)
from engines.moonshot.deterministic.br30b_tastytrade_sandbox_read_only_connectivity_smoke_test import (
    APPROVED_SYMBOLS,
    DEFAULT_REPORT_DIR,
    JSON_REPORT_NAME,
    MARKDOWN_REPORT_NAME,
    MODULE_NAME,
    NORMALIZED_SNAPSHOT_NAME,
    PHASE_ID,
    SandboxCustomerDiscovery,
    SandboxMarketDataEvent,
    SandboxMarketDataSample,
    SandboxQuoteToken,
    SandboxSmokeTestRequest,
    build_tastytrade_sandbox_read_only_connectivity_smoke_test,
    render_markdown_tastytrade_sandbox_read_only_connectivity,
    run_tastytrade_sandbox_read_only_connectivity_smoke_test,
    safety_manifest,
    tastytrade_sandbox_read_only_connectivity_payload,
)
from risk.policies import BLOCKED_BY_SAFETY_GATE, HUMAN_REVIEW_REQUIRED


AS_OF = datetime(2026, 7, 11, 16, 5, tzinfo=timezone.utc)
MODULE_PATH = Path("engines/moonshot/deterministic/br30b_tastytrade_sandbox_read_only_connectivity_smoke_test.py")
SCRIPT_PATH = Path("scripts/run_br30b_tastytrade_sandbox_read_only_connectivity_smoke_test.py")
DOC_PATH = Path("docs/brendan_strategy/br30b_tastytrade_sandbox_read_only_connectivity_smoke_test.md")


def test_br30b_default_runtime_is_offline_and_fail_closed() -> None:
    result = build_tastytrade_sandbox_read_only_connectivity_smoke_test(
        SandboxSmokeTestRequest(as_of=AS_OF)
    )
    payload = tastytrade_sandbox_read_only_connectivity_payload(result)

    assert payload["phase"] == PHASE_ID
    assert payload["module"] == MODULE_NAME
    assert payload["label"] == BLOCKED_BY_SAFETY_GATE
    assert payload["request_mode"] == "offline"
    assert payload["accepted_for_monitoring"] is False
    assert "runtime_mode_not_allowed" in payload["rejection_reasons"]
    assert payload["safety"]["offline_by_default"] is True
    assert payload["safety"]["fail_closed_by_default"] is True
    assert payload["safety"]["LIVE TRADING"] == "DISABLED"


def test_br30b_safety_manifest_blocks_execution_mutation_routing_and_live_trading() -> None:
    manifest = safety_manifest()

    assert manifest["phase"] == PHASE_ID
    assert manifest["labels"]
    assert manifest["access_tokens_memory_only"] is True
    assert manifest["raw_account_identifiers_written"] is False
    assert manifest["account_mutation_methods_available"] is False
    assert manifest["execution_methods_available"] is False
    assert manifest["external_routing_paths_available"] is False
    assert manifest["position_change_methods_available"] is False
    assert manifest["live_trading_authorization_available"] is False
    assert manifest["broker_order_call_performed"] is False
    assert manifest["real_paper_order_submitted"] is False
    assert manifest["live_trading_enabled"] is False


def test_br30b_sandbox_network_accepts_mocked_read_only_delayed_sample_and_normalizes_to_br26() -> None:
    result = build_tastytrade_sandbox_read_only_connectivity_smoke_test(
        SandboxSmokeTestRequest(mode="sandbox_network", as_of=AS_OF),
        oauth_bridge=valid_bridge(),
        sandbox_client=FakeSandboxClient(),
    )
    payload = tastytrade_sandbox_read_only_connectivity_payload(result)
    snapshot = payload["normalized_snapshot"]

    assert payload["label"] == HUMAN_REVIEW_REQUIRED
    assert payload["accepted_for_monitoring"] is True
    assert payload["rejection_reasons"] == ()
    assert payload["market_data_evidence"]["feed_identity"] == "tastytrade.market-data.read-only"
    assert payload["market_data_evidence"]["delay_classification"] == "delayed_sandbox"
    assert set(payload["market_data_evidence"]["symbols"]) == {"SPY", "QQQ"}
    assert payload["checksums"]["raw_checksum_sha256"]
    assert payload["checksums"]["normalized_checksum_sha256"]
    assert snapshot["snapshot_version"] == "1"
    assert snapshot["provenance"]["schema_name"] == "br26.read_only_data_snapshot.v1"
    assert set(snapshot["symbols"]) == {"SPY", "QQQ"}
    assert len(snapshot["records"]) == 2
    assert "acct-raw-001" not in str(payload)
    assert "acct-raw-002" not in str(payload)
    assert "cust-raw-001" not in str(payload)
    assert "mock-access-token" not in str(payload)
    assert "mock-quote-token" not in str(payload)


def test_br30b_written_normalized_snapshot_is_importable_by_br26_when_approved() -> None:
    out_dir = Path(".codex_pytest_tmp/br30b_smoke")
    if out_dir.exists():
        shutil.rmtree(out_dir)

    result = run_tastytrade_sandbox_read_only_connectivity_smoke_test(
        request=SandboxSmokeTestRequest(mode="sandbox_network", as_of=AS_OF),
        out_dir=out_dir,
        oauth_bridge=valid_bridge(),
        sandbox_client=FakeSandboxClient(),
    )
    snapshot_path = out_dir / NORMALIZED_SNAPSHOT_NAME
    decision = import_read_only_data_snapshot(
        snapshot_path,
        approved_snapshot_paths=(snapshot_path,),
        as_of=AS_OF,
    )

    assert result.accepted_for_monitoring is True
    assert (out_dir / JSON_REPORT_NAME).exists()
    assert (out_dir / MARKDOWN_REPORT_NAME).exists()
    assert snapshot_path.exists()
    assert decision.accepted is True
    assert DEFAULT_REPORT_DIR.name in str(DEFAULT_REPORT_DIR)

    shutil.rmtree(out_dir)


@pytest.mark.parametrize(
    ("case", "expected_reason"),
    [
        ("missing_bridge", "oauth_bridge_missing"),
        ("missing_client", "sandbox_client_missing"),
        ("token_failure", "access_token_unavailable"),
        ("expired_token", "token_expired"),
        ("unexpected_scope", "unexpected_scope"),
        ("wrong_host", "wrong_sandbox_host"),
        ("discovery_error", "customer_discovery_failed"),
        ("quote_token_error", "quote_token_failed"),
    ],
)
def test_br30b_rejects_token_host_and_read_only_setup_failures(
    case: str,
    expected_reason: str,
) -> None:
    bridge: SecureLocalOAuthRuntimeBridge | None = valid_bridge()
    client: FakeSandboxClient | None = FakeSandboxClient()
    if case == "missing_bridge":
        bridge = None
    elif case == "missing_client":
        client = None
    elif case == "token_failure":
        bridge = SecureLocalOAuthRuntimeBridge(vault=FakeVault(missing=True), token_client=FakeTokenClient.valid())
    elif case == "expired_token":
        bridge = valid_bridge(OAuthTokenResponse("mock-access-token", AS_OF - timedelta(seconds=1), ("openid", "read")))
    elif case == "unexpected_scope":
        bridge = valid_bridge(OAuthTokenResponse("mock-access-token", AS_OF + timedelta(minutes=15), ("openid", "read", "trade")))
    elif case == "wrong_host":
        client = FakeSandboxClient(sandbox_host="api.tastytrade.com")
    elif case == "discovery_error":
        client = FakeSandboxClient(discovery_error=True)
    elif case == "quote_token_error":
        client = FakeSandboxClient(quote_token_error=True)

    result = build_tastytrade_sandbox_read_only_connectivity_smoke_test(
        SandboxSmokeTestRequest(mode="sandbox_network", as_of=AS_OF),
        oauth_bridge=bridge,
        sandbox_client=client,
    )

    assert result.accepted_for_monitoring is False
    assert result.label == BLOCKED_BY_SAFETY_GATE
    assert expected_reason in result.rejection_reasons


@pytest.mark.parametrize(
    ("case", "expected_reason"),
    [
        ("disconnect", "market_data_disconnect"),
        ("reconnect", "reconnect_boundary"),
        ("rate_limit", "rate_limit"),
        ("duplicate", "duplicate_event"),
        ("stale", "stale_quote"),
        ("clock_skew", "clock_skew"),
        ("malformed", "malformed_payload"),
        ("missing_symbol", "missing_symbol"),
        ("stream_error", "market_data_disconnect"),
    ],
)
def test_br30b_rejects_market_data_boundary_failures(case: str, expected_reason: str) -> None:
    sample_by_case = {
        "disconnect": valid_sample(disconnected=True),
        "reconnect": valid_sample(reconnect_count=1),
        "rate_limit": valid_sample(rate_limit_remaining=-1),
        "duplicate": valid_sample(duplicate=True),
        "stale": valid_sample(stale=True),
        "clock_skew": valid_sample(clock_skew=True),
        "malformed": valid_sample(malformed=True),
        "missing_symbol": valid_sample(missing_symbol=True),
    }
    client = FakeSandboxClient(stream_error=True) if case == "stream_error" else FakeSandboxClient(sample=sample_by_case[case])

    result = build_tastytrade_sandbox_read_only_connectivity_smoke_test(
        SandboxSmokeTestRequest(mode="sandbox_network", as_of=AS_OF),
        oauth_bridge=valid_bridge(),
        sandbox_client=client,
    )

    assert result.accepted_for_monitoring is False
    assert result.label == BLOCKED_BY_SAFETY_GATE
    assert expected_reason in result.rejection_reasons


def test_br30b_redacts_account_identifiers_and_rejects_unredacted_evidence() -> None:
    result = build_tastytrade_sandbox_read_only_connectivity_smoke_test(
        SandboxSmokeTestRequest(mode="sandbox_network", as_of=AS_OF),
        oauth_bridge=valid_bridge(),
        sandbox_client=FakeSandboxClient(),
    )
    payload = tastytrade_sandbox_read_only_connectivity_payload(result)

    assert payload["account_evidence"]["redacted"] is True
    assert payload["account_evidence"]["raw_account_identifiers_present"] is False
    assert payload["account_evidence"]["customer_fingerprint"].startswith("fp_")
    assert all(value.startswith("fp_") for value in payload["account_evidence"]["account_fingerprints"])

    with pytest.raises(ValueError, match="account evidence must be redacted"):
        replace(
            result,
            account_evidence={
                "customer_fingerprint": "raw_customer_id",
                "account_fingerprints": ("account_id_123",),
                "raw_account_identifiers_present": True,
                "redacted": False,
            },
        ).validate()


def test_br30b_markdown_script_and_doc_record_required_safety_sections() -> None:
    result = build_tastytrade_sandbox_read_only_connectivity_smoke_test(
        SandboxSmokeTestRequest(mode="sandbox_network", as_of=AS_OF),
        oauth_bridge=valid_bridge(),
        sandbox_client=FakeSandboxClient(),
    )
    markdown = render_markdown_tastytrade_sandbox_read_only_connectivity(result)
    doc = DOC_PATH.read_text(encoding="utf-8")
    script = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "BR-30B Tastytrade Sandbox Read Only Connectivity Smoke Test" in markdown
    assert "LIVE TRADING: DISABLED" in markdown
    assert "Default execution is fixture-only/offline and fail closed" in doc
    assert "Access tokens remain memory-only" in doc
    assert "Raw account identifiers must not appear" in doc
    assert "does not provide account mutation methods" in doc
    assert "does not provide execution methods" in doc
    assert "does not add external routing" in doc
    assert "does not change positions" in doc
    assert "does not authorize live trading" in doc
    assert "live_trading_enabled=false" in doc
    assert "JSON_REPORT_NAME" in script
    assert "MARKDOWN_REPORT_NAME" in script


def test_br30b_validation_rejects_unsafe_safety_mutations() -> None:
    result = build_tastytrade_sandbox_read_only_connectivity_smoke_test(
        SandboxSmokeTestRequest(as_of=AS_OF)
    )

    with pytest.raises(ValueError, match="cannot allow live_trading_enabled"):
        replace(result, safety={**result.safety, "live_trading_enabled": True}).validate()
    with pytest.raises(ValueError, match="cannot allow broker_order_call_performed"):
        replace(result, safety={**result.safety, "broker_order_call_performed": True}).validate()
    with pytest.raises(ValueError, match="cannot allow execution_methods_available"):
        replace(result, safety={**result.safety, "execution_methods_available": True}).validate()
    with pytest.raises(ValueError, match="must keep LIVE TRADING disabled"):
        replace(result, safety={**result.safety, "LIVE TRADING": "ENABLED"}).validate()


def test_br30b_source_does_not_introduce_order_paths_or_forbidden_labels() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    disallowed = [
        "BUY" + "_NOW",
        "SELL" + "_NOW",
        "EXECUTE" + "_TRADE",
        "AUTO" + "_TRADE",
        "submit_order",
        "place_order",
        "create_order",
        "cancel_order",
        "requests.",
        "httpx.",
        "urllib.request",
    ]

    for token in disallowed:
        assert token not in source


def valid_bridge(response: OAuthTokenResponse | None = None) -> SecureLocalOAuthRuntimeBridge:
    return SecureLocalOAuthRuntimeBridge(
        vault=FakeVault(),
        token_client=FakeTokenClient(response or OAuthTokenResponse("mock-access-token", AS_OF + timedelta(minutes=15), ("openid", "read"))),
    )


def valid_sample(
    *,
    disconnected: bool = False,
    reconnect_count: int = 0,
    rate_limit_remaining: int = 10,
    duplicate: bool = False,
    stale: bool = False,
    clock_skew: bool = False,
    malformed: bool = False,
    missing_symbol: bool = False,
) -> SandboxMarketDataSample:
    exchange_time = AS_OF - (timedelta(minutes=45) if stale else timedelta(minutes=15))
    provider_time = exchange_time + (timedelta(minutes=5) if clock_skew else timedelta(seconds=5))
    acquisition_time = AS_OF - timedelta(seconds=5)
    symbols = ("SPY",) if missing_symbol else APPROVED_SYMBOLS
    events: list[SandboxMarketDataEvent] = []
    for symbol in symbols:
        events.append(
            SandboxMarketDataEvent(
                event_id=f"{symbol}-bar",
                event_type="bar",
                symbol=symbol,
                provider_timestamp=provider_time.isoformat(),
                exchange_timestamp=exchange_time.isoformat(),
                acquisition_timestamp=acquisition_time.isoformat(),
                open=620.0 if not malformed else None,
                high=626.0,
                low=619.0,
                close=625.0,
                volume=1000,
                rate_limit_remaining=rate_limit_remaining,
            )
        )
        events.append(
            SandboxMarketDataEvent(
                event_id=f"{symbol}-quote",
                event_type="quote",
                symbol=symbol,
                provider_timestamp=provider_time.isoformat(),
                exchange_timestamp=exchange_time.isoformat(),
                acquisition_timestamp=acquisition_time.isoformat(),
                bid=624.9,
                ask=625.1,
                rate_limit_remaining=rate_limit_remaining,
            )
        )
    if duplicate:
        events = [*events, replace(events[0], event_id="duplicate-bar")]
    return SandboxMarketDataSample(
        connected=True,
        disconnected=disconnected,
        reconnect_count=reconnect_count,
        events=tuple(events),
    )


class FakeSandboxClient:
    provider_name = "tastytrade"

    def __init__(
        self,
        *,
        sandbox_host: str = "api.cert.tastytrade.com",
        discovery_error: bool = False,
        quote_token_error: bool = False,
        stream_error: bool = False,
        sample: SandboxMarketDataSample | None = None,
    ) -> None:
        self.sandbox_host = sandbox_host
        self.discovery_error = discovery_error
        self.quote_token_error = quote_token_error
        self.stream_error = stream_error
        self.sample = sample or valid_sample()

    def discover_customer_accounts(self, token: InMemoryAccessToken, as_of: datetime) -> SandboxCustomerDiscovery:
        if self.discovery_error:
            raise RuntimeError("discovery failed")
        return SandboxCustomerDiscovery(
            customer_id="cust-raw-001",
            account_ids=("acct-raw-001", "acct-raw-002"),
            provider_timestamp=as_of.isoformat(),
            acquisition_timestamp=as_of.isoformat(),
        )

    def obtain_quote_token(self, token: InMemoryAccessToken, as_of: datetime) -> SandboxQuoteToken:
        if self.quote_token_error:
            raise RuntimeError("quote token failed")
        return SandboxQuoteToken(
            quote_token="mock-quote-token",
            feed_identity="tastytrade.market-data.read-only",
            provider_timestamp=as_of.isoformat(),
            acquisition_timestamp=as_of.isoformat(),
        )

    def stream_delayed_market_data(
        self,
        quote_token: SandboxQuoteToken,
        symbols: tuple[str, ...],
        as_of: datetime,
    ) -> SandboxMarketDataSample:
        if self.stream_error:
            raise RuntimeError("stream failed")
        return self.sample


class FakeVault:
    def __init__(self, *, missing: bool = False, unavailable: bool = False) -> None:
        self.missing = missing
        self.unavailable = unavailable
        self.credentials = OAuthRuntimeCredentials(
            "tastytrade",
            "sandbox",
            "mock-client-id",
            "mock-client-secret",
            "mock-refresh-token",
        )

    def store_credentials(self, credentials: OAuthRuntimeCredentials) -> None:
        self.credentials = credentials

    def load_credentials(self, provider: str, environment: str) -> OAuthRuntimeCredentials:
        if self.unavailable:
            raise VaultUnavailableError("BR-30A credential vault is unavailable")
        if self.missing:
            raise MissingSecretError("BR-30A required OAuth credential is missing")
        return self.credentials

    def delete_credentials(self, provider: str, environment: str) -> None:
        self.missing = True


class FakeTokenClient:
    provider_name = "tastytrade"

    def __init__(self, response: OAuthTokenResponse) -> None:
        self.response = response

    @classmethod
    def valid(cls) -> "FakeTokenClient":
        return cls(OAuthTokenResponse("mock-access-token", AS_OF + timedelta(minutes=15), ("openid", "read")))

    def refresh_access_token(
        self,
        credentials: OAuthRuntimeCredentials,
        scopes: tuple[str, ...],
        as_of: datetime,
    ) -> OAuthTokenResponse:
        return self.response

    def revoke_access_token(self, access_token: InMemoryAccessToken) -> None:
        return None
