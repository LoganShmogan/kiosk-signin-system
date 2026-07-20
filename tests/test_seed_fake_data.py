"""
Tests for seed_fake_data.py — the dummy-data generator used to populate this
machine's dev database. Focused on the parts that changed for the staff
sign-in/out rework: unrestricted, varied-time, multi-session staff days
(including the occasional forgotten sign-out), and safe re-running.
"""
import random
from datetime import date, datetime

import seed_fake_data
from helpers import member as _member


# ── _staff_day_sessions ──────────────────────────────────────────────────────

def test_staff_day_sessions_returns_events_for_the_given_day():
    random.seed(1)
    day = date(2026, 6, 8)
    events = seed_fake_data._staff_day_sessions(day)
    assert events
    assert all(when.date() == day for _direction, when in events)


def test_staff_day_sessions_chronologically_ordered():
    random.seed(2)
    day = date(2026, 6, 8)
    events = seed_fake_data._staff_day_sessions(day)
    timestamps = [when for _direction, when in events]
    assert timestamps == sorted(timestamps)


def test_staff_day_sessions_between_one_and_three_sessions():
    day = date(2026, 6, 8)
    for seed in range(100):
        random.seed(seed)
        events = seed_fake_data._staff_day_sessions(day)
        in_count = sum(1 for direction, _when in events if direction == "IN")
        assert 1 <= in_count <= 3


def test_staff_day_sessions_at_most_one_dangling_in():
    """Only the final session of a day may be left open (a forgotten
    sign-out) — every earlier session must have a matching OUT."""
    day = date(2026, 6, 8)
    for seed in range(100):
        random.seed(seed)
        events = seed_fake_data._staff_day_sessions(day)
        directions = [d for d, _when in events]
        in_count, out_count = directions.count("IN"), directions.count("OUT")
        assert in_count - out_count in (0, 1)
        if in_count - out_count == 1:
            assert directions[-1] == "IN"   # the dangling one is the last event


def test_staff_day_sessions_alternates_in_out():
    day = date(2026, 6, 8)
    for seed in range(100):
        random.seed(seed)
        events = seed_fake_data._staff_day_sessions(day)
        directions = [d for d, _when in events]
        for i in range(0, len(directions) - 1, 2):
            assert directions[i] == "IN"
        # every OUT immediately follows its IN
        for i, d in enumerate(directions):
            if d == "OUT":
                assert directions[i - 1] == "IN"


def test_staff_day_sessions_sometimes_produces_multiple_sessions():
    day = date(2026, 6, 8)
    multi_session_seen = False
    for seed in range(200):
        random.seed(seed)
        events = seed_fake_data._staff_day_sessions(day)
        if sum(1 for d, _w in events if d == "IN") > 1:
            multi_session_seen = True
            break
    assert multi_session_seen


def test_staff_day_sessions_sometimes_leaves_a_session_open():
    """Regression guard for the 'Still signed in' / forgotten-sign-out case
    the new staff export needs dummy data to exercise."""
    day = date(2026, 6, 8)
    open_session_seen = False
    for seed in range(200):
        random.seed(seed)
        events = seed_fake_data._staff_day_sessions(day)
        directions = [d for d, _w in events]
        if directions and directions[-1] == "IN" and directions.count("IN") > directions.count("OUT"):
            open_session_seen = True
            break
    assert open_session_seen


# ── _clear_previous_fake_data ────────────────────────────────────────────────

def test_clear_previous_fake_data_removes_only_fake_named(db):
    fake_id = db.upsert_member(_member(first_name="Fake", last_name="Previous"))
    db.record_sign(fake_id, "IN")
    real_id = db.upsert_member(_member(first_name="Real", last_name="Person"))

    seed_fake_data._clear_previous_fake_data()

    assert db.get_member(fake_id) is None
    assert db.get_member(real_id) is not None


def test_clear_previous_fake_data_is_safe_when_nothing_to_clear(db):
    real_id = db.upsert_member(_member(first_name="Real", last_name="Person"))
    seed_fake_data._clear_previous_fake_data()   # must not raise
    assert db.get_member(real_id) is not None


# ── Full seeding run (integration) ───────────────────────────────────────────

def test_seed_run_is_idempotent(db):
    """Running the seeding helpers twice must not duplicate fake people."""
    with db.get_conn() as conn:
        seed_fake_data._clear_previous_fake_data()
        member_ids_1 = seed_fake_data._seed_members(conn)
        staff_ids_1 = seed_fake_data._seed_staff(conn)

    seed_fake_data._clear_previous_fake_data()
    with db.get_conn() as conn:
        member_ids_2 = seed_fake_data._seed_members(conn)
        staff_ids_2 = seed_fake_data._seed_staff(conn)

    assert len(member_ids_1) == len(member_ids_2)
    assert len(staff_ids_1) == len(staff_ids_2)
    with db.get_conn() as c:
        total_fake = c.execute(
            "SELECT COUNT(*) c FROM members WHERE first_name='Fake'"
        ).fetchone()["c"]
    assert total_fake == len(member_ids_2) + len(staff_ids_2)


def test_seed_history_gives_staff_multiple_sessions_on_some_day(db):
    """Regression guard: the seeded staff history must actually exercise the
    new unrestricted, multi-session-per-day behaviour, not the old fixed
    single AM/PM shift."""
    random.seed(7)
    with db.get_conn() as conn:
        member_ids = seed_fake_data._seed_members(conn)
        staff_ids = seed_fake_data._seed_staff(conn)
        seed_fake_data._seed_history(conn, member_ids, staff_ids)

    signs = db.get_staff_signs_for_export("2000-01-01", "2100-01-01")
    assert signs

    from collections import defaultdict
    by_person_day = defaultdict(int)
    for s in signs:
        if s["direction"] == "IN":
            by_person_day[(s["member_id"], s["timestamp"][:10])] += 1

    assert any(count > 1 for count in by_person_day.values())
