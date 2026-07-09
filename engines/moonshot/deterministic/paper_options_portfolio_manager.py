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


PHASE_ID = "BR-07"
MODULE_NAME = "Paper Options Portfolio Manager"
CONTRACT_MULTIPLIER = 100
REQUIRED_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
SAFE_ACTION_LABELS = REQUIRED_LABELS
DEFAULT_REPORT_DIR = Path("reports/br07_paper_options_portfolio_manager")


@dataclass(frozen=True)
class PaperOptionsConfig:
    starting_cash: float = 100_000.0
    max_position_premium_pct: float = 0.03
    max_portfolio_premium_pct: float = 0.12
    max_abs_delta_exposure_pct: float = 0.30
    max_abs_vega_exposure: float = 8_000.0

    def validate(self) -> None:
        _require_positive("starting_cash", self.starting_cash)
        _require_positive("max_position_premium_pct", self.max_position_premium_pct)
        _require_positive("max_portfolio_premium_pct", self.max_portfolio_premium_pct)
        _require_positive("max_abs_delta_exposure_pct", self.max_abs_delta_exposure_pct)
        _require_positive("max_abs_vega_exposure", self.max_abs_vega_exposure)
        if self.max_position_premium_pct > self.max_portfolio_premium_pct:
            raise ValueError("max_position_premium_pct cannot exceed portfolio cap")


@dataclass(frozen=True)
class PaperOptionGreeks:
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
class PaperOptionFill:
    fill_id: str
    contract_id: str
    symbol: str
    underlying_symbol: str
    contract_type: str
    strike: float
    expiration: date
    filled_at: datetime
    side: str
    contracts: int
    fill_price: float
    thesis_id: str
    label: str = PAPER_ONLY

    @property
    def premium(self) -> float:
        return round(self.contracts * self.fill_price * CONTRACT_MULTIPLIER, 2)

    def validate(self) -> None:
        _require_text("fill_id", self.fill_id)
        _require_text("contract_id", self.contract_id)
        _require_symbol(self.symbol)
        _require_symbol(self.underlying_symbol)
        if self.contract_type.lower() not in {"call", "put"}:
            raise ValueError("contract_type must be call or put")
        _require_positive("strike", self.strike)
        if self.side.lower() not in {"entry", "exit"}:
            raise ValueError("side must be entry or exit")
        if self.contracts <= 0:
            raise ValueError("contracts must be positive")
        _require_non_negative("fill_price", self.fill_price)
        _require_text("thesis_id", self.thesis_id)
        _require_safe_label(self.label)


@dataclass(frozen=True)
class PaperOptionMark:
    contract_id: str
    marked_at: datetime
    mark_price: float
    greeks: PaperOptionGreeks
    label: str = MONITOR_ONLY

    def validate(self) -> None:
        _require_text("contract_id", self.contract_id)
        _require_non_negative("mark_price", self.mark_price)
        self.greeks.validate()
        _require_safe_label(self.label)


@dataclass(frozen=True)
class PaperOptionPosition:
    contract_id: str
    symbol: str
    underlying_symbol: str
    contract_type: str
    strike: float
    expiration: date
    contracts: int
    average_price: float
    cost_basis: float
    mark_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    greeks: PaperOptionGreeks
    delta_exposure: float
    gamma_exposure: float
    theta_exposure: float
    vega_exposure: float
    label: str
    human_review_required: bool = True

    def validate(self) -> None:
        _require_text("contract_id", self.contract_id)
        _require_symbol(self.symbol)
        _require_symbol(self.underlying_symbol)
        if self.contracts <= 0:
            raise ValueError("position contracts must be positive")
        _require_non_negative("average_price", self.average_price)
        _require_non_negative("cost_basis", self.cost_basis)
        _require_non_negative("mark_price", self.mark_price)
        _require_non_negative("market_value", self.market_value)
        self.greeks.validate()
        _require_safe_label(self.label)
        if not self.human_review_required:
            raise ValueError("paper option positions must require human review")


@dataclass(frozen=True)
class PaperOptionHistoryEvent:
    event_id: str
    event_type: str
    contract_id: str
    occurred_at: datetime
    contracts: int
    price: float
    cash_change: float
    realized_pnl: float
    open_contracts_after: int
    label: str = PAPER_ONLY

    def validate(self) -> None:
        _require_text("event_id", self.event_id)
        if self.event_type not in {"ENTRY", "EXIT", "MARK"}:
            raise ValueError("event_type must be ENTRY, EXIT, or MARK")
        _require_text("contract_id", self.contract_id)
        if self.contracts < 0:
            raise ValueError("history contracts cannot be negative")
        _require_non_negative("price", self.price)
        if self.open_contracts_after < 0:
            raise ValueError("open_contracts_after cannot be negative")
        _require_safe_label(self.label)


@dataclass(frozen=True)
class PaperOptionsExposure:
    gross_market_value: float
    net_liquidation_value: float
    premium_at_risk: float
    premium_at_risk_pct: float
    delta_exposure: float
    delta_exposure_pct: float
    gamma_exposure: float
    theta_exposure: float
    vega_exposure: float
    by_underlying: dict[str, dict[str, float]]


@dataclass(frozen=True)
class PaperOptionsPortfolioReport:
    as_of: datetime
    config: PaperOptionsConfig
    positions: tuple[PaperOptionPosition, ...]
    fills: tuple[PaperOptionFill, ...]
    marks: tuple[PaperOptionMark, ...]
    history: tuple[PaperOptionHistoryEvent, ...]
    exposure: PaperOptionsExposure
    cash: float
    realized_pnl: float
    unrealized_pnl: float
    total_pnl: float
    warnings: tuple[str, ...]
    safety: dict[str, Any]
    label: str = PAPER_ONLY

    def validate(self) -> None:
        self.config.validate()
        for fill in self.fills:
            fill.validate()
        for mark in self.marks:
            mark.validate()
        for position in self.positions:
            position.validate()
        for event in self.history:
            event.validate()
        _require_safe_label(self.label)
        if self.safety.get("live_trading_enabled") is not False:
            raise ValueError("paper options manager cannot enable live trading")
        if self.safety.get("broker_order_call_performed") is not False:
            raise ValueError("paper options manager cannot perform broker calls")


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
        "simulated_entries_only": True,
        "simulated_exits_only": True,
        "local_marks_only": True,
        "real_paper_wrapper_connected": False,
        "real_paper_wrapper_attempted": False,
        "real_paper_order_submitted": False,
        "broker_order_call_performed": False,
        "broker_order_submitted": False,
        "broker_order_routing_enabled": False,
        "live_trading_enabled": False,
        "LIVE TRADING": "DISABLED",
    }


def build_paper_options_portfolio_report(
    fills: tuple[PaperOptionFill, ...] | list[PaperOptionFill],
    marks: tuple[PaperOptionMark, ...] | list[PaperOptionMark],
    as_of: datetime,
    config: PaperOptionsConfig | None = None,
) -> PaperOptionsPortfolioReport:
    cfg = config or PaperOptionsConfig()
    cfg.validate()
    ordered_fills = tuple(sorted(fills, key=lambda item: (item.filled_at, item.fill_id)))
    ordered_marks = tuple(sorted(marks, key=lambda item: (item.marked_at, item.contract_id)))
    for fill in ordered_fills:
        fill.validate()
    for mark in ordered_marks:
        mark.validate()

    latest_marks = _latest_marks(ordered_marks, as_of)
    lots: dict[str, dict[str, Any]] = {}
    cash = cfg.starting_cash
    realized_pnl = 0.0
    warnings: list[str] = []
    history: list[PaperOptionHistoryEvent] = []

    for fill in ordered_fills:
        lot = lots.get(fill.contract_id)
        if fill.side.lower() == "entry":
            cash -= fill.premium
            lot = lots.setdefault(
                fill.contract_id,
                {
                    "symbol": fill.symbol,
                    "underlying_symbol": fill.underlying_symbol,
                    "contract_type": fill.contract_type.lower(),
                    "strike": fill.strike,
                    "expiration": fill.expiration,
                    "contracts": 0,
                    "cost_basis": 0.0,
                    "label": fill.label,
                },
            )
            lot["contracts"] += fill.contracts
            lot["cost_basis"] += fill.premium
            lot["label"] = _combine_label(str(lot["label"]), fill.label)
            history.append(_history_from_fill(fill, -fill.premium, 0.0, int(lot["contracts"])))
            continue

        if lot is None or fill.contracts > int(lot["contracts"]):
            warnings.append(f"{fill.contract_id}:exit_exceeds_open_contracts")
            history.append(_history_from_fill(fill, 0.0, 0.0, 0))
            continue

        average_price = float(lot["cost_basis"]) / int(lot["contracts"]) / CONTRACT_MULTIPLIER
        closed_cost = round(fill.contracts * average_price * CONTRACT_MULTIPLIER, 2)
        proceeds = fill.premium
        fill_realized = round(proceeds - closed_cost, 2)
        cash += proceeds
        realized_pnl += fill_realized
        lot["contracts"] -= fill.contracts
        lot["cost_basis"] = round(float(lot["cost_basis"]) - closed_cost, 2)
        lot["label"] = _combine_label(str(lot["label"]), fill.label)
        history.append(_history_from_fill(fill, proceeds, fill_realized, int(lot["contracts"])))
        if int(lot["contracts"]) == 0:
            del lots[fill.contract_id]

    positions = tuple(
        _position_from_lot(contract_id, lot, latest_marks, warnings)
        for contract_id, lot in sorted(lots.items())
    )
    for mark in ordered_marks:
        open_contracts = next(
            (position.contracts for position in positions if position.contract_id == mark.contract_id),
            0,
        )
        history.append(
            PaperOptionHistoryEvent(
                event_id=f"mark-{mark.contract_id}-{mark.marked_at.isoformat()}",
                event_type="MARK",
                contract_id=mark.contract_id,
                occurred_at=mark.marked_at,
                contracts=0,
                price=mark.mark_price,
                cash_change=0.0,
                realized_pnl=0.0,
                open_contracts_after=open_contracts,
                label=MONITOR_ONLY,
            )
        )

    exposure = _build_exposure(positions, cash, cfg.starting_cash)
    warnings.extend(_risk_warnings(cfg, positions, exposure))
    clean_warnings = tuple(dict.fromkeys(warnings))
    report = PaperOptionsPortfolioReport(
        as_of=as_of,
        config=cfg,
        positions=positions,
        fills=ordered_fills,
        marks=ordered_marks,
        history=tuple(sorted(history, key=lambda item: (item.occurred_at, item.event_id))),
        exposure=exposure,
        cash=round(cash, 2),
        realized_pnl=round(realized_pnl, 2),
        unrealized_pnl=round(sum(position.unrealized_pnl for position in positions), 2),
        total_pnl=round(realized_pnl + sum(position.unrealized_pnl for position in positions), 2),
        warnings=clean_warnings,
        safety=safety_manifest(),
        label=BLOCKED_BY_SAFETY_GATE if clean_warnings else PAPER_ONLY,
    )
    report.validate()
    return report


def paper_options_portfolio_payload(report: PaperOptionsPortfolioReport) -> dict[str, Any]:
    report.validate()
    return {
        "phase": PHASE_ID,
        "module": MODULE_NAME,
        "as_of": report.as_of.isoformat(),
        "label": report.label,
        "cash": report.cash,
        "realized_pnl": report.realized_pnl,
        "unrealized_pnl": report.unrealized_pnl,
        "total_pnl": report.total_pnl,
        "metrics": {
            "position_count": len(report.positions),
            "fill_count": len(report.fills),
            "mark_count": len(report.marks),
            "history_event_count": len(report.history),
            "warning_count": len(report.warnings),
            "human_review_required_count": len(report.positions),
        },
        "exposure": _exposure_payload(report.exposure),
        "warnings": report.warnings,
        "positions": [_position_payload(position) for position in report.positions],
        "fills": [_fill_payload(fill) for fill in report.fills],
        "marks": [_mark_payload(mark) for mark in report.marks],
        "history": [_history_payload(event) for event in report.history],
        "safety": report.safety,
    }


def render_markdown_paper_options_portfolio(report: PaperOptionsPortfolioReport) -> str:
    payload = paper_options_portfolio_payload(report)
    lines = [
        f"# {PHASE_ID} {MODULE_NAME}",
        "",
        "Research labels: " + ", ".join(REQUIRED_LABELS),
        "LIVE TRADING: DISABLED",
        "",
        "## Summary",
        f"- label: {payload['label']}",
        f"- cash: {payload['cash']:.2f}",
        f"- realized_pnl: {payload['realized_pnl']:.2f}",
        f"- unrealized_pnl: {payload['unrealized_pnl']:.2f}",
        f"- total_pnl: {payload['total_pnl']:.2f}",
        f"- premium_at_risk_pct: {payload['exposure']['premium_at_risk_pct']:.6f}",
        f"- delta_exposure_pct: {payload['exposure']['delta_exposure_pct']:.6f}",
        "",
        "## Positions",
    ]
    if not payload["positions"]:
        lines.append("- no_open_paper_option_positions")
    for position in payload["positions"]:
        lines.append(
            "- "
            + position["contract_id"]
            + f": contracts={position['contracts']}, mark={position['mark_price']:.2f}, "
            + f"unrealized_pnl={position['unrealized_pnl']:.2f}, "
            + f"delta_exposure={position['delta_exposure']:.2f}, label={position['label']}"
        )

    lines.extend(["", "## Warnings"])
    if payload["warnings"]:
        for warning in payload["warnings"]:
            lines.append(f"- {warning}")
    else:
        lines.append("- no_paper_options_portfolio_warnings")

    lines.extend(
        [
            "",
            "## Safety",
            "- Paper options portfolio manager only; simulated entries, exits, marks, and PnL.",
            "- Local data only; no broker routing, broker calls, or live order submission.",
            "- Trade-relevant output remains paper-only and human-review-required.",
        ]
    )
    return "\n".join(lines)


def write_paper_options_portfolio_report(
    report: PaperOptionsPortfolioReport,
    out_dir: Path = DEFAULT_REPORT_DIR,
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "paper_options_portfolio.json"
    md_path = out_dir / "paper_options_portfolio.md"
    json_path.write_text(
        json.dumps(paper_options_portfolio_payload(report), indent=2, default=str),
        encoding="utf-8",
    )
    md_path.write_text(render_markdown_paper_options_portfolio(report), encoding="utf-8")
    return json_path, md_path


def _latest_marks(
    marks: tuple[PaperOptionMark, ...],
    as_of: datetime,
) -> dict[str, PaperOptionMark]:
    latest: dict[str, PaperOptionMark] = {}
    for mark in marks:
        if mark.marked_at > as_of:
            continue
        current = latest.get(mark.contract_id)
        if current is None or mark.marked_at > current.marked_at:
            latest[mark.contract_id] = mark
    return latest


def _position_from_lot(
    contract_id: str,
    lot: dict[str, Any],
    marks: dict[str, PaperOptionMark],
    warnings: list[str],
) -> PaperOptionPosition:
    contracts = int(lot["contracts"])
    cost_basis = round(float(lot["cost_basis"]), 2)
    average_price = round(cost_basis / contracts / CONTRACT_MULTIPLIER, 4)
    mark = marks.get(contract_id)
    if mark is None:
        warnings.append(f"{contract_id}:missing_mark_uses_average_cost")
        mark_price = average_price
        greeks = PaperOptionGreeks(delta=0.0, gamma=0.0, theta=0.0, vega=0.0)
    else:
        mark_price = mark.mark_price
        greeks = mark.greeks
    market_value = round(contracts * mark_price * CONTRACT_MULTIPLIER, 2)
    unrealized_pnl = round(market_value - cost_basis, 2)
    multiplier_contracts = contracts * CONTRACT_MULTIPLIER
    return PaperOptionPosition(
        contract_id=contract_id,
        symbol=str(lot["symbol"]),
        underlying_symbol=str(lot["underlying_symbol"]),
        contract_type=str(lot["contract_type"]),
        strike=float(lot["strike"]),
        expiration=lot["expiration"],
        contracts=contracts,
        average_price=average_price,
        cost_basis=cost_basis,
        mark_price=mark_price,
        market_value=market_value,
        unrealized_pnl=unrealized_pnl,
        unrealized_pnl_pct=round(unrealized_pnl / cost_basis, 6) if cost_basis else 0.0,
        greeks=greeks,
        delta_exposure=round(greeks.delta * multiplier_contracts, 4),
        gamma_exposure=round(greeks.gamma * multiplier_contracts, 4),
        theta_exposure=round(greeks.theta * multiplier_contracts, 4),
        vega_exposure=round(greeks.vega * multiplier_contracts, 4),
        label=_combine_label(PAPER_ONLY, str(lot["label"])),
    )


def _build_exposure(
    positions: tuple[PaperOptionPosition, ...],
    cash: float,
    starting_cash: float,
) -> PaperOptionsExposure:
    by_underlying: dict[str, dict[str, float]] = {}
    for position in positions:
        bucket = by_underlying.setdefault(
            position.underlying_symbol,
            {
                "market_value": 0.0,
                "premium_at_risk": 0.0,
                "delta_exposure": 0.0,
                "gamma_exposure": 0.0,
                "theta_exposure": 0.0,
                "vega_exposure": 0.0,
            },
        )
        bucket["market_value"] += position.market_value
        bucket["premium_at_risk"] += position.cost_basis
        bucket["delta_exposure"] += position.delta_exposure
        bucket["gamma_exposure"] += position.gamma_exposure
        bucket["theta_exposure"] += position.theta_exposure
        bucket["vega_exposure"] += position.vega_exposure

    rounded = {
        symbol: {name: round(value, 4) for name, value in values.items()}
        for symbol, values in sorted(by_underlying.items())
    }
    gross_market_value = round(sum(position.market_value for position in positions), 2)
    premium_at_risk = round(sum(position.cost_basis for position in positions), 2)
    delta_exposure = round(sum(position.delta_exposure for position in positions), 4)
    return PaperOptionsExposure(
        gross_market_value=gross_market_value,
        net_liquidation_value=round(cash + gross_market_value, 2),
        premium_at_risk=premium_at_risk,
        premium_at_risk_pct=round(premium_at_risk / starting_cash, 6),
        delta_exposure=delta_exposure,
        delta_exposure_pct=round(delta_exposure / starting_cash, 6),
        gamma_exposure=round(sum(position.gamma_exposure for position in positions), 4),
        theta_exposure=round(sum(position.theta_exposure for position in positions), 4),
        vega_exposure=round(sum(position.vega_exposure for position in positions), 4),
        by_underlying=rounded,
    )


def _risk_warnings(
    config: PaperOptionsConfig,
    positions: tuple[PaperOptionPosition, ...],
    exposure: PaperOptionsExposure,
) -> list[str]:
    warnings: list[str] = []
    for position in positions:
        premium_pct = position.cost_basis / config.starting_cash
        if premium_pct > config.max_position_premium_pct:
            warnings.append(f"{position.contract_id}:position_premium_cap_review")
    if exposure.premium_at_risk_pct > config.max_portfolio_premium_pct:
        warnings.append("portfolio_premium_cap_review")
    if abs(exposure.delta_exposure_pct) > config.max_abs_delta_exposure_pct:
        warnings.append("delta_exposure_cap_review")
    if abs(exposure.vega_exposure) > config.max_abs_vega_exposure:
        warnings.append("vega_exposure_cap_review")
    return warnings


def _history_from_fill(
    fill: PaperOptionFill,
    cash_change: float,
    realized_pnl: float,
    open_contracts_after: int,
) -> PaperOptionHistoryEvent:
    return PaperOptionHistoryEvent(
        event_id=fill.fill_id,
        event_type="ENTRY" if fill.side.lower() == "entry" else "EXIT",
        contract_id=fill.contract_id,
        occurred_at=fill.filled_at,
        contracts=fill.contracts,
        price=fill.fill_price,
        cash_change=round(cash_change, 2),
        realized_pnl=round(realized_pnl, 2),
        open_contracts_after=open_contracts_after,
        label=fill.label,
    )


def _fill_payload(fill: PaperOptionFill) -> dict[str, Any]:
    return {
        "fill_id": fill.fill_id,
        "contract_id": fill.contract_id,
        "symbol": fill.symbol,
        "underlying_symbol": fill.underlying_symbol,
        "contract_type": fill.contract_type.lower(),
        "strike": fill.strike,
        "expiration": fill.expiration.isoformat(),
        "filled_at": fill.filled_at.isoformat(),
        "side": fill.side.lower(),
        "contracts": fill.contracts,
        "fill_price": fill.fill_price,
        "premium": fill.premium,
        "thesis_id": fill.thesis_id,
        "label": fill.label,
        "simulated_fill": True,
    }


def _mark_payload(mark: PaperOptionMark) -> dict[str, Any]:
    return {
        "contract_id": mark.contract_id,
        "marked_at": mark.marked_at.isoformat(),
        "mark_price": mark.mark_price,
        "greeks": _greeks_payload(mark.greeks),
        "label": mark.label,
        "local_mark": True,
    }


def _position_payload(position: PaperOptionPosition) -> dict[str, Any]:
    return {
        "contract_id": position.contract_id,
        "symbol": position.symbol,
        "underlying_symbol": position.underlying_symbol,
        "contract_type": position.contract_type,
        "strike": position.strike,
        "expiration": position.expiration.isoformat(),
        "contracts": position.contracts,
        "average_price": position.average_price,
        "cost_basis": position.cost_basis,
        "mark_price": position.mark_price,
        "market_value": position.market_value,
        "unrealized_pnl": position.unrealized_pnl,
        "unrealized_pnl_pct": position.unrealized_pnl_pct,
        "greeks": _greeks_payload(position.greeks),
        "delta_exposure": position.delta_exposure,
        "gamma_exposure": position.gamma_exposure,
        "theta_exposure": position.theta_exposure,
        "vega_exposure": position.vega_exposure,
        "label": position.label,
        "human_review_required": position.human_review_required,
    }


def _history_payload(event: PaperOptionHistoryEvent) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "event_type": event.event_type,
        "contract_id": event.contract_id,
        "occurred_at": event.occurred_at.isoformat(),
        "contracts": event.contracts,
        "price": event.price,
        "cash_change": event.cash_change,
        "realized_pnl": event.realized_pnl,
        "open_contracts_after": event.open_contracts_after,
        "label": event.label,
    }


def _exposure_payload(exposure: PaperOptionsExposure) -> dict[str, Any]:
    return {
        "gross_market_value": exposure.gross_market_value,
        "net_liquidation_value": exposure.net_liquidation_value,
        "premium_at_risk": exposure.premium_at_risk,
        "premium_at_risk_pct": exposure.premium_at_risk_pct,
        "delta_exposure": exposure.delta_exposure,
        "delta_exposure_pct": exposure.delta_exposure_pct,
        "gamma_exposure": exposure.gamma_exposure,
        "theta_exposure": exposure.theta_exposure,
        "vega_exposure": exposure.vega_exposure,
        "by_underlying": exposure.by_underlying,
    }


def _greeks_payload(greeks: PaperOptionGreeks) -> dict[str, float]:
    return {
        "delta": greeks.delta,
        "gamma": greeks.gamma,
        "theta": greeks.theta,
        "vega": greeks.vega,
        "rho": greeks.rho,
    }


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
