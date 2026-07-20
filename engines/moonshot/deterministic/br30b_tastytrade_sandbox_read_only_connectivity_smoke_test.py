from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse

from engines.moonshot.deterministic.br30_read_only_live_market_data_adapter import (
    ADAPTER_SCHEMA_NAME,
    APPROVED_FEEDS,
    MarketDataRequest,
)
from engines.moonshot.deterministic.br30a_secure_local_oauth_runtime_bridge import (
    ALLOWED_OAUTH_SCOPES,
    InMemoryAccessToken,
    OAuthBridgeError,
    OAuthBridgeRequest,
    OAuthRuntimeCredentials,
    OAuthTokenResponse,
    ProviderResourceRequest,
    SecureLocalOAuthRuntimeBridge,
    authorize_provider_resource_request,
    effective_capability_manifest,
    redact_sensitive_payload,
    validate_oauth_scopes,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


PHASE_ID = "BR-30B"
PHASE_30B1_ID = "BR-30B1"
PHASE_30B2_ID = "BR-30B2"
PHASE_30B3_ID = "BR-30B3"
MODULE_NAME = "Tastytrade Sandbox Read Only Connectivity Smoke Test"
CONCRETE_CLIENT_NAME = "Tastytrade Sandbox Concrete Read Only Network Client"
DEFAULT_REPORT_DIR = Path("reports/br30b_tastytrade_sandbox_read_only_connectivity_smoke_test")
JSON_REPORT_NAME = "tastytrade_sandbox_read_only_connectivity_smoke_test.json"
MARKDOWN_REPORT_NAME = "tastytrade_sandbox_read_only_connectivity_smoke_test.md"
NORMALIZED_SNAPSHOT_NAME = "br30b_normalized_br26_snapshot.json"
SUPPORTED_MODES = ("offline", "sandbox_network")
APPROVED_SYMBOLS = ("SPY", "QQQ")
APPROVED_SANDBOX_HOSTS = ("api.cert.tastyworks.com",)
APPROVED_SANDBOX_ORIGIN = "https://api.cert.tastyworks.com"
OAUTH_TOKEN_PATH = "/oauth/token"
ACCOUNT_DISCOVERY_PATH = "/customers/me/accounts"
QUOTE_TOKEN_PATH = "/api-quote-tokens"
USER_AGENT = "JarvisQuant/BR-30B1 read-only-sandbox-smoke"
OPERATOR_CONFIRMATION_VALUE = "I_CONFIRM_BR30B1_SANDBOX_READ_ONLY_NETWORK_SMOKE"
DEFAULT_CONNECT_TIMEOUT_SECONDS = 5.0
DEFAULT_READ_TIMEOUT_SECONDS = 5.0
DEFAULT_OVERALL_TIMEOUT_SECONDS = 35.0
DXLINK_CHILD_SAMPLE_TIMEOUT_SECONDS = 30.0
DXLINK_PARENT_CLEANUP_GRACE_SECONDS = 5.0
DXLINK_SIDECAR_DIR = Path("integrations/tastytrade_dxlink")
DXLINK_SIDECAR_ENTRYPOINT = DXLINK_SIDECAR_DIR / "dxlink_read_only_sidecar.mjs"
DXLINK_RUNTIME_PREFLIGHT_ENTRYPOINT = DXLINK_SIDECAR_DIR / "dxlink_runtime_preflight.mjs"
DXLINK_NODE_EXECUTABLE = str(Path(shutil.which("node.exe") or shutil.which("node") or "node").resolve())
DXLINK_NODE_ARGV = (DXLINK_NODE_EXECUTABLE, str(DXLINK_SIDECAR_ENTRYPOINT))
DXLINK_RUNTIME_PREFLIGHT_ARGV = (DXLINK_NODE_EXECUTABLE, str(DXLINK_RUNTIME_PREFLIGHT_ENTRYPOINT))
DXLINK_STDIN_MAX_BYTES = 4096
DXLINK_STDOUT_MAX_BYTES = 16384
DXLINK_STDERR_MAX_BYTES = 2048
DXLINK_RUNTIME_PREFLIGHT_TIMEOUT_SECONDS = 8.0
DXLINK_ALLOWED_STAGES = (
    "child_started",
    "sdk_loaded",
    "client_created",
    "listeners_registered",
    "auth_token_set",
    "connect_called",
    "transport_connected",
    "authentication_authorized",
    "feed_created",
    "feed_opened",
    "quote_subscription_created",
    "candle_subscription_created",
    "subscriptions_active",
    "quote_received",
    "candle_received",
    "sample_complete",
    "cleanup_started",
    "cleanup_complete",
)
DXLINK_ALLOWED_STDERR_CODES = (
    "dxlink_dependency_unavailable",
    "dxlink_package_metadata_unavailable",
    "dxlink_contract_mismatch",
    "dxlink_authentication_failed",
    "dxlink_subscription_failed",
    "dxlink_connect_timeout",
    "dxlink_auth_timeout",
    "dxlink_feed_open_timeout",
    "dxlink_subscription_timeout",
    "dxlink_quote_timeout",
    "dxlink_candle_timeout",
    "dxlink_sample_timeout",
    "dxlink_cleanup_failed",
    "dxlink_process_failed",
    "dxlink_runtime_environment_unavailable",
    "dxlink_stdout_empty",
    "dxlink_stdout_truncated",
    "dxlink_stdout_not_json",
    "dxlink_stdout_schema_mismatch",
    "dxlink_stdout_oversized",
    "dxlink_stderr_oversized",
    "dxlink_stderr_unexpected",
)
DXLINK_OUTPUT_FAILURE_CODES = (
    "dxlink_stdout_empty",
    "dxlink_stdout_truncated",
    "dxlink_stdout_not_json",
    "dxlink_stdout_schema_mismatch",
    "dxlink_stdout_oversized",
    "dxlink_stderr_oversized",
    "dxlink_stderr_unexpected",
)
DXLINK_CHILD_ENV_ALLOWLIST = (
    "ALLUSERSPROFILE",
    "APPDATA",
    "COMMONPROGRAMFILES",
    "COMMONPROGRAMFILES(X86)",
    "COMMONPROGRAMW6432",
    "COMPUTERNAME",
    "COMSPEC",
    "DRIVERDATA",
    "HOMEDRIVE",
    "HOMEPATH",
    "LOCALAPPDATA",
    "LOGONSERVER",
    "NUMBER_OF_PROCESSORS",
    "OS",
    "PATH",
    "PATHEXT",
    "PROCESSOR_ARCHITECTURE",
    "PROCESSOR_IDENTIFIER",
    "PROCESSOR_LEVEL",
    "PROCESSOR_REVISION",
    "PROGRAMDATA",
    "PROGRAMFILES",
    "PROGRAMFILES(X86)",
    "PROGRAMW6432",
    "PSMODULEPATH",
    "PUBLIC",
    "SESSIONNAME",
    "SSL_CERT_DIR",
    "SSL_CERT_FILE",
    "SYSTEMDRIVE",
    "SYSTEMROOT",
    "TEMP",
    "TMP",
    "USERDOMAIN",
    "USERDOMAIN_ROAMINGPROFILE",
    "USERNAME",
    "USERPROFILE",
    "WINDIR",
)
DXLINK_CHILD_ENV_DENY_KEY_MARKERS = (
    "ACCOUNT",
    "API_KEY",
    "APIKEY",
    "AUTH",
    "AUTHORIZATION",
    "BROKER",
    "CLIENT_ID",
    "CLIENT_SECRET",
    "CREDENTIAL",
    "CUSTOMER",
    "KEY",
    "OAUTH",
    "PASSWORD",
    "PASSWD",
    "PRIVATE",
    "REFRESH",
    "SECRET",
    "TASTYTRADE",
    "TOKEN",
)
DXLINK_CHILD_ENV_FORBIDDEN_NAMES = (
    "NODE_DEBUG",
    "NODE_EXTRA_CA_CERTS",
    "NODE_OPTIONS",
    "NODE_PATH",
    "SSLKEYLOGFILE",
)
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
    "account_payload_malformed",
    "quote_token_payload_malformed",
    "missing_symbol",
    "duplicate_event",
    "stale_quote",
    "clock_skew",
    "redaction_failed",
    "normalization_failed",
    "unauthorized",
    "bad_request",
    "forbidden",
    "provider_server_error",
    "timeout",
    "websocket_endpoint_rejected",
    "dxlink_dependency_unavailable",
    "dxlink_package_metadata_unavailable",
    "dxlink_contract_mismatch",
    "dxlink_authentication_failed",
    "dxlink_subscription_failed",
    "dxlink_connect_timeout",
    "dxlink_auth_timeout",
    "dxlink_feed_open_timeout",
    "dxlink_subscription_timeout",
    "dxlink_quote_timeout",
    "dxlink_candle_timeout",
    "dxlink_sample_timeout",
    "dxlink_cleanup_failed",
    "dxlink_process_failed",
    "dxlink_runtime_environment_unavailable",
    "dxlink_stdout_empty",
    "dxlink_stdout_truncated",
    "dxlink_stdout_not_json",
    "dxlink_stdout_schema_mismatch",
    "dxlink_stdout_oversized",
    "dxlink_stderr_oversized",
    "dxlink_stderr_unexpected",
    "dxlink_output_malformed",
    "dxlink_secret_leak_detected",
    "unsupported_event",
)


class SandboxClientError(OAuthBridgeError):
    def __init__(self, reason: str) -> None:
        super().__init__(f"BR-30B1 sandbox client failed closed: {reason}")
        self.reason = reason


class SandboxTimeoutError(SandboxClientError):
    def __init__(self) -> None:
        super().__init__("timeout")


class HttpResponse(Protocol):
    status_code: int
    url: str

    def json(self) -> Any:
        ...


class HttpTransport(Protocol):
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
    ) -> HttpResponse:
        ...


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
    sandbox_host = "api.cert.tastyworks.com"

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


class RequestsHttpTransport:
    def __init__(self) -> None:
        import requests  # type: ignore[import-not-found]

        self._session = requests.Session()

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
    ) -> HttpResponse:
        return self._session.request(
            method,
            url,
            headers=headers,
            data=data,
            json=json_body,
            timeout=timeout,
            allow_redirects=allow_redirects,
        )


class DXLinkSidecarRunner(Protocol):
    def run(
        self,
        argv: tuple[str, ...],
        stdin_payload: str,
        timeout_seconds: float,
    ) -> "DXLinkSidecarCompleted":
        ...


@dataclass(frozen=True)
class DXLinkSidecarCompleted:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False


class SubprocessDXLinkSidecarRunner:
    def run(
        self,
        argv: tuple[str, ...],
        stdin_payload: str,
        timeout_seconds: float,
    ) -> DXLinkSidecarCompleted:
        try:
            child_env = _dxlink_child_environment()
        except SandboxClientError:
            raise
        except Exception as exc:
            raise SandboxClientError("dxlink_runtime_environment_unavailable") from exc
        try:
            process = subprocess.Popen(
                list(argv),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=False,
                env=child_env,
            )
        except FileNotFoundError as exc:
            raise SandboxClientError("dxlink_dependency_unavailable") from exc
        except Exception as exc:
            raise SandboxClientError("dxlink_process_failed") from exc
        try:
            stdout, stderr = process.communicate(stdin_payload, timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            return DXLinkSidecarCompleted(
                process.returncode if process.returncode is not None else -1,
                stdout[:DXLINK_STDOUT_MAX_BYTES + 1],
                stderr[:DXLINK_STDERR_MAX_BYTES + 1],
                timed_out=True,
            )
        return DXLinkSidecarCompleted(
            process.returncode if process.returncode is not None else -1,
            stdout[:DXLINK_STDOUT_MAX_BYTES + 1],
            stderr[:DXLINK_STDERR_MAX_BYTES + 1],
        )


class DXLinkRuntimePreflightRunner(Protocol):
    def run(
        self,
        argv: tuple[str, ...],
        stdin_payload: str,
        timeout_seconds: float,
    ) -> DXLinkSidecarCompleted:
        ...


class SubprocessDXLinkRuntimePreflightRunner:
    def run(
        self,
        argv: tuple[str, ...],
        stdin_payload: str,
        timeout_seconds: float,
    ) -> DXLinkSidecarCompleted:
        if stdin_payload:
            raise SandboxClientError("dxlink_runtime_environment_unavailable")
        return SubprocessDXLinkSidecarRunner().run(argv, "", timeout_seconds)


def run_dxlink_runtime_preflight(
    runner: DXLinkRuntimePreflightRunner | None = None,
    *,
    timeout_seconds: float = DXLINK_RUNTIME_PREFLIGHT_TIMEOUT_SECONDS,
) -> DXLinkSidecarCompleted:
    completed = (runner or SubprocessDXLinkRuntimePreflightRunner()).run(
        DXLINK_RUNTIME_PREFLIGHT_ARGV,
        "",
        timeout_seconds,
    )
    if completed.timed_out:
        return DXLinkSidecarCompleted(
            completed.returncode,
            "",
            "dxlink_sample_timeout",
            timed_out=True,
        )
    output_failure = _dxlink_output_failure_code(completed, preflight=True)
    if output_failure:
        return DXLinkSidecarCompleted(completed.returncode, "", output_failure)
    if completed.returncode != 0:
        code = completed.stderr if completed.stderr in DXLINK_ALLOWED_STDERR_CODES else "dxlink_process_failed"
        return DXLinkSidecarCompleted(completed.returncode, "", code)
    envelope = json.loads(completed.stdout)
    if envelope != {
        "ok": True,
        "sdk": "@dxfeed/dxlink-api",
        "contract": "0.3.0",
        "connection_attempted": False,
        "credentials_accepted": False,
    }:
        return DXLinkSidecarCompleted(completed.returncode, "", "dxlink_stdout_schema_mismatch")
    return DXLinkSidecarCompleted(0, completed.stdout, "")


class TastytradeSandboxOAuthRefreshTokenClient:
    provider_name = "tastytrade"

    def __init__(
        self,
        http_transport: HttpTransport | None = None,
        *,
        connect_timeout_seconds: float = DEFAULT_CONNECT_TIMEOUT_SECONDS,
        read_timeout_seconds: float = DEFAULT_READ_TIMEOUT_SECONDS,
    ) -> None:
        self._http = http_transport or RequestsHttpTransport()
        self._connect_timeout_seconds = connect_timeout_seconds
        self._read_timeout_seconds = read_timeout_seconds
        self.request_evidence: list[dict[str, Any]] = []

    def refresh_access_token(
        self,
        credentials: OAuthRuntimeCredentials,
        scopes: tuple[str, ...],
        as_of: datetime,
    ) -> OAuthTokenResponse:
        credentials.validate()
        validate_oauth_scopes(scopes)
        url = f"{APPROVED_SANDBOX_ORIGIN}{OAUTH_TOKEN_PATH}"
        _assert_firewall_allowed("POST", url, is_oauth_token_refresh=True)
        headers = _headers(with_authorization=None, content_type="application/json")
        try:
            response = self._http.request(
                "POST",
                url,
                headers=headers,
                json_body={
                    "grant_type": "refresh_token",
                    "refresh_token": credentials.refresh_token,
                    "client_secret": credentials.client_secret,
                    "scope": " ".join(scopes),
                },
                timeout=(self._connect_timeout_seconds, self._read_timeout_seconds),
                allow_redirects=False,
            )
        except TimeoutError as exc:
            raise SandboxTimeoutError() from exc
        self.request_evidence.append(_request_evidence("POST", url, response, as_of))
        _reject_bad_response("POST", url, response)
        payload = _oauth_token_payload(response)
        access_token = payload.get("access_token")
        expires_in = payload.get("expires_in")
        token_type = payload.get("token_type")
        scope_text = payload.get("scope")
        if not isinstance(access_token, str) or not access_token.strip():
            raise SandboxClientError("malformed_payload")
        if not isinstance(expires_in, int) or expires_in <= 0:
            raise SandboxClientError("malformed_payload")
        if not isinstance(token_type, str) or token_type != "Bearer":
            raise SandboxClientError("malformed_payload")
        if scope_text is None:
            granted_scopes = tuple(sorted(scopes))
        elif isinstance(scope_text, str):
            granted_scopes = tuple(sorted(scope for scope in scope_text.replace(",", " ").split() if scope))
        else:
            raise SandboxClientError("malformed_payload")
        return OAuthTokenResponse(
            access_token=access_token,
            expires_at=as_of + timedelta(seconds=expires_in),
            scopes=granted_scopes,
            token_type=token_type,
        )

    def revoke_access_token(self, access_token: InMemoryAccessToken) -> None:
        return None


class TastytradeSandboxConcreteReadOnlyNetworkClient:
    provider_name = "tastytrade"
    sandbox_host = "api.cert.tastyworks.com"

    def __init__(
        self,
        http_transport: HttpTransport | None = None,
        dxlink_runner: DXLinkSidecarRunner | None = None,
        *,
        connect_timeout_seconds: float = DEFAULT_CONNECT_TIMEOUT_SECONDS,
        read_timeout_seconds: float = DEFAULT_READ_TIMEOUT_SECONDS,
        overall_timeout_seconds: float = DEFAULT_OVERALL_TIMEOUT_SECONDS,
    ) -> None:
        self._http = http_transport or RequestsHttpTransport()
        self._dxlink_runner = dxlink_runner or SubprocessDXLinkSidecarRunner()
        self._connect_timeout_seconds = connect_timeout_seconds
        self._read_timeout_seconds = read_timeout_seconds
        self._overall_timeout_seconds = overall_timeout_seconds
        self.request_evidence: list[dict[str, Any]] = []
        self.dxlink_request_evidence: list[dict[str, Any]] = []

    def discover_customer_accounts(
        self,
        token: InMemoryAccessToken,
        as_of: datetime,
    ) -> "SandboxCustomerDiscovery":
        response = self._get(ACCOUNT_DISCOVERY_PATH, token, as_of)
        payload = _json_payload(response, malformed_reason="account_payload_malformed")
        accounts = _extract_accounts(payload)
        customer_id = _extract_customer_id(payload)
        return SandboxCustomerDiscovery(
            customer_id=customer_id,
            account_ids=accounts,
            provider_timestamp=_provider_timestamp(payload, as_of),
            acquisition_timestamp=as_of.isoformat(),
        )

    def obtain_quote_token(self, token: InMemoryAccessToken, as_of: datetime) -> "SandboxQuoteToken":
        response = self._get(QUOTE_TOKEN_PATH, token, as_of)
        payload = _json_payload(response, malformed_reason="quote_token_payload_malformed")
        quote_payload = _quote_token_payload(payload)
        quote_token = _first_string(quote_payload, ("token", "quote_token", "api_quote_token"))
        websocket_url = _first_string(quote_payload, ("dxlink-url", "dxlink_url", "websocket_url", "streamer_url", "wss_url"))
        feed_identity = _first_string(quote_payload, ("feed", "feed_identity", "streamer_identity"), default="tastytrade.market-data.read-only")
        level = _first_string(quote_payload, ("level",), default="")
        if not quote_token or not websocket_url:
            raise SandboxClientError("quote_token_payload_malformed")
        _assert_websocket_endpoint_allowed(websocket_url)
        return SandboxQuoteToken(
            quote_token=quote_token,
            websocket_url=websocket_url,
            feed_identity=feed_identity,
            level=level,
            provider_timestamp=_provider_timestamp(payload, as_of),
            acquisition_timestamp=as_of.isoformat(),
        )

    def stream_delayed_market_data(
        self,
        quote_token: "SandboxQuoteToken",
        symbols: tuple[str, ...],
        as_of: datetime,
    ) -> "SandboxMarketDataSample":
        if tuple(symbols) != APPROVED_SYMBOLS:
            raise SandboxClientError("missing_symbol")
        _assert_websocket_endpoint_allowed(quote_token.websocket_url)
        if self._overall_timeout_seconds <= DXLINK_CHILD_SAMPLE_TIMEOUT_SECONDS:
            raise SandboxClientError("dxlink_process_failed")
        if self._overall_timeout_seconds - DXLINK_CHILD_SAMPLE_TIMEOUT_SECONDS < DXLINK_PARENT_CLEANUP_GRACE_SECONDS:
            raise SandboxClientError("dxlink_process_failed")
        stdin_payload = _dxlink_stdin_payload(quote_token, symbols, as_of, DXLINK_CHILD_SAMPLE_TIMEOUT_SECONDS)
        completed = self._dxlink_runner.run(DXLINK_NODE_ARGV, stdin_payload, self._overall_timeout_seconds)
        terminal_stage, stage_counts = _dxlink_sanitized_stage_evidence(completed.stdout)
        output_failure = _dxlink_output_failure_code(completed)
        self.dxlink_request_evidence.append(
            {
                "argv": DXLINK_NODE_ARGV,
                "shell": False,
                "parent_timeout_seconds": self._overall_timeout_seconds,
                "child_timeout_seconds": DXLINK_CHILD_SAMPLE_TIMEOUT_SECONDS,
                "parent_cleanup_grace_seconds": self._overall_timeout_seconds - DXLINK_CHILD_SAMPLE_TIMEOUT_SECONDS,
                "stdin_only_secret_transport": True,
                "stdin_size_bytes": len(stdin_payload.encode("utf-8")),
                "stdout_size_bytes": len(completed.stdout.encode("utf-8")),
                "stderr_size_bytes": len(completed.stderr.encode("utf-8")),
                "return_code": completed.returncode,
                "timed_out": completed.timed_out,
                "sanitized_terminal_stage": terminal_stage,
                "sanitized_stage_counts": stage_counts,
                "output_classification": output_failure,
                "environment_values_written": False,
                "command_line_secret_values_written": False,
                "temporary_files_written": False,
                "process_title_secret_values_written": False,
            }
        )
        if _contains_secret_material_text(completed.stdout, quote_token) or _contains_secret_material_text(completed.stderr, quote_token):
            raise SandboxClientError("dxlink_secret_leak_detected")
        if completed.timed_out:
            raise SandboxClientError("dxlink_sample_timeout")
        if output_failure:
            raise SandboxClientError(output_failure)
        failure_code = _dxlink_failure_code_from_stdout(completed.stdout)
        if failure_code:
            raise SandboxClientError(failure_code)
        stderr_code = completed.stderr
        if completed.returncode != 0:
            raise SandboxClientError(stderr_code if stderr_code in REJECTION_REASONS else "dxlink_process_failed")
        return _sample_from_dxlink_stdout(completed.stdout, as_of)

    def _get(self, path: str, token: InMemoryAccessToken, as_of: datetime) -> HttpResponse:
        url = f"{APPROVED_SANDBOX_ORIGIN}{path}"
        _assert_firewall_allowed("GET", url)
        try:
            response = self._http.request(
                "GET",
                url,
                headers=_headers(with_authorization=f"{token.token_type} {token.access_token}"),
                timeout=(self._connect_timeout_seconds, self._read_timeout_seconds),
                allow_redirects=False,
            )
        except TimeoutError as exc:
            raise SandboxTimeoutError() from exc
        self.request_evidence.append(_request_evidence("GET", url, response, as_of))
        _reject_bad_response("GET", url, response)
        return response


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
    level: str = ""
    websocket_url: str = field(default="", repr=False)


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
    except SandboxClientError as exc:
        return _blocked_result(resolved, as_of, (_client_reason(exc, "customer_discovery_failed"),), None, None, None, None)
    except Exception:
        return _blocked_result(resolved, as_of, ("customer_discovery_failed",), None, None, None, None)
    account_evidence = _redacted_account_evidence(discovery)
    if not _account_evidence_is_redacted(account_evidence):
        return _blocked_result(resolved, as_of, ("redaction_failed",), account_evidence, None, None, None)

    try:
        quote_token = sandbox_client.obtain_quote_token(token, as_of)
    except SandboxClientError as exc:
        return _blocked_result(resolved, as_of, (_client_reason(exc, "quote_token_failed"),), account_evidence, None, None, None)
    except Exception:
        return _blocked_result(resolved, as_of, ("quote_token_failed",), account_evidence, None, None, None)
    try:
        sample = sandbox_client.stream_delayed_market_data(quote_token, resolved.symbols, as_of)
    except SandboxClientError as exc:
        return _blocked_result(
            resolved,
            as_of,
            (_client_reason(exc, "market_data_disconnect"),),
            account_evidence,
            None,
            None,
            None,
            sandbox_client,
        )
    except Exception:
        return _blocked_result(
            resolved,
            as_of,
            ("market_data_disconnect",),
            account_evidence,
            None,
            None,
            None,
            sandbox_client,
        )

    raw_payload = _raw_market_data_payload(quote_token, sample)
    reasons = _sample_rejection_reasons(sample, resolved, as_of)
    if reasons:
        return _blocked_result(resolved, as_of, reasons, account_evidence, raw_payload, None, sample, sandbox_client)

    # Reuse the BR-30 normalizer without file IO by invoking its provider through
    # the same validation path on an in-memory payload.
    adapter_result = _normalize_in_memory_br30(raw_payload, resolved, as_of)
    if not adapter_result.accepted_for_shadow_research or adapter_result.normalized_snapshot is None:
        return _blocked_result(
            resolved,
            as_of,
            ("normalization_failed",),
            account_evidence,
            raw_payload,
            None,
            sample,
            sandbox_client,
        )
    normalized_snapshot = _restamp_br30b_snapshot_artifact(adapter_result.normalized_snapshot)

    result = SandboxSmokeTestResult(
        as_of=as_of,
        label=HUMAN_REVIEW_REQUIRED,
        request_mode=resolved.mode,
        accepted_for_monitoring=True,
        rejection_reasons=(),
        account_evidence=account_evidence,
        market_data_evidence={
            **_market_data_evidence(raw_payload, sample, as_of),
            **_client_request_evidence(sandbox_client),
        },
        normalized_snapshot=normalized_snapshot,
        checksums=_checksums(raw_payload, normalized_snapshot),
        safety=safety_manifest(resolved.mode, sandbox_network_attempted=True),
    )
    result.validate()
    return result


def safety_manifest(mode: str = "offline", sandbox_network_attempted: bool = False) -> dict[str, Any]:
    return {
        "phase": PHASE_ID,
        "concrete_client_phase": PHASE_30B1_ID,
        "oauth_contract_phase": PHASE_30B2_ID,
        "rest_response_contract_phase": PHASE_30B3_ID,
        "module": MODULE_NAME,
        "concrete_client": CONCRETE_CLIENT_NAME,
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
        "approved_sandbox_origin": APPROVED_SANDBOX_ORIGIN,
        "approved_http_paths": (ACCOUNT_DISCOVERY_PATH, QUOTE_TOKEN_PATH),
        "approved_oauth_token_path": OAUTH_TOKEN_PATH,
        "oauth_token_request_body_keys": ("client_secret", "grant_type", "refresh_token", "scope"),
        "oauth_token_request_uses_json_body": True,
        "oauth_token_request_omits_client_id": True,
        "oauth_error_bodies_persisted": False,
        "approved_user_agent": USER_AGENT,
        "production_hosts_rejected": True,
        "alternate_sandbox_hosts_rejected": True,
        "http_downgrade_rejected": True,
        "cross_host_redirects_rejected": True,
        "arbitrary_caller_urls_rejected": True,
        "websocket_endpoint_must_come_from_quote_token_response": True,
        "quote_token_endpoint_scheme_required": "wss",
        "quote_token_full_dxlink_url_written": False,
        "quote_token_values_written": False,
        "quote_token_level_metadata_supported": True,
        "dxlink_protocol_phase": "BR-30B4",
        "dxlink_verified_lifecycle_phase": "BR-30B4G",
        "dxlink_runtime_environment_phase": "BR-30B4C",
        "dxlink_official_sdk_required": True,
        "dxlink_sidecar_directory": str(DXLINK_SIDECAR_DIR),
        "dxlink_sidecar_fixed_argv": DXLINK_NODE_ARGV,
        "dxlink_runtime_preflight_fixed_argv": DXLINK_RUNTIME_PREFLIGHT_ARGV,
        "dxlink_sidecar_shell_execution": False,
        "dxlink_sidecar_stdin_only_secret_transport": True,
        "dxlink_sidecar_environment_secret_transport": False,
        "dxlink_sidecar_child_environment_explicit": True,
        "dxlink_sidecar_child_environment_case_insensitive": True,
        "dxlink_sidecar_child_environment_deny_filtered": True,
        "dxlink_sidecar_child_environment_non_secret": True,
        "dxlink_sidecar_child_environment_not_credential_transport": True,
        "dxlink_sidecar_child_environment_allowlist": DXLINK_CHILD_ENV_ALLOWLIST,
        "dxlink_sidecar_child_environment_secret_key_markers_blocked": DXLINK_CHILD_ENV_DENY_KEY_MARKERS,
        "dxlink_sidecar_child_environment_forbidden_names": DXLINK_CHILD_ENV_FORBIDDEN_NAMES,
        "dxlink_sidecar_node_no_warnings_fixed": "1",
        "dxlink_sidecar_command_line_secret_transport": False,
        "dxlink_sidecar_temporary_file_secret_transport": False,
        "dxlink_sidecar_stdout_machine_readable_only": True,
        "dxlink_sidecar_stderr_allowlisted_codes_only": True,
        "dxlink_sidecar_stdout_max_bytes": DXLINK_STDOUT_MAX_BYTES,
        "dxlink_sidecar_stderr_max_bytes": DXLINK_STDERR_MAX_BYTES,
        "dxlink_parent_timeout_seconds": DEFAULT_OVERALL_TIMEOUT_SECONDS,
        "dxlink_child_sample_timeout_seconds": DXLINK_CHILD_SAMPLE_TIMEOUT_SECONDS,
        "dxlink_parent_cleanup_grace_seconds": DXLINK_PARENT_CLEANUP_GRACE_SECONDS,
        "dxlink_feed_aggregation_period_seconds": 1,
        "dxlink_historical_candle_lookback_minutes": 30,
        "dxlink_child_timeout_shorter_than_parent": DXLINK_CHILD_SAMPLE_TIMEOUT_SECONDS < DEFAULT_OVERALL_TIMEOUT_SECONDS,
        "dxlink_allowed_symbols": APPROVED_SYMBOLS,
        "dxlink_allowed_event_types": ("Quote", "Candle"),
        "dxlink_disallowed_event_types": (
            "Trade",
            "Greeks",
            "Summary",
            "Profile",
            "Underlying",
            "Order",
            "account-streaming",
        ),
        "dxlink_feed_contract": "AUTO",
        "dxlink_feed_data_format": "COMPACT",
        "dxlink_candle_interval": "1m",
        "account_payload_malformed_reason_supported": True,
        "quote_token_payload_malformed_reason_supported": True,
        "dxlink_stage_rejection_reasons_supported": (
            "dxlink_dependency_unavailable",
            "dxlink_authentication_failed",
            "dxlink_subscription_failed",
            "dxlink_connect_timeout",
            "dxlink_auth_timeout",
            "dxlink_feed_open_timeout",
            "dxlink_subscription_timeout",
            "dxlink_quote_timeout",
            "dxlink_candle_timeout",
            "dxlink_sample_timeout",
            "dxlink_cleanup_failed",
            "dxlink_process_failed",
            "dxlink_runtime_environment_unavailable",
            "dxlink_stdout_empty",
            "dxlink_stdout_truncated",
            "dxlink_stdout_not_json",
            "dxlink_stdout_schema_mismatch",
            "dxlink_stdout_oversized",
            "dxlink_stderr_oversized",
            "dxlink_stderr_unexpected",
            "dxlink_output_malformed",
            "dxlink_secret_leak_detected",
        ),
        "long_running_stream_permitted": False,
        "access_tokens_memory_only": True,
        "quote_tokens_memory_only": True,
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
        ProviderResourceRequest("GET", f"https://{client.sandbox_host}{ACCOUNT_DISCOVERY_PATH}")
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
    capabilities = effective_capability_manifest(token.scopes)
    if not set(ALLOWED_OAUTH_SCOPES).issubset(set(token.scopes)):
        reasons.append("unexpected_scope")
    if any(
        capabilities.get(name) is not False
        for name in (
            "order_read_capability",
            "order_create_capability",
            "order_replace_capability",
            "order_cancel_capability",
            "account_mutation_capability",
            "position_mutation_capability",
            "execution_capability",
            "external_routing_capability",
            "live_trading_capability",
        )
    ):
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
            "quote_token_level": quote_token.level,
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
    quote_symbols = {event.symbol for event in sample.events if event.event_type == "quote"}
    bar_symbols = {event.symbol for event in sample.events if event.event_type == "bar"}
    if set(request.symbols) - symbols or set(request.symbols) - quote_symbols or set(request.symbols) - bar_symbols:
        reasons.append("missing_symbol")
    for event in sample.events:
        if event.event_type not in ("quote", "bar") or event.symbol not in APPROVED_SYMBOLS:
            reasons.append("unsupported_event")
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
        if event.delay_minutes != 15:
            reasons.append("stale_quote")
        if event.event_type == "quote" and any(value is None for value in (event.bid, event.ask)):
            reasons.append("malformed_payload")
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
        "quote_token_level": raw_payload.get("metadata", {}).get("quote_token_level"),
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
        "provider_resource_write_count": 0,
        "order_call_count": 0,
        "mutation_call_count": 0,
        "routing_call_count": 0,
        "execution_call_count": 0,
    }


def _client_request_evidence(client: TastytradeSandboxReadOnlyClient | None) -> dict[str, Any]:
    records = getattr(client, "request_evidence", None)
    dxlink_records = getattr(client, "dxlink_request_evidence", None)
    if not isinstance(records, list):
        base = {
            "request_records": (),
            "provider_resource_write_count": 0,
            "order_call_count": 0,
            "mutation_call_count": 0,
            "routing_call_count": 0,
            "execution_call_count": 0,
        }
        if isinstance(dxlink_records, list):
            base["dxlink_sidecar_records"] = tuple(dxlink_records)
        return base
    sanitized = tuple(redact_sensitive_payload(record) for record in records)
    return {
        "request_records": sanitized,
        "dxlink_sidecar_records": tuple(dxlink_records) if isinstance(dxlink_records, list) else (),
        "provider_resource_write_count": 0,
        "order_call_count": 0,
        "mutation_call_count": 0,
        "routing_call_count": 0,
        "execution_call_count": 0,
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
    client: TastytradeSandboxReadOnlyClient | None = None,
) -> SandboxSmokeTestResult:
    result = SandboxSmokeTestResult(
        as_of=as_of,
        label=BLOCKED_BY_SAFETY_GATE,
        request_mode=request.mode,
        accepted_for_monitoring=False,
        rejection_reasons=tuple(dict.fromkeys(reasons)),
        account_evidence=account_evidence or {"redacted": True, "raw_account_identifiers_present": False},
        market_data_evidence={
            **(_market_data_evidence(raw_payload, sample, as_of) if raw_payload and sample else {}),
            **_client_request_evidence(client),
        },
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


def _client_reason(exc: SandboxClientError, fallback: str) -> str:
    return exc.reason if exc.reason in REJECTION_REASONS else fallback


def _headers(with_authorization: str | None, *, content_type: str = "application/x-www-form-urlencoded") -> dict[str, str]:
    headers = {
        "Accept": "application/json",
        "Content-Type": content_type,
        "User-Agent": USER_AGENT,
    }
    if with_authorization:
        headers["Authorization"] = with_authorization
    return headers


def _dxlink_stdin_payload(
    quote_token: SandboxQuoteToken,
    symbols: tuple[str, ...],
    as_of: datetime,
    timeout_seconds: float,
) -> str:
    if tuple(symbols) != APPROVED_SYMBOLS:
        raise SandboxClientError("missing_symbol")
    payload = {
        "quoteToken": quote_token.quote_token,
        "dxlinkUrl": quote_token.websocket_url,
        "symbols": list(symbols),
        "acquisitionTimestamp": as_of.isoformat(),
        "timeoutMs": int(max(1.0, timeout_seconds) * 1000),
    }
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    if len(text.encode("utf-8")) > DXLINK_STDIN_MAX_BYTES:
        raise SandboxClientError("dxlink_output_malformed")
    return text


def _dxlink_output_failure_code(completed: DXLinkSidecarCompleted, *, preflight: bool = False) -> str | None:
    stdout_bytes = len(completed.stdout.encode("utf-8"))
    stderr_bytes = len(completed.stderr.encode("utf-8"))
    if stdout_bytes > DXLINK_STDOUT_MAX_BYTES:
        return "dxlink_stdout_oversized"
    if stderr_bytes > DXLINK_STDERR_MAX_BYTES:
        return "dxlink_stderr_oversized"
    if completed.stderr:
        if completed.stderr not in DXLINK_ALLOWED_STDERR_CODES:
            return "dxlink_stderr_unexpected"
        if completed.returncode == 0:
            return "dxlink_stderr_unexpected"
        return None
    if completed.returncode != 0:
        return _classify_dxlink_stdout(completed.stdout, preflight=preflight) if completed.stdout else None
    return _classify_dxlink_stdout(completed.stdout, preflight=preflight)


def _classify_dxlink_stdout(stdout: str, *, preflight: bool = False) -> str | None:
    stripped = stdout.strip()
    if not stripped:
        return "dxlink_stdout_empty"
    try:
        envelope = json.loads(stripped)
    except json.JSONDecodeError as exc:
        if exc.msg == "Extra data":
            return "dxlink_stdout_not_json"
        if _looks_like_truncated_json(stripped):
            return "dxlink_stdout_truncated"
        return "dxlink_stdout_not_json"
    if stripped != stdout:
        return "dxlink_stdout_not_json"
    if preflight:
        return None if _valid_dxlink_preflight_envelope(envelope) else "dxlink_stdout_schema_mismatch"
    return None if (_valid_dxlink_success_envelope(envelope) or _valid_dxlink_failure_envelope(envelope)) else "dxlink_stdout_schema_mismatch"


def _looks_like_truncated_json(text: str) -> bool:
    if not text or text[0] not in "[{":
        return False
    expected = "}" if text[0] == "{" else "]"
    return not text.endswith(expected)


def _valid_dxlink_preflight_envelope(envelope: Any) -> bool:
    return envelope == {
        "ok": True,
        "sdk": "@dxfeed/dxlink-api",
        "contract": "0.3.0",
        "connection_attempted": False,
        "credentials_accepted": False,
    }


def _valid_dxlink_success_envelope(envelope: Any) -> bool:
    if not isinstance(envelope, dict):
        return False
    if set(envelope) != {"ok", "connected", "disconnected", "reconnect_count", "terminal_stage", "stage_counts", "counts", "events"}:
        return False
    if envelope.get("ok") is not True or envelope.get("connected") is not True:
        return False
    if not isinstance(envelope.get("disconnected"), bool):
        return False
    if not isinstance(envelope.get("reconnect_count"), int) or envelope["reconnect_count"] < 0:
        return False
    if envelope.get("terminal_stage") not in DXLINK_ALLOWED_STAGES:
        return False
    if not _valid_dxlink_stage_counts(envelope.get("stage_counts"), envelope.get("terminal_stage")):
        return False
    if envelope["stage_counts"]["sample_complete"] <= 0 or envelope["stage_counts"]["cleanup_complete"] <= 0:
        return False
    counts = envelope.get("counts")
    if not _valid_dxlink_record_counts(counts, require_complete=True):
        return False
    events = envelope.get("events")
    if not isinstance(events, list) or len(events) != 4:
        return False
    logical_keys: set[tuple[str, str]] = set()
    for event in events:
        if not isinstance(event, dict):
            return False
        event_type = event.get("event_type") or event.get("eventType")
        symbol = event.get("symbol") or event.get("eventSymbol")
        try:
            normalized_symbol = _normalize_dxlink_symbol(symbol)
        except SandboxClientError:
            return False
        if event_type == "Quote":
            required = {"event_type", "symbol", "provider_timestamp", "exchange_timestamp", "acquisition_timestamp"}
            if not required.issubset(event) or not (("bidPrice" in event and "askPrice" in event) or ("bid" in event and "ask" in event)):
                return False
            logical_keys.add(("quote", normalized_symbol))
        elif event_type == "Candle":
            required = {
                "event_type",
                "symbol",
                "provider_timestamp",
                "exchange_timestamp",
                "acquisition_timestamp",
                "open",
                "high",
                "low",
                "close",
                "volume",
            }
            if not required.issubset(event):
                return False
            logical_keys.add(("bar", normalized_symbol))
        else:
            return False
    return logical_keys == {("quote", "SPY"), ("quote", "QQQ"), ("bar", "SPY"), ("bar", "QQQ")}


def _valid_dxlink_failure_envelope(envelope: Any) -> bool:
    if not isinstance(envelope, dict):
        return False
    required_keys = {
        "ok",
        "failure_code",
        "terminal_stage",
        "stage_counts",
        "counts",
        "approved_symbols",
        "approved_event_types",
        "child_timeout_ms",
        "cleanup_status",
        "real_paper_order_submitted",
        "broker_order_call_performed",
        "live_trading_enabled",
    }
    if set(envelope) != required_keys:
        return False
    if envelope.get("ok") is not False:
        return False
    if envelope.get("failure_code") not in {
        "dxlink_connect_timeout",
        "dxlink_auth_timeout",
        "dxlink_feed_open_timeout",
        "dxlink_subscription_timeout",
        "dxlink_quote_timeout",
        "dxlink_candle_timeout",
        "dxlink_sample_timeout",
        "dxlink_cleanup_failed",
        "dxlink_dependency_unavailable",
        "dxlink_contract_mismatch",
        "dxlink_process_failed",
    }:
        return False
    if envelope.get("terminal_stage") not in DXLINK_ALLOWED_STAGES:
        return False
    if not _valid_dxlink_stage_counts(envelope.get("stage_counts"), envelope.get("terminal_stage")):
        return False
    if not _valid_dxlink_record_counts(envelope.get("counts"), require_complete=False):
        return False
    if tuple(envelope.get("approved_symbols", ())) != APPROVED_SYMBOLS:
        return False
    if tuple(envelope.get("approved_event_types", ())) != ("Quote", "Candle"):
        return False
    if not isinstance(envelope.get("child_timeout_ms"), int) or not 2_000 <= envelope["child_timeout_ms"] <= 30_000:
        return False
    if envelope.get("cleanup_status") not in {"complete", "failed"}:
        return False
    if envelope["cleanup_status"] == "complete" and envelope["stage_counts"]["cleanup_complete"] <= 0:
        return False
    if envelope["cleanup_status"] == "failed" and envelope["stage_counts"]["cleanup_complete"] > 0:
        return False
    for flag in ("real_paper_order_submitted", "broker_order_call_performed", "live_trading_enabled"):
        if envelope.get(flag) is not False:
            return False
    return not _contains_forbidden_dxlink_value(envelope)


def _valid_dxlink_record_counts(counts: Any, *, require_complete: bool) -> bool:
    if not isinstance(counts, dict):
        return False
    required_counts = ("quote_records", "candle_records", "logical_records", "raw_batches_processed", "raw_records_processed")
    if set(counts) != set(required_counts):
        return False
    if any(not isinstance(counts[key], int) or counts[key] < 0 or counts[key] > 64 for key in required_counts):
        return False
    if require_complete and (
        counts["quote_records"] != 2 or counts["candle_records"] != 2 or counts["logical_records"] != 4
    ):
        return False
    if counts["logical_records"] != counts["quote_records"] + counts["candle_records"]:
        return False
    if counts["raw_records_processed"] < counts["logical_records"]:
        return False
    return True


def _valid_dxlink_stage_counts(stage_counts: Any, terminal_stage: Any) -> bool:
    if not isinstance(stage_counts, dict) or set(stage_counts) != set(DXLINK_ALLOWED_STAGES):
        return False
    if any(not isinstance(stage_counts[stage], int) or stage_counts[stage] < 0 or stage_counts[stage] > 64 for stage in DXLINK_ALLOWED_STAGES):
        return False
    if not isinstance(terminal_stage, str) or terminal_stage not in DXLINK_ALLOWED_STAGES:
        return False
    terminal_index = DXLINK_ALLOWED_STAGES.index(terminal_stage)
    for index, stage in enumerate(DXLINK_ALLOWED_STAGES):
        count = stage_counts[stage]
        if index <= terminal_index:
            if count < 1 and stage not in {"quote_received", "candle_received", "sample_complete", "cleanup_started", "cleanup_complete"}:
                return False
        elif stage not in {"cleanup_started", "cleanup_complete"} and count != 0:
            return False
    prerequisites = {
        "sdk_loaded": ("child_started",),
        "listeners_registered": ("client_created",),
        "auth_token_set": ("listeners_registered",),
        "connect_called": ("auth_token_set",),
        "transport_connected": ("connect_called",),
        "authentication_authorized": ("transport_connected",),
        "feed_created": ("authentication_authorized",),
        "feed_opened": ("feed_created",),
        "quote_subscription_created": ("feed_opened",),
        "candle_subscription_created": ("quote_subscription_created",),
        "subscriptions_active": ("candle_subscription_created",),
        "quote_received": ("subscriptions_active",),
        "candle_received": ("subscriptions_active",),
        "sample_complete": ("quote_received", "candle_received"),
        "cleanup_complete": ("cleanup_started",),
    }
    for stage, required in prerequisites.items():
        if stage_counts[stage] > 0 and any(stage_counts[prereq] <= 0 for prereq in required):
            return False
    return True


def _dxlink_sanitized_stage_evidence(stdout: str) -> tuple[str | None, dict[str, int]]:
    if not stdout or len(stdout.encode("utf-8")) > DXLINK_STDOUT_MAX_BYTES:
        return None, {}
    try:
        envelope = json.loads(stdout)
    except json.JSONDecodeError:
        return None, {}
    if not isinstance(envelope, dict):
        return None, {}
    stage = envelope.get("terminal_stage")
    counts = envelope.get("counts")
    clean_counts: dict[str, int] = {}
    if isinstance(counts, dict):
        for key in ("quote_records", "candle_records", "logical_records", "raw_batches_processed", "raw_records_processed"):
            value = counts.get(key)
            if isinstance(value, int) and 0 <= value <= 64:
                clean_counts[key] = value
    return (stage if stage in DXLINK_ALLOWED_STAGES else None), clean_counts


def _dxlink_failure_code_from_stdout(stdout: str) -> str | None:
    try:
        envelope = json.loads(stdout)
    except json.JSONDecodeError:
        return None
    if not _valid_dxlink_failure_envelope(envelope):
        return None
    code = envelope.get("failure_code")
    return code if isinstance(code, str) else None


def _contains_forbidden_dxlink_value(value: Any) -> bool:
    text = json.dumps(value, sort_keys=True, separators=(",", ":")).lower()
    return any(
        marker in text
        for marker in (
            "quote-token",
            "access-token",
            "refresh-token",
            "client-secret",
            "authorization",
            "oauth",
            "wss://",
            "https://",
            "api.cert.tasty",
            "tastyworks.com",
            "bidprice",
            "askprice",
            "stack",
            "error:",
            "account-number",
        )
    )


def _dxlink_child_environment(source_env: dict[str, str] | None = None) -> dict[str, str]:
    child_env: dict[str, str] = {}
    seen_folded: set[str] = set()
    allowed = {name.upper() for name in DXLINK_CHILD_ENV_ALLOWLIST}
    forbidden = {name.upper() for name in DXLINK_CHILD_ENV_FORBIDDEN_NAMES}
    environ = dict(os.environ) if source_env is None else source_env
    for key, value in environ.items():
        upper_key = _env_key_fold(key)
        if upper_key in forbidden:
            raise SandboxClientError("dxlink_runtime_environment_unavailable")
        if upper_key not in allowed:
            continue
        if upper_key in seen_folded:
            raise SandboxClientError("dxlink_runtime_environment_unavailable")
        seen_folded.add(upper_key)
        if _dxlink_env_key_is_denied(upper_key):
            raise SandboxClientError("dxlink_runtime_environment_unavailable")
        if _dxlink_env_value_is_sensitive(value):
            raise SandboxClientError("dxlink_runtime_environment_unavailable")
        child_env[key] = value
    child_env["NODE_NO_WARNINGS"] = "1"
    return child_env


def dxlink_child_environment_audit_keys(source_env: dict[str, str] | None = None) -> tuple[str, ...]:
    return tuple(sorted(_dxlink_child_environment(source_env).keys(), key=lambda key: key.upper()))


def _env_key_fold(key: str) -> str:
    return key.upper()


def _dxlink_env_key_is_denied(upper_key: str) -> bool:
    if upper_key in {name.upper() for name in DXLINK_CHILD_ENV_FORBIDDEN_NAMES}:
        return True
    return any(marker in upper_key for marker in DXLINK_CHILD_ENV_DENY_KEY_MARKERS)


def _dxlink_env_value_is_sensitive(value: str) -> bool:
    lowered = value.lower()
    return any(
        marker in lowered
        for marker in (
            "wss://",
            "https://api.cert.tasty",
            "https://api.tasty",
            "tastytrade",
            "tastyworks",
            "quote-token",
            "access-token",
            "refresh-token",
            "client-secret",
            "api-key",
            "oauth",
            "password",
            "private key",
            "cookie=",
            "database=",
        )
    )


def _sample_from_dxlink_stdout(stdout: str, as_of: datetime) -> SandboxMarketDataSample:
    try:
        envelope = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise SandboxClientError("dxlink_output_malformed") from exc
    if not isinstance(envelope, dict) or envelope.get("ok") is not True:
        raise SandboxClientError("dxlink_output_malformed")
    if envelope.get("connected") is not True:
        raise SandboxClientError("market_data_disconnect")
    events = envelope.get("events")
    if not isinstance(events, list) or len(events) > 16:
        raise SandboxClientError("dxlink_output_malformed")
    normalized = tuple(_dxlink_event_from_payload(event, as_of) for event in events)
    if len(normalized) != 4:
        raise SandboxClientError("missing_symbol")
    logical_keys = {(event.event_type, event.symbol) for event in normalized}
    if logical_keys != {("quote", "SPY"), ("quote", "QQQ"), ("bar", "SPY"), ("bar", "QQQ")}:
        raise SandboxClientError("missing_symbol")
    return SandboxMarketDataSample(
        connected=True,
        disconnected=bool(envelope.get("disconnected", False)),
        reconnect_count=_required_int(envelope.get("reconnect_count", 0), "dxlink_output_malformed"),
        events=normalized,
    )


def _dxlink_event_from_payload(payload: Any, as_of: datetime) -> SandboxMarketDataEvent:
    if not isinstance(payload, dict):
        raise SandboxClientError("dxlink_output_malformed")
    raw_type = str(payload.get("event_type") or payload.get("eventType") or "")
    if raw_type not in ("Quote", "Candle", "quote", "candle"):
        raise SandboxClientError("unsupported_event")
    event_type = "quote" if raw_type.lower() == "quote" else "bar"
    symbol = _normalize_dxlink_symbol(payload.get("symbol") or payload.get("eventSymbol"))
    if symbol not in APPROVED_SYMBOLS:
        raise SandboxClientError("missing_symbol")
    provider_timestamp = _required_timestamp(payload.get("provider_timestamp") or payload.get("providerTimestamp"))
    exchange_timestamp = _required_timestamp(payload.get("exchange_timestamp") or payload.get("exchangeTimestamp"))
    acquisition_timestamp = _required_timestamp(payload.get("acquisition_timestamp") or payload.get("acquisitionTimestamp") or as_of.isoformat())
    if event_type == "quote":
        bid = _required_float(payload.get("bid") if "bid" in payload else payload.get("bidPrice"), "dxlink_output_malformed")
        ask = _required_float(payload.get("ask") if "ask" in payload else payload.get("askPrice"), "dxlink_output_malformed")
        return SandboxMarketDataEvent(
            event_id=f"{symbol}-quote-{exchange_timestamp}",
            event_type="quote",
            symbol=symbol,
            provider_timestamp=provider_timestamp,
            exchange_timestamp=exchange_timestamp,
            acquisition_timestamp=acquisition_timestamp,
            bid=bid,
            ask=ask,
            delay_minutes=15,
        )
    return SandboxMarketDataEvent(
        event_id=f"{symbol}-bar-{exchange_timestamp}",
        event_type="bar",
        symbol=symbol,
        provider_timestamp=provider_timestamp,
        exchange_timestamp=exchange_timestamp,
        acquisition_timestamp=acquisition_timestamp,
        open=_required_float(payload.get("open"), "dxlink_output_malformed"),
        high=_required_float(payload.get("high"), "dxlink_output_malformed"),
        low=_required_float(payload.get("low"), "dxlink_output_malformed"),
        close=_required_float(payload.get("close"), "dxlink_output_malformed"),
        volume=_required_int(payload.get("volume"), "dxlink_output_malformed"),
        delay_minutes=15,
    )


def _normalize_dxlink_symbol(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SandboxClientError("dxlink_output_malformed")
    candidate = value.strip().upper()
    for symbol in APPROVED_SYMBOLS:
        if candidate == symbol or candidate.startswith(f"{symbol}{{") or candidate.startswith(f"{symbol}:"):
            return symbol
    return candidate


def _required_timestamp(value: Any) -> str:
    if _parse_datetime(value) is None:
        raise SandboxClientError("dxlink_output_malformed")
    return str(value)


def _required_float(value: Any, reason: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise SandboxClientError(reason) from exc
    if not math.isfinite(parsed):
        raise SandboxClientError(reason)
    return parsed


def _required_int(value: Any, reason: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise SandboxClientError(reason) from exc
    return parsed


def _contains_secret_material_text(text: str, quote_token: SandboxQuoteToken) -> bool:
    if not text:
        return False
    return quote_token.quote_token in text or quote_token.websocket_url in text


def _assert_firewall_allowed(method: str, url: str, *, is_oauth_token_refresh: bool = False) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise SandboxClientError("wrong_sandbox_host")
    decision = authorize_provider_resource_request(
        ProviderResourceRequest(method, url, is_oauth_token_refresh=is_oauth_token_refresh)
    )
    if not decision.allowed:
        if "provider_mutation_path_blocked" in decision.rejection_reasons:
            raise SandboxClientError("wrong_sandbox_host")
        if "provider_http_method_not_allowed" in decision.rejection_reasons:
            raise SandboxClientError("wrong_sandbox_host")
        raise SandboxClientError("wrong_sandbox_host")


def _assert_same_approved_origin(url: str, response_url: str) -> None:
    expected = urlparse(url)
    actual = urlparse(response_url or url)
    if actual.scheme != expected.scheme or actual.hostname != expected.hostname:
        raise SandboxClientError("wrong_sandbox_host")
    if (actual.path or "/") != (expected.path or "/"):
        raise SandboxClientError("wrong_sandbox_host")


def _assert_websocket_endpoint_allowed(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "wss" or parsed.hostname in (None, ""):
        raise SandboxClientError("websocket_endpoint_rejected")
    if parsed.scheme in ("http", "https", "ws"):
        raise SandboxClientError("websocket_endpoint_rejected")


def _request_evidence(method: str, url: str, response: HttpResponse, as_of: datetime) -> dict[str, Any]:
    parsed = urlparse(url)
    return {
        "method": method.upper(),
        "path": parsed.path,
        "host": parsed.hostname,
        "status_class": f"{int(response.status_code) // 100}xx",
        "timestamp": as_of.isoformat(),
        "redacted": True,
        "authorization_header_written": False,
        "request_body_written": False,
        "query_string_used": False,
        "response_body_written": False,
        "token_values_written": False,
    }


def _reject_bad_response(method: str, url: str, response: HttpResponse) -> None:
    _assert_same_approved_origin(url, response.url)
    status = int(response.status_code)
    if status == 400:
        raise SandboxClientError("bad_request")
    if status == 401:
        raise SandboxClientError("unauthorized")
    if status == 403:
        raise SandboxClientError("forbidden")
    if status == 429:
        raise SandboxClientError("rate_limit")
    if status >= 500:
        raise SandboxClientError("provider_server_error")
    if not 200 <= status < 300:
        raise SandboxClientError("malformed_payload")


def _oauth_token_payload(response: HttpResponse) -> dict[str, Any]:
    payload = _json_payload(response)
    return {key: payload[key] for key in ("access_token", "expires_in", "token_type", "scope") if key in payload}


def _json_payload(response: HttpResponse, *, malformed_reason: str = "malformed_payload") -> dict[str, Any]:
    try:
        payload = response.json()
    except Exception as exc:
        raise SandboxClientError(malformed_reason) from exc
    if not isinstance(payload, dict):
        raise SandboxClientError(malformed_reason)
    return payload


def _extract_accounts(payload: dict[str, Any]) -> tuple[str, ...]:
    candidates = payload.get("data", payload)
    if isinstance(candidates, dict):
        candidates = candidates.get("accounts", candidates.get("items", ()))
    if not isinstance(candidates, list):
        raise SandboxClientError("account_payload_malformed")
    account_ids: list[str] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        nested = item.get("account")
        account_id = ""
        if isinstance(nested, dict):
            account_id = nested.get("account-number") or nested.get("account_number") or nested.get("account_id") or nested.get("id") or ""
        account_id = account_id or item.get("account-number") or item.get("account_number") or item.get("account_id") or item.get("id")
        if isinstance(account_id, str) and account_id.strip():
            account_ids.append(account_id.strip())
    if not account_ids:
        raise SandboxClientError("account_payload_malformed")
    return tuple(account_ids)


def _quote_token_payload(payload: dict[str, Any]) -> dict[str, Any]:
    wrapped = payload.get("data", payload)
    if not isinstance(wrapped, dict):
        raise SandboxClientError("quote_token_payload_malformed")
    return wrapped


def _extract_customer_id(payload: dict[str, Any]) -> str:
    candidate = _first_string(payload, ("customer_id", "customer-id", "id"), default="")
    if candidate:
        return candidate
    data = payload.get("data")
    if isinstance(data, dict):
        candidate = _first_string(data, ("customer_id", "customer-id", "id"), default="")
    return candidate or "sandbox-customer-redacted"


def _provider_timestamp(payload: dict[str, Any], as_of: datetime) -> str:
    value = _first_string(payload, ("timestamp", "provider_timestamp", "time"), default="")
    return value or as_of.isoformat()


def _first_string(payload: dict[str, Any], keys: tuple[str, ...], default: str = "") -> str:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    data = payload.get("data")
    if isinstance(data, dict):
        for key in keys:
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return default


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
