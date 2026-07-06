from paper_trading.execution_gate import PaperExecutionGateResult
from paper_trading.fake_executor import FakePaperExecutionResult
from paper_trading.market_session import MarketSessionStatus
from paper_trading.order_intent import PaperOrderIntent
from paper_trading.pipeline_decision import (
    classify_fake_pipeline_decision,
    write_fake_pipeline_decision,
)
from paper_trading.preflight import PaperPreflightReport


def make_market(open_status=True, reason="US equity market is within regular cash-session hours"):
    return MarketSessionStatus(
        timestamp_utc="2026-07-06T14:00:00+00:00",
        timestamp_eastern="2026-07-06T10:00:00-04:00",
        is_weekday=True,
        is_regular_hours=open_status,
        is_market_open=open_status,
        reason=reason,
    )


def make_preflight(**overrides):
    values = {
        "timestamp_utc": "2026-07-06T14:00:00+00:00",
        "symbol": "EEM",
        "strategy": "rsi_revert",
        "account_status": "ACTIVE",
        "cash": "100000",
        "buying_power": "400000",
        "portfolio_value": "100000",
        "positions_count": 0,
        "open_orders_count": 0,
        "dry_run_signal": "HOLD",
        "dry_run_reason": "RSI neutral",
        "dry_run_final_decision": "HOLD: RSI neutral",
        "dry_run_order_submitted": False,
        "risk_gate_passed": True,
        "risk_gate_checks": {},
        "ready_for_paper_order_phase": True,
        "blocked_reasons": [],
        "order_submission_enabled": False,
        "live_trading_enabled": False,
    }
    values.update(overrides)
    return PaperPreflightReport(**values)


def make_intent(**overrides):
    values = {
        "timestamp_utc": "2026-07-06T14:00:00+00:00",
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
        "timestamp_utc": "2026-07-06T14:00:00+00:00",
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


def make_fake(**overrides):
    values = {
        "timestamp_utc": "2026-07-06T14:00:00+00:00",
        "symbol": "EEM",
        "strategy": "rsi_revert",
        "intent_action": "HOLD",
        "requested_signal": "HOLD",
        "execution_attempted": False,
        "execution_status": "NO_ACTION",
        "submitted_side": None,
        "submitted_quantity": 0,
        "submitted_order_type": None,
        "submitted_time_in_force": None,
        "fake_order_id": None,
        "blocked_reasons": [],
        "fake_client_used": True,
        "real_broker_client_used": False,
        "live_trading_enabled": False,
        "order_submission_to_real_broker_enabled": False,
    }
    values.update(overrides)
    return FakePaperExecutionResult(**values)


def test_closed_market_classifies_as_wait():
    decision = classify_fake_pipeline_decision(
        market_session=make_market(
            open_status=False,
            reason="US equity market is outside regular cash-session hours",
        ),
        preflight_report=make_preflight(ready_for_paper_order_phase=False),
        intent=make_intent(intent_action="BLOCKED"),
        execution_gate=make_gate(execution_allowed=False, execution_status="BLOCKED"),
        fake_result=make_fake(execution_status="BLOCKED"),
    )

    assert decision.decision_status == "WAIT_MARKET_CLOSED"
    assert decision.actionable is False
    assert decision.market_session_open is False
    assert "outside regular" in decision.reason


def test_open_market_hold_classifies_as_no_action():
    decision = classify_fake_pipeline_decision(
        market_session=make_market(open_status=True),
        preflight_report=make_preflight(dry_run_signal="HOLD"),
        intent=make_intent(intent_action="HOLD"),
        execution_gate=make_gate(execution_status="ALLOWED", execution_allowed=True),
        fake_result=make_fake(execution_status="NO_ACTION"),
    )

    assert decision.decision_status == "NO_ACTION"
    assert decision.actionable is False


def test_open_market_fake_submitted_classifies_as_fake_executed():
    decision = classify_fake_pipeline_decision(
        market_session=make_market(open_status=True),
        preflight_report=make_preflight(dry_run_signal="BUY"),
        intent=make_intent(intent_action="BUY", requested_signal="BUY"),
        execution_gate=make_gate(execution_status="ALLOWED", execution_allowed=True),
        fake_result=make_fake(
            execution_status="FAKE_SUBMITTED",
            execution_attempted=True,
            intent_action="BUY",
            requested_signal="BUY",
            submitted_side="buy",
            submitted_quantity=100,
            fake_order_id="fake_order_123",
        ),
    )

    assert decision.decision_status == "FAKE_EXECUTED"
    assert decision.actionable is True
    assert decision.real_broker_client_used is False
    assert decision.real_paper_order_submitted is False


def test_open_market_preflight_block_classifies_as_blocked_preflight():
    decision = classify_fake_pipeline_decision(
        market_session=make_market(open_status=True),
        preflight_report=make_preflight(
            ready_for_paper_order_phase=False,
            blocked_reasons=["stale data"],
        ),
        intent=make_intent(intent_action="BLOCKED"),
        execution_gate=make_gate(execution_status="BLOCKED", execution_allowed=False),
        fake_result=make_fake(execution_status="BLOCKED"),
    )

    assert decision.decision_status == "BLOCKED_PREFLIGHT"
    assert "stale data" in decision.reason


def test_write_pipeline_decision_creates_json_without_secrets(tmp_path):
    decision = classify_fake_pipeline_decision(
        market_session=make_market(open_status=False),
        preflight_report=make_preflight(),
        intent=make_intent(),
        execution_gate=make_gate(),
        fake_result=make_fake(),
    )

    path = write_fake_pipeline_decision(decision, output_dir=tmp_path)
    text = path.read_text(encoding="utf-8")

    assert path.exists()
    assert '"decision_status": "WAIT_MARKET_CLOSED"' in text
    assert '"real_paper_order_submitted": false' in text
    assert "paper_key" not in text
    assert "paper_secret" not in text
