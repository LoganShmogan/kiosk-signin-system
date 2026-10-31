# Security Policy

The Kiosk Sign-In System is open source (MIT) and maintained by **Save Point Limited**.

## Reporting a problem

If you find a security issue, please email **[support@savepoint.co.nz](mailto:support@savepoint.co.nz)** with the subject line "Security: Kiosk Sign-In". Please don't open a public GitHub issue for it.

Include what you found, how to reproduce it, and what an attacker could do with it. We will acknowledge your report within 2 working days and give credit in the release notes if you'd like.

## If you run it yourself

The system stores personal information (members, caregivers, staff, signatures), so keep these out of git. They are all in `.gitignore`:

| File | Contents |
|---|---|
| `.env` | `DASHBOARD_SECRET_KEY` (signs dashboard session cookies). Copy from `.env.example`. |
| `kiosk_signin/email_config.json` | Gmail sender address and app password. Copy from `email_config.example.json`. |
| `kiosk_signin/signin_data.db` (+ `-wal`, `-shm`) | The SQLite database |

Change the default kiosk and dashboard passwords on first run, and set `DASHBOARD_SECRET_KEY` before exposing the dashboard beyond your local network.

## If a secret leaks

| Secret | What to do |
|---|---|
| Gmail app password | Google Account → Security → App passwords: revoke it and create a new one |
| `DASHBOARD_SECRET_KEY` | Generate a new one (`python -c "import secrets; print(secrets.token_hex(32))"`) and restart. Everyone is signed out. |
| A dashboard or kiosk password | Change it from "Manage Dashboard Users" / the admin panel |

How logins, hashing, CSRF and rate limiting work is covered in [Docs/09-authentication-and-security.md](Docs/09-authentication-and-security.md).
