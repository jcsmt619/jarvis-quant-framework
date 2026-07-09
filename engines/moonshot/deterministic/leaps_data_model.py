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


PHASE_ID = "BR-01"
MODULE_NAME = "Options LEAPS Data Model"
REQUIRED_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
SAFE_ACTION_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
DEFAULT_FIXTURE_PATH = Path("engines/moonshot/deterministic/fixtures/br01_leaps_data_model.json")


@dataclass(frozen=True)
class EquitySnapshot:
    symbol: str
    name: str
    sector: str
    last_price: float
    as_of: date
    average_volume_30d: int
    market_cap: float | None = None
    label: str = RESEARCH_ONLY

    def validate(self) -> None:
        _require_symbol(self.symbol)
        _require_text("name", self.name)
        _require_text("sector", self.sector)
        _require_positive("last_price", self.last_price)
        _require_non_negative("average_volume_30d", self.average_volume_30d)
        if self.market_cap is not None:
            _require_non_negative("market_cap", self.market_cap)
        _require_safe_label(self.label)


@dataclass(frozen=True)
class OptionGreeks:
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float = 0.0

    def validate(self) -> None:
        if not -1.0 <= self.delta <= 1.0:
            raise ValueError("delta must be between -1 and 1")
        _require_non_negative("gamma", self.gamma)
        _require_non_negative("vega", self.vega)


@dataclass(frozen=True)
class OptionQuote:
    bid: float
    ask: float
    last: float
    implied_volatility: float
    volume: int
    open_interest: int
    as_of: datetime

    @property
    def spread(self) -> float:
        return round(self.ask - self.bid, 4)

    @property
    def mid(self) -> float:
        return round((self.bid + self.ask) / 2, 4)

    @property
    def spread_pct(self) -> float:
        if self.mid == 0:
            return 0.0
        return round(self.spread / self.mid, 6)

    def validate(self) -> None:
        for field_name, value in (
            ("bid", self.bid),
            ("ask", self.ask),
            ("last", self.last),
            ("implied_volatility", self.implied_volatility),
        ):
            _require_non_negative(field_name, value)
        if self.ask < self.bid:
            raise ValueError("ask cannot be below bid")
        _require_non_negative("volume", self.volume)
        _require_non_negative("open_interest", self.open_interest)


@dataclass(frozen=True)
class CatalystMetadata:
    catalyst_id: str
    symbol: str
    catalyst_type: str
    description: str
    expected_date: date | None
    confidence: str
    source_note: str
    label: str = HUMAN_REVIEW_REQUIRED

    def validate(self) -> None:
        _require_text("catalyst_id", self.catalyst_id)
        _require_symbol(self.symbol)
        _require_text("catalyst_type", self.catalyst_type)
        _require_text("description", self.description)
        _require_text("confidence", self.confidence)
        _require_text("source_note", self.source_note)
        _require_safe_label(self.label)


@dataclass(frozen=True)
class AnalystThesisRecord:
    thesis_id: str
    symbol: str
    summary: str
    bull_case: str
    bear_case: str
    invalidation: str
    created_at: datetime
    author: str = "jarvis_analyst_workflow"
    label: str = HUMAN_REVIEW_REQUIRED

    def validate(self) -> None:
        _require_text("thesis_id", self.thesis_id)
        _require_symbol(self.symbol)
        for field_name, value in (
            ("summary", self.summary),
            ("bull_case", self.bull_case),
            ("bear_case", self.bear_case),
            ("invalidation", self.invalidation),
            ("author", self.author),
        ):
            _require_text(field_name, value)
        _require_safe_label(self.label)
        if self.label != HUMAN_REVIEW_REQUIRED:
            raise ValueError("trade-relevant analyst thesis records must require human review")


@dataclass(frozen=True)
class OptionContract:
    contract_id: str
    symbol: str
    underlying_symbol: str
    contract_type: str
    strike: float
    expiration: date
    quote: OptionQuote
    greeks: OptionGreeks
    label: str = MONITOR_ONLY

    @property
    def dte(self) -> int:
        return (self.expiration - self.quote.as_of.date()).days

    def validate(self) -> None:
        _require_text("contract_id", self.contract_id)
        _require_symbol(self.symbol)
        _require_symbol(self.underlying_symbol)
        if self.contract_type.lower() not in {"call", "put"}:
            raise ValueError("contract_type must be call or put")
        _require_positive("strike", self.strike)
        if self.expiration < self.quote.as_of.date():
            raise ValueError("expiration cannot be before quote date")
        self.quote.validate()
        self.greeks.validate()
        _require_safe_label(self.label)


@dataclass(frozen=True)
class OptionChain:
    underlying: EquitySnapshot
    contracts: tuple[OptionContract, ...]
    catalysts: tuple[CatalystMetadata, ...]
    as_of: datetime
    label: str = MONITOR_ONLY

    def validate(self) -> None:
        self.underlying.validate()
        if not self.contracts:
            raise ValueError("option chain requires at least one contract")
        for contract in self.contracts:
            contract.validate()
            if contract.underlying_symbol.upper() != self.underlying.symbol.upper():
                raise ValueError("contract underlying_symbol must match chain underlying")
        for catalyst in self.catalysts:
            catalyst.validate()
            if catalyst.symbol.upper() != self.underlying.symbol.upper():
                raise ValueError("catalyst symbol must match chain underlying")
        _require_safe_label(self.label)


@dataclass(frozen=True)
class PaperPortfolioPosition:
    position_id: str
    contract_id: str
    symbol: str
    contracts: int
    average_price: float
    mark_price: float
    opened_at: datetime
    thesis_id: str
    label: str = PAPER_ONLY

    @property
    def cost_basis(self) -> float:
        return round(self.contracts * self.average_price * 100, 2)

    @property
    def market_value(self) -> float:
        return round(self.contracts * self.mark_price * 100, 2)

    @property
    def unrealized_pnl(self) -> float:
        return round(self.market_value - self.cost_basis, 2)

    def validate(self) -> None:
        _require_text("position_id", self.position_id)
        _require_text("contract_id", self.contract_id)
        _require_symbol(self.symbol)
        if self.contracts <= 0:
            raise ValueError("contracts must be positive")
        _require_non_negative("average_price", self.average_price)
        _require_non_negative("mark_price", self.mark_price)
        _require_text("thesis_id", self.thesis_id)
        _require_safe_label(self.label)


@dataclass(frozen=True)
class LeapsDataSet:
    as_of: datetime
    equities: tuple[EquitySnapshot, ...]
    option_chains: tuple[OptionChain, ...]
    paper_positions: tuple[PaperPortfolioPosition, ...]
    analyst_theses: tuple[AnalystThesisRecord, ...]
    label: str = BLOCKED_BY_SAFETY_GATE

    def validate(self) -> None:
        if not self.equities:
            raise ValueError("dataset requires at least one equity")
        symbols = {equity.symbol.upper() for equity in self.equities}
        thesis_ids = {thesis.thesis_id for thesis in self.analyst_theses}
        contract_ids = {
            contract.contract_id
            for chain in self.option_chains
            for contract in chain.contracts
        }

        for equity in self.equities:
            equity.validate()
        for chain in self.option_chains:
            chain.validate()
            if chain.underlying.symbol.upper() not in symbols:
                raise ValueError("option chain underlying must be present in equities")
        for thesis in self.analyst_theses:
            thesis.validate()
            if thesis.symbol.upper() not in symbols:
                raise ValueError("analyst thesis symbol must be present in equities")
        for position in self.paper_positions:
            position.validate()
            if position.contract_id not in contract_ids:
                raise ValueError("paper position contract_id must exist in option chains")
            if position.thesis_id not in thesis_ids:
                raise ValueError("paper position thesis_id must exist in analyst theses")
        _require_safe_label(self.label)


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


def load_leaps_dataset(path: Path = DEFAULT_FIXTURE_PATH) -> LeapsDataSet:
    payload = json.loads(path.read_text(encoding="utf-8"))
    dataset = leaps_dataset_from_payload(payload)
    dataset.validate()
    return dataset


def leaps_dataset_from_payload(payload: dict[str, Any]) -> LeapsDataSet:
    equities = tuple(_equity_from_payload(item) for item in payload["equities"])
    equity_by_symbol = {equity.symbol.upper(): equity for equity in equities}
    chains = tuple(_chain_from_payload(item, equity_by_symbol) for item in payload["option_chains"])
    positions = tuple(_position_from_payload(item) for item in payload.get("paper_positions", ()))
    theses = tuple(_thesis_from_payload(item) for item in payload.get("analyst_theses", ()))
    return LeapsDataSet(
        as_of=_parse_datetime(payload["as_of"]),
        equities=equities,
        option_chains=chains,
        paper_positions=positions,
        analyst_theses=theses,
        label=payload.get("label", BLOCKED_BY_SAFETY_GATE),
    )


def leaps_dataset_payload(dataset: LeapsDataSet) -> dict[str, Any]:
    dataset.validate()
    return {
        "phase": PHASE_ID,
        "module": MODULE_NAME,
        "as_of": dataset.as_of.isoformat(),
        "label": dataset.label,
        "equities": [_equity_payload(item) for item in dataset.equities],
        "option_chains": [_chain_payload(item) for item in dataset.option_chains],
        "paper_positions": [_position_payload(item) for item in dataset.paper_positions],
        "analyst_theses": [_thesis_payload(item) for item in dataset.analyst_theses],
        "safety": safety_manifest(),
    }


def _equity_from_payload(payload: dict[str, Any]) -> EquitySnapshot:
    return EquitySnapshot(
        symbol=payload["symbol"],
        name=payload["name"],
        sector=payload["sector"],
        last_price=float(payload["last_price"]),
        as_of=_parse_date(payload["as_of"]),
        average_volume_30d=int(payload["average_volume_30d"]),
        market_cap=payload.get("market_cap"),
        label=payload.get("label", RESEARCH_ONLY),
    )


def _chain_from_payload(payload: dict[str, Any], equities: dict[str, EquitySnapshot]) -> OptionChain:
    symbol = payload["underlying_symbol"].upper()
    if symbol not in equities:
        raise ValueError("option chain underlying must be present in equities")
    return OptionChain(
        underlying=equities[symbol],
        contracts=tuple(_contract_from_payload(item) for item in payload["contracts"]),
        catalysts=tuple(_catalyst_from_payload(item) for item in payload.get("catalysts", ())),
        as_of=_parse_datetime(payload["as_of"]),
        label=payload.get("label", MONITOR_ONLY),
    )


def _contract_from_payload(payload: dict[str, Any]) -> OptionContract:
    return OptionContract(
        contract_id=payload["contract_id"],
        symbol=payload["symbol"],
        underlying_symbol=payload["underlying_symbol"],
        contract_type=payload["contract_type"],
        strike=float(payload["strike"]),
        expiration=_parse_date(payload["expiration"]),
        quote=_quote_from_payload(payload["quote"]),
        greeks=_greeks_from_payload(payload["greeks"]),
        label=payload.get("label", MONITOR_ONLY),
    )


def _quote_from_payload(payload: dict[str, Any]) -> OptionQuote:
    return OptionQuote(
        bid=float(payload["bid"]),
        ask=float(payload["ask"]),
        last=float(payload["last"]),
        implied_volatility=float(payload["implied_volatility"]),
        volume=int(payload["volume"]),
        open_interest=int(payload["open_interest"]),
        as_of=_parse_datetime(payload["as_of"]),
    )


def _greeks_from_payload(payload: dict[str, Any]) -> OptionGreeks:
    return OptionGreeks(
        delta=float(payload["delta"]),
        gamma=float(payload["gamma"]),
        theta=float(payload["theta"]),
        vega=float(payload["vega"]),
        rho=float(payload.get("rho", 0.0)),
    )


def _catalyst_from_payload(payload: dict[str, Any]) -> CatalystMetadata:
    return CatalystMetadata(
        catalyst_id=payload["catalyst_id"],
        symbol=payload["symbol"],
        catalyst_type=payload["catalyst_type"],
        description=payload["description"],
        expected_date=_parse_optional_date(payload.get("expected_date")),
        confidence=payload["confidence"],
        source_note=payload["source_note"],
        label=payload.get("label", HUMAN_REVIEW_REQUIRED),
    )


def _position_from_payload(payload: dict[str, Any]) -> PaperPortfolioPosition:
    return PaperPortfolioPosition(
        position_id=payload["position_id"],
        contract_id=payload["contract_id"],
        symbol=payload["symbol"],
        contracts=int(payload["contracts"]),
        average_price=float(payload["average_price"]),
        mark_price=float(payload["mark_price"]),
        opened_at=_parse_datetime(payload["opened_at"]),
        thesis_id=payload["thesis_id"],
        label=payload.get("label", PAPER_ONLY),
    )


def _thesis_from_payload(payload: dict[str, Any]) -> AnalystThesisRecord:
    return AnalystThesisRecord(
        thesis_id=payload["thesis_id"],
        symbol=payload["symbol"],
        summary=payload["summary"],
        bull_case=payload["bull_case"],
        bear_case=payload["bear_case"],
        invalidation=payload["invalidation"],
        created_at=_parse_datetime(payload["created_at"]),
        author=payload.get("author", "jarvis_analyst_workflow"),
        label=payload.get("label", HUMAN_REVIEW_REQUIRED),
    )


def _equity_payload(equity: EquitySnapshot) -> dict[str, Any]:
    return {
        "symbol": equity.symbol.upper(),
        "name": equity.name,
        "sector": equity.sector,
        "last_price": equity.last_price,
        "as_of": equity.as_of.isoformat(),
        "average_volume_30d": equity.average_volume_30d,
        "market_cap": equity.market_cap,
        "label": equity.label,
    }


def _chain_payload(chain: OptionChain) -> dict[str, Any]:
    return {
        "underlying_symbol": chain.underlying.symbol.upper(),
        "as_of": chain.as_of.isoformat(),
        "label": chain.label,
        "contracts": [_contract_payload(item) for item in chain.contracts],
        "catalysts": [_catalyst_payload(item) for item in chain.catalysts],
    }


def _contract_payload(contract: OptionContract) -> dict[str, Any]:
    return {
        "contract_id": contract.contract_id,
        "symbol": contract.symbol.upper(),
        "underlying_symbol": contract.underlying_symbol.upper(),
        "contract_type": contract.contract_type.lower(),
        "strike": contract.strike,
        "expiration": contract.expiration.isoformat(),
        "dte": contract.dte,
        "quote": {
            "bid": contract.quote.bid,
            "ask": contract.quote.ask,
            "last": contract.quote.last,
            "mid": contract.quote.mid,
            "spread": contract.quote.spread,
            "spread_pct": contract.quote.spread_pct,
            "implied_volatility": contract.quote.implied_volatility,
            "volume": contract.quote.volume,
            "open_interest": contract.quote.open_interest,
            "as_of": contract.quote.as_of.isoformat(),
        },
        "greeks": {
            "delta": contract.greeks.delta,
            "gamma": contract.greeks.gamma,
            "theta": contract.greeks.theta,
            "vega": contract.greeks.vega,
            "rho": contract.greeks.rho,
        },
        "label": contract.label,
    }


def _catalyst_payload(catalyst: CatalystMetadata) -> dict[str, Any]:
    return {
        "catalyst_id": catalyst.catalyst_id,
        "symbol": catalyst.symbol.upper(),
        "catalyst_type": catalyst.catalyst_type,
        "description": catalyst.description,
        "expected_date": catalyst.expected_date.isoformat() if catalyst.expected_date else None,
        "confidence": catalyst.confidence,
        "source_note": catalyst.source_note,
        "label": catalyst.label,
    }


def _position_payload(position: PaperPortfolioPosition) -> dict[str, Any]:
    return {
        "position_id": position.position_id,
        "contract_id": position.contract_id,
        "symbol": position.symbol.upper(),
        "contracts": position.contracts,
        "average_price": position.average_price,
        "mark_price": position.mark_price,
        "cost_basis": position.cost_basis,
        "market_value": position.market_value,
        "unrealized_pnl": position.unrealized_pnl,
        "opened_at": position.opened_at.isoformat(),
        "thesis_id": position.thesis_id,
        "label": position.label,
        "simulated_position": True,
    }


def _thesis_payload(thesis: AnalystThesisRecord) -> dict[str, Any]:
    return {
        "thesis_id": thesis.thesis_id,
        "symbol": thesis.symbol.upper(),
        "summary": thesis.summary,
        "bull_case": thesis.bull_case,
        "bear_case": thesis.bear_case,
        "invalidation": thesis.invalidation,
        "created_at": thesis.created_at.isoformat(),
        "author": thesis.author,
        "label": thesis.label,
    }


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _parse_optional_date(value: str | None) -> date | None:
    return _parse_date(value) if value else None


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


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
