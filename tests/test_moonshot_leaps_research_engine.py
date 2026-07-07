from __future__ import annotations

from datetime import date

import pytest

from engines.moonshot.deterministic.leaps_research_engine import (
    REQUIRED_LABELS,
    LeapsResearchConfig,
    LeapsResearchInput,
    build_leaps_payload,
    build_leaps_research_memo,
    render_markdown_memo,
    safety_manifest,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


def _candidate(**overrides: object) -> LeapsResearchInput:
    values = {
        "symbol": "TSLA",
        "contract_type": "call",
        "strike": 300.0,
        "underlying_price": 250.0,
        "expiration": date(2027, 12, 17),
        "as_of": date(2026, 7, 7),
        "delta": 0.45,
        "bid": 42.00,
        "ask": 45.00,
        "last": 43.25,
        "open_interest": 1_200,
        "volume": 75,
        "premium_at_risk_pct": 0.015,
        "data_age_minutes": 5,
        "thesis": "Research-only upside convexity thesis tied to operating leverage.",
        "catalyst": "Product cycle and margin expansion review window.",
        "risk": "Premium can decay or reprice if growth assumptions fail.",
        "monitoring": "Monitor DTE, IV, spread, volume, and thesis invalidation weekly.",
        "invalidation": "Revenue growth slows or option liquidity deteriorates.",
        "research_label": HUMAN_REVIEW_REQUIRED,
    }
    values.update(overrides)
    return LeapsResearchInput(**values)


def test_13d_safety_manifest_is_research_only_and_disabled() -> None:
    manifest = safety_manifest()

    assert REQUIRED_LABELS == (RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED)
    assert manifest["phase"] == "13D"
    assert manifest["research_only"] is True
    assert manifest["monitor_only"] is True
    assert manifest["paper_only"] is True
    assert manifest["human_review_required"] is True
    assert manifest["live_trading_enabled"] is False
    assert manifest["broker_order_routing_enabled"] is False
    assert manifest["broker_order_call_performed"] is False
    assert manifest["broker_order_submitted"] is False
    assert manifest["LIVE TRADING"] == "DISABLED"


def test_13d_builds_research_memo_with_required_fields() -> None:
    memo = build_leaps_research_memo(_candidate())
    payload = build_leaps_payload(memo)

    assert memo.label == RESEARCH_ONLY
    assert memo.monitor_allowed is True
    assert memo.dte == 528
    assert memo.expiration_bucket == "long_duration_leaps"
    assert memo.moneyness == "out_of_the_money"
    assert memo.warnings == ()
    assert payload["research"]["thesis"].startswith("Research-only")
    assert payload["research"]["catalyst"] == "Product cycle and margin expansion review window."
    assert payload["delta"]["value"] == pytest.approx(0.45)
    assert payload["liquidity"]["open_interest"] == 1_200
    assert payload["risk"]["premium_at_risk_pct"] == pytest.approx(0.015)
    assert payload["monitoring"]["human_review_required"] is True


def test_13d_flags_expiration_delta_liquidity_risk_and_monitoring_warnings() -> None:
    memo = build_leaps_research_memo(
        _candidate(
            expiration=date(2026, 10, 16),
            delta=0.90,
            bid=1.00,
            ask=1.40,
            open_interest=20,
            volume=0,
            premium_at_risk_pct=0.06,
            data_age_minutes=90,
        )
    )

    assert memo.label == BLOCKED_BY_SAFETY_GATE
    assert memo.monitor_allowed is False
    assert set(memo.warnings) >= {
        "below_leaps_dte_threshold_research_only",
        "delta_too_high_directional_risk_review",
        "open_interest_liquidity_warning",
        "volume_liquidity_warning",
        "wide_bid_ask_spread_warning",
        "premium_at_risk_cap_review",
        "stale_options_data",
        "HUMAN_REVIEW_REQUIRED",
    }


def test_13d_payload_and_markdown_remain_research_outputs() -> None:
    memo = build_leaps_research_memo(_candidate(contract_type="put", strike=300.0))
    payload = build_leaps_payload(memo)
    markdown = render_markdown_memo(memo)

    assert payload["phase"] == "13D"
    assert payload["contract_type"] == "put"
    assert payload["moneyness"] == "in_the_money"
    assert payload["safety"]["broker_order_submitted"] is False
    assert payload["research"]["label"] == HUMAN_REVIEW_REQUIRED
    assert "LIVE TRADING: DISABLED" in markdown
    assert "Research-only LEAPS memo; no broker routing or order submission." in markdown


def test_13d_custom_config_can_allow_shorter_research_duration() -> None:
    memo = build_leaps_research_memo(
        _candidate(expiration=date(2027, 3, 19)),
        LeapsResearchConfig(min_leaps_dte=180, ideal_min_dte=180),
    )

    assert memo.expiration_bucket == "long_duration_leaps"
    assert memo.warnings == ()


def test_13d_validation_rejects_invalid_candidate_and_config() -> None:
    with pytest.raises(ValueError, match="expiration cannot be before as_of"):
        build_leaps_research_memo(_candidate(expiration=date(2026, 7, 6)))

    with pytest.raises(ValueError, match="delta"):
        build_leaps_research_memo(_candidate(delta=1.25))

    with pytest.raises(ValueError, match="ideal_min_dte"):
        build_leaps_research_memo(
            _candidate(),
            LeapsResearchConfig(min_leaps_dte=365, ideal_min_dte=180),
        )
