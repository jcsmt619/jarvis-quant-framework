from __future__ import annotations

import json
import shutil
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path

import pytest

from engines.moonshot.deterministic.candidate_universe_builder import load_candidate_universe_report
from engines.moonshot.deterministic.daily_position_monitor_alert_engine import (
    DailyPositionMonitorConfig,
    PositionMonitorSnapshot,
    build_daily_position_monitor_report,
)
from engines.moonshot.deterministic.llm_analyst_thesis_generator import (
    build_analyst_thesis_report,
    load_fixture_analyst_responses,
)
from engines.moonshot.deterministic.local_operator_dashboard import (
    build_local_operator_dashboard_report,
    local_operator_dashboard_payload,
    render_markdown_local_operator_dashboard,
    safety_manifest,
    write_local_operator_dashboard_report,
)
from engines.moonshot.deterministic.paper_options_portfolio_manager import (
    PaperOptionFill,
    PaperOptionGreeks,
    PaperOptionMark,
    build_paper_options_portfolio_report,
)
from engines.moonshot.deterministic.trade_score_risk_gate import load_trade_score_risk_gate_report
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


def _fill(**overrides: object) -> PaperOptionFill:
    values = {
        "fill_id": "fill-br09-001",
        "contract_id": "NVDA-20271217-C-140",
        "symbol": "NVDA271217C00140000",
        "underlying_symbol": "NVDA",
        "contract_type": "call",
        "strike": 140.0,
        "expiration": date(2027, 12, 17),
        "filled_at": datetime(2026, 7, 8, 15, 30),
        "side": "entry",
        "contracts": 2,
        "fill_price": 32.00,
        "thesis_id": "THESIS-BR05-NVDA-001",
        "label": PAPER_ONLY,
    }
    values.update(overrides)
    return PaperOptionFill(**values)


def _mark(**overrides: object) -> PaperOptionMark:
    values = {
        "contract_id": "NVDA-20271217-C-140",
        "marked_at": datetime(2026, 7, 9, 16, 0),
        "mark_price": 35.25,
        "greeks": PaperOptionGreeks(delta=0.62, gamma=0.012, theta=-0.018, vega=0.42, rho=0.21),
        "label": MONITOR_ONLY,
    }
    values.update(overrides)
    return PaperOptionMark(**values)


def _snapshot(**overrides: object) -> PositionMonitorSnapshot:
    values = {
        "contract_id": "NVDA-20271217-C-140",
        "observed_at": datetime(2026, 7, 9, 16, 0),
        "previous_underlying_price": 150.0,
        "current_underlying_price": 166.0,
        "previous_bid_ask_spread_pct": 0.06,
        "current_bid_ask_spread_pct": 0.19,
        "previous_implied_volatility": 0.40,
        "current_implied_volatility": 0.54,
        "thesis_valid": True,
        "thesis_status_note": "thesis_still_valid",
        "previous_risk_gate_label": PAPER_ONLY,
        "current_risk_gate_label": PAPER_ONLY,
        "risk_gate_reasons": (),
        "label": MONITOR_ONLY,
    }
    values.update(overrides)
    return PositionMonitorSnapshot(**values)


def _portfolio():
    return build_paper_options_portfolio_report(
        [_fill()],
        [_mark()],
        datetime(2026, 7, 9, 16, 0),
    )


def _monitor():
    return build_daily_position_monitor_report(
        _portfolio(),
        [_snapshot()],
        datetime(2026, 7, 9, 16, 0),
        DailyPositionMonitorConfig(
            theta_decay_alert_abs=3.0,
            near_expiration_dte=730,
            urgent_expiration_dte=45,
            max_bid_ask_spread_pct=0.18,
            spread_degradation_pct=0.05,
            volatility_change_pct=0.20,
            underlying_price_move_pct=0.08,
        ),
    )


def _dashboard():
    return build_local_operator_dashboard_report(
        candidate_universe_report=load_candidate_universe_report(),
        trade_score_risk_gate_report=load_trade_score_risk_gate_report(),
        paper_options_portfolio_report=_portfolio(),
        daily_position_monitor_report=_monitor(),
        analyst_thesis_report=build_analyst_thesis_report(response_text_by_prompt_id=load_fixture_analyst_responses()),
    )


def test_br09_safety_manifest_is_read_only_static_and_disabled() -> None:
    manifest = safety_manifest()

    assert manifest["phase"] == "BR-09"
    assert manifest["labels"] == (
        RESEARCH_ONLY,
        MONITOR_ONLY,
        PAPER_ONLY,
        HUMAN_REVIEW_REQUIRED,
        BLOCKED_BY_SAFETY_GATE,
    )
    assert manifest["read_only"] is True
    assert manifest["static_output_only"] is True
    assert manifest["local_reports_only"] is True
    assert manifest["real_paper_wrapper_connected"] is False
    assert manifest["real_paper_wrapper_attempted"] is False
    assert manifest["real_paper_order_submitted"] is False
    assert manifest["broker_order_call_performed"] is False
    assert manifest["broker_order_submitted"] is False
    assert manifest["broker_order_routing_enabled"] is False
    assert manifest["live_trading_enabled"] is False
    assert manifest["LIVE TRADING"] == "DISABLED"


def test_br09_payload_combines_candidates_scores_positions_pnl_alerts_and_thesis_notes() -> None:
    report = _dashboard()
    payload = local_operator_dashboard_payload(report)
    nvda = next(candidate for candidate in payload["candidates"] if candidate["symbol"] == "NVDA")

    assert payload["phase"] == "BR-09"
    assert payload["label"] == HUMAN_REVIEW_REQUIRED
    assert payload["metrics"]["candidate_count"] == 5
    assert payload["metrics"]["paper_position_count"] == 1
    assert payload["metrics"]["alert_count"] == 6
    assert payload["metrics"]["thesis_note_count"] == 1
    assert payload["portfolio_pnl"]["total_pnl"] == 650.0
    assert nvda["candidate_score"] == 89
    assert nvda["risk_score"] is not None
    assert nvda["paper_position_count"] == 1
    assert nvda["paper_unrealized_pnl"] == 650.0
    assert nvda["alert_count"] == 6
    assert nvda["thesis_id"] == "THESIS-BR05-NVDA-001"
    assert nvda["label"] == HUMAN_REVIEW_REQUIRED
    assert all(alert["live_trading_enabled"] is False for alert in payload["alerts"])
    assert payload["safety_status"]["read_only"] is True
    assert payload["safety_status"]["live_trading_enabled"] is False


def test_br09_markdown_and_report_files_are_static_dashboard_outputs() -> None:
    report = _dashboard()
    markdown = render_markdown_local_operator_dashboard(report)

    assert "BR-09 Local Operator Dashboard" in markdown
    assert "LIVE TRADING: DISABLED" in markdown
    assert "Read-only local operator dashboard" in markdown
    assert "No broker routing, broker calls, live trading, or order submission." in markdown
    assert "## Paper Positions" in markdown
    assert "## Thesis Notes" in markdown

    out_dir = Path(".codex_pytest_tmp/br09_local_operator_dashboard_test")
    if out_dir.exists():
        shutil.rmtree(out_dir)

    json_path, md_path = write_local_operator_dashboard_report(report, out_dir)

    assert json_path.exists()
    assert md_path.exists()
    assert json.loads(json_path.read_text(encoding="utf-8"))["phase"] == "BR-09"
    assert "Safety Status" in md_path.read_text(encoding="utf-8")
    shutil.rmtree(out_dir)


def test_br09_validation_rejects_enabled_safety_state() -> None:
    report = _dashboard()

    with pytest.raises(ValueError, match="read-only"):
        replace(report, safety={**report.safety, "read_only": False}).validate()

    with pytest.raises(ValueError, match="cannot enable live trading"):
        replace(report, safety={**report.safety, "live_trading_enabled": True}).validate()

    with pytest.raises(ValueError, match="cannot enable broker routing"):
        replace(report, safety={**report.safety, "broker_order_routing_enabled": True}).validate()
