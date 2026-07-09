from __future__ import annotations

import json
import shutil
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path

import pytest

from engines.moonshot.deterministic.paper_options_portfolio_manager import (
    PaperOptionFill,
    PaperOptionGreeks,
    PaperOptionMark,
    PaperOptionsConfig,
    build_paper_options_portfolio_report,
    paper_options_portfolio_payload,
    render_markdown_paper_options_portfolio,
    safety_manifest,
    write_paper_options_portfolio_report,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


def _fill(**overrides: object) -> PaperOptionFill:
    values = {
        "fill_id": "fill-001",
        "contract_id": "NVDA-20271217-C-180",
        "symbol": "NVDA271217C00180000",
        "underlying_symbol": "NVDA",
        "contract_type": "call",
        "strike": 180.0,
        "expiration": date(2027, 12, 17),
        "filled_at": datetime(2026, 7, 8, 15, 30),
        "side": "entry",
        "contracts": 1,
        "fill_price": 28.50,
        "thesis_id": "thesis-nvda-ai-capex",
        "label": PAPER_ONLY,
    }
    values.update(overrides)
    return PaperOptionFill(**values)


def _mark(**overrides: object) -> PaperOptionMark:
    values = {
        "contract_id": "NVDA-20271217-C-180",
        "marked_at": datetime(2026, 7, 8, 16, 0),
        "mark_price": 31.00,
        "greeks": PaperOptionGreeks(delta=0.52, gamma=0.011, theta=-0.021, vega=0.39, rho=0.18),
        "label": MONITOR_ONLY,
    }
    values.update(overrides)
    return PaperOptionMark(**values)


def test_br07_safety_manifest_is_paper_only_and_disabled() -> None:
    manifest = safety_manifest()

    assert manifest["phase"] == "BR-07"
    assert manifest["labels"] == (
        RESEARCH_ONLY,
        MONITOR_ONLY,
        PAPER_ONLY,
        HUMAN_REVIEW_REQUIRED,
        BLOCKED_BY_SAFETY_GATE,
    )
    assert manifest["research_only"] is True
    assert manifest["monitor_only"] is True
    assert manifest["paper_only"] is True
    assert manifest["human_review_required"] is True
    assert manifest["blocked_by_safety_gate"] is True
    assert manifest["simulated_entries_only"] is True
    assert manifest["simulated_exits_only"] is True
    assert manifest["local_marks_only"] is True
    assert manifest["real_paper_wrapper_connected"] is False
    assert manifest["real_paper_wrapper_attempted"] is False
    assert manifest["real_paper_order_submitted"] is False
    assert manifest["broker_order_call_performed"] is False
    assert manifest["broker_order_submitted"] is False
    assert manifest["broker_order_routing_enabled"] is False
    assert manifest["live_trading_enabled"] is False
    assert manifest["LIVE TRADING"] == "DISABLED"


def test_br07_tracks_entries_marks_pnl_exposure_greeks_and_history() -> None:
    report = build_paper_options_portfolio_report(
        [_fill()],
        [_mark()],
        datetime(2026, 7, 8, 16, 0),
    )
    payload = paper_options_portfolio_payload(report)

    assert report.label == PAPER_ONLY
    assert report.cash == pytest.approx(97_150.0)
    assert report.realized_pnl == pytest.approx(0.0)
    assert report.unrealized_pnl == pytest.approx(250.0)
    assert report.total_pnl == pytest.approx(250.0)
    assert payload["metrics"] == {
        "position_count": 1,
        "fill_count": 1,
        "mark_count": 1,
        "history_event_count": 2,
        "warning_count": 0,
        "human_review_required_count": 1,
    }

    position = payload["positions"][0]
    assert position["contract_id"] == "NVDA-20271217-C-180"
    assert position["contracts"] == 1
    assert position["cost_basis"] == pytest.approx(2_850.0)
    assert position["market_value"] == pytest.approx(3_100.0)
    assert position["delta_exposure"] == pytest.approx(52.0)
    assert position["gamma_exposure"] == pytest.approx(1.1)
    assert position["theta_exposure"] == pytest.approx(-2.1)
    assert position["vega_exposure"] == pytest.approx(39.0)
    assert position["human_review_required"] is True

    assert payload["exposure"]["gross_market_value"] == pytest.approx(3_100.0)
    assert payload["exposure"]["net_liquidation_value"] == pytest.approx(100_250.0)
    assert payload["exposure"]["premium_at_risk_pct"] == pytest.approx(0.0285)
    assert payload["exposure"]["by_underlying"]["NVDA"]["delta_exposure"] == pytest.approx(52.0)
    assert [event["event_type"] for event in payload["history"]] == ["ENTRY", "MARK"]
    assert payload["fills"][0]["simulated_fill"] is True
    assert payload["marks"][0]["local_mark"] is True
    assert payload["safety"]["broker_order_call_performed"] is False


def test_br07_partial_exit_realizes_pnl_and_updates_open_position() -> None:
    report = build_paper_options_portfolio_report(
        [
            _fill(contracts=3, fill_price=20.00),
            _fill(
                fill_id="fill-002",
                filled_at=datetime(2026, 8, 1, 15, 30),
                side="exit",
                contracts=1,
                fill_price=25.00,
            ),
        ],
        [_mark(marked_at=datetime(2026, 8, 1, 16, 0), mark_price=26.00)],
        datetime(2026, 8, 1, 16, 0),
    )
    payload = paper_options_portfolio_payload(report)

    assert report.cash == pytest.approx(96_500.0)
    assert report.realized_pnl == pytest.approx(500.0)
    assert report.unrealized_pnl == pytest.approx(1_200.0)
    assert report.total_pnl == pytest.approx(1_700.0)
    assert payload["positions"][0]["contracts"] == 2
    assert payload["positions"][0]["average_price"] == pytest.approx(20.0)
    assert [event["event_type"] for event in payload["history"]] == ["ENTRY", "EXIT", "MARK"]
    assert payload["history"][1]["realized_pnl"] == pytest.approx(500.0)
    assert payload["history"][1]["open_contracts_after"] == 2


def test_br07_missing_mark_and_cap_breaches_are_blocked_by_safety_gate() -> None:
    report = build_paper_options_portfolio_report(
        [_fill(contracts=4, fill_price=40.00, label=HUMAN_REVIEW_REQUIRED)],
        [],
        datetime(2026, 7, 8, 16, 0),
        PaperOptionsConfig(starting_cash=100_000, max_position_premium_pct=0.03),
    )

    assert report.label == BLOCKED_BY_SAFETY_GATE
    assert report.positions[0].label == HUMAN_REVIEW_REQUIRED
    assert set(report.warnings) >= {
        "NVDA-20271217-C-180:missing_mark_uses_average_cost",
        "NVDA-20271217-C-180:position_premium_cap_review",
        "portfolio_premium_cap_review",
    }


def test_br07_exit_without_open_position_is_recorded_and_blocked() -> None:
    report = build_paper_options_portfolio_report(
        [_fill(side="exit", contracts=1, fill_price=25.00)],
        [],
        datetime(2026, 7, 8, 16, 0),
    )

    assert report.label == BLOCKED_BY_SAFETY_GATE
    assert report.positions == ()
    assert report.cash == pytest.approx(100_000.0)
    assert report.warnings == ("NVDA-20271217-C-180:exit_exceeds_open_contracts",)
    assert report.history[0].event_type == "EXIT"
    assert report.history[0].open_contracts_after == 0


def test_br07_payload_markdown_and_report_files_are_local_paper_outputs() -> None:
    report = build_paper_options_portfolio_report(
        [_fill()],
        [_mark()],
        datetime(2026, 7, 8, 16, 0),
    )
    markdown = render_markdown_paper_options_portfolio(report)

    assert "BR-07 Paper Options Portfolio Manager" in markdown
    assert "LIVE TRADING: DISABLED" in markdown
    assert "Local data only; no broker routing, broker calls, or live order submission." in markdown

    out_dir = Path(".codex_pytest_tmp/br07_paper_options_portfolio_manager_test")
    if out_dir.exists():
        shutil.rmtree(out_dir)

    json_path, md_path = write_paper_options_portfolio_report(report, out_dir)

    assert json_path.exists()
    assert md_path.exists()
    assert json.loads(json_path.read_text(encoding="utf-8"))["phase"] == "BR-07"
    assert "Paper Options Portfolio Manager" in md_path.read_text(encoding="utf-8")
    shutil.rmtree(out_dir)


def test_br07_validation_rejects_invalid_inputs_and_enabled_safety_state() -> None:
    with pytest.raises(ValueError, match="side must be entry or exit"):
        build_paper_options_portfolio_report([_fill(side="route")], [], datetime(2026, 7, 8, 16, 0))

    with pytest.raises(ValueError, match="symbol must be uppercase"):
        build_paper_options_portfolio_report(
            [_fill(symbol="nvda271217c00180000")],
            [],
            datetime(2026, 7, 8, 16, 0),
        )

    with pytest.raises(ValueError, match="label must be a safe"):
        build_paper_options_portfolio_report([_fill(label="UNSAFE")], [], datetime(2026, 7, 8, 16, 0))

    with pytest.raises(ValueError, match="mark_price cannot be negative"):
        build_paper_options_portfolio_report(
            [_fill()],
            [_mark(mark_price=-1.0)],
            datetime(2026, 7, 8, 16, 0),
        )

    with pytest.raises(ValueError, match="delta must be between"):
        build_paper_options_portfolio_report(
            [_fill()],
            [_mark(greeks=PaperOptionGreeks(delta=1.5, gamma=0.0, theta=0.0, vega=0.0))],
            datetime(2026, 7, 8, 16, 0),
        )

    with pytest.raises(ValueError, match="cannot enable live trading"):
        replace(
            build_paper_options_portfolio_report([_fill()], [_mark()], datetime(2026, 7, 8, 16, 0)),
            safety={"live_trading_enabled": True, "broker_order_call_performed": False},
        ).validate()
