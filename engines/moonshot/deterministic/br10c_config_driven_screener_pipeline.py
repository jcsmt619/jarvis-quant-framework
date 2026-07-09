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


PHASE_ID = "BR-10C"
MODULE_NAME = "Track B Config Driven Screener Pipeline"
ASSET_CLASSES = ("stock", "crypto")
REQUIRED_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
SAFE_ACTION_LABELS = REQUIRED_LABELS
DEFAULT_FIXTURE_PATH = Path("engines/moonshot/deterministic/fixtures/br10c_screener_pipeline.json")
DEFAULT_REPORT_DIR = Path("reports/br10c_config_driven_screener_pipeline")


@dataclass(frozen=True)
class ScreenerMetricRange:
    metric: str
    minimum: float | None = None
    maximum: float | None = None

    def validate(self) -> None:
        _require_text("metric", self.metric)
        if self.minimum is None and self.maximum is None:
            raise ValueError("metric range requires a minimum or maximum")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("metric range minimum cannot exceed maximum")


@dataclass(frozen=True)
class ScreenerFilterGroup:
    name: str
    asset_classes: tuple[str, ...] = ASSET_CLASSES
    metric_ranges: tuple[ScreenerMetricRange, ...] = ()
    required_tags: tuple[str, ...] = ()
    allowed_sectors: tuple[str, ...] = ()
    allowed_networks: tuple[str, ...] = ()

    def validate(self) -> None:
        _require_text("name", self.name)
        _require_unique_text("asset_classes", self.asset_classes)
        _require_unique_text("required_tags", self.required_tags)
        _require_unique_text("allowed_sectors", self.allowed_sectors)
        _require_unique_text("allowed_networks", self.allowed_networks)
        for asset_class in self.asset_classes:
            if asset_class not in ASSET_CLASSES:
                raise ValueError("filter group asset class must be stock or crypto")
        for metric_range in self.metric_ranges:
            metric_range.validate()


@dataclass(frozen=True)
class ScreenerRankingRule:
    metric: str
    weight: float
    direction: str = "higher"

    def validate(self) -> None:
        _require_text("metric", self.metric)
        _require_positive("weight", self.weight)
        if self.direction not in ("higher", "lower"):
            raise ValueError("ranking direction must be higher or lower")


@dataclass(frozen=True)
class ScreenerPipelineConfig:
    filter_groups: tuple[ScreenerFilterGroup, ...]
    ranking_rules: tuple[ScreenerRankingRule, ...]
    max_queue_size: int = 10
    include_blocked_profiles: bool = True

    def validate(self) -> None:
        if not self.filter_groups:
            raise ValueError("screener pipeline requires at least one filter group")
        if not self.ranking_rules:
            raise ValueError("screener pipeline requires at least one ranking rule")
        if self.max_queue_size <= 0:
            raise ValueError("max_queue_size must be positive")
        _require_unique_text("filter group names", tuple(group.name for group in self.filter_groups))
        for group in self.filter_groups:
            group.validate()
        for rule in self.ranking_rules:
            rule.validate()


@dataclass(frozen=True)
class ScreenerCandidate:
    symbol: str
    name: str
    asset_class: str
    as_of: datetime
    metrics: dict[str, float]
    tags: tuple[str, ...] = ()
    sector: str | None = None
    network: str | None = None
    quote_currency: str = "USD"
    profile_notes: tuple[str, ...] = ()
    label: str = RESEARCH_ONLY

    def validate(self) -> None:
        _require_symbol(self.symbol)
        _require_text("name", self.name)
        if self.asset_class not in ASSET_CLASSES:
            raise ValueError("candidate asset_class must be stock or crypto")
        if not self.metrics:
            raise ValueError("candidate metrics are required")
        for metric, value in self.metrics.items():
            _require_text("metric", metric)
            if not isinstance(value, int | float):
                raise ValueError("candidate metric values must be numeric")
        _require_unique_text("tags", self.tags)
        _require_unique_text("profile_notes", self.profile_notes)
        _require_text("quote_currency", self.quote_currency)
        if self.asset_class == "stock" and not self.sector:
            raise ValueError("stock candidates require sector")
        if self.asset_class == "crypto" and not self.network:
            raise ValueError("crypto candidates require network")
        _require_safe_label(self.label)


@dataclass(frozen=True)
class ScreenerCandidateProfile:
    candidate: ScreenerCandidate
    matched_filter_groups: tuple[str, ...]
    blocked_reasons: tuple[str, ...]
    ranking_score: float
    rank: int | None
    included: bool
    label: str
    human_review_required: bool = True

    def validate(self) -> None:
        self.candidate.validate()
        _require_safe_label(self.label)
        _require_unique_text("matched_filter_groups", self.matched_filter_groups)
        _require_unique_text("blocked_reasons", self.blocked_reasons)
        if self.ranking_score < 0:
            raise ValueError("ranking_score cannot be negative")
        if self.included and self.rank is None:
            raise ValueError("included profiles require a rank")
        if not self.included and self.label != BLOCKED_BY_SAFETY_GATE:
            raise ValueError("blocked profiles must use blocked safety label")
        if not self.human_review_required:
            raise ValueError("screener profiles must require human review")


@dataclass(frozen=True)
class ScreenerPipelineReport:
    as_of: datetime
    config: ScreenerPipelineConfig
    profiles: tuple[ScreenerCandidateProfile, ...]
    safety: dict[str, Any]
    label: str = HUMAN_REVIEW_REQUIRED

    @property
    def research_queue(self) -> tuple[ScreenerCandidateProfile, ...]:
        return tuple(profile for profile in self.profiles if profile.included)

    @property
    def blocked_profiles(self) -> tuple[ScreenerCandidateProfile, ...]:
        return tuple(profile for profile in self.profiles if not profile.included)

    def validate(self) -> None:
        self.config.validate()
        if not self.profiles:
            raise ValueError("screener pipeline report requires at least one profile")
        for profile in self.profiles:
            profile.validate()
        _require_safe_label(self.label)
        if self.label != HUMAN_REVIEW_REQUIRED:
            raise ValueError("screener pipeline report must require human review")
        _validate_disabled_safety(self.safety, "config driven screener pipeline")


def safety_manifest() -> dict[str, Any]:
    return {
        "phase": PHASE_ID,
        "module": MODULE_NAME,
        "labels": REQUIRED_LABELS,
        "research_only": True,
        "monitor_only": True,
        "paper_only": True,
        "human_review_required": True,
        "ranked_research_queue_only": True,
        "trade_signals_generated": False,
        "stock_schema_supported": True,
        "crypto_schema_supported": True,
        "config_driven_filters": True,
        "local_reports_only": True,
        "real_paper_wrapper_connected": False,
        "real_paper_wrapper_attempted": False,
        "real_paper_order_submitted": False,
        "broker_order_call_performed": False,
        "broker_order_submitted": False,
        "broker_order_routing_enabled": False,
        "live_trading_enabled": False,
        "LIVE TRADING": "DISABLED",
    }


def load_screener_fixture(path: Path = DEFAULT_FIXTURE_PATH) -> tuple[ScreenerPipelineConfig, tuple[ScreenerCandidate, ...]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    config = _config_from_payload(payload["config"])
    candidates = tuple(_candidate_from_payload(item) for item in payload["candidates"])
    config.validate()
    if not candidates:
        raise ValueError("screener fixture requires at least one candidate")
    for candidate in candidates:
        candidate.validate()
    return config, candidates


def load_screener_pipeline_report(path: Path = DEFAULT_FIXTURE_PATH) -> ScreenerPipelineReport:
    config, candidates = load_screener_fixture(path)
    return build_screener_pipeline_report(candidates, config)


def build_screener_pipeline_report(
    candidates: tuple[ScreenerCandidate, ...] | list[ScreenerCandidate],
    config: ScreenerPipelineConfig,
    as_of: datetime | None = None,
) -> ScreenerPipelineReport:
    config.validate()
    if not candidates:
        raise ValueError("screener pipeline requires at least one candidate")
    validated = tuple(candidates)
    for candidate in validated:
        candidate.validate()
    _require_unique_symbols(validated)

    prelim = tuple(_profile_for_candidate(candidate, config) for candidate in validated)
    ranked = sorted(
        (profile for profile in prelim if profile.included),
        key=lambda item: (-item.ranking_score, item.candidate.symbol),
    )
    included_symbols = {profile.candidate.symbol for profile in ranked[: config.max_queue_size]}
    rank_by_symbol = {profile.candidate.symbol: index for index, profile in enumerate(ranked[: config.max_queue_size], start=1)}

    profiles = tuple(
        _apply_queue_rank(profile, included_symbols, rank_by_symbol)
        for profile in sorted(prelim, key=lambda item: item.candidate.symbol)
        if config.include_blocked_profiles or profile.candidate.symbol in included_symbols
    )
    report = ScreenerPipelineReport(
        as_of=as_of or max(candidate.as_of for candidate in validated),
        config=config,
        profiles=profiles,
        safety=safety_manifest(),
    )
    report.validate()
    return report


def screener_pipeline_payload(report: ScreenerPipelineReport) -> dict[str, Any]:
    report.validate()
    queue = sorted(report.research_queue, key=lambda item: item.rank or 999_999)
    blocked = sorted(report.blocked_profiles, key=lambda item: item.candidate.symbol)
    return {
        "phase": PHASE_ID,
        "module": MODULE_NAME,
        "as_of": report.as_of.isoformat(),
        "label": report.label,
        "safety": report.safety,
        "config": _config_payload(report.config),
        "metrics": {
            "candidate_count": len(report.profiles),
            "research_queue_count": len(queue),
            "blocked_count": len(blocked),
            "stock_profile_count": _asset_count(report.profiles, "stock"),
            "crypto_profile_count": _asset_count(report.profiles, "crypto"),
            "human_review_required_count": len(report.profiles),
        },
        "research_queue": [_profile_payload(profile) for profile in queue],
        "blocked_profiles": [_profile_payload(profile) for profile in blocked],
        "dashboard": {
            "queue_symbols": [profile.candidate.symbol for profile in queue],
            "by_asset_class": _queue_by_asset_class(queue),
            "top_profile": _profile_payload(queue[0]) if queue else None,
        },
    }


def render_markdown_screener_pipeline(report: ScreenerPipelineReport) -> str:
    payload = screener_pipeline_payload(report)
    lines = [
        f"# {PHASE_ID} {MODULE_NAME}",
        "",
        "Research labels: " + ", ".join(REQUIRED_LABELS),
        "LIVE TRADING: DISABLED",
        "",
        "## Dashboard",
    ]
    for name, value in payload["metrics"].items():
        lines.append(f"- {name}: {value}")

    lines.extend(["", "## Ranked Research Queue"])
    if not payload["research_queue"]:
        lines.append("- no_candidates_passed_filters")
    for profile in payload["research_queue"]:
        lines.append(
            "- "
            + f"rank={profile['rank']} "
            + profile["symbol"]
            + f": asset_class={profile['asset_class']}, score={profile['ranking_score']:.2f}, "
            + f"filters={', '.join(profile['matched_filter_groups'])}, label={profile['label']}"
        )
        lines.append("  profile: " + "; ".join(profile["profile_notes"]))

    lines.extend(["", "## Blocked Profiles"])
    if not payload["blocked_profiles"]:
        lines.append("- no_blocked_profiles")
    for profile in payload["blocked_profiles"]:
        lines.append(
            "- "
            + profile["symbol"]
            + f": asset_class={profile['asset_class']}, reasons="
            + ", ".join(profile["blocked_reasons"])
        )

    lines.extend(
        [
            "",
            "## Safety",
            "- Ranked research queue only; entries are not trade signals.",
            "- Stock and crypto candidates are local fixture inputs for paper-only review.",
            "- No broker routing, broker calls, live trading, or order submission.",
        ]
    )
    return "\n".join(lines)


def write_screener_pipeline_report(
    report: ScreenerPipelineReport,
    out_dir: Path = DEFAULT_REPORT_DIR,
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "config_driven_screener_pipeline.json"
    md_path = out_dir / "config_driven_screener_pipeline.md"
    json_path.write_text(json.dumps(screener_pipeline_payload(report), indent=2, default=str), encoding="utf-8")
    md_path.write_text(render_markdown_screener_pipeline(report), encoding="utf-8")
    return json_path, md_path


def _profile_for_candidate(
    candidate: ScreenerCandidate,
    config: ScreenerPipelineConfig,
) -> ScreenerCandidateProfile:
    matched_groups: list[str] = []
    group_rejections: list[str] = []
    for group in config.filter_groups:
        reasons = _filter_group_rejections(candidate, group)
        if reasons:
            group_rejections.extend(f"{group.name}:{reason}" for reason in reasons)
        else:
            matched_groups.append(group.name)
    included = bool(matched_groups)
    return ScreenerCandidateProfile(
        candidate=candidate,
        matched_filter_groups=tuple(matched_groups),
        blocked_reasons=() if included else tuple(group_rejections),
        ranking_score=_ranking_score(candidate, config.ranking_rules),
        rank=None,
        included=included,
        label=HUMAN_REVIEW_REQUIRED if included else BLOCKED_BY_SAFETY_GATE,
    )


def _filter_group_rejections(candidate: ScreenerCandidate, group: ScreenerFilterGroup) -> list[str]:
    reasons: list[str] = []
    if candidate.asset_class not in group.asset_classes:
        reasons.append("asset_class_filter_mismatch")
    if group.required_tags and not set(group.required_tags).issubset(set(candidate.tags)):
        reasons.append("required_tags_missing")
    if group.allowed_sectors and candidate.sector not in group.allowed_sectors:
        reasons.append("sector_filter_mismatch")
    if group.allowed_networks and candidate.network not in group.allowed_networks:
        reasons.append("network_filter_mismatch")
    for metric_range in group.metric_ranges:
        value = candidate.metrics.get(metric_range.metric)
        if value is None:
            reasons.append(f"{metric_range.metric}_missing")
            continue
        if metric_range.minimum is not None and value < metric_range.minimum:
            reasons.append(f"{metric_range.metric}_below_minimum")
        if metric_range.maximum is not None and value > metric_range.maximum:
            reasons.append(f"{metric_range.metric}_above_maximum")
    return reasons


def _ranking_score(candidate: ScreenerCandidate, ranking_rules: tuple[ScreenerRankingRule, ...]) -> float:
    score = 0.0
    for rule in ranking_rules:
        value = candidate.metrics.get(rule.metric, 0.0)
        component = value if rule.direction == "higher" else max(0.0, 1.0 - value)
        score += component * rule.weight
    return round(score, 4)


def _apply_queue_rank(
    profile: ScreenerCandidateProfile,
    included_symbols: set[str],
    rank_by_symbol: dict[str, int],
) -> ScreenerCandidateProfile:
    if not profile.included:
        return profile
    if profile.candidate.symbol not in included_symbols:
        return ScreenerCandidateProfile(
            candidate=profile.candidate,
            matched_filter_groups=profile.matched_filter_groups,
            blocked_reasons=("queue_limit_exceeded",),
            ranking_score=profile.ranking_score,
            rank=None,
            included=False,
            label=BLOCKED_BY_SAFETY_GATE,
        )
    return ScreenerCandidateProfile(
        candidate=profile.candidate,
        matched_filter_groups=profile.matched_filter_groups,
        blocked_reasons=(),
        ranking_score=profile.ranking_score,
        rank=rank_by_symbol[profile.candidate.symbol],
        included=True,
        label=HUMAN_REVIEW_REQUIRED,
    )


def _config_from_payload(payload: dict[str, Any]) -> ScreenerPipelineConfig:
    return ScreenerPipelineConfig(
        filter_groups=tuple(
            ScreenerFilterGroup(
                name=group["name"],
                asset_classes=tuple(group.get("asset_classes", ASSET_CLASSES)),
                metric_ranges=tuple(
                    ScreenerMetricRange(
                        metric=item["metric"],
                        minimum=item.get("minimum"),
                        maximum=item.get("maximum"),
                    )
                    for item in group.get("metric_ranges", ())
                ),
                required_tags=tuple(group.get("required_tags", ())),
                allowed_sectors=tuple(group.get("allowed_sectors", ())),
                allowed_networks=tuple(group.get("allowed_networks", ())),
            )
            for group in payload["filter_groups"]
        ),
        ranking_rules=tuple(
            ScreenerRankingRule(
                metric=rule["metric"],
                weight=float(rule["weight"]),
                direction=rule.get("direction", "higher"),
            )
            for rule in payload["ranking_rules"]
        ),
        max_queue_size=int(payload.get("max_queue_size", 10)),
        include_blocked_profiles=bool(payload.get("include_blocked_profiles", True)),
    )


def _candidate_from_payload(payload: dict[str, Any]) -> ScreenerCandidate:
    return ScreenerCandidate(
        symbol=payload["symbol"],
        name=payload["name"],
        asset_class=payload["asset_class"],
        as_of=datetime.fromisoformat(payload["as_of"]),
        metrics={key: float(value) for key, value in payload["metrics"].items()},
        tags=tuple(payload.get("tags", ())),
        sector=payload.get("sector"),
        network=payload.get("network"),
        quote_currency=payload.get("quote_currency", "USD"),
        profile_notes=tuple(payload.get("profile_notes", ())),
        label=payload.get("label", RESEARCH_ONLY),
    )


def _config_payload(config: ScreenerPipelineConfig) -> dict[str, Any]:
    return {
        "filter_groups": [
            {
                "name": group.name,
                "asset_classes": group.asset_classes,
                "metric_ranges": [
                    {
                        "metric": item.metric,
                        "minimum": item.minimum,
                        "maximum": item.maximum,
                    }
                    for item in group.metric_ranges
                ],
                "required_tags": group.required_tags,
                "allowed_sectors": group.allowed_sectors,
                "allowed_networks": group.allowed_networks,
            }
            for group in config.filter_groups
        ],
        "ranking_rules": [
            {"metric": rule.metric, "weight": rule.weight, "direction": rule.direction}
            for rule in config.ranking_rules
        ],
        "max_queue_size": config.max_queue_size,
        "include_blocked_profiles": config.include_blocked_profiles,
    }


def _profile_payload(profile: ScreenerCandidateProfile) -> dict[str, Any]:
    candidate = profile.candidate
    return {
        "symbol": candidate.symbol,
        "name": candidate.name,
        "asset_class": candidate.asset_class,
        "sector": candidate.sector,
        "network": candidate.network,
        "quote_currency": candidate.quote_currency,
        "as_of": candidate.as_of.isoformat(),
        "metrics": candidate.metrics,
        "tags": candidate.tags,
        "profile_notes": candidate.profile_notes,
        "matched_filter_groups": profile.matched_filter_groups,
        "blocked_reasons": profile.blocked_reasons,
        "ranking_score": profile.ranking_score,
        "rank": profile.rank,
        "included": profile.included,
        "label": profile.label,
        "human_review_required": profile.human_review_required,
        "paper_only": True,
        "trade_signal": False,
    }


def _asset_count(profiles: tuple[ScreenerCandidateProfile, ...], asset_class: str) -> int:
    return sum(1 for profile in profiles if profile.candidate.asset_class == asset_class)


def _queue_by_asset_class(profiles: tuple[ScreenerCandidateProfile, ...] | list[ScreenerCandidateProfile]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for profile in profiles:
        grouped.setdefault(profile.candidate.asset_class, []).append(profile.candidate.symbol)
    return {asset_class: sorted(symbols) for asset_class, symbols in sorted(grouped.items())}


def _validate_disabled_safety(manifest: dict[str, Any], owner: str) -> None:
    for field_name in (
        "real_paper_wrapper_connected",
        "real_paper_wrapper_attempted",
        "real_paper_order_submitted",
        "broker_order_call_performed",
        "broker_order_submitted",
        "broker_order_routing_enabled",
        "live_trading_enabled",
    ):
        if manifest.get(field_name) is not False:
            raise ValueError(f"{owner} cannot set {field_name}")
    if manifest.get("LIVE TRADING") != "DISABLED":
        raise ValueError(f"{owner} must keep LIVE TRADING disabled")
    if manifest.get("trade_signals_generated") is not False:
        raise ValueError(f"{owner} cannot generate trade signals")


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


def _require_unique_symbols(candidates: tuple[ScreenerCandidate, ...]) -> None:
    symbols = [candidate.symbol for candidate in candidates]
    if len(symbols) != len(set(symbols)):
        raise ValueError("candidate symbols must be unique")


def _require_positive(field_name: str, value: float) -> None:
    if value <= 0:
        raise ValueError(f"{field_name} must be positive")


def _require_safe_label(label: str) -> None:
    if label not in SAFE_ACTION_LABELS:
        raise ValueError("label must be a safe research, monitor, paper, review, or blocked label")
