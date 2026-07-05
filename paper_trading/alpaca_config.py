"""Alpaca paper-mode configuration validation.

Phase 3A-1 safety layer only.

This module does not connect to Alpaca.
This module does not submit orders.
This module does not implement broker execution.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Mapping
from urllib.parse import urlparse


PAPER_ALPACA_HOST = "paper-api.alpaca.markets"
LIVE_ALPACA_HOSTS = {
    "api.alpaca.markets",
}


class AlpacaConfigError(ValueError):
    """Raised when Alpaca paper configuration is missing or unsafe."""


@dataclass(frozen=True)
class AlpacaPaperConfig:
    """Validated Alpaca paper-only configuration.

    API credentials are excluded from repr to reduce accidental key exposure
    in logs, exceptions, screenshots, and debugging output.
    """

    api_key: str = field(repr=False)
    secret_key: str = field(repr=False)
    base_url: str
    paper_only: bool
    confirm_live: bool

    def redacted_summary(self) -> dict[str, object]:
        """Return a safe summary that never includes secret values."""
        return {
            "api_key_present": bool(self.api_key),
            "secret_key_present": bool(self.secret_key),
            "base_url": self.base_url,
            "paper_only": self.paper_only,
            "confirm_live": self.confirm_live,
        }


def _require_non_empty(value: str | None, name: str) -> str:
    if value is None or not value.strip():
        raise AlpacaConfigError(f"{name} is required and cannot be empty.")
    return value.strip()


def _parse_bool(value: str | None, name: str) -> bool:
    raw = _require_non_empty(value, name).lower()
    if raw == "true":
        return True
    if raw == "false":
        return False
    raise AlpacaConfigError(f"{name} must be exactly 'true' or 'false'.")


def is_paper_endpoint(base_url: str) -> bool:
    """Return True only for the Alpaca paper trading endpoint."""
    parsed = urlparse(base_url)
    return parsed.scheme == "https" and parsed.hostname == PAPER_ALPACA_HOST


def is_live_endpoint(base_url: str) -> bool:
    """Return True for known Alpaca live endpoints."""
    parsed = urlparse(base_url)
    return parsed.hostname in LIVE_ALPACA_HOSTS


def validate_alpaca_paper_config(config: AlpacaPaperConfig) -> AlpacaPaperConfig:
    """Validate that config is safe for Alpaca paper mode only."""
    _require_non_empty(config.api_key, "ALPACA_API_KEY")
    _require_non_empty(config.secret_key, "ALPACA_SECRET_KEY")
    _require_non_empty(config.base_url, "ALPACA_BASE_URL")

    if not config.paper_only:
        raise AlpacaConfigError("ALPACA_PAPER_ONLY must be true.")

    if config.confirm_live:
        raise AlpacaConfigError("ALPACA_CONFIRM_LIVE must be false for paper mode.")

    if is_live_endpoint(config.base_url):
        raise AlpacaConfigError("Live Alpaca endpoint is not allowed.")

    if not is_paper_endpoint(config.base_url):
        raise AlpacaConfigError(
            "ALPACA_BASE_URL must be the Alpaca paper endpoint only."
        )

    return config


def load_alpaca_paper_config(
    env: Mapping[str, str] | None = None,
) -> AlpacaPaperConfig:
    """Load and validate Alpaca paper config from environment variables."""
    source = os.environ if env is None else env

    config = AlpacaPaperConfig(
        api_key=_require_non_empty(source.get("ALPACA_API_KEY"), "ALPACA_API_KEY"),
        secret_key=_require_non_empty(
            source.get("ALPACA_SECRET_KEY"), "ALPACA_SECRET_KEY"
        ),
        base_url=_require_non_empty(source.get("ALPACA_BASE_URL"), "ALPACA_BASE_URL"),
        paper_only=_parse_bool(source.get("ALPACA_PAPER_ONLY"), "ALPACA_PAPER_ONLY"),
        confirm_live=_parse_bool(
            source.get("ALPACA_CONFIRM_LIVE"), "ALPACA_CONFIRM_LIVE"
        ),
    )

    return validate_alpaca_paper_config(config)
