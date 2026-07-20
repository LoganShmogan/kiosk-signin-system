# Authentication and Security

This document covers the authentication mechanisms, security practices, and data protection measures applied throughout the system.

## Kiosk Authentication

### Admin Password

The kiosk's admin panel is protected by a password. The password is stored as a SHA-256 hash in the `admins` table:

```python
h = hashlib.sha256(password.encode()).hexdigest()
```

When a user enters a password, it is hashed and compared against the stored hash:

```python
def check_admin_password(password: str) -> bool:
    h = hashlib.sha256(password.encode()).hexdigest()
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM admins WHERE password_hash=?", (h,)).fetchone()
    return row is not None
```

#### Hashing

Hashing is a one-way function: it is computationally infeasible to recover the original password from its hash. This means that even if the database file is accessed directly, the admin password cannot be read.

SHA-256 produces a fixed 64-character hexadecimal string regardless of input length. The same input always produces the same hash, which is how password verification works.

#### Default Credentials

The system seeds a default admin account on first run:
- Username: `admin`
- Password: `admin1234`

The password should be changed through the admin panel after initial setup.

### Member PIN Verification

Members can optionally have a PIN set on their profile. The `verify_pin()` function checks the entered PIN against the stored one:

```python
def verify_pin(member_id: int, pin: str) -> bool:
    stored = row["pin"] or ""
    return stored == "" or stored == pin
```

A blank PIN means no restriction -- anyone can sign the member in without entering a PIN. This is a deliberate design choice for simplicity in a childcare environment where caregivers may not always have a PIN available.

## Dashboard Authentication

### Session-Based Login

The web dashboard uses Flask's session system. After successful login, a flag is set in the session:

```python
session["logged_in"] = True
```

Protected routes check this flag using the `login_required` decorator:

```python
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated
```

Sessions are signed cookies stored in the browser. Flask's `secret_key` is used to cryptographically sign the cookie, preventing tampering. The session data itself is stored client-side but cannot be modified without knowing the secret key.

### Credential Storage

The dashboard credentials are currently hardcoded:

```python
DASHBOARD_USER = "admin"
DASHBOARD_PASS = "1234"
```

In a production deployment, these should be moved to environment variables or a configuration file.

## SQL Injection Prevention

All database queries use parameterised placeholders (`?`) with bound parameters:

```python
conn.execute("SELECT * FROM members WHERE id=?", (member_id,))
```

This is the primary defence against SQL injection. The database driver handles escaping and quoting of parameter values, making it impossible for user input to be interpreted as SQL code.

This practice is applied consistently across both `database.py` and `dashboard/app.py`. Even dynamically constructed WHERE clauses in the dashboard (for filtering logs) use parameterised queries:

```python
where_parts.append("s.direction = ?")
params.append(direction)
```

## Input Validation

### Form Validation

Both the kiosk and dashboard validate that required fields (first name, last name) are not empty before saving. The kiosk shows a `PopupOverlay` error, while the dashboard uses `flash()` messages.

### Date Validation

Export date ranges are validated using `datetime.strptime()` to ensure they match the expected `YYYY-MM-DD` format before being passed to database queries. The single-person export (`/export/person`) treats its `date_from`/`date_to` query params as optional and does not strictly validate their format — they are only ever used in parameterised `DATE(s.timestamp) >= ?` / `<= ?` comparisons, so a malformed value just matches no rows rather than posing an injection risk.

### Direction Constraint

The `sign_ins` table enforces valid directions at the database level:

```sql
direction TEXT NOT NULL CHECK(direction IN ('IN', 'OUT'))
```

This is a database-level constraint that rejects any value other than "IN" or "OUT".

## Data Integrity

### Foreign Key Constraints

Foreign keys are enabled with `PRAGMA foreign_keys=ON` on every connection. Combined with `ON DELETE CASCADE` on all foreign key definitions, this ensures:

- Deleting a member automatically removes their sign-in records, caregiver details, run sheet assignments, and holiday enrolments.
- No orphaned records can exist in child tables.

### Unique Constraints

Several tables enforce uniqueness:
- `admins.username` -- prevents duplicate admin accounts.
- `run_groups.name` -- prevents duplicate run sheet names.
- `notices.post_id` -- prevents duplicate Facebook posts.
- `holiday_enrollments(member_id, period_id)` -- prevents duplicate enrolments.

### Transaction Safety

SQLite connections used with Python's `with` statement provide automatic transaction management:
- Successful execution commits the transaction.
- Any exception rolls back the transaction.

This ensures that multi-statement operations (e.g. creating a member and logging the event) either both succeed or both fail.

## Audit Trail

All significant actions are recorded in the `audit_log` table via the `log_event()` function:

- Member and staff creation, updates, and deletion
- Sign-in and sign-out events
- Dashboard login and logout
- Data exports

The audit log is append-only -- there is no mechanism to delete or modify audit entries through the application. Each entry includes an event type, description, and timestamp.

This provides accountability and traceability for all system operations.

## Error Handling Strategy

### Silent Failures for Non-Critical Operations

Email notifications and audit logging use broad exception handling that silently catches errors:

```python
try:
    # send email / log event
except Exception:
    pass
```

This is intentional for operations that should not disrupt the primary workflow. A failed email should not prevent a sign-in from being recorded.

### User-Facing Errors

Operations that affect data (saving profiles, changing passwords, exporting) show explicit error messages to the user through `PopupOverlay` (kiosk) or `flash()` (dashboard).
