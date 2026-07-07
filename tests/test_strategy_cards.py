from __future__ import annotations

import dataclasses

import pytest

from engines.strategy_cards import STRATEGY_CARDS, StrategyCard, validate_strategy_cards
from risk.policies import (
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    RESEARCH_ONLY,
)


def test_11c_strategy_cards_validate_required_schema_and_safety() -> None:
    validate_strategy_cards()

    assert len(STRATEGY_CARDS) >= 4
    assert {card.engine for card in STRATEGY_CARDS} == {"wealth", "moonshot"}
    assert {card.candidate_type for card in STRATEGY_CARDS} == {
        "deterministic",
        "non_deterministic",
    }

    for card in STRATEGY_CARDS:
        assert card.hypothesis
        assert card.universe
        assert card.timeframe
        assert card.signals
        assert card.risk_rules
        assert card.validation_requirements
        assert card.promotion_criteria
        assert card.live_trading_enabled is False
        assert card.broker_order_routing_enabled is False
        assert card.broker_order_call_performed is False
        assert card.secrets_required is False


def test_11c_non_deterministic_cards_are_human_review_required() -> None:
    analyst_cards = [
        card for card in STRATEGY_CARDS if card.candidate_type == "non_deterministic"
    ]

    assert analyst_cards
    for card in analyst_cards:
        assert card.lane == "analyst_outputs"
        assert card.label == HUMAN_REVIEW_REQUIRED


def test_11c_deterministic_cards_stay_in_deterministic_lane() -> None:
    deterministic_cards = [
        card for card in STRATEGY_CARDS if card.candidate_type == "deterministic"
    ]

    assert deterministic_cards
    for card in deterministic_cards:
        assert card.lane == "deterministic"
        assert card.label in {RESEARCH_ONLY, MONITOR_ONLY}


def test_11c_rejects_missing_required_card_field() -> None:
    bad_card = dataclasses.replace(STRATEGY_CARDS[0], signals=())

    with pytest.raises(ValueError, match="signals"):
        bad_card.validate()


def test_11c_rejects_unsafe_flags_and_labels() -> None:
    live_card = dataclasses.replace(
        STRATEGY_CARDS[0],
        **{"live_trading_enabled": not STRATEGY_CARDS[0].live_trading_enabled},
    )
    broker_card = dataclasses.replace(
        STRATEGY_CARDS[0],
        broker_order_routing_enabled=True,
    )
    analyst_without_review = dataclasses.replace(
        STRATEGY_CARDS[1],
        label=RESEARCH_ONLY,
    )
    unsafe_label = dataclasses.replace(
        STRATEGY_CARDS[0],
        label="BUY" + "_NOW",
    )

    with pytest.raises(ValueError, match="live trading"):
        live_card.validate()
    with pytest.raises(ValueError, match="broker routing"):
        broker_card.validate()
    with pytest.raises(ValueError, match="human review"):
        analyst_without_review.validate()
    with pytest.raises(ValueError, match="unsafe strategy-card label"):
        unsafe_label.validate()


def test_11c_rejects_duplicate_strategy_card_ids() -> None:
    duplicate = dataclasses.replace(STRATEGY_CARDS[0])

    with pytest.raises(ValueError, match="duplicate strategy card id"):
        validate_strategy_cards((STRATEGY_CARDS[0], duplicate))
