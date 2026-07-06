from types import SimpleNamespace

from paper_trading.preflight import _build_blocked_reasons, _failed_risk_gate_reasons


def active_snapshot():
    return SimpleNamespace(
        account_status="ACTIVE",
        trading_blocked=False,
        account_blocked=False,
    )


def test_failed_risk_gate_reasons_reports_specific_failed_gates():
    checks = {
        "kill_switch": (True, "kill switch not engaged"),
        "market_hours": (False, "market is closed"),
        "stale_data": (True, "latest bar age 4.1 days; within closed-market daily-bar threshold"),
    }

    reasons = _failed_risk_gate_reasons(checks)

    assert reasons == ["market_hours: market is closed"]


def test_build_blocked_reasons_uses_specific_risk_gate_reason():
    dry_run = SimpleNamespace(
        risk_gate_passed=False,
        risk_gate_checks={
            "market_hours": (False, "market is closed"),
            "stale_data": (True, "latest bar age 4.1 days; within closed-market daily-bar threshold"),
        },
        order_submitted=False,
        final_decision="HOLD: RSI between thresholds",
    )

    reasons = _build_blocked_reasons(
        snapshot=active_snapshot(),
        dry_run=dry_run,
    )

    assert reasons == ["market_hours: market is closed"]
    assert "dry-run risk gates did not pass" not in reasons


def test_build_blocked_reasons_keeps_fail_safe_generic_when_no_specific_gate_exists():
    dry_run = SimpleNamespace(
        risk_gate_passed=False,
        risk_gate_checks={},
        order_submitted=False,
        final_decision="HOLD: RSI between thresholds",
    )

    reasons = _build_blocked_reasons(
        snapshot=active_snapshot(),
        dry_run=dry_run,
    )

    assert reasons == ["dry-run risk gates did not pass"]


def test_failed_risk_gate_reasons_handles_malformed_gate_result():
    reasons = _failed_risk_gate_reasons(
        {
            "market_hours": "bad_result",
        }
    )

    assert reasons == ["market_hours: malformed risk gate result"]
