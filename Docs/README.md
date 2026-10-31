# Kiosk Sign-In System: Documentation

Documentation for the Kiosk Sign-In System kiosk and web dashboard. Built by Save Point Limited. Open source under the [MIT Licence](../LICENSE).

Printable PDFs of these docs are in [`PrintableDocs/`](PrintableDocs/), regenerated with `python Docs/generate_printable_docs.py`.

| # | Doc | Read it when |
|---|---|---|
| 01 | [Architecture overview](01-architecture-overview.md) | You want to know how the kiosk, dashboard and database fit together |
| 02 | [Database design](02-database-design.md) | You need the tables, columns and relationships |
| 03 | [Kiosk user guide](03-kiosk-user-guide.md) | You're signing people in and out or using the admin panel on the kiosk |
| 04 | [Dashboard user guide](04-dashboard-user-guide.md) | You're using the web dashboard |
| 05 | [Tkinter UI framework](05-tkinter-ui-framework.md) | Changing kiosk screens or widgets |
| 06 | [Flask web dashboard](06-flask-web-dashboard.md) | Changing dashboard routes or templates |
| 07 | [Export system](07-export-system.md) | Excel, PDF and CSV exports |
| 08 | [Email integration](08-email-integration.md) | Caregiver notifications and `email_config.json` |
| 09 | [Authentication and security](09-authentication-and-security.md) | Logins, password hashing, CSRF, rate limits, sessions |
| 10 | [Testing](10-testing.md) | Running or adding tests |
| 11 | [Threading and concurrency](11-threading-and-concurrency.md) | Background work and database locking |
| 12 | [Build and deployment](12-build-and-deployment.md) | Building the Windows executable and installing it on the kiosk |
| 14 | [Dashboard hosting and network](14-dashboard-hosting.md) | The Cloudflare Tunnel, routine checks and troubleshooting |

Security reporting and secret handling are in [`../SECURITY.md`](../SECURITY.md).
