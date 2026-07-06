from email.message import EmailMessage

import scripts.process_gmail_approvals as script
from automation.approval_gateway import create_approval_record, read_approval_record, write_approval_record
from automation.gmail_approval_inbox import (
    GMAIL_INBOX_READ_CONFIRMATION,
    GmailApprovalInboxConfig,
    read_gmail_approval_inbox,
)
from automation.gmail_approval_processor import process_gmail_approval_emails


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


def test_processor_applies_authorized_approve(tmp_path):
    record = create_approval_record(target="PAPER_DRILL")
    write_approval_record(record, output_dir=tmp_path)

    raw = make_raw_email(
        from_email="owner@gmail.com",
        subject="Jarvis Approval",
        body=f"APPROVE {record.approval_id}",
    )

    def fake_factory(host, port):
        return FakeImapClient([raw])

    inbox_result = read_gmail_approval_inbox(
        config=GmailApprovalInboxConfig(
            username="sender@gmail.com",
            app_password="app-password",
            authorized_from_email="owner@gmail.com",
        ),
        imap_client_factory=fake_factory,
    )

    result = process_gmail_approval_emails(
        inbox_result=inbox_result,
        approvals_dir=tmp_path,
    )

    loaded = read_approval_record(tmp_path / f"approval_{record.approval_id}.json")

    assert result.processed_count == 1
    assert result.applied_count == 1
    assert result.processed_emails[0].applied is True
    assert result.processed_emails[0].decision_status == "APPROVED"
    assert loaded.status == "APPROVED"
    assert loaded.live_trading_enabled is False
    assert result.broker_order_call_performed is False
    assert result.live_trading_enabled is False


def test_processor_applies_authorized_deny(tmp_path):
    record = create_approval_record(target="PAPER_DRILL")
    write_approval_record(record, output_dir=tmp_path)

    raw = make_raw_email(
        from_email="owner@gmail.com",
        subject="Jarvis Approval",
        body=f"DENY {record.approval_id}",
    )

    def fake_factory(host, port):
        return FakeImapClient([raw])

    inbox_result = read_gmail_approval_inbox(
        config=GmailApprovalInboxConfig(
            username="sender@gmail.com",
            app_password="app-password",
            authorized_from_email="owner@gmail.com",
        ),
        imap_client_factory=fake_factory,
    )

    result = process_gmail_approval_emails(
        inbox_result=inbox_result,
        approvals_dir=tmp_path,
    )

    loaded = read_approval_record(tmp_path / f"approval_{record.approval_id}.json")

    assert result.applied_count == 1
    assert result.processed_emails[0].decision_status == "DENIED"
    assert loaded.status == "DENIED"


def test_processor_rejects_unauthorized_sender(tmp_path):
    record = create_approval_record(target="PAPER_DRILL")
    write_approval_record(record, output_dir=tmp_path)

    raw = make_raw_email(
        from_email="attacker@gmail.com",
        subject="Jarvis Approval",
        body=f"APPROVE {record.approval_id}",
    )

    def fake_factory(host, port):
        return FakeImapClient([raw])

    inbox_result = read_gmail_approval_inbox(
        config=GmailApprovalInboxConfig(
            username="sender@gmail.com",
            app_password="app-password",
            authorized_from_email="owner@gmail.com",
        ),
        imap_client_factory=fake_factory,
    )

    result = process_gmail_approval_emails(
        inbox_result=inbox_result,
        approvals_dir=tmp_path,
    )

    loaded = read_approval_record(tmp_path / f"approval_{record.approval_id}.json")

    assert result.applied_count == 0
    assert result.processed_emails[0].sender_authorized is False
    assert result.processed_emails[0].decision_status == "BLOCKED"
    assert loaded.status == "PENDING"


def test_processor_status_does_not_update_record(tmp_path):
    raw = make_raw_email(
        from_email="owner@gmail.com",
        subject="Jarvis Approval",
        body="STATUS",
    )

    def fake_factory(host, port):
        return FakeImapClient([raw])

    inbox_result = read_gmail_approval_inbox(
        config=GmailApprovalInboxConfig(
            username="sender@gmail.com",
            app_password="app-password",
            authorized_from_email="owner@gmail.com",
        ),
        imap_client_factory=fake_factory,
    )

    result = process_gmail_approval_emails(
        inbox_result=inbox_result,
        approvals_dir=tmp_path,
    )

    assert result.applied_count == 0
    assert result.processed_emails[0].decision_status == "NO_RECORD_ACTION"
    assert "STATUS does not update an approval record" in result.processed_emails[0].blocked_reasons


def test_processor_missing_record_is_blocked(tmp_path):
    raw = make_raw_email(
        from_email="owner@gmail.com",
        subject="Jarvis Approval",
        body="APPROVE 123456",
    )

    def fake_factory(host, port):
        return FakeImapClient([raw])

    inbox_result = read_gmail_approval_inbox(
        config=GmailApprovalInboxConfig(
            username="sender@gmail.com",
            app_password="app-password",
            authorized_from_email="owner@gmail.com",
        ),
        imap_client_factory=fake_factory,
    )

    result = process_gmail_approval_emails(
        inbox_result=inbox_result,
        approvals_dir=tmp_path,
    )

    assert result.applied_count == 0
    assert result.processed_emails[0].decision_status == "MISSING_RECORD"


def test_script_disabled_does_not_read_or_update(capsys, tmp_path):
    code = script.run_gmail_approval_processor_report(
        env_file=None,
        approvals_dir=tmp_path,
        enable_real_inbox_read=False,
        confirmation=None,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "GMAIL APPROVAL PROCESSOR REPORT: PASS" in output
    assert "Inbox read enabled: false" in output
    assert "Inbox client used: false" in output
    assert "Approval records updated: 0" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output


def test_script_enabled_requires_confirmation(capsys, tmp_path):
    code = script.run_gmail_approval_processor_report(
        env_file=None,
        approvals_dir=tmp_path,
        enable_real_inbox_read=True,
        confirmation=None,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "Inbox read enabled: true" in output
    assert "Confirmation accepted: false" in output
    assert "Inbox client used: false" in output
    assert "Approval records updated: 0" in output
    assert "LIVE TRADING: DISABLED" in output


def test_script_processes_authorized_approval_with_injected_imap(capsys, monkeypatch, tmp_path):
    monkeypatch.setenv("GMAIL_SMTP_USERNAME", "sender@gmail.com")
    monkeypatch.setenv("GMAIL_SMTP_APP_PASSWORD", "app-password")
    monkeypatch.setenv("JARVIS_APPROVAL_EMAIL_FROM", "owner@gmail.com")

    record = create_approval_record(target="PAPER_DRILL")
    write_approval_record(record, output_dir=tmp_path)

    raw = make_raw_email(
        from_email="owner@gmail.com",
        subject="Jarvis Approval",
        body=f"APPROVE {record.approval_id}",
    )

    def fake_factory(host, port):
        return FakeImapClient([raw])

    code = script.run_gmail_approval_processor_report(
        env_file=None,
        approvals_dir=tmp_path,
        enable_real_inbox_read=True,
        confirmation=GMAIL_INBOX_READ_CONFIRMATION,
        injected_imap_client_factory=fake_factory,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "Inbox client used: true" in output
    assert "Approval records updated: 1" in output
    assert "Applied to approval record: true" in output
    assert "Decision status: APPROVED" in output
    assert "Broker order call performed: false" in output
    assert "LIVE TRADING: DISABLED" in output
