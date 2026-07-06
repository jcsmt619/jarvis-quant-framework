from types import SimpleNamespace

import scripts.send_jarvis_email_alert as script
from paper_trading.email_alerts import GMAIL_EMAIL_CONFIRMATION


def test_email_alert_script_dry_run_does_not_need_env_or_client(capsys):
    code = script.run_email_alert_report(
        event="READY_TO_ARM_TRUE",
        engine="Wealth",
        symbol="EEM",
        intent_action="BUY",
        ready_to_arm=True,
        reasons=[],
        enable_real_email_send=False,
        confirmation=None,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "EMAIL ALERT REPORT: PASS" in output
    assert "Email send enabled: false" in output
    assert "SMTP client used: false" in output
    assert "Email sent: false" in output
    assert "real email send is disabled" in output
    assert "LIVE TRADING: DISABLED" in output


def test_email_alert_script_blocks_without_confirmation(capsys, monkeypatch):
    monkeypatch.setenv("GMAIL_SMTP_USERNAME", "sender@gmail.com")
    monkeypatch.setenv("GMAIL_SMTP_APP_PASSWORD", "app-password")
    monkeypatch.setenv("JARVIS_ALERT_EMAIL_TO", "owner@gmail.com")

    code = script.run_email_alert_report(
        event="READY_TO_ARM_TRUE",
        enable_real_email_send=True,
        confirmation=None,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "Email send enabled: true" in output
    assert "Confirmation accepted: false" in output
    assert "SMTP client used: false" in output
    assert "Email sent: false" in output
    assert "real email confirmation phrase was not accepted" in output
    assert "LIVE TRADING: DISABLED" in output


def test_email_alert_script_sends_with_confirmation_and_injected_client(capsys, monkeypatch):
    monkeypatch.setenv("GMAIL_SMTP_USERNAME", "sender@gmail.com")
    monkeypatch.setenv("GMAIL_SMTP_APP_PASSWORD", "app-password")
    monkeypatch.setenv("JARVIS_ALERT_EMAIL_TO", "owner@gmail.com")

    class FakeSmtp:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def login(self, username, password):
            return None

        def send_message(self, message):
            return None

    def fake_factory(host, port, context):
        return FakeSmtp()

    code = script.run_email_alert_report(
        event="READY_TO_ARM_TRUE",
        engine="Wealth",
        symbol="EEM",
        intent_action="BUY",
        ready_to_arm=True,
        enable_real_email_send=True,
        confirmation=GMAIL_EMAIL_CONFIRMATION,
        injected_smtp_client_factory=fake_factory,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "EMAIL ALERT REPORT: PASS" in output
    assert "Email send enabled: true" in output
    assert "Confirmation accepted: true" in output
    assert "SMTP client used: true" in output
    assert "Email sent: true" in output
    assert "From: s***r@gmail.com" in output
    assert "To: o***r@gmail.com" in output
    assert "LIVE TRADING: DISABLED" in output
