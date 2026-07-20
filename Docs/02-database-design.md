# Database Design

This document covers the SQLite database schema, the data access layer, and the programming concepts applied in the database module.

## Overview

The system uses a single SQLite database file (`signin_data.db`) accessed by both the kiosk and the web dashboard. All schema definitions, queries, and data access functions live in `kiosk_signin/database.py`.

## Schema

The database consists of nine tables:

### members

The central table. Stores both children (members) and staff. The `person_type` column distinguishes between them (`"member"` or `"staff"`). Staff members reuse the `school` column to store their role/position.

| Column             | Type    | Purpose                                    |
|--------------------|---------|--------------------------------------------|
| id                 | INTEGER | Primary key, auto-increment                |
| first_name         | TEXT    | Required                                   |
| last_name          | TEXT    | Required                                   |
| date_of_birth      | TEXT    | Date string (YYYY-MM-DD)                   |
| school             | TEXT    | School name (members) or role (staff)       |
| mornings_days      | TEXT    | Comma-separated days (e.g. "Mon,Tue,Wed")  |
| afternoons_days    | TEXT    | Comma-separated days                       |
| needs_pickup       | INTEGER | Boolean (0/1)                              |
| activity           | TEXT    | After-school activity name                 |
| activity_time      | TEXT    | Time of activity                           |
| activity_address   | TEXT    | Address of activity                        |
| transport_required | INTEGER | Boolean (0/1)                              |
| activity_days      | TEXT    | Comma-separated days                       |
| pin                | TEXT    | Optional PIN for sign-in verification      |
| person_type        | TEXT    | "member" or "staff"                        |
| created_at         | TEXT    | Auto-set to local datetime on insert       |
| updated_at         | TEXT    | Set on update                              |

### caregivers

Each caregiver is linked to a member via `member_id`. A member can have one caregiver record. The `notify_on` column controls email notification preferences.

| Column                 | Type    | Purpose                              |
|------------------------|---------|--------------------------------------|
| id                     | INTEGER | Primary key                          |
| member_id              | INTEGER | Foreign key to members, CASCADE      |
| full_name              | TEXT    | Caregiver's name                     |
| phone                  | TEXT    | Phone number                         |
| street_address         | TEXT    | Address line                         |
| suburb                 | TEXT    | Suburb                               |
| city                   | TEXT    | City                                 |
| email                  | TEXT    | Email for notifications              |
| emergency_contact_name | TEXT    | Emergency contact                    |
| emergency_contact_phone| TEXT    | Emergency phone                      |
| relationship           | TEXT    | e.g. "Parent/Guardian"               |
| notify_on              | TEXT    | "NONE", "IN", "OUT", or "BOTH"       |

### sign_ins

Records every sign-in and sign-out event. The `signature` column stores raw stroke data as a serialised Python list (bytes).

| Column    | Type    | Purpose                                  |
|-----------|---------|------------------------------------------|
| id        | INTEGER | Primary key                              |
| member_id | INTEGER | Foreign key to members, CASCADE          |
| direction | TEXT    | "IN" or "OUT" (enforced with CHECK)      |
| timestamp | TEXT    | Auto-set to local datetime               |
| notes     | TEXT    | Optional notes entered during sign-in    |
| signature | BLOB    | Serialised stroke coordinates            |

A member's "current"/most-recently-used signature is never stored separately — it's computed on demand by `database.get_last_signature(member_id)`, which finds the most recent row for that member with a non-null signature. This follows the same "compute on the fly" pattern as `get_last_sign()`/`get_today_last_sign()`/`get_allowed_direction()` below rather than caching state on the `members` row.

### notices

Stores posts fetched from the organisation's Facebook page.

| Column     | Type    | Purpose                          |
|------------|---------|----------------------------------|
| id         | INTEGER | Primary key                      |
| title      | TEXT    | First line of the post           |
| body       | TEXT    | Full post text                   |
| source     | TEXT    | Always "facebook"                |
| post_id    | TEXT    | Facebook post ID (unique)        |
| posted_at  | TEXT    | When the post was published      |
| fetched_at | TEXT    | When the system fetched it       |

### admins

Stores the admin account. Only one admin account exists by default.

| Column        | Type    | Purpose                      |
|---------------|---------|------------------------------|
| id            | INTEGER | Primary key                  |
| username      | TEXT    | Unique username              |
| password_hash | TEXT    | SHA-256 hash of the password |

### run_groups and run_members

Run sheets group members for batch sign-in (e.g. a school bus run). `run_members` is a junction table implementing the many-to-many relationship.

**run_groups:**

| Column | Type    | Purpose             |
|--------|---------|---------------------|
| id     | INTEGER | Primary key         |
| name   | TEXT    | Unique run name     |

**run_members:**

| Column    | Type    | Purpose                        |
|-----------|---------|--------------------------------|
| run_id    | INTEGER | Foreign key to run_groups      |
| member_id | INTEGER | Foreign key to members         |

Composite primary key on `(run_id, member_id)`.

### holiday_periods and holiday_enrollments

Manages holiday programme enrolments.

**holiday_periods:**

| Column | Type    | Purpose                         |
|--------|---------|---------------------------------|
| id     | INTEGER | Primary key                     |
| name   | TEXT    | e.g. "Term 1 Break"            |
| active | INTEGER | Boolean, controls visibility    |

**holiday_enrollments:**

| Column           | Type    | Purpose                             |
|------------------|---------|-------------------------------------|
| id               | INTEGER | Primary key                         |
| member_id        | INTEGER | Foreign key to members              |
| period_id        | INTEGER | Foreign key to holiday_periods      |
| days             | TEXT    | Comma-separated enrolled days       |
| afternoon_pickup | INTEGER | Boolean                             |
| morning_pickup   | INTEGER | Boolean                             |

Unique constraint on `(member_id, period_id)` to prevent duplicate enrolments.

### audit_log

Immutable log of all system events (sign-ins, profile changes, exports, dashboard logins).

| Column      | Type    | Purpose                         |
|-------------|---------|---------------------------------|
| id          | INTEGER | Primary key                     |
| event_type  | TEXT    | e.g. "SIGN_IN", "MEMBER_CREATED"|
| description | TEXT    | Human-readable description      |
| timestamp   | TEXT    | Auto-set to local datetime      |

## Entity Relationship Summary

```
members  1 --- *  sign_ins
members  1 --- 1  caregivers
members  * --- *  run_groups       (via run_members junction table)
members  1 --- *  holiday_enrollments
holiday_periods  1 --- *  holiday_enrollments
```

All foreign keys use `ON DELETE CASCADE`, so deleting a member automatically removes their sign-in records, caregiver details, run sheet assignments, and holiday enrolments.

## Programming Concepts Applied

### Connection Management

Each function opens a fresh connection with `get_conn()` and uses Python's `with` statement (context manager) for automatic transaction handling. SQLite connections in Python commit on successful exit from the `with` block and roll back on exception.

```python
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row    # rows behave like dicts
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
```

### WAL Mode

Write-Ahead Logging (`PRAGMA journal_mode=WAL`) allows concurrent readers and a single writer without blocking. This is essential because the kiosk and dashboard both access the same database file simultaneously from different threads.

### Row Factory

Setting `conn.row_factory = sqlite3.Row` means query results are returned as `sqlite3.Row` objects that support both index-based and key-based access. All functions convert these to plain dictionaries with `dict(row)` before returning, keeping the rest of the codebase independent of SQLite internals.

### Upsert Pattern

The `upsert_member()` function checks whether the data dictionary contains an `id` key. If it does, it performs an UPDATE; otherwise, it performs an INSERT and returns the new row's ID via `cursor.lastrowid`. This avoids requiring separate create and update functions.

For notices, SQLite's `ON CONFLICT ... DO UPDATE` syntax is used for a true upsert based on the unique `post_id` column.

### Schema Migration

New columns are added using `ALTER TABLE ... ADD COLUMN` wrapped in try/except blocks. If the column already exists, the `ALTER TABLE` raises an error which is silently caught. This allows the schema to evolve without requiring a separate migration tool.

```python
try:
    conn.execute("ALTER TABLE members ADD COLUMN person_type TEXT DEFAULT 'member'")
except Exception:
    pass
```

### Seed Data

`init_db()` checks whether key tables are empty (e.g. `SELECT COUNT(*) FROM admins`) and inserts default data if so. This provides a working system out of the box with sample members, a default admin account, and preset holiday periods.

### Parameterised Queries

All queries use parameterised placeholders (`?`) rather than string interpolation to prevent SQL injection. This is a fundamental security practice applied consistently throughout the module.

### Audit Logging

The `log_event()` function records an entry in the `audit_log` table. It accepts an optional `conn` parameter so it can participate in the same transaction as the operation being logged, ensuring atomicity. If no connection is provided, it opens its own.

### Direction Validation

The `get_allowed_direction()` function implements a small state machine for the sign-in/out flow, shared by members and staff alike:

1. No signs today: allowed direction is `IN`
2. Last sign today was `IN`: allowed direction is `OUT`
3. Last sign today was `OUT`: allowed direction is `IN`

There is no time-of-day cutoff and no daily session limit — a person can sign in and out as many times as they like, at any time of day. The function only ever alternates between `IN` and `OUT` based on the most recent event; it never returns `None`. An earlier version locked a person out after a second ("PM") sign-out each day — that lockout was removed so both members and staff can freely sign in/out whenever they need to (e.g. staff popping out and back multiple times in a shift).
