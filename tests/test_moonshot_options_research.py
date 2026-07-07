from __future__ import annotations

from datetime import date

import pytest

from engines.moonshot.deterministic.options_research import (
    REQUIRED_LABELS,
    GreeksSnapshot,
    OptionThesis,
    OptionsResearchConfig,
    build_options_research_memo,
    memo_payload,
    render_markdown_memo,
    safety_manifest,
)
from risk.policies import HUMAN_REVIEW_REQUIRED, MONITOR_ONLY, PAPER_ONLY, RESEARCH_ONLY


def _thesis(**overrides: object) -> OptionThesis:
    values = {
        "symbol": "NVDA",
        "contract_type": "call",
        "strike": 180.0,
        "underlying_price": 150.0,
        "expiration": date(2027, 6, 18),
        "as_of": date(2026, 7, 7),
        "thesis": "Research-only upside convexity setup tied to datacenter growth.",
        "catalyst": "Earnings revision cycle and product launch window.",
        "invalidation": "Revenue growth decelerates or IV expands beyond acceptable research range.",
        "target_note": "Monitor upside scenario; no trade instruction.",
        "stop_note": "Flag for review if thesis breaks or option decay accelerates.",
        "research_label": HUMAN_REVIEW_REQUIRED,
    }
    values.update(overrides)
    return OptionThesis(**values)


def test_13b_safety_manifest_is_research_only_and_disabled() -> None:
    manifest = safety_manifest()

    assert REQUIRED_LABELS == (RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED)
    assert manifest["phase"] == "13B"
    assert manifest["research_only"] is True
    assert manifest["monitor_only"] is True
    assert manifest["paper_only"] is True
    assert manifest["human_review_required"] is True
    assert manifest["live_trading_enabled"] is False
    assert manifest["broker_order_routing_enabled"] is False
    assert manifest["broker_order_call_performed"] is False
    assert manifest["broker_order_submitted"] is False
    assert manifest["LIVE TRADING"] == "DISABLED"


def test_13b_builds_option_thesis_with_expiration_and_moneyness() -> None:
    memo = build_options_research_memo(
        _thesis(),
        GreeksSnapshot(delta=0.55, gamma=0.03, theta=-0.01, vega=0.12, rho=0.04),
    )

    assert memo.dte == 346
    assert memo.expiration_bucket == "leaps"
    assert memo.moneyness == "out_of_the_money"
    assert memo.thesis.research_label == HUMAN_REVIEW_REQUIRED
    assert "expiration_bucket=leaps; dte=346" in memo.risk_notes
    assert "HUMAN_REVIEW_REQUIRED" in memo.risk_notes


def test_13b_greeks_notes_capture_theta_gamma_vega_and_delta_risks() -> None:
    memo = build_options_research_memo(
        _thesis(),
        GreeksSnapshot(
            delta=0.82,
            gamma=0.12,
            theta=-0.03,
            vega=0.25,
            implied_volatility=0.80,
        ),
    )

    assert set(memo.risk_notes) >= {
        "high_delta_underlying_direction_risk",
        "high_gamma_convexity_risk",
        "theta_decay_risk",
        "high_vega_iv_crush_risk",
        "implied_volatility_context_required",
    }


def test_13b_expiration_handling_flags_near_expiration_and_intermediate_dte() -> None:
    near = build_options_research_memo(
        _thesis(expiration=date(2026, 8, 1)),
        GreeksSnapshot(delta=0.40, gamma=0.02, theta=-0.01, vega=0.05),
    )
    intermediate = build_options_research_memo(
        _thesis(expiration=date(2026, 11, 1)),
        GreeksSnapshot(delta=0.40, gamma=0.02, theta=-0.01, vega=0.05),
    )

    assert near.expiration_bucket == "near_expiration"
    assert "near_expiration_theta_and_gamma_risk_requires_human_review" in near.risk_notes
    assert intermediate.expiration_bucket == "intermediate"
    assert "below_leaps_dte_threshold_research_only" in intermediate.risk_notes


def test_13b_payload_and_markdown_remain_research_memos() -> None:
    memo = build_options_research_memo(
        _thesis(contract_type="put", strike=120.0, underlying_price=150.0),
        GreeksSnapshot(delta=-0.35, gamma=0.03, theta=-0.01, vega=0.10),
    )
    payload = memo_payload(memo)
    markdown = render_markdown_memo(memo)

    assert payload["phase"] == "13B"
    assert payload["moneyness"] == "out_of_the_money"
    assert payload["safety"]["broker_order_submitted"] is False
    assert payload["thesis"]["label"] == HUMAN_REVIEW_REQUIRED
    assert "LIVE TRADING: DISABLED" in markdown
    assert "Research memo only; no broker routing or order submission." in markdown


def test_13b_validation_rejects_expired_options_and_invalid_greeks() -> None:
    with pytest.raises(ValueError, match="expiration cannot be before as_of"):
        build_options_research_memo(
            _thesis(expiration=date(2026, 7, 6)),
            GreeksSnapshot(delta=0.40, gamma=0.02, theta=-0.01, vega=0.05),
        )

    with pytest.raises(ValueError, match="delta"):
        build_options_research_memo(
            _thesis(),
            GreeksSnapshot(delta=1.5, gamma=0.02, theta=-0.01, vega=0.05),
        )


def test_13b_config_requires_valid_expiration_thresholds() -> None:
    with pytest.raises(ValueError, match="near_expiration_dte"):
        build_options_research_memo(
            _thesis(),
            GreeksSnapshot(delta=0.40, gamma=0.02, theta=-0.01, vega=0.05),
            OptionsResearchConfig(min_leaps_dte=90, near_expiration_dte=120),
        )
