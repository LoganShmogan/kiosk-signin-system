# Flask Web Dashboard

This document describes the web dashboard's architecture, the Flask concepts applied, and how the backend communicates with the frontend.

## Overview

The web dashboard is a server-side rendered Flask application. It provides administrators with analytics, sign-in logs, people management, and data export functionality through a standard web browser.

The dashboard code lives in the `dashboard/` directory:
- `app.py` -- All routes, logic, and database queries.
- `templates/` -- Jinja2 HTML templates.
- `static/style.css` -- Stylesheet.

## Flask Application Setup

The Flask app is created with standard configuration:

```python
app = Flask(__name__)
app.secret_key = "kiosk-dashboard-secret-key"
```

The secret key is used for signing session cookies. When running from a PyInstaller bundle, the template and static directories are resolved relative to the bundle's temporary extraction directory (`sys._MEIPASS`).

## Routing

Flask uses decorators to map URL paths to Python functions. The dashboard defines these routes:

| Route                          | Method     | Purpose                          |
|--------------------------------|------------|----------------------------------|
| `/`                            | GET        | Redirect to dashboard or login   |
| `/login`                       | GET, POST  | Login form and authentication    |
| `/logout`                      | GET        | Clear session and redirect       |
| `/dashboard`                   | GET        | Analytics overview               |
| `/logs`                        | GET        | Paginated sign-in log            |
| `/audit`                       | GET        | Paginated audit log              |
| `/people`                      | GET        | Member or staff listing          |
| `/people/new`                  | GET, POST  | Create a new person              |
| `/people/<int:person_id>`      | GET, POST  | Edit an existing person          |
| `/people/<int:person_id>/delete`| POST      | Delete a person                  |
| `/exports`                     | GET        | Export page                      |
| `/export/members`              | GET        | Download member Excel file       |
| `/export/staff`                | GET        | Download staff Excel file        |
| `/export/person`               | GET        | Download one person's Excel file (`person_id` required; `date_from`/`date_to` optional query params) |
| `/people/<int:person_id>/signature.png` | GET | Stream that person's most recently used signature as a PNG (404 if none on file) |

## Authentication

The dashboard uses a simple session-based authentication system:

1. User submits username and password via the login form.
2. The server compares them against hardcoded credentials.
3. On success, `session["logged_in"] = True` is set.
4. A `login_required` decorator checks this flag on protected routes.

```python
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated
```

The `@wraps(f)` decorator from `functools` preserves the original function's name and docstring, which Flask needs for `url_for()` to work correctly.

## Template Rendering (Jinja2)

Flask uses Jinja2 as its template engine. Templates live in `dashboard/templates/` and use template inheritance:

### Base Template (`base.html`)

Defines the page skeleton: HTML head, navigation bar, flash message area, and a content block. All other templates extend this:

```html
{% extends "base.html" %}
{% block content %}
  <!-- page-specific content -->
{% endblock %}
```

### Template Variables

Python data is passed to templates via `render_template()`:

```python
return render_template(
    "dashboard.html",
    today_ins=today_ins,
    daily_labels=json.dumps(daily_labels),
    daily_values=json.dumps(daily_values),
    # ...
)
```

Lists and dictionaries intended for JavaScript (chart data) are serialised to JSON with `json.dumps()` in Python and then parsed in the template with Jinja2's `| safe` filter or `| tojson`.

### Flash Messages

The dashboard uses Flask's `flash()` system for one-time status messages:

```python
flash("Changes saved.", "success")
flash("First name and last name are required.", "error")
```

These are rendered in the base template after redirect, providing user feedback for form submissions.

## Database Access

The dashboard has its own `get_conn()` function that connects to the same SQLite database as the kiosk. For operations that involve the kiosk's data models (creating/updating members, caregivers), it imports functions directly from the kiosk's `database.py` module:

```python
from database import upsert_member, upsert_caregiver
```

This avoids duplicating business logic. The imports are done inside route functions (lazy imports) rather than at module level to avoid import order issues when both the kiosk and dashboard initialise.

## Analytics Queries

The dashboard route performs several aggregate queries to compute statistics:

### Currently Signed In

Uses a correlated subquery to find members whose most recent sign event today has direction "IN":

```sql
SELECT COUNT(*) FROM (
    SELECT s.member_id FROM sign_ins s
    WHERE DATE(s.timestamp) = ?
    AND s.direction = 'IN'
    AND s.id = (
        SELECT MAX(id) FROM sign_ins s2
        WHERE s2.member_id = s.member_id
        AND DATE(s2.timestamp) = ?
    )
)
```

This finds each member's latest sign event today (by maximum ID) and counts only those where the direction is IN.

### Daily Totals

Groups sign events by date for the last 30 days. The Python code then fills in gaps (days with zero events) to produce a continuous series for the chart:

```python
for i in range(30, -1, -1):
    d = (date.today() - timedelta(days=i)).isoformat()
    daily_labels.append(d[5:])
    daily_values.append(daily_map.get(d, 0))
```

### Peak Hours

Uses SQLite's `strftime('%H', timestamp)` to extract the hour from each sign event and groups by hour across all time.

### Weekly and Monthly Totals

Uses `strftime('%Y-W%W', timestamp)` and `strftime('%Y-%m', timestamp)` respectively to group sign events into week and month buckets.

## Pagination

The logs, audit, and people pages implement server-side pagination:

```python
page = max(1, int(request.args.get("page", 1)))
per_page = 50
offset = (page - 1) * per_page
total_pages = max(1, (total + per_page - 1) // per_page)
```

The total count is queried first, then the page's rows are fetched with `LIMIT ? OFFSET ?`. Page navigation links are generated in the template.

## Filtering

The logs page supports filtering by direction and date range using query parameters. Filter conditions are dynamically built:

```python
where_parts = []
params = []
if direction in ("IN", "OUT"):
    where_parts.append("s.direction = ?")
    params.append(direction)
if date_from:
    where_parts.append("DATE(s.timestamp) >= ?")
    params.append(date_from)
where_clause = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""
```

This approach safely constructs SQL WHERE clauses while still using parameterised queries to prevent injection.

## File Downloads

The export routes generate Excel files in memory using `io.BytesIO()` and send them to the browser with `send_file()`:

```python
buf = io.BytesIO()
generate_export(signs, date_from, date_to, buf)
buf.seek(0)
return send_file(buf, as_attachment=True, download_name=filename,
                 mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
```

The `as_attachment=True` flag tells the browser to download the file rather than displaying it. The MIME type specifies the `.xlsx` format.

## Charts (Client-Side)

The dashboard page uses Chart.js (loaded from a CDN in the template) to render interactive charts. Chart data is injected into the HTML as JSON:

```html
<script>
  const dailyLabels = {{ daily_labels | safe }};
  const dailyValues = {{ daily_values | safe }};
  new Chart(ctx, { type: 'bar', data: { labels: dailyLabels, datasets: [...] } });
</script>
```

The `| safe` filter tells Jinja2 not to escape the JSON string, since it was already serialised safely in Python.

## Form Handling

People creation and editing use standard HTML forms with POST method. Flask's `request.form` dictionary provides access to submitted values:

```python
data = {
    "first_name": request.form.get("first_name", "").strip(),
    "last_name":  request.form.get("last_name", "").strip(),
    # ...
}
```

Multi-value form fields (like day checkboxes) use `request.form.getlist()` and are joined into comma-separated strings for storage.

After a successful save, the pattern is Post/Redirect/Get (PRG): the route processes the form, then redirects to the edit page. This prevents duplicate submissions if the user refreshes the page.
