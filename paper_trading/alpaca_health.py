"""Alpaca paper connection health checks.

Phase 3A-2 safety layer only.

This module can validate paper account connectivity through a safe interface.
It does not submit orders.
It does not implement broker execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from paper_trading.alpaca_config import (
    AlpacaConfigError,
    AlpacaPaperConfig,
    validate_alpaca_paper_config,
)


class AlpacaHealthCheckError(RuntimeError):
    """Raised when Alpaca paper health check cannot be completed safely."""


@dataclass(frozen=True)
class AlpacaPaperHealthResult:
    """Safe paper-connection health result with no secrets."""

    ok: bool
    message: str
    account_status: str | None = None
    trading_blocked: bool | None = None
    account_blocked: bool | None = None


def _load_alpaca_rest_class() -> Any:
    """Load Alpaca REST class lazily so tests do not require live credentials."""
    try:
        import alpaca_trade_api as tradeapi
    except ImportError as exc:
        raise AlpacaHealthCheckError(
            "alpaca_trade_api is not installed. Install it before running "
            "paper connection health checks."
        ) from exc

    try:
        return tradeapi.REST
    except AttributeError as exc:
        raise AlpacaHealthCheckError(
            "alpaca_trade_api.REST is unavailable in the installed SDK."
        ) from exc


def create_alpaca_paper_client(
    config: AlpacaPaperConfig,
    client_factory: Callable[..., Any] | None = None,
) -> Any:
    """Create a paper Alpaca client after validating paper-only config.

    This function creates a client object only. It does not submit orders.
    Tests should pass a mock client_factory and never require real credentials.
    """
    safe_config = validate_alpaca_paper_config(config)
    factory = client_factory or _load_alpaca_rest_class()

    return factory(
        key_id=safe_config.api_key,
        secret_key=safe_config.secret_key,
        base_url=safe_config.base_url,
    )


def check_alpaca_paper_connection(
    config: AlpacaPaperConfig,
    client_factory: Callable[..., Any] | None = None,
) -> AlpacaPaperHealthResult:
    """Check Alpaca paper account health through a safe read-only call.

    The only client call allowed here is get_account().
    This function must not submit orders.
    """
    try:
        client = create_alpaca_paper_client(config, client_factory=client_factory)
        account = client.get_account()
    except (AlpacaConfigError, AlpacaHealthCheckError):
        raise
    except Exception as exc:  # pragma: no cover - defensive wrapper
        return AlpacaPaperHealthResult(
            ok=False,
            message=f"Alpaca paper health check failed: {exc}",
        )

    status = getattr(account, "status", None)
    trading_blocked = bool(getattr(account, "trading_blocked", False))
    account_blocked = bool(getattr(account, "account_blocked", False))

    ok = status == "ACTIVE" and not trading_blocked and not account_blocked

    if ok:
        message = "Alpaca paper account health check passed."
    else:
        message = "Alpaca paper account health check did not pass."

    return AlpacaPaperHealthResult(
        ok=ok,
        message=message,
        account_status=status,
        trading_blocked=trading_blocked,
        account_blocked=account_blocked,
    )
