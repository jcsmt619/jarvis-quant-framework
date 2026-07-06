from pathlib import Path

from paper_trading.alpaca_config import AlpacaPaperConfig
from paper_trading.execution_gate import PaperExecutionGateResult
from paper_trading.fake_executor import FakePaperExecutionResult
from paper_trading.order_intent import PaperOrderIntent
from paper_trading.preflight import PaperPreflightReport
from scripts import run_fake_paper_execution_pipeline as script


def valid_config():
    return AlpacaPaperConfig(
        api_key="paper_key",
        secret_key="paper_secret",
        base_url="https://paper-api.alpaca.markets",
        paper_only=True,
        confirm_live=False,
    )


def make_preflight(**overrides):
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


def make_intent(**overrides):
    values = {
        "timestamp_utc": "2026-07-05T00:00:00+00:00",
        "symbol": "EEM",
        "strategy": "rsi_revert",
        "requested_signal": "HOLD",
        "intent_action": "HOLD",
        "estimated_quantity": 0,
        "estimated_notional": 0.0,
        "latest_price": 66.0,
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


def make_fake_result(**overrides):
    values = {
        "timestamp_utc": "2026-07-05T00:00:00+00:00",
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


def patch_common(monkeypatch, fake_result=None, intent=None):
    monkeypatch.setattr(script, "load_env_file", lambda env_file: None)
    monkeypatch.setattr(script, "load_alpaca_paper_config", valid_config)
    monkeypatch.setattr(script, "build_paper_preflight_report", lambda **kwargs: make_preflight())
    monkeypatch.setattr(script, "write_paper_preflight_report", lambda report: Path("preflight.json"))
    monkeypatch.setattr(script, "build_paper_order_intent", lambda **kwargs: intent or make_intent())
    monkeypatch.setattr(script, "write_paper_order_intent", lambda intent: Path("intent.json"))
    monkeypatch.setattr(script, "evaluate_paper_execution_gate", lambda **kwargs: make_gate())
    monkeypatch.setattr(script, "write_paper_execution_gate_result", lambda result: Path("gate.json"))
    monkeypatch.setattr(script, "execute_with_fake_paper_client", lambda **kwargs: fake_result or make_fake_result())
    monkeypatch.setattr(script, "write_fake_paper_execution_result", lambda result: Path("fake.json"))


def test_fake_pipeline_hold_no_action_success(tmp_path, capsys, monkeypatch):
    csv_path = tmp_path / "eem.csv"
    csv_path.write_text("Date,Close\n2026-07-01,65\n2026-07-02,66\n", encoding="utf-8")
    patch_common(monkeypatch)

    code = script.run_fake_execution_pipeline(env_file=Path(".env"), close_csv=csv_path)
    output = capsys.readouterr().out

    assert code == 0
    assert "FAKE PAPER EXECUTION PIPELINE: PASS" in output
    assert "Fake execution status: NO_ACTION" in output
    assert "FAKE CLIENT USED: true" in output
    assert "REAL BROKER CLIENT USED: false" in output
    assert "REAL PAPER ORDER SUBMITTED: false" in output


def test_fake_pipeline_buy_fake_submitted_success(tmp_path, capsys, monkeypatch):
    csv_path = tmp_path / "eem.csv"
    csv_path.write_text("Date,Close\n2026-07-01,50\n2026-07-02,50\n", encoding="utf-8")

    intent = make_intent(
        requested_signal="BUY",
        intent_action="BUY",
        estimated_quantity=200,
        estimated_notional=10_000.0,
    )
    fake_result = make_fake_result(
        requested_signal="BUY",
        intent_action="BUY",
        execution_attempted=True,
        execution_status="FAKE_SUBMITTED",
        submitted_side="buy",
        submitted_quantity=200,
        submitted_order_type="market",
        submitted_time_in_force="day",
        fake_order_id="fake_order_123",
    )
    patch_common(monkeypatch, fake_result=fake_result, intent=intent)

    code = script.run_fake_execution_pipeline(env_file=Path(".env"), close_csv=csv_path)
    output = capsys.readouterr().out

    assert code == 0
    assert "Fake execution status: FAKE_SUBMITTED" in output
    assert "Fake submitted side: buy" in output
    assert "Fake submitted quantity: 200" in output
    assert "Fake order id: fake_order_123" in output


def test_fake_pipeline_blocked_returns_one(tmp_path, capsys, monkeypatch):
    csv_path = tmp_path / "eem.csv"
    csv_path.write_text("Date,Close\n2026-07-01,50\n2026-07-02,50\n", encoding="utf-8")

    fake_result = make_fake_result(
        execution_status="BLOCKED",
        blocked_reasons=["fake execution is disabled"],
    )
    patch_common(monkeypatch, fake_result=fake_result)

    code = script.run_fake_execution_pipeline(
        env_file=Path(".env"),
        close_csv=csv_path,
        fake_execution_enabled=False,
    )
    output = capsys.readouterr().out

    assert code == 1
    assert "Fake execution status: BLOCKED" in output
    assert "fake execution is disabled" in output


def test_fake_pipeline_bad_csv_returns_one(tmp_path, capsys):
    csv_path = tmp_path / "bad.csv"
    csv_path.write_text("Date,Wrong\n2026-07-01,50\n", encoding="utf-8")

    code = script.run_fake_execution_pipeline(env_file=None, close_csv=csv_path)
    output = capsys.readouterr().out

    assert code == 1
    assert "FAKE PAPER EXECUTION PIPELINE: FAIL" in output


def test_fake_pipeline_execution_gate_enabled_for_fake_only(tmp_path, monkeypatch):
    csv_path = tmp_path / "eem.csv"
    csv_path.write_text("Date,Close\n2026-07-01,50\n2026-07-02,50\n", encoding="utf-8")
    captured = {}

    def fake_gate(**kwargs):
        captured["order_submission_enabled"] = kwargs["order_submission_enabled"]
        return make_gate()

    patch_common(monkeypatch)
    monkeypatch.setattr(script, "evaluate_paper_execution_gate", fake_gate)

    code = script.run_fake_execution_pipeline(env_file=Path(".env"), close_csv=csv_path)

    assert code == 0
    assert captured["order_submission_enabled"] is True
