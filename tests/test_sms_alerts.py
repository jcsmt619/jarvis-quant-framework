from types import SimpleNamespace

import pytest

from paper_trading.sms_alerts import (
    SmsAlertResult,
    TwilioSmsConfig,
    TwilioSmsConfigError,
    build_blocked_sms_result,
    build_sms_alert_body,
    load_twilio_sms_config_from_env,
    mask_phone_number,
    send_sms_alert,
)


def test_load_twilio_sms_config_from_env(monkeypatch):
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC_test")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "secret")
    monkeypatch.setenv("TWILIO_FROM_NUMBER", "+15550001111")
    monkeypatch.setenv("JARVIS_OWNER_PHONE", "+15550002222")

    config = load_twilio_sms_config_from_env()

    assert config.account_sid == "AC_test"
    assert config.auth_token == "secret"
    assert config.from_number == "+15550001111"
    assert config.owner_phone == "+15550002222"


def test_load_twilio_sms_config_requires_env(monkeypatch):
    for key in [
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
        "TWILIO_FROM_NUMBER",
        "JARVIS_OWNER_PHONE",
    ]:
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(TwilioSmsConfigError):
        load_twilio_sms_config_from_env()


def test_mask_phone_number():
    assert mask_phone_number("+1 555 000 2222") == "***2222"


def test_build_sms_alert_body_contains_safety_fields():
    body = build_sms_alert_body(
        event="READY_TO_ARM_TRUE",
        engine="Wealth",
        symbol="EEM",
        intent_action="BUY",
        ready_to_arm=True,
        reasons=[],
    )

    assert "Jarvis Alert: READY_TO_ARM_TRUE" in body
    assert "Engine: Wealth" in body
    assert "Symbol: EEM" in body
    assert "Intent: BUY" in body
    assert "READY TO ARM: true" in body
    assert "LIVE TRADING: DISABLED" in body


def test_build_blocked_sms_result_does_not_send():
    result = build_blocked_sms_result(
        event="TEST_ALERT",
        body="hello",
        blocked_reasons=["real SMS send is disabled"],
    )

    assert result.sent is False
    assert result.twilio_client_used is False
    assert result.blocked_reasons == ["real SMS send is disabled"]
    assert result.live_trading_enabled is False


def test_send_sms_alert_uses_injected_client():
    calls = []

    class FakeMessages:
        def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(sid="SM_test", status="queued")

    class FakeClient:
        def __init__(self):
            self.messages = FakeMessages()

    def fake_factory(account_sid, auth_token):
        assert account_sid == "AC_test"
        assert auth_token == "secret"
        return FakeClient()

    config = TwilioSmsConfig(
        account_sid="AC_test",
        auth_token="secret",
        from_number="+15550001111",
        owner_phone="+15550002222",
    )

    result = send_sms_alert(
        config=config,
        event="READY_TO_ARM_TRUE",
        body="Jarvis Alert",
        twilio_client_factory=fake_factory,
    )

    assert result.sent is True
    assert result.twilio_client_used is True
    assert result.message_sid == "SM_test"
    assert result.message_status == "queued"
    assert calls == [
        {
            "body": "Jarvis Alert",
            "from_": "+15550001111",
            "to": "+15550002222",
        }
    ]
    assert result.live_trading_enabled is False
