from __future__ import annotations

import json
import shutil
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path

import pytest

from engines.moonshot.deterministic.daily_position_monitor_alert_engine import (
    DailyPositionAlert,
    DailyPositionMonitorConfig,
    PositionMonitorSnapshot,
    build_daily_position_monitor_report,
    daily_position_monitor_payload,
    render_markdown_daily_position_monitor,
    safety_manifest,
    write_daily_position_monitor_report,
)
from engines.moonshot.deterministic.paper_options_portfolio_manager import (
    PaperOptionFill,
    PaperOptionGreeks,
    PaperOptionMark,
    build_paper_options_portfolio_report,
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
        "contract_id": "NVDA-20261218-C-180",
        "symbol": "NVDA261218C00180000",
        "underlying_symbol": "NVDA",
        "contract_type": "call",
        "strike": 180.0,
        "expiration": date(2026, 12, 18),
        "filled_at": datetime(2026, 7, 8, 15, 30),
        "side": "entry",
        "contracts": 3,
        "fill_price": 28.50,
        "thesis_id": "thesis-nvda-ai-capex",
        "label": PAPER_ONLY,
    }
    values.update(overrides)
    return PaperOptionFill(**values)


def _mark(**overrides: object) -> PaperOptionMark:
    values = {
        "contract_id": "NVDA-20261218-C-180",
        "marked_at": datetime(2026, 7, 9, 16, 0),
        "mark_price": 24.00,
        "greeks": PaperOptionGreeks(delta=0.52, gamma=0.011, theta=-0.021, vega=0.39, rho=0.18),
        "label": MONITOR_ONLY,
    }
    values.update(overrides)
    return PaperOptionMark(**values)


def _portfolio():
    return build_paper_options_portfolio_report(
        [_fill()],
        [_mark()],
        datetime(2026, 7, 9, 16, 0),
    )


def _snapshot(**overrides: object) -> PositionMonitorSnapshot:
    values = {
        "contract_id": "NVDA-20261218-C-180",
        "observed_at": datetime(2026, 7, 9, 16, 0),
        "previous_underlying_price": 150.0,
        "current_underlying_price": 168.0,
        "previous_bid_ask_spread_pct": 0.08,
        "current_bid_ask_spread_pct": 0.20,
        "previous_implied_volatility": 0.42,
        "current_implied_volatility": 0.55,
        "thesis_valid": False,
        "thesis_status_note": "thesis_invalidation_level_breached",
        "previous_risk_gate_label": PAPER_ONLY,
        "current_risk_gate_label": BLOCKED_BY_SAFETY_GATE,
        "risk_gate_reasons": ("position_loss_breach", "theta_decay_breach"),
        "label": MONITOR_ONLY,
    }
    values.update(overrides)
    return PositionMonitorSnapshot(**values)


def test_br08_safety_manifest_is_human_review_alerts_only_and_disabled() -> None:
    manifest = safety_manifest()

    assert manifest["phase"] == "BR-08"
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
    assert manifest["paper_positions_only"] is True
    assert manifest["human_review_alerts_only"] is True
    assert manifest["real_paper_wrapper_connected"] is False
    assert manifest["real_paper_wrapper_attempted"] is False
    assert manifest["real_paper_order_submitted"] is False
    assert manifest["broker_order_call_performed"] is False
    assert manifest["broker_order_submitted"] is False
    assert manifest["broker_order_routing_enabled"] is False
    assert manifest["live_trading_enabled"] is False
    assert manifest["LIVE TRADING"] == "DISABLED"


def test_br08_flags_required_daily_position_monitor_alert_categories() -> None:
    report = build_daily_position_monitor_report(
        _portfolio(),
        [_snapshot()],
        datetime(2026, 7, 9, 16, 0),
        DailyPositionMonitorConfig(
            theta_decay_alert_abs=5.0,
            near_expiration_dte=180,
            urgent_expiration_dte=45,
            max_bid_ask_spread_pct=0.18,
            spread_degradation_pct=0.05,
            volatility_change_pct=0.20,
            underlying_price_move_pct=0.08,
        ),
    )
    payload = daily_position_monitor_payload(report)
    categories = {alert["category"] for alert in payload["alerts"]}
    reasons = {alert["reason"] for alert in payload["alerts"]}

    assert payload["phase"] == "BR-08"
    assert payload["label"] == HUMAN_REVIEW_REQUIRED
    assert payload["metrics"] == {
        "position_count": 1,
        "snapshot_count": 1,
        "alert_count": 9,
        "warning_count": 0,
        "human_review_required_alert_count": 9,
    }
    assert categories == {
        "theta_decay",
        "dte_threshold",
        "spread_degradation",
        "thesis_invalidation",
        "volatility_change",
        "price_move",
        "risk_gate_change",
    }
    assert "theta_decay_threshold_reached" in reasons
    assert "near_dte_threshold_reached" in reasons
    assert "bid_ask_spread_above_threshold" in reasons
    assert "bid_ask_spread_degraded" in reasons
    assert "thesis_invalidation_level_breached" in reasons
    assert "implied_volatility_change_threshold_reached" in reasons
    assert "underlying_price_move_threshold_reached" in reasons
    assert "risk_gate_label_changed" in reasons
    assert "position_loss_breach,theta_decay_breach" in reasons
    assert {alert["label"] for alert in payload["alerts"]} == {HUMAN_REVIEW_REQUIRED}
    assert all(alert["human_review_required"] is True for alert in payload["alerts"])
    assert all(alert["live_trading_enabled"] is False for alert in payload["alerts"])
    assert all(alert["broker_order_call_performed"] is False for alert in payload["alerts"])


def test_br08_no_alert_snapshot_keeps_report_monitor_only() -> None:
    report = build_daily_position_monitor_report(
        _portfolio(),
        [
            _snapshot(
                previous_underlying_price=150.0,
                current_underlying_price=153.0,
                previous_bid_ask_spread_pct=0.08,
                current_bid_ask_spread_pct=0.09,
                previous_implied_volatility=0.42,
                current_implied_volatility=0.44,
                thesis_valid=True,
                thesis_status_note="thesis_still_valid",
                previous_risk_gate_label=PAPER_ONLY,
                current_risk_gate_label=PAPER_ONLY,
                risk_gate_reasons=(),
            )
        ],
        datetime(2026, 7, 9, 16, 0),
        DailyPositionMonitorConfig(theta_decay_alert_abs=10.0, near_expiration_dte=90),
    )

    assert report.label == MONITOR_ONLY
    assert report.alerts == ()
    assert report.warnings == ()


def test_br08_missing_snapshot_creates_human_review_alert_and_warning() -> None:
    report = build_daily_position_monitor_report(
        _portfolio(),
        [],
        datetime(2026, 7, 9, 16, 0),
    )

    assert report.label == HUMAN_REVIEW_REQUIRED
    assert report.warnings == ("NVDA-20261218-C-180:missing_monitor_snapshot",)
    assert report.alerts[0].category == "risk_gate_change"
    assert report.alerts[0].reason == "missing_daily_monitor_snapshot"
    assert report.alerts[0].label == HUMAN_REVIEW_REQUIRED


def test_br08_payload_markdown_and_report_files_are_local_monitor_outputs() -> None:
    report = build_daily_position_monitor_report(
        _portfolio(),
        [_snapshot()],
        datetime(2026, 7, 9, 16, 0),
    )
    markdown = render_markdown_daily_position_monitor(report)

    assert "BR-08 Daily Position Monitor Alert Engine" in markdown
    assert "LIVE TRADING: DISABLED" in markdown
    assert "alerts are human-review-required" in markdown
    assert "No broker routing, broker calls, live trading, or order submission." in markdown

    out_dir = Path(".codex_pytest_tmp/br08_daily_position_monitor_alert_engine_test")
    if out_dir.exists():
        shutil.rmtree(out_dir)

    json_path, md_path = write_daily_position_monitor_report(report, out_dir)

    assert json_path.exists()
    assert md_path.exists()
    assert json.loads(json_path.read_text(encoding="utf-8"))["phase"] == "BR-08"
    assert "Human Review Alerts" in md_path.read_text(encoding="utf-8")
    shutil.rmtree(out_dir)


def test_br08_validation_rejects_invalid_inputs_and_enabled_safety_state() -> None:
    with pytest.raises(ValueError, match="urgent_expiration_dte cannot exceed"):
        DailyPositionMonitorConfig(near_expiration_dte=30, urgent_expiration_dte=45).validate()

    with pytest.raises(ValueError, match="symbol must be uppercase"):
        replace(
            DailyPositionAlert(
                alert_id="alert-1",
                contract_id="NVDA-20261218-C-180",
                underlying_symbol="nvda",
                category="price_move",
                severity="WARN",
                reason="underlying_price_move_threshold_reached",
                observed_value=0.10,
                threshold=0.08,
            )
        ).validate()

    with pytest.raises(ValueError, match="must be human-review-required"):
        replace(
            DailyPositionAlert(
                alert_id="alert-1",
                contract_id="NVDA-20261218-C-180",
                underlying_symbol="NVDA",
                category="price_move",
                severity="WARN",
                reason="underlying_price_move_threshold_reached",
                observed_value=0.10,
                threshold=0.08,
            ),
            label=MONITOR_ONLY,
        ).validate()

    with pytest.raises(ValueError, match="safe research"):
        _snapshot(current_risk_gate_label="UNSAFE").validate()

    with pytest.raises(ValueError, match="cannot enable live trading"):
        replace(
            build_daily_position_monitor_report(_portfolio(), [_snapshot()], datetime(2026, 7, 9, 16, 0)),
            safety={"live_trading_enabled": True, "broker_order_call_performed": False},
        ).validate()
