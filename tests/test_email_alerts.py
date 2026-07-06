from email.message import EmailMessage

import pytest

from paper_trading.email_alerts import (
    EmailAlertResult,
    GmailEmailConfig,
    GmailEmailConfigError,
    build_blocked_email_result,
    build_email_alert_body,
    build_email_alert_subject,
    load_gmail_email_config_from_env,
    mask_email,
    send_email_alert,
)


def test_load_gmail_email_config_from_env(monkeypatch):
    monkeypatch.setenv("GMAIL_SMTP_USERNAME", "sender@gmail.com")
    monkeypatch.setenv("GMAIL_SMTP_APP_PASSWORD", "app-password")
    monkeypatch.setenv("JARVIS_ALERT_EMAIL_TO", "owner@gmail.com")

    config = load_gmail_email_config_from_env()

    assert config.username == "sender@gmail.com"
    assert config.app_password == "app-password"
    assert config.from_email == "sender@gmail.com"
    assert config.to_email == "owner@gmail.com"
    assert config.smtp_host == "smtp.gmail.com"
    assert config.smtp_port == 465


def test_load_gmail_email_config_requires_env(monkeypatch):
    for key in [
        "GMAIL_SMTP_USERNAME",
        "GMAIL_SMTP_APP_PASSWORD",
        "GMAIL_SMTP_FROM",
        "JARVIS_ALERT_EMAIL_TO",
    ]:
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(GmailEmailConfigError):
        load_gmail_email_config_from_env()


def test_mask_email():
    assert mask_email("james@example.com") == "j***s@example.com"


def test_build_email_alert_subject():
    subject = build_email_alert_subject(
        event="READY_TO_ARM_TRUE",
        symbol="EEM",
        ready_to_arm=True,
    )

    assert subject == "Jarvis Alert: READY_TO_ARM_TRUE | EEM | READY_TO_ARM=TRUE"


def test_build_email_alert_body_contains_safety_fields():
    body = build_email_alert_body(
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
    assert "does not submit broker orders" in body


def test_build_blocked_email_result_does_not_send():
    result = build_blocked_email_result(
        event="TEST_ALERT",
        subject="subject",
        body="body",
        blocked_reasons=["real email send is disabled"],
    )

    assert result.sent is False
    assert result.smtp_client_used is False
    assert result.blocked_reasons == ["real email send is disabled"]
    assert result.live_trading_enabled is False


def test_send_email_alert_uses_injected_smtp_client():
    calls = []

    class FakeSmtp:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def login(self, username, password):
            calls.append(("login", username, password))

        def send_message(self, message):
            assert isinstance(message, EmailMessage)
            calls.append(("send_message", message["From"], message["To"], message["Subject"]))

    def fake_factory(host, port, context):
        calls.append(("factory", host, port, context is not None))
        return FakeSmtp()

    config = GmailEmailConfig(
        username="sender@gmail.com",
        app_password="app-password",
        from_email="sender@gmail.com",
        to_email="owner@gmail.com",
    )

    result = send_email_alert(
        config=config,
        event="READY_TO_ARM_TRUE",
        subject="Jarvis subject",
        body="Jarvis body",
        smtp_client_factory=fake_factory,
    )

    assert result.sent is True
    assert result.smtp_client_used is True
    assert result.from_email == "sender@gmail.com"
    assert result.to_email == "owner@gmail.com"
    assert calls[0] == ("factory", "smtp.gmail.com", 465, True)
    assert calls[1] == ("login", "sender@gmail.com", "app-password")
    assert calls[2] == ("send_message", "sender@gmail.com", "owner@gmail.com", "Jarvis subject")
    assert result.live_trading_enabled is False
