# Kiosk Sign-In System

A sign-in/out kiosk and web dashboard for tracking member and staff attendance. Built originally for a childcare/after-school programme, but the data model (members, caregivers, run groups) generalises to any small organisation that needs sign-in/out tracking with a touchscreen kiosk. The kiosk runs as a fullscreen Tkinter application on a Windows touchscreen PC, while the web dashboard runs alongside it on the local network for staff to manage records and view analytics.

## Features

- Member and staff sign-in/out with optional signature capture, from the kiosk or a mobile-friendly web page
- Caregiver contact management with email notifications on sign-in/out
- Run sheet management for grouping members, usable for signing a group in or out
- Multi-user web dashboard logins with admin/staff roles, CSRF protection, and login rate limiting
- Admin panel with password-protected access
- Web dashboard with sign-in analytics, charts, searchable/filterable logs, and in-place correction or backfill of a sign-in/out time
- Excel export of member and staff sign-in records with embedded signatures, one worksheet per person, including a single-person export with an optional date range
- Audit logging of all system events
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
- Dashboard login: name `admin`, PIN `1234` (a `dashboard_users` account, seeded on first run)

**Change these before using this anywhere beyond local development.** Additional dashboard logins (admin or staff role) can be created from the "Manage Dashboard Users" page once logged in as admin. Set `DASHBOARD_SECRET_KEY` in the environment (see `.env.example`) so dashboard sessions survive restarts -- without it, a random key is generated each run and everyone is logged out.

## Testing

Tests use pytest and are located in the `tests/` directory.

```
pytest
```

With coverage:

```
pytest --cov --cov-report=term-missing
```

`.coveragerc` sets the required coverage threshold; see [Docs/10-testing.md](Docs/10-testing.md) for what's covered and the known gap (no automated tests yet for the Tkinter kiosk screens).

## Pre-built Binaries

A GitHub Actions workflow builds standalone executables on release for:

- Windows (x64) -- the kiosk's deployment platform
- Linux (x64) -- for development/testing

These are single-file executables bundled with PyInstaller and attached to each GitHub release.

## Printable Docs

`Docs/generate_printable_docs.py` converts every `Docs/*.md` file into a styled PDF under `Docs/PrintableDocs/`. It's a docs-authoring-time tool, not a runtime dependency, so its packages aren't in `requirements.txt`:

```
pip install markdown xhtml2pdf
python Docs/generate_printable_docs.py
```

Re-run it any time the `.md` files change to regenerate the PDFs.

## Tech Stack

- **Kiosk UI:** Python, Tkinter
- **Database:** SQLite (WAL mode)
- **Web Dashboard:** Flask, Waitress (production WSGI server), Flask-WTF (CSRF), Flask-Limiter (rate limiting), HTML/CSS, Chart.js
- **Exports:** openpyxl (Excel), Pillow (signature rendering)
- **Notifications:** SMTP (Gmail)
- **CI/CD:** GitHub Actions, PyInstaller

## License

MIT License. See [LICENSE](LICENSE) for details.

## File Tree

```
kiosk_signin/
├── app.py                        # Main application entry point
├── database.py                   # SQLite schema, queries, and data access
├── theme.py                      # Colours, fonts, and widget style helpers
├── export_util.py                # Excel export generation (members and staff)
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
│   ├── bus_sheets_screen.py      # Bus sheet management
│   └── social_screen.py          # Contact/social info display screen
└── components/
    ├── __init__.py
    ├── widgets.py                # Reusable UI widgets
    └── virtual_keyboard.py       # On-screen keyboard for kiosk mode

dashboard/
├── app.py                        # Flask web application
├── static/
│   ├── style.css                 # Dashboard stylesheet
│   └── signin.js                 # Web sign-in page: search, selection, signature pad
└── templates/
    ├── base.html                 # Base layout template
    ├── login.html                # Login page
    ├── signin.html                # Web Sign In / Out page (any logged-in user)
    ├── status.html                # "Who's Here" read-only view (staff home page)
    ├── dashboard.html            # Analytics dashboard with charts
    ├── logs.html                 # Sign-in/out log viewer
    ├── sign_edit.html             # Correct an existing sign-in/out time
    ├── sign_add.html               # Add a missing sign-in/out time
    ├── audit.html                # Audit log viewer
    ├── alerts.html                # Sign-in alert creation and list
    ├── exports.html              # Excel export date picker
    ├── people.html               # Member and staff listing
    ├── person_form.html          # Member/staff create and edit form
    └── dashboard_users.html       # Manage dashboard login accounts (admin only)
```

## Configuration

- `.env.example` -- copy to `.env` for `DASHBOARD_SECRET_KEY` and `DASHBOARD_COOKIE_SECURE` (loaded automatically via `python-dotenv` if present; `.env` itself is gitignored).
- `.coveragerc` -- pytest coverage configuration.
- `.github/workflows/test.yml` -- runs the test suite with coverage on every push/PR.
- `.github/workflows/build.yml` -- builds and attaches Windows/Linux binaries on a GitHub release.
