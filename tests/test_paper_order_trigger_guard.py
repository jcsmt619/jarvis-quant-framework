from types import SimpleNamespace

from paper_trading.alpaca_account_state import AlpacaPaperSymbolState
from paper_trading.paper_executor import PAPER_ORDER_CONFIRMATION
from paper_trading.paper_order_trigger_guard import evaluate_paper_order_trigger_guard


def make_account_state(
    *,
    account_status="ACTIVE",
    open_order_count=0,
):
    return AlpacaPaperSymbolState(
        timestamp_utc="2026-07-06T00:00:00+00:00",
        symbol="EEM",
        account_status=account_status,
        cash="100000",
        portfolio_value="100000",
        buying_power="400000",
        position_quantity=0.0,
        position_open=False,
        open_symbol_orders_count=open_order_count,
        open_symbol_order_ids=[f"order_{i}" for i in range(open_order_count)],
        read_only=True,
        order_submission_enabled=False,
        broker_order_call_performed=False,
        live_trading_enabled=False,
    )


def make_market_session(is_open=True):
    return SimpleNamespace(is_open=is_open)


def make_intent(action="BUY"):
    return SimpleNamespace(
        symbol="EEM",
        strategy="rsi_revert",
        intent_action=action,
        requested_signal=action,
    )


def make_execution_gate(status="ALLOWED"):
    return SimpleNamespace(execution_status=status)


def test_trigger_guard_allows_only_when_every_condition_is_true():
    result = evaluate_paper_order_trigger_guard(
        account_state=make_account_state(),
        market_session=make_market_session(is_open=True),
        intent=make_intent("BUY"),
        execution_gate=make_execution_gate("ALLOWED"),
        real_paper_execution_enabled=True,
        confirmation=PAPER_ORDER_CONFIRMATION,
        live_trading_enabled=False,
        paper_only=True,
    )

    assert result.allowed_to_attempt_order is True
    assert result.blocked_reasons == []
    assert result.intent_action == "BUY"
    assert result.execution_gate_status == "ALLOWED"
    assert result.market_session_open is True
    assert result.confirmation_accepted is True
    assert result.real_paper_execution_enabled is True
    assert result.live_trading_enabled is False
    assert result.paper_only is True
    assert result.order_submission_attempted is False
    assert result.real_broker_client_used is False


def test_trigger_guard_blocks_hold_even_when_armed_and_confirmed():
    result = evaluate_paper_order_trigger_guard(
        account_state=make_account_state(),
        market_session=make_market_session(is_open=True),
        intent=make_intent("HOLD"),
        execution_gate=make_execution_gate("NO_ACTION"),
        real_paper_execution_enabled=True,
        confirmation=PAPER_ORDER_CONFIRMATION,
    )

    assert result.allowed_to_attempt_order is False
    assert "intent action is not executable: HOLD" in result.blocked_reasons
    assert "execution gate status is not ALLOWED: NO_ACTION" in result.blocked_reasons


def test_trigger_guard_blocks_when_market_closed():
    result = evaluate_paper_order_trigger_guard(
        account_state=make_account_state(),
        market_session=make_market_session(is_open=False),
        intent=make_intent("BUY"),
        execution_gate=make_execution_gate("ALLOWED"),
        real_paper_execution_enabled=True,
        confirmation=PAPER_ORDER_CONFIRMATION,
    )

    assert result.allowed_to_attempt_order is False
    assert "market session is not open" in result.blocked_reasons


def test_trigger_guard_blocks_when_account_not_active():
    result = evaluate_paper_order_trigger_guard(
        account_state=make_account_state(account_status="ACCOUNT_BLOCKED"),
        market_session=make_market_session(is_open=True),
        intent=make_intent("BUY"),
        execution_gate=make_execution_gate("ALLOWED"),
        real_paper_execution_enabled=True,
        confirmation=PAPER_ORDER_CONFIRMATION,
    )

    assert result.allowed_to_attempt_order is False
    assert "paper account status is not ACTIVE: ACCOUNT_BLOCKED" in result.blocked_reasons


def test_trigger_guard_blocks_when_open_symbol_orders_exist():
    result = evaluate_paper_order_trigger_guard(
        account_state=make_account_state(open_order_count=2),
        market_session=make_market_session(is_open=True),
        intent=make_intent("BUY"),
        execution_gate=make_execution_gate("ALLOWED"),
        real_paper_execution_enabled=True,
        confirmation=PAPER_ORDER_CONFIRMATION,
    )

    assert result.allowed_to_attempt_order is False
    assert "open EEM paper orders exist: 2" in result.blocked_reasons


def test_trigger_guard_blocks_when_execution_gate_not_allowed():
    result = evaluate_paper_order_trigger_guard(
        account_state=make_account_state(),
        market_session=make_market_session(is_open=True),
        intent=make_intent("BUY"),
        execution_gate=make_execution_gate("BLOCKED"),
        real_paper_execution_enabled=True,
        confirmation=PAPER_ORDER_CONFIRMATION,
    )

    assert result.allowed_to_attempt_order is False
    assert "execution gate status is not ALLOWED: BLOCKED" in result.blocked_reasons


def test_trigger_guard_blocks_when_not_armed():
    result = evaluate_paper_order_trigger_guard(
        account_state=make_account_state(),
        market_session=make_market_session(is_open=True),
        intent=make_intent("BUY"),
        execution_gate=make_execution_gate("ALLOWED"),
        real_paper_execution_enabled=False,
        confirmation=PAPER_ORDER_CONFIRMATION,
    )

    assert result.allowed_to_attempt_order is False
    assert "real paper execution is disabled" in result.blocked_reasons


def test_trigger_guard_blocks_when_confirmation_wrong():
    result = evaluate_paper_order_trigger_guard(
        account_state=make_account_state(),
        market_session=make_market_session(is_open=True),
        intent=make_intent("BUY"),
        execution_gate=make_execution_gate("ALLOWED"),
        real_paper_execution_enabled=True,
        confirmation="wrong",
    )

    assert result.allowed_to_attempt_order is False
    assert "real paper confirmation phrase was not accepted" in result.blocked_reasons


def test_trigger_guard_blocks_live_trading_and_non_paper_mode():
    result = evaluate_paper_order_trigger_guard(
        account_state=make_account_state(),
        market_session=make_market_session(is_open=True),
        intent=make_intent("BUY"),
        execution_gate=make_execution_gate("ALLOWED"),
        real_paper_execution_enabled=True,
        confirmation=PAPER_ORDER_CONFIRMATION,
        live_trading_enabled=True,
        paper_only=False,
    )

    assert result.allowed_to_attempt_order is False
    assert "paper_only is false" in result.blocked_reasons
    assert "live trading is enabled" in result.blocked_reasons


def test_trigger_guard_accepts_is_market_open_field_name():
    market_session = SimpleNamespace(is_market_open=True)

    result = evaluate_paper_order_trigger_guard(
        account_state=make_account_state(),
        market_session=market_session,
        intent=make_intent("BUY"),
        execution_gate=make_execution_gate("ALLOWED"),
        real_paper_execution_enabled=True,
        confirmation=PAPER_ORDER_CONFIRMATION,
        live_trading_enabled=False,
        paper_only=True,
    )

    assert result.allowed_to_attempt_order is True
    assert result.market_session_open is True
    assert result.blocked_reasons == []
