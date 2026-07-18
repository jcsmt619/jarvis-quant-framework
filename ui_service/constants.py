from __future__ import annotations

SCHEMA_VERSION = "ui01.local_service.v1"
EVENT_SCHEMA_VERSION = "ui01.event.v1"
LIVE_TRADING_STATUS = "LIVE TRADING: DISABLED"
PROVIDER_VALIDATION_PENDING = "pending"
SAFETY_STATE = {
    "labels": [
        "RESEARCH_ONLY",
        "MONITOR_ONLY",
        "PAPER_ONLY",
        "HUMAN_REVIEW_REQUIRED",
        "BLOCKED_BY_SAFETY_GATE",
    ],
    "live_trading_enabled": False,
    "broker_order_call_performed": False,
    "broker_order_submitted": False,
    "broker_order_routing_enabled": False,
    "real_paper_wrapper_connected": False,
    "real_paper_wrapper_attempted": False,
    "real_paper_order_submitted": False,
    "external_network_call_attempted": False,
    "credential_loading_attempted": False,
    "secret_request_attempted": False,
    "is_live": False,
    "LIVE TRADING": "DISABLED",
    "live_trading_status": LIVE_TRADING_STATUS,
}

READ_ENDPOINTS = {
    "health": "system_health",
    "safety": "safety",
    "data-status": "data_status",
    "research": "research",
    "screener": "screener",
    "opportunities": "opportunities",
    "analyst-theses": "analyst_theses",
    "market-regime": "market_regime",
    "lifecycle": "lifecycle",
    "risk-gate": "risk_gate",
    "portfolio": "portfolio",
    "alerts": "alerts",
    "models": "models",
    "performance": "performance_analytics",
    "backtests": "backtests",
    "paper-activity": "paper_activity",
    "options": "options",
    "moonshot-research": "moonshot_research",
}

PUBLIC_ENDPOINTS = {"/api/v1/health", "/api/v1/version"}
ALLOWED_METHODS = {"GET", "HEAD", "OPTIONS"}
MUTATION_METHODS = {"POST", "PUT", "PATCH", "DELETE", "CONNECT", "TRACE"}
SOURCE_MODES = {"fixture", "recorded_response", "live_provider"}

FORBIDDEN_IMPORT_PREFIXES = (
    "keyring",
    "win32cred",
    "broker.",
    "paper_trading.paper_executor",
    "paper_trading.execution_gate",
    "paper_trading.order_intent",
    "automation.orchestrator_real_paper_wrapper_connector",
    "execution.",
)

SECRET_FIELD_MARKERS = (
    "api_key",
    "apikey",
    "oauth",
    "token",
    "password",
    "private_key",
    "secret",
    "credential",
    "account_number",
    "account_id",
    "customer_id",
)

MAX_JSON_BYTES = 32_768
MAX_EVENT_BYTES = 8_192
MAX_CORRELATION_ID_BYTES = 96
MAX_REQUEST_BODY_BYTES = 1_024
MAX_HEADER_VALUE_BYTES = 2_048
