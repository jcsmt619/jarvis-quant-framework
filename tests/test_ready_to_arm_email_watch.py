from types import SimpleNamespace

import scripts.run_ready_to_arm_email_watch as script
from paper_trading.email_alerts import GMAIL_EMAIL_CONFIRMATION


def make_completed(stdout: str, returncode: int = 0, stderr: str = ""):
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)


def test_parse_ready_to_arm_true():
    parsed = script.parse_ready_to_arm_output(
        """
Intent action: BUY
READY TO ARM: true
READY TO ARM REASONS: []
"""
    )

    assert parsed.ready_to_arm is True
    assert parsed.intent_action == "BUY"
    assert parsed.reasons == []


def test_parse_ready_to_arm_false_with_reasons():
    parsed = script.parse_ready_to_arm_output(
        """
Intent action: HOLD
READY TO ARM: false
READY TO ARM REASONS: ['intent action is not executable: HOLD']
"""
    )

    assert parsed.ready_to_arm is False
    assert parsed.intent_action == "HOLD"
    assert parsed.reasons == ["intent action is not executable: HOLD"]


def test_ready_to_arm_false_skips_email(capsys):
    def fake_runner(command):
        return make_completed(
            """
Intent action: HOLD
READY TO ARM: false
READY TO ARM REASONS: ['intent action is not executable: HOLD']
"""
        )

    code = script.run_ready_to_arm_email_watch(
        env_file=None,
        injected_workflow_runner=fake_runner,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "Ready to arm detected: false" in output
    assert "Email alert decision: SKIPPED_READY_TO_ARM_FALSE" in output
    assert "SMTP client used: false" in output
    assert "Email sent: false" in output
    assert "LIVE TRADING: DISABLED" in output


def test_ready_to_arm_true_dry_run_blocks_email(capsys):
    def fake_runner(command):
        return make_completed(
            """
Intent action: BUY
READY TO ARM: true
READY TO ARM REASONS: []
"""
        )

    code = script.run_ready_to_arm_email_watch(
        env_file=None,
        injected_workflow_runner=fake_runner,
        enable_real_email_send=False,
        confirmation=None,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "Ready to arm detected: true" in output
    assert "Email alert decision: READY_TO_ARM_TRUE" in output
    assert "Email send enabled: false" in output
    assert "SMTP client used: false" in output
    assert "Email sent: false" in output
    assert "real email send is disabled" in output
    assert "LIVE TRADING: DISABLED" in output


def test_ready_to_arm_true_sends_with_confirmation_and_injected_smtp(capsys, monkeypatch):
    monkeypatch.setenv("GMAIL_SMTP_USERNAME", "sender@gmail.com")
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
            return None

    def fake_smtp_factory(host, port, context):
        return FakeSmtp()

    code = script.run_ready_to_arm_email_watch(
        env_file=None,
        injected_workflow_runner=fake_runner,
        injected_smtp_client_factory=fake_smtp_factory,
        enable_real_email_send=True,
        confirmation=GMAIL_EMAIL_CONFIRMATION,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "Ready to arm detected: true" in output
    assert "Email sent: true" in output
    assert "SMTP client used: true" in output
    assert "From: s***r@gmail.com" in output
    assert "To: o***r@gmail.com" in output
    assert "LIVE TRADING: DISABLED" in output


def test_workflow_failure_skips_email(capsys):
    def fake_runner(command):
        return make_completed("bad output", returncode=1, stderr="workflow failed")

    code = script.run_ready_to_arm_email_watch(
        env_file=None,
        injected_workflow_runner=fake_runner,
    )
    output = capsys.readouterr().out

    assert code == 1
    assert "READY TO ARM EMAIL WATCH: FAIL" in output
    assert "Email alert decision: SKIPPED_WORKFLOW_FAILED" in output
    assert "Email sent: false" in output
    assert "LIVE TRADING: DISABLED" in output
