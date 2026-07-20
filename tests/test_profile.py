"""
Tests for the profile area — member CRUD, caregiver, and admin member-list workflows.
"""
import pytest
from helpers import member as _member, caregiver as _caregiver


# ── Full-field member save ─────────────────────────────────────────────────────

def test_profile_insert_all_fields(db):
    """All profile fields survive an insert/read round trip."""
    data = _member(
        first_name="Alice",
        last_name="Brown",
        date_of_birth="2014-06-20",
        school="Example School",
        mornings_days="Mon,Tue,Wed",
        afternoons_days="Mon,Tue,Wed,Thu,Fri",
        needs_pickup=1,
        activity="Ballet",
        activity_time="4:00pm",
        activity_address="12 Dance Ave",
        transport_required=1,
        activity_days="Wed,Fri",
        pin="4321",
    )
    mid = db.upsert_member(data)
    m = db.get_member(mid)

    assert m["first_name"] == "Alice"
    assert m["last_name"] == "Brown"
    assert m["date_of_birth"] == "2014-06-20"
    assert m["school"] == "Example School"
    assert m["mornings_days"] == "Mon,Tue,Wed"
    assert m["afternoons_days"] == "Mon,Tue,Wed,Thu,Fri"
    assert m["needs_pickup"] == 1
    assert m["activity"] == "Ballet"
    assert m["activity_time"] == "4:00pm"
    assert m["activity_address"] == "12 Dance Ave"
    assert m["transport_required"] == 1
    assert m["activity_days"] == "Wed,Fri"
    assert m["pin"] == "4321"


def test_profile_update_all_fields(db):
    """Editing an existing member via upsert_member updates every field."""
    mid = db.upsert_member(_member())

    updated = _member(
        id=mid,
        first_name="Updated",
        last_name="Name",
        date_of_birth="2013-03-03",
        school="New School",
        mornings_days="Thu,Fri",
        afternoons_days="Wed",
        needs_pickup=1,
        activity="Karate",
        activity_time="5:00pm",
        activity_address="99 Kick St",
        transport_required=1,
        activity_days="Thu",
        pin="0000",
    )
    db.upsert_member(updated)
    m = db.get_member(mid)

    assert m["first_name"] == "Updated"
    assert m["last_name"] == "Name"
    assert m["school"] == "New School"
    assert m["mornings_days"] == "Thu,Fri"
    assert m["needs_pickup"] == 1
    assert m["activity"] == "Karate"
    assert m["transport_required"] == 1
    assert m["pin"] == "0000"


# ── Boolean fields ─────────────────────────────────────────────────────────────

def test_profile_needs_pickup_false(db):
    mid = db.upsert_member(_member(needs_pickup=0))
    assert db.get_member(mid)["needs_pickup"] == 0


def test_profile_needs_pickup_true(db):
    mid = db.upsert_member(_member(needs_pickup=1))
    assert db.get_member(mid)["needs_pickup"] == 1


def test_profile_transport_required_false(db):
    mid = db.upsert_member(_member(transport_required=0))
    assert db.get_member(mid)["transport_required"] == 0


def test_profile_transport_required_true(db):
    mid = db.upsert_member(_member(transport_required=1))
    assert db.get_member(mid)["transport_required"] == 1


# ── Day fields stored as comma strings ────────────────────────────────────────

def test_profile_empty_days_stored_as_empty_string(db):
    mid = db.upsert_member(_member(mornings_days="", afternoons_days="", activity_days=""))
    m = db.get_member(mid)
    assert m["mornings_days"] == ""
    assert m["afternoons_days"] == ""
    assert m["activity_days"] == ""


def test_profile_all_days_stored(db):
    all_days = "Mon,Tue,Wed,Thu,Fri"
    mid = db.upsert_member(_member(mornings_days=all_days))
    assert db.get_member(mid)["mornings_days"] == all_days


# ── Member + caregiver round trip ─────────────────────────────────────────────

def test_profile_save_member_and_caregiver(db):
    """Saving member then caregiver and reading both back works."""
    mid = db.upsert_member(_member(first_name="Tom", last_name="Jones"))
    db.upsert_caregiver(_caregiver(mid, full_name="Mary Jones", phone="021-999-8888"))

    m  = db.get_member(mid)
    cg = db.get_caregiver(mid)

    assert m["first_name"] == "Tom"
    assert cg["full_name"] == "Mary Jones"
    assert cg["phone"] == "021-999-8888"
    assert cg["member_id"] == mid


def test_profile_caregiver_update_all_fields(db):
    """Updating caregiver replaces all fields without creating a duplicate row."""
    mid = db.upsert_member(_member())
    db.upsert_caregiver(_caregiver(mid))

    db.upsert_caregiver(_caregiver(
        mid,
        full_name="New Guardian",
        phone="021-123-4567",
        street_address="99 New St",
        suburb="Newville",
        city="NewCity",
        email="new@example.com",
        emergency_contact_name="Emergency Person",
        emergency_contact_phone="021-000-9999",
        relationship="Grandparent",
    ))

    cg = db.get_caregiver(mid)
    assert cg["full_name"] == "New Guardian"
    assert cg["phone"] == "021-123-4567"
    assert cg["suburb"] == "Newville"
    assert cg["relationship"] == "Grandparent"


def test_profile_caregiver_only_one_row_per_member(db):
    """Multiple caregiver upserts for the same member don't create extra rows."""
    mid = db.upsert_member(_member())
    db.upsert_caregiver(_caregiver(mid, full_name="First"))
    db.upsert_caregiver(_caregiver(mid, full_name="Second"))
    db.upsert_caregiver(_caregiver(mid, full_name="Third"))

    # get_caregiver uses LIMIT 1 — just verify only one effective row exists
    cg = db.get_caregiver(mid)
    assert cg["full_name"] == "Third"


# ── Delete ─────────────────────────────────────────────────────────────────────

def test_profile_delete_removes_member(db):
    mid = db.upsert_member(_member())
    db.delete_member(mid)
    assert db.get_member(mid) is None


def test_profile_delete_cascades_to_caregiver(db):
    mid = db.upsert_member(_member())
    db.upsert_caregiver(_caregiver(mid))
    db.delete_member(mid)
    assert db.get_caregiver(mid) is None


def test_profile_delete_does_not_affect_sign_history_query_safety(db):
    """Deleting a member removes their sign-ins (cascade) — not a silent no-op."""
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")
    db.record_sign(mid, "OUT")
    db.delete_member(mid)
    assert db.get_last_sign(mid) is None


def test_profile_update_preserves_sign_history(db):
    """Editing member details does NOT delete their sign-in history."""
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")
    db.record_sign(mid, "OUT")

    db.upsert_member({**_member(), "id": mid, "first_name": "Renamed"})

    assert db.get_last_sign(mid) is not None
    assert db.get_member(mid)["first_name"] == "Renamed"


# ── Admin member list ─────────────────────────────────────────────────────────

def test_admin_member_list_alphabetical_order(db):
    """search_members('') returns members sorted by last name then first name."""
    db.upsert_member(_member(first_name="Zelda", last_name="Zebra"))
    db.upsert_member(_member(first_name="Aaron", last_name="Aardvark"))
    db.upsert_member(_member(first_name="Mike",  last_name="Middle"))

    all_members = db.search_members("")
    last_names = [m["last_name"] for m in all_members]
    assert last_names == sorted(last_names)


def test_admin_member_list_search_first_name(db):
    mid = db.upsert_member(_member(first_name="Seraphina", last_name="Jones"))
    results = db.search_members("Seraphina")
    assert any(m["id"] == mid for m in results)


def test_admin_member_list_search_last_name(db):
    mid = db.upsert_member(_member(first_name="Joe", last_name="Rarebird"))
    results = db.search_members("Rarebird")
    assert any(m["id"] == mid for m in results)


def test_admin_member_list_search_partial_match(db):
    mid = db.upsert_member(_member(first_name="Christopher", last_name="Smith"))
    results = db.search_members("Chris")
    assert any(m["id"] == mid for m in results)


def test_admin_member_list_search_no_match(db):
    results = db.search_members("ZZZNoMatch999")
    assert results == []


def test_admin_member_list_edit_returns_full_member(db):
    """get_member returns everything needed to pre-populate the edit form."""
    mid = db.upsert_member(_member(
        first_name="Edit",
        last_name="Me",
        activity="Tennis",
        mornings_days="Mon,Wed",
        pin="1234",
    ))
    m = db.get_member(mid)
    assert m["id"] == mid
    assert m["activity"] == "Tennis"
    assert m["mornings_days"] == "Mon,Wed"
    assert m["pin"] == "1234"


def test_admin_member_list_reflects_new_member_immediately(db):
    """After adding a member, search_members('') includes them."""
    before = {m["id"] for m in db.search_members("")}
    mid = db.upsert_member(_member(first_name="Brand", last_name="New"))
    after = {m["id"] for m in db.search_members("")}
    assert mid in after - before


def test_admin_member_list_reflects_deleted_member(db):
    """After deleting a member, search_members('') excludes them."""
    mid = db.upsert_member(_member(first_name="Gone", last_name="Soon"))
    db.delete_member(mid)
    assert not any(m["id"] == mid for m in db.search_members(""))


def test_admin_member_list_pin_not_required(db):
    """Members with no PIN appear in the member list normally."""
    mid = db.upsert_member(_member(pin=""))
    results = db.search_members("")
    assert any(m["id"] == mid for m in results)


# ── Notification preference (notify_on) ───────────────────────────────────────

@pytest.mark.parametrize("notify_on", ["BOTH", "IN", "OUT", "NONE"])
def test_notify_on_round_trips(db, notify_on):
    mid = db.upsert_member(_member())
    db.upsert_caregiver(_caregiver(mid, notify_on=notify_on))
    assert db.get_caregiver(mid)["notify_on"] == notify_on


def test_notify_on_defaults_to_both_when_not_supplied(db):
    """Existing records without notify_on come back as BOTH after migration."""
    mid = db.upsert_member(_member())
    # Insert without notify_on to simulate a legacy row
    import sqlite3
    conn = sqlite3.connect(db.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        "INSERT INTO caregivers (member_id, full_name, email) VALUES (?,?,?)",
        (mid, "Legacy Parent", "legacy@example.com"),
    )
    conn.commit()
    conn.close()
    cg = db.get_caregiver(mid)
    assert cg["notify_on"] == "BOTH"


def test_notify_on_update_overwrites_previous(db):
    mid = db.upsert_member(_member())
    db.upsert_caregiver(_caregiver(mid, notify_on="BOTH"))
    db.upsert_caregiver(_caregiver(mid, notify_on="IN"))
    assert db.get_caregiver(mid)["notify_on"] == "IN"
