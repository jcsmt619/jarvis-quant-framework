from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from risk.policies import HUMAN_REVIEW_REQUIRED, MONITOR_ONLY, PAPER_ONLY, RESEARCH_ONLY


PHASE_ID = "13B"
MODULE_NAME = "Moonshot Options Research"
REQUIRED_LABELS = (RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED)


@dataclass(frozen=True)
class OptionThesis:
    symbol: str
    contract_type: str
    strike: float
    underlying_price: float
    expiration: date
    as_of: date
    thesis: str
    catalyst: str
    invalidation: str
    target_note: str
    stop_note: str
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
        for field_name, value in (
            ("thesis", self.thesis),
            ("catalyst", self.catalyst),
            ("invalidation", self.invalidation),
            ("target_note", self.target_note),
            ("stop_note", self.stop_note),
        ):
            if not value.strip():
                raise ValueError(f"{field_name} is required")
        if self.research_label not in REQUIRED_LABELS:
            raise ValueError("research_label must be a safe research label")


@dataclass(frozen=True)
class GreeksSnapshot:
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float = 0.0
    implied_volatility: float | None = None

    def validate(self) -> None:
        if not -1.0 <= self.delta <= 1.0:
            raise ValueError("delta must be between -1 and 1")
        if self.gamma < 0:
            raise ValueError("gamma cannot be negative")
        if self.vega < 0:
            raise ValueError("vega cannot be negative")
        if self.implied_volatility is not None and self.implied_volatility < 0:
            raise ValueError("implied_volatility cannot be negative")


@dataclass(frozen=True)
class OptionsResearchConfig:
    min_leaps_dte: int = 180
    near_expiration_dte: int = 45
    high_abs_delta: float = 0.75
    high_gamma: float = 0.08
    high_daily_theta_loss_pct: float = 0.02
    high_vega: float = 0.20

    def validate(self) -> None:
        if self.min_leaps_dte <= 0:
            raise ValueError("min_leaps_dte must be positive")
        if self.near_expiration_dte <= 0:
            raise ValueError("near_expiration_dte must be positive")
        if self.near_expiration_dte >= self.min_leaps_dte:
            raise ValueError("near_expiration_dte must be below min_leaps_dte")
        if not 0.0 < self.high_abs_delta <= 1.0:
            raise ValueError("high_abs_delta must be between 0 and 1")
        if self.high_gamma < 0:
            raise ValueError("high_gamma cannot be negative")
        if self.high_daily_theta_loss_pct < 0:
            raise ValueError("high_daily_theta_loss_pct cannot be negative")
        if self.high_vega < 0:
            raise ValueError("high_vega cannot be negative")


@dataclass(frozen=True)
class OptionsResearchMemo:
    thesis: OptionThesis
    greeks: GreeksSnapshot
    dte: int
    expiration_bucket: str
    moneyness: str
    risk_notes: tuple[str, ...]
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


def build_options_research_memo(
    thesis: OptionThesis,
    greeks: GreeksSnapshot,
    config: OptionsResearchConfig | None = None,
) -> OptionsResearchMemo:
    cfg = config or OptionsResearchConfig()
    cfg.validate()
    thesis.validate()
    greeks.validate()

    dte = (thesis.expiration - thesis.as_of).days
    expiration_bucket = _expiration_bucket(dte, cfg)
    moneyness = _moneyness(thesis)
    risk_notes = tuple(
        _expiration_notes(dte, expiration_bucket, cfg)
        + _greeks_risk_notes(greeks, cfg)
        + _thesis_risk_notes(thesis)
    )

    return OptionsResearchMemo(
        thesis=thesis,
        greeks=greeks,
        dte=dte,
        expiration_bucket=expiration_bucket,
        moneyness=moneyness,
        risk_notes=risk_notes,
        required_labels=REQUIRED_LABELS,
        safety=safety_manifest(),
    )


def memo_payload(memo: OptionsResearchMemo) -> dict[str, Any]:
    thesis = memo.thesis
    greeks = memo.greeks
    return {
        "phase": PHASE_ID,
        "module": MODULE_NAME,
        "symbol": thesis.symbol,
        "contract_type": thesis.contract_type.lower(),
        "strike": thesis.strike,
        "underlying_price": thesis.underlying_price,
        "expiration": thesis.expiration.isoformat(),
        "as_of": thesis.as_of.isoformat(),
        "dte": memo.dte,
        "expiration_bucket": memo.expiration_bucket,
        "moneyness": memo.moneyness,
        "thesis": {
            "summary": thesis.thesis,
            "catalyst": thesis.catalyst,
            "invalidation": thesis.invalidation,
            "target_note": thesis.target_note,
            "stop_note": thesis.stop_note,
            "label": thesis.research_label,
        },
        "greeks": {
            "delta": greeks.delta,
            "gamma": greeks.gamma,
            "theta": greeks.theta,
            "vega": greeks.vega,
            "rho": greeks.rho,
            "implied_volatility": greeks.implied_volatility,
        },
        "risk_notes": memo.risk_notes,
        "required_labels": memo.required_labels,
        "safety": memo.safety,
    }


def render_markdown_memo(memo: OptionsResearchMemo) -> str:
    payload = memo_payload(memo)
    lines = [
        f"# {PHASE_ID} {MODULE_NAME}",
        "",
        "Research labels: " + ", ".join(REQUIRED_LABELS),
        "LIVE TRADING: DISABLED",
        "",
        f"## {payload['symbol']} Option Thesis",
        f"- contract_type: {payload['contract_type']}",
        f"- strike: {payload['strike']:.2f}",
        f"- underlying_price: {payload['underlying_price']:.2f}",
        f"- expiration: {payload['expiration']}",
        f"- dte: {payload['dte']}",
        f"- expiration_bucket: {payload['expiration_bucket']}",
        f"- moneyness: {payload['moneyness']}",
        f"- label: {payload['thesis']['label']}",
        "",
        "## Thesis Structure",
        f"- thesis: {payload['thesis']['summary']}",
        f"- catalyst: {payload['thesis']['catalyst']}",
        f"- invalidation: {payload['thesis']['invalidation']}",
        f"- target_note: {payload['thesis']['target_note']}",
        f"- stop_note: {payload['thesis']['stop_note']}",
        "",
        "## Greeks",
    ]
    for name, value in payload["greeks"].items():
        lines.append(f"- {name}: {value}")

    lines.extend(["", "## Risk Notes"])
    for note in payload["risk_notes"]:
        lines.append(f"- {note}")

    lines.extend(
        [
            "",
            "## Safety",
            "- Research memo only; no broker routing or order submission.",
            "- Trade-relevant conclusions require human review.",
        ]
    )
    return "\n".join(lines)


def _expiration_bucket(dte: int, config: OptionsResearchConfig) -> str:
    if dte <= config.near_expiration_dte:
        return "near_expiration"
    if dte < config.min_leaps_dte:
        return "intermediate"
    return "leaps"


def _moneyness(thesis: OptionThesis) -> str:
    if thesis.contract_type.lower() == "call":
        if thesis.strike < thesis.underlying_price:
            return "in_the_money"
        if thesis.strike > thesis.underlying_price:
            return "out_of_the_money"
        return "at_the_money"

    if thesis.strike > thesis.underlying_price:
        return "in_the_money"
    if thesis.strike < thesis.underlying_price:
        return "out_of_the_money"
    return "at_the_money"


def _expiration_notes(
    dte: int,
    expiration_bucket: str,
    config: OptionsResearchConfig,
) -> list[str]:
    notes = [f"expiration_bucket={expiration_bucket}; dte={dte}"]
    if expiration_bucket == "near_expiration":
        notes.append("near_expiration_theta_and_gamma_risk_requires_human_review")
    elif dte < config.min_leaps_dte:
        notes.append("below_leaps_dte_threshold_research_only")
    return notes


def _greeks_risk_notes(
    greeks: GreeksSnapshot,
    config: OptionsResearchConfig,
) -> list[str]:
    notes: list[str] = []
    if abs(greeks.delta) >= config.high_abs_delta:
        notes.append("high_delta_underlying_direction_risk")
    if greeks.gamma >= config.high_gamma:
        notes.append("high_gamma_convexity_risk")
    if abs(greeks.theta) >= config.high_daily_theta_loss_pct:
        notes.append("theta_decay_risk")
    if greeks.vega >= config.high_vega:
        notes.append("high_vega_iv_crush_risk")
    if greeks.implied_volatility is not None:
        notes.append("implied_volatility_context_required")
    return notes


def _thesis_risk_notes(thesis: OptionThesis) -> list[str]:
    notes = ["HUMAN_REVIEW_REQUIRED"]
    if thesis.research_label != HUMAN_REVIEW_REQUIRED:
        notes.append("trade_relevant_research_should_remain_human_review_required")
    return notes
