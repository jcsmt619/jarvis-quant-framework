from __future__ import annotations

from dataclasses import dataclass

from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


ALLOWED_ENGINES = ("wealth", "moonshot")
ALLOWED_LANES = ("deterministic", "analyst_outputs")
ALLOWED_CANDIDATE_TYPES = ("deterministic", "non_deterministic")
SAFE_STRATEGY_CARD_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
DISALLOWED_STRATEGY_CARD_LABELS = tuple(
    verb + suffix
    for verb, suffix in (
        ("BUY", "_NOW"),
        ("SELL", "_NOW"),
        ("EXECUTE", "_TRADE"),
        ("AUTO", "_TRADE"),
    )
)


@dataclass(frozen=True)
class StrategyCard:
    card_id: str
    engine: str
    lane: str
    candidate_type: str
    label: str
    hypothesis: str
    universe: tuple[str, ...]
    timeframe: str
    signals: tuple[str, ...]
    risk_rules: tuple[str, ...]
    validation_requirements: tuple[str, ...]
    promotion_criteria: tuple[str, ...]
    live_trading_enabled: bool = False
    broker_order_routing_enabled: bool = False
    broker_order_call_performed: bool = False
    secrets_required: bool = False

    def validate(self) -> None:
        if self.engine not in ALLOWED_ENGINES:
            raise ValueError(f"unknown engine: {self.engine}")
        if self.lane not in ALLOWED_LANES:
            raise ValueError(f"unknown strategy-card lane: {self.lane}")
        if self.candidate_type not in ALLOWED_CANDIDATE_TYPES:
            raise ValueError(f"unknown candidate type: {self.candidate_type}")
        if self.label not in SAFE_STRATEGY_CARD_LABELS:
            raise ValueError(f"unsafe strategy-card label: {self.label}")
        if self.label in DISALLOWED_STRATEGY_CARD_LABELS:
            raise ValueError(f"disallowed strategy-card label: {self.label}")
        if self.candidate_type == "deterministic" and self.lane != "deterministic":
            raise ValueError("deterministic strategy cards must use the deterministic lane")
        if self.candidate_type == "non_deterministic" and self.lane != "analyst_outputs":
            raise ValueError("non-deterministic strategy cards must use the analyst output lane")
        if self.candidate_type == "non_deterministic" and self.label != HUMAN_REVIEW_REQUIRED:
            raise ValueError("non-deterministic trade-relevant cards require human review")

        required_text = {
            "card_id": self.card_id,
            "hypothesis": self.hypothesis,
            "timeframe": self.timeframe,
        }
        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(f"strategy card is missing {field_name}")

        required_collections = {
            "universe": self.universe,
            "signals": self.signals,
            "risk_rules": self.risk_rules,
            "validation_requirements": self.validation_requirements,
            "promotion_criteria": self.promotion_criteria,
        }
        for field_name, values in required_collections.items():
            if not values or any(not value.strip() for value in values):
                raise ValueError(f"strategy card is missing {field_name}")

        if self.live_trading_enabled:
            raise ValueError("strategy cards cannot enable live trading")
        if self.broker_order_routing_enabled or self.broker_order_call_performed:
            raise ValueError("strategy cards cannot enable or perform broker routing")
        if self.secrets_required:
            raise ValueError("strategy cards cannot require secrets")


STRATEGY_CARDS = (
    StrategyCard(
        card_id="11C-WEALTH-DET-RESIDUAL-MOMENTUM",
        engine="wealth",
        lane="deterministic",
        candidate_type="deterministic",
        label=RESEARCH_ONLY,
        hypothesis=(
            "Residual momentum may identify persistent relative strength after "
            "removing broad-market beta from candidate returns."
        ),
        universe=("SPY", "QQQ", "IWM", "XLK", "XLF", "XLE", "XLV"),
        timeframe="Daily bars with 126-bar beta window and 63-bar residual momentum ranking.",
        signals=(
            "Rolling causal beta versus SPY",
            "Residual return rank",
            "Top-quartile research watchlist inclusion",
        ),
        risk_rules=(
            "Research-only output",
            "Max candidate weight bounded by the wealth risk policy",
            "Stop rule required before any paper-only drill",
            "Stale data blocks promotion",
        ),
        validation_requirements=(
            "Walk-forward out-of-sample validation",
            "CPCV robustness check",
            "Deflated Sharpe review",
            "Look-ahead test coverage for rolling beta and ranks",
            "Slippage and crash stress tests",
        ),
        promotion_criteria=(
            "Pass the strategy validation gate",
            "Complete the wealth paper-history requirement",
            "Remain blocked from live trading and broker routing",
        ),
    ),
    StrategyCard(
        card_id="11C-WEALTH-ANALYST-THESIS-REVIEW",
        engine="wealth",
        lane="analyst_outputs",
        candidate_type="non_deterministic",
        label=HUMAN_REVIEW_REQUIRED,
        hypothesis=(
            "Analyst review may improve research triage by challenging a "
            "deterministic candidate's thesis, assumptions, and failure modes."
        ),
        universe=("Wealth strategy candidates",),
        timeframe="Per candidate review before paper-only promotion.",
        signals=(
            "Thesis quality notes",
            "Catalyst and risk summary",
            "Second-opinion critique",
        ),
        risk_rules=(
            "Human review required",
            "Analyst text cannot override deterministic gates",
            "Research-only memo output",
            "No order routing or execution authority",
        ),
        validation_requirements=(
            "Memo must cite reviewed deterministic evidence",
            "Memo must disclose uncertainty and missing data",
            "Trade-relevant conclusions require human review",
        ),
        promotion_criteria=(
            "Used only as supporting research",
            "Deterministic validation gate remains authoritative",
            "Remain blocked from live trading and broker routing",
        ),
    ),
    StrategyCard(
        card_id="11C-MOONSHOT-DET-LEAPS-QUALITY-MONITOR",
        engine="moonshot",
        lane="deterministic",
        candidate_type="deterministic",
        label=MONITOR_ONLY,
        hypothesis=(
            "A repeatable LEAPS quality monitor can filter asymmetric setups "
            "by liquidity, DTE, IV, theta decay, and stop-condition status."
        ),
        universe=("High-conviction equity watchlist", "LEAPS option chains"),
        timeframe="Daily option-chain snapshot with event-driven stale-data checks.",
        signals=(
            "Minimum DTE threshold",
            "Open-interest and spread quality checks",
            "IV rank and theta decay monitors",
            "Risk-policy stop-condition flags",
        ),
        risk_rules=(
            "Monitor-only output",
            "Moonshot max position sizing remains policy-bound",
            "Option-chain stale data blocks promotion",
            "Human review required for trade-relevant interpretation",
        ),
        validation_requirements=(
            "Schema validation for option-chain inputs",
            "Historical snapshot replay where available",
            "Theta and IV threshold sensitivity review",
            "Stop-condition test coverage",
        ),
        promotion_criteria=(
            "Clean monitor history across the moonshot paper requirement",
            "No unresolved stale-data or stop-condition flags",
            "Remain blocked from live trading and broker routing",
        ),
    ),
    StrategyCard(
        card_id="11C-MOONSHOT-ANALYST-CATALYST-REVIEW",
        engine="moonshot",
        lane="analyst_outputs",
        candidate_type="non_deterministic",
        label=HUMAN_REVIEW_REQUIRED,
        hypothesis=(
            "Catalyst review may identify asymmetric setup risks that fixed "
            "option-chain monitors do not capture."
        ),
        universe=("Moonshot LEAPS research candidates",),
        timeframe="Per candidate before inclusion in a human-reviewed research memo.",
        signals=(
            "Catalyst summary",
            "Risk/reward critique",
            "Option-chain quality commentary",
            "Thesis invalidation notes",
        ),
        risk_rules=(
            "Human review required",
            "Research-only memo output",
            "Cannot bypass moonshot risk policy",
            "Cannot route options orders",
        ),
        validation_requirements=(
            "Memo must separate facts from analyst judgment",
            "Memo must include uncertainty and invalidation conditions",
            "Trade-relevant conclusions require human review",
        ),
        promotion_criteria=(
            "Used only as supporting research",
            "Deterministic moonshot monitors remain authoritative",
            "Remain blocked from live trading and broker routing",
        ),
    ),
)


def validate_strategy_cards(cards: tuple[StrategyCard, ...] = STRATEGY_CARDS) -> None:
    seen_ids: set[str] = set()
    for card in cards:
        if card.card_id in seen_ids:
            raise ValueError(f"duplicate strategy card id: {card.card_id}")
        seen_ids.add(card.card_id)
        card.validate()
