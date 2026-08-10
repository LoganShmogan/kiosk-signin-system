"""
Tests for the Flask web dashboard — auth, pages, CRUD, and exports.
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "kiosk_signin"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import database as db_module
from helpers import member as _member, staff_member as _staff, caregiver as _caregiver


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
                "/people/new", "/people/1"]:
        resp = client.get(url)
        assert resp.status_code == 302, f"{url} should redirect when not logged in"


# ── Dashboard ─────────────────────────────────────────────────────────────────

def test_dashboard_page_loads(auth_client):
    resp = auth_client.get("/dashboard")
    assert resp.status_code == 200
    assert b"Kiosk Sign-In Dashboard" in resp.data


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


def test_logs_filter_excludes_signed_out(auth_client, db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")
    resp = auth_client.get("/logs?status=CLOSED")
    assert resp.status_code == 200
    assert b"Jane" not in resp.data


def test_logs_search_filters_by_name(auth_client, db):
    mid = db.upsert_member(_member(first_name="Findme", last_name="Person"))
    db.record_sign(mid, "IN")
    other = db.upsert_member(_member(first_name="Other", last_name="Person"))
    db.record_sign(other, "IN")
    resp = auth_client.get("/logs?search=Findme")
    assert b"Findme" in resp.data
    assert b"Other Person" not in resp.data


def test_logs_shows_edit_link_for_existing_sign(auth_client, db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")
    resp = auth_client.get("/logs")
    assert b"/logs/sign/" in resp.data
    assert b"/edit" in resp.data


def test_logs_shows_add_link_for_missing_sign(auth_client, db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")
    resp = auth_client.get("/logs")
    assert b"/logs/sign/add" in resp.data


def test_sign_edit_updates_timestamp(auth_client, db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")
    sign_id = db.get_last_sign(mid)["id"]
    resp = auth_client.post(
        f"/logs/sign/{sign_id}/edit", data={"timestamp": "2026-01-01T09:30"}
    )
    assert resp.status_code == 302
    assert db.get_sign(sign_id)["timestamp"] == "2026-01-01 09:30:00"


def test_sign_edit_invalid_timestamp_flashes_error(auth_client, db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")
    sign_id = db.get_last_sign(mid)["id"]
    resp = auth_client.post(
        f"/logs/sign/{sign_id}/edit", data={"timestamp": "not-a-date"}, follow_redirects=True
    )
    assert b"Enter a valid date and time" in resp.data


def test_sign_edit_not_found(auth_client):
    resp = auth_client.get("/logs/sign/999999/edit", follow_redirects=True)
    assert b"Sign-in record not found" in resp.data


def test_sign_add_creates_record(auth_client, db):
    from datetime import datetime
    mid = db.upsert_member(_member())
    today = datetime.now().strftime("%Y-%m-%d")
    resp = auth_client.post(
        "/logs/sign/add",
        data={"member_id": str(mid), "direction": "IN", "timestamp": f"{today}T08:00"},
    )
    assert resp.status_code == 302
    assert db.get_allowed_direction(mid) == "OUT"


def test_sign_add_invalid_request_flashes_error(auth_client):
    resp = auth_client.get("/logs/sign/add", follow_redirects=True)
    assert b"Invalid request" in resp.data


def test_sign_add_person_not_found(auth_client):
    resp = auth_client.get(
        "/logs/sign/add?member_id=999999&direction=IN", follow_redirects=True
    )
    assert b"Person not found" in resp.data


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


def test_new_staff_form_renders_person_type_hidden_field(auth_client):
    resp = auth_client.get("/people/new?type=staff")
    assert b'name="person_type" value="staff"' in resp.data


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


# ── Exports page ──────────────────────────────────────────────────────────────

def test_exports_page_loads(auth_client):
    resp = auth_client.get("/exports")
    assert resp.status_code == 200
    assert b"Staff Signing Sheets" in resp.data
    assert b"Export a Person's Sign-ins" in resp.data


def test_export_members_route_removed(auth_client):
    resp = auth_client.get("/export/members")
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


def test_export_staff_single_person_by_id(auth_client, db):
    sid = db.upsert_member(_staff())
    db.record_sign(sid, "IN")
    resp = auth_client.get(f"/export/staff?person_id={sid}")
    assert resp.status_code == 200
    assert resp.headers["Content-Disposition"].startswith("attachment")
    assert "KioskSignIn_" in resp.headers["Content-Disposition"]


def test_export_staff_person_id_not_staff_flashes_error(auth_client, db):
    mid = db.upsert_member(_member())
    resp = auth_client.get(f"/export/staff?person_id={mid}", follow_redirects=True)
    assert b"Staff member not found" in resp.data


def test_export_person_downloads_member(auth_client, db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")
    resp = auth_client.get(f"/export/person?person_id={mid}")
    assert resp.status_code == 200
    assert resp.content_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def test_export_person_no_records_flashes_error(auth_client, db):
    mid = db.upsert_member(_member())
    resp = auth_client.get(f"/export/person?person_id={mid}", follow_redirects=True)
    assert b"No sign-in records found" in resp.data


def test_export_person_no_person_id_flashes_error(auth_client):
    resp = auth_client.get("/export/person", follow_redirects=True)
    assert b"Select a person to export" in resp.data


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


# ── CSRF protection ───────────────────────────────────────────────────────────
# The `client`/`auth_client` fixtures disable WTF_CSRF_ENABLED so the rest of
# the suite can POST without wiring up real tokens. These tests turn CSRF
# enforcement back on for a single request each, to make sure protection is
# actually wired up rather than the fixture silently masking a gap.

def test_login_form_renders_csrf_token(client):
    resp = client.get("/login")
    assert b'name="csrf_token"' in resp.data


def test_alerts_form_renders_csrf_token(auth_client):
    resp = auth_client.get("/alerts")
    assert b'name="csrf_token"' in resp.data


def test_person_form_renders_csrf_token(auth_client):
    resp = auth_client.get("/people/new")
    assert b'name="csrf_token"' in resp.data


def test_post_without_csrf_token_rejected_when_enabled(client):
    from dashboard.app import app
    app.config["WTF_CSRF_ENABLED"] = True
    try:
        resp = client.post("/login", data={"username": "admin", "password": "1234"})
        assert resp.status_code == 400
    finally:
        app.config["WTF_CSRF_ENABLED"] = False


def test_post_with_csrf_token_from_rendered_form_succeeds(client):
    from dashboard.app import app
    app.config["WTF_CSRF_ENABLED"] = True
    try:
        get_resp = client.get("/login")
        token = get_resp.data.decode().split('name="csrf_token" value="')[1].split('"')[0]
        resp = client.post(
            "/login",
            data={"username": "admin", "password": "1234", "csrf_token": token},
        )
        assert resp.status_code == 302
        assert "/dashboard" in resp.headers["Location"]
    finally:
        app.config["WTF_CSRF_ENABLED"] = False


# ── _parse_signature ─────────────────────────────────────────────────────────

def test_parse_signature_empty_returns_none():
    from dashboard.app import _parse_signature
    assert _parse_signature("") is None
    assert _parse_signature(None) is None


def test_parse_signature_valid_strokes():
    from dashboard.app import _parse_signature
    raw = '[[1,2,3,4],[5,6,7,8]]'
    result = _parse_signature(raw)
    assert result == str([(1, 2, 3, 4), (5, 6, 7, 8)]).encode()


def test_parse_signature_not_a_list_raises():
    from dashboard.app import _parse_signature
    with pytest.raises(ValueError):
        _parse_signature('{"not": "a list"}')


def test_parse_signature_too_many_strokes_raises():
    from dashboard.app import _parse_signature
    import json as _json
    raw = _json.dumps([[1, 2, 3, 4]] * 20001)
    with pytest.raises(ValueError):
        _parse_signature(raw)


def test_parse_signature_bad_segment_shape_raises():
    from dashboard.app import _parse_signature
    with pytest.raises(ValueError):
        _parse_signature('[[1,2,3]]')


def test_parse_signature_non_numeric_segment_raises():
    from dashboard.app import _parse_signature
    with pytest.raises(ValueError):
        _parse_signature('[[1,2,3,"x"]]')


# ── Web sign-in / out page ───────────────────────────────────────────────────

def test_signin_page_loads_for_admin(auth_client):
    resp = auth_client.get("/signin")
    assert resp.status_code == 200
    assert b"Sign In / Out" in resp.data


def test_signin_page_loads_for_staff(staff_client):
    resp = staff_client.get("/signin")
    assert resp.status_code == 200


def test_signin_requires_login(client):
    resp = client.get("/signin")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_signin_post_records_sign_in(auth_client, db):
    mid = db.upsert_member(_member())
    resp = auth_client.post("/signin", data={"member_ids": [str(mid)], "direction": "IN"})
    assert resp.status_code == 302
    assert db.get_allowed_direction(mid) == "OUT"


def test_signin_post_no_members_selected_flashes_error(auth_client):
    resp = auth_client.post("/signin", data={"direction": "IN"}, follow_redirects=True)
    assert b"Select at least one person" in resp.data


def test_signin_post_invalid_direction_flashes_error(auth_client, db):
    mid = db.upsert_member(_member())
    resp = auth_client.post(
        "/signin", data={"member_ids": [str(mid)], "direction": "SIDEWAYS"}, follow_redirects=True
    )
    assert b"Choose a direction" in resp.data


def test_signin_post_blocked_direction_flashes_skip_message(auth_client, db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")
    resp = auth_client.post(
        "/signin", data={"member_ids": [str(mid)], "direction": "IN"}, follow_redirects=True
    )
    assert b"need to sign" in resp.data


def test_signin_search_members(auth_client, db):
    db.upsert_member(_member(first_name="Unique", last_name="Searchable"))
    resp = auth_client.get("/signin/search?type=member&q=Unique")
    data = resp.get_json()
    assert any(r["name"] == "Unique Searchable" for r in data["results"])


def test_signin_search_staff(auth_client, db):
    db.upsert_member(_staff(first_name="StaffUnique"))
    resp = auth_client.get("/signin/search?type=staff&q=StaffUnique")
    data = resp.get_json()
    assert any("StaffUnique" in r["name"] for r in data["results"])


def test_signin_search_empty_query_returns_no_results(auth_client):
    resp = auth_client.get("/signin/search?type=member&q=")
    assert resp.get_json() == {"results": []}


def test_signin_alerts_returns_matching_alerts(auth_client, db):
    mid = db.upsert_member(_member())
    db.create_alert("all", None, "Reminder for everyone")
    resp = auth_client.get(f"/signin/alerts?member_ids={mid}")
    data = resp.get_json()
    assert any(a["message"] == "Reminder for everyone" for a in data["alerts"])


def test_signin_alerts_no_ids_returns_empty(auth_client):
    resp = auth_client.get("/signin/alerts?member_ids=")
    assert resp.get_json() == {"alerts": []}


# ── Status page ("Who's Here") ───────────────────────────────────────────────

def test_status_page_loads_for_staff(staff_client):
    resp = staff_client.get("/status")
    assert resp.status_code == 200
    assert b"Who's Here" in resp.data


def test_status_page_loads_for_admin(auth_client):
    resp = auth_client.get("/status")
    assert resp.status_code == 200


def test_status_requires_login(client):
    resp = client.get("/status")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_status_shows_currently_signed_in(auth_client, db):
    mid = db.upsert_member(_member(first_name="Present", last_name="Now"))
    db.record_sign(mid, "IN")
    resp = auth_client.get("/status")
    assert b"Present Now" in resp.data


# ── Dashboard users ───────────────────────────────────────────────────────────

def test_dashboard_users_page_admin_only(auth_client):
    resp = auth_client.get("/dashboard-users")
    assert resp.status_code == 200
    assert b"Dashboard Users" in resp.data


def test_dashboard_users_page_blocked_for_staff(staff_client):
    resp = staff_client.get("/dashboard-users", follow_redirects=True)
    assert b"Admin access required" in resp.data


def test_dashboard_user_new_creates_user(auth_client, db):
    resp = auth_client.post(
        "/dashboard-users/new", data={"name": "NewStaffer", "pin": "1111", "role": "staff"}
    )
    assert resp.status_code == 302
    assert db.check_dashboard_login("NewStaffer", "1111") is not None


def test_dashboard_user_new_duplicate_name_flashes_error(auth_client, db):
    db.create_dashboard_user("Dup", "1111", "staff")
    resp = auth_client.post(
        "/dashboard-users/new", data={"name": "Dup", "pin": "2222", "role": "staff"},
        follow_redirects=True,
    )
    assert b"already exists" in resp.data


def test_dashboard_user_new_missing_fields_flashes_error(auth_client):
    resp = auth_client.post("/dashboard-users/new", data={"name": "", "pin": ""}, follow_redirects=True)
    assert b"required" in resp.data


def test_dashboard_user_new_invalid_role_defaults_to_staff(auth_client, db):
    auth_client.post(
        "/dashboard-users/new", data={"name": "WeirdRole", "pin": "1234", "role": "superuser"}
    )
    user = db.check_dashboard_login("WeirdRole", "1234")
    assert user["role"] == "staff"


def test_dashboard_user_delete_removes_user(auth_client, db):
    uid = db.create_dashboard_user("ToDelete", "1234", "staff")
    resp = auth_client.post(f"/dashboard-users/{uid}/delete")
    assert resp.status_code == 302
    assert db.get_dashboard_user(uid) is None


def test_dashboard_user_delete_blocks_last_admin(auth_client, db):
    admin_id = db.check_dashboard_login("admin", "1234")["id"]
    resp = auth_client.post(f"/dashboard-users/{admin_id}/delete", follow_redirects=True)
    assert b"Cannot delete the last remaining admin" in resp.data
    assert db.get_dashboard_user(admin_id) is not None


def test_dashboard_user_delete_not_found(auth_client):
    resp = auth_client.post("/dashboard-users/999999/delete", follow_redirects=True)
    assert b"not found" in resp.data
