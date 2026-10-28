# Dashboard User Guide

This document explains how to use the web-based dashboard for managing the Kiosk Sign-In System remotely.

## Accessing the Dashboard

The dashboard can be published through a tunnel (e.g. Cloudflare Tunnel) and reached from anywhere at a URL like:

```
https://kiosk-dashboard.example.com/login
```

See [14-dashboard-hosting.md](14-dashboard-hosting.md) for how the hosting is set up and what to check if the site is unreachable.

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

The dashboard is protected by a name and password, looked up against the `dashboard_users` table -- there's no longer a single shared password for everyone.

- **Default admin login:** name `admin`, password `1234` (seeded on first run -- change this from the "Manage Dashboard Users" page as soon as you've set up real accounts; `1234` is far too short for the password rules described below, but existing logins are never forced to change, so this old default keeps working until you change it)
- **Staff logins:** created by an admin (see "Manage Dashboard Users" below), using whatever name and password the admin sets for them

Enter your name and password and click "Log In". Admin accounts land on the main dashboard; staff accounts land straight on the Sign In / Out page. Repeated failed login attempts from the same device are temporarily rate-limited, and an individual account is temporarily locked out after 5 wrong attempts in a row (it unlocks itself automatically after about 15 minutes -- no admin action needed). Use the "Logout" link to end your session.

Sessions are managed using Flask's built-in session handling with a server-side secret key, secure cookie settings, and CSRF protection on every form -- see [09-authentication-and-security.md](09-authentication-and-security.md) for details.

## Sign In / Out

Every logged-in user (admin or staff) can use this page -- it's the web equivalent of the kiosk's sign-in/out flow.

1. **Find people.** Use the Members/Staff tabs to choose which list you're searching, then type a name into the search box. Matching results appear in a dropdown as you type.
2. **Select.** Click a result to add them to the "Selected" list, shown as removable chips. You can select more than one person at once (e.g. siblings arriving together).
3. **Alerts.** If any selected person has an active alert (set up on the Alerts page), a popup shows the alert message(s) before you continue -- the same warning the kiosk shows.
4. **Choose IN or OUT, add notes, and sign.** Pick a direction, optionally type a note, and optionally sign in the signature box (draw with a mouse or a finger on a touchscreen/phone -- "Clear Signature" resets it). A signature is not required.
5. **Submit.** Everyone selected who's actually eligible for that direction (e.g. not already signed in) is recorded; anyone who isn't eligible is skipped and called out in the confirmation message, exactly like the kiosk.

This page is also mobile-friendly, so it can be used from a phone.

### Loading a Run Sheet

Instead of searching for people one at a time, you can load a whole saved group at once:

1. **Search for a run sheet.** Type its name into the "Or load a run sheet" box (this searches run sheet names, not people -- see [Run Sheets](#run-sheets) below for how to create one).
2. **Pick it from the dropdown.** Every person in that run sheet is added to the "Selected" list as chips, on top of anyone already selected.
3. **Continue as normal.** Add or remove individual people, choose IN or OUT, and submit exactly as described above.

### Selecting Everyone Currently Signed In

At the end of the day, use this to sign everyone out at once instead of searching for each person:

1. Click **"Select all currently signed in"**.
2. Everyone whose most recent event today is IN is added to the "Selected" list, and the direction automatically switches to **OUT**, since that's the only valid action for people who are already signed in.
3. Review the list, add notes or a signature if needed, and click **Submit**. You can still switch the direction back to IN by hand if you clicked this by mistake.

## Run Sheets

A run sheet is a saved, named group of people (e.g. "Group A" for an afternoon bus pickup) that can be loaded on the Sign In / Out page to sign a whole group in or out at once, instead of searching for each person individually. Run sheets created here are shared with the kiosk (and vice versa) -- they're the same groups either way.

### Viewing and Searching Run Sheets

The Run Sheets page (in the navigation bar) lists every saved run sheet with how many people are in it. Use the search box to filter by name.

### Creating a Run Sheet

1. Click **"+ New Run Sheet"**.
2. Enter a name (e.g. "Group A"). Names must be unique -- if the name is already taken, you'll get an error asking you to choose another.
3. Use the Members/Staff tabs and search box to find and add people, the same way you would on the Sign In / Out page.
4. Click **"Create Run Sheet"**.

### Editing a Run Sheet

Click a run sheet's name (or its "Edit" link) to open it. You can rename it and add or remove members, then click **"Save Changes"**. Renaming to a name another run sheet already has is rejected with an error, and your existing run sheet is left unchanged.

### Deleting a Run Sheet

Click "Delete" next to a run sheet in the list and confirm. This only removes the saved group -- it does not affect anyone's sign-in history.

## Who's Here (Staff)

Staff accounts get a lightweight, read-only "Who's Here" page (`/status`) -- the closest thing to a dashboard they can see. It shows only:

- **Signed In Today** and **Currently In** counts for today.
- A "Currently Signed In" list of everyone whose most recent sign event today is IN, with their sign-in time.

It has none of the historical charts, and none of the People/Exports/Alerts/Audit/Dashboard Users management links -- those stay admin-only. Admins can also open this page (it's not staff-exclusive), but they normally use the fuller Dashboard instead.

## My Timesheet (Staff)

If your dashboard login has been linked to your staff record (an admin does this once from the "Manage Dashboard Users" page -- see below), a "My Timesheet" link appears in the navigation bar. This is your own personal sign-in/out history -- useful for checking your hours before payday, since staff are paid fortnightly.

1. Click **My Timesheet**.
2. You'll see a table of your own sign-in/out sessions. To narrow it down (e.g. to just the current pay fortnight), enter a **From date** and **To date** and click **Filter**. Leave both blank to see your entire history.
3. To get a copy you can keep or print, choose a **Download format** (Excel, PDF, or CSV) and click **Download**. It downloads exactly the date range currently shown on the page.

You can only ever see and download your own history from this page -- there's no way to view anyone else's timesheet here, linked or not.

If you see a message saying your account isn't linked to a staff record, ask an admin to link it from the Manage Dashboard Users page.

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
- **Add** -- shown instead of Edit when that side is missing, e.g. someone forgot to sign out (an open visit with no Out time) or forgot to sign in (a stray Out with no In). Click it to open a form defaulting to just after the sign-in (or just before the sign-out); enter the correct date/time and click "Save" to create the missing record. This is recorded in the Audit Log (event type `SIGN_TIME_ADDED`).

In and Out times are edited or added independently -- correcting or filling in one doesn't touch the other.

**Allowed times:** a sign-out has to be after its sign-in, and a time can't be moved past the person's previous or next sign-in/out. The form shows the allowed range under the date/time box, and a time outside it is rejected with a message. This stops a correction from accidentally splitting one visit into two rows.

### Deleting a Sign-In or Sign-Out

- **Delete a whole visit** -- click the red **Delete** button at the end of the row on the Logs page and confirm. This removes both the sign-in and sign-out for that visit.
- **Delete just one side** -- click **Edit** next to the In or Out time, then **Delete this sign-in** (or sign-out) and confirm.

This works the same for members and staff. Deletions can't be undone, and each one is recorded in the Audit Log (event type `SIGN_DELETED`) with the person, direction and time that was removed.

Staff visits are marked with a **STAFF** badge next to the name.

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

The Exports page provides downloads of sign-in data as Excel (.xlsx), PDF, or CSV -- pick whichever format suits how you'll use the file (Excel or CSV for spreadsheets, PDF for printing or emailing). There is no bulk "export every member" option -- use "Export a Person's Sign-ins" below to export one member (or all of them one at a time). Staff, however, can still be exported either in bulk or one at a time from a single card.

Member and staff exports share the exact same layout -- one worksheet per person, one row per sign-in/out session -- so they read identically regardless of which export you use; the only difference is the title text on the sheet.

### Staff Export

Nobody is restricted to one AM and one PM sign -- anyone can sign in and out any number of times, at any time of day -- so this export lists every sign-in/out session that actually happened rather than a fixed AM/PM grid.

1. Choose a staff member from the dropdown, or leave it on "All Staff" to export everyone.
2. Select a date range.
   - With "All Staff" selected, both dates are required.
   - With a specific staff member selected, the dates are optional -- leave both blank to export their entire sign-in history.
3. Choose a **Format** (Excel, PDF, or CSV).
4. Click "Download Staff Export".
5. An Excel file downloads (portrait orientation) with one worksheet (tab) per staff member -- so downloading "All Staff" gives you one tab per person to flip between, not one long combined sheet (a PDF download instead starts each person on a new page, and a CSV download lists everyone in one file separated by a "Total" row per person). Each person's sheet has:
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
3. Choose a **Format** (Excel, PDF, or CSV).
4. Click "Download Person Export".
5. The file uses the same layout described above for the staff export, regardless of whether the selected person is a member or staff.

## Alerts (Admin Only)

Alerts are messages that pop up when the people they apply to are being signed in or out, both on the kiosk and on the Sign In / Out page here. They are the same alerts as the kiosk Admin Panel's "Member / Run Alerts" section, so one created in either place shows up in both.

### Creating an Alert

1. Under **Applies To**, choose all members, a run sheet, or a single person, then pick the run sheet or person if asked.
2. Enter the **Message**.
3. Under **Stay Up For**, choose **No expiry**, or enter an amount of Hours, Days, Weeks, or Months.
4. Click **Create Alert**.

### Active Alerts

The table lists every alert that hasn't expired, with who it applies to, the message, when it was created, and when it expires. Click **Delete** to remove one early. If the run sheet or person an alert was for has since been deleted, it shows "(deleted run)" or "(deleted person)".

## Manage Dashboard Users (Admin Only)

This page lists everyone who can log into the dashboard and lets an admin create, edit, and delete logins.

### Creating a Login

1. Enter a name and a password. Passwords must be at least 10 characters long and include at least one number and one special character (e.g. `!`, `?`, `#`) -- the form will tell you if it doesn't meet these rules.
2. Choose "Staff (Sign In / Out only)" or "Admin (full access)".
3. If this login belongs to a staff member and you want them to be able to see their own timesheet, pick them from the **Linked staff member** dropdown. Leave it on "-- none --" if you don't want to link it (you can always come back and link it later from the Edit page).
4. Click "Create User". The name must be unique -- if it's already taken, you'll get an error asking you to pick another.

### Editing a Login

Click "Edit" next to a user to rename them, change their access level, change which staff member they're linked to, or set a new password.

- To change the password, type a new one in the password field (same rules as creating a login above). To leave the password unchanged, leave that field blank.
- You cannot change the last remaining admin account's access level down to Staff -- create a second admin first if you need to do that.

### Deleting a Login

Click "Delete" next to a user and confirm. You cannot delete the only remaining admin account -- create a second admin first if you need to remove one.

## Navigation

The dashboard has a consistent navigation bar at the top of every page. Whenever the links don't all fit on one line (phones, tablets, and smaller laptops) they collapse behind a menu icon (☰) in the top-right corner -- tap it to open the menu and again (or press Esc) to close it. On phones, tables such as the Logs and People lists show each row as its own card with labelled fields, so nothing needs side-scrolling. Links shown depend on your role:

- **Everyone:** Sign In / Out, Run Sheets, Logout
- **Anyone linked to a staff record:** My Timesheet (your own sign-in/out history)
- **Staff only:** Who's Here (today's counts and currently-signed-in list)
- **Admins only:** Dashboard (analytics), Logs (sign-in history), Audit (system events), People (member and staff management), Alerts (sign-in popups), Exports (data downloads), Dashboard Users (manage logins)
