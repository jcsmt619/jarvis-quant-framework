from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime

import pytest

from engines.moonshot.deterministic.leaps_data_model import (
    AnalystThesisRecord,
    CatalystMetadata,
    EquitySnapshot,
    LeapsDataSet,
    OptionChain,
    OptionContract,
    OptionGreeks,
    OptionQuote,
    PaperPortfolioPosition,
    leaps_dataset_from_payload,
    leaps_dataset_payload,
    load_leaps_dataset,
    safety_manifest,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


def _quote(**overrides: object) -> OptionQuote:
    values = {
        "bid": 28.4,
        "ask": 29.2,
        "last": 28.9,
        "implied_volatility": 0.46,
        "volume": 185,
        "open_interest": 2460,
        "as_of": datetime(2026, 7, 8, 16, 0),
    }
    values.update(overrides)
    return OptionQuote(**values)


def _contract(**overrides: object) -> OptionContract:
    values = {
        "contract_id": "NVDA-20271217-C-180",
        "symbol": "NVDA271217C00180000",
        "underlying_symbol": "NVDA",
        "contract_type": "call",
        "strike": 180.0,
        "expiration": date(2027, 12, 17),
        "quote": _quote(),
        "greeks": OptionGreeks(delta=0.52, gamma=0.011, theta=-0.021, vega=0.39, rho=0.18),
        "label": MONITOR_ONLY,
    }
    values.update(overrides)
    return OptionContract(**values)


def _dataset() -> LeapsDataSet:
    equity = EquitySnapshot(
        symbol="NVDA",
        name="NVIDIA Corporation",
        sector="Technology",
        last_price=150.0,
        as_of=date(2026, 7, 8),
        average_volume_30d=42_000_000,
        market_cap=3_700_000_000_000,
        label=RESEARCH_ONLY,
    )
    chain = OptionChain(
        underlying=equity,
        contracts=(_contract(),),
        catalysts=(
            CatalystMetadata(
                catalyst_id="NVDA-FY27-DC-REVISIONS",
                symbol="NVDA",
                catalyst_type="earnings_revision_cycle",
                description="Synthetic catalyst metadata for revision monitoring.",
                expected_date=date(2026, 8, 26),
                confidence="medium",
                source_note="local deterministic fixture; no external data call",
                label=HUMAN_REVIEW_REQUIRED,
            ),
        ),
        as_of=datetime(2026, 7, 8, 16, 0),
        label=MONITOR_ONLY,
    )
    return LeapsDataSet(
        as_of=datetime(2026, 7, 8, 16, 0),
        equities=(equity,),
        option_chains=(chain,),
        paper_positions=(
            PaperPortfolioPosition(
                position_id="PAPER-NVDA-001",
                contract_id="NVDA-20271217-C-180",
                symbol="NVDA",
                contracts=1,
                average_price=27.5,
                mark_price=28.9,
                opened_at=datetime(2026, 7, 8, 15, 45),
                thesis_id="THESIS-NVDA-LEAPS-001",
                label=PAPER_ONLY,
            ),
        ),
        analyst_theses=(
            AnalystThesisRecord(
                thesis_id="THESIS-NVDA-LEAPS-001",
                symbol="NVDA",
                summary="Research-only LEAPS thesis record.",
                bull_case="Upside scenario monitoring.",
                bear_case="Liquidity deterioration or IV expansion risk.",
                invalidation="Flag for review if thesis breaks.",
                created_at=datetime(2026, 7, 8, 15, 30),
                label=HUMAN_REVIEW_REQUIRED,
            ),
        ),
        label=BLOCKED_BY_SAFETY_GATE,
    )


def test_br01_safety_manifest_is_disabled_and_research_only() -> None:
    manifest = safety_manifest()

    assert manifest["phase"] == "BR-01"
    assert manifest["research_only"] is True
    assert manifest["monitor_only"] is True
    assert manifest["paper_only"] is True
    assert manifest["human_review_required"] is True
    assert manifest["blocked_by_safety_gate"] is True
    assert manifest["real_paper_wrapper_connected"] is False
    assert manifest["real_paper_wrapper_attempted"] is False
    assert manifest["real_paper_order_submitted"] is False
    assert manifest["broker_order_call_performed"] is False
    assert manifest["broker_order_submitted"] is False
    assert manifest["broker_order_routing_enabled"] is False
    assert manifest["live_trading_enabled"] is False
    assert manifest["LIVE TRADING"] == "DISABLED"


def test_br01_dataset_payload_covers_leaps_chain_fields() -> None:
    payload = leaps_dataset_payload(_dataset())
    contract = payload["option_chains"][0]["contracts"][0]
    position = payload["paper_positions"][0]

    assert payload["phase"] == "BR-01"
    assert payload["label"] == BLOCKED_BY_SAFETY_GATE
    assert payload["equities"][0]["symbol"] == "NVDA"
    assert contract["dte"] > 500
    assert contract["quote"]["implied_volatility"] == pytest.approx(0.46)
    assert contract["quote"]["volume"] == 185
    assert contract["quote"]["open_interest"] == 2460
    assert contract["quote"]["spread"] == pytest.approx(0.8)
    assert contract["quote"]["spread_pct"] == pytest.approx(0.027778)
    assert contract["greeks"]["delta"] == pytest.approx(0.52)
    assert position["simulated_position"] is True
    assert position["cost_basis"] == pytest.approx(2750.0)
    assert position["market_value"] == pytest.approx(2890.0)
    assert payload["analyst_theses"][0]["label"] == HUMAN_REVIEW_REQUIRED
    assert payload["safety"]["live_trading_enabled"] is False


def test_br01_loads_json_fixture_with_safe_labels() -> None:
    dataset = load_leaps_dataset()
    payload = leaps_dataset_payload(dataset)

    assert dataset.label == BLOCKED_BY_SAFETY_GATE
    assert dataset.equities[0].label == RESEARCH_ONLY
    assert dataset.option_chains[0].contracts[0].label == MONITOR_ONLY
    assert dataset.option_chains[0].catalysts[0].label == HUMAN_REVIEW_REQUIRED
    assert dataset.paper_positions[0].label == PAPER_ONLY
    assert payload["option_chains"][0]["contracts"][0]["quote"]["spread"] == pytest.approx(0.8)


def test_br01_payload_round_trip_preserves_references() -> None:
    payload = leaps_dataset_payload(_dataset())
    dataset = leaps_dataset_from_payload(payload)

    dataset.validate()
    assert dataset.option_chains[0].contracts[0].contract_id == "NVDA-20271217-C-180"
    assert dataset.paper_positions[0].thesis_id == "THESIS-NVDA-LEAPS-001"


def test_br01_validation_rejects_bad_quote_chain_and_thesis_state() -> None:
    with pytest.raises(ValueError, match="ask cannot be below bid"):
        _contract(quote=_quote(bid=30.0, ask=29.0)).validate()

    with pytest.raises(ValueError, match="symbol must be uppercase"):
        replace(_dataset().equities[0], symbol="nvda").validate()

    unsafe_thesis = replace(_dataset().analyst_theses[0], label=RESEARCH_ONLY)
    with pytest.raises(ValueError, match="must require human review"):
        unsafe_thesis.validate()


def test_br01_validation_rejects_missing_position_references() -> None:
    dataset = _dataset()
    missing_contract = replace(
        dataset,
        paper_positions=(replace(dataset.paper_positions[0], contract_id="MISSING-CONTRACT"),),
    )
    missing_thesis = replace(
        dataset,
        paper_positions=(replace(dataset.paper_positions[0], thesis_id="MISSING-THESIS"),),
    )

    with pytest.raises(ValueError, match="contract_id must exist"):
        missing_contract.validate()

    with pytest.raises(ValueError, match="thesis_id must exist"):
        missing_thesis.validate()
