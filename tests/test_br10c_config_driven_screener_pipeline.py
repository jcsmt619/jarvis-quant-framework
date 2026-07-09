from __future__ import annotations

import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from engines.moonshot.deterministic.br10c_config_driven_screener_pipeline import (
    ScreenerCandidate,
    ScreenerFilterGroup,
    ScreenerMetricRange,
    ScreenerPipelineConfig,
    ScreenerRankingRule,
    build_screener_pipeline_report,
    load_screener_fixture,
    load_screener_pipeline_report,
    render_markdown_screener_pipeline,
    safety_manifest,
    screener_pipeline_payload,
    write_screener_pipeline_report,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


MODULE_PATH = Path("engines/moonshot/deterministic/br10c_config_driven_screener_pipeline.py")


def test_br10c_safety_manifest_is_paper_only_research_queue_and_disabled() -> None:
    manifest = safety_manifest()

    assert manifest["phase"] == "BR-10C"
    assert manifest["labels"] == (
        RESEARCH_ONLY,
        MONITOR_ONLY,
        PAPER_ONLY,
        HUMAN_REVIEW_REQUIRED,
        BLOCKED_BY_SAFETY_GATE,
    )
    assert manifest["paper_only"] is True
    assert manifest["human_review_required"] is True
    assert manifest["ranked_research_queue_only"] is True
    assert manifest["trade_signals_generated"] is False
    assert manifest["stock_schema_supported"] is True
    assert manifest["crypto_schema_supported"] is True
    assert manifest["real_paper_wrapper_connected"] is False
    assert manifest["real_paper_wrapper_attempted"] is False
    assert manifest["real_paper_order_submitted"] is False
    assert manifest["broker_order_call_performed"] is False
    assert manifest["broker_order_submitted"] is False
    assert manifest["broker_order_routing_enabled"] is False
    assert manifest["live_trading_enabled"] is False
    assert manifest["LIVE TRADING"] == "DISABLED"


def test_br10c_loads_fixture_and_builds_ranked_stock_crypto_research_queue() -> None:
    report = load_screener_pipeline_report()
    payload = screener_pipeline_payload(report)

    assert payload["phase"] == "BR-10C"
    assert payload["label"] == HUMAN_REVIEW_REQUIRED
    assert payload["metrics"] == {
        "candidate_count": 6,
        "research_queue_count": 3,
        "blocked_count": 3,
        "stock_profile_count": 3,
        "crypto_profile_count": 3,
        "human_review_required_count": 6,
    }
    assert payload["dashboard"]["queue_symbols"] == ["NVDA", "BTC", "MSFT"]
    assert payload["dashboard"]["by_asset_class"] == {
        "crypto": ["BTC"],
        "stock": ["MSFT", "NVDA"],
    }
    assert [profile["rank"] for profile in payload["research_queue"]] == [1, 2, 3]
    assert {profile["label"] for profile in payload["research_queue"]} == {HUMAN_REVIEW_REQUIRED}
    assert all(profile["paper_only"] is True for profile in payload["research_queue"])
    assert all(profile["trade_signal"] is False for profile in payload["research_queue"])
    assert payload["safety"]["broker_order_call_performed"] is False


def test_br10c_filter_groups_block_failed_candidates_and_queue_limit() -> None:
    report = load_screener_pipeline_report()
    payload = screener_pipeline_payload(report)
    blocked = {profile["symbol"]: profile for profile in payload["blocked_profiles"]}

    assert blocked["SOL"]["blocked_reasons"] == ("queue_limit_exceeded",)
    assert blocked["XYZL"]["label"] == BLOCKED_BY_SAFETY_GATE
    assert set(blocked["XYZL"]["blocked_reasons"]) >= {
        "stock_growth_quality:required_tags_missing",
        "stock_growth_quality:sector_filter_mismatch",
        "stock_growth_quality:liquidity_score_below_minimum",
    }
    assert set(blocked["DOGE"]["blocked_reasons"]) >= {
        "crypto_liquid_momentum:network_filter_mismatch",
        "crypto_liquid_momentum:drawdown_risk_above_maximum",
    }


def test_br10c_custom_config_can_return_crypto_only_without_blocked_profiles() -> None:
    _, candidates = load_screener_fixture()
    config = ScreenerPipelineConfig(
        filter_groups=(
            ScreenerFilterGroup(
                name="crypto_only",
                asset_classes=("crypto",),
                metric_ranges=(
                    ScreenerMetricRange(metric="liquidity_score", minimum=0.75),
                    ScreenerMetricRange(metric="drawdown_risk", maximum=0.60),
                ),
                required_tags=("liquid",),
                allowed_networks=("Bitcoin", "Solana"),
            ),
        ),
        ranking_rules=(ScreenerRankingRule(metric="liquidity_score", weight=1.0),),
        max_queue_size=5,
        include_blocked_profiles=False,
    )
    payload = screener_pipeline_payload(build_screener_pipeline_report(candidates, config))

    assert payload["dashboard"]["queue_symbols"] == ["BTC", "SOL"]
    assert payload["metrics"]["candidate_count"] == 2
    assert payload["metrics"]["blocked_count"] == 0
    assert {profile["asset_class"] for profile in payload["research_queue"]} == {"crypto"}


def test_br10c_markdown_and_report_files_are_dashboard_outputs() -> None:
    report = load_screener_pipeline_report()
    markdown = render_markdown_screener_pipeline(report)

    assert "BR-10C Track B Config Driven Screener Pipeline" in markdown
    assert "LIVE TRADING: DISABLED" in markdown
    assert "Ranked research queue only; entries are not trade signals." in markdown
    assert "No broker routing, broker calls, live trading, or order submission." in markdown
    assert "## Ranked Research Queue" in markdown

    out_dir = Path(".codex_pytest_tmp/br10c_config_driven_screener_pipeline_test")
    if out_dir.exists():
        shutil.rmtree(out_dir)

    json_path, md_path = write_screener_pipeline_report(report, out_dir)

    assert json_path.exists()
    assert md_path.exists()
    assert json.loads(json_path.read_text(encoding="utf-8"))["phase"] == "BR-10C"
    assert "Blocked Profiles" in md_path.read_text(encoding="utf-8")
    shutil.rmtree(out_dir)


def test_br10c_validation_rejects_invalid_config_candidates_and_enabled_safety() -> None:
    config, candidates = load_screener_fixture()

    with pytest.raises(ValueError, match="max_queue_size must be positive"):
        replace(config, max_queue_size=0).validate()

    with pytest.raises(ValueError, match="requires at least one candidate"):
        build_screener_pipeline_report([], config)

    with pytest.raises(ValueError, match="symbols must be unique"):
        build_screener_pipeline_report([candidates[0], candidates[0]], config)

    with pytest.raises(ValueError, match="stock candidates require sector"):
        replace(candidates[0], sector=None).validate()

    with pytest.raises(ValueError, match="crypto candidates require network"):
        replace(next(candidate for candidate in candidates if candidate.symbol == "BTC"), network=None).validate()

    with pytest.raises(ValueError, match="safe research"):
        replace(candidates[0], label="UNSAFE_LABEL").validate()

    report = build_screener_pipeline_report(candidates, config)
    with pytest.raises(ValueError, match="cannot set live_trading_enabled"):
        replace(report, safety={**report.safety, "live_trading_enabled": True}).validate()

    with pytest.raises(ValueError, match="cannot generate trade signals"):
        replace(report, safety={**report.safety, "trade_signals_generated": True}).validate()


def test_br10c_source_does_not_introduce_forbidden_execution_labels() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    disallowed = [
        "BUY" + "_NOW",
        "SELL" + "_NOW",
        "EXECUTE" + "_TRADE",
        "AUTO" + "_TRADE",
    ]

    for label in disallowed:
        assert label not in source


def test_br10c_candidate_schema_requires_supported_asset_class() -> None:
    candidate = ScreenerCandidate(
        symbol="TEST",
        name="Test Candidate",
        asset_class="future",
        as_of=load_screener_pipeline_report().as_of,
        metrics={"liquidity_score": 1.0},
        sector="Technology",
    )

    with pytest.raises(ValueError, match="asset_class must be stock or crypto"):
        candidate.validate()
