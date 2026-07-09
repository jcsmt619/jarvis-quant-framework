from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from engines.moonshot.deterministic.options_chain_quality_scanner import (
    DEFAULT_FIXTURE_PATH as DEFAULT_CHAIN_QUALITY_FIXTURE_PATH,
)
from engines.moonshot.deterministic.options_chain_quality_scanner import (
    OptionChainQualityInput,
    OptionContractQualityInput,
    load_options_chain_quality_inputs,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


PHASE_ID = "BR-04"
MODULE_NAME = "Greeks IV Spread DTE Scoring"
REQUIRED_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
SAFE_ACTION_LABELS = REQUIRED_LABELS
DEFAULT_FIXTURE_PATH = DEFAULT_CHAIN_QUALITY_FIXTURE_PATH
DEFAULT_REPORT_DIR = Path("reports/br04_options_contract_scoring")


@dataclass(frozen=True)
class ContractScoringConfig:
    target_delta_min: float = 0.35
    target_delta_max: float = 0.65
    acceptable_delta_min: float = 0.25
    acceptable_delta_max: float = 0.75
    ideal_theta_abs_max: float = 0.030
    acceptable_theta_abs_max: float = 0.060
    ideal_vega_min: float = 0.30
    acceptable_vega_min: float = 0.15
    ideal_iv_min: float = 0.20
    ideal_iv_max: float = 0.65
    acceptable_iv_min: float = 0.05
    acceptable_iv_max: float = 1.20
    ideal_spread_pct_max: float = 0.03
    acceptable_spread_pct_max: float = 0.08
    ideal_dte_min: int = 360
    ideal_dte_max: int = 760
    acceptable_dte_min: int = 180
    acceptable_dte_max: int = 900
    min_volume: int = 25
    min_open_interest: int = 250
    ideal_volume: int = 100
    ideal_open_interest: int = 1000
    ideal_strike_to_underlying_min: float = 0.85
    ideal_strike_to_underlying_max: float = 1.50
    acceptable_strike_to_underlying_min: float = 0.70
    acceptable_strike_to_underlying_max: float = 1.80
    min_component_score: int = 50
    min_total_score: int = 75

    def validate(self) -> None:
        _require_range("target_delta", self.target_delta_min, self.target_delta_max, -1.0, 1.0)
        _require_range("acceptable_delta", self.acceptable_delta_min, self.acceptable_delta_max, -1.0, 1.0)
        if self.acceptable_delta_min > self.target_delta_min:
            raise ValueError("acceptable_delta_min cannot be above target_delta_min")
        if self.acceptable_delta_max < self.target_delta_max:
            raise ValueError("acceptable_delta_max cannot be below target_delta_max")
        _require_positive("ideal_theta_abs_max", self.ideal_theta_abs_max)
        if self.acceptable_theta_abs_max < self.ideal_theta_abs_max:
            raise ValueError("acceptable_theta_abs_max cannot be below ideal_theta_abs_max")
        _require_positive("ideal_vega_min", self.ideal_vega_min)
        _require_positive("acceptable_vega_min", self.acceptable_vega_min)
        if self.acceptable_vega_min > self.ideal_vega_min:
            raise ValueError("acceptable_vega_min cannot be above ideal_vega_min")
        _require_range("ideal_iv", self.ideal_iv_min, self.ideal_iv_max, 0.0, 10.0)
        _require_range("acceptable_iv", self.acceptable_iv_min, self.acceptable_iv_max, 0.0, 10.0)
        if self.acceptable_iv_min > self.ideal_iv_min:
            raise ValueError("acceptable_iv_min cannot be above ideal_iv_min")
        if self.acceptable_iv_max < self.ideal_iv_max:
            raise ValueError("acceptable_iv_max cannot be below ideal_iv_max")
        _require_positive("ideal_spread_pct_max", self.ideal_spread_pct_max)
        if self.acceptable_spread_pct_max < self.ideal_spread_pct_max:
            raise ValueError("acceptable_spread_pct_max cannot be below ideal_spread_pct_max")
        _require_int_range("ideal_dte", self.ideal_dte_min, self.ideal_dte_max, 0)
        _require_int_range("acceptable_dte", self.acceptable_dte_min, self.acceptable_dte_max, 0)
        if self.acceptable_dte_min > self.ideal_dte_min:
            raise ValueError("acceptable_dte_min cannot be above ideal_dte_min")
        if self.acceptable_dte_max < self.ideal_dte_max:
            raise ValueError("acceptable_dte_max cannot be below ideal_dte_max")
        for field_name, value in (
            ("min_volume", self.min_volume),
            ("min_open_interest", self.min_open_interest),
            ("ideal_volume", self.ideal_volume),
            ("ideal_open_interest", self.ideal_open_interest),
        ):
            if value < 0:
                raise ValueError(f"{field_name} cannot be negative")
        _require_range(
            "ideal_strike_to_underlying",
            self.ideal_strike_to_underlying_min,
            self.ideal_strike_to_underlying_max,
            0.0,
            10.0,
        )
        _require_range(
            "acceptable_strike_to_underlying",
            self.acceptable_strike_to_underlying_min,
            self.acceptable_strike_to_underlying_max,
            0.0,
            10.0,
        )
        if self.acceptable_strike_to_underlying_min > self.ideal_strike_to_underlying_min:
            raise ValueError("acceptable_strike_to_underlying_min cannot be above ideal minimum")
        if self.acceptable_strike_to_underlying_max < self.ideal_strike_to_underlying_max:
            raise ValueError("acceptable_strike_to_underlying_max cannot be below ideal maximum")
        _require_score("min_component_score", self.min_component_score)
        _require_score("min_total_score", self.min_total_score)


@dataclass(frozen=True)
class ComponentScore:
    name: str
    score: int
    weight: int
    passed: bool
    reason: str

    def validate(self) -> None:
        _require_text("name", self.name)
        _require_score("score", self.score)
        if self.weight <= 0:
            raise ValueError("component weight must be positive")
        _require_text("reason", self.reason)


@dataclass(frozen=True)
class ContractScoreDecision:
    contract: OptionContractQualityInput
    underlying_price: float
    evaluated_as_of: datetime
    total_score: int
    component_scores: tuple[ComponentScore, ...]
    suitable: bool
    label: str
    reasons: tuple[str, ...]
    human_review_required: bool = True

    def validate(self) -> None:
        self.contract.validate()
        _require_positive("underlying_price", self.underlying_price)
        _require_score("total_score", self.total_score)
        if not self.component_scores:
            raise ValueError("contract score requires component scores")
        for component in self.component_scores:
            component.validate()
        _require_safe_label(self.label)
        if self.suitable and self.label != MONITOR_ONLY:
            raise ValueError("suitable contract scores must remain monitor-only")
        if not self.suitable and self.label != BLOCKED_BY_SAFETY_GATE:
            raise ValueError("unsuitable contract scores must be blocked by safety gate")
        if not self.human_review_required:
            raise ValueError("contract score decisions must require human review")


@dataclass(frozen=True)
class ContractScoringReport:
    as_of: datetime
    config: ContractScoringConfig
    decisions: tuple[ContractScoreDecision, ...]
    safety: dict[str, Any]
    label: str = BLOCKED_BY_SAFETY_GATE

    @property
    def suitable_contracts(self) -> tuple[ContractScoreDecision, ...]:
        return tuple(decision for decision in self.decisions if decision.suitable)

    @property
    def blocked_contracts(self) -> tuple[ContractScoreDecision, ...]:
        return tuple(decision for decision in self.decisions if not decision.suitable)

    def validate(self) -> None:
        self.config.validate()
        if not self.decisions:
            raise ValueError("contract scoring report requires at least one decision")
        for decision in self.decisions:
            decision.validate()
        _require_safe_label(self.label)
        if self.label != BLOCKED_BY_SAFETY_GATE:
            raise ValueError("contract scoring report must remain blocked by safety gate")


def safety_manifest() -> dict[str, Any]:
    return {
        "phase": PHASE_ID,
        "module": MODULE_NAME,
        "labels": REQUIRED_LABELS,
        "research_only": True,
        "monitor_only": True,
        "paper_only": True,
        "human_review_required": True,
        "blocked_by_safety_gate": True,
        "real_paper_wrapper_connected": False,
        "real_paper_wrapper_attempted": False,
        "real_paper_order_submitted": False,
        "broker_order_call_performed": False,
        "broker_order_submitted": False,
        "broker_order_routing_enabled": False,
        "live_trading_enabled": False,
        "LIVE TRADING": "DISABLED",
    }


def load_contract_scoring_inputs(
    path: Path = DEFAULT_FIXTURE_PATH,
) -> tuple[OptionChainQualityInput, ...]:
    return load_options_chain_quality_inputs(path)


def build_contract_scoring_report(
    chains: tuple[OptionChainQualityInput, ...] | list[OptionChainQualityInput],
    config: ContractScoringConfig | None = None,
    as_of: datetime | None = None,
) -> ContractScoringReport:
    cfg = config or ContractScoringConfig()
    cfg.validate()
    if not chains:
        raise ValueError("contract scoring requires at least one chain")
    validated = tuple(chains)
    for chain in validated:
        chain.validate()
    report_as_of = as_of or max(chain.as_of for chain in validated)
    decisions = tuple(
        _score_contract(contract, chain.underlying_price, cfg, report_as_of)
        for chain in sorted(validated, key=lambda item: item.underlying_symbol)
        for contract in sorted(chain.contracts, key=lambda item: (item.underlying_symbol, item.expiration, item.strike))
    )
    report = ContractScoringReport(
        as_of=report_as_of,
        config=cfg,
        decisions=decisions,
        safety=safety_manifest(),
    )
    report.validate()
    return report


def load_contract_scoring_report(
    path: Path = DEFAULT_FIXTURE_PATH,
    config: ContractScoringConfig | None = None,
) -> ContractScoringReport:
    return build_contract_scoring_report(load_contract_scoring_inputs(path), config=config)


def contract_scoring_payload(report: ContractScoringReport) -> dict[str, Any]:
    report.validate()
    suitable = sorted(report.suitable_contracts, key=lambda item: (-item.total_score, item.contract.contract_id))
    blocked = sorted(report.blocked_contracts, key=lambda item: item.contract.contract_id)
    return {
        "phase": PHASE_ID,
        "module": MODULE_NAME,
        "as_of": report.as_of.isoformat(),
        "label": report.label,
        "safety": report.safety,
        "config": _config_payload(report.config),
        "metrics": {
            "contract_count": len(report.decisions),
            "suitable_contract_count": len(suitable),
            "blocked_contract_count": len(blocked),
            "human_review_required_count": len(report.decisions),
        },
        "suitable_contracts": [_decision_payload(decision) for decision in suitable],
        "blocked_contracts": [_decision_payload(decision) for decision in blocked],
    }


def render_markdown_contract_scoring(report: ContractScoringReport) -> str:
    payload = contract_scoring_payload(report)
    lines = [
        f"# {PHASE_ID} {MODULE_NAME}",
        "",
        "Research labels: " + ", ".join(REQUIRED_LABELS),
        "LIVE TRADING: DISABLED",
        "",
        "## Metrics",
    ]
    for name, value in payload["metrics"].items():
        lines.append(f"- {name}: {value}")

    lines.extend(["", "## Suitable Contracts"])
    if payload["suitable_contracts"]:
        for decision in payload["suitable_contracts"]:
            lines.append(
                "- "
                + decision["contract_id"]
                + f": total_score={decision['total_score']}, label={decision['label']}, "
                + f"dte={decision['dte']}, iv={decision['implied_volatility']}"
            )
    else:
        lines.append("- no_contracts_passed_scoring_gate")

    lines.extend(["", "## Blocked Contracts"])
    if payload["blocked_contracts"]:
        for decision in payload["blocked_contracts"]:
            lines.append(
                "- "
                + decision["contract_id"]
                + f": total_score={decision['total_score']}, label={decision['label']}, reasons="
                + ", ".join(decision["reasons"])
            )
    else:
        lines.append("- no_blocked_contracts")

    lines.extend(["", "## Component Scores"])
    for decision in payload["suitable_contracts"] + payload["blocked_contracts"]:
        lines.append("- " + decision["contract_id"])
        for component in decision["component_scores"]:
            lines.append(
                "  - "
                + component["name"]
                + f": score={component['score']}, weight={component['weight']}, "
                + f"passed={component['passed']}, reason={component['reason']}"
            )

    lines.extend(
        [
            "",
            "## Safety",
            "- Deterministic options scoring report only; no broker routing or order submission.",
            "- Contract suitability is monitor-only research and requires human review.",
            "- Report-level state remains blocked by safety gate.",
        ]
    )
    return "\n".join(lines)


def write_contract_scoring_report(
    report: ContractScoringReport,
    out_dir: Path = DEFAULT_REPORT_DIR,
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "options_contract_scoring.json"
    md_path = out_dir / "options_contract_scoring.md"
    json_path.write_text(json.dumps(contract_scoring_payload(report), indent=2, default=str), encoding="utf-8")
    md_path.write_text(render_markdown_contract_scoring(report), encoding="utf-8")
    return json_path, md_path


def _score_contract(
    contract: OptionContractQualityInput,
    underlying_price: float,
    config: ContractScoringConfig,
    as_of: datetime,
) -> ContractScoreDecision:
    component_scores = (
        _delta_score(contract, config),
        _theta_score(contract, config),
        _vega_score(contract, config),
        _iv_score(contract, config),
        _spread_score(contract, config),
        _dte_score(contract, config, as_of),
        _liquidity_score(contract, config),
        _suitability_score(contract, underlying_price, config),
    )
    weighted_score = sum(component.score * component.weight for component in component_scores)
    total_weight = sum(component.weight for component in component_scores)
    total_score = int(round(weighted_score / total_weight))
    reasons = tuple(
        f"{component.name}_below_minimum"
        for component in component_scores
        if component.score < config.min_component_score
    )
    if total_score < config.min_total_score:
        reasons = (*reasons, "total_score_below_minimum")
    suitable = not reasons
    return ContractScoreDecision(
        contract=contract,
        underlying_price=underlying_price,
        evaluated_as_of=as_of,
        total_score=total_score,
        component_scores=component_scores,
        suitable=suitable,
        label=MONITOR_ONLY if suitable else BLOCKED_BY_SAFETY_GATE,
        reasons=reasons,
    )


def _delta_score(contract: OptionContractQualityInput, config: ContractScoringConfig) -> ComponentScore:
    delta = contract.greeks.delta
    if delta is None:
        return _component("delta", 0, 15, "missing_delta")
    abs_delta = abs(delta)
    if config.target_delta_min <= abs_delta <= config.target_delta_max:
        return _component("delta", 100, 15, "delta_inside_target_band")
    if config.acceptable_delta_min <= abs_delta <= config.acceptable_delta_max:
        return _component("delta", 70, 15, "delta_inside_acceptable_band")
    return _component("delta", 30, 15, "delta_outside_acceptable_band")


def _theta_score(contract: OptionContractQualityInput, config: ContractScoringConfig) -> ComponentScore:
    theta = contract.greeks.theta
    if theta is None:
        return _component("theta", 0, 12, "missing_theta")
    theta_abs = abs(theta)
    if theta_abs <= config.ideal_theta_abs_max:
        return _component("theta", 100, 12, "theta_decay_inside_ideal_limit")
    if theta_abs <= config.acceptable_theta_abs_max:
        return _component("theta", 70, 12, "theta_decay_inside_acceptable_limit")
    return _component("theta", 30, 12, "theta_decay_above_acceptable_limit")


def _vega_score(contract: OptionContractQualityInput, config: ContractScoringConfig) -> ComponentScore:
    vega = contract.greeks.vega
    if vega is None:
        return _component("vega", 0, 10, "missing_vega")
    if vega >= config.ideal_vega_min:
        return _component("vega", 100, 10, "vega_inside_ideal_floor")
    if vega >= config.acceptable_vega_min:
        return _component("vega", 70, 10, "vega_inside_acceptable_floor")
    return _component("vega", 30, 10, "vega_below_acceptable_floor")


def _iv_score(contract: OptionContractQualityInput, config: ContractScoringConfig) -> ComponentScore:
    iv = contract.implied_volatility
    if iv is None:
        return _component("implied_volatility", 0, 14, "missing_implied_volatility")
    if config.ideal_iv_min <= iv <= config.ideal_iv_max:
        return _component("implied_volatility", 100, 14, "implied_volatility_inside_ideal_band")
    if config.acceptable_iv_min <= iv <= config.acceptable_iv_max:
        return _component("implied_volatility", 70, 14, "implied_volatility_inside_acceptable_band")
    return _component("implied_volatility", 25, 14, "implied_volatility_outside_acceptable_band")


def _spread_score(contract: OptionContractQualityInput, config: ContractScoringConfig) -> ComponentScore:
    if contract.spread_pct <= config.ideal_spread_pct_max:
        return _component("spread", 100, 12, "spread_inside_ideal_limit")
    if contract.spread_pct <= config.acceptable_spread_pct_max:
        return _component("spread", 70, 12, "spread_inside_acceptable_limit")
    return _component("spread", 20, 12, "spread_above_acceptable_limit")


def _dte_score(
    contract: OptionContractQualityInput,
    config: ContractScoringConfig,
    as_of: datetime,
) -> ComponentScore:
    dte = contract.dte(as_of)
    if config.ideal_dte_min <= dte <= config.ideal_dte_max:
        return _component("dte", 100, 14, "dte_inside_ideal_band")
    if config.acceptable_dte_min <= dte <= config.acceptable_dte_max:
        return _component("dte", 70, 14, "dte_inside_acceptable_band")
    return _component("dte", 25, 14, "dte_outside_acceptable_band")


def _liquidity_score(contract: OptionContractQualityInput, config: ContractScoringConfig) -> ComponentScore:
    if contract.volume >= config.ideal_volume and contract.open_interest >= config.ideal_open_interest:
        return _component("liquidity", 100, 13, "volume_and_open_interest_inside_ideal_floor")
    if contract.volume >= config.min_volume and contract.open_interest >= config.min_open_interest:
        return _component("liquidity", 70, 13, "volume_and_open_interest_inside_minimum_floor")
    return _component("liquidity", 25, 13, "volume_or_open_interest_below_minimum_floor")


def _suitability_score(
    contract: OptionContractQualityInput,
    underlying_price: float,
    config: ContractScoringConfig,
) -> ComponentScore:
    strike_to_underlying = contract.strike / underlying_price
    if config.ideal_strike_to_underlying_min <= strike_to_underlying <= config.ideal_strike_to_underlying_max:
        return _component("contract_suitability", 100, 10, "strike_to_underlying_inside_ideal_band")
    if (
        config.acceptable_strike_to_underlying_min
        <= strike_to_underlying
        <= config.acceptable_strike_to_underlying_max
    ):
        return _component("contract_suitability", 70, 10, "strike_to_underlying_inside_acceptable_band")
    return _component("contract_suitability", 30, 10, "strike_to_underlying_outside_acceptable_band")


def _component(name: str, score: int, weight: int, reason: str) -> ComponentScore:
    return ComponentScore(name=name, score=score, weight=weight, passed=score >= 50, reason=reason)


def _config_payload(config: ContractScoringConfig) -> dict[str, Any]:
    return {
        "target_delta_min": config.target_delta_min,
        "target_delta_max": config.target_delta_max,
        "acceptable_delta_min": config.acceptable_delta_min,
        "acceptable_delta_max": config.acceptable_delta_max,
        "ideal_theta_abs_max": config.ideal_theta_abs_max,
        "acceptable_theta_abs_max": config.acceptable_theta_abs_max,
        "ideal_vega_min": config.ideal_vega_min,
        "acceptable_vega_min": config.acceptable_vega_min,
        "ideal_iv_min": config.ideal_iv_min,
        "ideal_iv_max": config.ideal_iv_max,
        "acceptable_iv_min": config.acceptable_iv_min,
        "acceptable_iv_max": config.acceptable_iv_max,
        "ideal_spread_pct_max": config.ideal_spread_pct_max,
        "acceptable_spread_pct_max": config.acceptable_spread_pct_max,
        "ideal_dte_min": config.ideal_dte_min,
        "ideal_dte_max": config.ideal_dte_max,
        "acceptable_dte_min": config.acceptable_dte_min,
        "acceptable_dte_max": config.acceptable_dte_max,
        "min_volume": config.min_volume,
        "min_open_interest": config.min_open_interest,
        "ideal_volume": config.ideal_volume,
        "ideal_open_interest": config.ideal_open_interest,
        "ideal_strike_to_underlying_min": config.ideal_strike_to_underlying_min,
        "ideal_strike_to_underlying_max": config.ideal_strike_to_underlying_max,
        "acceptable_strike_to_underlying_min": config.acceptable_strike_to_underlying_min,
        "acceptable_strike_to_underlying_max": config.acceptable_strike_to_underlying_max,
        "min_component_score": config.min_component_score,
        "min_total_score": config.min_total_score,
    }


def _decision_payload(decision: ContractScoreDecision) -> dict[str, Any]:
    contract = decision.contract
    return {
        "contract_id": contract.contract_id,
        "symbol": contract.symbol,
        "underlying_symbol": contract.underlying_symbol,
        "underlying_price": decision.underlying_price,
        "contract_type": contract.contract_type.lower(),
        "strike": contract.strike,
        "strike_to_underlying": round(contract.strike / decision.underlying_price, 6),
        "expiration": contract.expiration.isoformat(),
        "evaluated_as_of": decision.evaluated_as_of.isoformat(),
        "dte": contract.dte(decision.evaluated_as_of),
        "bid": contract.bid,
        "ask": contract.ask,
        "last": contract.last,
        "mid": contract.mid,
        "spread": contract.spread,
        "spread_pct": contract.spread_pct,
        "implied_volatility": contract.implied_volatility,
        "volume": contract.volume,
        "open_interest": contract.open_interest,
        "quote_as_of": contract.quote_as_of.isoformat(),
        "greeks": {
            "delta": contract.greeks.delta,
            "gamma": contract.greeks.gamma,
            "theta": contract.greeks.theta,
            "vega": contract.greeks.vega,
            "rho": contract.greeks.rho,
        },
        "total_score": decision.total_score,
        "component_scores": [_component_payload(component) for component in decision.component_scores],
        "suitable": decision.suitable,
        "label": decision.label,
        "reasons": decision.reasons,
        "human_review_required": decision.human_review_required,
    }


def _component_payload(component: ComponentScore) -> dict[str, Any]:
    return {
        "name": component.name,
        "score": component.score,
        "weight": component.weight,
        "passed": component.passed,
        "reason": component.reason,
    }


def _require_range(field_name: str, minimum: float, maximum: float, floor: float, ceiling: float) -> None:
    if minimum < floor or maximum > ceiling:
        raise ValueError(f"{field_name} must stay within allowed bounds")
    if maximum < minimum:
        raise ValueError(f"{field_name} maximum cannot be below minimum")


def _require_int_range(field_name: str, minimum: int, maximum: int, floor: int) -> None:
    if minimum < floor:
        raise ValueError(f"{field_name} minimum cannot be below {floor}")
    if maximum < minimum:
        raise ValueError(f"{field_name} maximum cannot be below minimum")


def _require_score(field_name: str, value: int) -> None:
    if not 0 <= value <= 100:
        raise ValueError(f"{field_name} must be between 0 and 100")


def _require_text(field_name: str, value: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required")


def _require_positive(field_name: str, value: float) -> None:
    if value <= 0:
        raise ValueError(f"{field_name} must be positive")


def _require_safe_label(label: str) -> None:
    if label not in SAFE_ACTION_LABELS:
        raise ValueError("label must be a safe research, monitor, paper, review, or blocked label")
