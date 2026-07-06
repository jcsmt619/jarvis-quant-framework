import pytest

from paper_trading.alpaca_config import AlpacaConfigError, AlpacaPaperConfig
from paper_trading.execution_gate import (
    evaluate_paper_execution_gate,
    write_paper_execution_gate_result,
)
from paper_trading.order_intent import PaperOrderIntent


def valid_config(**overrides):
    values = {
        "api_key": "paper_key",
        "secret_key": "paper_secret",
        "base_url": "https://paper-api.alpaca.markets",
        "paper_only": True,
        "confirm_live": False,
    }
    values.update(overrides)
    return AlpacaPaperConfig(**values)


def make_intent(**overrides):
    values = {
        "timestamp_utc": "2026-07-05T00:00:00+00:00",
        "symbol": "EEM",
        "strategy": "rsi_revert",
        "requested_signal": "HOLD",
        "intent_action": "HOLD",
        "estimated_quantity": 0,
        "estimated_notional": 0.0,
        "latest_price": 65.0,
        "preflight_ready": True,
        "blocked_reasons": [],
        "reason": "HOLD: RSI neutral",
        "order_submission_enabled": False,
        "live_trading_enabled": False,
        "broker_call_performed": False,
    }
    values.update(overrides)
    return PaperOrderIntent(**values)


def test_gate_blocks_by_default_even_for_valid_buy_intent():
    result = evaluate_paper_execution_gate(
        config=valid_config(),
        intent=make_intent(
            requested_signal="BUY",
            intent_action="BUY",
            estimated_quantity=100,
            estimated_notional=6500.0,
        ),
    )

    assert result.execution_allowed is False
    assert result.execution_status == "BLOCKED"
    assert "order submission is disabled" in result.blocked_reasons
    assert result.order_submitted is False
    assert result.broker_call_performed is False
    assert result.live_trading_enabled is False


def test_gate_allows_valid_buy_only_when_submission_flag_enabled():
    result = evaluate_paper_execution_gate(
        config=valid_config(),
        intent=make_intent(
            requested_signal="BUY",
            intent_action="BUY",
            estimated_quantity=100,
            estimated_notional=6500.0,
        ),
        order_submission_enabled=True,
    )

    assert result.execution_allowed is True
    assert result.execution_status == "ALLOWED"
    assert result.blocked_reasons == []
    assert result.order_submitted is False
    assert result.broker_call_performed is False


def test_gate_allows_valid_exit_only_when_submission_flag_enabled():
    result = evaluate_paper_execution_gate(
        config=valid_config(),
        intent=make_intent(
            requested_signal="EXIT",
            intent_action="EXIT",
            estimated_quantity=25,
            estimated_notional=1625.0,
        ),
        order_submission_enabled=True,
    )

    assert result.execution_allowed is True
    assert result.execution_status == "ALLOWED"
    assert result.order_submitted is False
    assert result.broker_call_performed is False


def test_gate_blocks_hold_when_submission_disabled():
    result = evaluate_paper_execution_gate(
        config=valid_config(),
        intent=make_intent(),
    )

    assert result.execution_allowed is True
    assert result.execution_status == "NO_ACTION"
    assert result.blocked_reasons == []
    assert result.order_submission_enabled is False
    assert result.live_trading_enabled is False
    assert result.broker_call_performed is False
    assert result.order_submitted is False

def test_gate_allows_hold_when_submission_flag_enabled_but_still_submits_nothing():
    result = evaluate_paper_execution_gate(
        config=valid_config(),
        intent=make_intent(),
        order_submission_enabled=True,
    )

    assert result.execution_allowed is True
    assert result.execution_status == "NO_ACTION"
    assert result.blocked_reasons == []
    assert result.order_submission_enabled is False
    assert result.live_trading_enabled is False
    assert result.broker_call_performed is False
    assert result.order_submitted is False

def test_gate_rejects_live_endpoint():
    with pytest.raises(AlpacaConfigError):
        evaluate_paper_execution_gate(
            config=valid_config(base_url="https://api.alpaca.markets"),
            intent=make_intent(),
            order_submission_enabled=True,
        )


def test_gate_rejects_intent_that_claims_live_trading_enabled():
    result = evaluate_paper_execution_gate(
        config=valid_config(),
        intent=make_intent(live_trading_enabled=True),
        order_submission_enabled=True,
    )

    assert result.execution_allowed is False
    assert "intent live_trading_enabled must be False" in result.blocked_reasons


def test_gate_rejects_intent_that_claims_broker_call_already_performed():
    result = evaluate_paper_execution_gate(
        config=valid_config(),
        intent=make_intent(broker_call_performed=True),
        order_submission_enabled=True,
    )

    assert result.execution_allowed is False
    assert "intent already reports broker_call_performed=True" in result.blocked_reasons


def test_gate_rejects_buy_with_zero_quantity():
    result = evaluate_paper_execution_gate(
        config=valid_config(),
        intent=make_intent(
            requested_signal="BUY",
            intent_action="BUY",
            estimated_quantity=0,
            estimated_notional=0.0,
        ),
        order_submission_enabled=True,
    )

    assert result.execution_allowed is False
    assert "estimated quantity must be positive for BUY/EXIT" in result.blocked_reasons


def test_gate_rejects_unsupported_intent_action():
    result = evaluate_paper_execution_gate(
        config=valid_config(),
        intent=make_intent(intent_action="SHORT"),
        order_submission_enabled=True,
    )

    assert result.execution_allowed is False
    assert "unsupported intent action: 'SHORT'" in result.blocked_reasons


def test_write_gate_result_creates_json_without_secrets(tmp_path):
    result = evaluate_paper_execution_gate(
        config=valid_config(),
        intent=make_intent(),
    )

    path = write_paper_execution_gate_result(result, output_dir=tmp_path)
    text = path.read_text(encoding="utf-8")

    assert path.exists()
    assert '"execution_status": "NO_ACTION"' in text
    assert "paper_key" not in text
    assert "paper_secret" not in text
