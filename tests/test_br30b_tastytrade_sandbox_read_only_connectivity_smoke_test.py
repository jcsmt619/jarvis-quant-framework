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
    OAuthBridgeRequest,
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
    OPERATOR_CONFIRMATION_VALUE,
    PHASE_ID,
    SandboxCustomerDiscovery,
    SandboxClientError,
    SandboxMarketDataEvent,
    SandboxMarketDataSample,
    SandboxQuoteToken,
    SandboxSmokeTestRequest,
    TastytradeSandboxConcreteReadOnlyNetworkClient,
    TastytradeSandboxOAuthRefreshTokenClient,
    USER_AGENT,
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
    assert manifest["oauth_contract_phase"] == "BR-30B2"
    assert manifest["oauth_token_request_uses_json_body"] is True
    assert manifest["oauth_token_request_omits_client_id"] is True
    assert manifest["oauth_error_bodies_persisted"] is False
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


def test_br30b_accepts_provider_granted_trade_scope_when_effective_capabilities_remain_false() -> None:
    result = build_tastytrade_sandbox_read_only_connectivity_smoke_test(
        SandboxSmokeTestRequest(mode="sandbox_network", as_of=AS_OF),
        oauth_bridge=valid_bridge(
            OAuthTokenResponse("mock-access-token", AS_OF + timedelta(minutes=15), ("openid", "read", "trade"))
        ),
        sandbox_client=FakeSandboxClient(),
    )

    assert result.accepted_for_monitoring is True
    assert result.safety["execution_methods_available"] is False
    assert result.safety["broker_order_call_performed"] is False
    assert result.safety["live_trading_enabled"] is False


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


def test_br30b1_concrete_token_exchange_uses_only_oauth_post_and_redacts_tokens() -> None:
    transport = FakeHttpTransport(
        {
            ("POST", "https://api.cert.tastyworks.com/oauth/token"): FakeResponse(
                200,
                "https://api.cert.tastyworks.com/oauth/token",
                {"access_token": "mock-access-token", "expires_in": 900, "scope": "openid read trade", "token_type": "Bearer"},
            )
        }
    )
    client = TastytradeSandboxOAuthRefreshTokenClient(http_transport=transport)

    response = client.refresh_access_token(FakeVault().credentials, ("openid", "read"), AS_OF)
    call = transport.calls[0]

    assert response.scopes == ("openid", "read", "trade")
    assert call["method"] == "POST"
    assert call["url"] == "https://api.cert.tastyworks.com/oauth/token"
    assert call["allow_redirects"] is False
    assert call["headers"] == {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
    }
    assert call["data"] is None
    assert set(call["json_body"]) == {"grant_type", "refresh_token", "client_secret", "scope"}
    assert call["json_body"]["grant_type"] == "refresh_token"
    assert call["json_body"]["scope"] == "openid read"
    assert "client_id" not in call["json_body"]
    assert "client_id" not in call["url"]
    assert "mock-access-token" not in str(client.request_evidence)
    assert "mock-client-secret" not in str(client.request_evidence)
    assert "mock-refresh-token" not in str(client.request_evidence)


def test_br30b2_oauth_token_contract_falls_back_to_requested_scopes_when_scope_absent() -> None:
    transport = FakeHttpTransport(
        {
            ("POST", "https://api.cert.tastyworks.com/oauth/token"): FakeResponse(
                200,
                "https://api.cert.tastyworks.com/oauth/token",
                {"access_token": "mock-access-token", "expires_in": 900, "token_type": "Bearer"},
            )
        }
    )
    client = TastytradeSandboxOAuthRefreshTokenClient(http_transport=transport)

    response = client.refresh_access_token(FakeVault().credentials, ("openid", "read"), AS_OF)

    assert response.scopes == ("openid", "read")
    assert response.token_type == "Bearer"


def test_br30b2_oauth_token_contract_keeps_provider_trade_scope_isolated_by_bridge() -> None:
    transport = FakeHttpTransport(
        {
            ("POST", "https://api.cert.tastyworks.com/oauth/token"): FakeResponse(
                200,
                "https://api.cert.tastyworks.com/oauth/token",
                {"access_token": "mock-access-token", "expires_in": 900, "scope": "openid read trade", "token_type": "Bearer"},
            )
        }
    )
    token_client = TastytradeSandboxOAuthRefreshTokenClient(http_transport=transport)
    bridge = SecureLocalOAuthRuntimeBridge(vault=FakeVault(), token_client=token_client)

    result = bridge.get_access_token_for_read_only_client(
        request=OAuthBridgeRequest(mode="local_runtime", as_of=AS_OF)
    )[0]

    assert result.access_token_ready is True
    assert result.token_summary["provider_scope_contains_trade"] is True
    assert result.safety["order_create_capability"] is False
    assert result.safety["broker_order_call_performed"] is False
    assert result.safety["live_trading_enabled"] is False


def test_br30b2_oauth_token_contract_blocks_malformed_success_response() -> None:
    transport = FakeHttpTransport(
        {
            ("POST", "https://api.cert.tastyworks.com/oauth/token"): FakeResponse(
                200,
                "https://api.cert.tastyworks.com/oauth/token",
                {"access_token": "mock-access-token", "expires_in": "900", "scope": "openid read", "token_type": "Bearer"},
            )
        }
    )
    client = TastytradeSandboxOAuthRefreshTokenClient(http_transport=transport)

    with pytest.raises(SandboxClientError) as exc:
        client.refresh_access_token(FakeVault().credentials, ("openid", "read"), AS_OF)

    assert exc.value.reason == "malformed_payload"


@pytest.mark.parametrize(
    ("status", "expected_reason"),
    [
        (400, "bad_request"),
        (401, "unauthorized"),
        (403, "forbidden"),
        (429, "rate_limit"),
        (500, "provider_server_error"),
        (503, "provider_server_error"),
    ],
)
def test_br30b2_oauth_token_contract_classifies_errors_without_response_body(
    status: int,
    expected_reason: str,
) -> None:
    transport = FakeHttpTransport(
        {
            ("POST", "https://api.cert.tastyworks.com/oauth/token"): FakeResponse(
                status,
                "https://api.cert.tastyworks.com/oauth/token",
                {"error": "provider_body_not_persisted"},
            )
        }
    )
    client = TastytradeSandboxOAuthRefreshTokenClient(http_transport=transport)

    with pytest.raises(SandboxClientError) as exc:
        client.refresh_access_token(FakeVault().credentials, ("openid", "read"), AS_OF)

    assert exc.value.reason == expected_reason
    assert "provider_body_not_persisted" not in str(exc.value)
    assert "provider_body_not_persisted" not in str(client.request_evidence)
    assert "mock-refresh-token" not in str(exc.value)
    assert "mock-client-secret" not in str(exc.value)
    assert "mock-refresh-token" not in str(client.request_evidence)
    assert "mock-client-secret" not in str(client.request_evidence)


def test_br30b2_oauth_token_contract_rejects_redirected_or_non_sandbox_token_response() -> None:
    redirected = FakeHttpTransport(
        {
            ("POST", "https://api.cert.tastyworks.com/oauth/token"): FakeResponse(
                200,
                "https://api.tastytrade.com/oauth/token",
                {"access_token": "mock-access-token", "expires_in": 900, "scope": "openid read", "token_type": "Bearer"},
            )
        }
    )
    client = TastytradeSandboxOAuthRefreshTokenClient(http_transport=redirected)

    with pytest.raises(SandboxClientError) as exc:
        client.refresh_access_token(FakeVault().credentials, ("openid", "read"), AS_OF)

    assert exc.value.reason == "wrong_sandbox_host"
    assert redirected.calls[0]["allow_redirects"] is False

    with pytest.raises(SandboxClientError):
        FakeHttpTransport({}).force_request_through_firewall(
            "POST",
            "https://api.cert.tastytrade.com/oauth/token",
            is_oauth_token_refresh=True,
        )


def test_br30b1_concrete_client_discovers_accounts_and_quote_token_with_redacted_evidence() -> None:
    transport = FakeHttpTransport.valid()
    websocket = FakeWebSocketTransport()
    client = TastytradeSandboxConcreteReadOnlyNetworkClient(http_transport=transport, websocket_transport=websocket)
    token = InMemoryAccessToken("tastytrade", "sandbox", "mock-access-token", AS_OF + timedelta(minutes=15), ("openid", "read"))

    result = build_tastytrade_sandbox_read_only_connectivity_smoke_test(
        SandboxSmokeTestRequest(mode="sandbox_network", as_of=AS_OF),
        oauth_bridge=valid_bridge(),
        sandbox_client=client,
    )
    payload = tastytrade_sandbox_read_only_connectivity_payload(result)

    assert client.discover_customer_accounts(token, AS_OF).account_ids == ("raw-acct-001", "raw-acct-002")
    assert payload["accepted_for_monitoring"] is True
    assert payload["market_data_evidence"]["request_records"][0]["method"] == "GET"
    assert payload["market_data_evidence"]["request_records"][0]["path"] == "/customers/me/accounts"
    assert payload["market_data_evidence"]["request_records"][1]["path"] == "/api-quote-tokens"
    assert payload["market_data_evidence"]["provider_resource_write_count"] == 0
    assert payload["market_data_evidence"]["order_call_count"] == 0
    assert payload["market_data_evidence"]["mutation_call_count"] == 0
    assert payload["market_data_evidence"]["routing_call_count"] == 0
    assert payload["market_data_evidence"]["execution_call_count"] == 0
    assert websocket.connected_url == "wss://streamer.cert.tastyworks.com/quote"
    assert "mock-access-token" not in str(payload)
    assert "mock-quote-token" not in str(payload)
    assert "raw-acct-001" not in str(payload)


@pytest.mark.parametrize(
    ("status", "expected_reason"),
    [
        (401, "unauthorized"),
        (403, "forbidden"),
        (429, "rate_limit"),
        (500, "provider_server_error"),
    ],
)
def test_br30b1_concrete_client_maps_http_failures_to_sanitized_reasons(status: int, expected_reason: str) -> None:
    transport = FakeHttpTransport(
        {
            ("GET", "https://api.cert.tastyworks.com/customers/me/accounts"): FakeResponse(
                status,
                "https://api.cert.tastyworks.com/customers/me/accounts",
                {"error": "redacted"},
            )
        }
    )
    client = TastytradeSandboxConcreteReadOnlyNetworkClient(http_transport=transport, websocket_transport=FakeWebSocketTransport())

    result = build_tastytrade_sandbox_read_only_connectivity_smoke_test(
        SandboxSmokeTestRequest(mode="sandbox_network", as_of=AS_OF),
        oauth_bridge=valid_bridge(),
        sandbox_client=client,
    )

    assert result.accepted_for_monitoring is False
    assert expected_reason in result.rejection_reasons


@pytest.mark.parametrize(
    ("method", "url"),
    [
        ("GET", "https://api.tastytrade.com/customers/me/accounts"),
        ("GET", "https://api.cert.tastytrade.com/customers/me/accounts"),
        ("GET", "http://api.cert.tastyworks.com/customers/me/accounts"),
        ("POST", "https://api.cert.tastyworks.com/customers/me/accounts"),
        ("GET", "https://api.cert.tastyworks.com/accounts/123/orders"),
    ],
)
def test_br30b1_firewall_rejects_production_alternate_http_write_and_order_paths(method: str, url: str) -> None:
    transport = FakeHttpTransport({})

    with pytest.raises(SandboxClientError):
        transport.force_request_through_firewall(method, url)


def test_br30b1_rejects_cross_host_redirect_and_websocket_substitution() -> None:
    redirected = FakeHttpTransport(
        {
            ("GET", "https://api.cert.tastyworks.com/customers/me/accounts"): FakeResponse(
                200,
                "https://api.tastytrade.com/customers/me/accounts",
                {"data": {"accounts": [{"account-number": "raw-acct"}]}},
            )
        }
    )
    client = TastytradeSandboxConcreteReadOnlyNetworkClient(http_transport=redirected, websocket_transport=FakeWebSocketTransport())

    assert _blocked_reason_for_client(client) == "wrong_sandbox_host"

    substituted = FakeHttpTransport.valid(quote_url="https://streamer.cert.tastyworks.com/quote")
    client = TastytradeSandboxConcreteReadOnlyNetworkClient(http_transport=substituted, websocket_transport=FakeWebSocketTransport())

    assert _blocked_reason_for_client(client) == "websocket_endpoint_rejected"


@pytest.mark.parametrize(
    ("case", "expected_reason"),
    [
        ("timeout", "timeout"),
        ("malformed_json", "malformed_payload"),
        ("missing_symbols", "missing_symbol"),
        ("disconnect", "market_data_disconnect"),
    ],
)
def test_br30b1_concrete_client_rejects_timeout_malformed_json_missing_symbols_and_disconnect(
    case: str,
    expected_reason: str,
) -> None:
    if case == "timeout":
        client = TastytradeSandboxConcreteReadOnlyNetworkClient(
            http_transport=FakeHttpTransport.valid(timeout=True),
            websocket_transport=FakeWebSocketTransport(),
        )
    elif case == "malformed_json":
        client = TastytradeSandboxConcreteReadOnlyNetworkClient(
            http_transport=FakeHttpTransport.valid(malformed=True),
            websocket_transport=FakeWebSocketTransport(),
        )
    elif case == "missing_symbols":
        client = TastytradeSandboxConcreteReadOnlyNetworkClient(
            http_transport=FakeHttpTransport.valid(),
            websocket_transport=FakeWebSocketTransport(messages_for=("SPY",)),
        )
    else:
        client = TastytradeSandboxConcreteReadOnlyNetworkClient(
            http_transport=FakeHttpTransport.valid(),
            websocket_transport=FakeWebSocketTransport(disconnect=True),
        )

    assert _blocked_reason_for_client(client) == expected_reason


def test_br30b1_operator_runner_requires_exact_confirmation_value() -> None:
    script = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "--confirm" in script
    assert "OPERATOR_CONFIRMATION_VALUE" in script
    assert "KeyringCredentialVault()" in script
    assert "TastytradeSandboxConcreteReadOnlyNetworkClient()" in script


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
        sandbox_host: str = "api.cert.tastyworks.com",
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


class FakeResponse:
    def __init__(self, status_code: int, url: str, payload: object, *, json_error: bool = False) -> None:
        self.status_code = status_code
        self.url = url
        self.payload = payload
        self.json_error = json_error

    def json(self) -> object:
        if self.json_error:
            raise ValueError("malformed")
        return self.payload


class FakeHttpTransport:
    def __init__(
        self,
        responses: dict[tuple[str, str], FakeResponse],
        *,
        timeout: bool = False,
    ) -> None:
        self.responses = responses
        self.timeout = timeout
        self.calls: list[dict[str, object]] = []

    @classmethod
    def valid(
        cls,
        *,
        quote_url: str = "wss://streamer.cert.tastyworks.com/quote",
        timeout: bool = False,
        malformed: bool = False,
    ) -> "FakeHttpTransport":
        return cls(
            {
                ("GET", "https://api.cert.tastyworks.com/customers/me/accounts"): FakeResponse(
                    200,
                    "https://api.cert.tastyworks.com/customers/me/accounts",
                    {"data": {"customer-id": "raw-customer", "accounts": [{"account-number": "raw-acct-001"}, {"account-number": "raw-acct-002"}]}},
                    json_error=malformed,
                ),
                ("GET", "https://api.cert.tastyworks.com/api-quote-tokens"): FakeResponse(
                    200,
                    "https://api.cert.tastyworks.com/api-quote-tokens",
                    {
                        "data": {
                            "token": "mock-quote-token",
                            "websocket_url": quote_url,
                            "feed_identity": "tastytrade.market-data.read-only",
                        }
                    },
                ),
            },
            timeout=timeout,
        )

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        data: dict[str, str] | None = None,
        json_body: dict[str, str] | None = None,
        timeout: tuple[float, float] | float | None = None,
        allow_redirects: bool = False,
    ) -> FakeResponse:
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": headers,
                "data": data,
                "json_body": json_body,
                "timeout": timeout,
                "allow_redirects": allow_redirects,
            }
        )
        if self.timeout:
            raise TimeoutError("timeout")
        return self.responses[(method, url)]

    def force_request_through_firewall(self, method: str, url: str, *, is_oauth_token_refresh: bool = False) -> None:
        from engines.moonshot.deterministic import br30b_tastytrade_sandbox_read_only_connectivity_smoke_test as br30b

        br30b._assert_firewall_allowed(method, url, is_oauth_token_refresh=is_oauth_token_refresh)  # type: ignore[attr-defined]


class FakeWebSocketTransport:
    def __init__(
        self,
        *,
        messages_for: tuple[str, ...] = APPROVED_SYMBOLS,
        disconnect: bool = False,
    ) -> None:
        self.messages_for = messages_for
        self.disconnect = disconnect
        self.connected_url: str | None = None

    def connect(
        self,
        url: str,
        *,
        headers: dict[str, str],
        timeout: float,
    ) -> "FakeWebSocketConnection":
        self.connected_url = url
        if self.disconnect:
            raise RuntimeError("disconnect")
        return FakeWebSocketConnection(self.messages_for)


class FakeWebSocketConnection:
    def __init__(self, messages_for: tuple[str, ...]) -> None:
        exchange_time = AS_OF - timedelta(minutes=15)
        self.messages = [
            json_message(
                {
                    "event_type": "bar",
                    "symbol": symbol,
                    "provider_timestamp": (exchange_time + timedelta(seconds=5)).isoformat(),
                    "exchange_timestamp": exchange_time.isoformat(),
                    "open": 620.0,
                    "high": 626.0,
                    "low": 619.0,
                    "close": 625.0,
                    "volume": 1000,
                }
            )
            for symbol in messages_for
        ]
        self.sent: list[str] = []
        self.closed = False

    def send(self, payload: str) -> None:
        self.sent.append(payload)

    def recv(self) -> str:
        if not self.messages:
            raise TimeoutError("bounded sample exhausted")
        return self.messages.pop(0)

    def close(self) -> None:
        self.closed = True


def json_message(payload: dict[str, object]) -> str:
    import json

    return json.dumps(payload)


def _blocked_reason_for_client(client: TastytradeSandboxConcreteReadOnlyNetworkClient) -> str:
    result = build_tastytrade_sandbox_read_only_connectivity_smoke_test(
        SandboxSmokeTestRequest(mode="sandbox_network", as_of=AS_OF),
        oauth_bridge=valid_bridge(),
        sandbox_client=client,
    )
    assert result.accepted_for_monitoring is False
    return result.rejection_reasons[0]


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
