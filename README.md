# Kiosk Sign-In System

A sign-in/out kiosk and web dashboard for tracking member and staff attendance. Built originally for a childcare/after-school programme, but the data model (members, caregivers, run groups) generalises to any small organisation that needs sign-in/out tracking with a touchscreen kiosk. The kiosk runs as a fullscreen Tkinter application on a Windows touchscreen PC, while the web dashboard runs alongside it on the local network for staff to manage records and view analytics.

## Features

- Member and staff sign-in/out with optional signature capture, from the kiosk or a mobile-friendly web page
- Bulk sign in/out on the web dashboard: load a saved run sheet's members, or select everyone currently signed in, instead of adding people one at a time
- Staff self-service "My Timesheet" page: view and download your own sign-in/out history (e.g. for a pay period) once an admin links your login to your staff record
- Caregiver contact management with email notifications on sign-in/out
- Run sheet management for grouping members, on both the kiosk and the web dashboard
- Multi-user web dashboard logins (name + password) with admin/staff roles, CSRF protection, login rate limiting, and per-account lockout after repeated failed logins
- Hashed, salted admin passwords on both the kiosk and the dashboard
- Mobile-first web dashboard with sign-in analytics, charts, security response headers, searchable/filterable logs, and in-place correction, backfill, or deletion of a sign-in/out time
- Excel, PDF, and CSV export of member and staff sign-in records (Excel includes embedded signatures), one worksheet per person, including a single-person export with an optional date range
- Audit logging of all system events, including failed dashboard login attempts
- Virtual on-screen keyboard for Windows kiosk mode

## Requirements

- Python 3.11+
- Tkinter (included with Python on most platforms, install `python3-tk` on Linux)
- Dependencies listed in `requirements.txt`

## Installation

```
git clone https://github.com/LoganShmogan/kiosk-signin-system.git
cd kiosk-signin-system
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Linux you may also need:

```
sudo apt install python3-tk
```

## Usage

Run the kiosk application (this also starts the web dashboard on port 5000):

```
python kiosk_signin/app.py
```

The kiosk opens maximised on Windows (or in a fixed 1280x720 window on Linux, used for development). The web dashboard is accessible at `http://localhost:5000`.

To run the web dashboard on its own:

```
python dashboard/app.py
```

### Default Credentials

- Kiosk admin password: `admin1234`
- Dashboard login: name `admin`, password `1234` (a `dashboard_users` account, seeded on first run)

**Change these before using this anywhere beyond local development.** Additional dashboard logins (admin or staff role) can be created from the "Manage Dashboard Users" page once logged in as admin; new or changed passwords must be at least 10 characters with a number and a special character. A staff login can be linked to that person's staff record so they can use the "My Timesheet" page. See [Docs/09-authentication-and-security.md](Docs/09-authentication-and-security.md). Set `DASHBOARD_SECRET_KEY` in the environment (see `.env.example`) so dashboard sessions survive restarts -- without it, a random key is generated each run and everyone is logged out.

## Testing

Tests use pytest and are located in the `tests/` directory.

```
pytest
```

With coverage:

```
pytest --cov --cov-report=term-missing
```

`.coveragerc` requires 100% coverage, including the Tkinter kiosk screens (driven through real widgets, so they need a display; CI runs them under `xvfb-run`). See [Docs/10-testing.md](Docs/10-testing.md).

## Pre-built Binaries

A GitHub Actions workflow builds standalone executables on release for:

- Windows (x64) -- the kiosk's deployment platform
- Linux (x64) -- for development/testing

These are single-file executables bundled with PyInstaller and attached to each GitHub release.

## Printable Docs

`Docs/generate_printable_docs.py` converts every `Docs/*.md` file into a styled PDF under `Docs/PrintableDocs/`. `xhtml2pdf` is already in `requirements.txt` (the dashboard uses it for PDF exports); `markdown` is only needed for this docs tool:

```
pip install markdown
python Docs/generate_printable_docs.py
```

Re-run it any time the `.md` files change to regenerate the PDFs.

## Tech Stack

- **Kiosk UI:** Python, Tkinter
- **Database:** SQLite (WAL mode)
- **Web Dashboard:** Flask, Waitress (production WSGI server), Flask-WTF (CSRF), Flask-Limiter (rate limiting), HTML/CSS, Chart.js
- **Exports:** openpyxl (Excel), xhtml2pdf (PDF), stdlib `csv` (CSV), Pillow (signature rendering)
- **Notifications:** SMTP (Gmail)
- **CI/CD:** GitHub Actions, PyInstaller

## Documentation

Full documentation lives in [Docs/](Docs/) (printable PDFs in `Docs/PrintableDocs/`):

1. [Architecture Overview](Docs/01-architecture-overview.md)
2. [Database Design](Docs/02-database-design.md)
3. [Kiosk User Guide](Docs/03-kiosk-user-guide.md)
4. [Dashboard User Guide](Docs/04-dashboard-user-guide.md)
5. [Tkinter UI Framework](Docs/05-tkinter-ui-framework.md)
6. [Flask Web Dashboard](Docs/06-flask-web-dashboard.md)
7. [Export System](Docs/07-export-system.md)
8. [Email Integration](Docs/08-email-integration.md)
9. [Authentication and Security](Docs/09-authentication-and-security.md)
10. [Testing](Docs/10-testing.md)
11. [Threading and Concurrency](Docs/11-threading-and-concurrency.md)
12. [Build and Deployment](Docs/12-build-and-deployment.md)
13. [Dashboard Hosting and Network](Docs/14-dashboard-hosting.md) (optional: publishing the dashboard through a Cloudflare Tunnel)

## License

MIT License. See [LICENSE](LICENSE) for details.

## File Tree

```
kiosk_signin/
├── app.py                        # Main application entry point
├── database.py                   # SQLite schema, queries, and data access
├── theme.py                      # Colours, fonts, and widget style helpers
├── export_util.py                # Excel/CSV/PDF export generation (members and staff)
├── email_notifier.py             # Email notifications to caregivers on sign events
├── email_config.json             # SMTP configuration for email notifications
├── README.md
├── screens/
│   ├── __init__.py
│   ├── splash_screen.py          # Tap-to-start and main options screen
│   ├── signin_screen.py          # Member search and sign-in/out flow
│   ├── signature_screen.py       # Signature capture canvas
│   ├── profile_screen.py         # Member profile view and editing
│   ├── staff_profile_screen.py   # Staff profile view and editing
│   ├── admin_screen.py           # Admin password entry and admin panel
│   ├── run_sheets_screen.py      # Run sheet management
│   ├── bus_sheets_screen.py      # Bus sheet screen (not currently registered in app.py)
│   └── social_screen.py          # Contact/social info display screen
└── components/
    ├── __init__.py
    ├── widgets.py                # Reusable UI widgets
    └── virtual_keyboard.py       # On-screen keyboard for kiosk mode

dashboard/
├── app.py                        # Flask web application
├── static/
│   ├── style.css                 # Dashboard stylesheet (mobile-first)
│   ├── layout.js                 # Burger nav and stacked-table labels for small screens
│   ├── signin.js                 # Web sign-in page: search, selection, signature pad
│   ├── person-picker.js          # Shared search-and-select chip widget (sign-in + run sheet form)
│   └── run_sheet_form.js         # Run sheet create/edit form logic
└── templates/
    ├── base.html                 # Base layout template (role-aware nav)
    ├── login.html                # Login page (name + password)
    ├── signin.html                # Web Sign In / Out page (any logged-in user)
    ├── status.html                # "Who's Here" read-only view (staff home page)
    ├── dashboard.html            # Analytics dashboard with charts
    ├── logs.html                 # Sign-in/out log viewer
    ├── sign_edit.html             # Correct an existing sign-in/out time
    ├── sign_add.html               # Add a missing sign-in/out time
    ├── _sign_bounds.html           # Shared "must be between" time hint for sign edit/add
    ├── audit.html                # Audit log viewer
    ├── alerts.html                # Sign-in alert creation and list
    ├── exports.html              # Export date picker (Excel/PDF/CSV)
    ├── people.html               # Member and staff listing
    ├── person_form.html          # Member/staff create and edit form
    ├── run_sheets.html            # Run sheet list/search (any logged-in user)
    ├── run_sheet_form.html        # Run sheet create/edit form (any logged-in user)
    ├── my_timesheet.html          # Self-service staff timesheet (any linked user)
    ├── dashboard_users.html       # Manage dashboard login accounts (admin only)
    └── dashboard_user_edit.html   # Edit a dashboard login (admin only)
```

## Configuration

- `.env.example` -- copy to `.env` for `DASHBOARD_SECRET_KEY` and `DASHBOARD_COOKIE_SECURE` (loaded automatically via `python-dotenv` if present; `.env` itself is gitignored).
- `.coveragerc` -- pytest coverage configuration.
- `.github/workflows/test.yml` -- runs the test suite with coverage on every push/PR.
- `.github/workflows/build.yml` -- builds and attaches Windows/Linux binaries on a GitHub release.
