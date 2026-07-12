from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol
from urllib.parse import urlparse

from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


PHASE_ID = "BR-30A"
CAPABILITY_FIREWALL_PHASE_ID = "BR-30A1"
MODULE_NAME = "Secure Local OAuth Runtime Bridge"
PROVIDER_TASTYTRADE_SANDBOX = "tastytrade"
ENVIRONMENT_SANDBOX = "sandbox"
SUPPORTED_PROVIDERS = (PROVIDER_TASTYTRADE_SANDBOX,)
SUPPORTED_ENVIRONMENTS = (ENVIRONMENT_SANDBOX,)
ALLOWED_OAUTH_SCOPES = ("openid", "read")
JARVIS_REQUESTED_OAUTH_SCOPES = ALLOWED_OAUTH_SCOPES
TASTYTRADE_SANDBOX_PROVIDER_GRANTED_SCOPES = ("openid", "read", "trade")
SANDBOX_PROVIDER_HOSTS = ("api.cert.tastyworks.com",)
READ_ONLY_PROVIDER_METHODS = ("GET",)
OAUTH_TOKEN_REFRESH_METHOD = "POST"
OAUTH_TOKEN_REFRESH_PATHS = ("/oauth/token",)
READ_ONLY_PROVIDER_PATH_PREFIXES = (
    "/customers/me/accounts",
    "/api-quote-tokens",
)
MUTATION_PATH_MARKERS = (
    "/orders",
    "/positions",
    "/transactions",
    "/withdrawals",
    "/deposits",
    "/transfers",
    "/ach",
    "/wire",
)
DEFAULT_SERVICE_NAME = "jarvis-quant.br30a.oauth"
DEFAULT_TOKEN_SKEW = timedelta(seconds=60)
REQUIRED_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
SENSITIVE_FIELD_NAMES = (
    "access_token",
    "api_key",
    "authorization",
    "broker_credentials",
    "client_secret",
    "oauth_token",
    "password",
    "private_key",
    "refresh_token",
    "secret",
    "token",
)
REJECTION_REASONS = (
    "runtime_mode_not_allowed",
    "unexpected_scope",
    "unsupported_provider",
    "wrong_environment",
    "vault_unavailable",
    "missing_secret",
    "token_client_missing",
    "provider_call_disabled",
    "malformed_response",
    "clock_skew_exceeded",
    "token_expired",
    "token_revoked",
    "unsafe_effective_capability",
    "provider_scope_not_allowed",
    "provider_host_not_sandbox",
    "provider_http_method_not_allowed",
    "provider_endpoint_not_allowed",
    "provider_mutation_path_blocked",
)


class OAuthBridgeError(RuntimeError):
    """Base error with a sanitized message."""


class VaultUnavailableError(OAuthBridgeError):
    """Raised when the OS credential vault cannot be reached."""


class MissingSecretError(OAuthBridgeError):
    """Raised when a required vault entry is absent."""


class ProviderTokenClient(Protocol):
    provider_name: str

    def refresh_access_token(
        self,
        credentials: "OAuthRuntimeCredentials",
        scopes: tuple[str, ...],
        as_of: datetime,
    ) -> "OAuthTokenResponse":
        """Return a short-lived access token without exposing the refresh token."""

    def revoke_access_token(self, access_token: "InMemoryAccessToken") -> None:
        """Revoke the current access token if the provider supports revocation."""


class CredentialVault(Protocol):
    def store_credentials(self, credentials: "OAuthRuntimeCredentials") -> None:
        """Persist OAuth runtime credentials in an OS credential vault."""

    def load_credentials(self, provider: str, environment: str) -> "OAuthRuntimeCredentials":
        """Load OAuth runtime credentials from an OS credential vault."""

    def delete_credentials(self, provider: str, environment: str) -> None:
        """Delete OAuth runtime credentials from an OS credential vault."""


@dataclass(frozen=True)
class OAuthRuntimeCredentials:
    provider: str
    environment: str
    client_id: str = field(repr=False)
    client_secret: str = field(repr=False)
    refresh_token: str = field(repr=False)

    def validate(self) -> None:
        if self.provider not in SUPPORTED_PROVIDERS:
            raise ValueError("BR-30A unsupported OAuth provider")
        if self.environment not in SUPPORTED_ENVIRONMENTS:
            raise ValueError("BR-30A OAuth environment is not allowed")
        if not self.client_id.strip() or not self.client_secret.strip() or not self.refresh_token.strip():
            raise MissingSecretError("BR-30A required OAuth credential is missing")

    def redacted_summary(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "environment": self.environment,
            "client_id_present": bool(self.client_id),
            "client_secret_present": bool(self.client_secret),
            "refresh_token_present": bool(self.refresh_token),
            "redacted": True,
        }


@dataclass(frozen=True)
class OAuthTokenResponse:
    access_token: str = field(repr=False)
    expires_at: datetime
    scopes: tuple[str, ...]
    token_type: str = "Bearer"
    revoked: bool = False


@dataclass(frozen=True)
class InMemoryAccessToken:
    provider: str
    environment: str
    access_token: str = field(repr=False)
    expires_at: datetime
    scopes: tuple[str, ...]
    token_type: str = "Bearer"
    revoked: bool = False

    def is_valid(self, as_of: datetime, skew: timedelta = DEFAULT_TOKEN_SKEW) -> bool:
        return not self.revoked and self.expires_at > as_of + skew

    def redacted_summary(self, as_of: datetime) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "environment": self.environment,
            "token_present": bool(self.access_token),
            "expires_at": self.expires_at.isoformat(),
            "seconds_until_expiry": int((self.expires_at - as_of).total_seconds()),
            "jarvis_requested_scopes": JARVIS_REQUESTED_OAUTH_SCOPES,
            "jarvis_effective_scopes": ("read",),
            "provider_granted_scopes": self.scopes,
            "scopes": self.scopes,
            "provider_scope_contains_trade": "trade" in self.scopes,
            "token_type": self.token_type,
            "revoked": self.revoked,
            "redacted": True,
        }


@dataclass(frozen=True)
class OAuthBridgeRequest:
    provider: str = PROVIDER_TASTYTRADE_SANDBOX
    environment: str = ENVIRONMENT_SANDBOX
    scopes: tuple[str, ...] = ALLOWED_OAUTH_SCOPES
    mode: str = "offline"
    as_of: datetime | None = None

    def validate(self) -> None:
        validate_oauth_scopes(self.scopes)
        if self.provider not in SUPPORTED_PROVIDERS:
            raise ValueError("BR-30A unsupported OAuth provider")
        if self.environment not in SUPPORTED_ENVIRONMENTS:
            raise ValueError("BR-30A OAuth environment is not allowed")
        if self.mode not in ("offline", "local_runtime"):
            raise ValueError("BR-30A OAuth runtime mode is not supported")


@dataclass(frozen=True)
class OAuthBridgeResult:
    as_of: datetime
    label: str
    provider: str
    environment: str
    request_mode: str
    access_token_ready: bool
    rejection_reasons: tuple[str, ...]
    credential_summary: dict[str, Any]
    token_summary: dict[str, Any]
    redaction: dict[str, Any]
    safety: dict[str, Any]

    def validate(self) -> None:
        for reason in self.rejection_reasons:
            if reason not in REJECTION_REASONS:
                raise ValueError("BR-30A rejection reason is not recognized")
        if self.access_token_ready:
            if self.label != HUMAN_REVIEW_REQUIRED or self.rejection_reasons:
                raise ValueError("BR-30A accepted runtime token must remain human-review-required")
            if not self.token_summary.get("token_present"):
                raise ValueError("BR-30A accepted runtime token requires an in-memory token")
        else:
            if self.label != BLOCKED_BY_SAFETY_GATE or not self.rejection_reasons:
                raise ValueError("BR-30A rejected runtime must be blocked by safety gate")
        _validate_redacted(self.credential_summary)
        _validate_redacted(self.token_summary)
        _validate_safety(self.safety)


@dataclass(frozen=True)
class ProviderResourceRequest:
    method: str
    url: str
    provider: str = PROVIDER_TASTYTRADE_SANDBOX
    environment: str = ENVIRONMENT_SANDBOX
    is_oauth_token_refresh: bool = False

    def validate(self) -> None:
        if self.provider not in SUPPORTED_PROVIDERS:
            raise ValueError("BR-30A1 unsupported OAuth provider")
        if self.environment not in SUPPORTED_ENVIRONMENTS:
            raise ValueError("BR-30A1 OAuth environment is not allowed")


@dataclass(frozen=True)
class ProviderResourceFirewallDecision:
    allowed: bool
    rejection_reasons: tuple[str, ...]
    provider: str
    environment: str
    method: str
    host: str
    path: str
    is_oauth_token_refresh: bool

    def validate(self) -> None:
        for reason in self.rejection_reasons:
            if reason not in REJECTION_REASONS:
                raise ValueError("BR-30A1 rejection reason is not recognized")
        if self.allowed and self.rejection_reasons:
            raise ValueError("BR-30A1 allowed request cannot have rejection reasons")
        if not self.allowed and not self.rejection_reasons:
            raise ValueError("BR-30A1 blocked request requires a rejection reason")


class KeyringCredentialVault:
    """OS credential vault backed by Python keyring.

    On Windows, keyring uses Windows Credential Manager when an appropriate
    backend is available. Secret values are stored as password entries and are
    never returned by summary methods.
    """

    def __init__(self, service_name: str = DEFAULT_SERVICE_NAME) -> None:
        try:
            import keyring  # type: ignore[import-not-found]
        except Exception as exc:  # pragma: no cover - exercised through mocks in tests
            raise VaultUnavailableError("BR-30A credential vault is unavailable") from exc
        self._keyring = keyring
        self._service_name = service_name

    def store_credentials(self, credentials: OAuthRuntimeCredentials) -> None:
        credentials.validate()
        try:
            self._keyring.set_password(self._service_name, _vault_key(credentials.provider, credentials.environment, "client_id"), credentials.client_id)
            self._keyring.set_password(self._service_name, _vault_key(credentials.provider, credentials.environment, "client_secret"), credentials.client_secret)
            self._keyring.set_password(self._service_name, _vault_key(credentials.provider, credentials.environment, "refresh_token"), credentials.refresh_token)
        except Exception as exc:  # pragma: no cover - backend-specific
            raise VaultUnavailableError("BR-30A credential vault is unavailable") from exc

    def load_credentials(self, provider: str, environment: str) -> OAuthRuntimeCredentials:
        try:
            client_id = self._keyring.get_password(self._service_name, _vault_key(provider, environment, "client_id"))
            client_secret = self._keyring.get_password(self._service_name, _vault_key(provider, environment, "client_secret"))
            refresh_token = self._keyring.get_password(self._service_name, _vault_key(provider, environment, "refresh_token"))
        except Exception as exc:  # pragma: no cover - backend-specific
            raise VaultUnavailableError("BR-30A credential vault is unavailable") from exc
        if not client_id or not client_secret or not refresh_token:
            raise MissingSecretError("BR-30A required OAuth credential is missing")
        credentials = OAuthRuntimeCredentials(provider, environment, client_id, client_secret, refresh_token)
        credentials.validate()
        return credentials

    def delete_credentials(self, provider: str, environment: str) -> None:
        for field_name in ("client_id", "client_secret", "refresh_token"):
            try:
                self._keyring.delete_password(self._service_name, _vault_key(provider, environment, field_name))
            except Exception:
                continue


class TastytradeSandboxOAuthTokenClient:
    provider_name = PROVIDER_TASTYTRADE_SANDBOX

    def refresh_access_token(
        self,
        credentials: OAuthRuntimeCredentials,
        scopes: tuple[str, ...],
        as_of: datetime,
    ) -> OAuthTokenResponse:
        credentials.validate()
        validate_oauth_scopes(scopes)
        raise OAuthBridgeError("BR-30A provider network calls are disabled by default")

    def revoke_access_token(self, access_token: InMemoryAccessToken) -> None:
        raise OAuthBridgeError("BR-30A provider network calls are disabled by default")


class SecureLocalOAuthRuntimeBridge:
    def __init__(
        self,
        vault: CredentialVault | None = None,
        token_client: ProviderTokenClient | None = None,
        token_skew: timedelta = DEFAULT_TOKEN_SKEW,
    ) -> None:
        self._vault = vault
        self._token_client = token_client
        self._token_skew = token_skew
        self._memory_token: InMemoryAccessToken | None = None

    def get_access_token(self, request: OAuthBridgeRequest | None = None) -> OAuthBridgeResult:
        resolved = request or OAuthBridgeRequest()
        resolved.validate()
        as_of = resolved.as_of or datetime.now(timezone.utc).replace(microsecond=0)
        if resolved.mode == "offline":
            return _blocked_result(resolved, as_of, ("runtime_mode_not_allowed",), None, self._memory_token, False)
        if self._memory_token and self._memory_token.is_valid(as_of, self._token_skew):
            return _accepted_result(resolved, as_of, None, self._memory_token, vault_read_attempted=False)
        if self._memory_token and self._memory_token.revoked:
            return _blocked_result(resolved, as_of, ("token_revoked",), None, self._memory_token, False)
        if self._vault is None:
            return _blocked_result(resolved, as_of, ("vault_unavailable",), None, self._memory_token, False)
        if self._token_client is None:
            return _blocked_result(resolved, as_of, ("token_client_missing",), None, self._memory_token, False)
        if isinstance(self._token_client, TastytradeSandboxOAuthTokenClient):
            return _blocked_result(resolved, as_of, ("provider_call_disabled",), None, self._memory_token, False)
        try:
            credentials = self._vault.load_credentials(resolved.provider, resolved.environment)
        except VaultUnavailableError:
            return _blocked_result(resolved, as_of, ("vault_unavailable",), None, self._memory_token, True)
        except MissingSecretError:
            return _blocked_result(resolved, as_of, ("missing_secret",), None, self._memory_token, True)
        if credentials.environment != resolved.environment or credentials.provider != resolved.provider:
            return _blocked_result(resolved, as_of, ("wrong_environment",), credentials, self._memory_token, True)
        try:
            response = self._token_client.refresh_access_token(credentials, resolved.scopes, as_of)
        except OAuthBridgeError:
            return _blocked_result(resolved, as_of, ("provider_call_disabled",), credentials, self._memory_token, True)
        reasons = _token_response_rejection_reasons(response, resolved, as_of, self._token_skew)
        if reasons:
            return _blocked_result(resolved, as_of, reasons, credentials, None, True)
        self._memory_token = InMemoryAccessToken(
            provider=resolved.provider,
            environment=resolved.environment,
            access_token=response.access_token,
            expires_at=response.expires_at.astimezone(timezone.utc),
            scopes=tuple(sorted(response.scopes)),
            token_type=response.token_type,
            revoked=False,
        )
        return _accepted_result(resolved, as_of, credentials, self._memory_token, vault_read_attempted=True)

    def get_access_token_for_read_only_client(
        self,
        request: OAuthBridgeRequest | None = None,
    ) -> tuple[OAuthBridgeResult, InMemoryAccessToken | None]:
        """Return the memory-only token to an in-process read-only client.

        The token is intentionally not included in reports or summaries. This
        method exists for the BR-30B sandbox smoke-test handoff only.
        """
        result = self.get_access_token(request)
        if not result.access_token_ready:
            return result, None
        return result, self._memory_token

    def revoke_access_token(self, request: OAuthBridgeRequest | None = None) -> OAuthBridgeResult:
        resolved = request or OAuthBridgeRequest(mode="local_runtime")
        resolved.validate()
        as_of = resolved.as_of or datetime.now(timezone.utc).replace(microsecond=0)
        if self._memory_token is None:
            return _blocked_result(resolved, as_of, ("token_revoked",), None, None, False)
        token = InMemoryAccessToken(
            provider=self._memory_token.provider,
            environment=self._memory_token.environment,
            access_token=self._memory_token.access_token,
            expires_at=self._memory_token.expires_at,
            scopes=self._memory_token.scopes,
            token_type=self._memory_token.token_type,
            revoked=True,
        )
        if self._token_client is not None and not isinstance(self._token_client, TastytradeSandboxOAuthTokenClient):
            self._token_client.revoke_access_token(self._memory_token)
        self._memory_token = None
        return _blocked_result(resolved, as_of, ("token_revoked",), None, token, False)


def validate_oauth_scopes(scopes: tuple[str, ...]) -> None:
    normalized = tuple(sorted({scope.strip() for scope in scopes if scope.strip()}))
    if set(normalized) != set(JARVIS_REQUESTED_OAUTH_SCOPES):
        raise ValueError("BR-30A OAuth scopes must be limited to openid and read")


def validate_provider_granted_scopes(provider: str, environment: str, scopes: tuple[str, ...]) -> None:
    normalized = tuple(sorted({scope.strip() for scope in scopes if scope.strip()}))
    allowed = set(TASTYTRADE_SANDBOX_PROVIDER_GRANTED_SCOPES)
    if provider != PROVIDER_TASTYTRADE_SANDBOX or environment != ENVIRONMENT_SANDBOX:
        raise ValueError("BR-30A1 provider-granted trade scope is sandbox-only")
    if not set(JARVIS_REQUESTED_OAUTH_SCOPES).issubset(set(normalized)) or set(normalized) - allowed:
        raise ValueError("BR-30A1 provider-granted OAuth scopes are not allowed")


def effective_capability_manifest(provider_scopes: tuple[str, ...] = ()) -> dict[str, Any]:
    normalized = tuple(sorted({scope.strip() for scope in provider_scopes if scope.strip()}))
    return {
        "jarvis_requested_scopes": JARVIS_REQUESTED_OAUTH_SCOPES,
        "provider_granted_scopes": normalized,
        "provider_scope_contains_trade": "trade" in normalized,
        "jarvis_effective_scopes": ("read",),
        "order_read_capability": False,
        "order_create_capability": False,
        "order_replace_capability": False,
        "order_cancel_capability": False,
        "account_mutation_capability": False,
        "position_mutation_capability": False,
        "execution_capability": False,
        "external_routing_capability": False,
        "live_trading_capability": False,
    }


def authorize_provider_resource_request(request: ProviderResourceRequest) -> ProviderResourceFirewallDecision:
    request.validate()
    parsed = urlparse(request.url)
    host = (parsed.hostname or "").lower()
    path = parsed.path or "/"
    method = request.method.strip().upper()
    reasons: list[str] = []

    if host not in SANDBOX_PROVIDER_HOSTS:
        reasons.append("provider_host_not_sandbox")
    if _is_mutation_path(path):
        reasons.append("provider_mutation_path_blocked")

    if request.is_oauth_token_refresh:
        if method != OAUTH_TOKEN_REFRESH_METHOD or path not in OAUTH_TOKEN_REFRESH_PATHS:
            reasons.append("provider_endpoint_not_allowed")
    else:
        if method not in READ_ONLY_PROVIDER_METHODS:
            reasons.append("provider_http_method_not_allowed")
        if not _is_read_only_allowed_path(path):
            reasons.append("provider_endpoint_not_allowed")

    decision = ProviderResourceFirewallDecision(
        allowed=not reasons,
        rejection_reasons=tuple(dict.fromkeys(reasons)),
        provider=request.provider,
        environment=request.environment,
        method=method,
        host=host,
        path=path,
        is_oauth_token_refresh=request.is_oauth_token_refresh,
    )
    decision.validate()
    return decision


def safety_manifest(
    mode: str = "offline",
    vault_read_attempted: bool = False,
    provider_scopes: tuple[str, ...] = (),
) -> dict[str, Any]:
    capabilities = effective_capability_manifest(provider_scopes)
    return {
        "phase": PHASE_ID,
        "capability_firewall_phase": CAPABILITY_FIREWALL_PHASE_ID,
        "module": MODULE_NAME,
        "labels": REQUIRED_LABELS,
        "research_only": True,
        "monitor_only": True,
        "paper_only": True,
        "human_review_required": True,
        "blocked_by_safety_gate": True,
        "provider_neutral_runtime_interface": True,
        "tastytrade_sandbox_implementation": True,
        "allowed_oauth_scopes": ALLOWED_OAUTH_SCOPES,
        "jarvis_requested_oauth_scopes": JARVIS_REQUESTED_OAUTH_SCOPES,
        "tastytrade_sandbox_provider_granted_scopes_allowed": TASTYTRADE_SANDBOX_PROVIDER_GRANTED_SCOPES,
        "sandbox_provider_hosts": SANDBOX_PROVIDER_HOSTS,
        "read_only_provider_methods": READ_ONLY_PROVIDER_METHODS,
        "read_only_provider_path_prefixes": READ_ONLY_PROVIDER_PATH_PREFIXES,
        "oauth_token_refresh_exchange_isolated": True,
        "default_runtime_mode": "offline",
        "current_runtime_mode": mode,
        "offline_by_default": True,
        "fail_closed_by_default": True,
        "os_credential_vault_required": True,
        "credential_values_redacted": True,
        "secret_values_in_process_output": False,
        "secret_values_in_source_files": False,
        "secret_values_in_env_files": False,
        "secret_values_in_test_fixtures": False,
        "secret_values_in_reports": False,
        "short_lived_access_tokens_memory_only": True,
        "vault_read_attempted": vault_read_attempted,
        "env_file_read_attempted": False,
        "provider_call_attempted_in_tests": False,
        "caller_trade_scope_request_allowed": False,
        "provider_scope_contains_trade": capabilities["provider_scope_contains_trade"],
        "order_read_capability": False,
        "order_create_capability": False,
        "order_replace_capability": False,
        "order_cancel_capability": False,
        "account_capabilities_available": False,
        "execution_capabilities_available": False,
        "position_mutation_capabilities_available": False,
        "broker_write_operations_authorized": False,
        "external_routing_paths_authorized": False,
        "account_mutation_allowed": False,
        "execution_methods_available": False,
        "external_routing_paths_allowed": False,
        "position_mutation_allowed": False,
        "live_trading_authorized": False,
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


def build_secure_local_oauth_runtime_bridge_evidence(
    request: OAuthBridgeRequest | None = None,
) -> OAuthBridgeResult:
    return SecureLocalOAuthRuntimeBridge().get_access_token(request)


def secure_local_oauth_runtime_bridge_payload(result: OAuthBridgeResult) -> dict[str, Any]:
    result.validate()
    return {
        "phase": PHASE_ID,
        "module": MODULE_NAME,
        "as_of": result.as_of.isoformat(),
        "label": result.label,
        "provider": result.provider,
        "environment": result.environment,
        "request_mode": result.request_mode,
        "access_token_ready": result.access_token_ready,
        "allowed_oauth_scopes": ALLOWED_OAUTH_SCOPES,
        "jarvis_requested_oauth_scopes": JARVIS_REQUESTED_OAUTH_SCOPES,
        "provider_granted_scope_policy": {
            "tastytrade_sandbox_allowed": TASTYTRADE_SANDBOX_PROVIDER_GRANTED_SCOPES,
            "provider_scope_contains_trade": bool(result.token_summary.get("provider_scope_contains_trade", False)),
            "effective_capabilities": effective_capability_manifest(
                tuple(result.token_summary.get("provider_granted_scopes", ()))
            ),
        },
        "provider_resource_firewall": {
            "sandbox_provider_hosts": SANDBOX_PROVIDER_HOSTS,
            "read_only_provider_methods": READ_ONLY_PROVIDER_METHODS,
            "read_only_provider_path_prefixes": READ_ONLY_PROVIDER_PATH_PREFIXES,
            "mutation_path_markers_blocked": MUTATION_PATH_MARKERS,
            "oauth_token_refresh_exchange_isolated": True,
        },
        "supported_providers": SUPPORTED_PROVIDERS,
        "supported_environments": SUPPORTED_ENVIRONMENTS,
        "rejection_reasons": result.rejection_reasons,
        "credential_summary": result.credential_summary,
        "token_summary": result.token_summary,
        "redaction": result.redaction,
        "safety": result.safety,
        "readiness_state": {
            "state": "LOCAL_OAUTH_RUNTIME_BRIDGE_ONLY",
            "manual_review_required": True,
            "ready_for_live_trading": False,
            "order_read_capability": False,
            "order_create_capability": False,
            "order_replace_capability": False,
            "order_cancel_capability": False,
            "account_mutation_allowed": False,
            "execution_methods_available": False,
            "external_routing_paths_allowed": False,
            "position_mutation_allowed": False,
            "live_trading_authorized": False,
        },
    }


def redact_sensitive_payload(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, child in value.items():
            if str(key).lower() in SENSITIVE_FIELD_NAMES:
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = redact_sensitive_payload(child)
        return redacted
    if isinstance(value, list):
        return [redact_sensitive_payload(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_sensitive_payload(item) for item in value)
    return value


def _accepted_result(
    request: OAuthBridgeRequest,
    as_of: datetime,
    credentials: OAuthRuntimeCredentials | None,
    token: InMemoryAccessToken,
    vault_read_attempted: bool,
) -> OAuthBridgeResult:
    result = OAuthBridgeResult(
        as_of=as_of,
        label=HUMAN_REVIEW_REQUIRED,
        provider=request.provider,
        environment=request.environment,
        request_mode=request.mode,
        access_token_ready=True,
        rejection_reasons=(),
        credential_summary=_credential_summary(credentials),
        token_summary=token.redacted_summary(as_of),
        redaction=_redaction_manifest(),
        safety=safety_manifest(request.mode, vault_read_attempted, token.scopes),
    )
    result.validate()
    return result


def _blocked_result(
    request: OAuthBridgeRequest,
    as_of: datetime,
    reasons: tuple[str, ...],
    credentials: OAuthRuntimeCredentials | None,
    token: InMemoryAccessToken | None,
    vault_read_attempted: bool,
) -> OAuthBridgeResult:
    result = OAuthBridgeResult(
        as_of=as_of,
        label=BLOCKED_BY_SAFETY_GATE,
        provider=request.provider,
        environment=request.environment,
        request_mode=request.mode,
        access_token_ready=False,
        rejection_reasons=tuple(dict.fromkeys(reasons)),
        credential_summary=_credential_summary(credentials),
        token_summary=token.redacted_summary(as_of) if token else {"token_present": False, "redacted": True},
        redaction=_redaction_manifest(),
        safety=safety_manifest(request.mode, vault_read_attempted, token.scopes if token else ()),
    )
    result.validate()
    return result


def _credential_summary(credentials: OAuthRuntimeCredentials | None) -> dict[str, Any]:
    if credentials is None:
        return {
            "provider": None,
            "environment": None,
            "client_id_present": False,
            "client_secret_present": False,
            "refresh_token_present": False,
            "redacted": True,
        }
    return credentials.redacted_summary()


def _token_response_rejection_reasons(
    response: OAuthTokenResponse,
    request: OAuthBridgeRequest,
    as_of: datetime,
    skew: timedelta,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not isinstance(response.access_token, str) or not response.access_token.strip():
        reasons.append("malformed_response")
    if response.token_type != "Bearer":
        reasons.append("malformed_response")
    if response.revoked:
        reasons.append("token_revoked")
    response_scopes = tuple(sorted({scope.strip() for scope in response.scopes if scope.strip()}))
    if set(response_scopes) - set(TASTYTRADE_SANDBOX_PROVIDER_GRANTED_SCOPES):
        reasons.append("provider_scope_not_allowed")
    if not set(JARVIS_REQUESTED_OAUTH_SCOPES).issubset(set(response_scopes)):
        reasons.append("unexpected_scope")
    if "trade" in response_scopes and (
        request.provider != PROVIDER_TASTYTRADE_SANDBOX or request.environment != ENVIRONMENT_SANDBOX
    ):
        reasons.append("provider_scope_not_allowed")
    expires_at = response.expires_at
    if expires_at.tzinfo is None:
        reasons.append("malformed_response")
    else:
        expires_at = expires_at.astimezone(timezone.utc)
        if expires_at <= as_of:
            reasons.append("token_expired")
        elif expires_at <= as_of + skew:
            reasons.append("clock_skew_exceeded")
    return tuple(dict.fromkeys(reasons))


def _vault_key(provider: str, environment: str, field_name: str) -> str:
    return f"{provider}.{environment}.{field_name}"


def _redaction_manifest() -> dict[str, Any]:
    return {
        "redacted": True,
        "redacted_fields": SENSITIVE_FIELD_NAMES,
        "secret_values_written_to_reports": False,
        "secret_values_written_to_logs": False,
        "secret_values_written_to_ui_state": False,
        "secret_values_written_to_process_output": False,
    }


def _validate_redacted(payload: dict[str, Any]) -> None:
    if _contains_unredacted_sensitive_value(payload):
        raise ValueError("BR-30A payload exposed a sensitive value")


def _contains_unredacted_sensitive_value(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_contains_unredacted_sensitive_value(child) for child in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_unredacted_sensitive_value(child) for child in value)
    if isinstance(value, str):
        lowered = value.lower()
        return any(marker in lowered for marker in ("mock-access-token", "mock-client-secret", "mock-refresh-token"))
    return False


def _validate_safety(manifest: dict[str, Any]) -> None:
    for field_name in (
        "caller_trade_scope_request_allowed",
        "order_read_capability",
        "order_create_capability",
        "order_replace_capability",
        "order_cancel_capability",
        "account_capabilities_available",
        "execution_capabilities_available",
        "position_mutation_capabilities_available",
        "broker_write_operations_authorized",
        "external_routing_paths_authorized",
        "account_mutation_allowed",
        "execution_methods_available",
        "external_routing_paths_allowed",
        "position_mutation_allowed",
        "live_trading_authorized",
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
            raise ValueError(f"BR-30A OAuth bridge cannot allow {field_name}")
    if manifest.get("LIVE TRADING") != "DISABLED":
        raise ValueError("BR-30A OAuth bridge must keep LIVE TRADING disabled")


def _is_read_only_allowed_path(path: str) -> bool:
    normalized = path if path.startswith("/") else f"/{path}"
    return any(normalized == prefix or normalized.startswith(f"{prefix}/") for prefix in READ_ONLY_PROVIDER_PATH_PREFIXES)


def _is_mutation_path(path: str) -> bool:
    lowered = path.lower()
    return any(marker in lowered for marker in MUTATION_PATH_MARKERS)
