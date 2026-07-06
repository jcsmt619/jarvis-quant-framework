from datetime import UTC, datetime

import scripts.run_full_approval_drill as script
from automation.approval_gateway import read_approval_record
from automation.approval_receipt_gate import evaluate_approval_receipt_gate


def fixed_now():
    return datetime(2026, 7, 6, 12, 0, tzinfo=UTC)


def test_full_drill_auto_approves_and_runs_gated_arm(capsys, tmp_path):
    calls = []

    def fake_gated_runner(**kwargs):
        calls.append(kwargs)
        print("FAKE GATED ARM RUNNER")
        print("Broker order call performed: false")
        print("LIVE TRADING: DISABLED")
        return 0

    code = script.run_full_approval_drill(
        env_file=None,
        approvals_dir=tmp_path,
        now=fixed_now(),
        injected_gated_arm_runner=fake_gated_runner,
    )
    output = capsys.readouterr().out

    approval_files = list(tmp_path.glob("approval_*.json"))
    assert code == 0
    assert len(approval_files) == 1
    record = read_approval_record(approval_files[0])

    assert record.status == "APPROVED"
    assert len(calls) == 1
    assert calls[0]["approval_id"] == record.approval_id
    assert calls[0]["enable_real_paper_execution"] is False
    assert "FULL APPROVAL DRILL REPORT: PASS" in output
    assert "Pending gate allowed before approval: false" in output
    assert "Approval applied: true" in output
    assert "Receipt gate allowed after approval step: true" in output
    assert "Approval-gated wrapper drill: ATTEMPTED_DISABLED_MODE" in output
    assert "Gated arm attempted: true" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output


def test_full_drill_no_auto_approve_skips_gated_arm(capsys, tmp_path):
    calls = []

    def fake_gated_runner(**kwargs):
        calls.append(kwargs)
        return 0

    code = script.run_full_approval_drill(
        env_file=None,
        approvals_dir=tmp_path,
        auto_approve=False,
        now=fixed_now(),
        injected_gated_arm_runner=fake_gated_runner,
    )
    output = capsys.readouterr().out

    approval_files = list(tmp_path.glob("approval_*.json"))
    record = read_approval_record(approval_files[0])

    assert code == 0
    assert record.status == "PENDING"
    assert calls == []
    assert "Auto approve enabled: false" in output
    assert "Approval applied: false" in output
    assert "Receipt gate allowed after approval step: false" in output
    assert "Approval-gated wrapper drill: SKIPPED_RECEIPT_GATE_BLOCKED" in output
    assert "Gated arm attempted: false" in output
    assert "LIVE TRADING: DISABLED" in output


def test_full_drill_can_skip_gated_arm_after_approval(capsys, tmp_path):
    calls = []

    def fake_gated_runner(**kwargs):
        calls.append(kwargs)
        return 0

    code = script.run_full_approval_drill(
        env_file=None,
        approvals_dir=tmp_path,
        run_gated_arm=False,
        now=fixed_now(),
        injected_gated_arm_runner=fake_gated_runner,
    )
    output = capsys.readouterr().out

    approval_files = list(tmp_path.glob("approval_*.json"))
    record = read_approval_record(approval_files[0])
    gate = evaluate_approval_receipt_gate(
        approval_id=record.approval_id,
        approvals_dir=tmp_path,
        now=fixed_now(),
    )

    assert code == 0
    assert record.status == "APPROVED"
    assert gate.allowed is True
    assert calls == []
    assert "Approval-gated wrapper drill: SKIPPED_BY_FLAG" in output
    assert "Gated arm attempted: false" in output
    assert "LIVE TRADING: DISABLED" in output


def test_full_drill_returns_gated_arm_failure_code(capsys, tmp_path):
    def fake_gated_runner(**kwargs):
        print("FAKE GATED ARM FAILURE")
        print("Broker order call performed: false")
        print("LIVE TRADING: DISABLED")
        return 7

    code = script.run_full_approval_drill(
        env_file=None,
        approvals_dir=tmp_path,
        now=fixed_now(),
        injected_gated_arm_runner=fake_gated_runner,
    )
    output = capsys.readouterr().out

    assert code == 7
    assert "Approval-gated wrapper return code: 7" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output


def test_full_drill_writes_approval_record_with_safe_target(tmp_path):
    code = script.run_full_approval_drill(
        env_file=None,
        approvals_dir=tmp_path,
        run_gated_arm=False,
        now=fixed_now(),
    )

    approval_files = list(tmp_path.glob("approval_*.json"))
    record = read_approval_record(approval_files[0])

    assert code == 0
    assert record.target == "READY_TO_ARM_REVIEW"
    assert record.source == "local_drill"
    assert record.live_trading_enabled is False
