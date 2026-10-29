<p align="center">
  <a href="https://savepoint.co.nz"><img src="Docs/assets/save-point-banner.png" alt="Save Point" width="480"></a>
</p>

<h1 align="center">Kiosk Sign-In System</h1>

<p align="center">
  A touchscreen sign-in/out kiosk and web dashboard for tracking member and staff attendance.<br>
  Built by <a href="https://savepoint.co.nz"><b>Save Point Limited</b></a>, New Zealand.
</p>

<p align="center">
  <a href="Docs/">Docs</a> ·
  <a href="Docs/03-kiosk-user-guide.md">Kiosk Guide</a> ·
  <a href="Docs/04-dashboard-user-guide.md">Dashboard Guide</a> ·
  <a href="Docs/09-authentication-and-security.md">Security</a> ·
  <a href="LICENSE">Licence</a>
</p>

---

> [!NOTE]
> This is the general-purpose version of the sign-in system Save Point built for an after-school childcare programme. Its data model (members, caregivers, run groups) works for any small organisation that needs sign-in/out tracking with a touchscreen kiosk. It is open source under the [MIT Licence](LICENSE).

## What it does

The kiosk runs as a fullscreen Tkinter app on a Windows touchscreen PC. The web dashboard runs alongside it on the local network so staff can manage records and see analytics.

- **✍️ Sign in and out.** Members and staff sign in or out from the kiosk or a mobile-friendly web page, with optional signature capture.
- **📋 Run sheets and bulk sign-in.** Group members into run sheets on the kiosk or dashboard, then sign a whole sheet (or everyone currently in) in or out at once.
- **📧 Caregiver notifications.** Caregivers get an email when their child is signed in or out.
- **📊 Analytics and logs.** A mobile-first dashboard with charts, searchable logs, and in-place correction, backfill or deletion of sign-in/out times.
- **🧾 Exports.** Excel (with embedded signatures), PDF and CSV, one worksheet per person, for everyone or a single person over a date range.
- **🕒 Staff timesheets.** Staff can view and download their own sign-in/out history once an admin links their login to their staff record.
- **🔒 Secure by default.** Multiple dashboard logins with admin/staff roles, hashed and salted passwords, CSRF protection, rate limiting, account lockout and a full audit log.
- **⌨️ Kiosk-ready.** A virtual on-screen keyboard for Windows kiosk mode.

## Quick start

Requires Python 3.11+ and Tkinter (`sudo apt install python3-tk` on Linux).

```sh
git clone https://github.com/LoganShmogan/kiosk-signin-system.git
cd kiosk-signin-system
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env              # set DASHBOARD_SECRET_KEY
python kiosk_signin/app.py        # kiosk + dashboard on http://localhost:5000
```

The kiosk opens maximised on Windows, or in a fixed 1280x720 window on Linux for development. To run the dashboard on its own, use `python dashboard/app.py`.

> [!WARNING]
> **Change the default credentials before using this anywhere beyond local development.** The kiosk admin password is `admin1234` and the dashboard login is name `admin`, password `1234`. New or changed passwords must be at least 10 characters with a number and a special character. Without `DASHBOARD_SECRET_KEY` set, a random key is generated each run and everyone is logged out on restart. See [Authentication and Security](Docs/09-authentication-and-security.md).

## Testing

```sh
pytest
pytest --cov --cov-report=term-missing
```

`.coveragerc` requires 100% coverage, including the Tkinter kiosk screens. They're driven through real widgets, so they need a display; CI runs them under `xvfb-run`. See [Testing](Docs/10-testing.md).

## Releases

A GitHub Actions workflow builds single-file PyInstaller executables on each release and attaches them to it:

- **Windows (x64)**, the kiosk's deployment platform
- **Linux (x64)**, for development and testing

## Tech stack

| Area | Technology |
|---|---|
| Kiosk UI | Python, Tkinter |
| Database | SQLite (WAL mode) |
| Web dashboard | Flask, Waitress, Flask-WTF (CSRF), Flask-Limiter, HTML/CSS, Chart.js |
| Exports | openpyxl (Excel), xhtml2pdf (PDF), stdlib `csv`, Pillow (signatures) |
| Notifications | SMTP (Gmail) |
| CI/CD | GitHub Actions, PyInstaller |

## Documentation

The full walkthrough is in **[Docs/](Docs/)**, with printable PDFs in `Docs/PrintableDocs/`.

| Doc | What's in it |
|---|---|
| [Architecture Overview](Docs/01-architecture-overview.md) | How the kiosk, dashboard and database fit together |
| [Database Design](Docs/02-database-design.md) | Tables, relationships and queries |
| [Kiosk User Guide](Docs/03-kiosk-user-guide.md) | Using the touchscreen kiosk |
| [Dashboard User Guide](Docs/04-dashboard-user-guide.md) | Using the web dashboard |
| [Tkinter UI Framework](Docs/05-tkinter-ui-framework.md) | Screens, widgets and theming |
| [Flask Web Dashboard](Docs/06-flask-web-dashboard.md) | Routes, templates and static files |
| [Export System](Docs/07-export-system.md) | Excel, PDF and CSV exports |
| [Email Integration](Docs/08-email-integration.md) | Caregiver notifications |
| [Authentication and Security](Docs/09-authentication-and-security.md) | Logins, roles, passwords and protections |
| [Testing](Docs/10-testing.md) | Running tests and coverage |
| [Threading and Concurrency](Docs/11-threading-and-concurrency.md) | Running the kiosk and dashboard together |
| [Build and Deployment](Docs/12-build-and-deployment.md) | Building releases and installing |
| [Dashboard Hosting](Docs/14-dashboard-hosting.md) | Optional: publishing the dashboard through a Cloudflare Tunnel |

To regenerate the PDFs after changing the `.md` files:

```sh
pip install markdown
python Docs/generate_printable_docs.py
```

<details>
<summary><b>File tree</b></summary>

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
    ├── signin.html               # Web Sign In / Out page (any logged-in user)
    ├── status.html               # "Who's Here" read-only view (staff home page)
    ├── dashboard.html            # Analytics dashboard with charts
    ├── logs.html                 # Sign-in/out log viewer
    ├── sign_edit.html            # Correct an existing sign-in/out time
    ├── sign_add.html             # Add a missing sign-in/out time
    ├── _sign_bounds.html         # Shared "must be between" time hint for sign edit/add
    ├── audit.html                # Audit log viewer
    ├── alerts.html               # Sign-in alert creation and list
    ├── exports.html              # Export date picker (Excel/PDF/CSV)
    ├── people.html               # Member and staff listing
    ├── person_form.html          # Member/staff create and edit form
    ├── run_sheets.html           # Run sheet list/search (any logged-in user)
    ├── run_sheet_form.html       # Run sheet create/edit form (any logged-in user)
    ├── my_timesheet.html         # Self-service staff timesheet (any linked user)
    ├── dashboard_users.html      # Manage dashboard login accounts (admin only)
    └── dashboard_user_edit.html  # Edit a dashboard login (admin only)
```

</details>

### Configuration

- `.env.example`: copy to `.env` for `DASHBOARD_SECRET_KEY` and `DASHBOARD_COOKIE_SECURE`. It's loaded automatically by `python-dotenv`, and `.env` itself is gitignored.
- `.coveragerc`: pytest coverage configuration.
- `.github/workflows/test.yml`: runs the test suite with coverage on every push and pull request.
- `.github/workflows/build.yml`: builds and attaches the Windows and Linux binaries on a GitHub release.

## Ownership

**Kiosk Sign-In System** is built and maintained by Save Point Limited, a New Zealand company (company number 9392145), and released under the [MIT Licence](LICENSE).

- Website: [savepoint.co.nz](https://savepoint.co.nz)
- General enquiries: [contact@savepoint.co.nz](mailto:contact@savepoint.co.nz)
- Support, privacy and security: [support@savepoint.co.nz](mailto:support@savepoint.co.nz)

"Save Point" and the Save Point flag logo are the property of Save Point Limited and are not covered by the MIT Licence.
