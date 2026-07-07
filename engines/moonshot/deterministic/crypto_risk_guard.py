from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from risk.policies import BLOCKED_BY_SAFETY_GATE, HUMAN_REVIEW_REQUIRED, MONITOR_ONLY, PAPER_ONLY, RESEARCH_ONLY


PHASE_ID = "13C"
MODULE_NAME = "Moonshot Crypto Risk Guard"
REQUIRED_LABELS = (RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED)


@dataclass(frozen=True)
class CryptoRiskGuardConfig:
    max_account_drawdown_pct: float = 0.08
    max_daily_drawdown_pct: float = 0.03
    min_24h_quote_volume_usd: float = 25_000_000.0
    max_spread_pct: float = 0.01
    max_24h_realized_volatility_pct: float = 0.18
    max_7d_realized_volatility_pct: float = 0.45
    max_data_age_minutes: int = 15

    def validate(self) -> None:
        if self.max_account_drawdown_pct <= 0:
            raise ValueError("max_account_drawdown_pct must be positive")
        if self.max_daily_drawdown_pct <= 0:
            raise ValueError("max_daily_drawdown_pct must be positive")
        if self.min_24h_quote_volume_usd <= 0:
            raise ValueError("min_24h_quote_volume_usd must be positive")
        if self.max_spread_pct < 0:
            raise ValueError("max_spread_pct cannot be negative")
        if self.max_24h_realized_volatility_pct <= 0:
            raise ValueError("max_24h_realized_volatility_pct must be positive")
        if self.max_7d_realized_volatility_pct <= 0:
            raise ValueError("max_7d_realized_volatility_pct must be positive")
        if self.max_data_age_minutes < 0:
            raise ValueError("max_data_age_minutes cannot be negative")


@dataclass(frozen=True)
class CryptoRiskSnapshot:
    symbol: str
    account_drawdown_pct: float
    daily_drawdown_pct: float
    quote_volume_24h_usd: float
    bid_ask_spread_pct: float
    realized_volatility_24h_pct: float
    realized_volatility_7d_pct: float
    data_age_minutes: int
    thesis: str = "Crypto moonshot research monitor."

    def validate(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol is required")
        if not self.thesis.strip():
            raise ValueError("thesis is required")
        for field_name, value in (
            ("account_drawdown_pct", self.account_drawdown_pct),
            ("daily_drawdown_pct", self.daily_drawdown_pct),
            ("quote_volume_24h_usd", self.quote_volume_24h_usd),
            ("bid_ask_spread_pct", self.bid_ask_spread_pct),
            ("realized_volatility_24h_pct", self.realized_volatility_24h_pct),
            ("realized_volatility_7d_pct", self.realized_volatility_7d_pct),
        ):
            if value < 0:
                raise ValueError(f"{field_name} cannot be negative")
        if self.data_age_minutes < 0:
            raise ValueError("data_age_minutes cannot be negative")


@dataclass(frozen=True)
class CryptoRiskGuardResult:
    snapshot: CryptoRiskSnapshot
    label: str
    monitor_allowed: bool
    warnings: tuple[str, ...]
    required_labels: tuple[str, ...]
    safety: dict[str, Any]


def safety_manifest() -> dict[str, Any]:
    return {
        "phase": PHASE_ID,
        "module": MODULE_NAME,
        "labels": REQUIRED_LABELS,
        "research_only": True,
        "monitor_only": True,
        "paper_only": True,
        "human_review_required": True,
        "exchange_credentials_required": False,
        "exchange_order_routing_enabled": False,
        "live_trading_enabled": False,
        "broker_order_routing_enabled": False,
        "broker_order_call_performed": False,
        "broker_order_submitted": False,
        "LIVE TRADING": "DISABLED",
    }


def evaluate_crypto_risk_guard(
    snapshot: CryptoRiskSnapshot,
    config: CryptoRiskGuardConfig | None = None,
) -> CryptoRiskGuardResult:
    cfg = config or CryptoRiskGuardConfig()
    cfg.validate()
    snapshot.validate()

    warnings = tuple(_risk_warnings(snapshot, cfg))
    return CryptoRiskGuardResult(
        snapshot=snapshot,
        label=RESEARCH_ONLY if not warnings else BLOCKED_BY_SAFETY_GATE,
        monitor_allowed=not warnings,
        warnings=warnings,
        required_labels=REQUIRED_LABELS,
        safety=safety_manifest(),
    )


def build_guard_payload(result: CryptoRiskGuardResult) -> dict[str, Any]:
    snapshot = result.snapshot
    return {
        "phase": PHASE_ID,
        "module": MODULE_NAME,
        "symbol": snapshot.symbol,
        "thesis": snapshot.thesis,
        "label": result.label,
        "monitor_allowed": result.monitor_allowed,
        "warnings": result.warnings,
        "required_labels": result.required_labels,
        "metrics": {
            "account_drawdown_pct": snapshot.account_drawdown_pct,
            "daily_drawdown_pct": snapshot.daily_drawdown_pct,
            "quote_volume_24h_usd": snapshot.quote_volume_24h_usd,
            "bid_ask_spread_pct": snapshot.bid_ask_spread_pct,
            "realized_volatility_24h_pct": snapshot.realized_volatility_24h_pct,
            "realized_volatility_7d_pct": snapshot.realized_volatility_7d_pct,
            "data_age_minutes": snapshot.data_age_minutes,
        },
        "safety": result.safety,
    }


def render_markdown_guard(result: CryptoRiskGuardResult) -> str:
    payload = build_guard_payload(result)
    lines = [
        f"# {PHASE_ID} {MODULE_NAME}",
        "",
        "Research labels: " + ", ".join(REQUIRED_LABELS),
        "LIVE TRADING: DISABLED",
        "",
        f"## {payload['symbol']} Crypto Monitor",
        f"- label: {payload['label']}",
        f"- monitor_allowed: {payload['monitor_allowed']}",
        f"- thesis: {payload['thesis']}",
        "",
        "## Risk Metrics",
    ]
    for name, value in payload["metrics"].items():
        lines.append(f"- {name}: {value}")

    lines.extend(["", "## Warnings"])
    if payload["warnings"]:
        for warning in payload["warnings"]:
            lines.append(f"- {warning}")
    else:
        lines.append("- no_guard_warnings")

    lines.extend(
        [
            "",
            "## Safety",
            "- Research-only crypto risk guard; no exchange credentials or order routing.",
            "- Trade-relevant output requires human review.",
        ]
    )
    return "\n".join(lines)


def _risk_warnings(
    snapshot: CryptoRiskSnapshot,
    config: CryptoRiskGuardConfig,
) -> list[str]:
    warnings: list[str] = []
    if snapshot.account_drawdown_pct > config.max_account_drawdown_pct:
        warnings.append("account_drawdown_cap_breach")
    if snapshot.daily_drawdown_pct > config.max_daily_drawdown_pct:
        warnings.append("daily_drawdown_cap_breach")
    if snapshot.quote_volume_24h_usd < config.min_24h_quote_volume_usd:
        warnings.append("liquidity_volume_warning")
    if snapshot.bid_ask_spread_pct > config.max_spread_pct:
        warnings.append("liquidity_spread_warning")
    if snapshot.realized_volatility_24h_pct > config.max_24h_realized_volatility_pct:
        warnings.append("volatility_24h_filter_breach")
    if snapshot.realized_volatility_7d_pct > config.max_7d_realized_volatility_pct:
        warnings.append("volatility_7d_filter_breach")
    if snapshot.data_age_minutes > config.max_data_age_minutes:
        warnings.append("stale_crypto_market_data")
    if warnings:
        warnings.append("HUMAN_REVIEW_REQUIRED")
    return warnings
