from pathlib import Path

from paper_trading.alpaca_config import AlpacaPaperConfig
from paper_trading.execution_gate import PaperExecutionGateResult
from paper_trading.order_intent import PaperOrderIntent
from paper_trading.preflight import PaperPreflightReport
from scripts import run_paper_pipeline_report as script


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
        "execution_allowed": False,
        "execution_status": "BLOCKED",
        "blocked_reasons": ["order submission is disabled"],
        "order_submission_enabled": False,
        "live_trading_enabled": False,
        "broker_call_performed": False,
        "order_submitted": False,
        "order_id": None,
    }
    values.update(overrides)
    return PaperExecutionGateResult(**values)


def test_write_pipeline_summary_creates_json_without_secrets(tmp_path):
    path = script.write_pipeline_summary(
        preflight_report=make_preflight(),
        intent=make_intent(),
        execution_gate=make_gate(),
        output_dir=tmp_path,
    )

    text = path.read_text(encoding="utf-8")

    assert path.exists()
    assert '"symbol": "EEM"' in text
    assert '"order_submitted": false' in text
    assert '"live_trading_enabled": false' in text
    assert "paper_key" not in text
    assert "paper_secret" not in text


def test_run_pipeline_report_hold_success(tmp_path, capsys, monkeypatch):
    csv_path = tmp_path / "eem.csv"
    csv_path.write_text(
        "Date,Close\n2026-07-01,65\n2026-07-02,66\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(script, "load_env_file", lambda env_file: None)
    monkeypatch.setattr(script, "load_alpaca_paper_config", valid_config)
    monkeypatch.setattr(
        script,
        "build_paper_preflight_report",
        lambda **kwargs: make_preflight(dry_run_signal="HOLD"),
    )
    monkeypatch.setattr(
        script,
        "write_paper_preflight_report",
        lambda report: Path("reports/paper_trading/mock_preflight.json"),
    )
    monkeypatch.setattr(
        script,
        "write_paper_order_intent",
        lambda intent: Path("reports/paper_trading/mock_intent.json"),
    )
    monkeypatch.setattr(
        script,
        "evaluate_paper_execution_gate",
        lambda **kwargs: make_gate(),
    )
    monkeypatch.setattr(
        script,
        "write_paper_execution_gate_result",
        lambda result: Path("reports/paper_trading/mock_gate.json"),
    )
    monkeypatch.setattr(
        script,
        "write_pipeline_summary",
        lambda **kwargs: Path("reports/paper_trading/mock_pipeline.json"),
    )

    code = script.run_pipeline_report(
        env_file=Path(".env"),
        close_csv=csv_path,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "PAPER PIPELINE REPORT: PASS" in output
    assert "Intent action: HOLD" in output
    assert "Execution gate status: BLOCKED" in output
    assert "BROKER CALL PERFORMED: false" in output
    assert "ORDER SUBMISSION: DISABLED" in output
    assert "LIVE TRADING: DISABLED" in output
    assert "ORDER SUBMITTED: false" in output


def test_run_pipeline_report_bad_csv_returns_one(tmp_path, capsys):
    csv_path = tmp_path / "bad.csv"
    csv_path.write_text("Date,Wrong\n2026-07-01,50\n", encoding="utf-8")

    code = script.run_pipeline_report(
        env_file=None,
        close_csv=csv_path,
    )
    output = capsys.readouterr().out

    assert code == 1
    assert "PAPER PIPELINE REPORT: FAIL" in output


def test_pipeline_always_calls_execution_gate_with_submission_disabled(tmp_path, monkeypatch):
    csv_path = tmp_path / "eem.csv"
    csv_path.write_text(
        "Date,Close\n2026-07-01,65\n2026-07-02,66\n",
        encoding="utf-8",
    )

    captured = {}

    def fake_gate(**kwargs):
        captured["order_submission_enabled"] = kwargs["order_submission_enabled"]
        return make_gate()

    monkeypatch.setattr(script, "load_env_file", lambda env_file: None)
    monkeypatch.setattr(script, "load_alpaca_paper_config", valid_config)
    monkeypatch.setattr(script, "build_paper_preflight_report", lambda **kwargs: make_preflight())
    monkeypatch.setattr(script, "write_paper_preflight_report", lambda report: Path("preflight.json"))
    monkeypatch.setattr(script, "write_paper_order_intent", lambda intent: Path("intent.json"))
    monkeypatch.setattr(script, "evaluate_paper_execution_gate", fake_gate)
    monkeypatch.setattr(script, "write_paper_execution_gate_result", lambda result: Path("gate.json"))
    monkeypatch.setattr(script, "write_pipeline_summary", lambda **kwargs: Path("pipeline.json"))

    code = script.run_pipeline_report(
        env_file=Path(".env"),
        close_csv=csv_path,
    )

    assert code == 0
    assert captured["order_submission_enabled"] is False
