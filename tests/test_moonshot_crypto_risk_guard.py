from __future__ import annotations

import pytest

from engines.moonshot.deterministic.crypto_risk_guard import (
    REQUIRED_LABELS,
    CryptoRiskGuardConfig,
    CryptoRiskSnapshot,
    build_guard_payload,
    evaluate_crypto_risk_guard,
    render_markdown_guard,
    safety_manifest,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


def _snapshot(**overrides: object) -> CryptoRiskSnapshot:
    values = {
        "symbol": "BTC-USD",
        "account_drawdown_pct": 0.02,
        "daily_drawdown_pct": 0.01,
        "quote_volume_24h_usd": 2_500_000_000.0,
        "bid_ask_spread_pct": 0.001,
        "realized_volatility_24h_pct": 0.06,
        "realized_volatility_7d_pct": 0.20,
        "data_age_minutes": 3,
        "thesis": "Research-only crypto moonshot monitor.",
    }
    values.update(overrides)
    return CryptoRiskSnapshot(**values)


def test_13c_safety_manifest_is_research_only_and_disabled() -> None:
    manifest = safety_manifest()

    assert REQUIRED_LABELS == (RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED)
    assert manifest["phase"] == "13C"
    assert manifest["research_only"] is True
    assert manifest["monitor_only"] is True
    assert manifest["paper_only"] is True
    assert manifest["human_review_required"] is True
    assert manifest["exchange_credentials_required"] is False
    assert manifest["exchange_order_routing_enabled"] is False
    assert manifest["live_trading_enabled"] is False
    assert manifest["broker_order_routing_enabled"] is False
    assert manifest["broker_order_call_performed"] is False
    assert manifest["broker_order_submitted"] is False
    assert manifest["LIVE TRADING"] == "DISABLED"


def test_13c_clean_snapshot_passes_research_monitor_guard() -> None:
    result = evaluate_crypto_risk_guard(_snapshot())

    assert result.label == RESEARCH_ONLY
    assert result.monitor_allowed is True
    assert result.warnings == ()
    assert result.required_labels == REQUIRED_LABELS
    assert result.safety["LIVE TRADING"] == "DISABLED"


def test_13c_drawdown_caps_block_monitoring() -> None:
    result = evaluate_crypto_risk_guard(
        _snapshot(account_drawdown_pct=0.09, daily_drawdown_pct=0.04)
    )

    assert result.label == BLOCKED_BY_SAFETY_GATE
    assert result.monitor_allowed is False
    assert set(result.warnings) >= {
        "account_drawdown_cap_breach",
        "daily_drawdown_cap_breach",
        "HUMAN_REVIEW_REQUIRED",
    }


def test_13c_liquidity_and_volatility_filters_emit_warnings() -> None:
    result = evaluate_crypto_risk_guard(
        _snapshot(
            quote_volume_24h_usd=500_000.0,
            bid_ask_spread_pct=0.025,
            realized_volatility_24h_pct=0.30,
            realized_volatility_7d_pct=0.60,
            data_age_minutes=60,
        )
    )

    assert result.label == BLOCKED_BY_SAFETY_GATE
    assert set(result.warnings) >= {
        "liquidity_volume_warning",
        "liquidity_spread_warning",
        "volatility_24h_filter_breach",
        "volatility_7d_filter_breach",
        "stale_crypto_market_data",
        "HUMAN_REVIEW_REQUIRED",
    }


def test_13c_custom_config_changes_thresholds() -> None:
    result = evaluate_crypto_risk_guard(
        _snapshot(quote_volume_24h_usd=10_000_000.0),
        CryptoRiskGuardConfig(min_24h_quote_volume_usd=5_000_000.0),
    )

    assert result.monitor_allowed is True
    assert result.warnings == ()


def test_13c_payload_and_markdown_remain_research_outputs() -> None:
    result = evaluate_crypto_risk_guard(_snapshot(realized_volatility_24h_pct=0.25))
    payload = build_guard_payload(result)
    markdown = render_markdown_guard(result)

    assert payload["phase"] == "13C"
    assert payload["label"] == BLOCKED_BY_SAFETY_GATE
    assert payload["safety"]["exchange_credentials_required"] is False
    assert payload["safety"]["broker_order_submitted"] is False
    assert "LIVE TRADING: DISABLED" in markdown
    assert "no exchange credentials or order routing" in markdown


def test_13c_validation_rejects_invalid_snapshot_and_config() -> None:
    with pytest.raises(ValueError, match="symbol is required"):
        evaluate_crypto_risk_guard(_snapshot(symbol=" "))

    with pytest.raises(ValueError, match="account_drawdown_pct cannot be negative"):
        evaluate_crypto_risk_guard(_snapshot(account_drawdown_pct=-0.01))

    with pytest.raises(ValueError, match="max_data_age_minutes"):
        evaluate_crypto_risk_guard(
            _snapshot(),
            CryptoRiskGuardConfig(max_data_age_minutes=-1),
        )
