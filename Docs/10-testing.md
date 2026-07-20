# Testing

This document describes the testing strategy, test infrastructure, and the programming concepts applied in the test suite.

## Overview

The project uses pytest as its test framework. Tests live in the `tests/` directory and cover the database layer, export functionality, email notifications, dashboard routes, profile logic, the virtual keyboard, and the fake-data seeding script.

Test configuration is in `pytest.ini`:

```ini
[pytest]
testpaths = tests
pythonpath = kiosk_signin tests
```

The `pythonpath` setting adds both `kiosk_signin` and `tests` to the Python path, allowing test files to import application modules directly (e.g. `import database`) and shared test helpers.

## Running Tests

```
pytest
```

Or for verbose output:

```
pytest -v
```

## Test Infrastructure

### Database Fixture

The core test fixture is defined in `tests/conftest.py`:

```python
@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "test.db"))
    db_module.init_db()
    return db_module
```

This fixture:

1. Uses pytest's `tmp_path` fixture to create a temporary directory that is automatically cleaned up after the test.
2. Uses `monkeypatch.setattr()` to redirect the `DB_PATH` constant in `database.py` to a temporary file. This means every test gets a fresh, isolated database.
3. Calls `init_db()` to set up the schema and seed data.
4. Returns the `database` module so tests can call its functions directly.

This approach is a form of dependency injection -- the production database path is replaced with a test-specific one at runtime, without modifying the source code.

### Test Helpers

`tests/helpers.py` provides factory functions for creating test data:

```python
def member(**overrides):
    defaults = {
        "first_name": "Jane",
        "last_name": "Smith",
        "date_of_birth": "2015-01-01",
        ...
    }
    return {**defaults, **overrides}
```

These use the dictionary merge pattern (`{**defaults, **overrides}`) to provide sensible defaults that can be selectively overridden per test. This keeps tests concise while ensuring all required fields are populated.

## Test Modules

### test_database.py

The largest test module, covering all database operations:

**Member CRUD:**
- Insert, update, search, and delete members.
- Verify cascading deletes (deleting a member removes their sign-ins and caregiver).
- Test the `person_type` field for member/staff distinction.
- Verify that search filters work correctly for each type.

**PIN Verification:**
- Correct PIN returns True.
- Incorrect PIN returns False.
- Blank PIN allows any input (no restriction).

**Sign-in/out:**
- Recording and retrieving sign events.
- Getting the latest sign event (all time and today only).
- Getting all of today's signs.
- Export queries with date range filtering.
- Verifying that member exports exclude staff and vice versa.

**Direction Validation:**
- No signs today: allowed direction is IN.
- After sign IN: allowed direction is OUT.
- After sign OUT (any time of day): allowed direction is IN again — no am/pm cutoff and no daily lockout.
- Full day sequence test (IN, OUT, IN, OUT) still allows another IN afterwards.
- Many IN/OUT cycles in a single day remain unrestricted.
- Staff use the exact same unrestricted logic as members.

**Admin Password:**
- Default password works.
- Wrong password is rejected.
- Password change updates the hash.

**Run Groups:**
- Create a run sheet with members.
- Re-saving the same name replaces the member list.
- Search by name.
- Delete a run sheet.

**Holiday Enrolments:**
- Seed data includes five holiday periods.
- Create, update, and delete enrolments.
- Unique constraint prevents duplicates.

### test_dashboard.py

Tests the Flask dashboard routes using Flask's test client:

```python
def client(db):
    dashboard_app.config["TESTING"] = True
    with dashboard_app.test_client() as client:
        yield client
```

Tests cover:
- Login page rendering.
- Successful and failed login attempts.
- Dashboard page loads with analytics.
- Logs page pagination and filtering.
- Audit log page.
- People listing and filtering by type.
- Person creation, editing, and deletion.
- Export downloads (verifying the response is an Excel file).

### test_export.py

Tests the Excel export generation:
- Member export produces a valid .xlsx file.
- Staff export produces a valid .xlsx file.
- Empty data produces a file with only headers.
- Signature rendering produces PNG bytes from stroke data.
- Duration calculation handles various cases (normal, missing start/end, negative).
- A multi-day member export produces one worksheet per calendar day with data, each showing that day's own sign-in times (regression test for a bug where multi-day ranges collapsed to a single row per member, keeping only the first day's events).
- A single-day member export still produces exactly one worksheet, so the common "Today" export is unaffected by the multi-day fix.

**Staff session pairing (`_build_staff_sessions`)** — staff aren't restricted to one AM and one PM sign, so sessions are built by pairing IN/OUT events chronologically rather than by AM/PM slot:
- A single IN/OUT pair produces one session.
- Multiple sessions in the same day are all kept, in order (not just the first).
- Sessions are grouped correctly across multiple days.
- People are sorted by last name.
- A dangling IN with no matching OUT yet is kept with `out: None` ("still signed in").
- A stray OUT with nothing open is kept with `in: None` rather than silently dropped.
- A second IN while one is already open closes the previous session with no sign-out, then opens a new one (defensive handling — the kiosk itself never produces this sequence).

**Staff export layout (`generate_staff_export`)**:
- A still-open session renders "Still signed in" in the sheet.
- The "Total time in the centre" line at the end of a person's section sums every session's duration.
- The name banner shows the year (or a year range, e.g. "2026–2027", when the exported data spans a calendar year boundary).
- `_day_month()` formats dates as day/month with no year.

### test_email_notifier.py

Tests the email notification system using `unittest.mock` to avoid sending real emails:

```python
@patch("email_notifier.smtplib.SMTP")
def test_send_notification(mock_smtp, db):
    ...
```

Tests cover:
- Email is sent when a caregiver has an email address and notifications are enabled.
- Email is not sent when notifications are disabled.
- Email is not sent when the caregiver has no email.
- Notification preference filtering (IN only, OUT only, BOTH, NONE).

### test_profile.py

Tests member profile creation and update logic through the database layer:
- Creating a member with all fields.
- Updating specific fields.
- Caregiver upsert (insert and update).

### test_virtual_keyboard.py

Tests the virtual keyboard component without requiring a display:
- Key press inserts characters.
- Backspace deletes characters.
- Shift toggles case.
- Shift auto-releases after one character.

### test_seed_fake_data.py

Tests `seed_fake_data.py`, the dummy-data generator used to populate a dev machine's database:
- `_staff_day_sessions()` (the varied-time, multi-session staff day generator): every event falls on the requested day, events are chronologically ordered, session count stays within 1-3, at most the final session of a day is ever left open (a simulated forgotten sign-out), directions alternate correctly, and — checked across many random seeds — both multi-session days and open (still-signed-in) sessions do actually occur.
- `_clear_previous_fake_data()` removes only "Fake"-named people, leaving real records untouched, and is a no-op (doesn't raise) when there's nothing to clear.
- Running the seeding helpers twice back-to-back doesn't duplicate fake people (idempotency).
- The full `_seed_history()` run actually produces staff days with more than one session — a regression guard that the dummy data reflects the new unrestricted sign-in/out behaviour rather than the old one-shift-per-day pattern.

## Programming Concepts Applied

### Test Isolation

Each test runs with a completely fresh database. The `tmp_path` fixture creates a unique temporary directory per test, and `monkeypatch` redirects the database path. This ensures tests cannot interfere with each other regardless of execution order.

### Fixtures and Dependency Injection

pytest fixtures provide test dependencies through function parameters. The `db` fixture encapsulates all database setup, and tests declare their dependency simply by including `db` as a parameter:

```python
def test_upsert_member_insert(db):
    mid = db.upsert_member(_member())
    ...
```

This is dependency injection: the test receives its dependencies from the framework rather than creating them itself.

### Factory Pattern (Test Helpers)

The `member()`, `caregiver()`, and `staff_member()` helper functions implement the factory pattern. They produce test data with sensible defaults, allowing tests to specify only the values relevant to what they are testing:

```python
def test_search_by_name(db):
    mid = db.upsert_member(_member(first_name="Unique", last_name="Person"))
    results = db.search_members("Unique")
    assert any(m["id"] == mid for m in results)
```

### Mocking (unittest.mock)

The email tests use `@patch` to replace the SMTP client with a mock object. This allows testing the notification logic without sending real emails or requiring network access:

```python
@patch("email_notifier.smtplib.SMTP")
def test_send_notification(mock_smtp, db):
    mock_smtp.return_value.__enter__.return_value = MagicMock()
    ...
```

### Arrange-Act-Assert

Tests follow the Arrange-Act-Assert pattern:
1. **Arrange**: Set up test data (create members, sign events, etc.).
2. **Act**: Call the function being tested.
3. **Assert**: Verify the result matches expectations.

### Boundary Testing

The direction validation tests specifically target boundary conditions:
- The start of day (no signs) — allowed direction is IN.
- Straight after a sign IN — allowed direction is OUT.
- Straight after a sign OUT, at any time of day — allowed direction is IN again (no am/pm cutoff, no lockout).
- A full day sequence from start to finish, and many IN/OUT cycles in a single day.
