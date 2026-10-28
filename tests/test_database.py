"""
Tests for database.py — all tests use a fresh temp DB via the db fixture.
"""
from datetime import datetime, timedelta
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


def test_delete_member_unlinks_dashboard_user(db):
    mid = db.upsert_member(_member())
    uid = db.create_dashboard_user("linked", "1234", "staff", member_id=mid)
    db.delete_member(mid)
    assert db.get_member(mid) is None
    user = db.get_dashboard_user(uid)
    assert user is not None
    assert user["member_id"] is None


def test_delete_member_cascades_signs(db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")
    db.delete_member(mid)
    assert db.get_last_sign(mid) is None


# ── PIN ────────────────────────────────────────────────────────────────────────

def test_verify_pin_unknown_member_returns_false(db):
    assert db.verify_pin(99999, "1234") is False


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


def test_get_sign_returns_record_with_member_name(db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")
    sign_id = db.get_today_signs()[0]["id"]
    sign = db.get_sign(sign_id)
    assert sign["member_id"] == mid
    assert sign["first_name"] == "Jane"


def test_get_sign_unknown_id_returns_none(db):
    assert db.get_sign(999999) is None


def test_update_sign_time_changes_timestamp(db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")
    sign_id = db.get_today_signs()[0]["id"]
    db.update_sign_time(sign_id, "2026-05-01 08:15:00")
    assert db.get_sign(sign_id)["timestamp"] == "2026-05-01 08:15:00"


def test_add_sign_inserts_record_at_given_timestamp(db):
    mid = db.upsert_member(_member())
    sign_id = db.add_sign(mid, "OUT", "2026-05-01 17:30:00")
    sign = db.get_sign(sign_id)
    assert sign["member_id"] == mid
    assert sign["direction"] == "OUT"
    assert sign["timestamp"] == "2026-05-01 17:30:00"


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


def test_set_admin_password_uses_salted_hash(db):
    db.set_admin_password("newpass99")
    with db.get_conn() as conn:
        stored = conn.execute("SELECT password_hash FROM admins WHERE username='admin'").fetchone()[0]
    assert ":" in stored


def _seed_legacy_admin_hash(db, password):
    import hashlib
    h = hashlib.sha256(password.encode()).hexdigest()
    with db.get_conn() as conn:
        conn.execute("UPDATE admins SET password_hash=? WHERE username='admin'", (h,))


def test_check_admin_password_legacy_hash_still_authenticates(db):
    _seed_legacy_admin_hash(db, "oldstylepass")
    assert db.check_admin_password("oldstylepass")


def test_check_admin_password_legacy_hash_wrong_password_stays_legacy(db):
    _seed_legacy_admin_hash(db, "oldstylepass")
    assert not db.check_admin_password("wrongpassword")
    with db.get_conn() as conn:
        stored = conn.execute("SELECT password_hash FROM admins WHERE username='admin'").fetchone()[0]
    assert ":" not in stored


def test_check_admin_password_legacy_hash_upgrades_on_success(db):
    _seed_legacy_admin_hash(db, "oldstylepass")
    assert db.check_admin_password("oldstylepass")
    with db.get_conn() as conn:
        stored = conn.execute("SELECT password_hash FROM admins WHERE username='admin'").fetchone()[0]
    assert ":" in stored
    assert db.check_admin_password("oldstylepass")  # still works after the upgrade


def test_check_admin_password_no_admin_row_returns_false(db):
    with db.get_conn() as conn:
        conn.execute("DELETE FROM admins")
    assert not db.check_admin_password("anything")


# ── Dashboard users ───────────────────────────────────────────────────────────

def test_validate_dashboard_password_too_short(db):
    assert db.validate_dashboard_password("Ab1!") is not None


def test_validate_dashboard_password_missing_digit(db):
    assert db.validate_dashboard_password("NoDigits!!!") is not None


def test_validate_dashboard_password_missing_special_char(db):
    assert db.validate_dashboard_password("NoSpecial123") is not None


def test_validate_dashboard_password_valid(db):
    assert db.validate_dashboard_password("Valid1Password!") is None

def test_init_seeds_default_dashboard_admin(db):
    user = db.check_dashboard_login("admin", "1234")
    assert user is not None
    assert user["role"] == "admin"


def test_create_dashboard_user(db):
    uid = db.create_dashboard_user("Jamie", "2468", "staff")
    assert uid is not None
    user = db.get_dashboard_user(uid)
    assert user["name"] == "Jamie"
    assert user["role"] == "staff"


def test_create_dashboard_user_duplicate_name_returns_none(db):
    db.create_dashboard_user("Jamie", "2468", "staff")
    assert db.create_dashboard_user("Jamie", "9999", "staff") is None


def test_check_dashboard_login_correct_pin(db):
    db.create_dashboard_user("Jamie", "2468", "staff")
    user = db.check_dashboard_login("Jamie", "2468")
    assert user is not None
    assert user["name"] == "Jamie"


def test_check_dashboard_login_wrong_pin(db):
    db.create_dashboard_user("Jamie", "2468", "staff")
    assert db.check_dashboard_login("Jamie", "wrong") is None


def test_check_dashboard_login_unknown_name(db):
    assert db.check_dashboard_login("nobody", "1234") is None


def test_get_dashboard_user_unknown_returns_none(db):
    assert db.get_dashboard_user(999999) is None


def test_list_dashboard_users_ordered_by_name(db):
    db.create_dashboard_user("Zack", "1111", "staff")
    db.create_dashboard_user("Amy", "2222", "staff")
    names = [u["name"] for u in db.list_dashboard_users()]
    assert names == sorted(names)


def test_delete_dashboard_user(db):
    uid = db.create_dashboard_user("Jamie", "2468", "staff")
    db.delete_dashboard_user(uid)
    assert db.get_dashboard_user(uid) is None


def test_set_dashboard_user_pin(db):
    uid = db.create_dashboard_user("Jamie", "2468", "staff")
    db.set_dashboard_user_pin(uid, "1357")
    assert db.check_dashboard_login("Jamie", "1357") is not None
    assert db.check_dashboard_login("Jamie", "2468") is None


def test_create_dashboard_user_with_member_id(db):
    mid = db.upsert_member(_staff())
    uid = db.create_dashboard_user("Jamie", "2468", "staff", mid)
    assert db.get_dashboard_user(uid)["member_id"] == mid


def test_create_dashboard_user_without_member_id_defaults_none(db):
    uid = db.create_dashboard_user("Jamie", "2468", "staff")
    assert db.get_dashboard_user(uid)["member_id"] is None


def test_update_dashboard_user_renames_and_relinks(db):
    mid = db.upsert_member(_staff())
    uid = db.create_dashboard_user("Jamie", "2468", "staff")
    assert db.update_dashboard_user(uid, "James", "staff", mid) is True
    user = db.get_dashboard_user(uid)
    assert user["name"] == "James"
    assert user["member_id"] == mid


def test_update_dashboard_user_does_not_touch_password(db):
    uid = db.create_dashboard_user("Jamie", "2468", "staff")
    db.update_dashboard_user(uid, "James", "staff", None)
    assert db.check_dashboard_login("James", "2468") is not None


def test_update_dashboard_user_duplicate_name_returns_false(db):
    db.create_dashboard_user("Amy", "2222", "staff")
    uid = db.create_dashboard_user("Jamie", "2468", "staff")
    assert db.update_dashboard_user(uid, "Amy", "staff", None) is False
    assert db.get_dashboard_user(uid)["name"] == "Jamie"


def test_update_dashboard_user_unknown_id_returns_false(db):
    assert db.update_dashboard_user(999999, "Ghost", "staff", None) is False


def test_check_dashboard_login_increments_failed_attempts(db):
    db.create_dashboard_user("Jamie", "2468", "staff")
    db.check_dashboard_login("Jamie", "wrong")
    with db.get_conn() as conn:
        attempts = conn.execute("SELECT failed_attempts FROM dashboard_users WHERE name='Jamie'").fetchone()[0]
    assert attempts == 1


def test_check_dashboard_login_locks_after_threshold(db):
    db.create_dashboard_user("Jamie", "2468", "staff")
    for _ in range(db.LOCKOUT_THRESHOLD):
        db.check_dashboard_login("Jamie", "wrong")
    assert db.is_dashboard_user_locked("Jamie") is True


def test_check_dashboard_login_success_resets_failed_attempts(db):
    db.create_dashboard_user("Jamie", "2468", "staff")
    db.check_dashboard_login("Jamie", "wrong")
    db.check_dashboard_login("Jamie", "2468")
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT failed_attempts, locked_until FROM dashboard_users WHERE name='Jamie'"
        ).fetchone()
    assert row["failed_attempts"] == 0
    assert row["locked_until"] is None


def test_is_dashboard_user_locked_false_for_unknown_name(db):
    assert db.is_dashboard_user_locked("nobody") is False


def test_is_dashboard_user_locked_false_when_not_locked(db):
    db.create_dashboard_user("Jamie", "2468", "staff")
    assert db.is_dashboard_user_locked("Jamie") is False


def test_is_dashboard_user_locked_false_after_expiry(db):
    db.create_dashboard_user("Jamie", "2468", "staff")
    past = (datetime.now() - timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")
    with db.get_conn() as conn:
        conn.execute("UPDATE dashboard_users SET locked_until=? WHERE name='Jamie'", (past,))
    assert db.is_dashboard_user_locked("Jamie") is False


def test_get_signs_for_member_includes_id_and_notes(db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN", notes="test note")
    signs = db.get_signs_for_member(mid)
    assert signs[0]["id"] is not None
    assert signs[0]["notes"] == "test note"


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


def test_get_run_returns_dict(db):
    rid = db.upsert_run("Morning Run", [])
    run = db.get_run(rid)
    assert run["name"] == "Morning Run"


def test_get_run_unknown_returns_none(db):
    assert db.get_run(99999) is None


def test_list_runs_includes_member_count(db):
    mid1 = db.upsert_member(_member(first_name="A"))
    mid2 = db.upsert_member(_member(first_name="B"))
    rid = db.upsert_run("Morning Run", [mid1, mid2])
    runs = {r["id"]: r for r in db.list_runs()}
    assert runs[rid]["member_count"] == 2


def test_list_runs_zero_members(db):
    rid = db.upsert_run("Empty Run", [])
    runs = {r["id"]: r for r in db.list_runs()}
    assert runs[rid]["member_count"] == 0


def test_list_runs_filters_by_query(db):
    db.upsert_run("Morning Run", [])
    db.upsert_run("Afternoon Bus", [])
    results = db.list_runs("Morning")
    assert [r["name"] for r in results] == ["Morning Run"]


def test_create_run_inserts_and_logs(db):
    mid = db.upsert_member(_member())
    rid = db.create_run("New Run", [mid])
    assert rid is not None
    assert {m["id"] for m in db.get_run_members(rid)} == {mid}
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM audit_log WHERE event_type='RUN_CREATED' AND description LIKE '%New Run%'"
        ).fetchone()
    assert row is not None


def test_create_run_duplicate_name_returns_none(db):
    db.upsert_run("Taken Name", [])
    assert db.create_run("Taken Name", []) is None


def test_update_run_renames_and_replaces_members(db):
    mid1 = db.upsert_member(_member(first_name="A"))
    mid2 = db.upsert_member(_member(first_name="B"))
    rid = db.upsert_run("Old Name", [mid1])
    assert db.update_run(rid, "New Name", [mid2]) is True
    run = db.get_run(rid)
    assert run["name"] == "New Name"
    assert {m["id"] for m in db.get_run_members(rid)} == {mid2}


def test_update_run_logs_event(db):
    rid = db.upsert_run("Old Name", [])
    db.update_run(rid, "New Name", [])
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM audit_log WHERE event_type='RUN_UPDATED' AND description LIKE '%New Name%'"
        ).fetchone()
    assert row is not None


def test_update_run_duplicate_name_returns_false(db):
    db.upsert_run("Existing Run", [])
    rid = db.upsert_run("Renamed Run", [])
    assert db.update_run(rid, "Existing Run", []) is False
    assert db.get_run(rid)["name"] == "Renamed Run"


def test_update_run_unknown_id_returns_false(db):
    assert db.update_run(99999, "Ghost Run", []) is False


def test_upsert_run_logs_created_event(db):
    db.upsert_run("Brand New Run", [])
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM audit_log WHERE event_type='RUN_CREATED' AND description LIKE '%Brand New Run%'"
        ).fetchone()
    assert row is not None


def test_upsert_run_logs_updated_event(db):
    db.upsert_run("Repeat Run", [])
    db.upsert_run("Repeat Run", [])
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_log WHERE event_type='RUN_UPDATED' AND description LIKE '%Repeat Run%'"
        ).fetchall()
    assert len(rows) == 1


def test_delete_run_logs_event(db):
    rid = db.upsert_run("Doomed Run", [])
    db.delete_run(rid)
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM audit_log WHERE event_type='RUN_DELETED' AND description LIKE '%Doomed Run%'"
        ).fetchone()
    assert row is not None


def test_delete_run_unknown_id_no_error(db):
    db.delete_run(99999)  # must not raise
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM audit_log WHERE event_type='RUN_DELETED'"
        ).fetchone()
    assert row is None


def test_get_currently_signed_in_includes_id(db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")
    signed_in = db.get_currently_signed_in()
    assert len(signed_in) == 1
    assert signed_in[0]["id"] == mid


def test_get_currently_signed_in_excludes_signed_out(db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")
    db.record_sign(mid, "OUT")
    assert db.get_currently_signed_in() == []


def test_get_currently_signed_in_empty(db):
    assert db.get_currently_signed_in() == []


# ── Removed holiday enrolment tables ──────────────────────────────────────────

def test_init_db_drops_holiday_tables(db):
    with db.get_conn() as conn:
        conn.execute("CREATE TABLE holiday_periods (id INTEGER PRIMARY KEY)")
        conn.execute("CREATE TABLE holiday_enrollments (id INTEGER PRIMARY KEY)")
    db.init_db()
    with db.get_conn() as conn:
        names = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    assert "holiday_periods" not in names
    assert "holiday_enrollments" not in names


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


# ── log_event resilience ─────────────────────────────────────────────────────

def test_log_event_swallows_errors_instead_of_raising(db):
    # A non-connection object raises AttributeError on .execute(); log_event
    # must not let that propagate, since audit logging is best-effort and
    # should never break the operation it's logging.
    db.log_event("TEST_EVENT", "should not raise", conn="not-a-real-connection")


def test_log_event_without_conn_still_records(db):
    db.log_event("TEST_EVENT", "recorded via its own connection")
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM audit_log WHERE event_type='TEST_EVENT'"
        ).fetchone()
    assert row is not None
    assert row["description"] == "recorded via its own connection"


# ── Schema migration ─────────────────────────────────────────────────────────

def test_init_db_is_idempotent(db):
    # Re-running init_db() on an already-migrated database must not raise
    # (the ALTER TABLE ... ADD COLUMN calls hit "column already exists" on a
    # second run, which is caught) and must not disturb existing data.
    mid = db.upsert_member(_member(first_name="Persists"))
    db.init_db()
    db.init_db()
    m = db.get_member(mid)
    assert m is not None
    assert m["first_name"] == "Persists"
    assert m["person_type"] == "member"


# ── Alerts ────────────────────────────────────────────────────────────────────

def test_create_alert_scope_all(db):
    alert_id = db.create_alert("all", None, "Centre closed tomorrow")
    alerts = db.get_alerts()
    assert any(a["id"] == alert_id and a["scope"] == "all" for a in alerts)


def test_create_alert_scope_member(db):
    mid = db.upsert_member(_member())
    alert_id = db.create_alert("member", mid, "Reminder for this member")
    alert = next(a for a in db.get_alerts() if a["id"] == alert_id)
    assert alert["scope"] == "member"
    assert alert["target_id"] == mid


def test_create_alert_scope_run(db):
    mid = db.upsert_member(_member())
    run_id = db.upsert_run("Test Run", [mid])
    alert_id = db.create_alert("run", run_id, "Run-specific alert")
    alert = next(a for a in db.get_alerts() if a["id"] == alert_id)
    assert alert["scope"] == "run"
    assert alert["target_id"] == run_id


def test_create_alert_without_duration_never_expires(db):
    alert_id = db.create_alert("all", None, "No expiry")
    alert = next(a for a in db.get_alerts() if a["id"] == alert_id)
    assert alert["expires_at"] is None


def test_create_alert_with_duration_sets_future_expiry(db):
    alert_id = db.create_alert("all", None, "Expires soon", duration_hours=1)
    alert = next(a for a in db.get_alerts(include_expired=True) if a["id"] == alert_id)
    assert alert["expires_at"] is not None
    assert alert["expires_at"] > datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def test_get_alerts_excludes_already_expired_by_default(db):
    alert_id = db.create_alert("all", None, "Already expired", duration_hours=-1)
    alerts = db.get_alerts()
    assert not any(a["id"] == alert_id for a in alerts)


def test_get_alerts_include_expired_true_shows_expired(db):
    alert_id = db.create_alert("all", None, "Already expired", duration_hours=-1)
    alerts = db.get_alerts(include_expired=True)
    assert any(a["id"] == alert_id for a in alerts)


def test_delete_alert(db):
    alert_id = db.create_alert("all", None, "To be deleted")
    db.delete_alert(alert_id)
    assert not any(a["id"] == alert_id for a in db.get_alerts(include_expired=True))


def test_get_alerts_for_members_empty_list_returns_empty(db):
    assert db.get_alerts_for_members([]) == []


def test_get_alerts_for_members_scope_all_matches_any_member(db):
    mid = db.upsert_member(_member())
    db.create_alert("all", None, "Everyone sees this")
    alerts = db.get_alerts_for_members([mid])
    assert any(a["scope"] == "all" for a in alerts)


def test_get_alerts_for_members_scope_member_matches_only_that_member(db):
    mid1 = db.upsert_member(_member(first_name="Target"))
    mid2 = db.upsert_member(_member(first_name="Other"))
    db.create_alert("member", mid1, "Just for Target")
    alerts1 = db.get_alerts_for_members([mid1])
    alerts2 = db.get_alerts_for_members([mid2])
    assert any(a["message"] == "Just for Target" for a in alerts1)
    assert not any(a["message"] == "Just for Target" for a in alerts2)


def test_get_alerts_for_members_scope_run_matches_run_members(db):
    mid_in_run = db.upsert_member(_member(first_name="InRun"))
    mid_outside = db.upsert_member(_member(first_name="Outside"))
    run_id = db.upsert_run("Alert Run", [mid_in_run])
    db.create_alert("run", run_id, "Run alert")

    alerts_in = db.get_alerts_for_members([mid_in_run])
    alerts_out = db.get_alerts_for_members([mid_outside])
    assert any(a["message"] == "Run alert" for a in alerts_in)
    assert not any(a["message"] == "Run alert" for a in alerts_out)


def test_get_alerts_for_members_excludes_expired(db):
    mid = db.upsert_member(_member())
    db.create_alert("member", mid, "Expired alert", duration_hours=-1)
    alerts = db.get_alerts_for_members([mid])
    assert not any(a["message"] == "Expired alert" for a in alerts)


def test_get_sign_neighbours_unknown_id_returns_none_pair(db):
    assert db.get_sign_neighbours(999999) == (None, None)


def test_delete_signs_empty_list_is_noop(db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")
    db.delete_signs([])
    assert len(db.get_today_signs()) == 1
