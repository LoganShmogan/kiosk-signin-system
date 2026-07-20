#!/usr/bin/env python3
"""Populate signin_data.db with synthetic members, staff, and several weeks of
backdated sign-in/out history — so this machine can be used for testing and
development without ever holding real member data.

Staff sign-in/out is unrestricted (no am/pm cutoff, no daily limit), so the
fake staff history includes 1-3 varied-time sessions per day and the
occasional forgotten sign-out (an open session, shown as "Still signed in"
in the staff export) to exercise that behaviour.

Re-running this script is safe — any previously seeded "Fake"-named people
(and their sign-in history) are deleted and regenerated from scratch each
time, without touching the handful of real-looking sample records `init_db()`
creates on a fresh database.

Usage:
    python seed_fake_data.py                 # seed the normal dev DB path
    python seed_fake_data.py --reset          # wipe and rebuild from scratch
    python seed_fake_data.py --path some.db   # seed a specific file instead
"""
import argparse
import os
import random
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "kiosk_signin"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import database  # noqa: E402
from tests.helpers import member, staff_member, caregiver  # noqa: E402

FAKE_MEMBER_NAMES = [
    ("Fake", "Anderson"), ("Fake", "Baxter"), ("Fake", "Cruz"),
    ("Fake", "Delgado"), ("Fake", "Everett"), ("Fake", "Farrow"),
    ("Fake", "Grover"), ("Fake", "Holt"),
]
FAKE_STAFF_NAMES = [
    ("Fake", "Coordinator"), ("Fake", "TeamLeader"), ("Fake", "Assistant"),
]

DAYS_BACK = 21  # three weeks of history


def _fake_signature(seed) -> bytes:
    """Build a small synthetic stroke list in the same format the real
    signature pad produces, so render_signature() has real data to draw."""
    rnd = random.Random(seed)
    strokes = []
    x, y = rnd.randint(5, 30), rnd.randint(5, 30)
    for _ in range(rnd.randint(3, 6)):
        nx = x + rnd.randint(-20, 30)
        ny = y + rnd.randint(-15, 15)
        strokes.append((x, y, nx, ny))
        x, y = nx, ny
    return str(strokes).encode()


def _insert_sign(conn, member_id, direction, when, sig_seed):
    signature = _fake_signature(sig_seed) if sig_seed is not None else None
    conn.execute(
        "INSERT INTO sign_ins (member_id, direction, timestamp, notes, signature) "
        "VALUES (?,?,?,?,?)",
        (member_id, direction, when.strftime("%Y-%m-%d %H:%M:%S"), "", signature),
    )


def _seed_members(conn):
    ids = []
    for i, (first, last) in enumerate(FAKE_MEMBER_NAMES):
        data = member(first_name=first, last_name=last, pin="")
        data.pop("id", None)
        mid = database.upsert_member(data)
        database.upsert_caregiver(caregiver(
            mid,
            full_name=f"Fake Parent {i + 1}",
            email=f"fake.parent{i + 1}@example.test",
            phone="000-000-0000",
        ))
        ids.append(mid)
    return ids


def _seed_staff(conn):
    ids = []
    for first, last in FAKE_STAFF_NAMES:
        data = staff_member(first_name=first, last_name=last)
        data.pop("id", None)
        ids.append(database.upsert_member(data))
    return ids


def _clear_previous_fake_data():
    """Delete any 'Fake'-named people from a previous run (sign-ins and
    caregivers cascade-delete with them) so re-running this script doesn't
    pile up duplicate fake records on top of real ones.

    Runs in its own connection/transaction, committed before the rest of the
    seeding starts — the seeding helpers below (via database.upsert_member
    etc.) each open their own nested connection, which would deadlock against
    an uncommitted write still held open on a shared connection.
    """
    with database.get_conn() as conn:
        conn.execute("DELETE FROM members WHERE first_name = 'Fake'")


def _staff_day_sessions(day):
    """Build 1-3 sign-in/out sessions for one staff member on one day, at
    varied times of day (not fixed AM/PM slots) — staff can sign in and out
    as often as they like, whenever they like. The last session of the day
    is occasionally left open (no sign-out) to simulate someone forgetting
    to sign out, which the staff export shows as "Still signed in".

    Returns a list of (direction, datetime) tuples in chronological order.
    """
    events = []
    num_sessions = random.choices([1, 2, 3], weights=[0.5, 0.35, 0.15])[0]
    cursor_hours = random.uniform(7.5, 9.0)   # first arrival, e.g. 7:30-9:00am

    for i in range(num_sessions):
        start = datetime.combine(day, datetime.min.time()) + timedelta(hours=cursor_hours)
        duration_hours = random.uniform(1.0, 4.5)
        end_hours = cursor_hours + duration_hours
        end = datetime.combine(day, datetime.min.time()) + timedelta(hours=end_hours)

        events.append(("IN", start))
        is_last = i == num_sessions - 1
        if is_last and random.random() < 0.08:
            pass  # forgot to sign out — session stays open, no OUT recorded
        else:
            events.append(("OUT", end))

        cursor_hours = end_hours + random.uniform(0.25, 1.5)   # gap before next session
        if cursor_hours > 20:   # don't run sessions past 8pm
            break

    return events


def _seed_history(conn, member_ids, staff_ids):
    today = datetime.now().date()
    seed_counter = 0

    for day_offset in range(DAYS_BACK, -1, -1):
        day = today - timedelta(days=day_offset)
        if day == today:
            continue  # leave today alone so the kiosk's own sign-ins aren't clobbered

        for mid in member_ids:
            if random.random() < 0.2:
                continue  # a day off, like a real attendance pattern
            seed_counter += 1
            am_in = datetime.combine(day, datetime.min.time()) + timedelta(hours=8, minutes=45)
            am_out = am_in + timedelta(hours=3, minutes=5)
            _insert_sign(conn, mid, "IN", am_in, seed_counter)
            _insert_sign(conn, mid, "OUT", am_out, seed_counter + 1)
            if random.random() < 0.6:
                pm_in = datetime.combine(day, datetime.min.time()) + timedelta(hours=12, minutes=30)
                pm_out = pm_in + timedelta(hours=2, minutes=45)
                _insert_sign(conn, mid, "IN", pm_in, seed_counter + 2)
                _insert_sign(conn, mid, "OUT", pm_out, seed_counter + 3)
            seed_counter += 4

        # Staff aren't restricted to weekdays or to a fixed AM/PM pattern any
        # more — mostly weekday sessions, with an occasional weekend one too.
        is_weekday = day.weekday() < 5
        if is_weekday or random.random() < 0.05:
            for sid in staff_ids:
                if not is_weekday and random.random() > 0.15:
                    continue
                for direction, when in _staff_day_sessions(day):
                    seed_counter += 1
                    sig_seed = seed_counter if random.random() < 0.7 else None
                    _insert_sign(conn, sid, direction, when, sig_seed)

    # Deliberately blank out the most recent signature for a couple of
    # members, simulating genuine pre-fix records (before signatures were
    # made mandatory) — exercises get_last_signature()'s NULL-skipping filter.
    for mid in member_ids[:2]:
        conn.execute("""
            UPDATE sign_ins SET signature = NULL
            WHERE id = (SELECT id FROM sign_ins WHERE member_id=? ORDER BY id DESC LIMIT 1)
        """, (mid,))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", default=None,
                         help="DB file to seed (default: kiosk_signin/signin_data.db)")
    parser.add_argument("--reset", action="store_true",
                         help="Delete the existing DB file first and rebuild from scratch")
    args = parser.parse_args()

    target = args.path or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "kiosk_signin", "signin_data.db")

    if args.reset:
        for suffix in ("", "-wal", "-shm"):
            p = target + suffix
            if os.path.exists(p):
                os.remove(p)

    database.DB_PATH = target
    database.init_db()
    _clear_previous_fake_data()

    with database.get_conn() as conn:
        member_ids = _seed_members(conn)
        staff_ids = _seed_staff(conn)
        _seed_history(conn, member_ids, staff_ids)

    print(f"Seeded fake data into: {target}")
    print(f"  {len(member_ids)} fake members, {len(staff_ids)} fake staff")
    print(f"  ~{DAYS_BACK} days of backdated sign-in/out history with synthetic signatures")
    print("  Staff sessions are unrestricted: 1-3 varied-time sign-in/outs per day,")
    print("  occasional weekend attendance, and the odd forgotten sign-out (shown")
    print("  as 'Still signed in' in the staff export).")
    print("  Admin login (if this was a fresh DB): admin / admin1234")


if __name__ == "__main__":
    main()
