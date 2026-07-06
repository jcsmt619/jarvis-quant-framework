from types import SimpleNamespace

import scripts.run_ready_to_arm_approval_request as script
from automation.approval_gateway import read_approval_record
from paper_trading.email_alerts import GMAIL_EMAIL_CONFIRMATION


def make_completed(stdout: str, returncode: int = 0, stderr: str = ""):
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)


def test_ready_to_arm_false_skips_approval_record_and_email(capsys, tmp_path):
    def fake_runner(command):
        return make_completed(
            """
Intent action: BLOCKED
READY TO ARM: false
READY TO ARM REASONS: ['market session is not open']
"""
        )

    code = script.run_ready_to_arm_approval_request(
        env_file=None,
        approvals_dir=tmp_path,
        injected_workflow_runner=fake_runner,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "Ready to arm detected: false" in output
    assert "Approval request decision: SKIPPED_READY_TO_ARM_FALSE" in output
    assert "Approval record created: false" in output
    assert "Email sent: false" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output
    assert list(tmp_path.glob("approval_*.json")) == []


def test_ready_to_arm_unknown_skips_approval_record_and_email(capsys, tmp_path):
    def fake_runner(command):
        return make_completed(
            """
Intent action: UNKNOWN
READY TO ARM: maybe
READY TO ARM REASONS: ['unparseable']
"""
        )

    code = script.run_ready_to_arm_approval_request(
        env_file=None,
        approvals_dir=tmp_path,
        injected_workflow_runner=fake_runner,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "Ready to arm detected: unknown" in output
    assert "Approval request decision: SKIPPED_READY_TO_ARM_UNKNOWN" in output
    assert "Approval record created: false" in output
    assert list(tmp_path.glob("approval_*.json")) == []


def test_ready_to_arm_true_creates_approval_record_but_blocks_email_by_default(capsys, tmp_path):
    def fake_runner(command):
        return make_completed(
            """
Intent action: BUY
READY TO ARM: true
READY TO ARM REASONS: []
"""
        )

    code = script.run_ready_to_arm_approval_request(
        env_file=None,
        approvals_dir=tmp_path,
        injected_workflow_runner=fake_runner,
        enable_real_email_send=False,
        confirmation=None,
    )
    output = capsys.readouterr().out

    files = list(tmp_path.glob("approval_*.json"))
    assert code == 0
    assert len(files) == 1
    record = read_approval_record(files[0])

    assert record.status == "PENDING"
    assert record.target == "READY_TO_ARM_REVIEW"
    assert record.live_trading_enabled is False
    assert "Approval record created: true" in output
    assert f"Approval command: APPROVE {record.approval_id}" in output
    assert f"Deny command: DENY {record.approval_id}" in output
    assert "Email send enabled: false" in output
    assert "Email sent: false" in output
    assert "real email send is disabled" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output


def test_ready_to_arm_true_requires_email_confirmation(capsys, tmp_path):
    def fake_runner(command):
        return make_completed(
            """
Intent action: BUY
READY TO ARM: true
READY TO ARM REASONS: []
"""
        )

    code = script.run_ready_to_arm_approval_request(
        env_file=None,
        approvals_dir=tmp_path,
        injected_workflow_runner=fake_runner,
        enable_real_email_send=True,
        confirmation=None,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "Approval record created: true" in output
    assert "Email send enabled: true" in output
    assert "Confirmation accepted: false" in output
    assert "SMTP client used: false" in output
    assert "Email sent: false" in output
    assert "real email confirmation phrase was not accepted" in output
    assert "LIVE TRADING: DISABLED" in output


def test_ready_to_arm_true_sends_email_with_confirmation_and_injected_smtp(capsys, monkeypatch, tmp_path):
    monkeypatch.setenv("GMAIL_SMTP_USERNAME", "jarvisquant619@gmail.com")
    monkeypatch.setenv("GMAIL_SMTP_APP_PASSWORD", "app-password")
    monkeypatch.setenv("JARVIS_ALERT_EMAIL_TO", "owner@gmail.com")

    def fake_runner(command):
        return make_completed(
            """
Intent action: BUY
READY TO ARM: true
READY TO ARM REASONS: []
"""
        )

    class FakeSmtp:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def login(self, username, password):
            return None

        def send_message(self, message):
            self.message = message
            return None

    def fake_smtp_factory(host, port, context):
        return FakeSmtp()

    code = script.run_ready_to_arm_approval_request(
        env_file=None,
        approvals_dir=tmp_path,
        injected_workflow_runner=fake_runner,
        injected_smtp_client_factory=fake_smtp_factory,
        enable_real_email_send=True,
        confirmation=GMAIL_EMAIL_CONFIRMATION,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "Approval record created: true" in output
    assert "SMTP client used: true" in output
    assert "Email sent: true" in output
    assert "From: j***9@gmail.com" in output
    assert "To: o***r@gmail.com" in output
    assert "APPROVE " in output
    assert "DENY " in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output


def test_workflow_failure_does_not_create_approval_record_or_email(capsys, tmp_path):
    def fake_runner(command):
        return make_completed("bad output", returncode=1, stderr="workflow failed")

    code = script.run_ready_to_arm_approval_request(
        env_file=None,
        approvals_dir=tmp_path,
        injected_workflow_runner=fake_runner,
    )
    output = capsys.readouterr().out

    assert code == 1
    assert "READY TO ARM APPROVAL REQUEST: FAIL" in output
    assert "Approval record created: false" in output
    assert "Email sent: false" in output
    assert "LIVE TRADING: DISABLED" in output
    assert list(tmp_path.glob("approval_*.json")) == []
