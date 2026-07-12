from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
import uuid
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
    DXLINK_ALLOWED_STDERR_CODES,
    DXLINK_CHILD_ENV_ALLOWLIST,
    DXLINK_CHILD_ENV_DENY_KEY_MARKERS,
    DXLINK_STDERR_MAX_BYTES,
    DXLINK_STDOUT_MAX_BYTES,
    JSON_REPORT_NAME,
    MARKDOWN_REPORT_NAME,
    MODULE_NAME,
    NORMALIZED_SNAPSHOT_NAME,
    OPERATOR_CONFIRMATION_VALUE,
    PHASE_ID,
    SandboxCustomerDiscovery,
    SandboxClientError,
    DXLinkSidecarCompleted,
    DXLINK_NODE_ARGV,
    SandboxMarketDataEvent,
    SandboxMarketDataSample,
    SandboxQuoteToken,
    SandboxSmokeTestRequest,
    TastytradeSandboxConcreteReadOnlyNetworkClient,
    TastytradeSandboxOAuthRefreshTokenClient,
    USER_AGENT,
    _dxlink_child_environment,
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
    assert manifest["real_paper_wrapper_connected"] is False
    assert manifest["real_paper_wrapper_attempted"] is False
    assert manifest["broker_order_call_performed"] is False
    assert manifest["real_paper_order_submitted"] is False
    assert manifest["live_trading_enabled"] is False
    assert manifest["dxlink_protocol_phase"] == "BR-30B4"
    assert manifest["dxlink_sidecar_shell_execution"] is False
    assert manifest["dxlink_allowed_symbols"] == APPROVED_SYMBOLS
    assert manifest["dxlink_allowed_event_types"] == ("Quote", "Candle")
    assert manifest["dxlink_feed_contract"] == "AUTO"
    assert manifest["dxlink_feed_data_format"] == "COMPACT"


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
    dxlink = FakeDXLinkRunner()
    client = TastytradeSandboxConcreteReadOnlyNetworkClient(http_transport=transport, dxlink_runner=dxlink)
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
    assert dxlink.calls[0]["argv"] == DXLINK_NODE_ARGV
    assert dxlink.calls[0]["shell"] is False
    assert "mock-quote-token" in dxlink.calls[0]["stdin"]
    assert "wss://streamer.cert.tastyworks.com/quote" in dxlink.calls[0]["stdin"]
    assert "mock-quote-token" not in str(dxlink.calls[0]["argv"])
    assert "wss://streamer.cert.tastyworks.com/quote" not in str(dxlink.calls[0]["argv"])
    assert "mock-access-token" not in str(payload)
    assert "mock-quote-token" not in str(payload)
    assert "raw-acct-001" not in str(payload)


def test_br30b4_dxlink_child_process_uses_fixed_argv_and_stdin_only_secret_transport() -> None:
    runner = FakeDXLinkRunner()
    client = TastytradeSandboxConcreteReadOnlyNetworkClient(
        http_transport=FakeHttpTransport.valid(),
        dxlink_runner=runner,
    )

    result = build_tastytrade_sandbox_read_only_connectivity_smoke_test(
        SandboxSmokeTestRequest(mode="sandbox_network", as_of=AS_OF),
        oauth_bridge=valid_bridge(),
        sandbox_client=client,
    )
    stdin_payload = json.loads(runner.calls[0]["stdin"])
    dxlink_record = result.market_data_evidence["dxlink_sidecar_records"][0]

    assert runner.calls[0]["argv"] == DXLINK_NODE_ARGV
    assert runner.calls[0]["shell"] is False
    assert stdin_payload == {
        "acquisitionTimestamp": AS_OF.isoformat(),
        "dxlinkUrl": "wss://streamer.cert.tastyworks.com/quote",
        "quoteToken": "mock-quote-token",
        "symbols": ["SPY", "QQQ"],
        "timeoutMs": 20000,
    }
    assert dxlink_record["stdin_only_secret_transport"] is True
    assert dxlink_record["environment_values_written"] is False
    assert dxlink_record["command_line_secret_values_written"] is False
    assert dxlink_record["temporary_files_written"] is False
    assert "mock-quote-token" not in str(result)
    assert "wss://streamer.cert.tastyworks.com/quote" not in str(result)


def test_br30b4_dxlink_sidecar_source_uses_official_sdk_compact_quote_and_candle_only() -> None:
    sidecar = Path("integrations/tastytrade_dxlink/dxlink_read_only_sidecar.mjs").read_text(encoding="utf-8")
    preflight = Path("integrations/tastytrade_dxlink/dxlink_runtime_preflight.mjs").read_text(encoding="utf-8")
    package = json.loads(Path("integrations/tastytrade_dxlink/package.json").read_text(encoding="utf-8"))
    lock = json.loads(Path("integrations/tastytrade_dxlink/package-lock.json").read_text(encoding="utf-8"))

    assert package["engines"]["node"] == ">=20"
    assert package["dependencies"]["@dxfeed/dxlink-api"] == "0.3.0"
    assert lock["packages"][""]["dependencies"]["@dxfeed/dxlink-api"] == "0.3.0"
    assert lock["packages"]["node_modules/@dxfeed/dxlink-api"]["version"] == "0.3.0"
    assert "DXLinkWebSocketClient" in sidecar
    assert "setAuthToken" in sidecar
    assert "DXLinkFeed" in sidecar
    assert "FeedContract.AUTO" in sidecar
    assert "FeedDataFormat.COMPACT" in sidecar
    assert "createRequire" not in preflight
    assert 'require("@dxfeed/dxlink-api/package.json")' not in preflight
    assert 'import("@dxfeed/dxlink-api/package.json")' not in preflight
    assert 'import.meta.resolve("@dxfeed/dxlink-api")' in preflight
    assert 'const SDK_PACKAGE = "@dxfeed/dxlink-api"' in preflight
    assert "fileURLToPath" in preflight
    assert "readFile(manifestPath" in preflight
    assert "JSON.parse(text)" in preflight
    assert "dxlink_package_metadata_unavailable" in preflight
    assert "dxlink_contract_mismatch" in preflight
    assert "connection_attempted: false" in preflight
    assert "credentials_accepted: false" in preflight
    assert '"Quote"' in sidecar
    assert '"Candle"' in sidecar
    assert "bidPrice" in sidecar
    assert "askPrice" in sidecar
    assert "open" in sidecar
    assert "high" in sidecar
    assert "low" in sidecar
    assert "close" in sidecar
    assert "volume" in sidecar
    for forbidden in ("Trade", "Greeks", "Summary", "Profile", "Underlying", "Order", "account-streaming"):
        assert f'"{forbidden}"' not in sidecar


def test_br30b4a_dxlink_sidecar_source_matches_pinned_sdk_contract() -> None:
    sidecar = Path("integrations/tastytrade_dxlink/dxlink_read_only_sidecar.mjs").read_text(encoding="utf-8")

    assert "new DXLinkWebSocketClient()" in sidecar
    assert "new DXLinkWebSocketClient(request.dxlinkUrl)" not in sidecar
    assert "connect(dxlinkUrl)" in sidecar
    assert "client.connect()" not in sidecar
    assert "client.connect(dxlinkUrl)" in sidecar
    assert "new DXLinkFeed(client, FeedContract.AUTO)" in sidecar
    assert "new DXLinkFeed(client, FeedContract.AUTO," not in sidecar
    assert "feed.configure" in sidecar
    assert "acceptAggregationPeriod" in sidecar
    assert "acceptEventFields" in sidecar
    assert "feed.addSubscriptions({ type: eventType, symbol })" in sidecar
    assert "symbols:" not in sidecar
    assert "fields:" not in sidecar
    assert "feed.addEventListener(listener)" in sidecar
    assert "addEventListener(\"event\"" not in sidecar
    assert "feed.on(" not in sidecar
    assert "boundedEventBatch" in sidecar


def test_br30b4a_dxlink_node_argv_is_absolute_and_environment_is_scrubbed(monkeypatch: pytest.MonkeyPatch) -> None:
    assert Path(DXLINK_NODE_ARGV[0]).is_absolute()
    assert Path(DXLINK_NODE_ARGV[0]).name.lower() in {"node.exe", "node"}
    assert DXLINK_NODE_ARGV[1] == str(Path("integrations/tastytrade_dxlink/dxlink_read_only_sidecar.mjs"))

    monkeypatch.setenv("PATH", "C:\\Windows\\System32")
    monkeypatch.setenv("SYSTEMROOT", "C:\\Windows")
    monkeypatch.setenv("BROKER_TOKEN", "must-not-pass")
    monkeypatch.setenv("API_KEY", "must-not-pass")
    monkeypatch.setenv("OAUTH_REFRESH_TOKEN", "must-not-pass")
    monkeypatch.setenv("CUSTOMER_ACCOUNT", "must-not-pass")

    child_env = _dxlink_child_environment()

    assert child_env["PATH"] == "C:\\Windows\\System32"
    assert child_env["SYSTEMROOT"] == "C:\\Windows"
    assert set(key.upper() for key in child_env) <= set(DXLINK_CHILD_ENV_ALLOWLIST)
    assert not any(marker in key.upper() for key in child_env for marker in DXLINK_CHILD_ENV_DENY_KEY_MARKERS)
    assert "must-not-pass" not in str(child_env)


def test_br30b4a_fake_sdk_harness_runs_actual_sidecar_offline() -> None:
    node = shutil.which("node.exe") or shutil.which("node")
    if node is None:
        pytest.skip("Node is not installed in this environment")
    tmp_path = Path(".codex_pytest_tmp") / f"br30b4a_fake_sdk_harness_{uuid.uuid4().hex}"
    sidecar_dir = tmp_path / "integrations" / "tastytrade_dxlink"
    sidecar_dir.mkdir(parents=True)
    shutil.copyfile(
        Path("integrations/tastytrade_dxlink/dxlink_read_only_sidecar.mjs"),
        sidecar_dir / "dxlink_read_only_sidecar.mjs",
    )
    fake_sdk_dir = sidecar_dir / "node_modules" / "@dxfeed" / "dxlink-api"
    fake_sdk_dir.mkdir(parents=True)
    (fake_sdk_dir / "package.json").write_text(
        json.dumps({"name": "@dxfeed/dxlink-api", "version": "0.3.0", "type": "module", "exports": "./index.mjs"}),
        encoding="utf-8",
    )
    (fake_sdk_dir / "index.mjs").write_text(_fake_dxlink_sdk_source(), encoding="utf-8")
    stdin_payload = json.dumps(
        {
            "quoteToken": "stdin-only-quote-token",
            "dxlinkUrl": "wss://streamer.cert.tastyworks.com/quote",
            "symbols": ["SPY", "QQQ"],
            "acquisitionTimestamp": AS_OF.isoformat(),
            "timeoutMs": 1000,
        },
        separators=(",", ":"),
    )

    completed = subprocess.run(
        [node, str(sidecar_dir / "dxlink_read_only_sidecar.mjs")],
        input=stdin_payload,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=5,
        shell=False,
        env={"PATH": str(Path(node).parent), "SYSTEMROOT": "C:\\Windows"},
    )
    envelope = json.loads(completed.stdout)

    assert completed.returncode == 0
    assert completed.stderr == ""
    assert envelope["ok"] is True
    assert envelope["connected"] is True
    assert {event["event_type"] for event in envelope["events"]} == {"Quote", "Candle"}
    assert {event["symbol"] for event in envelope["events"]} == {"SPY", "QQQ"}
    assert "stdin-only-quote-token" not in completed.stdout
    assert "streamer.cert.tastyworks.com" not in completed.stdout
    assert "stdin-only-quote-token" not in completed.stderr
    assert "streamer.cert.tastyworks.com" not in completed.stderr


def test_br30b4b_runtime_preflight_resolves_physical_manifest_without_package_subpath() -> None:
    completed = _run_fake_runtime_preflight()

    envelope = json.loads(completed.stdout)
    assert completed.returncode == 0
    assert completed.stderr == ""
    assert envelope == {
        "ok": True,
        "sdk": "@dxfeed/dxlink-api",
        "contract": "0.3.0",
        "connection_attempted": False,
        "credentials_accepted": False,
    }
    assert len(completed.stdout.encode("utf-8")) <= DXLINK_STDOUT_MAX_BYTES
    assert "quote-token" not in completed.stdout
    assert "client-secret" not in completed.stdout
    assert "wss://" not in completed.stdout


@pytest.mark.parametrize(
    ("manifest", "expected_code"),
    [
        ({"name": "wrong-package", "version": "0.3.0", "type": "module", "exports": "./index.mjs"}, "dxlink_contract_mismatch"),
        ({"name": "@dxfeed/dxlink-api", "version": "0.3.1", "type": "module", "exports": "./index.mjs"}, "dxlink_contract_mismatch"),
    ],
)
def test_br30b4b_runtime_preflight_rejects_wrong_package_name_and_version(
    manifest: dict[str, str],
    expected_code: str,
) -> None:
    completed = _run_fake_runtime_preflight(manifest=manifest)

    assert completed.returncode == 1
    assert completed.stdout == ""
    assert completed.stderr == expected_code
    assert "\\" not in completed.stderr
    assert "/" not in completed.stderr


@pytest.mark.parametrize(
    ("case", "expected_code"),
    [
        ("missing", "dxlink_package_metadata_unavailable"),
        ("malformed", "dxlink_package_metadata_unavailable"),
        ("ambiguous", "dxlink_package_metadata_unavailable"),
    ],
)
def test_br30b4b_runtime_preflight_rejects_missing_malformed_and_ambiguous_metadata(
    case: str,
    expected_code: str,
) -> None:
    completed = _run_fake_runtime_preflight(metadata_case=case)

    assert completed.returncode == 1
    assert completed.stdout == ""
    assert completed.stderr == expected_code
    assert completed.stderr in DXLINK_ALLOWED_STDERR_CODES
    assert len(completed.stderr.encode("utf-8")) <= DXLINK_STDERR_MAX_BYTES


def test_br30b4b_runtime_preflight_rejects_path_escape_when_sdk_entry_leaves_package_root() -> None:
    completed = _run_fake_runtime_preflight(metadata_case="escape_main")

    assert completed.returncode == 1
    assert completed.stdout == ""
    assert completed.stderr == "dxlink_package_metadata_unavailable"


def test_br30b4b_python_wrapper_rejects_mixed_or_additional_stderr() -> None:
    runner = FakeDXLinkRunner(returncode=1, stderr="dxlink_process_failed\nprovider stack")
    client = TastytradeSandboxConcreteReadOnlyNetworkClient(
        http_transport=FakeHttpTransport.valid(),
        dxlink_runner=runner,
    )

    assert _blocked_reason_for_client(client) == "dxlink_output_malformed"


def test_br30b3_concrete_client_parses_nested_and_direct_account_number_variants() -> None:
    transport = FakeHttpTransport.valid(
        account_payload={
            "data": {
                "customer-id": "raw-customer",
                "accounts": [
                    {"account": {"account-number": "raw-nested-acct"}},
                    {"account-number": "raw-direct-acct"},
                    {"account_number": "raw-underscore-acct"},
                ],
            }
        }
    )
    client = TastytradeSandboxConcreteReadOnlyNetworkClient(
        http_transport=transport,
        dxlink_runner=FakeDXLinkRunner(),
    )
    token = InMemoryAccessToken("tastytrade", "sandbox", "mock-access-token", AS_OF + timedelta(minutes=15), ("openid", "read"))

    discovery = client.discover_customer_accounts(token, AS_OF)
    evidence = tastytrade_sandbox_read_only_connectivity_payload(
        build_tastytrade_sandbox_read_only_connectivity_smoke_test(
            SandboxSmokeTestRequest(mode="sandbox_network", as_of=AS_OF),
            oauth_bridge=valid_bridge(),
            sandbox_client=client,
        )
    )["account_evidence"]

    assert discovery.account_ids == ("raw-nested-acct", "raw-direct-acct", "raw-underscore-acct")
    assert all(value.startswith("fp_") for value in evidence["account_fingerprints"])
    assert "raw-nested-acct" not in str(evidence)
    assert "raw-direct-acct" not in str(evidence)


def test_br30b3_concrete_client_parses_canonical_quote_token_data_wrapper_and_level() -> None:
    full_dxlink_url = "wss://streamer.cert.tastyworks.com/quote"
    transport = FakeHttpTransport.valid(
        quote_payload={
            "data": {
                "token": "mock-quote-token",
                "dxlink-url": full_dxlink_url,
                "level": "delayed",
                "feed_identity": "tastytrade.market-data.read-only",
            }
        }
    )
    client = TastytradeSandboxConcreteReadOnlyNetworkClient(
        http_transport=transport,
        dxlink_runner=FakeDXLinkRunner(),
    )
    token = InMemoryAccessToken("tastytrade", "sandbox", "mock-access-token", AS_OF + timedelta(minutes=15), ("openid", "read"))

    quote = client.obtain_quote_token(token, AS_OF)
    payload = tastytrade_sandbox_read_only_connectivity_payload(
        build_tastytrade_sandbox_read_only_connectivity_smoke_test(
            SandboxSmokeTestRequest(mode="sandbox_network", as_of=AS_OF),
            oauth_bridge=valid_bridge(),
            sandbox_client=client,
        )
    )

    assert quote.quote_token == "mock-quote-token"
    assert quote.websocket_url == full_dxlink_url
    assert quote.level == "delayed"
    assert payload["normalized_snapshot"]["provenance"]["source_file_name"] == NORMALIZED_SNAPSHOT_NAME
    assert payload["market_data_evidence"]["quote_token_level"] == "delayed"
    assert "mock-quote-token" not in str(payload)
    assert full_dxlink_url not in str(payload)


def test_br30b3_concrete_client_parses_top_level_canonical_quote_token_response() -> None:
    client = TastytradeSandboxConcreteReadOnlyNetworkClient(
        http_transport=FakeHttpTransport.valid(
            quote_payload={
                "token": "mock-quote-token",
                "dxlink-url": "wss://streamer.cert.tastyworks.com/quote",
                "level": "delayed",
            }
        ),
        dxlink_runner=FakeDXLinkRunner(),
    )
    token = InMemoryAccessToken("tastytrade", "sandbox", "mock-access-token", AS_OF + timedelta(minutes=15), ("openid", "read"))

    quote = client.obtain_quote_token(token, AS_OF)

    assert quote.quote_token == "mock-quote-token"
    assert quote.websocket_url == "wss://streamer.cert.tastyworks.com/quote"
    assert quote.level == "delayed"


@pytest.mark.parametrize(
    ("account_payload", "expected_reason"),
    [
        ({"data": {"accounts": [{"account": {}}]}}, "account_payload_malformed"),
        ({"data": {"accounts": "not-a-list"}}, "account_payload_malformed"),
        ({"data": "not-a-container"}, "account_payload_malformed"),
    ],
)
def test_br30b3_account_payload_malformed_uses_stage_specific_reason(
    account_payload: object,
    expected_reason: str,
) -> None:
    client = TastytradeSandboxConcreteReadOnlyNetworkClient(
        http_transport=FakeHttpTransport.valid(account_payload=account_payload),
        dxlink_runner=FakeDXLinkRunner(),
    )

    assert _blocked_reason_for_client(client) == expected_reason


@pytest.mark.parametrize(
    ("quote_payload", "expected_reason"),
    [
        ({"data": {"dxlink-url": "wss://streamer.cert.tastyworks.com/quote"}}, "quote_token_payload_malformed"),
        ({"data": {"token": "mock-quote-token"}}, "quote_token_payload_malformed"),
        ({"data": []}, "quote_token_payload_malformed"),
        (["unexpected-container"], "quote_token_payload_malformed"),
    ],
)
def test_br30b3_quote_token_payload_malformed_uses_stage_specific_reason(
    quote_payload: object,
    expected_reason: str,
) -> None:
    client = TastytradeSandboxConcreteReadOnlyNetworkClient(
        http_transport=FakeHttpTransport.valid(quote_payload=quote_payload),
        dxlink_runner=FakeDXLinkRunner(),
    )

    assert _blocked_reason_for_client(client) == expected_reason


@pytest.mark.parametrize(
    "quote_url",
    [
        "http://streamer.cert.tastyworks.com/quote",
        "https://streamer.cert.tastyworks.com/quote",
        "ws://streamer.cert.tastyworks.com/quote",
        "",
        "not a url",
    ],
)
def test_br30b3_quote_token_rejects_non_wss_missing_and_malformed_dxlink_urls(quote_url: str) -> None:
    client = TastytradeSandboxConcreteReadOnlyNetworkClient(
        http_transport=FakeHttpTransport.valid(
            quote_payload={"data": {"token": "mock-quote-token", "dxlink-url": quote_url}}
        ),
        dxlink_runner=FakeDXLinkRunner(),
    )

    reason = _blocked_reason_for_client(client)

    assert reason in {"websocket_endpoint_rejected", "quote_token_payload_malformed"}


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
    client = TastytradeSandboxConcreteReadOnlyNetworkClient(http_transport=transport, dxlink_runner=FakeDXLinkRunner())

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
    client = TastytradeSandboxConcreteReadOnlyNetworkClient(http_transport=redirected, dxlink_runner=FakeDXLinkRunner())

    assert _blocked_reason_for_client(client) == "wrong_sandbox_host"

    substituted = FakeHttpTransport.valid(quote_url="https://streamer.cert.tastyworks.com/quote")
    client = TastytradeSandboxConcreteReadOnlyNetworkClient(http_transport=substituted, dxlink_runner=FakeDXLinkRunner())

    assert _blocked_reason_for_client(client) == "websocket_endpoint_rejected"


@pytest.mark.parametrize(
    ("case", "expected_reason"),
    [
        ("timeout", "timeout"),
        ("malformed_json", "account_payload_malformed"),
        ("missing_symbols", "missing_symbol"),
        ("disconnect", "dxlink_process_failed"),
    ],
)
def test_br30b1_concrete_client_rejects_timeout_malformed_json_missing_symbols_and_disconnect(
    case: str,
    expected_reason: str,
) -> None:
    if case == "timeout":
        client = TastytradeSandboxConcreteReadOnlyNetworkClient(
            http_transport=FakeHttpTransport.valid(timeout=True),
            dxlink_runner=FakeDXLinkRunner(),
        )
    elif case == "malformed_json":
        client = TastytradeSandboxConcreteReadOnlyNetworkClient(
            http_transport=FakeHttpTransport.valid(malformed=True),
            dxlink_runner=FakeDXLinkRunner(),
        )
    elif case == "missing_symbols":
        client = TastytradeSandboxConcreteReadOnlyNetworkClient(
            http_transport=FakeHttpTransport.valid(),
            dxlink_runner=FakeDXLinkRunner(messages_for=("SPY",)),
        )
    else:
        client = TastytradeSandboxConcreteReadOnlyNetworkClient(
            http_transport=FakeHttpTransport.valid(),
            dxlink_runner=FakeDXLinkRunner(stderr="dxlink_process_failed", returncode=1),
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
        account_payload: object | None = None,
        quote_payload: object | None = None,
    ) -> "FakeHttpTransport":
        resolved_account_payload = (
            account_payload
            if account_payload is not None
            else {
                "data": {
                    "customer-id": "raw-customer",
                    "accounts": [
                        {"account": {"account-number": "raw-acct-001"}},
                        {"account": {"account-number": "raw-acct-002"}},
                    ],
                }
            }
        )
        resolved_quote_payload = (
            quote_payload
            if quote_payload is not None
            else {
                "data": {
                    "token": "mock-quote-token",
                    "dxlink-url": quote_url,
                    "level": "delayed",
                    "feed_identity": "tastytrade.market-data.read-only",
                }
            }
        )
        return cls(
            {
                ("GET", "https://api.cert.tastyworks.com/customers/me/accounts"): FakeResponse(
                    200,
                    "https://api.cert.tastyworks.com/customers/me/accounts",
                    resolved_account_payload,
                    json_error=malformed,
                ),
                ("GET", "https://api.cert.tastyworks.com/api-quote-tokens"): FakeResponse(
                    200,
                    "https://api.cert.tastyworks.com/api-quote-tokens",
                    resolved_quote_payload,
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


class FakeDXLinkRunner:
    def __init__(
        self,
        *,
        messages_for: tuple[str, ...] = APPROVED_SYMBOLS,
        returncode: int = 0,
        stderr: str = "",
        stdout: str | None = None,
        timed_out: bool = False,
    ) -> None:
        self.messages_for = messages_for
        self.returncode = returncode
        self.stderr = stderr
        self.stdout = stdout
        self.timed_out = timed_out
        self.calls: list[dict[str, object]] = []

    def run(
        self,
        argv: tuple[str, ...],
        stdin_payload: str,
        timeout_seconds: float,
    ) -> DXLinkSidecarCompleted:
        self.calls.append({"argv": argv, "stdin": stdin_payload, "timeout_seconds": timeout_seconds, "shell": False})
        return DXLinkSidecarCompleted(
            returncode=self.returncode,
            stdout=self.stdout if self.stdout is not None else dxlink_stdout(self.messages_for),
            stderr=self.stderr,
            timed_out=self.timed_out,
        )


def dxlink_stdout(symbols: tuple[str, ...] = APPROVED_SYMBOLS) -> str:
    exchange_time = AS_OF - timedelta(minutes=15)
    provider_time = exchange_time + timedelta(seconds=5)
    events: list[dict[str, object]] = []
    for symbol in symbols:
        events.append(
            {
                "event_type": "Quote",
                "symbol": symbol,
                "provider_timestamp": provider_time.isoformat(),
                "exchange_timestamp": exchange_time.isoformat(),
                "acquisition_timestamp": AS_OF.isoformat(),
                "bidPrice": 624.9,
                "askPrice": 625.1,
            }
        )
        events.append(
            {
                "event_type": "Candle",
                "symbol": f"{symbol}{{=1m}}",
                "provider_timestamp": provider_time.isoformat(),
                "exchange_timestamp": exchange_time.isoformat(),
                "acquisition_timestamp": AS_OF.isoformat(),
                "open": 620.0,
                "high": 626.0,
                "low": 619.0,
                "close": 625.0,
                "volume": 1000,
            }
        )
    return json_message({"ok": True, "connected": True, "disconnected": False, "reconnect_count": 0, "events": events})


def dxlink_stdout_without_candle() -> str:
    exchange_time = AS_OF - timedelta(minutes=15)
    provider_time = exchange_time + timedelta(seconds=5)
    events = [
        {
            "event_type": "Quote",
            "symbol": symbol,
            "provider_timestamp": provider_time.isoformat(),
            "exchange_timestamp": exchange_time.isoformat(),
            "acquisition_timestamp": AS_OF.isoformat(),
            "bidPrice": 624.9,
            "askPrice": 625.1,
        }
        for symbol in APPROVED_SYMBOLS
    ]
    return json_message({"ok": True, "connected": True, "disconnected": False, "reconnect_count": 0, "events": events})


def dxlink_stdout_with_event(event_type: str) -> str:
    exchange_time = AS_OF - timedelta(minutes=15)
    event = {
        "event_type": event_type,
        "symbol": "SPY",
        "provider_timestamp": exchange_time.isoformat(),
        "exchange_timestamp": exchange_time.isoformat(),
        "acquisition_timestamp": AS_OF.isoformat(),
        "bidPrice": 624.9,
        "askPrice": 625.1,
    }
    return json_message({"ok": True, "connected": True, "disconnected": False, "reconnect_count": 0, "events": [event]})


def json_message(payload: dict[str, object]) -> str:
    import json

    return json.dumps(payload)


def _fake_dxlink_sdk_source() -> str:
    return textwrap.dedent(
        """
        export const FeedContract = Object.freeze({ AUTO: "AUTO" });
        export const FeedDataFormat = Object.freeze({ COMPACT: "COMPACT" });

        export class DXLinkWebSocketClient {
          constructor() {
            if (arguments.length !== 0) {
              throw new Error("url-in-constructor");
            }
            globalThis.__client = this;
            this.closed = false;
          }
          setAuthToken(token) {
            if (typeof token !== "string" || token.length < 1) {
              throw new Error("auth");
            }
            this.tokenWasSet = true;
          }
          async connect(url) {
            if (arguments.length !== 1 || typeof url !== "string" || !url.startsWith("wss://")) {
              throw new Error("connect-contract");
            }
            if (!this.tokenWasSet) {
              throw new Error("auth");
            }
            this.connected = true;
          }
          close() {
            this.closed = true;
          }
        }

        export class DXLinkFeed {
          constructor(client, contract) {
            if (arguments.length !== 2 || contract !== FeedContract.AUTO || !client) {
              throw new Error("feed-contract");
            }
            this.subscriptions = [];
          }
          configure(config) {
            if (
              config.acceptAggregationPeriod !== 60 ||
              config.acceptDataFormat !== FeedDataFormat.COMPACT ||
              !config.acceptEventFields ||
              !Array.isArray(config.acceptEventFields.Quote) ||
              !Array.isArray(config.acceptEventFields.Candle)
            ) {
              throw new Error("configure-contract");
            }
          }
          addEventListener(listener) {
            if (arguments.length !== 1 || typeof listener !== "function") {
              throw new Error("listener-contract");
            }
            this.listener = listener;
          }
          addSubscriptions(subscription) {
            if (
              arguments.length !== 1 ||
              subscription.symbols !== undefined ||
              subscription.fields !== undefined ||
              typeof subscription.symbol !== "string" ||
              !["Quote", "Candle"].includes(subscription.type)
            ) {
              throw new Error("subscription-contract");
            }
            this.subscriptions.push(subscription);
            if (this.subscriptions.length === 4) {
              queueMicrotask(() => this.listener(events()));
            }
          }
        }

        function events() {
          return [
            quote("SPY"),
            candle("SPY{=1m}"),
            quote("QQQ"),
            candle("QQQ{=1m}"),
          ];
        }

        function quote(symbol) {
          return {
            type: "Quote",
            eventSymbol: symbol,
            time: "2026-07-11T15:50:05.000Z",
            bidPrice: 624.9,
            askPrice: 625.1,
          };
        }

        function candle(symbol) {
          return {
            type: "Candle",
            eventSymbol: symbol,
            time: "2026-07-11T15:50:05.000Z",
            eventTime: "2026-07-11T15:50:00.000Z",
            open: 620,
            high: 626,
            low: 619,
            close: 625,
            volume: 1000,
          };
        }
        """
    )


def _fake_preflight_sdk_source() -> str:
    return textwrap.dedent(
        """
        export const FeedContract = Object.freeze({ AUTO: "AUTO" });
        export const FeedDataFormat = Object.freeze({ COMPACT: "COMPACT" });

        export class DXLinkWebSocketClient {
          connect() {
            throw new Error("network-method-must-not-be-called");
          }
          setAuthToken() {
            throw new Error("credentials-must-not-be-accepted");
          }
        }

        export class DXLinkFeed {
          constructor(client, contract) {
            if (arguments.length !== 2 || contract !== FeedContract.AUTO || !client) {
              throw new Error("feed-contract");
            }
          }
          configure() {}
          addSubscriptions() {}
          addEventListener() {}
        }
        """
    )


def _make_fake_preflight_tree(
    tmp_path: Path,
    *,
    manifest: dict[str, str] | None = None,
    metadata_case: str = "valid",
) -> Path:
    sidecar_dir = tmp_path / "integrations" / "tastytrade_dxlink"
    sidecar_dir.mkdir(parents=True)
    shutil.copyfile(
        Path("integrations/tastytrade_dxlink/dxlink_runtime_preflight.mjs"),
        sidecar_dir / "dxlink_runtime_preflight.mjs",
    )
    fake_sdk_dir = sidecar_dir / "node_modules" / "@dxfeed" / "dxlink-api"
    fake_sdk_dir.mkdir(parents=True)
    resolved_manifest = manifest or {
        "name": "@dxfeed/dxlink-api",
        "version": "0.3.0",
        "type": "module",
        "exports": "./index.mjs",
    }
    if metadata_case == "malformed":
        (fake_sdk_dir / "package.json").write_text("{not-json", encoding="utf-8")
    elif metadata_case != "missing":
        (fake_sdk_dir / "package.json").write_text(json.dumps(resolved_manifest), encoding="utf-8")
    if metadata_case == "ambiguous":
        dist_dir = fake_sdk_dir / "dist"
        dist_dir.mkdir()
        (dist_dir / "index.mjs").write_text(_fake_preflight_sdk_source(), encoding="utf-8")
        (dist_dir / "package.json").write_text(
            json.dumps({"name": "@dxfeed/dxlink-api", "version": "0.3.0"}),
            encoding="utf-8",
        )
        package_json = json.loads((fake_sdk_dir / "package.json").read_text(encoding="utf-8"))
        package_json["exports"] = "./dist/index.mjs"
        (fake_sdk_dir / "package.json").write_text(json.dumps(package_json), encoding="utf-8")
    elif metadata_case == "missing":
        (fake_sdk_dir / "index.js").write_text(_fake_preflight_sdk_source(), encoding="utf-8")
    elif metadata_case == "escape_main":
        outside = sidecar_dir / "outside"
        outside.mkdir(parents=True)
        (outside / "index.mjs").write_text(_fake_preflight_sdk_source(), encoding="utf-8")
        package_json = json.loads((fake_sdk_dir / "package.json").read_text(encoding="utf-8"))
        package_json.pop("exports", None)
        package_json["main"] = "../../../outside/index.mjs"
        (fake_sdk_dir / "package.json").write_text(json.dumps(package_json), encoding="utf-8")
    else:
        (fake_sdk_dir / "index.mjs").write_text(_fake_preflight_sdk_source(), encoding="utf-8")
    return sidecar_dir


def _run_fake_runtime_preflight(
    *,
    manifest: dict[str, str] | None = None,
    metadata_case: str = "valid",
) -> subprocess.CompletedProcess[str]:
    node = shutil.which("node.exe") or shutil.which("node")
    if node is None:
        pytest.skip("Node is not installed in this environment")
    tmp_path = Path(".codex_pytest_tmp") / f"br30b4b_preflight_{uuid.uuid4().hex}"
    sidecar_dir = _make_fake_preflight_tree(tmp_path, manifest=manifest, metadata_case=metadata_case)
    completed = _run_node_preflight(node, sidecar_dir)
    shutil.rmtree(tmp_path)
    return completed


def _run_node_preflight(node: str, sidecar_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [node, str(sidecar_dir / "dxlink_runtime_preflight.mjs")],
        input="",
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=5,
        shell=False,
        env={"PATH": str(Path(node).parent), "SYSTEMROOT": "C:\\Windows"},
    )


@pytest.mark.parametrize(
    ("runner", "expected_reason"),
    [
        (FakeDXLinkRunner(messages_for=("SPY",)), "missing_symbol"),
        (FakeDXLinkRunner(stdout=dxlink_stdout_without_candle()), "missing_symbol"),
        (FakeDXLinkRunner(stdout=dxlink_stdout_with_event("Trade")), "unsupported_event"),
        (FakeDXLinkRunner(stdout="{not-json"), "dxlink_output_malformed"),
        (FakeDXLinkRunner(stdout="x" * (DXLINK_STDOUT_MAX_BYTES + 1)), "dxlink_output_malformed"),
        (FakeDXLinkRunner(timed_out=True), "dxlink_timeout"),
        (FakeDXLinkRunner(returncode=1, stderr="dxlink_dependency_unavailable"), "dxlink_dependency_unavailable"),
        (FakeDXLinkRunner(returncode=1, stderr="provider raw failure"), "dxlink_output_malformed"),
        (FakeDXLinkRunner(stdout=json_message({"ok": True, "connected": True, "events": [], "leak": "mock-quote-token"})), "dxlink_secret_leak_detected"),
    ],
)
def test_br30b4_dxlink_rejects_child_process_and_output_boundary_failures(
    runner: FakeDXLinkRunner,
    expected_reason: str,
) -> None:
    client = TastytradeSandboxConcreteReadOnlyNetworkClient(
        http_transport=FakeHttpTransport.valid(),
        dxlink_runner=runner,
    )

    assert _blocked_reason_for_client(client) == expected_reason


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
