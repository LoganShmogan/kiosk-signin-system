"""
Tests for the Flask web dashboard — auth, pages, CRUD, and exports.
"""
import re
import sqlite3
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "kiosk_signin"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import database as db_module
import dashboard.app as dashboard_app
from helpers import member as _member, staff_member as _staff, caregiver as _caregiver


def _rendered_form_fields(html: bytes) -> dict:
    """Extract {name: value} for every hidden/text input in a rendered <form>.

    Used to build POST bodies the way a real browser would: from whatever
    the GET form actually renders, rather than hand-assembling a payload
    that assumes fields exist. This is what catches bugs where a field is
    missing from the template but present in the test's own POST data.
    """
    fields = {}
    for tag in re.findall(r"<input\b[^>]*>", html.decode()):
        type_match = re.search(r'type="([^"]*)"', tag)
        input_type = type_match.group(1) if type_match else "text"
        if input_type in ("checkbox", "radio", "submit", "button"):
            continue
        name_match = re.search(r'name="([^"]*)"', tag)
        if not name_match:
            continue
        value_match = re.search(r'value="([^"]*)"', tag)
        fields[name_match.group(1)] = value_match.group(1) if value_match else ""
    return fields


@pytest.fixture
def db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(db_module, "DB_PATH", db_path)
    db_module.init_db()
    return db_module


@pytest.fixture
def client(db, monkeypatch):
    from dashboard.app import app, limiter, get_conn as _orig_get_conn
    monkeypatch.setattr("dashboard.app.DB_PATH", db_module.DB_PATH)
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    limiter.enabled = False
    with app.test_client() as c:
        yield c


@pytest.fixture
def auth_client(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["role"] = "admin"
        sess["name"] = "admin"
    return client


@pytest.fixture
def staff_client(client, db):
    user_id = db_module.create_dashboard_user("Jamie", "2468", "staff")
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["role"] = "staff"
        sess["name"] = "Jamie"
    return client


# ── Authentication ────────────────────────────────────────────────────────────

def test_index_redirects_to_login(client):
    resp = client.get("/")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_index_redirects_to_dashboard_when_logged_in(auth_client):
    resp = auth_client.get("/")
    assert resp.status_code == 302
    assert "/dashboard" in resp.headers["Location"]


def test_login_valid_credentials(client):
    resp = client.post("/login", data={"username": "admin", "password": "1234"})
    assert resp.status_code == 302
    assert "/dashboard" in resp.headers["Location"]


def test_login_invalid_credentials(client):
    resp = client.post("/login", data={"username": "admin", "password": "wrong"})
    assert resp.status_code == 200
    assert b"Invalid" in resp.data


def test_logout_clears_session(auth_client):
    resp = auth_client.get("/logout")
    assert resp.status_code == 302
    resp = auth_client.get("/dashboard")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_protected_pages_require_login(client):
    for url in ["/dashboard", "/logs", "/audit", "/people", "/exports",
                "/people/new", "/people/1", "/run-sheets", "/run-sheets/new"]:
        resp = client.get(url)
        assert resp.status_code == 302, f"{url} should redirect when not logged in"


def test_log_event_swallows_errors_instead_of_raising(db, monkeypatch):
    def _broken_conn():
        raise sqlite3.OperationalError("simulated failure")
    monkeypatch.setattr(dashboard_app, "get_conn", _broken_conn)
    dashboard_app.log_event("TEST_EVENT", "should not raise")


def test_resolve_secret_key_uses_env_var(monkeypatch):
    monkeypatch.setenv("DASHBOARD_SECRET_KEY", "my-fixed-key")
    assert dashboard_app._resolve_secret_key() == "my-fixed-key"


def test_resolve_secret_key_generates_random_when_unset(monkeypatch, capsys):
    monkeypatch.delenv("DASHBOARD_SECRET_KEY", raising=False)
    key1 = dashboard_app._resolve_secret_key()
    key2 = dashboard_app._resolve_secret_key()
    assert key1 != key2
    assert "WARNING" in capsys.readouterr().out


# ── Dashboard ─────────────────────────────────────────────────────────────────

def test_dashboard_page_loads(auth_client):
    resp = auth_client.get("/dashboard")
    assert resp.status_code == 200
    assert b"Kiosk Sign-In Dashboard" in resp.data


def _stat_value(html: bytes, label: str) -> int:
    m = re.search(
        r'<div class="value[^"]*">(\d+)</div>\s*<div class="label">' + re.escape(label),
        html.decode(),
    )
    assert m, f"Could not find stat tile for label {label!r}"
    return int(m.group(1))


def test_dashboard_total_members_count(auth_client, db):
    db.upsert_member(_member(first_name="Count", last_name="Me"))
    resp = auth_client.get("/dashboard")
    # Seed data already has >= 5 members; assert the tile reflects the true DB count.
    assert _stat_value(resp.data, "Total members") == len(db.search_members(""))


def test_dashboard_today_ins_counts_distinct_members_only(auth_client, db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")
    db.record_sign(mid, "OUT")
    db.record_sign(mid, "IN")  # same member signing in twice today
    resp = auth_client.get("/dashboard")
    assert _stat_value(resp.data, "Children signed in today") == 1


def test_dashboard_currently_here_reflects_open_sign_ins(auth_client, db):
    still_in = db.upsert_member(_member(first_name="Still", last_name="In"))
    signed_out = db.upsert_member(_member(first_name="Already", last_name="Out"))
    db.record_sign(still_in, "IN")
    db.record_sign(signed_out, "IN")
    db.record_sign(signed_out, "OUT")
    resp = auth_client.get("/dashboard")
    assert _stat_value(resp.data, "Currently here") == 1


def test_dashboard_currently_here_zero_when_all_signed_out(auth_client, db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")
    db.record_sign(mid, "OUT")
    resp = auth_client.get("/dashboard")
    assert _stat_value(resp.data, "Currently here") == 0


# ── Logs ──────────────────────────────────────────────────────────────────────

def test_logs_page_loads(auth_client):
    resp = auth_client.get("/logs")
    assert resp.status_code == 200
    assert b"Sign-In Logs" in resp.data


def test_logs_pairs_in_and_out_on_one_row(auth_client, db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")
    db.record_sign(mid, "OUT")
    resp = auth_client.get("/logs")
    assert resp.status_code == 200
    assert b"Jane" in resp.data
    assert resp.data.count(b"Jane") == 1


def test_logs_filter_still_signed_in(auth_client, db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")
    resp = auth_client.get("/logs?status=OPEN")
    assert resp.status_code == 200
    assert b"Jane" in resp.data
    assert b"SIGNED IN" in resp.data


def test_logs_filter_by_date_range_includes_within_range(auth_client, db):
    mid = db.upsert_member(_member())
    with db.get_conn() as conn:
        conn.execute("INSERT INTO sign_ins (member_id, direction, timestamp) VALUES (?, 'IN', ?)",
                     (mid, "2020-01-01 09:00:00"))
        conn.execute("INSERT INTO sign_ins (member_id, direction, timestamp) VALUES (?, 'IN', ?)",
                     (mid, "2025-06-15 09:00:00"))
    resp = auth_client.get("/logs?date_from=2025-06-01&date_to=2025-06-30")
    assert resp.status_code == 200
    assert resp.data.count(b"Jane") == 1


def test_logs_filter_by_date_range_excludes_outside_range(auth_client, db):
    mid = db.upsert_member(_member())
    with db.get_conn() as conn:
        conn.execute("INSERT INTO sign_ins (member_id, direction, timestamp) VALUES (?, 'IN', ?)",
                     (mid, "2020-01-01 09:00:00"))
    resp = auth_client.get("/logs?date_from=2025-01-01&date_to=2025-12-31")
    assert resp.status_code == 200
    assert b"Jane" not in resp.data


def test_logs_filter_excludes_signed_out(auth_client, db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")
    resp = auth_client.get("/logs?status=CLOSED")
    assert resp.status_code == 200
    assert b"Jane" not in resp.data


def test_logs_search_filters_by_name(auth_client, db):
    mid = db.upsert_member(_member())
    other = db.upsert_member(_member(first_name="Other", last_name="Person"))
    db.record_sign(mid, "IN")
    db.record_sign(other, "IN")
    resp = auth_client.get("/logs?search=Jane")
    assert resp.status_code == 200
    assert b"Jane" in resp.data
    assert b"Other" not in resp.data


def test_logs_search_matches_last_name(auth_client, db):
    mid = db.upsert_member(_member())
    other = db.upsert_member(_member(first_name="Other", last_name="Person"))
    db.record_sign(mid, "IN")
    db.record_sign(other, "IN")
    resp = auth_client.get("/logs?search=Smith")
    assert resp.status_code == 200
    assert b"Jane" in resp.data
    assert b"Other" not in resp.data


def test_logs_search_is_case_insensitive(auth_client, db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")
    resp = auth_client.get("/logs?search=jane")
    assert resp.status_code == 200
    assert b"Jane" in resp.data


def test_logs_search_no_match_shows_no_records(auth_client, db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")
    resp = auth_client.get("/logs?search=Nobody")
    assert resp.status_code == 200
    assert b"Jane" not in resp.data
    assert b"No records found." in resp.data


def test_logs_search_combines_with_status_filter(auth_client, db):
    mid = db.upsert_member(_member())
    other = db.upsert_member(_member(first_name="Other", last_name="Person"))
    db.record_sign(mid, "IN")
    db.record_sign(other, "IN")
    db.record_sign(other, "OUT")
    resp = auth_client.get("/logs?search=Other&status=CLOSED")
    assert resp.status_code == 200
    assert b"Other" in resp.data
    assert b"Jane" not in resp.data


def test_logs_shows_edit_links_for_in_and_out(auth_client, db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")
    db.record_sign(mid, "OUT")
    resp = auth_client.get("/logs")
    assert resp.data.count(b">Edit<") == 2
    assert b">Add<" not in resp.data


def test_logs_shows_add_link_for_open_visit(auth_client, db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")
    resp = auth_client.get("/logs")
    assert resp.data.count(b">Edit<") == 1
    assert resp.data.count(b">Add<") == 1


def test_logs_shows_add_link_for_stray_out(auth_client, db):
    mid = db.upsert_member(_member())
    with db.get_conn() as conn:
        conn.execute("INSERT INTO sign_ins (member_id, direction, timestamp) VALUES (?, 'OUT', ?)",
                     (mid, "2026-01-01 09:00:00"))
    resp = auth_client.get("/logs")
    assert resp.data.count(b">Edit<") == 1
    assert resp.data.count(b">Add<") == 1


# ── Edit sign-in/out time ──────────────────────────────────────────────

def test_sign_edit_form_loads(auth_client, db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")
    sign = db.get_today_signs()[0]
    resp = auth_client.get(f"/logs/sign/{sign['id']}/edit")
    assert resp.status_code == 200
    assert b"Jane" in resp.data


def test_sign_edit_unknown_id_redirects_with_flash(auth_client):
    resp = auth_client.get("/logs/sign/999999/edit", follow_redirects=True)
    assert resp.status_code == 200
    assert b"not found" in resp.data


def test_sign_edit_updates_timestamp(auth_client, db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")
    sign = db.get_today_signs()[0]
    resp = auth_client.post(
        f"/logs/sign/{sign['id']}/edit",
        data={"timestamp": "2026-03-01T09:30"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    updated = db.get_sign(sign["id"])
    assert updated["timestamp"] == "2026-03-01 09:30:00"


def test_sign_edit_rejects_invalid_timestamp(auth_client, db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")
    sign = db.get_today_signs()[0]
    original = sign["timestamp"]
    resp = auth_client.post(
        f"/logs/sign/{sign['id']}/edit",
        data={"timestamp": "not-a-date"},
    )
    assert resp.status_code == 200
    assert b"valid date" in resp.data
    assert db.get_sign(sign["id"])["timestamp"] == original


def test_sign_edit_logs_audit_event(auth_client, db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")
    sign = db.get_today_signs()[0]
    auth_client.post(
        f"/logs/sign/{sign['id']}/edit",
        data={"timestamp": "2026-03-01T09:30"},
    )
    resp = auth_client.get("/audit")
    assert b"SIGN_TIME_EDITED" in resp.data


def test_sign_edit_requires_admin(staff_client, db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")
    sign = db.get_today_signs()[0]
    resp = staff_client.get(f"/logs/sign/{sign['id']}/edit", follow_redirects=True)
    assert b"Admin access required" in resp.data


# ── Add missing sign-in/out time ───────────────────────────────────────

def _insert_sign(db, mid, direction, ts):
    with db.get_conn() as conn:
        return conn.execute(
            "INSERT INTO sign_ins (member_id, direction, timestamp) VALUES (?, ?, ?)",
            (mid, direction, ts),
        ).lastrowid


def _signs(db, mid):
    with db.get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM sign_ins WHERE member_id=? ORDER BY timestamp, id", (mid,)
        ).fetchall()]


def test_sign_add_form_loads(auth_client, db):
    mid = db.upsert_member(_member())
    in_id = _insert_sign(db, mid, "IN", "2026-03-01 08:30:00")
    resp = auth_client.get(f"/logs/sign/add?member_id={mid}&direction=OUT&pair_id={in_id}")
    assert resp.status_code == 200
    assert b"Jane" in resp.data
    # Defaults to just after the IN, never before it
    assert b'value="2026-03-01T08:31"' in resp.data
    assert b'min="2026-03-01T08:30"' in resp.data


def test_sign_add_missing_member_id_redirects_with_flash(auth_client):
    resp = auth_client.get("/logs/sign/add?direction=OUT", follow_redirects=True)
    assert resp.status_code == 200
    assert b"Invalid request" in resp.data


def test_sign_add_invalid_direction_redirects_with_flash(auth_client, db):
    mid = db.upsert_member(_member())
    resp = auth_client.get(f"/logs/sign/add?member_id={mid}&direction=SIDEWAYS", follow_redirects=True)
    assert resp.status_code == 200
    assert b"Invalid request" in resp.data


def test_sign_add_unknown_member_redirects_with_flash(auth_client):
    resp = auth_client.get("/logs/sign/add?member_id=999999&direction=OUT", follow_redirects=True)
    assert resp.status_code == 200
    assert b"not found" in resp.data


def test_sign_add_requires_pair_record(auth_client, db):
    mid = db.upsert_member(_member())
    resp = auth_client.get(f"/logs/sign/add?member_id={mid}&direction=OUT", follow_redirects=True)
    assert b"not found" in resp.data


def test_sign_add_rejects_pair_from_another_person(auth_client, db):
    mid = db.upsert_member(_member())
    other = db.upsert_member(_member(first_name="Other"))
    in_id = _insert_sign(db, other, "IN", "2026-03-01 08:30:00")
    auth_client.post(
        "/logs/sign/add",
        data={"member_id": mid, "direction": "OUT", "pair_id": in_id,
              "timestamp": "2026-03-01T17:00"},
    )
    assert _signs(db, mid) == []


def test_sign_add_creates_missing_out_for_open_visit(auth_client, db):
    mid = db.upsert_member(_member())
    in_id = _insert_sign(db, mid, "IN", "2026-03-01 08:30:00")
    resp = auth_client.post(
        "/logs/sign/add",
        data={"member_id": mid, "direction": "OUT", "pair_id": in_id,
              "timestamp": "2026-03-01T17:00"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    rows = [r for r in _signs(db, mid) if r["direction"] == "OUT"]
    assert len(rows) == 1
    assert rows[0]["timestamp"] == "2026-03-01 17:00:00"


def test_sign_add_creates_missing_in_for_stray_out(auth_client, db):
    mid = db.upsert_member(_member())
    out_id = _insert_sign(db, mid, "OUT", "2026-01-01 09:00:00")
    auth_client.post(
        "/logs/sign/add",
        data={"member_id": mid, "direction": "IN", "pair_id": out_id,
              "timestamp": "2026-01-01T08:30"},
        follow_redirects=True,
    )
    rows = [r for r in _signs(db, mid) if r["direction"] == "IN"]
    assert len(rows) == 1
    assert rows[0]["timestamp"] == "2026-01-01 08:30:00"


def test_sign_add_rejects_invalid_timestamp(auth_client, db):
    mid = db.upsert_member(_member())
    in_id = _insert_sign(db, mid, "IN", "2026-03-01 08:30:00")
    resp = auth_client.post(
        "/logs/sign/add",
        data={"member_id": mid, "direction": "OUT", "pair_id": in_id,
              "timestamp": "not-a-date"},
    )
    assert resp.status_code == 200
    assert b"valid date" in resp.data
    assert [r["direction"] for r in _signs(db, mid)] == ["IN"]


def test_sign_add_logs_audit_event(auth_client, db):
    mid = db.upsert_member(_member())
    in_id = _insert_sign(db, mid, "IN", "2026-03-01 08:30:00")
    auth_client.post(
        "/logs/sign/add",
        data={"member_id": mid, "direction": "OUT", "pair_id": in_id,
              "timestamp": "2026-03-01T17:00"},
    )
    resp = auth_client.get("/audit")
    assert b"SIGN_TIME_ADDED" in resp.data


# Regression: an added/edited time on the wrong side of its partner used to
# re-pair the records, splitting one visit into two rows on /logs.

def test_sign_add_rejects_out_before_its_in(auth_client, db):
    mid = db.upsert_member(_member())
    in_id = _insert_sign(db, mid, "IN", "2026-03-01 15:00:00")
    resp = auth_client.post(
        "/logs/sign/add",
        data={"member_id": mid, "direction": "OUT", "pair_id": in_id,
              "timestamp": "2026-03-01T09:00"},
    )
    assert b"stay part of this visit" in resp.data
    assert [r["direction"] for r in _signs(db, mid)] == ["IN"]


def test_sign_add_rejects_out_after_next_visit(auth_client, db):
    mid = db.upsert_member(_member())
    in_id = _insert_sign(db, mid, "IN", "2026-03-01 08:00:00")
    _insert_sign(db, mid, "IN", "2026-03-02 08:00:00")
    auth_client.post(
        "/logs/sign/add",
        data={"member_id": mid, "direction": "OUT", "pair_id": in_id,
              "timestamp": "2026-03-02T17:00"},
    )
    assert [r["direction"] for r in _signs(db, mid)] == ["IN", "IN"]


def test_sign_add_then_edit_keeps_single_visit(auth_client, db):
    mid = db.upsert_member(_member())
    in_id = _insert_sign(db, mid, "IN", "2026-03-01 08:30:00")
    auth_client.post(
        "/logs/sign/add",
        data={"member_id": mid, "direction": "OUT", "pair_id": in_id,
              "timestamp": "2026-03-01T17:00"},
    )
    out_id = _signs(db, mid)[1]["id"]
    auth_client.post(f"/logs/sign/{out_id}/edit", data={"timestamp": "2026-03-01T16:15"})
    resp = auth_client.get("/logs")
    assert resp.data.count(b"Jane") == 1
    assert b"2026-03-01 16:15:00" in resp.data
    assert len(_signs(db, mid)) == 2


def test_sign_edit_rejects_moving_out_before_in(auth_client, db):
    mid = db.upsert_member(_member())
    _insert_sign(db, mid, "IN", "2026-03-01 08:30:00")
    out_id = _insert_sign(db, mid, "OUT", "2026-03-01 15:00:00")
    resp = auth_client.post(f"/logs/sign/{out_id}/edit", data={"timestamp": "2026-03-01T08:00"})
    assert b"stay part of this visit" in resp.data
    assert db.get_sign(out_id)["timestamp"] == "2026-03-01 15:00:00"


def test_sign_edit_rejects_moving_latest_record_before_previous(auth_client, db):
    mid = db.upsert_member(_member())
    _insert_sign(db, mid, "IN", "2026-03-01 08:30:00")
    out_id = _insert_sign(db, mid, "OUT", "2026-03-01 15:00:00")
    # Latest record has no next neighbour, so only the "after" bound applies
    resp = auth_client.post(f"/logs/sign/{out_id}/edit", data={"timestamp": "2026-03-01T08:00"})
    assert b"Time must be after 2026-03-01 08:30:00 to stay part of this visit" in resp.data
    assert db.get_sign(out_id)["timestamp"] == "2026-03-01 15:00:00"


def test_sign_edit_rejects_moving_first_record_after_next(auth_client, db):
    mid = db.upsert_member(_member())
    in_id = _insert_sign(db, mid, "IN", "2026-03-01 08:30:00")
    _insert_sign(db, mid, "OUT", "2026-03-01 15:00:00")
    # First record has no previous neighbour, so only the "before" bound applies
    resp = auth_client.post(f"/logs/sign/{in_id}/edit", data={"timestamp": "2026-03-01T16:00"})
    assert b"Time must be before 2026-03-01 15:00:00 to stay part of this visit" in resp.data
    assert db.get_sign(in_id)["timestamp"] == "2026-03-01 08:30:00"


def test_logs_date_filter_keeps_visit_paired(auth_client, db):
    mid = db.upsert_member(_member())
    _insert_sign(db, mid, "IN", "2026-03-01 23:30:00")
    _insert_sign(db, mid, "OUT", "2026-03-02 00:30:00")
    resp = auth_client.get("/logs?date_from=2026-03-02")
    # Visit is dated by its IN, so it's excluded rather than shown as a stray OUT
    assert b"Jane" not in resp.data
    resp = auth_client.get("/logs?date_from=2026-03-01&date_to=2026-03-01")
    assert resp.data.count(b"Jane") == 1
    assert b">Add<" not in resp.data


def test_currently_signed_in_uses_time_order_not_insert_order(db):
    from datetime import datetime
    mid = db.upsert_member(_member())
    today = datetime.now().strftime("%Y-%m-%d")
    _insert_sign(db, mid, "OUT", f"{today} 00:02:00")
    # Back-dated IN added afterwards from the dashboard has a higher id
    _insert_sign(db, mid, "IN", f"{today} 00:01:00")
    assert db.get_currently_signed_in() == []
    assert db.get_allowed_direction(mid) == "IN"


# ── Delete sign-in/out records ───────────────────────────────────────────────

def test_logs_shows_delete_button_per_visit(auth_client, db):
    mid = db.upsert_member(_member())
    _insert_sign(db, mid, "IN", "2026-03-01 08:30:00")
    _insert_sign(db, mid, "OUT", "2026-03-01 15:00:00")
    resp = auth_client.get("/logs")
    assert resp.data.count(b">Delete<") == 1


def test_sign_delete_removes_whole_visit(auth_client, db):
    mid = db.upsert_member(_member())
    in_id = _insert_sign(db, mid, "IN", "2026-03-01 08:30:00")
    out_id = _insert_sign(db, mid, "OUT", "2026-03-01 15:00:00")
    resp = auth_client.post("/logs/sign/delete", data={"sign_id": [in_id, out_id]},
                            follow_redirects=True)
    assert b"Visit deleted" in resp.data
    assert _signs(db, mid) == []
    assert b"SIGN_DELETED" in auth_client.get("/audit").data


def test_sign_delete_single_record(auth_client, db):
    mid = db.upsert_member(_member())
    _insert_sign(db, mid, "IN", "2026-03-01 08:30:00")
    out_id = _insert_sign(db, mid, "OUT", "2026-03-01 15:00:00")
    resp = auth_client.post("/logs/sign/delete", data={"sign_id": out_id},
                            follow_redirects=True)
    assert b"Sign-in record deleted" in resp.data
    assert [r["direction"] for r in _signs(db, mid)] == ["IN"]


def test_sign_delete_works_for_staff(auth_client, db):
    sid = db.upsert_member(_staff())
    in_id = _insert_sign(db, sid, "IN", "2026-03-01 08:30:00")
    auth_client.post("/logs/sign/delete", data={"sign_id": in_id})
    assert _signs(db, sid) == []


def test_sign_delete_unknown_id_flashes(auth_client):
    resp = auth_client.post("/logs/sign/delete", data={"sign_id": 999999},
                            follow_redirects=True)
    assert b"not found" in resp.data


def test_sign_delete_requires_admin(staff_client, db):
    mid = db.upsert_member(_member())
    in_id = _insert_sign(db, mid, "IN", "2026-03-01 08:30:00")
    resp = staff_client.post("/logs/sign/delete", data={"sign_id": in_id},
                             follow_redirects=True)
    assert b"Admin access required" in resp.data
    assert len(_signs(db, mid)) == 1


def test_sign_edit_page_has_delete_button(auth_client, db):
    mid = db.upsert_member(_member())
    in_id = _insert_sign(db, mid, "IN", "2026-03-01 08:30:00")
    resp = auth_client.get(f"/logs/sign/{in_id}/edit")
    assert b"Delete this sign-in" in resp.data


def test_sign_add_requires_admin(staff_client, db):
    mid = db.upsert_member(_member())
    resp = staff_client.get(f"/logs/sign/add?member_id={mid}&direction=OUT", follow_redirects=True)
    assert b"Admin access required" in resp.data


# ── Staff status view ──────────────────────────────────────────────────

def test_status_page_loads_for_staff(staff_client, db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")
    resp = staff_client.get("/status")
    assert resp.status_code == 200
    assert b"Who's Here" in resp.data
    assert b"Jane" in resp.data


def test_status_page_loads_for_admin(auth_client):
    resp = auth_client.get("/status")
    assert resp.status_code == 200


def test_status_page_requires_login(client):
    resp = client.get("/status", follow_redirects=True)
    assert b"username" in resp.data.lower() or b"login" in resp.data.lower()


def test_status_page_has_no_admin_only_links(staff_client):
    resp = staff_client.get("/status")
    assert b"Manage" not in resp.data
    assert b"Export" not in resp.data


def test_nav_shows_status_link_for_staff(staff_client):
    resp = staff_client.get("/signin")
    assert b"Who's Here" in resp.data


def test_nav_hides_status_link_for_admin(auth_client):
    resp = auth_client.get("/dashboard")
    # Admin has its own full Dashboard link, not the staff-only status page
    assert b'href="/status"' not in resp.data


# ── _pair_sign_in_visits ──────────────────────────────────────────────────────
# Direct unit tests for the IN/OUT pairing logic behind /logs. Input rows must
# already be ordered by member_id then timestamp, matching the SQL query.

_next_sign_id = [0]


def _sign_row(mid, first, last, direction, ts, notes=None):
    _next_sign_id[0] += 1
    return {"id": _next_sign_id[0], "member_id": mid, "first_name": first, "last_name": last,
            "direction": direction, "timestamp": ts, "notes": notes}


def test_pair_visits_empty_list():
    assert dashboard_app._pair_sign_in_visits([]) == []


def test_pair_visits_single_in_out_pair():
    rows = [
        _sign_row(1, "A", "B", "IN",  "2026-01-01 08:00:00"),
        _sign_row(1, "A", "B", "OUT", "2026-01-01 15:00:00"),
    ]
    visits = dashboard_app._pair_sign_in_visits(rows)
    assert len(visits) == 1
    assert visits[0]["in_time"] == "2026-01-01 08:00:00"
    assert visits[0]["out_time"] == "2026-01-01 15:00:00"
    assert visits[0]["in_id"] == rows[0]["id"]
    assert visits[0]["out_id"] == rows[1]["id"]


def test_pair_visits_dangling_in_has_no_out_time():
    rows = [_sign_row(1, "A", "B", "IN", "2026-01-01 08:00:00")]
    visits = dashboard_app._pair_sign_in_visits(rows)
    assert len(visits) == 1
    assert visits[0]["in_time"] == "2026-01-01 08:00:00"
    assert visits[0]["out_time"] is None
    assert visits[0]["in_id"] == rows[0]["id"]
    assert visits[0]["out_id"] is None


def test_pair_visits_stray_out_has_no_in_time():
    rows = [_sign_row(1, "A", "B", "OUT", "2026-01-01 08:00:00")]
    visits = dashboard_app._pair_sign_in_visits(rows)
    assert len(visits) == 1
    assert visits[0]["in_time"] is None
    assert visits[0]["out_time"] == "2026-01-01 08:00:00"
    assert visits[0]["in_id"] is None
    assert visits[0]["out_id"] == rows[0]["id"]


def test_pair_visits_multiple_visits_same_member_all_kept():
    rows = [
        _sign_row(1, "A", "B", "IN",  "2026-01-01 08:00:00"),
        _sign_row(1, "A", "B", "OUT", "2026-01-01 12:00:00"),
        _sign_row(1, "A", "B", "IN",  "2026-01-01 13:00:00"),
        _sign_row(1, "A", "B", "OUT", "2026-01-01 17:00:00"),
    ]
    visits = dashboard_app._pair_sign_in_visits(rows)
    assert len(visits) == 2


def test_pair_visits_second_in_while_open_closes_previous_with_no_out():
    rows = [
        _sign_row(1, "A", "B", "IN", "2026-01-01 08:00:00"),
        _sign_row(1, "A", "B", "IN", "2026-01-01 09:00:00"),
    ]
    visits = dashboard_app._pair_sign_in_visits(rows)
    assert len(visits) == 2
    closed, still_open = sorted(visits, key=lambda v: v["in_time"])
    assert closed["out_time"] is None
    assert still_open["out_time"] is None
    assert closed["in_time"] == "2026-01-01 08:00:00"
    assert still_open["in_time"] == "2026-01-01 09:00:00"


def test_pair_visits_separates_multiple_members():
    rows = [
        _sign_row(1, "A", "One", "IN",  "2026-01-01 08:00:00"),
        _sign_row(1, "A", "One", "OUT", "2026-01-01 12:00:00"),
        _sign_row(2, "B", "Two", "IN",  "2026-01-01 08:30:00"),
    ]
    visits = dashboard_app._pair_sign_in_visits(rows)
    assert len(visits) == 2
    assert {v["member_id"] for v in visits} == {1, 2}


def test_pair_visits_sorted_most_recent_first():
    rows = [
        _sign_row(1, "A", "One", "IN", "2026-01-01 08:00:00"),
        _sign_row(2, "B", "Two", "IN", "2026-01-01 10:00:00"),
    ]
    visits = dashboard_app._pair_sign_in_visits(rows)
    assert visits[0]["member_id"] == 2
    assert visits[1]["member_id"] == 1


# ── Audit ─────────────────────────────────────────────────────────────────────

def test_audit_page_loads(auth_client):
    resp = auth_client.get("/audit")
    assert resp.status_code == 200
    assert b"Audit" in resp.data


# ── People list ───────────────────────────────────────────────────────────────

def test_people_page_shows_members(auth_client, db):
    db.upsert_member(_member(first_name="Alice", last_name="Wonder"))
    resp = auth_client.get("/people?type=member")
    assert resp.status_code == 200
    assert b"Alice" in resp.data
    assert b"Wonder" in resp.data


def test_people_page_shows_staff(auth_client, db):
    db.upsert_member(_staff(first_name="Bob", last_name="Builder"))
    resp = auth_client.get("/people?type=staff")
    assert resp.status_code == 200
    assert b"Bob" in resp.data


def test_people_search_filters_by_name(auth_client, db):
    db.upsert_member(_member(first_name="Unique", last_name="Findme"))
    db.upsert_member(_member(first_name="Other", last_name="Person"))
    resp = auth_client.get("/people?type=member&search=Unique")
    assert resp.status_code == 200
    assert b"Unique" in resp.data
    assert b"Other" not in resp.data


def test_people_page_has_add_button(auth_client):
    resp = auth_client.get("/people?type=member")
    assert b"+ Add Member" in resp.data


def test_people_page_has_edit_links(auth_client, db):
    mid = db.upsert_member(_member())
    resp = auth_client.get("/people?type=member")
    assert f"/people/{mid}".encode() in resp.data


def test_people_member_shows_caregivers(auth_client, db):
    mid = db.upsert_member(_member())
    db.upsert_caregiver(_caregiver(mid, full_name="Caregiver Joe"))
    resp = auth_client.get("/people?type=member")
    assert b"Caregiver Joe" in resp.data


def test_people_staff_shows_role(auth_client, db):
    db.upsert_member(_staff(school="Lead Coordinator"))
    resp = auth_client.get("/people?type=staff")
    assert b"Lead Coordinator" in resp.data


# ── Create (new person) ──────────────────────────────────────────────────────

def test_new_member_form_loads(auth_client):
    resp = auth_client.get("/people/new?type=member")
    assert resp.status_code == 200
    assert b"Child Details" in resp.data
    assert b"Caregiver" in resp.data


def test_new_staff_form_loads(auth_client):
    resp = auth_client.get("/people/new?type=staff")
    assert resp.status_code == 200
    assert b"Staff Details" in resp.data
    assert b"Caregiver" not in resp.data


def test_create_member(auth_client, db):
    resp = auth_client.post("/people/new?type=member", data={
        "first_name": "New", "last_name": "Child",
        "date_of_birth": "2015-03-01", "school": "Test School",
        "pin": "", "person_type": "member",
        "cg_full_name": "Parent One", "cg_phone": "021111",
        "cg_email": "p@test.com", "cg_relationship": "Mother",
        "cg_street_address": "", "cg_suburb": "", "cg_city": "",
        "cg_emergency_contact_name": "", "cg_emergency_contact_phone": "",
        "cg_notify_on": "BOTH",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b"created" in resp.data
    results = db.search_members("New Child", "member")
    assert len(results) == 1
    cg = db.get_caregiver(results[0]["id"])
    assert cg["full_name"] == "Parent One"


def test_create_staff(auth_client, db):
    resp = auth_client.post("/people/new?type=staff", data={
        "first_name": "New", "last_name": "Staff",
        "school": "Manager", "pin": "1234",
        "person_type": "staff",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b"created" in resp.data
    results = db.search_members("New Staff", "staff")
    assert len(results) == 1
    assert results[0]["school"] == "Manager"


def test_create_member_with_day_pickers(auth_client, db):
    resp = auth_client.post("/people/new?type=member", data={
        "first_name": "Day", "last_name": "Picker",
        "date_of_birth": "", "school": "", "pin": "",
        "person_type": "member",
        "mornings_days": ["Mon", "Wed", "Fri"],
        "afternoons_days": ["Tue", "Thu"],
        "needs_pickup": "1",
        "activity": "Soccer", "activity_time": "3pm",
        "transport_required": "1",
        "activity_days": ["Mon"],
        "activity_address": "123 Field Rd",
        "cg_full_name": "", "cg_phone": "", "cg_email": "",
        "cg_relationship": "", "cg_street_address": "",
        "cg_suburb": "", "cg_city": "",
        "cg_emergency_contact_name": "", "cg_emergency_contact_phone": "",
        "cg_notify_on": "BOTH",
    }, follow_redirects=True)
    assert resp.status_code == 200
    results = db.search_members("Day Picker", "member")
    m = results[0]
    assert m["mornings_days"] == "Mon,Wed,Fri"
    assert m["afternoons_days"] == "Tue,Thu"
    assert m["needs_pickup"] == 1
    assert m["activity"] == "Soccer"
    assert m["transport_required"] == 1
    assert m["activity_days"] == "Mon"


# ── person_type regression (staff form was silently saved as "member") ──────
#
# Bug: the shared person_form.html template had no hidden `person_type`
# field, so a real browser submission always fell back to app.py's
# `request.form.get("person_type", "member")` default -- new "staff" records
# were saved as members, and the post-create redirect then rendered the
# member edit form instead of the staff one. Tests further up (e.g.
# test_create_staff) didn't catch this because they hand-assembled the POST
# body with `"person_type": "staff"` baked in, which masked the missing
# field. The tests below instead derive the POST body from the GET form's
# own rendered HTML, the way a browser actually would.

def test_new_staff_form_includes_person_type_hidden_field(auth_client):
    resp = auth_client.get("/people/new?type=staff")
    assert b'name="person_type" value="staff"' in resp.data


def test_new_member_form_includes_person_type_hidden_field(auth_client):
    resp = auth_client.get("/people/new?type=member")
    assert b'name="person_type" value="member"' in resp.data


def test_create_staff_via_rendered_form_fields_only(auth_client, db):
    get_resp = auth_client.get("/people/new?type=staff")
    fields = _rendered_form_fields(get_resp.data)
    assert fields.get("person_type") == "staff"
    fields["first_name"] = "Browser"
    fields["last_name"] = "Submitted"

    resp = auth_client.post("/people/new?type=staff", data=fields, follow_redirects=True)

    assert resp.status_code == 200
    assert b"Staff Details" in resp.data
    assert b"Caregiver" not in resp.data
    results = db.search_members("Browser Submitted", "staff")
    assert len(results) == 1
    assert results[0]["person_type"] == "staff"


def test_create_member_via_rendered_form_fields_only(auth_client, db):
    get_resp = auth_client.get("/people/new?type=member")
    fields = _rendered_form_fields(get_resp.data)
    assert fields.get("person_type") == "member"
    fields["first_name"] = "Browser"
    fields["last_name"] = "Kid"

    resp = auth_client.post("/people/new?type=member", data=fields, follow_redirects=True)

    assert resp.status_code == 200
    assert b"Child Details" in resp.data
    results = db.search_members("Browser Kid", "member")
    assert len(results) == 1
    assert results[0]["person_type"] == "member"


def test_create_staff_redirects_to_staff_edit_view_not_member(auth_client):
    resp = auth_client.post("/people/new?type=staff", data={
        "first_name": "New", "last_name": "Staffer",
        "school": "Coordinator", "pin": "", "person_type": "staff",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b"Edit Staff Member" in resp.data
    assert b"Staff Details" in resp.data
    assert b"Child Details" not in resp.data
    assert b"Caregiver" not in resp.data


def test_created_staff_does_not_appear_in_member_list(auth_client, db):
    db.upsert_member(_staff(first_name="Only", last_name="Staff"))
    resp = auth_client.get("/people?type=member")
    assert resp.status_code == 200
    assert b"Only" not in resp.data


def test_created_member_does_not_appear_in_staff_list(auth_client, db):
    db.upsert_member(_member(first_name="Only", last_name="Kid"))
    resp = auth_client.get("/people?type=staff")
    assert resp.status_code == 200
    assert b"Only" not in resp.data


def test_create_validates_required_fields(auth_client):
    resp = auth_client.post("/people/new?type=staff", data={
        "first_name": "", "last_name": "",
        "person_type": "staff",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b"required" in resp.data


# ── Edit (update person) ─────────────────────────────────────────────────────

def test_edit_member_form_loads(auth_client, db):
    mid = db.upsert_member(_member(first_name="Edit", last_name="Me"))
    resp = auth_client.get(f"/people/{mid}")
    assert resp.status_code == 200
    assert b"Edit" in resp.data
    assert b"Me" in resp.data


def test_edit_member_form_shows_caregiver(auth_client, db):
    mid = db.upsert_member(_member())
    db.upsert_caregiver(_caregiver(mid, full_name="Loaded Caregiver"))
    resp = auth_client.get(f"/people/{mid}")
    assert b"Loaded Caregiver" in resp.data


def test_edit_staff_form_loads(auth_client, db):
    sid = db.upsert_member(_staff(first_name="Staff", last_name="Edit"))
    resp = auth_client.get(f"/people/{sid}")
    assert resp.status_code == 200
    assert b"Staff Details" in resp.data
    assert b"Staff" in resp.data


def test_update_member(auth_client, db):
    mid = db.upsert_member(_member(first_name="Old", last_name="Name"))
    resp = auth_client.post(f"/people/{mid}", data={
        "first_name": "Updated", "last_name": "Name",
        "date_of_birth": "2015-01-01", "school": "New School",
        "pin": "5555", "person_type": "member",
        "cg_full_name": "New Parent", "cg_phone": "022222",
        "cg_email": "new@test.com", "cg_relationship": "Father",
        "cg_street_address": "", "cg_suburb": "", "cg_city": "",
        "cg_emergency_contact_name": "", "cg_emergency_contact_phone": "",
        "cg_notify_on": "IN",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b"Changes saved" in resp.data
    m = db.get_member(mid)
    assert m["first_name"] == "Updated"
    assert m["school"] == "New School"
    cg = db.get_caregiver(mid)
    assert cg["full_name"] == "New Parent"


def test_update_staff(auth_client, db):
    sid = db.upsert_member(_staff(first_name="Old", last_name="Staff"))
    resp = auth_client.post(f"/people/{sid}", data={
        "first_name": "Updated", "last_name": "Staff",
        "school": "Director", "pin": "9999",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b"Changes saved" in resp.data
    m = db.get_member(sid)
    assert m["first_name"] == "Updated"
    assert m["school"] == "Director"


def test_update_validates_required_fields(auth_client, db):
    mid = db.upsert_member(_member())
    resp = auth_client.post(f"/people/{mid}", data={
        "first_name": "", "last_name": "",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b"required" in resp.data


def test_edit_nonexistent_person_redirects(auth_client):
    resp = auth_client.get("/people/99999")
    assert resp.status_code == 302


# ── Delete ────────────────────────────────────────────────────────────────────

def test_delete_member(auth_client, db):
    mid = db.upsert_member(_member(first_name="Delete", last_name="Me"))
    resp = auth_client.post(f"/people/{mid}/delete", follow_redirects=True)
    assert resp.status_code == 200
    assert b"has been deleted" in resp.data
    assert db.get_member(mid) is None


def test_delete_staff(auth_client, db):
    sid = db.upsert_member(_staff(first_name="Delete", last_name="Staff"))
    resp = auth_client.post(f"/people/{sid}/delete", follow_redirects=True)
    assert resp.status_code == 200
    assert b"has been deleted" in resp.data
    assert db.get_member(sid) is None


def test_delete_nonexistent_person_redirects(auth_client):
    resp = auth_client.post("/people/99999/delete", follow_redirects=True)
    assert resp.status_code == 200
    assert b"not found" in resp.data


# ── Alerts ────────────────────────────────────────────────────────────────────

def test_alerts_page_loads(auth_client):
    resp = auth_client.get("/alerts")
    assert resp.status_code == 200


def test_create_alert_scope_all(auth_client, db):
    resp = auth_client.post("/alerts", data={
        "scope": "all", "message": "Centre closed tomorrow", "expiry_unit": "none",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b"Alert created" in resp.data
    alerts = db.get_alerts()
    assert any(a["message"] == "Centre closed tomorrow" and a["scope"] == "all" for a in alerts)


def test_create_alert_scope_member(auth_client, db):
    mid = db.upsert_member(_member())
    resp = auth_client.post("/alerts", data={
        "scope": "member", "member_id": str(mid),
        "message": "Reminder", "expiry_unit": "none",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b"Alert created" in resp.data
    alerts = db.get_alerts()
    assert any(a["scope"] == "member" and a["target_id"] == mid for a in alerts)


def test_create_alert_scope_member_without_selection_flashes_error(auth_client):
    resp = auth_client.post("/alerts", data={
        "scope": "member", "message": "Reminder", "expiry_unit": "none",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b"Select a person" in resp.data


def test_create_alert_scope_run(auth_client, db):
    mid = db.upsert_member(_member())
    run_id = db.upsert_run("Test Run", [mid])
    resp = auth_client.post("/alerts", data={
        "scope": "run", "run_id": str(run_id),
        "message": "Run alert", "expiry_unit": "none",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b"Alert created" in resp.data
    alerts = db.get_alerts()
    assert any(a["scope"] == "run" and a["target_id"] == run_id for a in alerts)


def test_create_alert_scope_run_without_selection_flashes_error(auth_client):
    resp = auth_client.post("/alerts", data={
        "scope": "run", "message": "Run alert", "expiry_unit": "none",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b"Select a run sheet" in resp.data


def test_create_alert_invalid_scope_flashes_error(auth_client):
    resp = auth_client.post("/alerts", data={
        "scope": "bogus", "message": "Bad scope", "expiry_unit": "none",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b"Invalid alert scope" in resp.data


def test_create_alert_empty_message_flashes_error(auth_client):
    resp = auth_client.post("/alerts", data={
        "scope": "all", "message": "", "expiry_unit": "none",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b"Alert message cannot be empty" in resp.data


def test_create_alert_with_expiry_duration(auth_client, db):
    resp = auth_client.post("/alerts", data={
        "scope": "all", "message": "Expires in a day",
        "expiry_unit": "days", "expiry_amount": "1",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b"Alert created" in resp.data
    alert = next(a for a in db.get_alerts() if a["message"] == "Expires in a day")
    assert alert["expires_at"] is not None


def test_create_alert_invalid_expiry_amount_flashes_error(auth_client):
    resp = auth_client.post("/alerts", data={
        "scope": "all", "message": "Bad duration",
        "expiry_unit": "days", "expiry_amount": "0",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b"Enter a valid duration" in resp.data


def test_alerts_page_shows_target_name_for_all_scope(auth_client, db):
    db.create_alert("all", None, "Everyone message")
    resp = auth_client.get("/alerts")
    assert b"All Members" in resp.data


def test_alerts_page_shows_target_name_for_member_scope(auth_client, db):
    mid = db.upsert_member(_member(first_name="Named", last_name="Person"))
    db.create_alert("member", mid, "Just for them")
    resp = auth_client.get("/alerts")
    assert b"Named Person" in resp.data


def test_alerts_page_shows_deleted_person_placeholder(auth_client, db):
    mid = db.upsert_member(_member())
    db.create_alert("member", mid, "For a soon-to-be-deleted person")
    db.delete_member(mid)
    resp = auth_client.get("/alerts")
    assert b"(deleted person)" in resp.data


def test_alerts_page_shows_deleted_run_placeholder(auth_client, db):
    mid = db.upsert_member(_member())
    run_id = db.upsert_run("Soon Deleted", [mid])
    db.create_alert("run", run_id, "For a soon-to-be-deleted run")
    db.delete_run(run_id)
    resp = auth_client.get("/alerts")
    assert b"(deleted run)" in resp.data


def test_alert_delete(auth_client, db):
    alert_id = db.create_alert("all", None, "To be deleted via dashboard")
    resp = auth_client.post(f"/alerts/{alert_id}/delete", follow_redirects=True)
    assert resp.status_code == 200
    assert b"Alert deleted" in resp.data
    assert not any(a["id"] == alert_id for a in db.get_alerts())


# ── Exports page ──────────────────────────────────────────────────────────────
#
# The old "Member Signing Sheets" bulk card (and its /export/members route)
# was removed in favour of "Export a Person's Sign-ins", which already lets
# an admin pick any member individually. The Staff Signing Sheets card was
# revamped to cover both its old bulk mode ("All Staff" + a required date
# range) and a per-person mode (pick one staff member, dates optional,
# defaulting to their full history) via the same /export/staff route.

def test_exports_page_loads(auth_client):
    resp = auth_client.get("/exports")
    assert resp.status_code == 200
    assert b"Member Signing Sheets" not in resp.data
    assert b"Staff Signing Sheets" in resp.data
    assert b"Export a Person's Sign-ins" in resp.data


def test_exports_page_has_no_bulk_member_route_reference(auth_client):
    resp = auth_client.get("/exports")
    assert b'action="/export/members"' not in resp.data


def test_exports_page_staff_dropdown_has_all_staff_option(auth_client, db):
    db.upsert_member(_staff(first_name="Sam", last_name="Taylor"))
    resp = auth_client.get("/exports")
    assert b"All Staff" in resp.data
    assert b"Sam Taylor" in resp.data


def test_export_members_route_removed(auth_client):
    resp = auth_client.get("/export/members?date_from=2000-01-01&date_to=2000-01-02")
    assert resp.status_code == 404


def test_export_staff_returns_xlsx(auth_client, db):
    sid = db.upsert_member(_staff())
    db.record_sign(sid, "IN")
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    resp = auth_client.get(f"/export/staff?date_from={today}&date_to={today}")
    assert resp.status_code == 200
    assert resp.content_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert b"PK" == resp.data[:2]


def test_export_staff_missing_params(auth_client):
    resp = auth_client.get("/export/staff")
    assert resp.status_code == 400


def test_export_staff_empty_range(auth_client):
    resp = auth_client.get("/export/staff?date_from=2000-01-01&date_to=2000-01-02")
    assert resp.status_code == 200
    assert b"PK" == resp.data[:2]


def test_export_staff_specific_person_full_history(auth_client, db):
    sid = db.upsert_member(_staff(first_name="One", last_name="Staffer"))
    db.record_sign(sid, "IN")
    db.record_sign(sid, "OUT")
    resp = auth_client.get(f"/export/staff?person_id={sid}")
    assert resp.status_code == 200
    assert resp.content_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert b"PK" == resp.data[:2]
    assert "One_Staffer" in resp.headers["Content-Disposition"]


def test_export_staff_specific_person_with_date_range(auth_client, db):
    sid = db.upsert_member(_staff())
    db.record_sign(sid, "IN")
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    resp = auth_client.get(f"/export/staff?person_id={sid}&date_from={today}&date_to={today}")
    assert resp.status_code == 200
    assert b"PK" == resp.data[:2]


def test_export_staff_specific_person_no_records_flashes_error(auth_client, db):
    sid = db.upsert_member(_staff(first_name="No", last_name="Records"))
    resp = auth_client.get(f"/export/staff?person_id={sid}", follow_redirects=True)
    assert resp.status_code == 200
    assert b"No sign-in records found" in resp.data


def test_export_staff_rejects_member_id(auth_client, db):
    mid = db.upsert_member(_member(first_name="Not", last_name="Staff"))
    resp = auth_client.get(f"/export/staff?person_id={mid}", follow_redirects=True)
    assert resp.status_code == 200
    assert b"Staff member not found" in resp.data


def test_export_staff_rejects_unknown_person_id(auth_client):
    resp = auth_client.get("/export/staff?person_id=999999", follow_redirects=True)
    assert resp.status_code == 200
    assert b"Staff member not found" in resp.data


# ── Export a Person's Sign-ins (/export/person) ──────────────────────────────

def test_export_person_no_person_id_flashes_error(auth_client):
    resp = auth_client.get("/export/person", follow_redirects=True)
    assert resp.status_code == 200
    assert b"Select a person to export" in resp.data


def test_export_person_unknown_id_flashes_error(auth_client):
    resp = auth_client.get("/export/person?person_id=999999", follow_redirects=True)
    assert resp.status_code == 200
    assert b"Person not found" in resp.data


def test_export_person_member_full_history_returns_xlsx(auth_client, db):
    mid = db.upsert_member(_member(first_name="Full", last_name="History"))
    db.record_sign(mid, "IN")
    db.record_sign(mid, "OUT")
    resp = auth_client.get(f"/export/person?person_id={mid}")
    assert resp.status_code == 200
    assert resp.content_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert b"PK" == resp.data[:2]
    assert "Full_History" in resp.headers["Content-Disposition"]


def test_export_person_staff_returns_xlsx(auth_client, db):
    sid = db.upsert_member(_staff(first_name="Staff", last_name="Exported"))
    db.record_sign(sid, "IN")
    db.record_sign(sid, "OUT")
    resp = auth_client.get(f"/export/person?person_id={sid}")
    assert resp.status_code == 200
    assert b"PK" == resp.data[:2]


def test_export_person_with_date_range(auth_client, db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    resp = auth_client.get(f"/export/person?person_id={mid}&date_from={today}&date_to={today}")
    assert resp.status_code == 200
    assert b"PK" == resp.data[:2]


def test_export_person_no_records_flashes_error(auth_client, db):
    mid = db.upsert_member(_member(first_name="No", last_name="Records"))
    resp = auth_client.get(f"/export/person?person_id={mid}", follow_redirects=True)
    assert resp.status_code == 200
    assert b"No sign-in records found" in resp.data


# ── Export format options (xlsx / pdf / csv) ─────────────────────────────────

def test_export_person_pdf_format(auth_client, db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")
    db.record_sign(mid, "OUT")
    resp = auth_client.get(f"/export/person?person_id={mid}&fmt=pdf")
    assert resp.status_code == 200
    assert resp.content_type == "application/pdf"
    assert resp.data[:4] == b"%PDF"


def test_export_person_csv_format(auth_client, db):
    mid = db.upsert_member(_member(first_name="Csv", last_name="Export"))
    db.record_sign(mid, "IN")
    db.record_sign(mid, "OUT")
    resp = auth_client.get(f"/export/person?person_id={mid}&fmt=csv")
    assert resp.status_code == 200
    assert resp.content_type.startswith("text/csv")
    assert b"Csv Export" in resp.data


def test_export_person_unknown_format_defaults_to_xlsx(auth_client, db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")
    db.record_sign(mid, "OUT")
    resp = auth_client.get(f"/export/person?person_id={mid}&fmt=bogus")
    assert resp.status_code == 200
    assert b"PK" == resp.data[:2]


def test_export_staff_pdf_format(auth_client, db):
    sid = db.upsert_member(_staff())
    db.record_sign(sid, "IN")
    db.record_sign(sid, "OUT")
    resp = auth_client.get(f"/export/staff?person_id={sid}&fmt=pdf")
    assert resp.status_code == 200
    assert resp.data[:4] == b"%PDF"


def test_export_staff_csv_format(auth_client, db):
    sid = db.upsert_member(_staff())
    db.record_sign(sid, "IN")
    db.record_sign(sid, "OUT")
    resp = auth_client.get(f"/export/staff?person_id={sid}&fmt=csv")
    assert resp.status_code == 200
    assert resp.content_type.startswith("text/csv")


def test_export_staff_bulk_pdf_format(auth_client, db):
    sid = db.upsert_member(_staff())
    db.record_sign(sid, "IN")
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    resp = auth_client.get(f"/export/staff?date_from={today}&date_to={today}&fmt=pdf")
    assert resp.status_code == 200
    assert resp.data[:4] == b"%PDF"


def test_export_staff_bulk_csv_format(auth_client, db):
    sid = db.upsert_member(_staff())
    db.record_sign(sid, "IN")
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    resp = auth_client.get(f"/export/staff?date_from={today}&date_to={today}&fmt=csv")
    assert resp.status_code == 200
    assert resp.content_type.startswith("text/csv")


def test_export_staff_bulk_unknown_format_defaults_to_xlsx(auth_client, db):
    sid = db.upsert_member(_staff())
    db.record_sign(sid, "IN")
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    resp = auth_client.get(f"/export/staff?date_from={today}&date_to={today}&fmt=bogus")
    assert resp.status_code == 200
    assert b"PK" == resp.data[:2]


# ── Last signature ─────────────────────────────────────────────────────────────

def test_person_signature_route_requires_login(client, db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN", signature=b"[(0, 0, 10, 10)]")
    resp = client.get(f"/people/{mid}/signature.png")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_person_signature_returns_png_when_signature_exists(auth_client, db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN", signature=b"[(0, 0, 10, 10)]")
    resp = auth_client.get(f"/people/{mid}/signature.png")
    assert resp.status_code == 200
    assert resp.content_type == "image/png"
    assert resp.data[:8] == b"\x89PNG\r\n\x1a\n"


def test_person_signature_returns_404_when_no_signature(auth_client, db):
    mid = db.upsert_member(_member())
    resp = auth_client.get(f"/people/{mid}/signature.png")
    assert resp.status_code == 404


def test_person_signature_returns_404_for_malformed_signature_data(auth_client, db):
    # A non-empty but unparseable signature: the DB row exists (get_last_signature
    # finds it) but render_signature() fails to decode it and returns None.
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN", signature=b"not a valid stroke literal")
    resp = auth_client.get(f"/people/{mid}/signature.png")
    assert resp.status_code == 404


def test_person_signature_returns_404_for_unknown_person(auth_client):
    resp = auth_client.get("/people/999999/signature.png")
    assert resp.status_code == 404


# ── Navigation ────────────────────────────────────────────────────────────────

def test_nav_has_all_links(auth_client):
    resp = auth_client.get("/dashboard")
    assert b"Dashboard" in resp.data
    assert b"Sign-In Logs" in resp.data
    assert b"People" in resp.data
    assert b"Audit Log" in resp.data
    assert b"Exports" in resp.data
    assert b"Sign In / Out" in resp.data
    assert b"Dashboard Users" in resp.data
    assert b"Run Sheets" in resp.data


def test_nav_hides_admin_links_for_staff(staff_client):
    resp = staff_client.get("/signin")
    assert b"Sign In / Out" in resp.data
    assert b'href="/people' not in resp.data
    assert b"Dashboard Users" not in resp.data
    assert b"Run Sheets" in resp.data


# ── Multi-user dashboard login (name + PIN, roles) ──────────────────────────────

def test_login_seeds_default_admin_name_and_pin(client):
    resp = client.post("/login", data={"username": "admin", "password": "1234"})
    assert resp.status_code == 302
    assert "/dashboard" in resp.headers["Location"]


def test_login_sets_role_in_session(client):
    client.post("/login", data={"username": "admin", "password": "1234"})
    with client.session_transaction() as sess:
        assert sess["role"] == "admin"
        assert sess["name"] == "admin"


def test_staff_login_redirects_to_signin_not_dashboard(client, db):
    db.create_dashboard_user("Jamie", "2468", "staff")
    resp = client.post("/login", data={"username": "Jamie", "password": "2468"})
    assert resp.status_code == 302
    assert "/signin" in resp.headers["Location"]


def test_login_rejects_unknown_name(client):
    resp = client.post("/login", data={"username": "nobody", "password": "1234"})
    assert resp.status_code == 200
    assert b"Invalid" in resp.data


def test_login_rejects_wrong_pin(client):
    resp = client.post("/login", data={"username": "admin", "password": "wrong"})
    assert resp.status_code == 200
    assert b"Invalid" in resp.data


def test_index_routes_staff_to_signin(staff_client):
    resp = staff_client.get("/")
    assert resp.status_code == 302
    assert "/signin" in resp.headers["Location"]


def test_admin_only_routes_reject_staff(staff_client):
    for url in ["/dashboard", "/logs", "/audit", "/people", "/exports",
                "/alerts", "/dashboard-users"]:
        resp = staff_client.get(url, follow_redirects=True)
        assert resp.status_code == 200
        assert b"Admin access required" in resp.data, url


def test_login_required_routes_allow_staff(staff_client):
    resp = staff_client.get("/signin")
    assert resp.status_code == 200


def test_run_sheets_allow_staff(staff_client):
    resp = staff_client.get("/run-sheets")
    assert resp.status_code == 200


def test_login_rate_limited_after_repeated_failures(client, db):
    from dashboard.app import limiter
    limiter.enabled = True
    try:
        for _ in range(5):
            client.post("/login", data={"username": "admin", "password": "wrong"})
        resp = client.post("/login", data={"username": "admin", "password": "wrong"})
        assert resp.status_code == 429
    finally:
        limiter.enabled = False


def test_csrf_protection_rejects_post_without_token(client):
    from dashboard.app import app as dashboard_flask_app
    dashboard_flask_app.config["WTF_CSRF_ENABLED"] = True
    try:
        resp = client.post("/alerts", data={"scope": "all", "message": "hi"})
        assert resp.status_code == 400
    finally:
        dashboard_flask_app.config["WTF_CSRF_ENABLED"] = False


# ── Manage Dashboard Users ───────────────────────────────────────────────────────

def test_dashboard_users_page_loads(auth_client):
    resp = auth_client.get("/dashboard-users")
    assert resp.status_code == 200


def test_dashboard_users_create(auth_client, db):
    resp = auth_client.post("/dashboard-users/new",
                            data={"name": "Pat", "pin": "Secret123!", "role": "staff"},
                            follow_redirects=True)
    assert resp.status_code == 200
    assert b"Pat" in resp.data
    users = db.list_dashboard_users()
    assert any(u["name"] == "Pat" and u["role"] == "staff" for u in users)


def test_dashboard_users_create_duplicate_name_rejected(auth_client, db):
    db.create_dashboard_user("Pat", "Secret123!", "staff")
    resp = auth_client.post("/dashboard-users/new",
                            data={"name": "Pat", "pin": "OtherPass456!", "role": "staff"},
                            follow_redirects=True)
    assert b"already exists" in resp.data
    assert len(db.list_dashboard_users()) == 2  # seeded admin + Pat, no duplicate


def test_dashboard_users_create_requires_name_and_pin(auth_client):
    resp = auth_client.post("/dashboard-users/new", data={"name": "", "pin": ""},
                            follow_redirects=True)
    assert b"required" in resp.data


def test_dashboard_users_create_weak_password_rejected(auth_client, db):
    resp = auth_client.post("/dashboard-users/new",
                            data={"name": "Pat", "pin": "1357", "role": "staff"},
                            follow_redirects=True)
    assert b"Password must be at least" in resp.data
    assert not any(u["name"] == "Pat" for u in db.list_dashboard_users())


def test_dashboard_users_create_invalid_role_defaults_to_staff(auth_client, db):
    auth_client.post("/dashboard-users/new",
                     data={"name": "Pat", "pin": "Secret123!", "role": "bogus"})
    user = next(u for u in db.list_dashboard_users() if u["name"] == "Pat")
    assert user["role"] == "staff"


def test_dashboard_users_delete_unknown_user_flashes_error(auth_client):
    resp = auth_client.post("/dashboard-users/999999/delete", follow_redirects=True)
    assert b"Dashboard user not found" in resp.data


def test_dashboard_users_delete(auth_client, db):
    uid = db.create_dashboard_user("Pat", "1357", "staff")
    resp = auth_client.post(f"/dashboard-users/{uid}/delete", follow_redirects=True)
    assert resp.status_code == 200
    assert db.get_dashboard_user(uid) is None


def test_dashboard_users_cannot_delete_last_admin(auth_client, db):
    admins = [u for u in db.list_dashboard_users() if u["role"] == "admin"]
    assert len(admins) == 1
    resp = auth_client.post(f"/dashboard-users/{admins[0]['id']}/delete", follow_redirects=True)
    assert b"Cannot delete the last remaining admin" in resp.data
    assert db.get_dashboard_user(admins[0]["id"]) is not None


def test_dashboard_users_can_delete_admin_when_another_admin_exists(auth_client, db):
    second_admin_id = db.create_dashboard_user("Other Admin", "1111", "admin")
    resp = auth_client.post(f"/dashboard-users/{second_admin_id}/delete", follow_redirects=True)
    assert resp.status_code == 200
    assert db.get_dashboard_user(second_admin_id) is None


def test_dashboard_users_requires_admin(staff_client):
    resp = staff_client.get("/dashboard-users", follow_redirects=True)
    assert b"Admin access required" in resp.data


def test_dashboard_user_edit_form_loads(auth_client, db):
    uid = db.create_dashboard_user("Pat", "Secret123!", "staff")
    resp = auth_client.get(f"/dashboard-users/{uid}/edit")
    assert resp.status_code == 200
    assert b"Pat" in resp.data


def test_dashboard_user_edit_unknown_id_flashes_not_found(auth_client):
    resp = auth_client.get("/dashboard-users/999999/edit", follow_redirects=True)
    assert b"Dashboard user not found" in resp.data


def test_dashboard_user_edit_renames_and_relinks(auth_client, db):
    mid = db.upsert_member(_staff())
    uid = db.create_dashboard_user("Pat", "Secret123!", "staff")
    resp = auth_client.post(f"/dashboard-users/{uid}/edit",
                            data={"name": "Patricia", "role": "staff", "member_id": str(mid), "pin": ""},
                            follow_redirects=True)
    assert resp.status_code == 200
    user = db.get_dashboard_user(uid)
    assert user["name"] == "Patricia"
    assert user["member_id"] == mid


def test_dashboard_user_edit_blank_password_keeps_current(auth_client, db):
    uid = db.create_dashboard_user("Pat", "Secret123!", "staff")
    auth_client.post(f"/dashboard-users/{uid}/edit",
                     data={"name": "Pat", "role": "staff", "member_id": "", "pin": ""})
    assert db.check_dashboard_login("Pat", "Secret123!") is not None


def test_dashboard_user_edit_weak_new_password_rejected(auth_client, db):
    uid = db.create_dashboard_user("Pat", "Secret123!", "staff")
    resp = auth_client.post(f"/dashboard-users/{uid}/edit",
                            data={"name": "Pat", "role": "staff", "member_id": "", "pin": "weak"},
                            follow_redirects=True)
    assert b"Password must be at least" in resp.data
    assert db.check_dashboard_login("Pat", "Secret123!") is not None


def test_dashboard_user_edit_new_password_changes_login(auth_client, db):
    uid = db.create_dashboard_user("Pat", "Secret123!", "staff")
    auth_client.post(f"/dashboard-users/{uid}/edit",
                     data={"name": "Pat", "role": "staff", "member_id": "", "pin": "NewSecret456!"})
    assert db.check_dashboard_login("Pat", "NewSecret456!") is not None
    assert db.check_dashboard_login("Pat", "Secret123!") is None


def test_dashboard_user_edit_empty_name_flashes_error(auth_client, db):
    uid = db.create_dashboard_user("Pat", "Secret123!", "staff")
    resp = auth_client.post(f"/dashboard-users/{uid}/edit",
                            data={"name": "", "role": "staff", "member_id": "", "pin": ""},
                            follow_redirects=True)
    assert b"Name is required" in resp.data


def test_dashboard_user_edit_duplicate_name_rejected(auth_client, db):
    db.create_dashboard_user("Amy", "Secret123!", "staff")
    uid = db.create_dashboard_user("Pat", "Secret123!", "staff")
    resp = auth_client.post(f"/dashboard-users/{uid}/edit",
                            data={"name": "Amy", "role": "staff", "member_id": "", "pin": ""},
                            follow_redirects=True)
    assert b"already exists" in resp.data
    assert db.get_dashboard_user(uid)["name"] == "Pat"


def test_dashboard_user_edit_cannot_demote_last_admin(auth_client, db):
    admins = [u for u in db.list_dashboard_users() if u["role"] == "admin"]
    resp = auth_client.post(f"/dashboard-users/{admins[0]['id']}/edit",
                            data={"name": admins[0]["name"], "role": "staff", "member_id": "", "pin": ""},
                            follow_redirects=True)
    assert b"Cannot change the role of the last remaining admin" in resp.data
    assert db.get_dashboard_user(admins[0]["id"])["role"] == "admin"


def test_dashboard_user_edit_invalid_role_defaults_to_staff(auth_client, db):
    uid = db.create_dashboard_user("Pat", "Secret123!", "staff")
    auth_client.post(f"/dashboard-users/{uid}/edit",
                     data={"name": "Pat", "role": "bogus", "member_id": "", "pin": ""})
    assert db.get_dashboard_user(uid)["role"] == "staff"


def test_dashboard_user_edit_requires_admin(staff_client, db):
    uid = db.create_dashboard_user("Pat", "Secret123!", "staff")
    resp = staff_client.get(f"/dashboard-users/{uid}/edit", follow_redirects=True)
    assert b"Admin access required" in resp.data


# ── Login security hardening ─────────────────────────────────────────────────────

def test_login_failed_attempt_logs_audit_event(auth_client, client, db):
    client.post("/login", data={"username": "admin", "password": "wrong"})
    resp = auth_client.get("/audit")
    assert b"DASHBOARD_LOGIN_FAILED" in resp.data


def test_login_locks_account_after_threshold(client, db):
    for _ in range(db.LOCKOUT_THRESHOLD):
        client.post("/login", data={"username": "admin", "password": "wrong"})
    resp = client.post("/login", data={"username": "admin", "password": "admin1234"})
    assert b"temporarily locked" in resp.data


def test_locked_account_rejects_even_correct_password(client, db):
    db.create_dashboard_user("Jamie", "Secret123!", "staff")
    for _ in range(db.LOCKOUT_THRESHOLD):
        client.post("/login", data={"username": "Jamie", "password": "wrong"})
    resp = client.post("/login", data={"username": "Jamie", "password": "Secret123!"})
    assert b"temporarily locked" in resp.data
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_security_headers_present_on_response(client):
    resp = client.get("/login")
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("Referrer-Policy") == "same-origin"
    assert "Content-Security-Policy" in resp.headers


def test_hsts_header_absent_over_plain_http(client):
    resp = client.get("/login")
    assert "Strict-Transport-Security" not in resp.headers


def test_hsts_header_present_over_https(client):
    resp = client.get("/login", base_url="https://localhost")
    assert "Strict-Transport-Security" in resp.headers


# ── Web Sign In / Out page ───────────────────────────────────────────────────────

def test_signin_page_loads(auth_client):
    resp = auth_client.get("/signin")
    assert resp.status_code == 200


def test_signin_requires_login(client):
    resp = client.get("/signin")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_signin_search_finds_member_by_name(auth_client, db):
    db.upsert_member(_member(first_name="Ava", last_name="Thompson"))
    resp = auth_client.get("/signin/search?type=member&q=Ava")
    assert resp.status_code == 200
    results = resp.get_json()["results"]
    assert any(r["name"] == "Ava Thompson" for r in results)


def test_signin_search_excludes_staff_when_type_is_member(auth_client, db):
    db.upsert_member(_staff(first_name="Sam", last_name="Taylor"))
    resp = auth_client.get("/signin/search?type=member&q=Sam")
    assert resp.get_json()["results"] == []


def test_signin_search_finds_staff_when_type_is_staff(auth_client, db):
    db.upsert_member(_staff(first_name="Sam", last_name="Taylor"))
    resp = auth_client.get("/signin/search?type=staff&q=Sam")
    results = resp.get_json()["results"]
    assert any(r["name"] == "Sam Taylor" for r in results)


def test_signin_search_empty_query_returns_no_results(auth_client):
    resp = auth_client.get("/signin/search?type=member&q=")
    assert resp.get_json()["results"] == []


def test_signin_alerts_returns_alerts_for_targeted_member(auth_client, db):
    mid = db.upsert_member(_member())
    db.create_alert("member", mid, "Remember swimming kit")
    resp = auth_client.get(f"/signin/alerts?member_ids={mid}")
    alerts = resp.get_json()["alerts"]
    assert any(a["message"] == "Remember swimming kit" for a in alerts)


def test_signin_alerts_empty_for_member_with_no_alerts(auth_client, db):
    mid = db.upsert_member(_member())
    resp = auth_client.get(f"/signin/alerts?member_ids={mid}")
    assert resp.get_json()["alerts"] == []


def test_signin_post_records_sign_in(auth_client, db):
    mid = db.upsert_member(_member())
    resp = auth_client.post("/signin", data={
        "member_ids": [str(mid)], "direction": "IN", "notes": "test note",
        "signature_data": "",
    }, follow_redirects=True)
    assert resp.status_code == 200
    last = db.get_last_sign(mid)
    assert last["direction"] == "IN"
    assert last["notes"] == "test note"


def test_signin_post_without_signature_is_accepted(auth_client, db):
    mid = db.upsert_member(_member())
    resp = auth_client.post("/signin", data={
        "member_ids": [str(mid)], "direction": "IN", "notes": "",
        "signature_data": "",
    }, follow_redirects=True)
    assert resp.status_code == 200
    last = db.get_last_sign(mid)
    assert last["signature"] is None


def test_signin_post_signature_round_trips_through_render_signature(auth_client, db):
    import json as _json
    from export_util import render_signature

    mid = db.upsert_member(_member())
    strokes = [[1, 2, 3, 4], [3, 4, 5, 6]]
    resp = auth_client.post("/signin", data={
        "member_ids": [str(mid)], "direction": "IN", "notes": "",
        "signature_data": _json.dumps(strokes),
    }, follow_redirects=True)
    assert resp.status_code == 200

    last = db.get_last_sign(mid)
    assert last["signature"] == str([(1, 2, 3, 4), (3, 4, 5, 6)]).encode()
    png = render_signature(last["signature"], width=100, height=50)
    assert png is not None
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_signin_post_malformed_signature_flashes_error(auth_client, db):
    mid = db.upsert_member(_member())
    resp = auth_client.post("/signin", data={
        "member_ids": [str(mid)], "direction": "IN", "notes": "",
        "signature_data": "not valid json",
    }, follow_redirects=True)
    assert b"Invalid signature data" in resp.data
    assert db.get_last_sign(mid) is None


def test_signin_post_signature_not_a_list_flashes_error(auth_client, db):
    import json as _json
    mid = db.upsert_member(_member())
    resp = auth_client.post("/signin", data={
        "member_ids": [str(mid)], "direction": "IN", "notes": "",
        "signature_data": _json.dumps({"not": "a list"}),
    }, follow_redirects=True)
    assert b"Invalid signature data" in resp.data
    assert db.get_last_sign(mid) is None


def test_signin_post_signature_bad_segment_flashes_error(auth_client, db):
    import json as _json
    mid = db.upsert_member(_member())
    resp = auth_client.post("/signin", data={
        "member_ids": [str(mid)], "direction": "IN", "notes": "",
        "signature_data": _json.dumps([[1, 2, 3]]),  # only 3 coords, needs 4
    }, follow_redirects=True)
    assert b"Invalid signature data" in resp.data
    assert db.get_last_sign(mid) is None


def test_signin_post_blocked_direction_records_nothing(auth_client, db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")  # already signed in
    resp = auth_client.post("/signin", data={
        "member_ids": [str(mid)], "direction": "IN", "notes": "",
        "signature_data": "",
    }, follow_redirects=True)
    assert b"need to sign OUT first" in resp.data
    signs = db.get_signs_for_member(mid)
    assert len(signs) == 1  # only the original IN, nothing new recorded


def test_signin_post_partial_block_skips_only_blocked_members(auth_client, db):
    ready = db.upsert_member(_member(first_name="Ready"))
    already_in = db.upsert_member(_member(first_name="Already"))
    db.record_sign(already_in, "IN")
    resp = auth_client.post("/signin", data={
        "member_ids": [str(ready), str(already_in)], "direction": "IN", "notes": "",
        "signature_data": "",
    }, follow_redirects=True)
    assert b"1 signed in" in resp.data
    assert b"1 skipped" in resp.data
    assert db.get_last_sign(ready)["direction"] == "IN"


def test_signin_post_no_members_selected_flashes_error(auth_client):
    resp = auth_client.post("/signin", data={
        "member_ids": [], "direction": "IN", "notes": "", "signature_data": "",
    }, follow_redirects=True)
    assert b"Select at least one person" in resp.data


def test_signin_post_invalid_direction_flashes_error(auth_client, db):
    mid = db.upsert_member(_member())
    resp = auth_client.post("/signin", data={
        "member_ids": [str(mid)], "direction": "SIDEWAYS", "notes": "",
        "signature_data": "",
    }, follow_redirects=True)
    assert b"Choose a direction" in resp.data


def test_signin_post_sends_email_notification(auth_client, db, monkeypatch):
    from unittest.mock import Mock
    import dashboard.app as dashboard_app_module

    mid = db.upsert_member(_member())
    db.upsert_caregiver(_caregiver(mid, notify_on="BOTH"))
    mock_send = Mock()
    monkeypatch.setattr("email_notifier.send_notification", mock_send)

    auth_client.post("/signin", data={
        "member_ids": [str(mid)], "direction": "IN", "notes": "",
        "signature_data": "",
    })
    mock_send.assert_called_once()
    called_member, called_direction, _ts = mock_send.call_args[0]
    assert called_member["id"] == mid
    assert called_direction == "IN"


def test_signin_available_to_staff_role(staff_client, db):
    mid = db.upsert_member(_member())
    resp = staff_client.post("/signin", data={
        "member_ids": [str(mid)], "direction": "IN", "notes": "",
        "signature_data": "",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert db.get_last_sign(mid)["direction"] == "IN"


# ── Run Sheets (dashboard) ───────────────────────────────────────────────────

def test_run_sheets_page_loads(auth_client):
    resp = auth_client.get("/run-sheets")
    assert resp.status_code == 200
    assert b"Run Sheets" in resp.data


def test_run_sheets_page_shows_member_count(auth_client, db):
    mid = db.upsert_member(_member())
    db.upsert_run("Morning Run", [mid])
    resp = auth_client.get("/run-sheets")
    assert b"Morning Run" in resp.data


def test_run_sheets_search_filters_by_name(auth_client, db):
    db.upsert_run("Morning Run", [])
    db.upsert_run("Afternoon Bus", [])
    resp = auth_client.get("/run-sheets?search=Morning")
    assert b"Morning Run" in resp.data
    assert b"Afternoon Bus" not in resp.data


def test_run_sheet_new_form_loads(auth_client):
    resp = auth_client.get("/run-sheets/new")
    assert resp.status_code == 200
    assert b"New Run Sheet" in resp.data


def test_run_sheet_new_post_creates(auth_client, db):
    mid = db.upsert_member(_member())
    resp = auth_client.post("/run-sheets/new", data={
        "name": "Created Run", "member_ids": [str(mid)],
    }, follow_redirects=True)
    assert resp.status_code == 200
    runs = db.search_runs("Created Run")
    assert len(runs) == 1
    assert {m["id"] for m in db.get_run_members(runs[0]["id"])} == {mid}


def test_run_sheet_new_post_missing_name_flashes_error(auth_client):
    resp = auth_client.post("/run-sheets/new", data={"name": "", "member_ids": []}, follow_redirects=True)
    assert b"Run sheet name is required." in resp.data


def test_run_sheet_new_post_duplicate_name_flashes_error(auth_client, db):
    db.upsert_run("Taken Name", [])
    resp = auth_client.post("/run-sheets/new", data={
        "name": "Taken Name", "member_ids": [],
    }, follow_redirects=True)
    assert b"already exists" in resp.data


def test_run_sheet_edit_get_prefills_members(auth_client, db):
    mid = db.upsert_member(_member(first_name="Runner"))
    rid = db.upsert_run("Existing Run", [mid])
    resp = auth_client.get(f"/run-sheets/{rid}/edit")
    assert resp.status_code == 200
    assert b"Existing Run" in resp.data
    assert b"Runner" in resp.data


def test_run_sheet_edit_unknown_id_flashes_not_found(auth_client):
    resp = auth_client.get("/run-sheets/99999/edit", follow_redirects=True)
    assert b"Run sheet not found." in resp.data


def test_run_sheet_edit_post_renames_and_updates_members(auth_client, db):
    mid1 = db.upsert_member(_member(first_name="A"))
    mid2 = db.upsert_member(_member(first_name="B"))
    rid = db.upsert_run("Old Name", [mid1])
    resp = auth_client.post(f"/run-sheets/{rid}/edit", data={
        "name": "New Name", "member_ids": [str(mid2)],
    }, follow_redirects=True)
    assert resp.status_code == 200
    run = db.get_run(rid)
    assert run["name"] == "New Name"
    assert {m["id"] for m in db.get_run_members(rid)} == {mid2}


def test_run_sheet_edit_post_missing_name_flashes_error(auth_client, db):
    rid = db.upsert_run("Old Name", [])
    resp = auth_client.post(f"/run-sheets/{rid}/edit", data={
        "name": "", "member_ids": [],
    }, follow_redirects=True)
    assert b"Run sheet name is required." in resp.data


def test_run_sheet_edit_post_duplicate_name_flashes_error(auth_client, db):
    db.upsert_run("Existing Run", [])
    rid = db.upsert_run("Renamed Run", [])
    resp = auth_client.post(f"/run-sheets/{rid}/edit", data={
        "name": "Existing Run", "member_ids": [],
    }, follow_redirects=True)
    assert b"already exists" in resp.data
    assert db.get_run(rid)["name"] == "Renamed Run"


def test_run_sheet_delete_removes_run(auth_client, db):
    rid = db.upsert_run("Delete Me", [])
    resp = auth_client.post(f"/run-sheets/{rid}/delete", follow_redirects=True)
    assert resp.status_code == 200
    assert db.get_run(rid) is None


def test_run_sheet_delete_unknown_id_flashes_not_found(auth_client):
    resp = auth_client.post("/run-sheets/99999/delete", follow_redirects=True)
    assert b"Run sheet not found." in resp.data


def test_run_sheet_search_endpoint_json(auth_client, db):
    db.upsert_run("Morning Run", [])
    resp = auth_client.get("/run-sheets/search?q=Morning")
    assert resp.get_json()["results"][0]["name"] == "Morning Run"


def test_run_sheet_search_endpoint_empty_query_returns_no_results(auth_client):
    resp = auth_client.get("/run-sheets/search?q=")
    assert resp.get_json()["results"] == []


def test_run_sheet_members_endpoint_json(auth_client, db):
    mid = db.upsert_member(_member(first_name="Runner", last_name="Kid"))
    rid = db.upsert_run("Morning Run", [mid])
    resp = auth_client.get(f"/run-sheets/{rid}/members")
    assert resp.get_json()["members"] == [{"id": mid, "name": "Runner Kid"}]


def test_run_sheet_members_endpoint_empty_run(auth_client, db):
    rid = db.upsert_run("Empty Run", [])
    resp = auth_client.get(f"/run-sheets/{rid}/members")
    assert resp.get_json()["members"] == []


def test_run_sheets_available_to_staff_role(staff_client, db):
    mid = db.upsert_member(_member())
    resp = staff_client.post("/run-sheets/new", data={
        "name": "Staff Created Run", "member_ids": [str(mid)],
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert len(db.search_runs("Staff Created Run")) == 1


# ── Bulk select currently signed in ─────────────────────────────────────────

def test_signin_currently_in_endpoint_json(auth_client, db):
    mid = db.upsert_member(_member(first_name="Here", last_name="Now"))
    db.record_sign(mid, "IN")
    resp = auth_client.get("/signin/currently-in")
    assert resp.get_json()["members"] == [{"id": mid, "name": "Here Now"}]


def test_signin_currently_in_excludes_signed_out(auth_client, db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")
    db.record_sign(mid, "OUT")
    resp = auth_client.get("/signin/currently-in")
    assert resp.get_json()["members"] == []


def test_signin_currently_in_empty(auth_client):
    resp = auth_client.get("/signin/currently-in")
    assert resp.get_json()["members"] == []


# ── My Timesheet (self-service) ──────────────────────────────────────────────

def _staff_client_linked_to(db, client, member_id):
    """Creates a staff dashboard login linked to member_id and logs it in."""
    uid = db.create_dashboard_user("Linked Staffer", "Secret123!", "staff", member_id)
    with client.session_transaction() as sess:
        sess["user_id"] = uid
        sess["role"] = "staff"
        sess["name"] = "Linked Staffer"
        sess["member_id"] = member_id
    return client


def test_my_timesheet_unlinked_account_redirects_with_flash(staff_client):
    resp = staff_client.get("/my-timesheet", follow_redirects=True)
    assert b"linked to a staff record" in resp.data


def test_my_timesheet_shows_own_sessions(client, db):
    sid = db.upsert_member(_staff(first_name="Own", last_name="Timesheet"))
    db.record_sign(sid, "IN")
    db.record_sign(sid, "OUT")
    c = _staff_client_linked_to(db, client, sid)
    resp = c.get("/my-timesheet")
    assert resp.status_code == 200
    assert b"SIGNED OUT" in resp.data


def test_my_timesheet_filters_by_date_range(client, db):
    sid = db.upsert_member(_staff())
    db.record_sign(sid, "IN")
    c = _staff_client_linked_to(db, client, sid)
    resp = c.get("/my-timesheet?date_from=2000-01-01&date_to=2000-01-02")
    assert resp.status_code == 200
    assert b"No sign-in records found" in resp.data


def test_my_timesheet_download_unlinked_account_redirects_with_flash(staff_client):
    resp = staff_client.get("/my-timesheet/download", follow_redirects=True)
    assert b"linked to a staff record" in resp.data


def test_my_timesheet_download_returns_own_xlsx(client, db):
    sid = db.upsert_member(_staff(first_name="Down", last_name="Loader"))
    db.record_sign(sid, "IN")
    db.record_sign(sid, "OUT")
    c = _staff_client_linked_to(db, client, sid)
    resp = c.get("/my-timesheet/download")
    assert resp.status_code == 200
    assert b"PK" == resp.data[:2]
    assert "Down_Loader" in resp.headers["Content-Disposition"]


def test_my_timesheet_download_pdf_format(client, db):
    sid = db.upsert_member(_staff())
    db.record_sign(sid, "IN")
    db.record_sign(sid, "OUT")
    c = _staff_client_linked_to(db, client, sid)
    resp = c.get("/my-timesheet/download?fmt=pdf")
    assert resp.status_code == 200
    assert resp.data[:4] == b"%PDF"


def test_my_timesheet_download_no_records_redirects(client, db):
    sid = db.upsert_member(_staff())
    c = _staff_client_linked_to(db, client, sid)
    resp = c.get("/my-timesheet/download", follow_redirects=True)
    assert resp.status_code == 200
    assert b"No sign-in records found" in resp.data


def test_my_timesheet_never_reads_client_supplied_person_id(client, db):
    """A staff account must never be able to view or download someone
    else's timesheet by tampering a query param -- the person is resolved
    strictly from the session's linked member_id, and these routes don't
    even accept a person/member id as input."""
    own = db.upsert_member(_staff(first_name="Owner", last_name="Account"))
    other = db.upsert_member(_staff(first_name="Victim", last_name="Person"))
    db.record_sign(other, "IN")
    db.record_sign(other, "OUT")
    c = _staff_client_linked_to(db, client, own)

    resp = c.get(f"/my-timesheet?person_id={other}&member_id={other}")
    assert b"No sign-in records found" in resp.data  # own account has none, other's are never read

    resp = c.get(f"/my-timesheet/download?person_id={other}&member_id={other}", follow_redirects=True)
    assert b"No sign-in records found" in resp.data


def test_nav_shows_my_timesheet_for_linked_staff(client, db):
    sid = db.upsert_member(_staff())
    c = _staff_client_linked_to(db, client, sid)
    resp = c.get("/my-timesheet")
    assert b"My Timesheet" in resp.data


def test_nav_hides_my_timesheet_for_unlinked_admin(auth_client):
    resp = auth_client.get("/dashboard")
    assert b"My Timesheet" not in resp.data
