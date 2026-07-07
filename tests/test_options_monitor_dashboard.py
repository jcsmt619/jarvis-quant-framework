from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path

import pytest

from engines.moonshot.deterministic.leaps_research_engine import (
    LeapsResearchInput,
    build_leaps_research_memo,
)
from engines.moonshot.deterministic.options_monitor_dashboard import (
    REQUIRED_LABELS,
    OptionsMonitorConfig,
    build_dashboard_payload,
    build_options_monitor_dashboard,
    render_markdown_dashboard,
    safety_manifest,
    write_options_monitor_report,
)
from engines.moonshot.deterministic.options_research import (
    GreeksSnapshot,
    OptionThesis,
    build_options_research_memo,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


def _option_memo(**overrides: object):
    values = {
        "symbol": "NVDA",
        "contract_type": "call",
        "strike": 180.0,
        "underlying_price": 150.0,
        "expiration": date(2027, 6, 18),
        "as_of": date(2026, 7, 7),
        "thesis": "Research-only upside convexity setup tied to datacenter growth.",
        "catalyst": "Earnings revision cycle and product launch window.",
        "invalidation": "Revenue growth decelerates or IV expands beyond research range.",
        "target_note": "Monitor upside scenario; no trade instruction.",
        "stop_note": "Flag for review if thesis breaks or option decay accelerates.",
        "research_label": HUMAN_REVIEW_REQUIRED,
    }
    values.update(overrides)
    return build_options_research_memo(
        OptionThesis(**values),
        GreeksSnapshot(delta=0.55, gamma=0.03, theta=-0.01, vega=0.12, rho=0.04),
    )


def _leaps_memo(**overrides: object):
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
    return build_leaps_research_memo(LeapsResearchInput(**values))


def test_13e_safety_manifest_is_research_only_and_disabled() -> None:
    manifest = safety_manifest()

    assert REQUIRED_LABELS == (RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED)
    assert manifest["phase"] == "13E"
    assert manifest["research_only"] is True
    assert manifest["monitor_only"] is True
    assert manifest["paper_only"] is True
    assert manifest["human_review_required"] is True
    assert manifest["live_trading_enabled"] is False
    assert manifest["broker_order_routing_enabled"] is False
    assert manifest["broker_order_call_performed"] is False
    assert manifest["broker_order_submitted"] is False
    assert manifest["LIVE TRADING"] == "DISABLED"


def test_13e_builds_static_monitor_rows_from_options_and_leaps_memos() -> None:
    dashboard = build_options_monitor_dashboard([_option_memo()], [_leaps_memo()])
    payload = build_dashboard_payload(dashboard)

    assert dashboard.metrics["row_count"] == 2
    assert dashboard.metrics["monitor_allowed_count"] == 2
    assert dashboard.metrics["blocked_count"] == 0
    assert payload["rows"][0]["source_phase"] == "13B"
    assert payload["rows"][1]["source_phase"] == "13D"
    assert {row["label"] for row in payload["rows"]} == {MONITOR_ONLY}
    assert all(row["human_review_required"] for row in payload["rows"])
    assert payload["safety"]["broker_order_submitted"] is False


def test_13e_blocks_monitor_rows_with_near_expiration_stale_or_liquidity_alerts() -> None:
    near_option = _option_memo(expiration=date(2026, 7, 31))
    stale_leaps = _leaps_memo(data_age_minutes=90, open_interest=25, volume=0)

    dashboard = build_options_monitor_dashboard([near_option], [stale_leaps])

    assert dashboard.metrics["blocked_count"] == 2
    assert dashboard.rows[0].label == BLOCKED_BY_SAFETY_GATE
    assert "near_expiration_monitor_review" in dashboard.rows[0].alerts
    assert dashboard.rows[1].label == BLOCKED_BY_SAFETY_GATE
    assert set(dashboard.rows[1].alerts) >= {
        "stale_options_data",
        "open_interest_liquidity_warning",
        "volume_liquidity_warning",
        "HUMAN_REVIEW_REQUIRED",
    }


def test_13e_payload_and_markdown_are_static_research_outputs() -> None:
    dashboard = build_options_monitor_dashboard([_option_memo()], [_leaps_memo()])
    payload = build_dashboard_payload(dashboard)
    markdown = render_markdown_dashboard(dashboard)

    assert payload["phase"] == "13E"
    assert payload["module"] == "Options Monitor Dashboard"
    assert payload["metrics"]["human_review_required_count"] == 2
    assert "LIVE TRADING: DISABLED" in markdown
    assert "Static monitor dashboard only; no broker routing or order submission." in markdown
    assert "Monitor Rows" in markdown


def test_13e_write_options_monitor_report_outputs_json_and_markdown() -> None:
    dashboard = build_options_monitor_dashboard([_option_memo()], [_leaps_memo()])
    out_dir = Path(".codex_pytest_tmp/options_monitor_dashboard_test")
    if out_dir.exists():
        shutil.rmtree(out_dir)

    json_path, md_path = write_options_monitor_report(dashboard, out_dir)

    assert json_path.exists()
    assert md_path.exists()
    assert json.loads(json_path.read_text(encoding="utf-8"))["phase"] == "13E"
    assert "Options Monitor Dashboard" in md_path.read_text(encoding="utf-8")
    shutil.rmtree(out_dir)


def test_13e_config_validation_rejects_invalid_thresholds() -> None:
    with pytest.raises(ValueError, match="near_expiration_dte"):
        build_options_monitor_dashboard(
            [_option_memo()],
            config=OptionsMonitorConfig(near_expiration_dte=0),
        )
