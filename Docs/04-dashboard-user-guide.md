# Dashboard User Guide

This document explains how to use the web-based dashboard for managing the Kiosk Sign-In System remotely.

## Accessing the Dashboard

The dashboard can be hosted behind a reverse tunnel and reached anywhere at a URL like:

```
https://kiosk-dashboard.example.com/login
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

The dashboard is protected by a name and PIN, looked up against the `dashboard_users` table -- there's no longer a single shared password for everyone.

- **Default admin login:** name `admin`, PIN `1234` (seeded on first run -- change this from the "Manage Dashboard Users" page as soon as you've set up real accounts)
- **Staff logins:** created by an admin (see "Manage Dashboard Users" below), using whatever name and PIN the admin sets for them

Enter your name and PIN and click "Log In". Admin accounts land on the main dashboard; staff accounts land straight on the Sign In / Out page. Repeated failed login attempts from the same device are temporarily rate-limited. Use the "Logout" link to end your session.

Sessions are managed using Flask's built-in session handling with a server-side secret key, secure cookie settings, and CSRF protection on every form -- see [09-authentication-and-security.md](09-authentication-and-security.md) for details.

## Sign In / Out

Every logged-in user (admin or staff) can use this page -- it's the web equivalent of the kiosk's sign-in/out flow.

1. **Find people.** Use the Members/Staff tabs to choose which list you're searching, then type a name into the search box. Matching results appear in a dropdown as you type.
2. **Select.** Click a result to add them to the "Selected" list, shown as removable chips. You can select more than one person at once (e.g. siblings arriving together).
3. **Alerts.** If any selected person has an active alert (set up on the Alerts page), a popup shows the alert message(s) before you continue -- the same warning the kiosk shows.
4. **Choose IN or OUT, add notes, and sign.** Pick a direction, optionally type a note, and optionally sign in the signature box (draw with a mouse or a finger on a touchscreen/phone -- "Clear Signature" resets it). A signature is not required.
5. **Submit.** Everyone selected who's actually eligible for that direction (e.g. not already signed in) is recorded; anyone who isn't eligible is skipped and called out in the confirmation message, exactly like the kiosk.

This page is also mobile-friendly, so it can be used from a phone.

## Who's Here (Staff)

Staff accounts get a lightweight, read-only "Who's Here" page (`/status`) -- the closest thing to a dashboard they can see. It shows only:

- **Signed In Today** and **Currently In** counts for today.
- A "Currently Signed In" list of everyone whose most recent sign event today is IN, with their sign-in time.

It has none of the historical charts, and none of the People/Exports/Alerts/Audit/Dashboard Users management links -- those stay admin-only. Admins can also open this page (it's not staff-exclusive), but they normally use the fuller Dashboard instead.

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

- **Search** -- Filter to visits matching a name (matches first name, last name, or the two together).
- **Status** -- Filter to "Still signed in" (an open visit with no sign-out yet), "Signed out", or All.
- **Date From / Date To** -- Filter to a specific date range.

All three filters combine (e.g. a search term plus a status plus a date range narrows to visits matching all of them at once). Click "Filter" to apply, or "Clear" to reset every field. The result count is displayed at the top.

### Pagination

Results are paginated at 50 records per page. Use the page navigation links at the bottom to move between pages.

### Correcting or Adding a Sign-In or Sign-Out Time

Each In and Out time on the Logs page has its own link next to it:

- **Edit** -- shown when that side of the visit already has a recorded event. Click it to open a small form pre-filled with the current date/time; pick a new one and click "Save". The change is recorded in the Audit Log (event type `SIGN_TIME_EDITED`) noting the old and new timestamps, so there's a record of who corrected what.
- **Add** -- shown instead of Edit when that side is missing, e.g. someone forgot to sign out (an open visit with no Out time) or forgot to sign in (a stray Out with no In). Click it to open a form defaulting to the same day as the recorded side of the visit; enter the correct date/time and click "Save" to create the missing record. This is recorded in the Audit Log (event type `SIGN_TIME_ADDED`).

In and Out times are edited or added independently -- correcting or filling in one doesn't touch the other.

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

The edit form also shows a "Last Signature on File" card -- the image of the signature this person most recently used to sign in or out. If they haven't signed in yet, or none of their recorded sign-ins captured a signature, it shows "No signature on file yet." instead.

### Deleting a Record

On the edit form, click "Delete" and confirm. This permanently removes the person and all associated data (sign-in records, caregiver details, run sheet assignments).

### Exporting One Person's History

The person's edit page has an "Export Sign-in History" button, which downloads that one person's complete sign-in/out history as an Excel file, one row per sign-in/out session -- the same layout used everywhere else exports show up. This is a quick way to get one person's records without setting up a date range -- for a specific date range, use the Exports page instead (below).

## Exports

The Exports page provides Excel (.xlsx) downloads of sign-in data. There is no bulk "export every member" option -- use "Export a Person's Sign-ins" below to export one member (or all of them one at a time). Staff, however, can still be exported either in bulk or one at a time from a single card.

Member and staff exports share the exact same layout -- one worksheet per person, one row per sign-in/out session -- so they read identically regardless of which export you use; the only difference is the title text on the sheet.

### Staff Export

Nobody is restricted to one AM and one PM sign -- anyone can sign in and out any number of times, at any time of day -- so this export lists every sign-in/out session that actually happened rather than a fixed AM/PM grid.

1. Choose a staff member from the dropdown, or leave it on "All Staff" to export everyone.
2. Select a date range.
   - With "All Staff" selected, both dates are required.
   - With a specific staff member selected, the dates are optional -- leave both blank to export their entire sign-in history.
3. Click "Download Staff Export".
4. An Excel file downloads (portrait orientation) with one worksheet (tab) per staff member -- so downloading "All Staff" gives you one tab per person to flip between, not one long combined sheet. Each person's sheet has:
   - A name / role / year banner at the top (the year is shown once per person, not repeated on every row -- unless the exported range spans a calendar year boundary, in which case it shows a range like "2026–2027")
   - One row per session, in the order it happened: date (day/month), sign-in time, sign-out time, and duration
   - If they haven't signed out of a session yet, that row shows "Still signed in" instead of a sign-out time, and the duration is left blank
   - A signature image row underneath a session's row, when a signature was captured for it
   - A "Total time in the centre" line at the end of their sheet, summing every session in the range

A person with a lot of sessions in the range can spill onto extra printed pages by themselves.

### Export a Person's Sign-ins

Use this when you want just one person's records instead of the whole roster -- this is also the way to export a single member's history, since there's no bulk member export:

1. Select a person from the dropdown (grouped into Members and Staff).
2. Optionally enter a "From" and "To" date. Leave both blank to export that person's entire sign-in history.
3. Click "Download Person Export".
4. The file uses the same one-worksheet-per-person, one-row-per-session layout described above for the staff export, regardless of whether the selected person is a member or staff.

## Manage Dashboard Users (Admin Only)

This page lists everyone who can log into the dashboard and lets an admin create new logins.

### Creating a Login

Enter a name and PIN, choose "Staff (Sign In / Out only)" or "Admin (full access)", and click "Create User". The name must be unique -- if it's already taken, you'll get an error asking you to pick another.

### Deleting a Login

Click "Delete" next to a user and confirm. You cannot delete the only remaining admin account -- create a second admin first if you need to remove one.

## Navigation

The dashboard has a consistent navigation bar at the top of every page. On phone-sized screens it collapses behind a menu icon (☰). Links shown depend on your role:

- **Everyone:** Sign In / Out, Logout
- **Staff only:** Who's Here (today's counts and currently-signed-in list)
- **Admins only:** Dashboard (analytics), Logs (sign-in history), Audit (system events), People (member and staff management), Exports (Excel downloads), Dashboard Users (manage logins)
