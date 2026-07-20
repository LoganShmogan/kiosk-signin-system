# Kiosk Sign-In System

A sign-in/out kiosk and web dashboard for tracking member and staff attendance. Built originally for a childcare/after-school programme, but the data model (members, caregivers, run groups) generalises to any small organisation that needs sign-in/out tracking with a touchscreen kiosk. The kiosk runs as a fullscreen Tkinter application on a Windows touchscreen PC, while the web dashboard runs alongside it on the local network for staff to manage records and view analytics.

## Features

- Member and staff sign-in/out with required signature capture (a sign event cannot be submitted without a signature)
- Caregiver contact management with email notifications on sign-in/out
- Run sheet management for grouping members
- Admin panel with password-protected access
- Web dashboard with sign-in analytics, charts, and data exports
- Excel export of member and staff sign-in records with embedded signatures, including a single-person export with an optional date range
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
- Dashboard login: `admin` / `1234`

**Change these, and the Flask `secret_key` in `dashboard/app.py`, before using this anywhere beyond local development.**

## Testing

Tests use pytest and are located in the `tests/` directory.

```
pytest
```

## Pre-built Binaries

A GitHub Actions workflow builds standalone executables on release for:

- Windows (x64) -- the kiosk's deployment platform
- Linux (x64) -- for development/testing

These are single-file executables bundled with PyInstaller and attached to each GitHub release.

## Tech Stack

- **Kiosk UI:** Python, Tkinter
- **Database:** SQLite (WAL mode)
- **Web Dashboard:** Flask, HTML/CSS, Chart.js
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
├── facebook_api.py               # Facebook Graph API integration for notices (LEGACY)
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
│   └── social_screen.py          # Facebook notice board display (LEGACY)
└── components/
    ├── __init__.py
    ├── widgets.py                # Reusable UI widgets
    └── virtual_keyboard.py       # On-screen keyboard for kiosk mode

dashboard/
├── app.py                        # Flask web application
├── static/
│   └── style.css                 # Dashboard stylesheet
└── templates/
    ├── base.html                 # Base layout template
    ├── login.html                # Login page
    ├── dashboard.html            # Analytics dashboard with charts
    ├── logs.html                 # Sign-in/out log viewer
    ├── audit.html                # Audit log viewer
    ├── exports.html              # Excel export date picker
    ├── people.html               # Member and staff listing
    └── person_form.html          # Member/staff create and edit form
```
