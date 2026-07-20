"""
Tests for email_notifier — covers happy path, skip conditions, silent failures,
and threading behaviour. All tests call _send() directly so they are synchronous.
"""
import base64
import json
import smtplib
import threading
from datetime import datetime
from unittest.mock import patch

import pytest

import email_notifier


MEMBER    = {"id": 1, "first_name": "Jane", "last_name": "Smith"}
CG_EMAIL  = {"email": "parent@example.com"}
CG_BLANK  = {"email": ""}
TIMESTAMP = datetime(2026, 6, 14, 15, 42, 0)


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def config_file(tmp_path, monkeypatch):
    """Point every test at a fresh temp config with notifications enabled."""
    path = tmp_path / "email_config.json"
    path.write_text(json.dumps({
        "sender_email": "sender@example.com",
        "app_password": "testpassword",
        "enabled": True,
    }))
    monkeypatch.setattr(email_notifier, "_CONFIG_PATH", str(path))
    return path


def smtp_server():
    """Return the mock 'server' object from inside a patched SMTP context manager."""
    # smtplib.SMTP is used as `with smtplib.SMTP(...) as server:`, so the object
    # the code writes to is mock_class.return_value.__enter__.return_value.
    return patch("smtplib.SMTP")


# ── Happy path ─────────────────────────────────────────────────────────────────

def test_email_is_sent_when_caregiver_has_email(monkeypatch):
    monkeypatch.setattr(email_notifier.database, "get_caregiver", lambda _: CG_EMAIL)
    with smtp_server() as cls:
        email_notifier._send(MEMBER, "IN", TIMESTAMP)
    cls.return_value.__enter__.return_value.send_message.assert_called_once()


def test_email_sent_to_correct_recipient(monkeypatch):
    monkeypatch.setattr(email_notifier.database, "get_caregiver", lambda _: CG_EMAIL)
    with smtp_server() as cls:
        email_notifier._send(MEMBER, "IN", TIMESTAMP)
    msg = cls.return_value.__enter__.return_value.send_message.call_args[0][0]
    assert msg["To"] == "parent@example.com"


def test_email_from_is_sender_address(monkeypatch):
    monkeypatch.setattr(email_notifier.database, "get_caregiver", lambda _: CG_EMAIL)
    with smtp_server() as cls:
        email_notifier._send(MEMBER, "IN", TIMESTAMP)
    msg = cls.return_value.__enter__.return_value.send_message.call_args[0][0]
    assert msg["From"] == "sender@example.com"


def test_smtp_uses_starttls(monkeypatch):
    monkeypatch.setattr(email_notifier.database, "get_caregiver", lambda _: CG_EMAIL)
    with smtp_server() as cls:
        email_notifier._send(MEMBER, "IN", TIMESTAMP)
    cls.return_value.__enter__.return_value.starttls.assert_called_once()


def test_smtp_logs_in_with_credentials(monkeypatch):
    monkeypatch.setattr(email_notifier.database, "get_caregiver", lambda _: CG_EMAIL)
    with smtp_server() as cls:
        email_notifier._send(MEMBER, "IN", TIMESTAMP)
    cls.return_value.__enter__.return_value.login.assert_called_once_with(
        "sender@example.com", "testpassword"
    )


# ── Subject line ───────────────────────────────────────────────────────────────

def test_subject_contains_in_direction(monkeypatch):
    monkeypatch.setattr(email_notifier.database, "get_caregiver", lambda _: CG_EMAIL)
    with smtp_server() as cls:
        email_notifier._send(MEMBER, "IN", TIMESTAMP)
    msg = cls.return_value.__enter__.return_value.send_message.call_args[0][0]
    assert "IN" in msg["Subject"]


def test_subject_contains_out_direction(monkeypatch):
    monkeypatch.setattr(email_notifier.database, "get_caregiver", lambda _: CG_EMAIL)
    with smtp_server() as cls:
        email_notifier._send(MEMBER, "OUT", TIMESTAMP)
    msg = cls.return_value.__enter__.return_value.send_message.call_args[0][0]
    assert "OUT" in msg["Subject"]


def test_subject_contains_member_name(monkeypatch):
    monkeypatch.setattr(email_notifier.database, "get_caregiver", lambda _: CG_EMAIL)
    with smtp_server() as cls:
        email_notifier._send(MEMBER, "IN", TIMESTAMP)
    msg = cls.return_value.__enter__.return_value.send_message.call_args[0][0]
    assert "Jane Smith" in msg["Subject"]


# ── Body content ───────────────────────────────────────────────────────────────

def _body(cls):
    msg = cls.return_value.__enter__.return_value.send_message.call_args[0][0]
    # MIMEMultipart body is base64-encoded; decode the first part's payload
    encoded = msg.get_payload(0).get_payload()
    return base64.b64decode(encoded).decode("utf-8")


def test_body_contains_member_name(monkeypatch):
    monkeypatch.setattr(email_notifier.database, "get_caregiver", lambda _: CG_EMAIL)
    with smtp_server() as cls:
        email_notifier._send(MEMBER, "IN", TIMESTAMP)
    assert "Jane Smith" in _body(cls)


def test_body_contains_formatted_time(monkeypatch):
    monkeypatch.setattr(email_notifier.database, "get_caregiver", lambda _: CG_EMAIL)
    with smtp_server() as cls:
        email_notifier._send(MEMBER, "IN", TIMESTAMP)
    assert "03:42 PM" in _body(cls)


def test_body_contains_formatted_date(monkeypatch):
    monkeypatch.setattr(email_notifier.database, "get_caregiver", lambda _: CG_EMAIL)
    with smtp_server() as cls:
        email_notifier._send(MEMBER, "IN", TIMESTAMP)
    assert "14 June 2026" in _body(cls)


def test_body_contains_direction(monkeypatch):
    monkeypatch.setattr(email_notifier.database, "get_caregiver", lambda _: CG_EMAIL)
    with smtp_server() as cls:
        email_notifier._send(MEMBER, "OUT", TIMESTAMP)
    assert "OUT" in _body(cls)


# ── Skip conditions ────────────────────────────────────────────────────────────

def test_skipped_when_no_caregiver(monkeypatch):
    monkeypatch.setattr(email_notifier.database, "get_caregiver", lambda _: None)
    with smtp_server() as cls:
        email_notifier._send(MEMBER, "IN", TIMESTAMP)
    cls.return_value.__enter__.return_value.send_message.assert_not_called()


def test_skipped_when_caregiver_email_is_empty(monkeypatch):
    monkeypatch.setattr(email_notifier.database, "get_caregiver", lambda _: CG_BLANK)
    with smtp_server() as cls:
        email_notifier._send(MEMBER, "IN", TIMESTAMP)
    cls.return_value.__enter__.return_value.send_message.assert_not_called()


def test_skipped_when_notifications_disabled(tmp_path, monkeypatch):
    disabled = tmp_path / "disabled.json"
    disabled.write_text(json.dumps({
        "sender_email": "sender@example.com",
        "app_password": "testpassword",
        "enabled": False,
    }))
    monkeypatch.setattr(email_notifier, "_CONFIG_PATH", str(disabled))
    monkeypatch.setattr(email_notifier.database, "get_caregiver", lambda _: CG_EMAIL)
    with smtp_server() as cls:
        email_notifier._send(MEMBER, "IN", TIMESTAMP)
    cls.return_value.__enter__.return_value.send_message.assert_not_called()


# ── notify_on filtering ────────────────────────────────────────────────────────

@pytest.mark.parametrize("notify_on,direction,should_send", [
    ("BOTH", "IN",  True),
    ("BOTH", "OUT", True),
    ("IN",   "IN",  True),
    ("IN",   "OUT", False),
    ("OUT",  "IN",  False),
    ("OUT",  "OUT", True),
    ("NONE", "IN",  False),
    ("NONE", "OUT", False),
])
def test_notify_on_filtering(monkeypatch, notify_on, direction, should_send):
    cg = {**CG_EMAIL, "notify_on": notify_on}
    monkeypatch.setattr(email_notifier.database, "get_caregiver", lambda _: cg)
    with smtp_server() as cls:
        email_notifier._send(MEMBER, direction, TIMESTAMP)
    send_called = cls.return_value.__enter__.return_value.send_message.called
    assert send_called == should_send


def test_missing_notify_on_defaults_to_both(monkeypatch):
    """Caregivers without a notify_on value (older records) default to BOTH."""
    cg = {"email": "parent@example.com"}  # no notify_on key
    monkeypatch.setattr(email_notifier.database, "get_caregiver", lambda _: cg)
    with smtp_server() as cls:
        email_notifier._send(MEMBER, "IN", TIMESTAMP)
    cls.return_value.__enter__.return_value.send_message.assert_called_once()


# ── Silent failures ────────────────────────────────────────────────────────────

def test_smtp_error_does_not_raise(monkeypatch):
    monkeypatch.setattr(email_notifier.database, "get_caregiver", lambda _: CG_EMAIL)
    with patch("smtplib.SMTP", side_effect=smtplib.SMTPException("down")):
        email_notifier._send(MEMBER, "IN", TIMESTAMP)


def test_missing_config_does_not_raise(monkeypatch):
    monkeypatch.setattr(email_notifier, "_CONFIG_PATH", "/nonexistent/config.json")
    email_notifier._send(MEMBER, "IN", TIMESTAMP)


def test_missing_caregiver_email_key_does_not_raise(monkeypatch):
    monkeypatch.setattr(email_notifier.database, "get_caregiver", lambda _: {})
    with smtp_server():
        email_notifier._send(MEMBER, "IN", TIMESTAMP)


# ── Threading behaviour ────────────────────────────────────────────────────────

def test_send_notification_spawns_daemon_thread(monkeypatch):
    """send_notification creates a daemon thread so it doesn't block app exit."""
    spawned = []
    original = threading.Thread

    def capture(**kwargs):
        t = original(**kwargs)
        spawned.append(t)
        return t

    monkeypatch.setattr(threading, "Thread", capture)
    monkeypatch.setattr(email_notifier.database, "get_caregiver", lambda _: CG_EMAIL)

    with smtp_server():
        email_notifier.send_notification(MEMBER, "IN", TIMESTAMP)

    assert len(spawned) == 1
    assert spawned[0].daemon is True
