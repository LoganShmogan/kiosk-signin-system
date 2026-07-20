# Build and Deployment

This document covers how the system is built, packaged, and deployed to target platforms.

## Development Setup

### Prerequisites

- Python 3.11 or later
- Tkinter (`python3-tk` package on Linux)

### Installation

```
git clone https://github.com/YOUR_USERNAME/kiosk-signin-system.git
cd kiosk-signin-system
python -m venv .venv
source .venv/bin/activate    # Linux/macOS
.venv\Scripts\activate       # Windows
pip install -r requirements.txt
```

### Running in Development

```
python kiosk_signin/app.py
```

This starts both the kiosk GUI and the web dashboard on port 5000.

### Dependencies

The `requirements.txt` file lists all Python dependencies:

| Package      | Purpose                                          |
|-------------|--------------------------------------------------|
| Flask        | Web dashboard framework                          |
| openpyxl     | Excel (.xlsx) file generation                    |
| Pillow       | Image processing for signature rendering         |
| pytest       | Test framework                                   |
| tkreload     | Live-reload for Tkinter during development       |
| watchdog     | File system monitoring (used by tkreload)        |
| click        | CLI framework (Flask dependency)                 |
| rich         | Terminal formatting                              |

## PyInstaller Builds

The system is packaged into standalone executables using PyInstaller. A single binary bundles the Python interpreter, all dependencies, and application files.

### Build Command

The core PyInstaller command (from the GitHub Actions workflow):

```
pyinstaller --onefile \
    --add-data "dashboard/templates:dashboard/templates" \
    --add-data "dashboard/static:dashboard/static" \
    --add-data "dashboard/app.py:dashboard" \
    --add-data "kiosk_signin/export_util.py:kiosk_signin" \
    --hidden-import flask \
    kiosk_signin/app.py \
    --name KioskSignIn
```

### Key Options

- `--onefile` -- Produces a single executable file rather than a directory of files. At runtime, the executable extracts its contents to a temporary directory.
- `--add-data` -- Bundles non-Python files (HTML templates, CSS, static assets) into the executable. The format is `source:destination` (colon on Linux, semicolon on Windows).
- `--hidden-import flask` -- Tells PyInstaller to include Flask, which it might not detect because the import happens inside a function (lazy import in `app.py`).

### Runtime Path Handling

When running from a PyInstaller bundle, the application detects the frozen state and adjusts paths:

```python
if getattr(sys, "frozen", False):
    _base_dir = os.path.dirname(sys.executable)
    _template_dir = os.path.join(sys._MEIPASS, "dashboard", "templates")
```

- `sys.frozen` is set to `True` when running inside a PyInstaller bundle.
- `sys._MEIPASS` points to the temporary directory where the bundle's contents are extracted.
- `sys.executable` points to the actual executable file on disk.

### Database Location

In development, the database is stored alongside the source code (`kiosk_signin/signin_data.db`). In a PyInstaller bundle, the internal filesystem is read-only, so the database is stored in a writable location:

- **Windows**: `%LOCALAPPDATA%\Kiosk Sign-In\signin_data.db`
- **Linux**: Same directory as the executable

```python
if getattr(sys, "frozen", False):
    _data_dir = os.path.join(
        os.environ.get("LOCALAPPDATA", os.path.dirname(sys.executable)),
        "Kiosk Sign-In",
    )
    os.makedirs(_data_dir, exist_ok=True)
    DB_PATH = os.path.join(_data_dir, "signin_data.db")
```

## CI/CD Pipeline

### GitHub Actions Workflow

The build workflow (`.github/workflows/build.yml`) runs automatically when a GitHub release is created. It builds executables for two platforms in parallel:

#### Windows (x64)

```yaml
build-windows:
    runs-on: windows-latest
    steps:
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt pyinstaller
      - run: pyinstaller ... --name KioskSignIn-Windows
```

Runs on a standard Windows runner. Produces an `.exe` file. This is the binary used on the kiosk device.

#### Linux (x64)

```yaml
build-linux-x64:
    runs-on: ubuntu-22.04
```

Built on Ubuntu 22.04 to match Pop!_OS 22.04's glibc version. Requires `python3-tk` and `python3-dev` system packages. Used for development/testing rather than kiosk deployment.

### Release Artifacts

Each build job uploads its executable to the GitHub release using `softprops/action-gh-release@v2`. The release page then has two downloadable binaries:

- `KioskSignIn-Windows.exe`
- `KioskSignIn-Linux-x64`

### Workflow Trigger

The workflow is triggered by the `release: created` event:

```yaml
on:
  release:
    types: [created]
```

To create a release: go to the GitHub repository > Releases > Draft a new release > Create a tag (e.g. `v1.0.0`) > Publish. The workflow starts automatically and attaches the built binaries.

## Target Platform: Windows Kiosk

The primary deployment target is a Windows 10 touchscreen PC (an HP kiosk unit) installed on-site.

### Hardware

- Windows 10 PC with a touchscreen
- HP kiosk unit (as currently deployed)

### Deployment Steps

1. Download `KioskSignIn-Windows.exe` from the GitHub release.
2. Copy it to the kiosk PC (no installer needed — it's a single-file executable).
3. Run it. The kiosk window opens maximised and the web dashboard starts automatically on port 5000.
4. Optionally configure it to start on login (e.g. a shortcut in the Windows Startup folder, or Task Scheduler) so the kiosk comes up automatically after a reboot.

### Network Access

The dashboard is served on `0.0.0.0:5000`, making it accessible from any device on the same network. This allows administrators to access the dashboard from their own computer or phone while the kiosk remains at the sign-in point.
