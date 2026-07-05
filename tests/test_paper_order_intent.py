from paper_trading import order_intent
from paper_trading.order_intent import (
    build_paper_order_intent,
    write_paper_order_intent,
)
from paper_trading.preflight import PaperPreflightReport


def make_report(**overrides):
    values = {
        "timestamp_utc": "2026-07-05T00:00:00+00:00",
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


def test_hold_signal_creates_hold_intent():
    intent = build_paper_order_intent(
        preflight_report=make_report(dry_run_signal="HOLD"),
        latest_price=65.0,
    )

    assert intent.intent_action == "HOLD"
    assert intent.estimated_quantity == 0
    assert intent.estimated_notional == 0.0
    assert intent.order_submission_enabled is False
    assert intent.live_trading_enabled is False
    assert intent.broker_call_performed is False


def test_buy_signal_creates_sized_buy_intent():
    intent = build_paper_order_intent(
        preflight_report=make_report(
            dry_run_signal="BUY",
            dry_run_final_decision="BUY: RSI below 30",
        ),
        latest_price=50.0,
        max_position_notional=10_000,
        max_equity_fraction=0.10,
    )

    assert intent.intent_action == "BUY"
    assert intent.estimated_quantity == 200
    assert intent.estimated_notional == 10_000.0
    assert intent.blocked_reasons == []
    assert intent.order_submission_enabled is False
    assert intent.broker_call_performed is False


def test_buy_signal_respects_equity_fraction_cap():
    intent = build_paper_order_intent(
        preflight_report=make_report(
            dry_run_signal="BUY",
            portfolio_value="50000",
            dry_run_final_decision="BUY: RSI below 30",
        ),
        latest_price=50.0,
        max_position_notional=10_000,
        max_equity_fraction=0.10,
    )

    assert intent.intent_action == "BUY"
    assert intent.estimated_quantity == 100
    assert intent.estimated_notional == 5_000.0


def test_buy_signal_blocks_when_quantity_zero():
    intent = build_paper_order_intent(
        preflight_report=make_report(
            dry_run_signal="BUY",
            cash="10",
            portfolio_value="10",
        ),
        latest_price=50.0,
    )

    assert intent.intent_action == "BLOCKED"
    assert intent.estimated_quantity == 0
    assert "zero" in " ".join(intent.blocked_reasons)


def test_exit_signal_with_position_creates_exit_intent():
    intent = build_paper_order_intent(
        preflight_report=make_report(
            dry_run_signal="EXIT",
            dry_run_final_decision="EXIT: RSI above 70",
        ),
        latest_price=60.0,
        current_position_quantity=25,
    )

    assert intent.intent_action == "EXIT"
    assert intent.estimated_quantity == 25
    assert intent.estimated_notional == 1_500.0


def test_exit_signal_without_position_holds():
    intent = build_paper_order_intent(
        preflight_report=make_report(dry_run_signal="EXIT"),
        latest_price=60.0,
        current_position_quantity=0,
    )

    assert intent.intent_action == "HOLD"
    assert intent.estimated_quantity == 0


def test_blocked_preflight_creates_blocked_intent():
    intent = build_paper_order_intent(
        preflight_report=make_report(
            ready_for_paper_order_phase=False,
            blocked_reasons=["paper account blocked"],
        ),
        latest_price=60.0,
    )

    assert intent.intent_action == "BLOCKED"
    assert "paper account blocked" in intent.blocked_reasons


def test_missing_latest_price_blocks_intent():
    intent = build_paper_order_intent(
        preflight_report=make_report(dry_run_signal="BUY"),
        latest_price=None,
    )

    assert intent.intent_action == "BLOCKED"
    assert "latest price is required" in intent.blocked_reasons


def test_write_intent_creates_json_without_secrets(tmp_path):
    intent = build_paper_order_intent(
        preflight_report=make_report(dry_run_signal="BUY"),
        latest_price=50.0,
    )

    path = write_paper_order_intent(intent, output_dir=tmp_path)
    text = path.read_text(encoding="utf-8")

    assert path.exists()
    assert '"intent_action": "BUY"' in text
    assert "paper_key" not in text
    assert "paper_secret" not in text


def test_no_broker_execution_function_exists():
    forbidden_names = {
        "submit_order",
        "place_order",
        "create_order",
        "send_order",
        "buy",
        "sell",
        "liquidate",
        "cancel_order",
    }

    module_names = set(dir(order_intent))

    assert forbidden_names.isdisjoint(module_names)
