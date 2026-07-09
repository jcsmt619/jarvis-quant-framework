from __future__ import annotations

import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from engines.moonshot.deterministic.candidate_universe_builder import (
    CandidateUniverseConfig,
    build_candidate_universe_report,
    candidate_universe_payload,
    load_candidate_records,
    load_candidate_universe_report,
    render_markdown_candidate_universe,
    safety_manifest,
    write_candidate_universe_report,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


def _config(**overrides: object) -> CandidateUniverseConfig:
    values = {
        "allowed_sectors": ("Technology", "Consumer Discretionary"),
        "min_average_volume_30d": 1_000_000,
        "min_dollar_volume_30d": 50_000_000.0,
        "min_price_trend_60d_pct": -0.05,
        "max_realized_volatility_30d": 0.75,
        "required_catalyst_tags": (),
        "allowed_market_cap_buckets": ("mega", "large", "mid"),
        "require_options_available": True,
        "max_candidates": 10,
    }
    values.update(overrides)
    return CandidateUniverseConfig(**values)


def test_br02_safety_manifest_is_disabled_and_research_only() -> None:
    manifest = safety_manifest()

    assert manifest["phase"] == "BR-02"
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
    assert manifest["real_paper_wrapper_connected"] is False
    assert manifest["real_paper_wrapper_attempted"] is False
    assert manifest["real_paper_order_submitted"] is False
    assert manifest["broker_order_call_performed"] is False
    assert manifest["broker_order_submitted"] is False
    assert manifest["broker_order_routing_enabled"] is False
    assert manifest["live_trading_enabled"] is False
    assert manifest["LIVE TRADING"] == "DISABLED"


def test_br02_loads_fixture_and_builds_deterministic_watchlists() -> None:
    report = load_candidate_universe_report(config=_config())
    payload = candidate_universe_payload(report)

    assert payload["phase"] == "BR-02"
    assert payload["label"] == BLOCKED_BY_SAFETY_GATE
    assert payload["metrics"] == {
        "candidate_count": 5,
        "included_count": 3,
        "blocked_count": 2,
        "human_review_required_count": 5,
    }
    assert payload["watchlists"]["primary"] == ["NVDA", "MSFT", "TSLA"]
    assert payload["watchlists"]["by_sector"] == {
        "Consumer Discretionary": ["TSLA"],
        "Technology": ["MSFT", "NVDA"],
    }
    assert payload["watchlists"]["catalyst_review"]["ai_datacenter"] == ["MSFT", "NVDA"]
    assert {item["label"] for item in payload["included_candidates"]} == {MONITOR_ONLY}
    assert all(item["human_review_required"] for item in payload["included_candidates"])
    assert payload["safety"]["broker_order_call_performed"] is False


def test_br02_blocks_candidates_for_filter_reasons() -> None:
    report = load_candidate_universe_report(config=_config())
    payload = candidate_universe_payload(report)
    blocked = {item["symbol"]: item for item in payload["blocked_candidates"]}

    assert blocked["XYZL"]["label"] == BLOCKED_BY_SAFETY_GATE
    assert set(blocked["XYZL"]["reasons"]) >= {
        "sector_filter_mismatch",
        "average_volume_below_minimum",
        "dollar_volume_below_minimum",
        "market_cap_bucket_filter_mismatch",
        "options_not_available",
    }
    assert blocked["ABCD"]["reasons"] == (
        "price_trend_below_minimum",
        "volatility_above_maximum",
    )


def test_br02_required_catalyst_and_candidate_limit_are_deterministic() -> None:
    report = load_candidate_universe_report(
        config=_config(required_catalyst_tags=("ai_datacenter",), max_candidates=1)
    )
    payload = candidate_universe_payload(report)

    assert payload["watchlists"]["primary"] == ["NVDA"]
    blocked = {item["symbol"]: item for item in payload["blocked_candidates"]}
    assert blocked["MSFT"]["reasons"] == ("candidate_limit_exceeded",)
    assert blocked["TSLA"]["reasons"] == ("required_catalyst_tags_missing",)


def test_br02_payload_markdown_and_report_files_are_human_review_outputs() -> None:
    report = load_candidate_universe_report(config=_config())
    markdown = render_markdown_candidate_universe(report)

    assert "BR-02 Candidate Universe Builder" in markdown
    assert "LIVE TRADING: DISABLED" in markdown
    assert "Static candidate universe report only; no broker routing or order submission." in markdown
    assert "Report-level state remains blocked by safety gate." in markdown

    out_dir = Path(".codex_pytest_tmp/br02_candidate_universe_test")
    if out_dir.exists():
        shutil.rmtree(out_dir)

    json_path, md_path = write_candidate_universe_report(report, out_dir)

    assert json_path.exists()
    assert md_path.exists()
    assert json.loads(json_path.read_text(encoding="utf-8"))["phase"] == "BR-02"
    assert "Primary Watchlist" in md_path.read_text(encoding="utf-8")
    shutil.rmtree(out_dir)


def test_br02_validation_rejects_invalid_config_labels_and_empty_input() -> None:
    with pytest.raises(ValueError, match="max_candidates must be positive"):
        build_candidate_universe_report(load_candidate_records(), config=_config(max_candidates=0))

    with pytest.raises(ValueError, match="requires at least one candidate"):
        build_candidate_universe_report([], config=_config())

    candidate = load_candidate_records()[0]
    with pytest.raises(ValueError, match="symbols must be unique"):
        build_candidate_universe_report([candidate, candidate], config=_config())

    with pytest.raises(ValueError, match="symbol must be uppercase"):
        replace(candidate, symbol="nvda").validate()

    with pytest.raises(ValueError, match="safe research"):
        replace(candidate, label="UNSAFE_LABEL").validate()
