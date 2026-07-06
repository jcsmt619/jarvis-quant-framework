import pytest

from paper_trading.alpaca_config import AlpacaConfigError, AlpacaPaperConfig
from paper_trading.execution_gate import PaperExecutionGateResult
from paper_trading.fake_executor import execute_with_fake_paper_client
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


def make_gate(**overrides):
    values = {
        "timestamp_utc": "2026-07-05T00:00:00+00:00",
        "symbol": "EEM",
        "strategy": "rsi_revert",
        "intent_action": "HOLD",
        "requested_signal": "HOLD",
        "estimated_quantity": 0,
        "estimated_notional": 0.0,
        "execution_allowed": True,
        "execution_status": "ALLOWED",
        "blocked_reasons": [],
        "order_submission_enabled": False,
        "live_trading_enabled": False,
        "broker_call_performed": False,
        "order_submitted": False,
        "order_id": None,
    }
    values.update(overrides)
    return PaperExecutionGateResult(**values)


class FakeOrder:
    def __init__(self, order_id="fake_order_123"):
        self.id = order_id


class FakeClient:
    def __init__(self):
        self.submitted_orders = []

    def submit_order(self, **kwargs):
        self.submitted_orders.append(kwargs)
        return FakeOrder()


def test_fake_buy_executes_against_fake_client_only():
    fake_client = FakeClient()

    result = execute_with_fake_paper_client(
        config=valid_config(),
        intent=make_intent(
            requested_signal="BUY",
            intent_action="BUY",
            estimated_quantity=100,
            estimated_notional=6500.0,
        ),
        execution_gate=make_gate(
            intent_action="BUY",
            requested_signal="BUY",
            estimated_quantity=100,
            estimated_notional=6500.0,
        ),
        fake_client_factory=lambda: fake_client,
        fake_execution_enabled=True,
    )

    assert result.execution_status == "FAKE_SUBMITTED"
    assert result.execution_attempted is True
    assert result.submitted_side == "buy"
    assert result.submitted_quantity == 100
    assert result.submitted_order_type == "market"
    assert result.submitted_time_in_force == "day"
    assert result.fake_order_id == "fake_order_123"
    assert result.real_broker_client_used is False
    assert result.live_trading_enabled is False
    assert result.order_submission_to_real_broker_enabled is False
    assert fake_client.submitted_orders == [
        {
            "symbol": "EEM",
            "qty": 100,
            "side": "buy",
            "type": "market",
            "time_in_force": "day",
        }
    ]


def test_fake_exit_executes_sell_against_fake_client_only():
    fake_client = FakeClient()

    result = execute_with_fake_paper_client(
        config=valid_config(),
        intent=make_intent(
            requested_signal="EXIT",
            intent_action="EXIT",
            estimated_quantity=25,
            estimated_notional=1625.0,
        ),
        execution_gate=make_gate(
            intent_action="EXIT",
            requested_signal="EXIT",
            estimated_quantity=25,
            estimated_notional=1625.0,
        ),
        fake_client_factory=lambda: fake_client,
        fake_execution_enabled=True,
    )

    assert result.execution_status == "FAKE_SUBMITTED"
    assert result.submitted_side == "sell"
    assert result.submitted_quantity == 25
    assert fake_client.submitted_orders[0]["side"] == "sell"


def test_hold_does_not_submit_even_when_fake_execution_enabled():
    fake_client = FakeClient()

    result = execute_with_fake_paper_client(
        config=valid_config(),
        intent=make_intent(intent_action="HOLD", requested_signal="HOLD"),
        execution_gate=make_gate(intent_action="HOLD", requested_signal="HOLD"),
        fake_client_factory=lambda: fake_client,
        fake_execution_enabled=True,
    )

    assert result.execution_status == "NO_ACTION"
    assert result.execution_attempted is False
    assert fake_client.submitted_orders == []


def test_fake_execution_disabled_blocks_before_client_created():
    called = False

    def factory():
        nonlocal called
        called = True
        return FakeClient()

    result = execute_with_fake_paper_client(
        config=valid_config(),
        intent=make_intent(
            requested_signal="BUY",
            intent_action="BUY",
            estimated_quantity=100,
            estimated_notional=6500.0,
        ),
        execution_gate=make_gate(),
        fake_client_factory=factory,
        fake_execution_enabled=False,
    )

    assert result.execution_status == "BLOCKED"
    assert "fake execution is disabled" in result.blocked_reasons
    assert called is False


def test_missing_fake_client_factory_blocks():
    result = execute_with_fake_paper_client(
        config=valid_config(),
        intent=make_intent(
            requested_signal="BUY",
            intent_action="BUY",
            estimated_quantity=100,
            estimated_notional=6500.0,
        ),
        execution_gate=make_gate(),
        fake_client_factory=None,
        fake_execution_enabled=True,
    )

    assert result.execution_status == "BLOCKED"
    assert "fake client factory is required" in result.blocked_reasons


def test_blocked_execution_gate_blocks_before_submit():
    fake_client = FakeClient()

    result = execute_with_fake_paper_client(
        config=valid_config(),
        intent=make_intent(
            requested_signal="BUY",
            intent_action="BUY",
            estimated_quantity=100,
            estimated_notional=6500.0,
        ),
        execution_gate=make_gate(
            execution_allowed=False,
            execution_status="BLOCKED",
            blocked_reasons=["order submission is disabled"],
        ),
        fake_client_factory=lambda: fake_client,
        fake_execution_enabled=True,
    )

    assert result.execution_status == "BLOCKED"
    assert "execution gate is not allowed" in result.blocked_reasons
    assert "order submission is disabled" in result.blocked_reasons
    assert fake_client.submitted_orders == []


def test_live_endpoint_rejected():
    with pytest.raises(AlpacaConfigError):
        execute_with_fake_paper_client(
            config=valid_config(base_url="https://api.alpaca.markets"),
            intent=make_intent(),
            execution_gate=make_gate(),
            fake_client_factory=lambda: FakeClient(),
            fake_execution_enabled=True,
        )


def test_intent_claiming_live_trading_blocks():
    fake_client = FakeClient()

    result = execute_with_fake_paper_client(
        config=valid_config(),
        intent=make_intent(live_trading_enabled=True),
        execution_gate=make_gate(),
        fake_client_factory=lambda: fake_client,
        fake_execution_enabled=True,
    )

    assert result.execution_status == "BLOCKED"
    assert "intent live_trading_enabled must be False" in result.blocked_reasons
    assert fake_client.submitted_orders == []


def test_intent_claiming_broker_call_blocks():
    fake_client = FakeClient()

    result = execute_with_fake_paper_client(
        config=valid_config(),
        intent=make_intent(broker_call_performed=True),
        execution_gate=make_gate(),
        fake_client_factory=lambda: fake_client,
        fake_execution_enabled=True,
    )

    assert result.execution_status == "BLOCKED"
    assert "intent already reports broker_call_performed=True" in result.blocked_reasons
    assert fake_client.submitted_orders == []


def test_unsupported_action_blocks():
    fake_client = FakeClient()

    result = execute_with_fake_paper_client(
        config=valid_config(),
        intent=make_intent(intent_action="SHORT", requested_signal="SHORT"),
        execution_gate=make_gate(),
        fake_client_factory=lambda: fake_client,
        fake_execution_enabled=True,
    )

    assert result.execution_status == "BLOCKED"
    assert "unsupported executable intent action: 'SHORT'" in result.blocked_reasons
    assert fake_client.submitted_orders == []


def test_zero_quantity_buy_blocks():
    fake_client = FakeClient()

    result = execute_with_fake_paper_client(
        config=valid_config(),
        intent=make_intent(
            requested_signal="BUY",
            intent_action="BUY",
            estimated_quantity=0,
            estimated_notional=0.0,
        ),
        execution_gate=make_gate(),
        fake_client_factory=lambda: fake_client,
        fake_execution_enabled=True,
    )

    assert result.execution_status == "BLOCKED"
    assert "estimated quantity must be positive" in result.blocked_reasons
    assert fake_client.submitted_orders == []


def test_order_id_can_be_extracted_from_dict_response():
    class DictOrderClient:
        def submit_order(self, **kwargs):
            return {"id": "dict_order_456"}

    result = execute_with_fake_paper_client(
        config=valid_config(),
        intent=make_intent(
            requested_signal="BUY",
            intent_action="BUY",
            estimated_quantity=1,
            estimated_notional=65.0,
        ),
        execution_gate=make_gate(),
        fake_client_factory=lambda: DictOrderClient(),
        fake_execution_enabled=True,
    )

    assert result.fake_order_id == "dict_order_456"
