from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from paper_trading.order_intent import PaperOrderIntent
from paper_trading.paper_executor import PAPER_ORDER_CONFIRMATION, RealPaperExecutionResult
from scripts import run_real_paper_executor_report as script


def make_csv(tmp_path):
    csv_path = tmp_path / "eem.csv"
    pd.DataFrame(
        {
            "Date": ["2026-07-01T04:00:00Z", "2026-07-02T04:00:00Z"],
            "Close": [66.0, 65.71],
        }
    ).to_csv(csv_path, index=False)
    return csv_path


def make_preflight(ready=True, signal="BUY"):
    return SimpleNamespace(
        symbol="EEM",
        strategy="rsi_revert",
        dry_run_signal=signal,
        blocked_reasons=[] if ready else ["market_hours: market is closed"],
        ready_for_paper_order_phase=ready,
        cash="100000",
        portfolio_value="100000",
    )


def make_intent(action="BUY"):
    return PaperOrderIntent(
        timestamp_utc="2026-07-06T00:00:00+00:00",
        symbol="EEM",
        strategy="rsi_revert",
        requested_signal=action,
        intent_action=action,
        estimated_quantity=10 if action == "BUY" else 0,
        estimated_notional=657.10 if action == "BUY" else 0.0,
        latest_price=65.71,
        preflight_ready=True,
        blocked_reasons=[],
        reason=f"{action} test intent",
    )


def make_gate(allowed=True):
    return SimpleNamespace(
        execution_allowed=allowed,
        execution_status="ALLOWED" if allowed else "BLOCKED",
        blocked_reasons=[] if allowed else ["market_hours: market is closed"],
    )


def make_result(status="BLOCKED", attempted=False, paper_client_used=False):
    return RealPaperExecutionResult(
        timestamp_utc="2026-07-06T00:00:00+00:00",
        symbol="EEM",
        strategy="rsi_revert",
        intent_action="BUY",
        requested_signal="BUY",
        execution_attempted=attempted,
        execution_status=status,
        submitted_side="buy" if attempted else None,
        submitted_quantity=10 if attempted else 0,
        submitted_order_type="market" if attempted else None,
        submitted_time_in_force="day" if attempted else None,
        paper_order_id="paper_order_123" if attempted else None,
        blocked_reasons=[] if attempted else ["real Alpaca paper execution is disabled"],
        paper_client_used=paper_client_used,
        real_broker_client_used=paper_client_used,
        live_trading_enabled=False,
        order_submission_to_real_broker_enabled=paper_client_used,
    )


def patch_common(monkeypatch, captured, result):
    monkeypatch.setattr(script, "load_env_file", lambda env_file: None)
    monkeypatch.setattr(script, "load_alpaca_paper_config", lambda: object())
    monkeypatch.setattr(
        script,
        "get_us_equity_market_session_status",
        lambda: SimpleNamespace(is_market_open=True, reason="US equity market is open"),
    )
    monkeypatch.setattr(script, "build_paper_preflight_report", lambda **kwargs: make_preflight())
    monkeypatch.setattr(script, "write_paper_preflight_report", lambda report: Path("preflight.json"))
    monkeypatch.setattr(script, "build_paper_order_intent", lambda **kwargs: make_intent("BUY"))
    monkeypatch.setattr(script, "write_paper_order_intent", lambda intent: Path("intent.json"))
    monkeypatch.setattr(script, "evaluate_paper_execution_gate", lambda **kwargs: make_gate(True))
    monkeypatch.setattr(script, "write_paper_execution_gate_result", lambda result: Path("gate.json"))

    def fake_execute(**kwargs):
        captured.update(kwargs)
        return result

    monkeypatch.setattr(script, "execute_real_alpaca_paper_order", fake_execute)
    monkeypatch.setattr(script, "write_real_paper_execution_result", lambda result: Path("real_paper.json"))


def test_real_paper_report_disabled_by_default(capsys, tmp_path, monkeypatch):
    captured = {}
    patch_common(monkeypatch, captured, make_result())

    code = script.run_real_paper_executor_report(
        env_file=Path(".env"),
        close_csv=make_csv(tmp_path),
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "ARMED REAL PAPER EXECUTOR REPORT: PASS" in output
    assert "REAL PAPER EXECUTION ENABLED: false" in output
    assert "REAL PAPER ORDER SUBMITTED: false" in output
    assert "LIVE TRADING: DISABLED" in output
    assert captured["real_paper_execution_enabled"] is False
    assert captured["confirmation"] is None
    assert captured["paper_client_factory"] is None


def test_real_paper_report_enabled_without_confirmation_keeps_client_factory_none(capsys, tmp_path, monkeypatch):
    captured = {}
    patch_common(monkeypatch, captured, make_result())

    code = script.run_real_paper_executor_report(
        env_file=Path(".env"),
        close_csv=make_csv(tmp_path),
        enable_real_paper_execution=True,
        confirmation=None,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "REAL PAPER EXECUTION ENABLED: true" in output
    assert "CONFIRMATION ACCEPTED: false" in output
    assert "REAL PAPER ORDER SUBMITTED: false" in output
    assert captured["real_paper_execution_enabled"] is True
    assert captured["confirmation"] is None
    assert captured["paper_client_factory"] is None


def test_real_paper_report_enabled_with_confirmation_provides_client_factory(capsys, tmp_path, monkeypatch):
    captured = {}
    patch_common(monkeypatch, captured, make_result(status="PAPER_SUBMITTED", attempted=True, paper_client_used=True))
    monkeypatch.setattr(script, "create_alpaca_paper_client", lambda config: "paper_client")

    code = script.run_real_paper_executor_report(
        env_file=Path(".env"),
        close_csv=make_csv(tmp_path),
        enable_real_paper_execution=True,
        confirmation=PAPER_ORDER_CONFIRMATION,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "Execution status: PAPER_SUBMITTED" in output
    assert "REAL PAPER ORDER SUBMITTED: true" in output
    assert "CONFIRMATION ACCEPTED: true" in output
    assert captured["real_paper_execution_enabled"] is True
    assert captured["confirmation"] == PAPER_ORDER_CONFIRMATION
    assert captured["paper_client_factory"]() == "paper_client"


def test_real_paper_report_missing_price_column_returns_one(capsys, tmp_path, monkeypatch):
    csv_path = tmp_path / "bad.csv"
    pd.DataFrame({"Date": ["2026-07-02"], "AdjClose": [65.71]}).to_csv(csv_path, index=False)

    monkeypatch.setattr(script, "load_alpaca_paper_config", lambda: object())

    code = script.run_real_paper_executor_report(
        env_file=None,
        close_csv=csv_path,
        price_column="Close",
    )
    output = capsys.readouterr().out

    assert code == 1
    assert "ARMED REAL PAPER EXECUTOR REPORT: FAIL" in output
    assert "price column" in output


def test_real_paper_report_applies_external_blocked_reasons(capsys, tmp_path, monkeypatch):
    captured = {}
    patch_common(monkeypatch, captured, make_result())

    def fake_execute(**kwargs):
        captured.update(kwargs)
        intent = kwargs["intent"]
        return RealPaperExecutionResult(
            timestamp_utc="2026-07-06T00:00:00+00:00",
            symbol=intent.symbol,
            strategy=intent.strategy,
            intent_action=intent.intent_action,
            requested_signal=intent.requested_signal,
            execution_attempted=False,
            execution_status="BLOCKED",
            submitted_side=None,
            submitted_quantity=0,
            submitted_order_type=None,
            submitted_time_in_force=None,
            paper_order_id=None,
            blocked_reasons=list(intent.blocked_reasons),
            paper_client_used=False,
            real_broker_client_used=False,
            live_trading_enabled=False,
            order_submission_to_real_broker_enabled=False,
        )

    monkeypatch.setattr(script, "execute_real_alpaca_paper_order", fake_execute)

    code = script.run_real_paper_executor_report(
        env_file=Path(".env"),
        close_csv=make_csv(tmp_path),
        external_blocked_reasons=["open EEM paper orders exist: 1"],
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "Intent action: BLOCKED" in output
    assert "open EEM paper orders exist: 1" in output
    assert captured["intent"].intent_action == "BLOCKED"
    assert "open EEM paper orders exist: 1" in captured["intent"].blocked_reasons
