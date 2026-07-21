from __future__ import annotations

from ui_service.constants import READ_ENDPOINTS

SHELL_SCHEMA_VERSION = "ui02.desktop_shell.v1"
LIVE_TRADING_STATUS = "LIVE TRADING: DISABLED"
HOST = "127.0.0.1"
MAX_REQUEST_BODY_BYTES = 1024
MAX_HEADER_VALUE_BYTES = 2048

APPROVED_PROXY_ENDPOINTS = frozenset(f"/api/v1/{endpoint}" for endpoint in READ_ENDPOINTS)
APPROVED_PROXY_ENDPOINTS = APPROVED_PROXY_ENDPOINTS | frozenset({"/api/v1/version", "/api/v1/events"})
APPROVED_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
MUTATION_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE", "CONNECT", "TRACE"})

ROUTES = (
    ("overview", "Overview", "health"),
    ("research", "Research", "research"),
    ("screener", "Screener", "screener"),
    ("opportunities", "Opportunities", "opportunities"),
    ("analyst-theses", "Analyst Theses", "analyst-theses"),
    ("market-regime", "Market Regime", "market-regime"),
    ("lifecycle", "Lifecycle", "lifecycle"),
    ("risk-gate", "Risk Gate", "risk-gate"),
    ("portfolio", "Portfolio", "portfolio"),
    ("alerts", "Alerts", "alerts"),
    ("models", "Models", "models"),
    ("performance", "Performance", "performance"),
    ("backtests", "Backtests", "backtests"),
    ("paper-activity", "Paper Activity", "paper-activity"),
    ("options", "Options", "options"),
    ("moonshot-research", "Moonshot Research", "moonshot-research"),
)

CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "img-src 'self' data:; "
    "font-src 'none'; "
    "connect-src 'self'; "
    "object-src 'none'; "
    "base-uri 'none'; "
    "form-action 'none'; "
    "frame-ancestors 'none'; "
    "worker-src 'none'; "
    "manifest-src 'none'; "
    "upgrade-insecure-requests"
)
