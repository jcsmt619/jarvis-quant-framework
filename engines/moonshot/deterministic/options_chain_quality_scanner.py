from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


PHASE_ID = "BR-03"
MODULE_NAME = "Options Chain Quality Scanner"
REQUIRED_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
SAFE_ACTION_LABELS = REQUIRED_LABELS
DEFAULT_FIXTURE_PATH = Path("engines/moonshot/deterministic/fixtures/br03_options_chain_quality.json")
DEFAULT_REPORT_DIR = Path("reports/br03_options_chain_quality")


@dataclass(frozen=True)
class OptionsChainQualityConfig:
    max_spread_pct: float = 0.08
    min_volume: int = 25
    min_open_interest: int = 250
    min_dte: int = 180
    max_dte: int = 900
    min_strike_count: int = 4
    max_quote_age_minutes: int = 30
    min_implied_volatility: float = 0.05
    max_implied_volatility: float = 1.50
    min_quality_score: int = 75

    def validate(self) -> None:
        _require_positive("max_spread_pct", self.max_spread_pct)
        _require_non_negative("min_volume", self.min_volume)
        _require_non_negative("min_open_interest", self.min_open_interest)
        if self.min_dte < 0:
            raise ValueError("min_dte cannot be negative")
        if self.max_dte < self.min_dte:
            raise ValueError("max_dte cannot be below min_dte")
        if self.min_strike_count <= 0:
            raise ValueError("min_strike_count must be positive")
        if self.max_quote_age_minutes < 0:
            raise ValueError("max_quote_age_minutes cannot be negative")
        _require_positive("min_implied_volatility", self.min_implied_volatility)
        if self.max_implied_volatility < self.min_implied_volatility:
            raise ValueError("max_implied_volatility cannot be below min_implied_volatility")
        if not 0 <= self.min_quality_score <= 100:
            raise ValueError("min_quality_score must be between 0 and 100")


@dataclass(frozen=True)
class OptionGreeksQuality:
    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None
    rho: float | None = None

    @property
    def missing_fields(self) -> tuple[str, ...]:
        return tuple(
            field_name
            for field_name, value in (
                ("delta", self.delta),
                ("gamma", self.gamma),
                ("theta", self.theta),
                ("vega", self.vega),
            )
            if value is None
        )

    def validate(self) -> None:
        if self.delta is not None and not -1.0 <= self.delta <= 1.0:
            raise ValueError("delta must be between -1 and 1")
        for field_name, value in (("gamma", self.gamma), ("vega", self.vega)):
            if value is not None:
                _require_non_negative(field_name, value)


@dataclass(frozen=True)
class OptionContractQualityInput:
    contract_id: str
    symbol: str
    underlying_symbol: str
    contract_type: str
    strike: float
    expiration: date
    bid: float
    ask: float
    last: float
    implied_volatility: float | None
    volume: int
    open_interest: int
    quote_as_of: datetime
    greeks: OptionGreeksQuality
    label: str = MONITOR_ONLY

    @property
    def mid(self) -> float:
        return round((self.bid + self.ask) / 2, 4)

    @property
    def spread(self) -> float:
        return round(self.ask - self.bid, 4)

    @property
    def spread_pct(self) -> float:
        if self.mid <= 0:
            return 0.0
        return round(self.spread / self.mid, 6)

    def dte(self, as_of: datetime) -> int:
        return (self.expiration - as_of.date()).days

    def quote_age_minutes(self, as_of: datetime) -> int:
        return max(0, int((as_of - self.quote_as_of).total_seconds() // 60))

    def validate(self) -> None:
        _require_text("contract_id", self.contract_id)
        _require_symbol(self.symbol)
        _require_symbol(self.underlying_symbol)
        if self.contract_type.lower() not in {"call", "put"}:
            raise ValueError("contract_type must be call or put")
        _require_positive("strike", self.strike)
        for field_name, value in (("bid", self.bid), ("ask", self.ask), ("last", self.last)):
            _require_non_negative(field_name, value)
        if self.ask < self.bid:
            raise ValueError("ask cannot be below bid")
        if self.implied_volatility is not None:
            _require_non_negative("implied_volatility", self.implied_volatility)
        _require_non_negative("volume", self.volume)
        _require_non_negative("open_interest", self.open_interest)
        self.greeks.validate()
        _require_safe_label(self.label)


@dataclass(frozen=True)
class OptionChainQualityInput:
    underlying_symbol: str
    underlying_price: float
    as_of: datetime
    contracts: tuple[OptionContractQualityInput, ...]
    label: str = MONITOR_ONLY

    def validate(self) -> None:
        _require_symbol(self.underlying_symbol)
        _require_positive("underlying_price", self.underlying_price)
        if not self.contracts:
            raise ValueError("option chain quality input requires at least one contract")
        for contract in self.contracts:
            contract.validate()
            if contract.underlying_symbol != self.underlying_symbol:
                raise ValueError("contract underlying_symbol must match chain underlying")
        _require_safe_label(self.label)


@dataclass(frozen=True)
class ContractQualityDecision:
    contract: OptionContractQualityInput
    score: int
    passed: bool
    label: str
    reasons: tuple[str, ...]
    human_review_required: bool = True

    def validate(self) -> None:
        self.contract.validate()
        if not 0 <= self.score <= 100:
            raise ValueError("score must be between 0 and 100")
        _require_safe_label(self.label)
        if self.passed and self.label != MONITOR_ONLY:
            raise ValueError("passing contract quality decisions must remain monitor-only")
        if not self.passed and self.label != BLOCKED_BY_SAFETY_GATE:
            raise ValueError("failing contract quality decisions must be blocked by safety gate")
        if not self.human_review_required:
            raise ValueError("contract quality decisions must require human review")


@dataclass(frozen=True)
class ChainQualityDecision:
    chain: OptionChainQualityInput
    score: int
    passed: bool
    label: str
    strike_count: int
    strike_availability_passed: bool
    reasons: tuple[str, ...]
    contract_decisions: tuple[ContractQualityDecision, ...]
    human_review_required: bool = True

    def validate(self) -> None:
        self.chain.validate()
        if not 0 <= self.score <= 100:
            raise ValueError("score must be between 0 and 100")
        if self.strike_count <= 0:
            raise ValueError("strike_count must be positive")
        for decision in self.contract_decisions:
            decision.validate()
        _require_safe_label(self.label)
        if self.passed and self.label != MONITOR_ONLY:
            raise ValueError("passing chain quality decisions must remain monitor-only")
        if not self.passed and self.label != BLOCKED_BY_SAFETY_GATE:
            raise ValueError("failing chain quality decisions must be blocked by safety gate")
        if not self.human_review_required:
            raise ValueError("chain quality decisions must require human review")


@dataclass(frozen=True)
class OptionsChainQualityReport:
    as_of: datetime
    config: OptionsChainQualityConfig
    chain_decisions: tuple[ChainQualityDecision, ...]
    safety: dict[str, Any]
    label: str = BLOCKED_BY_SAFETY_GATE

    @property
    def passed_chains(self) -> tuple[ChainQualityDecision, ...]:
        return tuple(decision for decision in self.chain_decisions if decision.passed)

    @property
    def blocked_chains(self) -> tuple[ChainQualityDecision, ...]:
        return tuple(decision for decision in self.chain_decisions if not decision.passed)

    def validate(self) -> None:
        self.config.validate()
        if not self.chain_decisions:
            raise ValueError("options chain quality report requires at least one chain decision")
        for decision in self.chain_decisions:
            decision.validate()
        _require_safe_label(self.label)
        if self.label != BLOCKED_BY_SAFETY_GATE:
            raise ValueError("options chain quality report must remain blocked by safety gate")


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


def load_options_chain_quality_inputs(
    path: Path = DEFAULT_FIXTURE_PATH,
) -> tuple[OptionChainQualityInput, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    chains = tuple(_chain_from_payload(item) for item in payload["chains"])
    if not chains:
        raise ValueError("options chain quality fixture requires at least one chain")
    for chain in chains:
        chain.validate()
    return chains


def build_options_chain_quality_report(
    chains: tuple[OptionChainQualityInput, ...] | list[OptionChainQualityInput],
    config: OptionsChainQualityConfig | None = None,
    as_of: datetime | None = None,
) -> OptionsChainQualityReport:
    cfg = config or OptionsChainQualityConfig()
    cfg.validate()
    if not chains:
        raise ValueError("options chain quality scanner requires at least one chain")
    validated = tuple(chains)
    for chain in validated:
        chain.validate()
    report_as_of = as_of or max(chain.as_of for chain in validated)
    decisions = tuple(
        _chain_decision(chain, cfg, report_as_of)
        for chain in sorted(validated, key=lambda item: item.underlying_symbol)
    )
    report = OptionsChainQualityReport(
        as_of=report_as_of,
        config=cfg,
        chain_decisions=decisions,
        safety=safety_manifest(),
    )
    report.validate()
    return report


def load_options_chain_quality_report(
    path: Path = DEFAULT_FIXTURE_PATH,
    config: OptionsChainQualityConfig | None = None,
) -> OptionsChainQualityReport:
    return build_options_chain_quality_report(load_options_chain_quality_inputs(path), config=config)


def options_chain_quality_payload(report: OptionsChainQualityReport) -> dict[str, Any]:
    report.validate()
    passed = sorted(report.passed_chains, key=lambda item: (-item.score, item.chain.underlying_symbol))
    blocked = sorted(report.blocked_chains, key=lambda item: item.chain.underlying_symbol)
    contract_decisions = tuple(
        decision for chain_decision in report.chain_decisions for decision in chain_decision.contract_decisions
    )
    return {
        "phase": PHASE_ID,
        "module": MODULE_NAME,
        "as_of": report.as_of.isoformat(),
        "label": report.label,
        "safety": report.safety,
        "config": _config_payload(report.config),
        "metrics": {
            "chain_count": len(report.chain_decisions),
            "passed_chain_count": len(passed),
            "blocked_chain_count": len(blocked),
            "contract_count": len(contract_decisions),
            "passed_contract_count": len(tuple(item for item in contract_decisions if item.passed)),
            "blocked_contract_count": len(tuple(item for item in contract_decisions if not item.passed)),
            "human_review_required_count": len(report.chain_decisions) + len(contract_decisions),
        },
        "passed_chains": [_chain_decision_payload(decision, report.as_of) for decision in passed],
        "blocked_chains": [_chain_decision_payload(decision, report.as_of) for decision in blocked],
    }


def render_markdown_options_chain_quality(report: OptionsChainQualityReport) -> str:
    payload = options_chain_quality_payload(report)
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

    lines.extend(["", "## Passed Chains"])
    if payload["passed_chains"]:
        for decision in payload["passed_chains"]:
            lines.append(
                "- "
                + decision["underlying_symbol"]
                + f": score={decision['score']}, strikes={decision['strike_count']}, "
                + f"label={decision['label']}"
            )
    else:
        lines.append("- no_chains_passed_quality_gate")

    lines.extend(["", "## Blocked Chains"])
    if payload["blocked_chains"]:
        for decision in payload["blocked_chains"]:
            lines.append(
                "- "
                + decision["underlying_symbol"]
                + f": score={decision['score']}, label={decision['label']}, reasons="
                + ", ".join(decision["reasons"])
            )
    else:
        lines.append("- no_blocked_chains")

    lines.extend(["", "## Contract Quality Flags"])
    for chain_decision in payload["passed_chains"] + payload["blocked_chains"]:
        for contract in chain_decision["contracts"]:
            if contract["reasons"]:
                lines.append(
                    "- "
                    + contract["contract_id"]
                    + f": score={contract['score']}, label={contract['label']}, reasons="
                    + ", ".join(contract["reasons"])
                )

    lines.extend(
        [
            "",
            "## Safety",
            "- Deterministic option-chain quality report only; no broker routing or order submission.",
            "- Quality pass state is monitor-only research and requires human review.",
            "- Report-level state remains blocked by safety gate.",
        ]
    )
    return "\n".join(lines)


def write_options_chain_quality_report(
    report: OptionsChainQualityReport,
    out_dir: Path = DEFAULT_REPORT_DIR,
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "options_chain_quality.json"
    md_path = out_dir / "options_chain_quality.md"
    json_path.write_text(
        json.dumps(options_chain_quality_payload(report), indent=2, default=str),
        encoding="utf-8",
    )
    md_path.write_text(render_markdown_options_chain_quality(report), encoding="utf-8")
    return json_path, md_path


def _chain_decision(
    chain: OptionChainQualityInput,
    config: OptionsChainQualityConfig,
    as_of: datetime,
) -> ChainQualityDecision:
    contract_decisions = tuple(
        _contract_decision(contract, config, as_of)
        for contract in sorted(chain.contracts, key=lambda item: (item.expiration, item.strike, item.symbol))
    )
    strike_count = len({contract.strike for contract in chain.contracts})
    reasons = []
    strike_availability_passed = strike_count >= config.min_strike_count
    if not strike_availability_passed:
        reasons.append("strike_availability_below_minimum")
    failed_contracts = tuple(decision for decision in contract_decisions if not decision.passed)
    if failed_contracts:
        reasons.append("one_or_more_contracts_failed_quality_gate")
    average_score = int(round(sum(decision.score for decision in contract_decisions) / len(contract_decisions)))
    if average_score < config.min_quality_score:
        reasons.append("chain_score_below_minimum")
    passed = not reasons
    return ChainQualityDecision(
        chain=chain,
        score=average_score,
        passed=passed,
        label=MONITOR_ONLY if passed else BLOCKED_BY_SAFETY_GATE,
        strike_count=strike_count,
        strike_availability_passed=strike_availability_passed,
        reasons=tuple(reasons),
        contract_decisions=contract_decisions,
    )


def _contract_decision(
    contract: OptionContractQualityInput,
    config: OptionsChainQualityConfig,
    as_of: datetime,
) -> ContractQualityDecision:
    reasons = _contract_blocking_reasons(contract, config, as_of)
    score = _score_contract(contract, config, as_of, reasons)
    passed = not reasons and score >= config.min_quality_score
    if not passed and score < config.min_quality_score and "contract_score_below_minimum" not in reasons:
        reasons = (*reasons, "contract_score_below_minimum")
    return ContractQualityDecision(
        contract=contract,
        score=score,
        passed=passed,
        label=MONITOR_ONLY if passed else BLOCKED_BY_SAFETY_GATE,
        reasons=tuple(reasons),
    )


def _contract_blocking_reasons(
    contract: OptionContractQualityInput,
    config: OptionsChainQualityConfig,
    as_of: datetime,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if contract.spread_pct > config.max_spread_pct:
        reasons.append("spread_pct_above_maximum")
    if contract.volume < config.min_volume:
        reasons.append("volume_below_minimum")
    if contract.open_interest < config.min_open_interest:
        reasons.append("open_interest_below_minimum")
    dte = contract.dte(as_of)
    if dte < config.min_dte:
        reasons.append("dte_below_minimum")
    if dte > config.max_dte:
        reasons.append("dte_above_maximum")
    if contract.quote_age_minutes(as_of) > config.max_quote_age_minutes:
        reasons.append("stale_quote_data")
    if contract.greeks.missing_fields:
        reasons.append("missing_greeks")
    if contract.implied_volatility is None:
        reasons.append("missing_implied_volatility")
    elif not config.min_implied_volatility <= contract.implied_volatility <= config.max_implied_volatility:
        reasons.append("implied_volatility_out_of_range")
    return tuple(reasons)


def _score_contract(
    contract: OptionContractQualityInput,
    config: OptionsChainQualityConfig,
    as_of: datetime,
    reasons: tuple[str, ...],
) -> int:
    score = 100
    penalty_by_reason = {
        "spread_pct_above_maximum": 20,
        "volume_below_minimum": 15,
        "open_interest_below_minimum": 15,
        "dte_below_minimum": 12,
        "dte_above_maximum": 12,
        "stale_quote_data": 15,
        "missing_greeks": 15,
        "missing_implied_volatility": 15,
        "implied_volatility_out_of_range": 15,
    }
    for reason in reasons:
        score -= penalty_by_reason[reason]
    if not reasons:
        spread_bonus = max(0, int((config.max_spread_pct - contract.spread_pct) / config.max_spread_pct * 8))
        liquidity_bonus = min(7, int(contract.volume / max(config.min_volume, 1)))
        oi_bonus = min(5, int(contract.open_interest / max(config.min_open_interest, 1)))
        freshness_bonus = 5 if contract.quote_age_minutes(as_of) <= config.max_quote_age_minutes // 2 else 0
        score = min(100, score + spread_bonus + liquidity_bonus + oi_bonus + freshness_bonus)
    return max(0, min(100, score))


def _chain_from_payload(payload: dict[str, Any]) -> OptionChainQualityInput:
    return OptionChainQualityInput(
        underlying_symbol=payload["underlying_symbol"],
        underlying_price=float(payload["underlying_price"]),
        as_of=datetime.fromisoformat(payload["as_of"]),
        contracts=tuple(_contract_from_payload(item) for item in payload["contracts"]),
        label=payload.get("label", MONITOR_ONLY),
    )


def _contract_from_payload(payload: dict[str, Any]) -> OptionContractQualityInput:
    return OptionContractQualityInput(
        contract_id=payload["contract_id"],
        symbol=payload["symbol"],
        underlying_symbol=payload["underlying_symbol"],
        contract_type=payload["contract_type"],
        strike=float(payload["strike"]),
        expiration=date.fromisoformat(payload["expiration"]),
        bid=float(payload["bid"]),
        ask=float(payload["ask"]),
        last=float(payload["last"]),
        implied_volatility=(
            None if payload.get("implied_volatility") is None else float(payload["implied_volatility"])
        ),
        volume=int(payload["volume"]),
        open_interest=int(payload["open_interest"]),
        quote_as_of=datetime.fromisoformat(payload["quote_as_of"]),
        greeks=_greeks_from_payload(payload.get("greeks", {})),
        label=payload.get("label", MONITOR_ONLY),
    )


def _greeks_from_payload(payload: dict[str, Any]) -> OptionGreeksQuality:
    return OptionGreeksQuality(
        delta=_optional_float(payload.get("delta")),
        gamma=_optional_float(payload.get("gamma")),
        theta=_optional_float(payload.get("theta")),
        vega=_optional_float(payload.get("vega")),
        rho=_optional_float(payload.get("rho")),
    )


def _config_payload(config: OptionsChainQualityConfig) -> dict[str, Any]:
    return {
        "max_spread_pct": config.max_spread_pct,
        "min_volume": config.min_volume,
        "min_open_interest": config.min_open_interest,
        "min_dte": config.min_dte,
        "max_dte": config.max_dte,
        "min_strike_count": config.min_strike_count,
        "max_quote_age_minutes": config.max_quote_age_minutes,
        "min_implied_volatility": config.min_implied_volatility,
        "max_implied_volatility": config.max_implied_volatility,
        "min_quality_score": config.min_quality_score,
    }


def _chain_decision_payload(decision: ChainQualityDecision, as_of: datetime) -> dict[str, Any]:
    return {
        "underlying_symbol": decision.chain.underlying_symbol,
        "underlying_price": decision.chain.underlying_price,
        "as_of": decision.chain.as_of.isoformat(),
        "score": decision.score,
        "passed": decision.passed,
        "label": decision.label,
        "strike_count": decision.strike_count,
        "strike_availability_passed": decision.strike_availability_passed,
        "reasons": decision.reasons,
        "human_review_required": decision.human_review_required,
        "contracts": [_contract_decision_payload(item, as_of) for item in decision.contract_decisions],
    }


def _contract_decision_payload(decision: ContractQualityDecision, as_of: datetime) -> dict[str, Any]:
    contract = decision.contract
    return {
        "contract_id": contract.contract_id,
        "symbol": contract.symbol,
        "underlying_symbol": contract.underlying_symbol,
        "contract_type": contract.contract_type.lower(),
        "strike": contract.strike,
        "expiration": contract.expiration.isoformat(),
        "dte": contract.dte(as_of),
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
        "quote_age_minutes": contract.quote_age_minutes(as_of),
        "greeks_missing_fields": contract.greeks.missing_fields,
        "score": decision.score,
        "passed": decision.passed,
        "label": decision.label,
        "reasons": decision.reasons,
        "human_review_required": decision.human_review_required,
    }


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


def _require_symbol(symbol: str) -> None:
    _require_text("symbol", symbol)
    if symbol.strip() != symbol.strip().upper():
        raise ValueError("symbol must be uppercase")


def _require_text(field_name: str, value: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required")


def _require_positive(field_name: str, value: float) -> None:
    if value <= 0:
        raise ValueError(f"{field_name} must be positive")


def _require_non_negative(field_name: str, value: float | int) -> None:
    if value < 0:
        raise ValueError(f"{field_name} cannot be negative")


def _require_safe_label(label: str) -> None:
    if label not in SAFE_ACTION_LABELS:
        raise ValueError("label must be a safe research, monitor, paper, review, or blocked label")
