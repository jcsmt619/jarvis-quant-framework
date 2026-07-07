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


PHASE_ID = "13F"
MODULE_NAME = "Paper LEAPS Portfolio"
REQUIRED_LABELS = (RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED)
DEFAULT_REPORT_DIR = Path("reports/paper_leaps_portfolio")
CONTRACT_MULTIPLIER = 100
THESIS_ACTIVE = "active"
THESIS_MONITOR = "monitor"
THESIS_REVIEW = "human_review_required"
THESIS_CLOSED = "closed"
VALID_THESIS_STATUSES = (THESIS_ACTIVE, THESIS_MONITOR, THESIS_REVIEW, THESIS_CLOSED)


@dataclass(frozen=True)
class PaperLeapsConfig:
    starting_cash: float = 100_000.0
    max_position_premium_pct: float = 0.03
    max_portfolio_premium_pct: float = 0.12
    max_contracts_per_fill: int = 10

    def validate(self) -> None:
        if self.starting_cash <= 0:
            raise ValueError("starting_cash must be positive")
        if self.max_position_premium_pct <= 0:
            raise ValueError("max_position_premium_pct must be positive")
        if self.max_portfolio_premium_pct <= 0:
            raise ValueError("max_portfolio_premium_pct must be positive")
        if self.max_position_premium_pct > self.max_portfolio_premium_pct:
            raise ValueError("max_position_premium_pct cannot exceed portfolio cap")
        if self.max_contracts_per_fill <= 0:
            raise ValueError("max_contracts_per_fill must be positive")


@dataclass(frozen=True)
class PaperLeapsFill:
    fill_id: str
    symbol: str
    contract_type: str
    strike: float
    expiration: date
    filled_at: datetime
    side: str
    contracts: int
    fill_price: float
    thesis: str
    thesis_status: str = THESIS_ACTIVE
    label: str = PAPER_ONLY

    @property
    def contract_key(self) -> str:
        return contract_key(self.symbol, self.contract_type, self.strike, self.expiration)

    @property
    def premium(self) -> float:
        return self.contracts * self.fill_price * CONTRACT_MULTIPLIER

    def validate(self) -> None:
        if not self.fill_id.strip():
            raise ValueError("fill_id is required")
        if not self.symbol.strip():
            raise ValueError("symbol is required")
        if self.contract_type.lower() not in {"call", "put"}:
            raise ValueError("contract_type must be call or put")
        if self.strike <= 0:
            raise ValueError("strike must be positive")
        if self.side.lower() not in {"open", "close"}:
            raise ValueError("side must be open or close")
        if self.contracts <= 0:
            raise ValueError("contracts must be positive")
        if self.fill_price < 0:
            raise ValueError("fill_price cannot be negative")
        if not self.thesis.strip():
            raise ValueError("thesis is required")
        if self.thesis_status not in VALID_THESIS_STATUSES:
            raise ValueError("thesis_status is invalid")
        if self.label not in REQUIRED_LABELS:
            raise ValueError("label must be a safe paper or research label")


@dataclass(frozen=True)
class PaperLeapsPosition:
    contract_key: str
    symbol: str
    contract_type: str
    strike: float
    expiration: date
    contracts: int
    average_price: float
    thesis: str
    thesis_status: str
    market_price: float
    market_value: float
    cost_basis: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    label: str
    human_review_required: bool


@dataclass(frozen=True)
class PaperLeapsPortfolio:
    config: PaperLeapsConfig
    as_of: date
    positions: tuple[PaperLeapsPosition, ...]
    fills: tuple[PaperLeapsFill, ...]
    cash: float
    total_cost_basis: float
    market_value: float
    equity: float
    realized_pnl: float
    unrealized_pnl: float
    total_pnl: float
    metrics: dict[str, Any]
    warnings: tuple[str, ...]
    label: str
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
        "simulated_fills_only": True,
        "live_trading_enabled": False,
        "broker_order_routing_enabled": False,
        "broker_order_call_performed": False,
        "broker_order_submitted": False,
        "LIVE TRADING": "DISABLED",
    }


def contract_key(symbol: str, contract_type: str, strike: float, expiration: date) -> str:
    return f"{symbol.upper()}:{contract_type.lower()}:{strike:.2f}:{expiration.isoformat()}"


def build_paper_leaps_portfolio(
    fills: list[PaperLeapsFill] | tuple[PaperLeapsFill, ...],
    marks: dict[str, float],
    as_of: date,
    config: PaperLeapsConfig | None = None,
) -> PaperLeapsPortfolio:
    cfg = config or PaperLeapsConfig()
    cfg.validate()
    ordered_fills = tuple(sorted(fills, key=lambda item: (item.filled_at, item.fill_id)))
    for fill in ordered_fills:
        fill.validate()

    open_lots: dict[str, dict[str, Any]] = {}
    cash = cfg.starting_cash
    realized_pnl = 0.0
    warnings: list[str] = []

    for fill in ordered_fills:
        key = fill.contract_key
        if fill.contracts > cfg.max_contracts_per_fill:
            warnings.append(f"{key}:contracts_per_fill_cap_review")

        if fill.side.lower() == "open":
            cash -= fill.premium
            lot = open_lots.setdefault(
                key,
                {
                    "symbol": fill.symbol.upper(),
                    "contract_type": fill.contract_type.lower(),
                    "strike": fill.strike,
                    "expiration": fill.expiration,
                    "contracts": 0,
                    "cost_basis": 0.0,
                    "thesis": fill.thesis,
                    "thesis_status": fill.thesis_status,
                    "label": fill.label,
                },
            )
            lot["contracts"] += fill.contracts
            lot["cost_basis"] += fill.premium
            lot["thesis"] = fill.thesis
            lot["thesis_status"] = _combine_thesis_status(lot["thesis_status"], fill.thesis_status)
            lot["label"] = _combine_label(lot["label"], fill.label)
            continue

        lot = open_lots.get(key)
        if lot is None or fill.contracts > int(lot["contracts"]):
            warnings.append(f"{key}:close_exceeds_open_contracts")
            continue

        average_price = float(lot["cost_basis"]) / int(lot["contracts"]) / CONTRACT_MULTIPLIER
        closed_cost = fill.contracts * average_price * CONTRACT_MULTIPLIER
        proceeds = fill.premium
        cash += proceeds
        realized_pnl += proceeds - closed_cost
        lot["contracts"] -= fill.contracts
        lot["cost_basis"] -= closed_cost
        lot["thesis_status"] = (
            THESIS_CLOSED if int(lot["contracts"]) == 0 else _combine_thesis_status(lot["thesis_status"], fill.thesis_status)
        )
        if int(lot["contracts"]) == 0:
            del open_lots[key]

    positions = tuple(
        _position_from_lot(key, lot, marks, warnings)
        for key, lot in sorted(open_lots.items())
    )
    total_cost_basis = sum(position.cost_basis for position in positions)
    market_value = sum(position.market_value for position in positions)
    unrealized_pnl = sum(position.unrealized_pnl for position in positions)
    equity = cash + market_value
    warnings.extend(_risk_warnings(cfg, positions, total_cost_basis))
    clean_warnings = tuple(dict.fromkeys(warnings))

    return PaperLeapsPortfolio(
        config=cfg,
        as_of=as_of,
        positions=positions,
        fills=ordered_fills,
        cash=cash,
        total_cost_basis=total_cost_basis,
        market_value=market_value,
        equity=equity,
        realized_pnl=realized_pnl,
        unrealized_pnl=unrealized_pnl,
        total_pnl=realized_pnl + unrealized_pnl,
        metrics={
            "position_count": len(positions),
            "fill_count": len(ordered_fills),
            "review_required_count": sum(1 for position in positions if position.human_review_required),
            "warning_count": len(clean_warnings),
            "premium_at_risk_pct": total_cost_basis / cfg.starting_cash,
        },
        warnings=clean_warnings,
        label=BLOCKED_BY_SAFETY_GATE if clean_warnings else PAPER_ONLY,
        safety=safety_manifest(),
    )


def build_paper_leaps_payload(portfolio: PaperLeapsPortfolio) -> dict[str, Any]:
    return {
        "phase": PHASE_ID,
        "module": MODULE_NAME,
        "as_of": portfolio.as_of.isoformat(),
        "label": portfolio.label,
        "cash": portfolio.cash,
        "total_cost_basis": portfolio.total_cost_basis,
        "market_value": portfolio.market_value,
        "equity": portfolio.equity,
        "realized_pnl": portfolio.realized_pnl,
        "unrealized_pnl": portfolio.unrealized_pnl,
        "total_pnl": portfolio.total_pnl,
        "metrics": portfolio.metrics,
        "warnings": portfolio.warnings,
        "positions": [_position_payload(position) for position in portfolio.positions],
        "fills": [_fill_payload(fill) for fill in portfolio.fills],
        "safety": portfolio.safety,
    }


def render_markdown_portfolio(portfolio: PaperLeapsPortfolio) -> str:
    payload = build_paper_leaps_payload(portfolio)
    lines = [
        f"# {PHASE_ID} {MODULE_NAME}",
        "",
        "Research labels: " + ", ".join(REQUIRED_LABELS),
        "LIVE TRADING: DISABLED",
        "",
        "## Summary",
        f"- label: {payload['label']}",
        f"- cash: {payload['cash']:.2f}",
        f"- market_value: {payload['market_value']:.2f}",
        f"- equity: {payload['equity']:.2f}",
        f"- realized_pnl: {payload['realized_pnl']:.2f}",
        f"- unrealized_pnl: {payload['unrealized_pnl']:.2f}",
        f"- total_pnl: {payload['total_pnl']:.2f}",
        "",
        "## Positions",
    ]
    if not payload["positions"]:
        lines.append("- no_open_paper_leaps_positions")
    for position in payload["positions"]:
        lines.append(
            "- "
            + position["contract_key"]
            + f": contracts={position['contracts']}, thesis_status={position['thesis_status']}, "
            + f"market_value={position['market_value']:.2f}, unrealized_pnl={position['unrealized_pnl']:.2f}, "
            + f"label={position['label']}"
        )

    lines.extend(["", "## Warnings"])
    if payload["warnings"]:
        for warning in payload["warnings"]:
            lines.append(f"- {warning}")
    else:
        lines.append("- no_paper_portfolio_warnings")

    lines.extend(
        [
            "",
            "## Safety",
            "- Paper LEAPS portfolio tracker only; simulated fills only.",
            "- No broker routing, broker calls, or live order submission.",
            "- Trade-relevant thesis state remains human-review-required.",
        ]
    )
    return "\n".join(lines)


def write_paper_leaps_report(
    portfolio: PaperLeapsPortfolio,
    out_dir: Path = DEFAULT_REPORT_DIR,
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_paper_leaps_payload(portfolio)
    json_path = out_dir / "summary.json"
    md_path = out_dir / "report.md"
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    md_path.write_text(render_markdown_portfolio(portfolio), encoding="utf-8")
    return json_path, md_path


def _position_from_lot(
    key: str,
    lot: dict[str, Any],
    marks: dict[str, float],
    warnings: list[str],
) -> PaperLeapsPosition:
    contracts = int(lot["contracts"])
    cost_basis = float(lot["cost_basis"])
    average_price = cost_basis / contracts / CONTRACT_MULTIPLIER
    market_price = float(marks.get(key, average_price))
    if key not in marks:
        warnings.append(f"{key}:missing_mark_price_uses_average_cost")
    if market_price < 0:
        raise ValueError("mark prices cannot be negative")
    market_value = contracts * market_price * CONTRACT_MULTIPLIER
    unrealized_pnl = market_value - cost_basis
    label = _position_label(str(lot["thesis_status"]), str(lot["label"]))
    return PaperLeapsPosition(
        contract_key=key,
        symbol=str(lot["symbol"]),
        contract_type=str(lot["contract_type"]),
        strike=float(lot["strike"]),
        expiration=lot["expiration"],
        contracts=contracts,
        average_price=average_price,
        thesis=str(lot["thesis"]),
        thesis_status=str(lot["thesis_status"]),
        market_price=market_price,
        market_value=market_value,
        cost_basis=cost_basis,
        unrealized_pnl=unrealized_pnl,
        unrealized_pnl_pct=unrealized_pnl / cost_basis if cost_basis else 0.0,
        label=label,
        human_review_required=True,
    )


def _risk_warnings(
    config: PaperLeapsConfig,
    positions: tuple[PaperLeapsPosition, ...],
    total_cost_basis: float,
) -> list[str]:
    warnings: list[str] = []
    for position in positions:
        premium_pct = position.cost_basis / config.starting_cash
        if premium_pct > config.max_position_premium_pct:
            warnings.append(f"{position.contract_key}:position_premium_cap_review")
        if position.thesis_status == THESIS_REVIEW:
            warnings.append(f"{position.contract_key}:thesis_human_review_required")
    if total_cost_basis / config.starting_cash > config.max_portfolio_premium_pct:
        warnings.append("portfolio_premium_cap_review")
    return warnings


def _combine_thesis_status(current: str, incoming: str) -> str:
    rank = {
        THESIS_ACTIVE: 0,
        THESIS_MONITOR: 1,
        THESIS_REVIEW: 2,
        THESIS_CLOSED: 3,
    }
    return incoming if rank[incoming] > rank[current] else current


def _combine_label(current: str, incoming: str) -> str:
    if BLOCKED_BY_SAFETY_GATE in {current, incoming}:
        return BLOCKED_BY_SAFETY_GATE
    if HUMAN_REVIEW_REQUIRED in {current, incoming}:
        return HUMAN_REVIEW_REQUIRED
    if PAPER_ONLY in {current, incoming}:
        return PAPER_ONLY
    if MONITOR_ONLY in {current, incoming}:
        return MONITOR_ONLY
    return RESEARCH_ONLY


def _position_label(thesis_status: str, fill_label: str) -> str:
    if thesis_status == THESIS_REVIEW:
        return HUMAN_REVIEW_REQUIRED
    return _combine_label(PAPER_ONLY, fill_label)


def _fill_payload(fill: PaperLeapsFill) -> dict[str, Any]:
    return {
        "fill_id": fill.fill_id,
        "contract_key": fill.contract_key,
        "symbol": fill.symbol.upper(),
        "contract_type": fill.contract_type.lower(),
        "strike": fill.strike,
        "expiration": fill.expiration.isoformat(),
        "filled_at": fill.filled_at.isoformat(),
        "side": fill.side.lower(),
        "contracts": fill.contracts,
        "fill_price": fill.fill_price,
        "premium": fill.premium,
        "thesis": fill.thesis,
        "thesis_status": fill.thesis_status,
        "label": fill.label,
        "simulated_fill": True,
    }


def _position_payload(position: PaperLeapsPosition) -> dict[str, Any]:
    return {
        "contract_key": position.contract_key,
        "symbol": position.symbol,
        "contract_type": position.contract_type,
        "strike": position.strike,
        "expiration": position.expiration.isoformat(),
        "contracts": position.contracts,
        "average_price": position.average_price,
        "thesis": position.thesis,
        "thesis_status": position.thesis_status,
        "market_price": position.market_price,
        "market_value": position.market_value,
        "cost_basis": position.cost_basis,
        "unrealized_pnl": position.unrealized_pnl,
        "unrealized_pnl_pct": position.unrealized_pnl_pct,
        "label": position.label,
        "human_review_required": position.human_review_required,
    }
