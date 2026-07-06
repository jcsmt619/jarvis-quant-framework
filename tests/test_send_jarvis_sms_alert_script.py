from pathlib import Path
from types import SimpleNamespace

import scripts.send_jarvis_sms_alert as script
from paper_trading.sms_alerts import TWILIO_SMS_CONFIRMATION


def test_sms_alert_script_dry_run_does_not_need_env_or_client(capsys):
    code = script.run_sms_alert_report(
        event="READY_TO_ARM_TRUE",
        engine="Wealth",
        symbol="EEM",
        intent_action="BUY",
        ready_to_arm=True,
        reasons=[],
        enable_real_sms_send=False,
        confirmation=None,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "SMS ALERT REPORT: PASS" in output
    assert "SMS send enabled: false" in output
    assert "Twilio client used: false" in output
    assert "SMS sent: false" in output
    assert "real SMS send is disabled" in output
    assert "LIVE TRADING: DISABLED" in output


def test_sms_alert_script_blocks_without_confirmation(capsys, monkeypatch):
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC_test")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "secret")
    monkeypatch.setenv("TWILIO_FROM_NUMBER", "+15550001111")
    monkeypatch.setenv("JARVIS_OWNER_PHONE", "+15550002222")

    code = script.run_sms_alert_report(
        event="READY_TO_ARM_TRUE",
        enable_real_sms_send=True,
        confirmation=None,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "SMS send enabled: true" in output
    assert "Confirmation accepted: false" in output
    assert "Twilio client used: false" in output
    assert "SMS sent: false" in output
    assert "real SMS confirmation phrase was not accepted" in output
    assert "LIVE TRADING: DISABLED" in output


def test_sms_alert_script_sends_with_confirmation_and_injected_client(capsys, monkeypatch):
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC_test")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "secret")
    monkeypatch.setenv("TWILIO_FROM_NUMBER", "+15550001111")
    monkeypatch.setenv("JARVIS_OWNER_PHONE", "+15550002222")

    class FakeMessages:
        def create(self, **kwargs):
            return SimpleNamespace(sid="SM_test", status="queued")

    class FakeClient:
        def __init__(self):
            self.messages = FakeMessages()

    def fake_factory(account_sid, auth_token):
        return FakeClient()

    code = script.run_sms_alert_report(
        event="READY_TO_ARM_TRUE",
        engine="Wealth",
        symbol="EEM",
        intent_action="BUY",
        ready_to_arm=True,
        enable_real_sms_send=True,
        confirmation=TWILIO_SMS_CONFIRMATION,
        injected_twilio_client_factory=fake_factory,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "SMS ALERT REPORT: PASS" in output
    assert "SMS send enabled: true" in output
    assert "Confirmation accepted: true" in output
    assert "Twilio client used: true" in output
    assert "SMS sent: true" in output
    assert "Message SID: SM_test" in output
    assert "Owner phone: ***2222" in output
    assert "LIVE TRADING: DISABLED" in output
