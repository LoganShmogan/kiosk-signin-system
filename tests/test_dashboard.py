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
    from dashboard.app import app, get_conn as _orig_get_conn
    monkeypatch.setattr("dashboard.app.DB_PATH", db_module.DB_PATH)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def auth_client(client):
    with client.session_transaction() as sess:
        sess["logged_in"] = True
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
    assert b"Member Signing Sheets" in resp.data
    assert b"Staff Signing Sheets" in resp.data


def test_export_members_returns_xlsx(auth_client, db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    resp = auth_client.get(f"/export/members?date_from={today}&date_to={today}")
    assert resp.status_code == 200
    assert resp.content_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert b"PK" == resp.data[:2]


def test_export_staff_returns_xlsx(auth_client, db):
    sid = db.upsert_member(_staff())
    db.record_sign(sid, "IN")
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    resp = auth_client.get(f"/export/staff?date_from={today}&date_to={today}")
    assert resp.status_code == 200
    assert resp.content_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert b"PK" == resp.data[:2]


def test_export_members_missing_params(auth_client):
    resp = auth_client.get("/export/members")
    assert resp.status_code == 400


def test_export_staff_missing_params(auth_client):
    resp = auth_client.get("/export/staff")
    assert resp.status_code == 400


def test_export_members_empty_range(auth_client):
    resp = auth_client.get("/export/members?date_from=2000-01-01&date_to=2000-01-02")
    assert resp.status_code == 200
    assert b"PK" == resp.data[:2]


def test_export_staff_empty_range(auth_client):
    resp = auth_client.get("/export/staff?date_from=2000-01-01&date_to=2000-01-02")
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
