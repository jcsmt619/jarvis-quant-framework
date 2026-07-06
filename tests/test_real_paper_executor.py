from paper_trading.alpaca_config import AlpacaPaperConfig
from paper_trading.execution_gate import PaperExecutionGateResult
from paper_trading.order_intent import PaperOrderIntent
from paper_trading.paper_executor import (
    PAPER_ORDER_CONFIRMATION,
    execute_real_alpaca_paper_order,
)


def valid_config():
    return AlpacaPaperConfig(
        api_key="paper_key",
        secret_key="paper_secret",
        base_url="https://paper-api.alpaca.markets",
        paper_only=True,
        confirm_live=False,
    )


def live_config():
    return AlpacaPaperConfig(
        api_key="live_key",
        secret_key="live_secret",
        base_url="https://api.alpaca.markets",
        paper_only=True,
        confirm_live=False,
    )


def buy_intent():
    return PaperOrderIntent(
        timestamp_utc="2026-07-06T00:00:00+00:00",
        symbol="EEM",
        strategy="rsi_revert",
        requested_signal="BUY",
        intent_action="BUY",
        estimated_quantity=10,
        estimated_notional=657.10,
        latest_price=65.71,
        preflight_ready=True,
        blocked_reasons=[],
        reason="BUY signal approved by all risk gates.",
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
        latest_price=65.71,
        preflight_ready=True,
        blocked_reasons=[],
        reason="HOLD: RSI between thresholds.",
    )


def blocked_intent():
    return PaperOrderIntent(
        timestamp_utc="2026-07-06T00:00:00+00:00",
        symbol="EEM",
        strategy="rsi_revert",
        requested_signal="BUY",
        intent_action="BLOCKED",
        estimated_quantity=0,
        estimated_notional=0.0,
        latest_price=65.71,
        preflight_ready=False,
        blocked_reasons=["market_hours: market is closed"],
        reason="Preflight blocked paper intent generation.",
    )


def allowed_gate(intent=None):
    intent = intent or buy_intent()
    return PaperExecutionGateResult(
        timestamp_utc="2026-07-06T00:00:00+00:00",
        symbol=intent.symbol,
        strategy=intent.strategy,
        intent_action=intent.intent_action,
        requested_signal=intent.requested_signal,
        estimated_quantity=intent.estimated_quantity,
        estimated_notional=intent.estimated_notional,
        execution_allowed=True,
        execution_status="ALLOWED",
        blocked_reasons=[],
        order_submission_enabled=False,
        live_trading_enabled=False,
        broker_call_performed=False,
        order_submitted=False,
        order_id=None,
    )


def blocked_gate(intent=None):
    intent = intent or blocked_intent()
    return PaperExecutionGateResult(
        timestamp_utc="2026-07-06T00:00:00+00:00",
        symbol=intent.symbol,
        strategy=intent.strategy,
        intent_action=intent.intent_action,
        requested_signal=intent.requested_signal,
        estimated_quantity=intent.estimated_quantity,
        estimated_notional=intent.estimated_notional,
        execution_allowed=False,
        execution_status="BLOCKED",
        blocked_reasons=["market_hours: market is closed"],
        order_submission_enabled=False,
        live_trading_enabled=False,
        broker_call_performed=False,
        order_submitted=False,
        order_id=None,
    )


class FakeOrder:
    id = "paper_order_123"


class RecordingPaperClient:
    def __init__(self):
        self.submit_order_calls = []

    def submit_order(self, **kwargs):
        self.submit_order_calls.append(kwargs)
        return FakeOrder()


def test_real_paper_executor_disabled_by_default_blocks_without_client_use():
    client = RecordingPaperClient()

    result = execute_real_alpaca_paper_order(
        config=valid_config(),
        intent=buy_intent(),
        execution_gate=allowed_gate(),
        paper_client_factory=lambda: client,
    )

    assert result.execution_status == "BLOCKED"
    assert result.execution_attempted is False
    assert result.paper_client_used is False
    assert result.real_broker_client_used is False
    assert result.order_submission_to_real_broker_enabled is False
    assert result.live_trading_enabled is False
    assert result.blocked_reasons == ["real Alpaca paper execution is disabled"]
    assert client.submit_order_calls == []


def test_real_paper_executor_requires_confirmation_phrase():
    client = RecordingPaperClient()

    result = execute_real_alpaca_paper_order(
        config=valid_config(),
        intent=buy_intent(),
        execution_gate=allowed_gate(),
        paper_client_factory=lambda: client,
        real_paper_execution_enabled=True,
        confirmation="wrong phrase",
    )

    assert result.execution_status == "BLOCKED"
    assert result.execution_attempted is False
    assert result.blocked_reasons == ["paper order confirmation phrase is missing or incorrect"]
    assert client.submit_order_calls == []


def test_real_paper_executor_requires_client_factory():
    result = execute_real_alpaca_paper_order(
        config=valid_config(),
        intent=buy_intent(),
        execution_gate=allowed_gate(),
        paper_client_factory=None,
        real_paper_execution_enabled=True,
        confirmation=PAPER_ORDER_CONFIRMATION,
    )

    assert result.execution_status == "BLOCKED"
    assert result.blocked_reasons == ["paper client factory is required"]


def test_real_paper_executor_rejects_blocked_execution_gate():
    client = RecordingPaperClient()
    intent = blocked_intent()

    result = execute_real_alpaca_paper_order(
        config=valid_config(),
        intent=intent,
        execution_gate=blocked_gate(intent),
        paper_client_factory=lambda: client,
        real_paper_execution_enabled=True,
        confirmation=PAPER_ORDER_CONFIRMATION,
    )

    assert result.execution_status == "BLOCKED"
    assert result.execution_attempted is False
    assert "execution gate is not allowed" in result.blocked_reasons
    assert "market_hours: market is closed" in result.blocked_reasons
    assert client.submit_order_calls == []


def test_real_paper_executor_hold_is_no_action():
    client = RecordingPaperClient()
    intent = hold_intent()

    result = execute_real_alpaca_paper_order(
        config=valid_config(),
        intent=intent,
        execution_gate=allowed_gate(intent),
        paper_client_factory=lambda: client,
        real_paper_execution_enabled=True,
        confirmation=PAPER_ORDER_CONFIRMATION,
    )

    assert result.execution_status == "NO_ACTION"
    assert result.execution_attempted is False
    assert result.paper_client_used is False
    assert result.real_broker_client_used is False
    assert client.submit_order_calls == []


def test_real_paper_executor_submits_buy_to_injected_paper_client_only_when_enabled_and_confirmed():
    client = RecordingPaperClient()
    intent = buy_intent()

    result = execute_real_alpaca_paper_order(
        config=valid_config(),
        intent=intent,
        execution_gate=allowed_gate(intent),
        paper_client_factory=lambda: client,
        real_paper_execution_enabled=True,
        confirmation=PAPER_ORDER_CONFIRMATION,
    )

    assert result.execution_status == "PAPER_SUBMITTED"
    assert result.execution_attempted is True
    assert result.submitted_side == "buy"
    assert result.submitted_quantity == 10
    assert result.submitted_order_type == "market"
    assert result.submitted_time_in_force == "day"
    assert result.paper_order_id == "paper_order_123"
    assert result.paper_client_used is True
    assert result.real_broker_client_used is True
    assert result.live_trading_enabled is False
    assert result.order_submission_to_real_broker_enabled is True
    assert client.submit_order_calls == [
        {
            "symbol": "EEM",
            "qty": 10,
            "side": "buy",
            "type": "market",
            "time_in_force": "day",
        }
    ]


def test_real_paper_executor_rejects_live_endpoint():
    client = RecordingPaperClient()

    try:
        execute_real_alpaca_paper_order(
            config=live_config(),
            intent=buy_intent(),
            execution_gate=allowed_gate(),
            paper_client_factory=lambda: client,
            real_paper_execution_enabled=True,
            confirmation=PAPER_ORDER_CONFIRMATION,
        )
    except ValueError as exc:
        message = str(exc).lower()
        assert "live alpaca endpoint" in message or "paper" in message
    else:
        raise AssertionError("Expected live endpoint validation to fail.")

    assert client.submit_order_calls == []
