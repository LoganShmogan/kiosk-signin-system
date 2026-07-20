import sqlite3
import hashlib
import os
import sys
from datetime import datetime, timedelta

if getattr(sys, "frozen", False):
    # LOCALAPPDATA (C:\Users\<user>\AppData\Local) is always writable by the
    # current user, including the restricted kiosk account.
    _data_dir = os.path.join(
        os.environ.get("LOCALAPPDATA", os.path.dirname(sys.executable)),
        "Kiosk Sign-In",
    )
    os.makedirs(_data_dir, exist_ok=True)
    DB_PATH = os.path.join(_data_dir, "signin_data.db")
else:
    DB_PATH = os.path.join(os.path.dirname(__file__), "signin_data.db")


def log_event(event_type: str, description: str, conn=None):
    """Record an audit event. Pass conn to reuse an open transaction."""
    sql = "INSERT INTO audit_log (event_type, description) VALUES (?, ?)"
    try:
        if conn:
            conn.execute(sql, (event_type, description))
        else:
            with get_conn() as c:
                c.execute(sql, (event_type, description))
    except Exception:
        pass


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ── Schema ────────────────────────────────────────────────────────────────────

def init_db():
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS members (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name      TEXT NOT NULL,
            last_name       TEXT NOT NULL,
            date_of_birth   TEXT,
            school          TEXT,
            mornings_days   TEXT DEFAULT '',
            afternoons_days TEXT DEFAULT '',
            needs_pickup    INTEGER DEFAULT 0,
            activity        TEXT,
            activity_time   TEXT,
            activity_address TEXT,
            transport_required INTEGER DEFAULT 0,
            activity_days   TEXT DEFAULT '',
            pin             TEXT DEFAULT '',
            created_at      TEXT DEFAULT (datetime('now', 'localtime'))
        );

        CREATE TABLE IF NOT EXISTS caregivers (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id               INTEGER NOT NULL REFERENCES members(id) ON DELETE CASCADE,
            full_name               TEXT,
            phone                   TEXT,
            street_address          TEXT,
            suburb                  TEXT,
            city                    TEXT,
            email                   TEXT,
            emergency_contact_name  TEXT,
            emergency_contact_phone TEXT,
            relationship            TEXT DEFAULT 'Parent/Guardian',
            notify_on               TEXT DEFAULT 'BOTH'
        );

        CREATE TABLE IF NOT EXISTS sign_ins (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id   INTEGER NOT NULL REFERENCES members(id) ON DELETE CASCADE,
            direction   TEXT NOT NULL CHECK(direction IN ('IN', 'OUT')),
            timestamp   TEXT DEFAULT (datetime('now', 'localtime')),
            notes       TEXT,
            signature   BLOB
        );

        CREATE TABLE IF NOT EXISTS notices (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT,
            body        TEXT NOT NULL,
            source      TEXT DEFAULT 'facebook',
            post_id     TEXT UNIQUE,
            posted_at   TEXT,
            fetched_at  TEXT DEFAULT (datetime('now', 'localtime'))
        );

        CREATE TABLE IF NOT EXISTS admins (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            username        TEXT UNIQUE NOT NULL,
            password_hash   TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS run_groups (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            name    TEXT UNIQUE NOT NULL
        );

        CREATE TABLE IF NOT EXISTS run_members (
            run_id      INTEGER REFERENCES run_groups(id) ON DELETE CASCADE,
            member_id   INTEGER REFERENCES members(id) ON DELETE CASCADE,
            PRIMARY KEY (run_id, member_id)
        );

        CREATE TABLE IF NOT EXISTS holiday_periods (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            name    TEXT UNIQUE NOT NULL,
            active  INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS holiday_enrollments (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id       INTEGER REFERENCES members(id) ON DELETE CASCADE,
            period_id       INTEGER REFERENCES holiday_periods(id) ON DELETE CASCADE,
            days            TEXT DEFAULT '',
            afternoon_pickup INTEGER DEFAULT 0,
            morning_pickup  INTEGER DEFAULT 0,
            UNIQUE(member_id, period_id)
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type  TEXT NOT NULL,
            description TEXT,
            timestamp   TEXT DEFAULT (datetime('now', 'localtime'))
        );

        CREATE TABLE IF NOT EXISTS alerts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            scope       TEXT NOT NULL CHECK(scope IN ('all', 'run', 'member')),
            target_id   INTEGER,
            message     TEXT NOT NULL,
            created_at  TEXT DEFAULT (datetime('now', 'localtime')),
            expires_at  TEXT
        );
        """)

        try:
            conn.execute("ALTER TABLE caregivers ADD COLUMN notify_on TEXT DEFAULT 'BOTH'")
        except Exception:
            pass

        try:
            conn.execute("ALTER TABLE members ADD COLUMN updated_at TEXT")
        except Exception:
            pass

        try:
            conn.execute("ALTER TABLE members ADD COLUMN person_type TEXT DEFAULT 'member'")
        except Exception:
            pass

        try:
            conn.execute("ALTER TABLE alerts ADD COLUMN expires_at TEXT")
        except Exception:
            pass

        cur = conn.execute("SELECT COUNT(*) FROM admins")
        if cur.fetchone()[0] == 0:
            h = hashlib.sha256("admin1234".encode()).hexdigest()
            conn.execute("INSERT INTO admins (username, password_hash) VALUES (?, ?)",
                         ("admin", h))

        cur = conn.execute("SELECT COUNT(*) FROM holiday_periods")
        if cur.fetchone()[0] == 0:
            for p in ["Term 1 Break", "Term 2 Break", "Mid Year Break",
                      "Term 3 Break", "Term 4 Break"]:
                conn.execute("INSERT INTO holiday_periods (name) VALUES (?)", (p,))

        cur = conn.execute("SELECT COUNT(*) FROM members")
        if cur.fetchone()[0] == 0:
            sample = [
                ("Ava",   "Thompson", "2015-03-12", "Example Primary School",
                 "Mon,Tue,Wed,Thu,Fri", "Mon,Tue,Wed,Thu,Fri", 0,
                 "Hockey", "4:30pm", "1 Example Street", 1, "Tue,Wed,Thu", "1234"),
                ("Noah",  "Bennett",  "2014-07-22", "Example Primary School",
                 "", "Mon,Tue,Wed,Thu,Fri", 1,
                 "Piano Lessons", "4:35pm", "2 Sample Street", 0, "Tue,Wed,Thu", "5678"),
                ("Mia",   "Roberts",  "2013-11-05", "Example Intermediate School",
                 "Mon,Tue,Wed,Thu,Fri", "Mon,Tue,Wed,Thu,Fri", 0,
                 "Soccer", "4:30pm", "", 1, "Mon,Wed,Fri", ""),
                ("Ella",  "Turner",   "2015-09-18", "Example Primary School",
                 "Mon,Tue,Wed,Thu,Fri", "", 0,
                 "Dance", "5:00pm", "", 0, "Mon,Wed", ""),
                ("Liam",  "Foster",   "2014-02-28", "Example Intermediate School",
                 "", "Mon,Tue,Wed,Thu,Fri", 0,
                 "Karate", "4:45pm", "", 0, "Tue,Thu", ""),
            ]
            for m in sample:
                conn.execute("""INSERT INTO members
                    (first_name, last_name, date_of_birth, school,
                     mornings_days, afternoons_days, needs_pickup,
                     activity, activity_time, activity_address,
                     transport_required, activity_days, pin)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", m)

            for mid, cg in [
                (1, ("Sophie Thompson", "021-000-0001", "1 Example Street",
                     "Example Suburb", "Example City", "sophie.thompson@example.com",
                     "James Thompson", "021-000-0002", "Parent/Guardian")),
                (2, ("Daniel Bennett", "021-000-0003", "2 Sample Street",
                     "Example Suburb", "Example City", "daniel.bennett@example.com",
                     "Rachel Bennett", "021-000-0004", "Parent/Guardian")),
            ]:
                conn.execute("""INSERT INTO caregivers
                    (member_id, full_name, phone, street_address, suburb, city,
                     email, emergency_contact_name, emergency_contact_phone, relationship)
                    VALUES (?,?,?,?,?,?,?,?,?,?)""", (mid, *cg))

            conn.execute("INSERT INTO run_groups (name) VALUES (?)", ("Group A",))
            rid = conn.execute("SELECT id FROM run_groups WHERE name='Group A'").fetchone()[0]
            for mid in [1, 2, 3, 4]:
                conn.execute("INSERT OR IGNORE INTO run_members VALUES (?,?)", (rid, mid))


# ── Members ───────────────────────────────────────────────────────────────────

def search_members(query: str, person_type: str = None):
    q = f"%{query}%"
    with get_conn() as conn:
        if person_type:
            rows = conn.execute("""
                SELECT * FROM members
                WHERE (first_name || ' ' || last_name) LIKE ?
                AND (person_type = ? OR (? = 'member' AND person_type IS NULL))
                ORDER BY last_name, first_name
            """, (q, person_type, person_type)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM members
                WHERE (first_name || ' ' || last_name) LIKE ?
                ORDER BY last_name, first_name
            """, (q,)).fetchall()
    return [dict(r) for r in rows]


def search_staff(query: str):
    return search_members(query, "staff")


def get_member(member_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM members WHERE id=?", (member_id,)).fetchone()
    return dict(row) if row else None


def get_caregiver(member_id: int):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM caregivers WHERE member_id=? LIMIT 1", (member_id,)
        ).fetchone()
    return dict(row) if row else None


def upsert_member(data: dict):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data = {**data}
    data.setdefault("person_type", "member")
    name = f"{data.get('first_name', '')} {data.get('last_name', '')}".strip()
    ptype = data["person_type"]
    with get_conn() as conn:
        if data.get("id"):
            conn.execute("""UPDATE members SET
                first_name=:first_name, last_name=:last_name,
                date_of_birth=:date_of_birth, school=:school,
                mornings_days=:mornings_days, afternoons_days=:afternoons_days,
                needs_pickup=:needs_pickup, activity=:activity,
                activity_time=:activity_time, activity_address=:activity_address,
                transport_required=:transport_required, activity_days=:activity_days,
                pin=:pin, updated_at=:updated_at
                WHERE id=:id""", {**data, "updated_at": now})
            label = "Staff" if ptype == "staff" else "Member"
            log_event(f"{label.upper()}_UPDATED", f"{label} profile updated: {name}", conn)
            return data["id"]
        else:
            cur = conn.execute("""INSERT INTO members
                (first_name, last_name, date_of_birth, school,
                 mornings_days, afternoons_days, needs_pickup, activity,
                 activity_time, activity_address, transport_required, activity_days,
                 pin, person_type)
                VALUES (:first_name,:last_name,:date_of_birth,:school,
                        :mornings_days,:afternoons_days,:needs_pickup,:activity,
                        :activity_time,:activity_address,:transport_required,:activity_days,
                        :pin,:person_type)
                """, data)
            label = "Staff" if ptype == "staff" else "Member"
            log_event(f"{label.upper()}_CREATED", f"New {label.lower()} added: {name}", conn)
            return cur.lastrowid


def upsert_caregiver(data: dict):
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM caregivers WHERE member_id=?", (data["member_id"],)
        ).fetchone()
        if existing:
            data["id"] = existing["id"]
            conn.execute("""UPDATE caregivers SET
                full_name=:full_name, phone=:phone, street_address=:street_address,
                suburb=:suburb, city=:city, email=:email,
                emergency_contact_name=:emergency_contact_name,
                emergency_contact_phone=:emergency_contact_phone,
                relationship=:relationship, notify_on=:notify_on
                WHERE id=:id""", data)
        else:
            conn.execute("""INSERT INTO caregivers
                (member_id, full_name, phone, street_address, suburb, city,
                 email, emergency_contact_name, emergency_contact_phone,
                 relationship, notify_on)
                VALUES (:member_id,:full_name,:phone,:street_address,:suburb,:city,
                        :email,:emergency_contact_name,:emergency_contact_phone,
                        :relationship,:notify_on)
                """, data)


def delete_member(member_id: int):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT first_name, last_name FROM members WHERE id=?", (member_id,)
        ).fetchone()
        name = f"{row['first_name']} {row['last_name']}" if row else f"ID {member_id}"
        conn.execute("DELETE FROM members WHERE id=?", (member_id,))
        log_event("MEMBER_DELETED", f"Member deleted: {name}", conn)


def verify_pin(member_id: int, pin: str) -> bool:
    with get_conn() as conn:
        row = conn.execute("SELECT pin FROM members WHERE id=?", (member_id,)).fetchone()
    if not row:
        return False
    stored = row["pin"] or ""
    # Blank PIN means no restriction — anyone can sign in without one
    return stored == "" or stored == pin


# ── Sign-in / out ─────────────────────────────────────────────────────────────

def record_sign(member_id: int, direction: str, notes: str = "", signature: bytes = None):
    with get_conn() as conn:
        conn.execute("""INSERT INTO sign_ins (member_id, direction, notes, signature)
                        VALUES (?,?,?,?)""",
                     (member_id, direction, notes, signature))
        row = conn.execute(
            "SELECT first_name, last_name FROM members WHERE id=?", (member_id,)
        ).fetchone()
        name = f"{row['first_name']} {row['last_name']}" if row else f"ID {member_id}"
        log_event(f"SIGN_{direction}", f"{name} signed {direction}", conn)


def get_last_sign(member_id: int):
    with get_conn() as conn:
        row = conn.execute("""SELECT * FROM sign_ins WHERE member_id=?
                              ORDER BY id DESC LIMIT 1""",
                           (member_id,)).fetchone()
    return dict(row) if row else None


def get_last_signature(member_id: int):
    """Most recent sign_ins row for this member that actually has a signature
    on file. Skips NULL/empty signatures (e.g. pre-existing records from
    before signatures were made mandatory) rather than returning them."""
    with get_conn() as conn:
        row = conn.execute("""SELECT * FROM sign_ins WHERE member_id=?
                              AND signature IS NOT NULL AND signature != ''
                              ORDER BY id DESC LIMIT 1""",
                           (member_id,)).fetchone()
    return dict(row) if row else None


def get_today_last_sign(member_id: int):
    today = datetime.now().strftime("%Y-%m-%d")
    with get_conn() as conn:
        row = conn.execute("""SELECT * FROM sign_ins WHERE member_id=?
                              AND timestamp LIKE ?
                              ORDER BY id DESC LIMIT 1""",
                           (member_id, f"{today}%")).fetchone()
    return dict(row) if row else None


def get_allowed_direction(member_id: int):
    """
    Returns what direction a person (member or staff) is permitted to sign next:
      'IN'  — no sign today, or last sign today was OUT
      'OUT' — last sign today was IN (currently checked in)
    No restriction on time of day or number of sign in/out cycles per day.
    """
    last = get_today_last_sign(member_id)
    if last is None:
        return "IN"
    return "OUT" if last["direction"] == "IN" else "IN"


def get_today_signs():
    today = datetime.now().strftime("%Y-%m-%d")
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT s.*, m.first_name, m.last_name
            FROM sign_ins s JOIN members m ON s.member_id=m.id
            WHERE s.timestamp LIKE ?
            ORDER BY s.timestamp DESC
        """, (f"{today}%",)).fetchall()
    return [dict(r) for r in rows]


# ── Notices ───────────────────────────────────────────────────────────────────

def upsert_notices(posts: list):
    with get_conn() as conn:
        for p in posts:
            conn.execute("""INSERT INTO notices (title, body, source, post_id, posted_at)
                            VALUES (:title, :body, 'facebook', :post_id, :posted_at)
                            ON CONFLICT(post_id) DO UPDATE SET
                                body=excluded.body, posted_at=excluded.posted_at,
                                fetched_at=datetime('now','localtime')
                         """, p)


def get_notices(limit: int = 20):
    with get_conn() as conn:
        rows = conn.execute("""SELECT * FROM notices
                               ORDER BY posted_at DESC LIMIT ?""", (limit,)).fetchall()
    return [dict(r) for r in rows]


# ── Auth ──────────────────────────────────────────────────────────────────────

def check_admin_password(password: str) -> bool:
    h = hashlib.sha256(password.encode()).hexdigest()
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM admins WHERE password_hash=?", (h,)).fetchone()
    return row is not None


def set_admin_password(new_password: str):
    h = hashlib.sha256(new_password.encode()).hexdigest()
    with get_conn() as conn:
        conn.execute("UPDATE admins SET password_hash=? WHERE username='admin'", (h,))


# ── Run groups ────────────────────────────────────────────────────────────────

def search_runs(query: str):
    q = f"%{query}%"
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM run_groups WHERE name LIKE ? ORDER BY name", (q,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_run_members(run_id: int):
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT m.* FROM members m
            JOIN run_members rm ON m.id=rm.member_id
            WHERE rm.run_id=?
            ORDER BY m.last_name, m.first_name
        """, (run_id,)).fetchall()
    return [dict(r) for r in rows]


def upsert_run(name: str, member_ids: list) -> int:
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM run_groups WHERE name=?", (name,)
        ).fetchone()
        if existing:
            run_id = existing["id"]
        else:
            cur = conn.execute("INSERT INTO run_groups (name) VALUES (?)", (name,))
            run_id = cur.lastrowid
        conn.execute("DELETE FROM run_members WHERE run_id=?", (run_id,))
        for mid in member_ids:
            conn.execute("INSERT OR IGNORE INTO run_members VALUES (?,?)", (run_id, mid))
    return run_id


def delete_run(run_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM run_groups WHERE id=?", (run_id,))


# ── Alerts ────────────────────────────────────────────────────────────────────

def create_alert(scope: str, target_id, message: str, duration_hours: float = None) -> int:
    """scope is 'all', 'run', or 'member'. target_id is a run_groups.id or
    members.id (ignored/NULL for scope='all'). duration_hours, if given,
    sets when the alert stops appearing (None = never expires)."""
    expires_at = None
    if duration_hours:
        expires_at = (datetime.now() + timedelta(hours=duration_hours)).strftime("%Y-%m-%d %H:%M:%S")
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO alerts (scope, target_id, message, expires_at) VALUES (?, ?, ?, ?)",
            (scope, target_id if scope != "all" else None, message, expires_at),
        )
        log_event("ALERT_CREATED", f"Alert created ({scope}): {message[:60]}", conn)
        return cur.lastrowid


def get_alerts(include_expired: bool = False) -> list:
    with get_conn() as conn:
        if include_expired:
            rows = conn.execute(
                "SELECT * FROM alerts ORDER BY created_at DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM alerts "
                "WHERE expires_at IS NULL OR expires_at > datetime('now', 'localtime') "
                "ORDER BY created_at DESC"
            ).fetchall()
    return [dict(r) for r in rows]


def delete_alert(alert_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM alerts WHERE id=?", (alert_id,))
        log_event("ALERT_DELETED", f"Alert {alert_id} deleted", conn)


def get_alerts_for_members(member_ids: list) -> list:
    """Alerts applicable to any of the given member ids: scope='all', or
    scope='run' where a member belongs to that run, or scope='member'
    matching one of the ids directly."""
    if not member_ids:
        return []
    with get_conn() as conn:
        id_placeholders = ",".join("?" * len(member_ids))
        run_rows = conn.execute(
            f"SELECT DISTINCT run_id FROM run_members WHERE member_id IN ({id_placeholders})",
            member_ids,
        ).fetchall()
        run_ids = [r["run_id"] for r in run_rows]

        conditions = ["scope = 'all'", f"(scope = 'member' AND target_id IN ({id_placeholders}))"]
        params = list(member_ids)
        if run_ids:
            run_placeholders = ",".join("?" * len(run_ids))
            conditions.append(f"(scope = 'run' AND target_id IN ({run_placeholders}))")
            params += run_ids

        rows = conn.execute(
            f"SELECT * FROM alerts "
            f"WHERE (expires_at IS NULL OR expires_at > datetime('now', 'localtime')) "
            f"AND ({' OR '.join(conditions)}) ORDER BY created_at",
            params,
        ).fetchall()
    return [dict(r) for r in rows]


# ── Holiday periods & enrollments ─────────────────────────────────────────────

def get_holiday_periods():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM holiday_periods WHERE active=1 ORDER BY id"
        ).fetchall()
    return [dict(r) for r in rows]


def get_holiday_enrollment(member_id: int, period_id: int):
    with get_conn() as conn:
        row = conn.execute("""SELECT * FROM holiday_enrollments
                              WHERE member_id=? AND period_id=?""",
                           (member_id, period_id)).fetchone()
    return dict(row) if row else None


def upsert_holiday_enrollment(data: dict):
    with get_conn() as conn:
        conn.execute("""INSERT INTO holiday_enrollments
            (member_id, period_id, days, afternoon_pickup, morning_pickup)
            VALUES (:member_id, :period_id, :days, :afternoon_pickup, :morning_pickup)
            ON CONFLICT(member_id, period_id) DO UPDATE SET
                days=excluded.days,
                afternoon_pickup=excluded.afternoon_pickup,
                morning_pickup=excluded.morning_pickup
        """, data)


def delete_holiday_enrollment(member_id: int, period_id: int):
    with get_conn() as conn:
        conn.execute("""DELETE FROM holiday_enrollments
                        WHERE member_id=? AND period_id=?""",
                     (member_id, period_id))


# ── Export ────────────────────────────────────────────────────────────────────

def get_signs_for_export(date_from: str, date_to: str) -> list:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT s.member_id, m.first_name, m.last_name,
                   s.direction, s.timestamp, s.signature
            FROM sign_ins s
            JOIN members m ON s.member_id = m.id
            WHERE DATE(s.timestamp) >= ? AND DATE(s.timestamp) <= ?
            AND (m.person_type = 'member' OR m.person_type IS NULL)
            ORDER BY m.last_name, m.first_name, s.timestamp
        """, (date_from, date_to)).fetchall()
    return [dict(r) for r in rows]


def get_staff_signs_for_export(date_from: str, date_to: str) -> list:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT s.member_id, m.first_name, m.last_name,
                   m.school AS role,
                   s.direction, s.timestamp, s.signature
            FROM sign_ins s
            JOIN members m ON s.member_id = m.id
            WHERE DATE(s.timestamp) >= ? AND DATE(s.timestamp) <= ?
            AND m.person_type = 'staff'
            ORDER BY m.last_name, m.first_name, s.timestamp
        """, (date_from, date_to)).fetchall()
    return [dict(r) for r in rows]


def get_signs_for_member(member_id: int, date_from: str = None, date_to: str = None) -> list:
    """Sign-in/out events for one person. With no dates, returns full history."""
    sql = """
        SELECT s.member_id, m.first_name, m.last_name, m.school AS role,
               s.direction, s.timestamp, s.signature
        FROM sign_ins s
        JOIN members m ON s.member_id = m.id
        WHERE s.member_id = ?
    """
    params = [member_id]
    if date_from:
        sql += " AND DATE(s.timestamp) >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND DATE(s.timestamp) <= ?"
        params.append(date_to)
    sql += " ORDER BY s.timestamp"
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]
