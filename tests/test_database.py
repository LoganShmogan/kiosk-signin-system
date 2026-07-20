"""
Tests for database.py — all tests use a fresh temp DB via the db fixture.
"""
from datetime import datetime
from helpers import member as _member, caregiver as _caregiver, staff_member as _staff


# ── Members ────────────────────────────────────────────────────────────────────

def test_init_seeds_admin(db):
    assert db.check_admin_password("admin1234")


def test_init_seeds_members(db):
    assert len(db.search_members("")) >= 5


def test_upsert_member_insert(db):
    mid = db.upsert_member(_member())
    m = db.get_member(mid)
    assert m["first_name"] == "Jane"
    assert m["last_name"] == "Smith"


def test_upsert_member_update(db):
    mid = db.upsert_member(_member())
    db.upsert_member({**_member(), "id": mid, "first_name": "Janet"})
    assert db.get_member(mid)["first_name"] == "Janet"


def test_search_members_by_name(db):
    mid = db.upsert_member(_member(first_name="Unique", last_name="Person"))
    results = db.search_members("Unique")
    assert any(m["id"] == mid for m in results)


def test_search_members_empty_returns_all(db):
    assert len(db.search_members("")) > 0


def test_get_member_not_found(db):
    assert db.get_member(99999) is None


def test_delete_member(db):
    mid = db.upsert_member(_member())
    db.delete_member(mid)
    assert db.get_member(mid) is None


def test_delete_member_cascades_signs(db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")
    db.delete_member(mid)
    assert db.get_last_sign(mid) is None


# ── PIN ────────────────────────────────────────────────────────────────────────

def test_verify_pin_correct(db):
    mid = db.upsert_member(_member(pin="9999"))
    assert db.verify_pin(mid, "9999")


def test_verify_pin_incorrect(db):
    mid = db.upsert_member(_member(pin="9999"))
    assert not db.verify_pin(mid, "0000")


def test_verify_pin_blank_allows_any_input(db):
    # Members with no PIN set can sign in without entering one
    mid = db.upsert_member(_member(pin=""))
    assert db.verify_pin(mid, "anything")
    assert db.verify_pin(mid, "")


# ── Caregivers ─────────────────────────────────────────────────────────────────

def test_upsert_caregiver_insert(db):
    mid = db.upsert_member(_member())
    db.upsert_caregiver(_caregiver(mid))
    cg = db.get_caregiver(mid)
    assert cg["full_name"] == "Bob Smith"


def test_upsert_caregiver_update(db):
    mid = db.upsert_member(_member())
    db.upsert_caregiver(_caregiver(mid))
    db.upsert_caregiver(_caregiver(mid, full_name="Updated Name"))
    assert db.get_caregiver(mid)["full_name"] == "Updated Name"


def test_delete_member_cascades_caregiver(db):
    mid = db.upsert_member(_member())
    db.upsert_caregiver(_caregiver(mid))
    db.delete_member(mid)
    assert db.get_caregiver(mid) is None


# ── Sign-in / out ─────────────────────────────────────────────────────────────

def test_record_and_get_last_sign(db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")
    last = db.get_last_sign(mid)
    assert last["direction"] == "IN"
    assert last["member_id"] == mid


def test_get_last_sign_returns_most_recent(db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")
    db.record_sign(mid, "OUT")
    assert db.get_last_sign(mid)["direction"] == "OUT"


def test_get_today_last_sign_no_signs(db):
    mid = db.upsert_member(_member())
    assert db.get_today_last_sign(mid) is None


def test_get_today_last_sign_returns_latest(db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")
    db.record_sign(mid, "OUT")
    assert db.get_today_last_sign(mid)["direction"] == "OUT"


def test_get_today_signs_includes_todays_records(db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")
    signs = db.get_today_signs()
    assert any(s["member_id"] == mid for s in signs)


def test_get_signs_for_export_date_range(db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")
    today = datetime.now().strftime("%Y-%m-%d")
    signs = db.get_signs_for_export(today, today)
    assert any(s["member_id"] == mid for s in signs)


def test_get_signs_for_export_excludes_outside_range(db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")
    signs = db.get_signs_for_export("2000-01-01", "2000-01-02")
    assert not any(s["member_id"] == mid for s in signs)


# ── Last signature ─────────────────────────────────────────────────────────────

def test_get_last_signature_returns_most_recent_with_signature(db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN", signature=b"[(0,0,1,1)]")
    db.record_sign(mid, "OUT", signature=b"[(2,2,3,3)]")
    sig = db.get_last_signature(mid)
    assert sig["direction"] == "OUT"
    assert sig["signature"] == b"[(2,2,3,3)]"


def test_get_last_signature_skips_null_signature_rows(db):
    # Simulates a pre-existing record with no captured signature: the most
    # recent row has none, so the previous row's signature should be used.
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN", signature=b"[(0,0,1,1)]")
    db.record_sign(mid, "OUT", signature=None)
    sig = db.get_last_signature(mid)
    assert sig["direction"] == "IN"
    assert sig["signature"] == b"[(0,0,1,1)]"


def test_get_last_signature_no_history_returns_none(db):
    mid = db.upsert_member(_member())
    assert db.get_last_signature(mid) is None


def test_get_last_signature_all_signatures_null_returns_none(db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN", signature=None)
    db.record_sign(mid, "OUT", signature=None)
    assert db.get_last_signature(mid) is None


# ── Direction validation ───────────────────────────────────────────────────────

def test_allowed_direction_no_signs_today(db):
    mid = db.upsert_member(_member())
    assert db.get_allowed_direction(mid) == "IN"


def test_allowed_direction_after_sign_in(db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")
    assert db.get_allowed_direction(mid) == "OUT"


def test_allowed_direction_after_am_sign_out(db):
    # A sign-out at any time of day just means they can sign back IN again
    mid = db.upsert_member(_member())
    today = datetime.now().strftime("%Y-%m-%d")
    with db.get_conn() as conn:
        conn.execute(
            "INSERT INTO sign_ins (member_id, direction, timestamp) VALUES (?,?,?)",
            (mid, "OUT", f"{today} 09:30:00"),
        )
    assert db.get_allowed_direction(mid) == "IN"


def test_allowed_direction_after_pm_sign_out(db):
    # No day-complete lockout — a sign-out in the afternoon still allows
    # signing back IN again the same day.
    mid = db.upsert_member(_member())
    today = datetime.now().strftime("%Y-%m-%d")
    with db.get_conn() as conn:
        conn.execute(
            "INSERT INTO sign_ins (member_id, direction, timestamp) VALUES (?,?,?)",
            (mid, "OUT", f"{today} 14:00:00"),
        )
    assert db.get_allowed_direction(mid) == "IN"


def test_allowed_direction_full_day_sequence(db):
    # After any number of IN/OUT cycles in a day, the next allowed direction
    # simply alternates from the last recorded sign — never locked out.
    mid = db.upsert_member(_member())
    today = datetime.now().strftime("%Y-%m-%d")
    with db.get_conn() as conn:
        for direction, ts in [
            ("IN",  f"{today} 08:00:00"),
            ("OUT", f"{today} 11:30:00"),
            ("IN",  f"{today} 13:00:00"),
            ("OUT", f"{today} 15:00:00"),
        ]:
            conn.execute(
                "INSERT INTO sign_ins (member_id, direction, timestamp) VALUES (?,?,?)",
                (mid, direction, ts),
            )
    assert db.get_allowed_direction(mid) == "IN"


def test_allowed_direction_many_cycles_same_day(db):
    # Members and staff alike can sign in/out as many times as they like in
    # a single day, whenever they like — no am/pm restriction.
    mid = db.upsert_member(_member())
    today = datetime.now().strftime("%Y-%m-%d")
    with db.get_conn() as conn:
        for direction, ts in [
            ("IN",  f"{today} 07:00:00"),
            ("OUT", f"{today} 08:00:00"),
            ("IN",  f"{today} 09:00:00"),
            ("OUT", f"{today} 10:00:00"),
            ("IN",  f"{today} 20:00:00"),
            ("OUT", f"{today} 21:00:00"),
        ]:
            conn.execute(
                "INSERT INTO sign_ins (member_id, direction, timestamp) VALUES (?,?,?)",
                (mid, direction, ts),
            )
    assert db.get_allowed_direction(mid) == "IN"


def test_allowed_direction_staff_same_as_member(db):
    # Staff use the exact same unrestricted logic as members.
    sid = db.upsert_member(_staff())
    assert db.get_allowed_direction(sid) == "IN"
    db.record_sign(sid, "IN")
    assert db.get_allowed_direction(sid) == "OUT"
    db.record_sign(sid, "OUT")
    assert db.get_allowed_direction(sid) == "IN"


# ── Admin password ─────────────────────────────────────────────────────────────

def test_check_admin_password_correct(db):
    assert db.check_admin_password("admin1234")


def test_check_admin_password_wrong(db):
    assert not db.check_admin_password("wrongpassword")


def test_set_admin_password(db):
    db.set_admin_password("newpass99")
    assert db.check_admin_password("newpass99")
    assert not db.check_admin_password("admin1234")


# ── Run groups ─────────────────────────────────────────────────────────────────

def test_upsert_and_get_run(db):
    mid1 = db.upsert_member(_member(first_name="A"))
    mid2 = db.upsert_member(_member(first_name="B"))
    rid  = db.upsert_run("Morning Run", [mid1, mid2])
    members = db.get_run_members(rid)
    assert {m["id"] for m in members} == {mid1, mid2}


def test_upsert_run_same_name_replaces_members(db):
    mid1 = db.upsert_member(_member(first_name="A"))
    mid2 = db.upsert_member(_member(first_name="B"))
    mid3 = db.upsert_member(_member(first_name="C"))
    rid  = db.upsert_run("Morning Run", [mid1, mid2])
    db.upsert_run("Morning Run", [mid3])
    members = db.get_run_members(rid)
    assert len(members) == 1
    assert members[0]["id"] == mid3


def test_search_runs(db):
    db.upsert_run("Afternoon Bus", [])
    results = db.search_runs("Afternoon")
    assert any(r["name"] == "Afternoon Bus" for r in results)


def test_delete_run(db):
    mid = db.upsert_member(_member())
    rid = db.upsert_run("Delete Me", [mid])
    db.delete_run(rid)
    assert db.get_run_members(rid) == []


# ── Holiday periods & enrollments ─────────────────────────────────────────────

def test_get_holiday_periods_seeded(db):
    periods = db.get_holiday_periods()
    assert len(periods) == 5
    assert any(p["name"] == "Term 1 Break" for p in periods)


def test_upsert_holiday_enrollment(db):
    mid    = db.upsert_member(_member())
    period = db.get_holiday_periods()[0]
    db.upsert_holiday_enrollment({
        "member_id": mid,
        "period_id": period["id"],
        "days": "Mon,Tue",
        "afternoon_pickup": 1,
        "morning_pickup": 0,
    })
    enroll = db.get_holiday_enrollment(mid, period["id"])
    assert enroll["days"] == "Mon,Tue"
    assert enroll["afternoon_pickup"] == 1


def test_upsert_holiday_enrollment_updates(db):
    mid    = db.upsert_member(_member())
    period = db.get_holiday_periods()[0]
    base   = {"member_id": mid, "period_id": period["id"],
               "days": "Mon", "afternoon_pickup": 0, "morning_pickup": 0}
    db.upsert_holiday_enrollment(base)
    db.upsert_holiday_enrollment({**base, "days": "Mon,Wed", "afternoon_pickup": 1})
    enroll = db.get_holiday_enrollment(mid, period["id"])
    assert enroll["days"] == "Mon,Wed"
    assert enroll["afternoon_pickup"] == 1


def test_delete_holiday_enrollment(db):
    mid    = db.upsert_member(_member())
    period = db.get_holiday_periods()[0]
    db.upsert_holiday_enrollment({
        "member_id": mid, "period_id": period["id"],
        "days": "Mon", "afternoon_pickup": 0, "morning_pickup": 0,
    })
    db.delete_holiday_enrollment(mid, period["id"])
    assert db.get_holiday_enrollment(mid, period["id"]) is None


# ── person_type / staff ────────────────────────────────────────────────────────

def test_upsert_member_defaults_to_member_type(db):
    mid = db.upsert_member(_member())
    assert db.get_member(mid)["person_type"] == "member"


def test_upsert_staff_sets_staff_type(db):
    mid = db.upsert_member(_staff())
    assert db.get_member(mid)["person_type"] == "staff"


def test_upsert_staff_stores_role_in_school_column(db):
    mid = db.upsert_member(_staff(school="Senior Coordinator"))
    assert db.get_member(mid)["school"] == "Senior Coordinator"


def test_update_member_does_not_change_person_type(db):
    # Editing an existing record via upsert_member must not flip person_type
    mid = db.upsert_member(_staff())
    db.upsert_member({**_member(), "id": mid})   # _member() has no person_type key
    assert db.get_member(mid)["person_type"] == "staff"


def test_search_members_with_member_filter_excludes_staff(db):
    db.upsert_member(_staff(first_name="StaffOnly"))
    results = db.search_members("StaffOnly", "member")
    assert results == []


def test_search_members_with_staff_filter_excludes_members(db):
    db.upsert_member(_member(first_name="MemberOnly"))
    results = db.search_members("MemberOnly", "staff")
    assert results == []


def test_search_members_no_filter_returns_both_types(db):
    db.upsert_member(_member(first_name="AMember"))
    db.upsert_member(_staff(first_name="AStaff"))
    all_results = db.search_members("A")
    names = [r["first_name"] for r in all_results]
    assert "AMember" in names
    assert "AStaff" in names


def test_search_staff_returns_only_staff(db):
    db.upsert_member(_member(first_name="RegMember"))
    sid = db.upsert_member(_staff(first_name="RegStaff"))
    results = db.search_staff("Reg")
    assert all(r["person_type"] == "staff" for r in results)
    assert any(r["id"] == sid for r in results)
    assert not any(r["first_name"] == "RegMember" for r in results)


def test_get_signs_for_export_excludes_staff_sign_ins(db):
    member_id = db.upsert_member(_member())
    staff_id  = db.upsert_member(_staff())
    db.record_sign(member_id, "IN")
    db.record_sign(staff_id,  "IN")
    today = datetime.now().strftime("%Y-%m-%d")
    signs = db.get_signs_for_export(today, today)
    ids = [s["member_id"] for s in signs]
    assert member_id in ids
    assert staff_id  not in ids


def test_get_staff_signs_for_export_excludes_member_sign_ins(db):
    member_id = db.upsert_member(_member())
    staff_id  = db.upsert_member(_staff())
    db.record_sign(member_id, "IN")
    db.record_sign(staff_id,  "IN")
    today = datetime.now().strftime("%Y-%m-%d")
    signs = db.get_staff_signs_for_export(today, today)
    ids = [s["member_id"] for s in signs]
    assert staff_id  in ids
    assert member_id not in ids


def test_get_staff_signs_for_export_includes_role_field(db):
    sid = db.upsert_member(_staff(school="Coordinator"))
    db.record_sign(sid, "IN")
    today = datetime.now().strftime("%Y-%m-%d")
    signs = db.get_staff_signs_for_export(today, today)
    assert signs[0]["role"] == "Coordinator"


def test_get_staff_signs_for_export_excludes_outside_range(db):
    sid = db.upsert_member(_staff())
    db.record_sign(sid, "IN")
    signs = db.get_staff_signs_for_export("2000-01-01", "2000-01-02")
    assert not any(s["member_id"] == sid for s in signs)
