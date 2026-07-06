from paper_trading.alpaca_config import AlpacaPaperConfig
from paper_trading.execution_gate import evaluate_paper_execution_gate
from paper_trading.order_intent import PaperOrderIntent
from paper_trading.paper_executor import execute_real_alpaca_paper_order


def valid_config():
    return AlpacaPaperConfig(
        api_key="paper_key",
        secret_key="paper_secret",
        base_url="https://paper-api.alpaca.markets",
        paper_only=True,
        confirm_live=False,
    )


def hold_intent():
    return PaperOrderIntent(
        timestamp_utc="2026-07-06T00:00:00+00:00",
        symbol="EEM",
        strategy="rsi_revert",
        requested_signal="HOLD",
        intent_action="HOLD",
        estimated_quantity=0,
        estimated_notional=0.0,
        latest_price=67.625,
        preflight_ready=True,
        blocked_reasons=[],
        reason="HOLD: RSI 51.18 between oversold 30 and overbought 70",
    )


def buy_intent():
    return PaperOrderIntent(
        timestamp_utc="2026-07-06T00:00:00+00:00",
        symbol="EEM",
        strategy="rsi_revert",
        requested_signal="BUY",
        intent_action="BUY",
        estimated_quantity=10,
        estimated_notional=676.25,
        latest_price=67.625,
        preflight_ready=True,
        blocked_reasons=[],
        reason="BUY signal approved by all risk gates.",
    )


def test_hold_execution_gate_is_no_action_even_when_order_submission_disabled():
    gate = evaluate_paper_execution_gate(
        config=valid_config(),
        intent=hold_intent(),
        order_submission_enabled=False,
    )

    assert gate.execution_allowed is True
    assert gate.execution_status == "NO_ACTION"
    assert gate.blocked_reasons == []
    assert gate.order_submitted is False
    assert gate.broker_call_performed is False
    assert gate.live_trading_enabled is False


def test_hold_real_paper_executor_is_no_action_even_when_real_execution_disabled():
    intent = hold_intent()
    gate = evaluate_paper_execution_gate(
        config=valid_config(),
        intent=intent,
        order_submission_enabled=False,
    )

    result = execute_real_alpaca_paper_order(
        config=valid_config(),
        intent=intent,
        execution_gate=gate,
        paper_client_factory=None,
        real_paper_execution_enabled=False,
        confirmation=None,
    )

    assert result.execution_status == "NO_ACTION"
    assert result.execution_attempted is False
    assert result.paper_client_used is False
    assert result.real_broker_client_used is False
    assert result.order_submission_to_real_broker_enabled is False
    assert result.live_trading_enabled is False
    assert result.blocked_reasons == []


def test_buy_still_blocks_when_order_submission_disabled():
    gate = evaluate_paper_execution_gate(
        config=valid_config(),
        intent=buy_intent(),
        order_submission_enabled=False,
    )

    assert gate.execution_allowed is False
    assert gate.execution_status == "BLOCKED"
    assert "order submission is disabled" in gate.blocked_reasons
