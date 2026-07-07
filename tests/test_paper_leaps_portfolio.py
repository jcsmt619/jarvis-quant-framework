from __future__ import annotations

import json
import shutil
from datetime import date, datetime
from pathlib import Path

import pytest

from engines.moonshot.deterministic.paper_leaps_portfolio import (
    REQUIRED_LABELS,
    PaperLeapsConfig,
    PaperLeapsFill,
    build_paper_leaps_payload,
    build_paper_leaps_portfolio,
    contract_key,
    render_markdown_portfolio,
    safety_manifest,
    write_paper_leaps_report,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


def _fill(**overrides: object) -> PaperLeapsFill:
    values = {
        "fill_id": "fill-001",
        "symbol": "TSLA",
        "contract_type": "call",
        "strike": 300.0,
        "expiration": date(2027, 12, 17),
        "filled_at": datetime(2026, 7, 7, 14, 30),
        "side": "open",
        "contracts": 1,
        "fill_price": 25.00,
        "thesis": "Research-only LEAPS convexity thesis for paper tracking.",
        "thesis_status": "active",
        "label": PAPER_ONLY,
    }
    values.update(overrides)
    return PaperLeapsFill(**values)


def test_13f_safety_manifest_is_paper_only_and_disabled() -> None:
    manifest = safety_manifest()

    assert REQUIRED_LABELS == (RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED)
    assert manifest["phase"] == "13F"
    assert manifest["research_only"] is True
    assert manifest["monitor_only"] is True
    assert manifest["paper_only"] is True
    assert manifest["human_review_required"] is True
    assert manifest["simulated_fills_only"] is True
    assert manifest["live_trading_enabled"] is False
    assert manifest["broker_order_routing_enabled"] is False
    assert manifest["broker_order_call_performed"] is False
    assert manifest["broker_order_submitted"] is False
    assert manifest["LIVE TRADING"] == "DISABLED"


def test_13f_tracks_simulated_fills_positions_and_pnl() -> None:
    key = contract_key("TSLA", "call", 300.0, date(2027, 12, 17))
    portfolio = build_paper_leaps_portfolio(
        [_fill()],
        {key: 30.00},
        date(2026, 7, 7),
    )
    payload = build_paper_leaps_payload(portfolio)

    assert portfolio.label == PAPER_ONLY
    assert portfolio.cash == pytest.approx(97_500.0)
    assert portfolio.total_cost_basis == pytest.approx(2_500.0)
    assert portfolio.market_value == pytest.approx(3_000.0)
    assert portfolio.realized_pnl == pytest.approx(0.0)
    assert portfolio.unrealized_pnl == pytest.approx(500.0)
    assert portfolio.total_pnl == pytest.approx(500.0)
    assert portfolio.equity == pytest.approx(100_500.0)
    assert portfolio.metrics["position_count"] == 1
    assert portfolio.warnings == ()
    assert payload["fills"][0]["simulated_fill"] is True
    assert payload["positions"][0]["label"] == PAPER_ONLY
    assert payload["safety"]["broker_order_submitted"] is False


def test_13f_partial_close_realizes_pnl_and_keeps_remaining_position() -> None:
    key = contract_key("TSLA", "call", 300.0, date(2027, 12, 17))
    close_fill = _fill(
        fill_id="fill-002",
        filled_at=datetime(2026, 8, 1, 14, 30),
        side="close",
        contracts=1,
        fill_price=50.00,
        thesis_status="monitor",
    )

    portfolio = build_paper_leaps_portfolio(
        [_fill(contracts=2, fill_price=40.00), close_fill],
        {key: 48.00},
        date(2026, 8, 1),
    )

    assert portfolio.cash == pytest.approx(97_000.0)
    assert portfolio.realized_pnl == pytest.approx(1_000.0)
    assert portfolio.market_value == pytest.approx(4_800.0)
    assert portfolio.unrealized_pnl == pytest.approx(800.0)
    assert portfolio.total_pnl == pytest.approx(1_800.0)
    assert portfolio.positions[0].contracts == 1
    assert portfolio.positions[0].thesis_status == "monitor"


def test_13f_blocks_on_review_status_and_premium_caps() -> None:
    key = contract_key("TSLA", "call", 300.0, date(2027, 12, 17))
    portfolio = build_paper_leaps_portfolio(
        [
            _fill(
                contracts=4,
                thesis_status="human_review_required",
                label=HUMAN_REVIEW_REQUIRED,
            )
        ],
        {key: 39.00},
        date(2026, 7, 7),
        PaperLeapsConfig(starting_cash=100_000, max_position_premium_pct=0.03),
    )

    assert portfolio.label == BLOCKED_BY_SAFETY_GATE
    assert portfolio.positions[0].label == HUMAN_REVIEW_REQUIRED
    assert portfolio.metrics["review_required_count"] == 1
    assert set(portfolio.warnings) >= {
        f"{key}:position_premium_cap_review",
        f"{key}:thesis_human_review_required",
    }


def test_13f_missing_mark_uses_average_cost_and_records_warning() -> None:
    portfolio = build_paper_leaps_portfolio([_fill()], {}, date(2026, 7, 7))

    assert portfolio.label == BLOCKED_BY_SAFETY_GATE
    assert portfolio.positions[0].market_price == pytest.approx(25.00)
    assert portfolio.unrealized_pnl == pytest.approx(0.0)
    assert "missing_mark_price_uses_average_cost" in portfolio.warnings[0]


def test_13f_payload_and_markdown_remain_static_paper_outputs() -> None:
    key = contract_key("TSLA", "call", 300.0, date(2027, 12, 17))
    portfolio = build_paper_leaps_portfolio([_fill()], {key: 30.00}, date(2026, 7, 7))
    payload = build_paper_leaps_payload(portfolio)
    markdown = render_markdown_portfolio(portfolio)

    assert payload["phase"] == "13F"
    assert payload["module"] == "Paper LEAPS Portfolio"
    assert "LIVE TRADING: DISABLED" in markdown
    assert "Paper LEAPS portfolio tracker only; simulated fills only." in markdown
    assert "No broker routing, broker calls, or live order submission." in markdown


def test_13f_write_report_outputs_json_and_markdown() -> None:
    key = contract_key("TSLA", "call", 300.0, date(2027, 12, 17))
    portfolio = build_paper_leaps_portfolio([_fill()], {key: 30.00}, date(2026, 7, 7))
    out_dir = Path(".codex_pytest_tmp/paper_leaps_portfolio_test")
    if out_dir.exists():
        shutil.rmtree(out_dir)

    json_path, md_path = write_paper_leaps_report(portfolio, out_dir)

    assert json_path.exists()
    assert md_path.exists()
    assert json.loads(json_path.read_text(encoding="utf-8"))["phase"] == "13F"
    assert "Paper LEAPS Portfolio" in md_path.read_text(encoding="utf-8")
    shutil.rmtree(out_dir)


def test_13f_validation_rejects_invalid_fills_config_and_marks() -> None:
    with pytest.raises(ValueError, match="side must be open or close"):
        build_paper_leaps_portfolio([_fill(side="route")], {}, date(2026, 7, 7))

    with pytest.raises(ValueError, match="label must be a safe"):
        build_paper_leaps_portfolio([_fill(label="unsafe")], {}, date(2026, 7, 7))

    with pytest.raises(ValueError, match="max_position_premium_pct"):
        build_paper_leaps_portfolio(
            [_fill()],
            {},
            date(2026, 7, 7),
            PaperLeapsConfig(max_position_premium_pct=0.20, max_portfolio_premium_pct=0.10),
        )

    key = contract_key("TSLA", "call", 300.0, date(2027, 12, 17))
    with pytest.raises(ValueError, match="mark prices cannot be negative"):
        build_paper_leaps_portfolio([_fill()], {key: -1.00}, date(2026, 7, 7))
