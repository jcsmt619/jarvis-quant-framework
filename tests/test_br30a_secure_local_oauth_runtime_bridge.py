from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from engines.moonshot.deterministic.br30a_secure_local_oauth_runtime_bridge import (
    ALLOWED_OAUTH_SCOPES,
    CAPABILITY_FIREWALL_PHASE_ID,
    JARVIS_REQUESTED_OAUTH_SCOPES,
    MODULE_NAME,
    PHASE_ID,
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    InMemoryAccessToken,
    MissingSecretError,
    OAuthBridgeRequest,
    OAuthRuntimeCredentials,
    OAuthTokenResponse,
    ProviderResourceRequest,
    SecureLocalOAuthRuntimeBridge,
    TASTYTRADE_SANDBOX_PROVIDER_GRANTED_SCOPES,
    TastytradeSandboxOAuthTokenClient,
    VaultUnavailableError,
    authorize_provider_resource_request,
    build_secure_local_oauth_runtime_bridge_evidence,
    effective_capability_manifest,
    redact_sensitive_payload,
    safety_manifest,
    secure_local_oauth_runtime_bridge_payload,
    validate_oauth_scopes,
    validate_provider_granted_scopes,
)


AS_OF = datetime(2026, 7, 11, 16, 5, tzinfo=timezone.utc)
MODULE_PATH = Path("engines/moonshot/deterministic/br30a_secure_local_oauth_runtime_bridge.py")
SCRIPT_PATH = Path("scripts/setup_br30a_secure_local_oauth_runtime_bridge.py")
DOC_PATH = Path("docs/brendan_strategy/br30a_secure_local_oauth_runtime_bridge.md")


def test_br30a_default_runtime_is_offline_and_fail_closed() -> None:
    result = build_secure_local_oauth_runtime_bridge_evidence(OAuthBridgeRequest(as_of=AS_OF))
    payload = secure_local_oauth_runtime_bridge_payload(result)

    assert payload["phase"] == PHASE_ID
    assert payload["module"] == MODULE_NAME
    assert payload["label"] == BLOCKED_BY_SAFETY_GATE
    assert payload["request_mode"] == "offline"
    assert payload["access_token_ready"] is False
    assert payload["rejection_reasons"] == ("runtime_mode_not_allowed",)
    assert payload["safety"]["offline_by_default"] is True
    assert payload["safety"]["fail_closed_by_default"] is True
    assert payload["safety"]["live_trading_enabled"] is False
    assert payload["safety"]["LIVE TRADING"] == "DISABLED"


def test_br30a_safety_manifest_blocks_execution_and_mutation_capabilities() -> None:
    manifest = safety_manifest()

    assert manifest["phase"] == PHASE_ID
    assert manifest["capability_firewall_phase"] == CAPABILITY_FIREWALL_PHASE_ID
    assert manifest["allowed_oauth_scopes"] == ALLOWED_OAUTH_SCOPES
    assert manifest["jarvis_requested_oauth_scopes"] == JARVIS_REQUESTED_OAUTH_SCOPES
    assert manifest["tastytrade_sandbox_provider_granted_scopes_allowed"] == TASTYTRADE_SANDBOX_PROVIDER_GRANTED_SCOPES
    assert manifest["tastytrade_sandbox_implementation"] is True
    assert manifest["secret_values_in_process_output"] is False
    assert manifest["short_lived_access_tokens_memory_only"] is True
    assert manifest["account_capabilities_available"] is False
    assert manifest["order_read_capability"] is False
    assert manifest["order_create_capability"] is False
    assert manifest["order_replace_capability"] is False
    assert manifest["order_cancel_capability"] is False
    assert manifest["execution_capabilities_available"] is False
    assert manifest["position_mutation_capabilities_available"] is False
    assert manifest["broker_order_call_performed"] is False
    assert manifest["real_paper_order_submitted"] is False
    assert manifest["live_trading_enabled"] is False


def test_br30a_rejects_unexpected_write_capable_scopes() -> None:
    with pytest.raises(ValueError, match="limited to openid and read"):
        validate_oauth_scopes(("openid", "read", "write"))

    with pytest.raises(ValueError, match="limited to openid and read"):
        OAuthBridgeRequest(scopes=("trade",), mode="local_runtime").validate()


def test_br30a1_accepts_tastytrade_sandbox_provider_trade_scope_without_effective_trade_capability() -> None:
    validate_oauth_scopes(("openid", "read"))
    validate_provider_granted_scopes("tastytrade", "sandbox", ("openid", "read", "trade"))
    bridge = SecureLocalOAuthRuntimeBridge(
        vault=FakeVault(),
        token_client=FakeTokenClient(
            OAuthTokenResponse(
                access_token="mock-access-token",
                expires_at=AS_OF + timedelta(minutes=15),
                scopes=("openid", "read", "trade"),
            )
        ),
    )

    result = bridge.get_access_token(OAuthBridgeRequest(mode="local_runtime", as_of=AS_OF))
    payload = secure_local_oauth_runtime_bridge_payload(result)
    effective = payload["provider_granted_scope_policy"]["effective_capabilities"]

    assert payload["label"] == HUMAN_REVIEW_REQUIRED
    assert payload["access_token_ready"] is True
    assert payload["token_summary"]["jarvis_requested_scopes"] == ("openid", "read")
    assert payload["token_summary"]["provider_granted_scopes"] == ("openid", "read", "trade")
    assert payload["token_summary"]["provider_scope_contains_trade"] is True
    assert payload["safety"]["provider_scope_contains_trade"] is True
    assert effective["provider_scope_contains_trade"] is True
    assert effective["order_read_capability"] is False
    assert effective["order_create_capability"] is False
    assert effective["order_replace_capability"] is False
    assert effective["order_cancel_capability"] is False
    assert effective["account_mutation_capability"] is False
    assert effective["position_mutation_capability"] is False
    assert effective["execution_capability"] is False
    assert effective["external_routing_capability"] is False
    assert effective["live_trading_capability"] is False
    assert payload["readiness_state"]["ready_for_live_trading"] is False


def test_br30a1_rejects_unknown_provider_granted_scopes() -> None:
    bridge = SecureLocalOAuthRuntimeBridge(
        vault=FakeVault(),
        token_client=FakeTokenClient(
            OAuthTokenResponse(
                access_token="mock-access-token",
                expires_at=AS_OF + timedelta(minutes=15),
                scopes=("openid", "read", "trade", "write"),
            )
        ),
    )

    result = bridge.get_access_token(OAuthBridgeRequest(mode="local_runtime", as_of=AS_OF))

    assert result.access_token_ready is False
    assert "provider_scope_not_allowed" in result.rejection_reasons


def test_br30a1_provider_resource_firewall_allows_only_sandbox_read_only_requests_and_token_refresh() -> None:
    read_allowed = authorize_provider_resource_request(
        ProviderResourceRequest("GET", "https://api.cert.tastytrade.com/customers/me")
    )
    refresh_allowed = authorize_provider_resource_request(
        ProviderResourceRequest(
            "POST",
            "https://api.cert.tastytrade.com/oauth/token",
            is_oauth_token_refresh=True,
        )
    )
    write_blocked = authorize_provider_resource_request(
        ProviderResourceRequest("POST", "https://api.cert.tastytrade.com/customers/me/accounts")
    )
    mutation_path_blocked = authorize_provider_resource_request(
        ProviderResourceRequest("GET", "https://api.cert.tastytrade.com/accounts/123/orders")
    )
    production_blocked = authorize_provider_resource_request(
        ProviderResourceRequest("GET", "https://api.tastytrade.com/customers/me")
    )

    assert read_allowed.allowed is True
    assert refresh_allowed.allowed is True
    assert write_blocked.allowed is False
    assert "provider_http_method_not_allowed" in write_blocked.rejection_reasons
    assert mutation_path_blocked.allowed is False
    assert "provider_mutation_path_blocked" in mutation_path_blocked.rejection_reasons
    assert production_blocked.allowed is False
    assert "provider_host_not_sandbox" in production_blocked.rejection_reasons


def test_br30a1_effective_capability_manifest_stays_read_only_when_provider_scope_has_trade() -> None:
    manifest = effective_capability_manifest(("openid", "read", "trade"))

    assert manifest["provider_scope_contains_trade"] is True
    assert manifest["jarvis_requested_scopes"] == ("openid", "read")
    assert manifest["jarvis_effective_scopes"] == ("read",)
    assert manifest["order_read_capability"] is False
    assert manifest["order_create_capability"] is False
    assert manifest["order_replace_capability"] is False
    assert manifest["order_cancel_capability"] is False
    assert manifest["account_mutation_capability"] is False
    assert manifest["position_mutation_capability"] is False
    assert manifest["execution_capability"] is False
    assert manifest["external_routing_capability"] is False
    assert manifest["live_trading_capability"] is False


def test_br30a_uses_mocked_vault_and_token_client_for_refresh_only() -> None:
    bridge = SecureLocalOAuthRuntimeBridge(
        vault=FakeVault(),
        token_client=FakeTokenClient(
            OAuthTokenResponse(
                access_token="mock-access-token",
                expires_at=AS_OF + timedelta(minutes=15),
                scopes=("openid", "read"),
            )
        ),
    )

    result = bridge.get_access_token(OAuthBridgeRequest(mode="local_runtime", as_of=AS_OF))
    payload = secure_local_oauth_runtime_bridge_payload(result)

    assert payload["label"] == HUMAN_REVIEW_REQUIRED
    assert payload["access_token_ready"] is True
    assert payload["rejection_reasons"] == ()
    assert payload["credential_summary"] == {
        "provider": "tastytrade",
        "environment": "sandbox",
        "client_id_present": True,
        "client_secret_present": True,
        "refresh_token_present": True,
        "redacted": True,
    }
    assert payload["token_summary"]["token_present"] is True
    assert "mock-access-token" not in str(payload)
    assert "mock-client-secret" not in str(payload)
    assert "mock-refresh-token" not in str(payload)


def test_br30a_reuses_valid_memory_token_and_refreshes_after_expiration() -> None:
    token_client = FakeTokenClient(
        OAuthTokenResponse(
            access_token="first-mock-token",
            expires_at=AS_OF + timedelta(minutes=10),
            scopes=("openid", "read"),
        )
    )
    bridge = SecureLocalOAuthRuntimeBridge(vault=FakeVault(), token_client=token_client)

    first = bridge.get_access_token(OAuthBridgeRequest(mode="local_runtime", as_of=AS_OF))
    second = bridge.get_access_token(OAuthBridgeRequest(mode="local_runtime", as_of=AS_OF + timedelta(minutes=1)))

    token_client.response = OAuthTokenResponse(
        access_token="second-mock-token",
        expires_at=AS_OF + timedelta(minutes=35),
        scopes=("openid", "read"),
    )
    third = bridge.get_access_token(OAuthBridgeRequest(mode="local_runtime", as_of=AS_OF + timedelta(minutes=10)))

    assert first.access_token_ready is True
    assert second.access_token_ready is True
    assert third.access_token_ready is True
    assert token_client.refresh_count == 2


@pytest.mark.parametrize(
    ("response", "expected_reason"),
    [
        (
            OAuthTokenResponse(access_token="", expires_at=AS_OF + timedelta(minutes=15), scopes=("openid", "read")),
            "malformed_response",
        ),
        (
            OAuthTokenResponse(
                access_token="mock-token",
                expires_at=AS_OF + timedelta(minutes=15),
                scopes=("openid", "read"),
                token_type="Basic",
            ),
            "malformed_response",
        ),
        (
            OAuthTokenResponse(access_token="mock-token", expires_at=AS_OF - timedelta(seconds=1), scopes=("openid", "read")),
            "token_expired",
        ),
        (
            OAuthTokenResponse(access_token="mock-token", expires_at=AS_OF + timedelta(seconds=30), scopes=("openid", "read")),
            "clock_skew_exceeded",
        ),
        (
            OAuthTokenResponse(access_token="mock-token", expires_at=AS_OF + timedelta(minutes=15), scopes=("openid", "read", "write")),
            "provider_scope_not_allowed",
        ),
        (
            OAuthTokenResponse(access_token="mock-token", expires_at=AS_OF + timedelta(minutes=15), scopes=("openid", "read"), revoked=True),
            "token_revoked",
        ),
    ],
)
def test_br30a_rejects_malformed_expired_clock_skew_scope_and_revoked_responses(
    response: OAuthTokenResponse,
    expected_reason: str,
) -> None:
    bridge = SecureLocalOAuthRuntimeBridge(vault=FakeVault(), token_client=FakeTokenClient(response))

    result = bridge.get_access_token(OAuthBridgeRequest(mode="local_runtime", as_of=AS_OF))

    assert result.access_token_ready is False
    assert result.label == BLOCKED_BY_SAFETY_GATE
    assert expected_reason in result.rejection_reasons


def test_br30a_blocks_missing_secret_wrong_environment_vault_unavailable_and_missing_client() -> None:
    missing = SecureLocalOAuthRuntimeBridge(vault=FakeVault(missing=True), token_client=FakeTokenClient.valid())
    wrong_environment = SecureLocalOAuthRuntimeBridge(
        vault=FakeVault(
            credentials=OAuthRuntimeCredentials("tastytrade", "unexpected-sandbox", "mock-client-id", "mock-client-secret", "mock-refresh-token")
        ),
        token_client=FakeTokenClient.valid(),
    )
    unavailable = SecureLocalOAuthRuntimeBridge(vault=FakeVault(unavailable=True), token_client=FakeTokenClient.valid())
    missing_client = SecureLocalOAuthRuntimeBridge(vault=FakeVault(), token_client=None)

    assert "missing_secret" in missing.get_access_token(OAuthBridgeRequest(mode="local_runtime", as_of=AS_OF)).rejection_reasons
    assert "wrong_environment" in wrong_environment.get_access_token(OAuthBridgeRequest(mode="local_runtime", as_of=AS_OF)).rejection_reasons
    assert "vault_unavailable" in unavailable.get_access_token(OAuthBridgeRequest(mode="local_runtime", as_of=AS_OF)).rejection_reasons
    assert "token_client_missing" in missing_client.get_access_token(OAuthBridgeRequest(mode="local_runtime", as_of=AS_OF)).rejection_reasons


def test_br30a_default_tastytrade_sandbox_client_is_disabled_by_default() -> None:
    bridge = SecureLocalOAuthRuntimeBridge(vault=FakeVault(), token_client=TastytradeSandboxOAuthTokenClient())

    result = bridge.get_access_token(OAuthBridgeRequest(mode="local_runtime", as_of=AS_OF))

    assert result.access_token_ready is False
    assert result.rejection_reasons == ("provider_call_disabled",)


def test_br30a_revocation_clears_memory_token_and_returns_blocked_state() -> None:
    token_client = FakeTokenClient.valid()
    bridge = SecureLocalOAuthRuntimeBridge(vault=FakeVault(), token_client=token_client)
    ready = bridge.get_access_token(OAuthBridgeRequest(mode="local_runtime", as_of=AS_OF))

    revoked = bridge.revoke_access_token(OAuthBridgeRequest(mode="local_runtime", as_of=AS_OF + timedelta(minutes=1)))
    after = bridge.get_access_token(OAuthBridgeRequest(mode="local_runtime", as_of=AS_OF + timedelta(minutes=2)))

    assert ready.access_token_ready is True
    assert revoked.access_token_ready is False
    assert "token_revoked" in revoked.rejection_reasons
    assert token_client.revoked_count == 1
    assert after.access_token_ready is True
    assert token_client.refresh_count == 2


def test_br30a_redaction_removes_sensitive_values_from_nested_payloads() -> None:
    payload = {
        "client_secret": "mock-client-secret",
        "nested": {"refresh_token": "mock-refresh-token", "safe": "visible"},
        "items": [{"access_token": "mock-access-token"}],
    }

    redacted = redact_sensitive_payload(payload)

    assert redacted["client_secret"] == "[REDACTED]"
    assert redacted["nested"]["refresh_token"] == "[REDACTED]"
    assert redacted["nested"]["safe"] == "visible"
    assert redacted["items"][0]["access_token"] == "[REDACTED]"
    assert "mock-" not in str(redacted)


def test_br30a_validation_rejects_unsafe_safety_mutations() -> None:
    result = build_secure_local_oauth_runtime_bridge_evidence(OAuthBridgeRequest(as_of=AS_OF))

    with pytest.raises(ValueError, match="cannot allow live_trading_enabled"):
        replace(result, safety={**result.safety, "live_trading_enabled": True}).validate()

    with pytest.raises(ValueError, match="cannot allow broker_order_call_performed"):
        replace(result, safety={**result.safety, "broker_order_call_performed": True}).validate()

    with pytest.raises(ValueError, match="must keep LIVE TRADING disabled"):
        replace(result, safety={**result.safety, "LIVE TRADING": "ENABLED"}).validate()


def test_br30a_source_script_and_doc_preserve_secret_boundaries() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    script = SCRIPT_PATH.read_text(encoding="utf-8")
    doc = DOC_PATH.read_text(encoding="utf-8")

    assert "getpass.getpass" in script
    assert "--client-secret" not in script
    assert "--refresh-token" not in script
    assert "python-dotenv" not in source
    assert "os.environ" not in source
    assert ".env" in doc
    assert "write-capable scopes are rejected" in doc
    assert "provider-granted sandbox `trade` scope is reported" in doc
    assert "POST, PUT, PATCH, and DELETE provider-resource operations are blocked" in doc
    assert "Windows Credential Manager" in doc
    assert "LIVE TRADING: DISABLED" in doc
    assert "does not submit broker orders" in doc
    assert "does not add broker order routing" in doc
    for token in ("submit_order", "place_order", "BUY" + "_NOW", "SELL" + "_NOW", "EXECUTE" + "_TRADE", "AUTO" + "_TRADE"):
        assert token not in source
        assert token not in script


class FakeVault:
    def __init__(
        self,
        credentials: OAuthRuntimeCredentials | None = None,
        missing: bool = False,
        unavailable: bool = False,
    ) -> None:
        self.credentials = credentials or OAuthRuntimeCredentials(
            "tastytrade",
            "sandbox",
            "mock-client-id",
            "mock-client-secret",
            "mock-refresh-token",
        )
        self.missing = missing
        self.unavailable = unavailable

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
        self.refresh_count = 0
        self.revoked_count = 0

    @classmethod
    def valid(cls) -> "FakeTokenClient":
        return cls(
            OAuthTokenResponse(
                access_token="mock-access-token",
                expires_at=AS_OF + timedelta(minutes=15),
                scopes=("openid", "read"),
            )
        )

    def refresh_access_token(
        self,
        credentials: OAuthRuntimeCredentials,
        scopes: tuple[str, ...],
        as_of: datetime,
    ) -> OAuthTokenResponse:
        self.refresh_count += 1
        return self.response

    def revoke_access_token(self, access_token: InMemoryAccessToken) -> None:
        self.revoked_count += 1
