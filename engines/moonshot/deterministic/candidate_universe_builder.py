from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


PHASE_ID = "BR-02"
MODULE_NAME = "Candidate Universe Builder"
REQUIRED_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
SAFE_ACTION_LABELS = REQUIRED_LABELS
DEFAULT_FIXTURE_PATH = Path("engines/moonshot/deterministic/fixtures/br02_candidate_universe.json")
DEFAULT_REPORT_DIR = Path("reports/br02_candidate_universe")


@dataclass(frozen=True)
class CandidateUniverseConfig:
    allowed_sectors: tuple[str, ...] = ()
    min_average_volume_30d: int = 1_000_000
    min_dollar_volume_30d: float = 50_000_000.0
    min_price_trend_60d_pct: float = -0.05
    max_realized_volatility_30d: float = 0.75
    required_catalyst_tags: tuple[str, ...] = ()
    allowed_market_cap_buckets: tuple[str, ...] = ()
    require_options_available: bool = True
    max_candidates: int = 25

    def validate(self) -> None:
        if self.min_average_volume_30d < 0:
            raise ValueError("min_average_volume_30d cannot be negative")
        if self.min_dollar_volume_30d < 0:
            raise ValueError("min_dollar_volume_30d cannot be negative")
        if self.max_realized_volatility_30d < 0:
            raise ValueError("max_realized_volatility_30d cannot be negative")
        if self.max_candidates <= 0:
            raise ValueError("max_candidates must be positive")
        _require_unique_text("allowed_sectors", self.allowed_sectors)
        _require_unique_text("required_catalyst_tags", self.required_catalyst_tags)
        _require_unique_text("allowed_market_cap_buckets", self.allowed_market_cap_buckets)


@dataclass(frozen=True)
class CandidateRecord:
    symbol: str
    name: str
    sector: str
    last_price: float
    average_volume_30d: int
    dollar_volume_30d: float
    price_trend_60d_pct: float
    realized_volatility_30d: float
    catalyst_tags: tuple[str, ...]
    market_cap_bucket: str
    options_available: bool
    as_of: datetime
    market_cap: float | None = None
    label: str = RESEARCH_ONLY

    def validate(self) -> None:
        _require_symbol(self.symbol)
        _require_text("name", self.name)
        _require_text("sector", self.sector)
        _require_positive("last_price", self.last_price)
        _require_non_negative("average_volume_30d", self.average_volume_30d)
        _require_non_negative("dollar_volume_30d", self.dollar_volume_30d)
        _require_non_negative("realized_volatility_30d", self.realized_volatility_30d)
        _require_unique_text("catalyst_tags", self.catalyst_tags)
        _require_text("market_cap_bucket", self.market_cap_bucket)
        if self.market_cap is not None:
            _require_non_negative("market_cap", self.market_cap)
        _require_safe_label(self.label)


@dataclass(frozen=True)
class CandidateDecision:
    candidate: CandidateRecord
    included: bool
    label: str
    score: int
    reasons: tuple[str, ...]
    human_review_required: bool = True

    def validate(self) -> None:
        self.candidate.validate()
        _require_safe_label(self.label)
        if not 0 <= self.score <= 100:
            raise ValueError("score must be between 0 and 100")
        if self.included and self.label != MONITOR_ONLY:
            raise ValueError("included candidates must remain monitor-only")
        if not self.included and self.label != BLOCKED_BY_SAFETY_GATE:
            raise ValueError("excluded candidates must be blocked by safety gate")
        if not self.human_review_required:
            raise ValueError("candidate decisions must require human review")


@dataclass(frozen=True)
class CandidateUniverseReport:
    as_of: datetime
    config: CandidateUniverseConfig
    decisions: tuple[CandidateDecision, ...]
    safety: dict[str, Any]
    label: str = BLOCKED_BY_SAFETY_GATE

    @property
    def included_decisions(self) -> tuple[CandidateDecision, ...]:
        return tuple(decision for decision in self.decisions if decision.included)

    @property
    def blocked_decisions(self) -> tuple[CandidateDecision, ...]:
        return tuple(decision for decision in self.decisions if not decision.included)

    def validate(self) -> None:
        self.config.validate()
        if not self.decisions:
            raise ValueError("candidate universe report requires at least one decision")
        for decision in self.decisions:
            decision.validate()
        _require_safe_label(self.label)
        if self.label != BLOCKED_BY_SAFETY_GATE:
            raise ValueError("candidate universe report must remain blocked by safety gate")


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


def load_candidate_records(path: Path = DEFAULT_FIXTURE_PATH) -> tuple[CandidateRecord, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = tuple(_record_from_payload(item) for item in payload["candidates"])
    if not records:
        raise ValueError("candidate fixture requires at least one candidate")
    for record in records:
        record.validate()
    return records


def build_candidate_universe_report(
    candidates: tuple[CandidateRecord, ...] | list[CandidateRecord],
    config: CandidateUniverseConfig | None = None,
    as_of: datetime | None = None,
) -> CandidateUniverseReport:
    cfg = config or CandidateUniverseConfig()
    cfg.validate()
    if not candidates:
        raise ValueError("candidate universe requires at least one candidate")

    validated = tuple(candidates)
    for candidate in validated:
        candidate.validate()
    _require_unique_symbols(validated)

    decision_by_symbol = {
        decision.candidate.symbol: decision for decision in (_decision_for_candidate(item, cfg) for item in validated)
    }
    included = sorted(
        (decision for decision in decision_by_symbol.values() if decision.included),
        key=lambda decision: (-decision.score, decision.candidate.symbol),
    )
    limited_symbols = {decision.candidate.symbol for decision in included[: cfg.max_candidates]}
    decisions = tuple(
        _apply_candidate_limit(decision, limited_symbols)
        for decision in sorted(decision_by_symbol.values(), key=lambda item: item.candidate.symbol)
    )
    report = CandidateUniverseReport(
        as_of=as_of or max(candidate.as_of for candidate in validated),
        config=cfg,
        decisions=decisions,
        safety=safety_manifest(),
    )
    report.validate()
    return report


def load_candidate_universe_report(
    path: Path = DEFAULT_FIXTURE_PATH,
    config: CandidateUniverseConfig | None = None,
) -> CandidateUniverseReport:
    return build_candidate_universe_report(load_candidate_records(path), config=config)


def candidate_universe_payload(report: CandidateUniverseReport) -> dict[str, Any]:
    report.validate()
    included = sorted(report.included_decisions, key=lambda item: (-item.score, item.candidate.symbol))
    blocked = sorted(report.blocked_decisions, key=lambda item: item.candidate.symbol)
    return {
        "phase": PHASE_ID,
        "module": MODULE_NAME,
        "as_of": report.as_of.isoformat(),
        "label": report.label,
        "safety": report.safety,
        "config": _config_payload(report.config),
        "metrics": {
            "candidate_count": len(report.decisions),
            "included_count": len(included),
            "blocked_count": len(blocked),
            "human_review_required_count": len(report.decisions),
        },
        "watchlists": {
            "primary": [decision.candidate.symbol for decision in included],
            "by_sector": _watchlist_by_sector(included),
            "catalyst_review": _watchlist_by_catalyst(included),
        },
        "included_candidates": [_decision_payload(decision) for decision in included],
        "blocked_candidates": [_decision_payload(decision) for decision in blocked],
    }


def render_markdown_candidate_universe(report: CandidateUniverseReport) -> str:
    payload = candidate_universe_payload(report)
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

    lines.extend(["", "## Primary Watchlist"])
    if payload["watchlists"]["primary"]:
        for symbol in payload["watchlists"]["primary"]:
            lines.append(f"- {symbol}")
    else:
        lines.append("- no_candidates_passed_filters")

    lines.extend(["", "## Included Candidates"])
    for decision in payload["included_candidates"]:
        lines.append(
            "- "
            + decision["symbol"]
            + f": score={decision['score']}, sector={decision['sector']}, "
            + f"trend_60d_pct={decision['price_trend_60d_pct']:.4f}, "
            + f"volatility_30d={decision['realized_volatility_30d']:.4f}, "
            + f"label={decision['label']}"
        )
        lines.append("  catalysts: " + ", ".join(decision["catalyst_tags"]))

    lines.extend(["", "## Blocked Candidates"])
    if payload["blocked_candidates"]:
        for decision in payload["blocked_candidates"]:
            lines.append(
                "- "
                + decision["symbol"]
                + f": label={decision['label']}, reasons="
                + ", ".join(decision["reasons"])
            )
    else:
        lines.append("- no_blocked_candidates")

    lines.extend(
        [
            "",
            "## Safety",
            "- Static candidate universe report only; no broker routing or order submission.",
            "- Candidate inclusion is monitor-only research and requires human review.",
            "- Report-level state remains blocked by safety gate.",
        ]
    )
    return "\n".join(lines)


def write_candidate_universe_report(
    report: CandidateUniverseReport,
    out_dir: Path = DEFAULT_REPORT_DIR,
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "candidate_universe.json"
    md_path = out_dir / "candidate_universe.md"
    json_path.write_text(
        json.dumps(candidate_universe_payload(report), indent=2, default=str),
        encoding="utf-8",
    )
    md_path.write_text(render_markdown_candidate_universe(report), encoding="utf-8")
    return json_path, md_path


def _decision_for_candidate(
    candidate: CandidateRecord,
    config: CandidateUniverseConfig,
) -> CandidateDecision:
    reasons = _blocking_reasons(candidate, config)
    included = not reasons
    return CandidateDecision(
        candidate=candidate,
        included=included,
        label=MONITOR_ONLY if included else BLOCKED_BY_SAFETY_GATE,
        score=_score_candidate(candidate, config),
        reasons=tuple(reasons),
    )


def _apply_candidate_limit(
    decision: CandidateDecision,
    included_symbols: set[str],
) -> CandidateDecision:
    if not decision.included or decision.candidate.symbol in included_symbols:
        return decision
    return CandidateDecision(
        candidate=decision.candidate,
        included=False,
        label=BLOCKED_BY_SAFETY_GATE,
        score=decision.score,
        reasons=(*decision.reasons, "candidate_limit_exceeded"),
    )


def _blocking_reasons(candidate: CandidateRecord, config: CandidateUniverseConfig) -> list[str]:
    reasons: list[str] = []
    if config.allowed_sectors and candidate.sector not in config.allowed_sectors:
        reasons.append("sector_filter_mismatch")
    if candidate.average_volume_30d < config.min_average_volume_30d:
        reasons.append("average_volume_below_minimum")
    if candidate.dollar_volume_30d < config.min_dollar_volume_30d:
        reasons.append("dollar_volume_below_minimum")
    if candidate.price_trend_60d_pct < config.min_price_trend_60d_pct:
        reasons.append("price_trend_below_minimum")
    if candidate.realized_volatility_30d > config.max_realized_volatility_30d:
        reasons.append("volatility_above_maximum")
    if config.required_catalyst_tags and not set(config.required_catalyst_tags).issubset(
        set(candidate.catalyst_tags)
    ):
        reasons.append("required_catalyst_tags_missing")
    if (
        config.allowed_market_cap_buckets
        and candidate.market_cap_bucket not in config.allowed_market_cap_buckets
    ):
        reasons.append("market_cap_bucket_filter_mismatch")
    if config.require_options_available and not candidate.options_available:
        reasons.append("options_not_available")
    return reasons


def _score_candidate(candidate: CandidateRecord, config: CandidateUniverseConfig) -> int:
    liquidity_score = min(40, int((candidate.dollar_volume_30d / max(config.min_dollar_volume_30d, 1.0)) * 20))
    trend_score = min(25, max(0, int((candidate.price_trend_60d_pct - config.min_price_trend_60d_pct) * 100)))
    volatility_ratio = candidate.realized_volatility_30d / max(config.max_realized_volatility_30d, 0.0001)
    volatility_score = max(0, min(15, int((1.0 - volatility_ratio) * 15)))
    catalyst_score = 10 if candidate.catalyst_tags else 0
    options_score = 10 if candidate.options_available else 0
    return min(100, liquidity_score + trend_score + volatility_score + catalyst_score + options_score)


def _watchlist_by_sector(decisions: tuple[CandidateDecision, ...] | list[CandidateDecision]) -> dict[str, list[str]]:
    by_sector: dict[str, list[str]] = {}
    for decision in decisions:
        by_sector.setdefault(decision.candidate.sector, []).append(decision.candidate.symbol)
    return {sector: sorted(symbols) for sector, symbols in sorted(by_sector.items())}


def _watchlist_by_catalyst(decisions: tuple[CandidateDecision, ...] | list[CandidateDecision]) -> dict[str, list[str]]:
    by_catalyst: dict[str, set[str]] = {}
    for decision in decisions:
        for tag in decision.candidate.catalyst_tags:
            by_catalyst.setdefault(tag, set()).add(decision.candidate.symbol)
    return {tag: sorted(symbols) for tag, symbols in sorted(by_catalyst.items())}


def _record_from_payload(payload: dict[str, Any]) -> CandidateRecord:
    return CandidateRecord(
        symbol=payload["symbol"],
        name=payload["name"],
        sector=payload["sector"],
        last_price=float(payload["last_price"]),
        average_volume_30d=int(payload["average_volume_30d"]),
        dollar_volume_30d=float(payload["dollar_volume_30d"]),
        price_trend_60d_pct=float(payload["price_trend_60d_pct"]),
        realized_volatility_30d=float(payload["realized_volatility_30d"]),
        catalyst_tags=tuple(payload.get("catalyst_tags", ())),
        market_cap_bucket=payload["market_cap_bucket"],
        options_available=bool(payload["options_available"]),
        as_of=datetime.fromisoformat(payload["as_of"]),
        market_cap=payload.get("market_cap"),
        label=payload.get("label", RESEARCH_ONLY),
    )


def _config_payload(config: CandidateUniverseConfig) -> dict[str, Any]:
    return {
        "allowed_sectors": config.allowed_sectors,
        "min_average_volume_30d": config.min_average_volume_30d,
        "min_dollar_volume_30d": config.min_dollar_volume_30d,
        "min_price_trend_60d_pct": config.min_price_trend_60d_pct,
        "max_realized_volatility_30d": config.max_realized_volatility_30d,
        "required_catalyst_tags": config.required_catalyst_tags,
        "allowed_market_cap_buckets": config.allowed_market_cap_buckets,
        "require_options_available": config.require_options_available,
        "max_candidates": config.max_candidates,
    }


def _decision_payload(decision: CandidateDecision) -> dict[str, Any]:
    candidate = decision.candidate
    return {
        "symbol": candidate.symbol,
        "name": candidate.name,
        "sector": candidate.sector,
        "last_price": candidate.last_price,
        "average_volume_30d": candidate.average_volume_30d,
        "dollar_volume_30d": candidate.dollar_volume_30d,
        "price_trend_60d_pct": candidate.price_trend_60d_pct,
        "realized_volatility_30d": candidate.realized_volatility_30d,
        "catalyst_tags": candidate.catalyst_tags,
        "market_cap_bucket": candidate.market_cap_bucket,
        "options_available": candidate.options_available,
        "as_of": candidate.as_of.isoformat(),
        "market_cap": candidate.market_cap,
        "included": decision.included,
        "label": decision.label,
        "score": decision.score,
        "reasons": decision.reasons,
        "human_review_required": decision.human_review_required,
    }


def _require_symbol(symbol: str) -> None:
    _require_text("symbol", symbol)
    if symbol.strip() != symbol.strip().upper():
        raise ValueError("symbol must be uppercase")


def _require_text(field_name: str, value: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required")


def _require_unique_text(field_name: str, values: tuple[str, ...]) -> None:
    seen: set[str] = set()
    for value in values:
        _require_text(field_name, value)
        if value in seen:
            raise ValueError(f"{field_name} must not contain duplicates")
        seen.add(value)


def _require_unique_symbols(candidates: tuple[CandidateRecord, ...]) -> None:
    symbols = [candidate.symbol for candidate in candidates]
    if len(symbols) != len(set(symbols)):
        raise ValueError("candidate symbols must be unique")


def _require_positive(field_name: str, value: float) -> None:
    if value <= 0:
        raise ValueError(f"{field_name} must be positive")


def _require_non_negative(field_name: str, value: float | int) -> None:
    if value < 0:
        raise ValueError(f"{field_name} cannot be negative")


def _require_safe_label(label: str) -> None:
    if label not in SAFE_ACTION_LABELS:
        raise ValueError("label must be a safe research, monitor, paper, review, or blocked label")
