from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


PHASE_ID = "13D"
MODULE_NAME = "Moonshot LEAPS Research Engine"
REQUIRED_LABELS = (RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED)


@dataclass(frozen=True)
class LeapsResearchConfig:
    min_leaps_dte: int = 180
    ideal_min_dte: int = 365
    min_abs_delta: float = 0.25
    max_abs_delta: float = 0.80
    min_open_interest: int = 100
    min_volume: int = 10
    max_bid_ask_spread_pct: float = 0.15
    max_premium_at_risk_pct: float = 0.03
    max_data_age_minutes: int = 30

    def validate(self) -> None:
        if self.min_leaps_dte <= 0:
            raise ValueError("min_leaps_dte must be positive")
        if self.ideal_min_dte < self.min_leaps_dte:
            raise ValueError("ideal_min_dte must be at least min_leaps_dte")
        if not 0.0 <= self.min_abs_delta <= self.max_abs_delta <= 1.0:
            raise ValueError("delta thresholds must be ordered between 0 and 1")
        if self.min_open_interest < 0:
            raise ValueError("min_open_interest cannot be negative")
        if self.min_volume < 0:
            raise ValueError("min_volume cannot be negative")
        if self.max_bid_ask_spread_pct < 0:
            raise ValueError("max_bid_ask_spread_pct cannot be negative")
        if self.max_premium_at_risk_pct <= 0:
            raise ValueError("max_premium_at_risk_pct must be positive")
        if self.max_data_age_minutes < 0:
            raise ValueError("max_data_age_minutes cannot be negative")


@dataclass(frozen=True)
class LeapsResearchInput:
    symbol: str
    contract_type: str
    strike: float
    underlying_price: float
    expiration: date
    as_of: date
    delta: float
    bid: float
    ask: float
    last: float
    open_interest: int
    volume: int
    premium_at_risk_pct: float
    data_age_minutes: int
    thesis: str
    catalyst: str
    risk: str
    monitoring: str
    invalidation: str
    research_label: str = HUMAN_REVIEW_REQUIRED

    def validate(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol is required")
        if self.contract_type.lower() not in {"call", "put"}:
            raise ValueError("contract_type must be call or put")
        if self.strike <= 0:
            raise ValueError("strike must be positive")
        if self.underlying_price <= 0:
            raise ValueError("underlying_price must be positive")
        if self.expiration < self.as_of:
            raise ValueError("expiration cannot be before as_of")
        if not -1.0 <= self.delta <= 1.0:
            raise ValueError("delta must be between -1 and 1")
        for field_name, value in (("bid", self.bid), ("ask", self.ask), ("last", self.last)):
            if value < 0:
                raise ValueError(f"{field_name} cannot be negative")
        if self.ask < self.bid:
            raise ValueError("ask cannot be below bid")
        if self.open_interest < 0:
            raise ValueError("open_interest cannot be negative")
        if self.volume < 0:
            raise ValueError("volume cannot be negative")
        if self.premium_at_risk_pct < 0:
            raise ValueError("premium_at_risk_pct cannot be negative")
        if self.data_age_minutes < 0:
            raise ValueError("data_age_minutes cannot be negative")
        for field_name, value in (
            ("thesis", self.thesis),
            ("catalyst", self.catalyst),
            ("risk", self.risk),
            ("monitoring", self.monitoring),
            ("invalidation", self.invalidation),
        ):
            if not value.strip():
                raise ValueError(f"{field_name} is required")
        if self.research_label not in REQUIRED_LABELS:
            raise ValueError("research_label must be a safe research label")


@dataclass(frozen=True)
class LeapsResearchMemo:
    candidate: LeapsResearchInput
    label: str
    monitor_allowed: bool
    dte: int
    expiration_bucket: str
    moneyness: str
    bid_ask_spread_pct: float
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
        "live_trading_enabled": False,
        "broker_order_routing_enabled": False,
        "broker_order_call_performed": False,
        "broker_order_submitted": False,
        "LIVE TRADING": "DISABLED",
    }


def build_leaps_research_memo(
    candidate: LeapsResearchInput,
    config: LeapsResearchConfig | None = None,
) -> LeapsResearchMemo:
    cfg = config or LeapsResearchConfig()
    cfg.validate()
    candidate.validate()

    dte = (candidate.expiration - candidate.as_of).days
    spread_pct = _bid_ask_spread_pct(candidate)
    warnings = tuple(_research_warnings(candidate, cfg, dte, spread_pct))
    return LeapsResearchMemo(
        candidate=candidate,
        label=RESEARCH_ONLY if not warnings else BLOCKED_BY_SAFETY_GATE,
        monitor_allowed=not warnings,
        dte=dte,
        expiration_bucket=_expiration_bucket(dte, cfg),
        moneyness=_moneyness(candidate),
        bid_ask_spread_pct=spread_pct,
        warnings=warnings,
        required_labels=REQUIRED_LABELS,
        safety=safety_manifest(),
    )


def build_leaps_payload(memo: LeapsResearchMemo) -> dict[str, Any]:
    candidate = memo.candidate
    return {
        "phase": PHASE_ID,
        "module": MODULE_NAME,
        "symbol": candidate.symbol,
        "contract_type": candidate.contract_type.lower(),
        "strike": candidate.strike,
        "underlying_price": candidate.underlying_price,
        "expiration": candidate.expiration.isoformat(),
        "as_of": candidate.as_of.isoformat(),
        "dte": memo.dte,
        "expiration_bucket": memo.expiration_bucket,
        "moneyness": memo.moneyness,
        "label": memo.label,
        "monitor_allowed": memo.monitor_allowed,
        "research": {
            "thesis": candidate.thesis,
            "catalyst": candidate.catalyst,
            "risk": candidate.risk,
            "monitoring": candidate.monitoring,
            "invalidation": candidate.invalidation,
            "label": candidate.research_label,
        },
        "delta": {
            "value": candidate.delta,
            "abs_delta": abs(candidate.delta),
        },
        "liquidity": {
            "bid": candidate.bid,
            "ask": candidate.ask,
            "last": candidate.last,
            "open_interest": candidate.open_interest,
            "volume": candidate.volume,
            "bid_ask_spread_pct": memo.bid_ask_spread_pct,
            "data_age_minutes": candidate.data_age_minutes,
        },
        "risk": {
            "premium_at_risk_pct": candidate.premium_at_risk_pct,
            "warnings": memo.warnings,
        },
        "monitoring": {
            "plan": candidate.monitoring,
            "required_labels": memo.required_labels,
            "human_review_required": True,
        },
        "safety": memo.safety,
    }


def render_markdown_memo(memo: LeapsResearchMemo) -> str:
    payload = build_leaps_payload(memo)
    lines = [
        f"# {PHASE_ID} {MODULE_NAME}",
        "",
        "Research labels: " + ", ".join(REQUIRED_LABELS),
        "LIVE TRADING: DISABLED",
        "",
        f"## {payload['symbol']} LEAPS Research",
        f"- label: {payload['label']}",
        f"- monitor_allowed: {payload['monitor_allowed']}",
        f"- contract_type: {payload['contract_type']}",
        f"- strike: {payload['strike']:.2f}",
        f"- expiration: {payload['expiration']}",
        f"- dte: {payload['dte']}",
        f"- expiration_bucket: {payload['expiration_bucket']}",
        f"- moneyness: {payload['moneyness']}",
        "",
        "## Thesis And Catalyst",
        f"- thesis: {payload['research']['thesis']}",
        f"- catalyst: {payload['research']['catalyst']}",
        f"- invalidation: {payload['research']['invalidation']}",
        "",
        "## Delta And Liquidity",
        f"- delta: {payload['delta']['value']}",
        f"- bid: {payload['liquidity']['bid']}",
        f"- ask: {payload['liquidity']['ask']}",
        f"- open_interest: {payload['liquidity']['open_interest']}",
        f"- volume: {payload['liquidity']['volume']}",
        f"- bid_ask_spread_pct: {payload['liquidity']['bid_ask_spread_pct']:.6f}",
        "",
        "## Risk And Monitoring",
        f"- risk: {payload['research']['risk']}",
        f"- premium_at_risk_pct: {payload['risk']['premium_at_risk_pct']}",
        f"- monitoring: {payload['monitoring']['plan']}",
    ]

    lines.extend(["", "## Warnings"])
    if payload["risk"]["warnings"]:
        for warning in payload["risk"]["warnings"]:
            lines.append(f"- {warning}")
    else:
        lines.append("- no_research_warnings")

    lines.extend(
        [
            "",
            "## Safety",
            "- Research-only LEAPS memo; no broker routing or order submission.",
            "- Trade-relevant output requires human review.",
        ]
    )
    return "\n".join(lines)


def _research_warnings(
    candidate: LeapsResearchInput,
    config: LeapsResearchConfig,
    dte: int,
    bid_ask_spread_pct: float,
) -> list[str]:
    warnings: list[str] = []
    abs_delta = abs(candidate.delta)
    if dte < config.min_leaps_dte:
        warnings.append("below_leaps_dte_threshold_research_only")
    elif dte < config.ideal_min_dte:
        warnings.append("below_ideal_leaps_duration_review")
    if abs_delta < config.min_abs_delta:
        warnings.append("delta_too_low_for_leaps_research_review")
    if abs_delta > config.max_abs_delta:
        warnings.append("delta_too_high_directional_risk_review")
    if candidate.open_interest < config.min_open_interest:
        warnings.append("open_interest_liquidity_warning")
    if candidate.volume < config.min_volume:
        warnings.append("volume_liquidity_warning")
    if bid_ask_spread_pct > config.max_bid_ask_spread_pct:
        warnings.append("wide_bid_ask_spread_warning")
    if candidate.premium_at_risk_pct > config.max_premium_at_risk_pct:
        warnings.append("premium_at_risk_cap_review")
    if candidate.data_age_minutes > config.max_data_age_minutes:
        warnings.append("stale_options_data")
    if candidate.research_label != HUMAN_REVIEW_REQUIRED:
        warnings.append("trade_relevant_research_should_remain_human_review_required")
    if warnings:
        warnings.append("HUMAN_REVIEW_REQUIRED")
    return warnings


def _expiration_bucket(dte: int, config: LeapsResearchConfig) -> str:
    if dte < config.min_leaps_dte:
        return "below_leaps_threshold"
    if dte < config.ideal_min_dte:
        return "leaps_minimum"
    return "long_duration_leaps"


def _moneyness(candidate: LeapsResearchInput) -> str:
    if candidate.contract_type.lower() == "call":
        if candidate.strike < candidate.underlying_price:
            return "in_the_money"
        if candidate.strike > candidate.underlying_price:
            return "out_of_the_money"
        return "at_the_money"

    if candidate.strike > candidate.underlying_price:
        return "in_the_money"
    if candidate.strike < candidate.underlying_price:
        return "out_of_the_money"
    return "at_the_money"


def _bid_ask_spread_pct(candidate: LeapsResearchInput) -> float:
    midpoint = (candidate.bid + candidate.ask) / 2.0
    if midpoint <= 0:
        return 0.0
    return (candidate.ask - candidate.bid) / midpoint
