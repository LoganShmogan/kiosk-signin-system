# Kiosk User Guide

This document explains how to use the touchscreen kiosk application from the perspective of a caregiver, staff member, or administrator.

## Starting the Application

Run the kiosk with:

```
python kiosk_signin/app.py
```

The application opens maximised on the Windows kiosk (or in a fixed 1280x720 window on Linux, used for development). The web dashboard also starts automatically on port 5000.

Press `Ctrl+Q` at any time to close the application.

## Tap Screen (Home)

The first screen displayed is the Tap Screen. It shows the organisation logo (or a text placeholder) and the text "Tap to start". Tap anywhere on the screen to proceed to the Options Menu.

An "Admin" button in the top-right corner provides direct access to the admin password screen.

## Options Menu

The Options Menu is the main navigation hub. It presents buttons for each section of the system:

- **Sign In / Sign Out** -- Search for members and sign them in or out.
- **Run Sheets** -- Load a predefined run sheet to sign in a group of members at once.
- **Social Media & Contacts** -- View the organisation's social media links and contact details.

An "Admin" button in the top-right corner opens the admin panel (password required). The "Back" button returns to the Tap Screen.

## Signing In and Out

### Step 1: Select Members

The Sign In screen is split into two panels:

- **Left panel**: A search bar and a dropdown list of everyone in the system -- both members and staff. Type a name to filter the list. Tap a name to add them to the selection. The search matches against first name, last name, or full name. After adding someone, the search text clears automatically and the on-screen keyboard (Windows kiosk) stays open, ready for the next name.
- **Right panel**: The "Selected Pupils" list. Members appear here sorted alphabetically. Tap the red X button next to a name to remove them.

You can select multiple members for a batch sign-in/out.

Tap "Enter" to proceed to the signature screen, or "Back" to return to the Options Menu.

### Step 2: Sign and Confirm

The Signature Screen shows:

- **Left side**:
  - The list of members being signed.
  - The current date and time (auto-stamped).
  - A notes field. For single-member sign-ins, this is pre-filled with the member's activity details if they have one on file.

- **Right side**:
  - **IN / OUT buttons**: Select the sign direction. The system auto-detects the correct direction based on the member's last sign event today. If the member is currently signed in, it defaults to OUT. If not signed in, it defaults to IN.
  - **Signature pad**: Draw a signature with your finger or mouse. Use "Clear signature" to reset.

Tap "DONE" to submit. A signature is optional: if the pad is left empty, the sign event is still recorded, just without a signature image. The system will:

1. Check each selected member's allowed direction for today.
2. Record the sign event for eligible members.
3. Send email notifications to caregivers (if configured).
4. Show a confirmation popup with the result.

If a member cannot sign in the selected direction (e.g. they are already signed in and you chose IN), they are skipped and the popup explains why.

### Direction Rules

Members and staff alike can sign in and out as many times as they like, whenever they like -- there's no time-of-day restriction and no daily limit. The only rule is simple alternation, based on that person's last sign event today:

1. No sign yet today (or their last sign today was **OUT**): they're expected to sign **IN**
2. Their last sign today was **IN**: they're expected to sign **OUT**

The IN/OUT buttons on the Signature Screen auto-select the expected direction, so this is normally invisible. If you pick the wrong direction for someone (e.g. they're already signed in and you select IN), they're skipped and the confirmation popup explains why -- everyone else in the batch is still signed as expected.

## Run Sheets

Run Sheets allow batch sign-in for predefined groups (e.g. a school bus pickup). The screen works similarly to the Sign In screen but starts by selecting a run sheet rather than individual members.

### Using a Run Sheet

1. Search for a run sheet by name in the left panel.
2. Tap a run sheet to load **all** of its members into the right panel, regardless of whether they're currently signed in or out -- a run sheet is used both for signing a group IN (e.g. a morning bus arrival) and for signing a group OUT (e.g. an afternoon bus departure), so nobody is pre-filtered out.
3. Use the "Add another" button to temporarily add extra members who are not on the run sheet.
4. Tap "Enter" to proceed to the signature screen, which auto-detects IN or OUT the same way it does for a direct sign-in (based on the first selected member's last sign event today) and skips anyone not eligible for that direction, same as described under [Direction Rules](#direction-rules) above.

Run sheets are created and managed through the Admin Panel.

## Social Media & Contacts

This screen displays the organisation's social media links (Facebook page, website) and contact information (phone number, email address). It is a static information display intended for caregivers at the kiosk.

## Admin Panel

### Accessing the Admin Panel

Tap "Admin" from the Tap Screen or Options Menu. Enter the admin password (default: `admin1234`) and tap "Enter".

### Today's Sign-in Log

At the top of the Admin Panel, a table shows all sign-in and sign-out events recorded today. Each row displays the member's name, direction (IN/OUT), time, and notes. Tap "Refresh" to reload.

### Export Member Sign-in Data

Export all member sign-in records to an Excel (.xlsx) file for a given date range. Quick-select buttons are provided for "Today", "Last 7 days", and "Last 30 days". Enter custom dates in YYYY-MM-DD format.

Members aren't restricted to one AM and one PM sign -- they can sign in and out any number of times, at any time of day -- so the export lists every sign-in/out session that actually happened. Each member gets their own worksheet (tab) in the workbook:

- A name/year banner at the top of their sheet
- One row per session: date (day/month), sign-in time, sign-out time (or "Still signed in" if they haven't signed out yet), and the duration
- A signature image row underneath a session's row, when a signature was captured for it
- A "Total time in the centre" line at the end of their sheet, summing every session in the exported range

The file is saved to the user's home directory.

### Export Staff Sign-in Data

Export all staff sign-in records to an Excel (.xlsx) file for a given date range. Quick-select buttons are provided for "Last 14 days" and "Last 30 days".

This uses the exact same layout as the member export above (one worksheet per staff member, one row per sign-in/out session, with a role added to the name banner) -- the two exports are identical apart from the title text on each sheet.

The file is saved to the user's home directory, same as the member export.

### Change Admin Password

Enter a new password (minimum 6 characters) and confirm it. The password is stored as a salted hash in the database, never as plain text. See [09-authentication-and-security.md](09-authentication-and-security.md).

### Member Management

Search for existing members and tap "Edit" to open their profile. Tap "+ Add New Member" to create a new member record. Each result row also has an "Export" button that opens a small dialog asking for an optional date range (with Today/7-day/30-day quick-select buttons, or "All history" to clear the range) before downloading that member's sign-in/out history to an Excel file in the user's home directory (same one-sheet layout as the bulk Member export above). Leaving both dates blank exports their complete history, as before.

The Profile Screen shows all member details in a scrollable two-column form:

**Left column (Child Details):**
- First name, last name, date of birth, school
- PIN (optional; stored on the profile, but not currently asked for when signing in)
- Attendance days (mornings and afternoons)
- Pickup requirements
- Activity details and transport

**Right column (Caregiver Details):**
- Caregiver name, phone, email
- Email notification preferences (None / IN only / OUT only / Both)
- Address (street, suburb, city)
- Emergency contact details
- **Last Signature on File** — shows the image of the signature this member most recently used to sign in or out, with the date/time and direction. Shows "No signature on file yet." if they haven't signed in yet, or none of their recorded sign-ins captured a signature.

Tap "Save" or "Save Profile" to persist changes. Tap "Delete" to permanently remove the member and all associated records (cascading delete).

### Staff Management

Same as member management but with a simplified form. Staff profiles only have: first name, last name, role/position, PIN, and the same "Last Signature on File" panel described above. The "Export" button on each row opens the same optional date-range dialog before exporting that staff member's sign-in history, same per-session layout as the bulk Staff export.

### Run Sheet Management

View existing run sheets, create new ones, or edit existing ones.

To create a run sheet:
1. Enter a name in the "Run Sheet Name" field.
2. Search for and add pupils to the sheet.
3. Tap "Save Run Sheet".

To edit a run sheet, tap "Edit" next to its name. The editor will populate with the sheet's current name and assigned pupils.

To delete a run sheet, tap "Delete" and confirm. Deleting a run sheet does not delete the pupils themselves.

### Member / Run Alerts

Alerts are short messages that pop up on the Sign In screen when the people they apply to are being signed in or out (for example, "Mum is collecting today" or "Bring hat for trip").

To create an alert:
1. Under **Applies To**, choose **All Members**, **A Run** (then pick the run sheet), or **Single Person** (then search for and tap the person).
2. Type the **Message**.
3. Under **Stay Up For**, choose how long it stays active: a number of Hours, Days, Weeks, or Months, or **No expiry**.
4. Tap **Create Alert**.

Active alerts are listed underneath under **Active Alerts**, showing who each applies to, the message, and when it expires, with a **Delete Alert** button. Expired alerts stop appearing automatically. Alerts created here also appear on the web dashboard's Sign In / Out page, and can be managed from the dashboard's Alerts page too.

