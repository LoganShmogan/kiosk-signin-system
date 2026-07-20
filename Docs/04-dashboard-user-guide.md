# Dashboard User Guide

This document explains how to use the web-based dashboard for managing the Kiosk Sign-In System remotely.

## Accessing the Dashboard

The dashboard is hosted on a cloudflare tunnel and can be reached anywhere at:

```
http://<dashboard-host>:5000/login
```

The dashboard runs on port 5000. When the kiosk is running, access it from any browser on the same network:

```
http://<kiosk-ip-address>:5000
```

On the kiosk machine itself:

```
http://localhost:5000
```

The dashboard can also be run standalone without the kiosk:

```
python dashboard/app.py
```

## Login

The dashboard is protected by a username and password.

- **Default username:** `admin`
- **Default password:** `1234`

Enter your credentials and click "Log In". After logging in, you are redirected to the main dashboard. Use the "Logout" link to end your session.

Sessions are managed using Flask's built-in session handling with a server-side secret key.

## Dashboard (Analytics)

The main dashboard provides an overview of sign-in activity with four summary cards:

- **Signed In Today** -- Number of unique members who signed in today.
- **Currently In** -- Number of members whose latest sign event today is IN (still on premises).
- **Total Members** -- Total number of member records in the database.
- **This Week** -- Number of unique members who signed in during the current week.

Below the summary cards, four charts display historical trends:

1. **Daily Sign-ins (Last 30 Days)** -- Bar chart showing total sign events per day.
2. **Peak Hours (All Time)** -- Bar chart showing sign events by hour of the day.
3. **Weekly Totals (Last 12 Weeks)** -- Bar chart of weekly sign-in totals.
4. **Monthly Totals (Last 12 Months)** -- Bar chart of monthly sign-in totals.

A "Currently Signed In" section lists all members whose most recent sign event today is IN, showing their name and sign-in time.

## Sign-in Logs

The Logs page displays a paginated table of all sign-in and sign-out events, ordered by most recent first. Each row shows:

- Member name
- Direction (IN / OUT)
- Timestamp
- Notes

### Filtering

Use the filter controls at the top of the page:

- **Direction** -- Filter by IN, OUT, or All.
- **Date From / Date To** -- Filter to a specific date range.

Click "Filter" to apply. The result count is displayed at the top.

### Pagination

Results are paginated at 50 records per page. Use the page navigation links at the bottom to move between pages.

## Audit Log

The Audit page shows a chronological log of all system events:

- Member and staff profile creation, updates, and deletions
- Sign-in and sign-out events
- Dashboard logins and logouts
- Data exports

Each entry shows the event type, description, and timestamp. Results are paginated at 50 per page.

## People (Members and Staff)

The People page lists all members or staff in the system, with a tab-style toggle between the two types.

### Viewing Members

The members list shows:
- First name, last name
- School
- Date of birth
- Date created
- Linked caregivers

### Viewing Staff

The staff list shows:
- First name, last name
- Role / position
- Date of birth
- Date created

### Searching

Use the search box to filter by first or last name.

### Creating a New Record

Click "Add New Member" or "Add New Staff Member" to open the creation form. Fill in the required fields (first name and last name) and any optional details, then click "Save".

For members, the form includes caregiver and emergency contact sections.

### Editing a Record

Click a person's name in the list to open their edit form. Make changes and click "Save".

The edit form also shows a "Last Signature on File" card — the image of the signature this person most recently used to sign in or out. If they haven't signed in yet, or none of their recorded sign-ins captured a signature, it shows "No signature on file yet." instead.

### Deleting a Record

On the edit form, click "Delete" and confirm. This permanently removes the person and all associated data (sign-in records, caregiver details, run sheet assignments).

### Exporting One Person's History

Each row in the People list has an "Export" link, and the person's edit page has an "Export Sign-in History" button. Both download that one person's complete sign-in/out history as an Excel file, formatted the same way as the bulk exports (AM/PM sheets for members, one row per sign-in/out session for staff). This is a quick way to get one person's records without setting up a date range — for a specific date range, use the Exports page instead (below).

## Exports

The Exports page provides Excel (.xlsx) downloads of sign-in data.

### Member Export

1. Select a date range using the "From" and "To" date pickers.
2. Click "Export Members".
3. An Excel file downloads to your browser. Each calendar day in the range gets its own sheet (tab) so a week or month export doesn't collapse into a single row per member; every sheet has the same columns per member:
   - Name
   - AM Sign In time + signature
   - AM Sign Out time + signature
   - PM Sign In time + signature
   - PM Sign Out time + signature

Signatures are rendered as embedded PNG images in the spreadsheet.

### Staff Export

Staff aren't restricted to one AM and one PM sign like members are — they can sign in and out any number of times, at any time of day — so this export lists every sign-in/out session that actually happened rather than a fixed AM/PM grid.

1. Select a date range.
2. Click "Export Staff".
3. An Excel file downloads (portrait orientation) with one section per staff member:
   - A name / role / year banner at the top (the year is shown once per person, not repeated on every row — unless the exported range spans a calendar year boundary, in which case it shows a range like "2026–2027")
   - One row per session, in the order it happened: date (day/month), sign-in time, sign-out time, and duration
   - If they haven't signed out of a session yet, that row shows "Still signed in" instead of a sign-out time, and the duration is left blank
   - A signature image row underneath a session's row, when a signature was captured for it
   - A "Total time in the centre" line at the end of their section, summing every session in the range

Each person's section starts on a fresh page; a person with a lot of sessions in the range can spill onto extra pages by themselves.

### Export a Person's Sign-ins

Use this when you want just one person's records instead of the whole roster:

1. Select a person from the dropdown (grouped into Members and Staff).
2. Optionally enter a "From" and "To" date. Leave both blank to export that person's entire sign-in history.
3. Click "Download Person Export".
4. The file uses the same member (AM/PM sheets, one-sheet-per-day) or staff (one row per session) layout as the bulk exports, depending on the selected person's type.

## Navigation

The dashboard has a consistent navigation bar at the top of every page with links to:

- Dashboard (analytics)
- Logs (sign-in history)
- Audit (system events)
- People (member and staff management)
- Exports (Excel downloads)
- Logout
