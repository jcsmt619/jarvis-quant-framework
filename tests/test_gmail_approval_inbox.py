from email.message import EmailMessage

import scripts.read_gmail_approval_inbox as script
from automation.gmail_approval_inbox import (
    GMAIL_INBOX_READ_CONFIRMATION,
    GmailApprovalInboxConfig,
    build_blocked_inbox_read_result,
    load_gmail_approval_inbox_config_from_env,
    read_gmail_approval_inbox,
)


def make_raw_email(*, from_email: str, subject: str, body: str) -> bytes:
    message = EmailMessage()
    message["From"] = from_email
    message["To"] = "jarvis@example.com"
    message["Subject"] = subject
    message.set_content(body)
    return message.as_bytes()


class FakeImapClient:
    def __init__(self, messages):
        self.messages = messages

    def login(self, username, password):
        return "OK", [b"logged in"]

    def select(self, mailbox, readonly=False):
        self.selected_readonly = readonly
        return "OK", [b"1"]

    def search(self, charset, criterion):
        ids = b" ".join(str(i + 1).encode() for i in range(len(self.messages)))
        return "OK", [ids]

    def fetch(self, raw_id, query):
        index = int(raw_id.decode()) - 1
        return "OK", [(b"RFC822", self.messages[index])]

    def close(self):
        return "OK", [b"closed"]

    def logout(self):
        return "BYE", [b"logout"]


def test_load_gmail_approval_inbox_config_from_env(monkeypatch):
    monkeypatch.setenv("GMAIL_SMTP_USERNAME", "sender@gmail.com")
    monkeypatch.setenv("GMAIL_SMTP_APP_PASSWORD", "app-password")
    monkeypatch.setenv("JARVIS_APPROVAL_EMAIL_FROM", "owner@gmail.com")

    config = load_gmail_approval_inbox_config_from_env()

    assert config.username == "sender@gmail.com"
    assert config.app_password == "app-password"
    assert config.authorized_from_email == "owner@gmail.com"
    assert config.imap_host == "imap.gmail.com"
    assert config.imap_port == 993


def test_blocked_inbox_read_result_does_not_use_client():
    result = build_blocked_inbox_read_result(
        blocked_reasons=["real Gmail inbox read is disabled"]
    )

    assert result.inbox_client_used is False
    assert result.messages_marked_read is False
    assert result.broker_order_call_performed is False
    assert result.live_trading_enabled is False


def test_read_gmail_approval_inbox_parses_authorized_approve():
    raw = make_raw_email(
        from_email="owner@gmail.com",
        subject="Jarvis Approval",
        body="APPROVE 482911\n\nextra text ignored",
    )

    def fake_factory(host, port):
        assert host == "imap.gmail.com"
        assert port == 993
        return FakeImapClient([raw])

    config = GmailApprovalInboxConfig(
        username="sender@gmail.com",
        app_password="app-password",
        authorized_from_email="owner@gmail.com",
    )

    result = read_gmail_approval_inbox(
        config=config,
        max_results=10,
        imap_client_factory=fake_factory,
    )

    assert result.inbox_client_used is True
    assert result.mailbox_selected_readonly is True
    assert result.messages_marked_read is False
    assert result.scanned_count == 1
    assert result.broker_order_call_performed is False

    email = result.approval_emails[0]
    assert email.command.action == "APPROVE"
    assert email.command.approval_id == "482911"
    assert email.command.valid is True
    assert email.sender_authorized is True
    assert email.blocked_reasons == []


def test_read_gmail_approval_inbox_blocks_unauthorized_sender():
    raw = make_raw_email(
        from_email="attacker@gmail.com",
        subject="Jarvis Approval",
        body="APPROVE 482911",
    )

    def fake_factory(host, port):
        return FakeImapClient([raw])

    config = GmailApprovalInboxConfig(
        username="sender@gmail.com",
        app_password="app-password",
        authorized_from_email="owner@gmail.com",
    )

    result = read_gmail_approval_inbox(
        config=config,
        imap_client_factory=fake_factory,
    )

    email = result.approval_emails[0]
    assert email.command.action == "APPROVE"
    assert email.sender_authorized is False
    assert "sender is not authorized: a***r@gmail.com" in email.blocked_reasons


def test_script_blocks_when_disabled(capsys):
    code = script.run_gmail_approval_inbox_report(
        env_file=None,
        enable_real_inbox_read=False,
        confirmation=None,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "GMAIL APPROVAL INBOX REPORT: PASS" in output
    assert "Inbox read enabled: false" in output
    assert "Inbox client used: false" in output
    assert "real Gmail inbox read is disabled" in output
    assert "Approval execution performed: false" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output


def test_script_blocks_without_confirmation(capsys, monkeypatch):
    monkeypatch.setenv("GMAIL_SMTP_USERNAME", "sender@gmail.com")
    monkeypatch.setenv("GMAIL_SMTP_APP_PASSWORD", "app-password")
    monkeypatch.setenv("JARVIS_APPROVAL_EMAIL_FROM", "owner@gmail.com")

    code = script.run_gmail_approval_inbox_report(
        env_file=None,
        enable_real_inbox_read=True,
        confirmation=None,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "Inbox read enabled: true" in output
    assert "Confirmation accepted: false" in output
    assert "Inbox client used: false" in output
    assert "real Gmail inbox read confirmation phrase was not accepted" in output
    assert "LIVE TRADING: DISABLED" in output


def test_script_reads_with_confirmation_and_injected_imap(capsys, monkeypatch):
    monkeypatch.setenv("GMAIL_SMTP_USERNAME", "sender@gmail.com")
    monkeypatch.setenv("GMAIL_SMTP_APP_PASSWORD", "app-password")
    monkeypatch.setenv("JARVIS_APPROVAL_EMAIL_FROM", "owner@gmail.com")

    raw = make_raw_email(
        from_email="owner@gmail.com",
        subject="Jarvis Approval",
        body="DENY 482911",
    )

    def fake_factory(host, port):
        return FakeImapClient([raw])

    code = script.run_gmail_approval_inbox_report(
        env_file=None,
        enable_real_inbox_read=True,
        confirmation=GMAIL_INBOX_READ_CONFIRMATION,
        injected_imap_client_factory=fake_factory,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "Inbox client used: true" in output
    assert "Messages marked read: false" in output
    assert "Parsed action: DENY" in output
    assert "Parsed approval id: 482911" in output
    assert "Approval execution performed: false" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output
