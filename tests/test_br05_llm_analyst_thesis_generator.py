from __future__ import annotations

import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from engines.moonshot.deterministic.llm_analyst_thesis_generator import (
    analyst_thesis_payload,
    build_analyst_prompt_packages,
    build_analyst_thesis_report,
    load_fixture_analyst_responses,
    parse_analyst_response,
    render_markdown_analyst_thesis,
    safety_manifest,
    write_analyst_thesis_report,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


def test_br05_safety_manifest_is_local_disabled_and_research_only() -> None:
    manifest = safety_manifest()

    assert manifest["phase"] == "BR-05"
    assert manifest["labels"] == (
        RESEARCH_ONLY,
        MONITOR_ONLY,
        PAPER_ONLY,
        HUMAN_REVIEW_REQUIRED,
        BLOCKED_BY_SAFETY_GATE,
    )
    assert manifest["research_only"] is True
    assert manifest["paper_only"] is True
    assert manifest["human_review_required"] is True
    assert manifest["live_api_calls_required"] is False
    assert manifest["local_prompt_packaging_only"] is True
    assert manifest["source_grounded_context_required"] is True
    assert manifest["real_paper_wrapper_connected"] is False
    assert manifest["real_paper_wrapper_attempted"] is False
    assert manifest["real_paper_order_submitted"] is False
    assert manifest["broker_order_call_performed"] is False
    assert manifest["broker_order_submitted"] is False
    assert manifest["broker_order_routing_enabled"] is False
    assert manifest["live_trading_enabled"] is False
    assert manifest["LIVE TRADING"] == "DISABLED"


def test_br05_builds_source_grounded_prompt_packages_from_contract_scores() -> None:
    packages = build_analyst_prompt_packages()

    assert len(packages) == 1
    package = packages[0]
    assert package.prompt_id == "BR-05-NVDA-20260708160000"
    assert package.symbol == "NVDA"
    assert package.label == HUMAN_REVIEW_REQUIRED
    assert package.contract_ids == (
        "NVDA-20271217-C-140",
        "NVDA-20271217-C-180",
        "NVDA-20271217-C-220",
    )
    assert package.source_context["phase"] == "BR-04"
    assert package.source_context["source_module"] == "Greeks IV Spread DTE Scoring"
    assert package.source_context["safety"]["live_trading_enabled"] is False
    assert "Use only the supplied JSON context" in package.system_prompt
    assert "Required response schema" in package.user_prompt
    assert "HUMAN_REVIEW_REQUIRED" in package.user_prompt


def test_br05_parses_fixture_response_into_human_review_record() -> None:
    package = build_analyst_prompt_packages()[0]
    responses = load_fixture_analyst_responses()
    record = parse_analyst_response(responses[package.prompt_id], package)

    assert record.thesis_id == "THESIS-BR05-NVDA-001"
    assert record.prompt_id == package.prompt_id
    assert record.symbol == "NVDA"
    assert record.label == HUMAN_REVIEW_REQUIRED
    assert record.research_only is True
    assert record.human_review_required is True
    assert record.live_trading_enabled is False
    assert record.broker_order_call_performed is False
    assert "NVDA-20271217-C-140" in record.source_citations


def test_br05_report_payload_markdown_and_files_are_local_review_outputs() -> None:
    packages = build_analyst_prompt_packages()
    report = build_analyst_thesis_report(packages, load_fixture_analyst_responses())
    payload = analyst_thesis_payload(report)
    markdown = render_markdown_analyst_thesis(report)

    assert payload["phase"] == "BR-05"
    assert payload["label"] == BLOCKED_BY_SAFETY_GATE
    assert payload["metrics"] == {
        "prompt_package_count": 1,
        "parsed_thesis_record_count": 1,
        "human_review_required_count": 2,
    }
    assert payload["safety"]["live_api_calls_required"] is False
    assert "BR-05 LLM Analyst Thesis Generator" in markdown
    assert "LIVE TRADING: DISABLED" in markdown
    assert "Local prompt packaging and response parsing only; no live API calls are required." in markdown

    out_dir = Path(".codex_pytest_tmp/br05_llm_analyst_thesis_generator_test")
    if out_dir.exists():
        shutil.rmtree(out_dir)

    json_path, md_path = write_analyst_thesis_report(report, out_dir)

    assert json_path.exists()
    assert md_path.exists()
    assert json.loads(json_path.read_text(encoding="utf-8"))["phase"] == "BR-05"
    assert "Parsed Thesis Records" in md_path.read_text(encoding="utf-8")
    shutil.rmtree(out_dir)


def test_br05_parser_rejects_mismatched_prompt_symbol_and_ungrounded_citations() -> None:
    package = build_analyst_prompt_packages()[0]
    payload = json.loads(load_fixture_analyst_responses()[package.prompt_id])

    bad_prompt = dict(payload, prompt_id="BR-05-NVDA-WRONG")
    with pytest.raises(ValueError, match="prompt_id must match"):
        parse_analyst_response(json.dumps(bad_prompt), package)

    bad_symbol = dict(payload, symbol="MSFT")
    with pytest.raises(ValueError, match="symbol must match"):
        parse_analyst_response(json.dumps(bad_symbol), package)

    bad_citation = dict(payload, source_citations=["UNSUPPLIED-SOURCE"])
    with pytest.raises(ValueError, match="source_citations"):
        parse_analyst_response(json.dumps(bad_citation), package)


def test_br05_validation_rejects_unsafe_labels_trading_flags_and_empty_inputs() -> None:
    package = build_analyst_prompt_packages()[0]
    payload = json.loads(load_fixture_analyst_responses()[package.prompt_id])

    unsafe_label = dict(payload, label="UNSAFE_LABEL")
    with pytest.raises(ValueError, match="safe research"):
        parse_analyst_response(json.dumps(unsafe_label), package)

    trading_enabled = dict(payload, **{"live_trading_" + "enabled": True})
    with pytest.raises(ValueError, match="cannot enable trading"):
        parse_analyst_response(json.dumps(trading_enabled), package)

    broker_call = dict(payload, **{"broker_order_call_" + "performed": True})
    with pytest.raises(ValueError, match="cannot enable trading"):
        parse_analyst_response(json.dumps(broker_call), package)

    with pytest.raises(ValueError, match="requires at least one prompt package"):
        build_analyst_thesis_report([])

    with pytest.raises(ValueError, match="must require human review"):
        replace(package, label=RESEARCH_ONLY).validate()
