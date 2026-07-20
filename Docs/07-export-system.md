# Export System

This document describes how the Excel export system works, the algorithms used to transform sign-in data into spreadsheet reports, and the libraries involved.

## Overview

The export system generates formatted Excel (.xlsx) files from sign-in records. It produces two types of reports:

1. **Member Export** -- A per-day summary of member sign-in/out times with embedded signature images, one worksheet per calendar day. Landscape.
2. **Staff Export** -- One row per actual sign-in/out session (staff aren't restricted to a fixed AM/PM pattern -- they can sign in and out any number of times, any time of day), with a duration per session and a running total per person. Portrait.

Either report can also be generated for a single person (see [Single-Person Export](#single-person-export) below), reusing the exact same layout functions.

The export logic lives in `kiosk_signin/export_util.py` and uses the `openpyxl` library for spreadsheet generation and `Pillow` (PIL) for rendering signature images.

## Member Export

### Data Flow

1. `database.get_signs_for_export(date_from, date_to)` retrieves all member sign events within the date range (staff are excluded by filtering on `person_type`).
2. `generate_export()` splits the events by calendar day (`timestamp[:10]`) and calls `_build_pupil_rows()` separately for each day.
3. `_build_pupil_rows(signs)` groups a **single day's** raw events by member and splits them into AM/PM sessions.
4. `_write_pupil_sheet()` builds one worksheet (headers, data rows, embedded signatures) per day.

### Grouping Algorithm (_build_pupil_rows)

The function uses a `defaultdict` to group sign events by member (keyed by `(member_id, first_name, last_name)`). For each member, it iterates through their events and assigns the first IN and first OUT event to either the AM or PM slot based on the hour (before 12:00 = AM, 12:00 onwards = PM):

```python
for e in events:
    hour = int(ts[11:13])
    is_am = hour < 12
    if is_am:
        if e["direction"] == "IN"  and am_in  is None: am_in  = e
        if e["direction"] == "OUT" and am_out is None: am_out = e
    else:
        if e["direction"] == "IN"  and pm_in  is None: pm_in  = e
        if e["direction"] == "OUT" and pm_out is None: pm_out = e
```

Only the first event per direction per half-day is recorded. This prevents duplicate entries if a sign event is accidentally recorded twice **on the same day**.

> **Important:** `_build_pupil_rows()` assumes its input is a single day's events. It is never called directly on a multi-day range — `generate_export()` is responsible for splitting the range by day first. An earlier version of `generate_export()` passed the whole multi-day range straight into `_build_pupil_rows()`, which silently kept only the very first IN/OUT it ever saw for each member and discarded every other day in the range (a member signed in 20 times over a month would show only 1 row). Splitting by day before grouping fixed this — see [Multi-Day Handling](#multi-day-handling).

### Multi-Day Handling

`generate_export(signs, date_from, date_to, output_path)` groups the incoming `signs` list by date:

```python
signs_by_date = defaultdict(list)
for s in signs:
    signs_by_date[s["timestamp"][:10]].append(s)
```

It then creates one worksheet per date present in the data (sheet title = the date, e.g. `2026-06-08`), calling `_write_pupil_sheet()` for each. This means:

- A single-day export (e.g. the kiosk's "Today" quick-select, or a same-day dashboard export) produces exactly one sheet, unchanged from before.
- A multi-day export (a week, a month, or a single person's full history) produces one sheet per day that has sign-in data, so every day's records are preserved instead of only the first day's.

Days with no sign-in data at all are skipped (no empty sheets are created), unlike the staff export's working-day grid.

### Spreadsheet Layout

Each day's worksheet has this structure:

```
Row 1:  Title bar (merged across all columns) -- shows that day's date
Row 2:  AM / PM group headers
Row 3:  Column headers (Name, Sign In, Signature, Sign Out, Signature x2)
Row 4+: One row per member who signed in that day, with data and embedded signatures
```

Alternating row fills (cream/white) improve readability. Each sheet is configured for A4 landscape printing with frozen panes at row 4.

## Staff Export

Staff sign-in/out has no restriction on time of day or on how many times a
person can sign in and out per day (see [Direction Validation](02-database-design.md#direction-validation)),
so the export can't rely on a fixed AM/PM grid the way the member export
does. Instead it lists every sign-in/out **session** that actually happened,
in the order it happened, how ever many there were on a given day.

### Data Flow

1. `database.get_staff_signs_for_export(date_from, date_to)` retrieves staff sign events.
2. `_build_staff_sessions(signs)` groups events by staff member and pairs them into sessions.
3. `generate_staff_export()` builds a portrait-oriented sheet with one section per staff member.

### Session Pairing Algorithm (`_build_staff_sessions`)

Events for each staff member are sorted chronologically, then walked through with a simple alternation state machine — the first `IN` opens a session, the next `OUT` closes it:

```python
for e in events:
    if e["direction"] == "IN":
        if open_in is not None:
            sessions.append({"date": open_in["timestamp"][:10], "in": open_in, "out": None})
        open_in = e
    else:  # OUT
        if open_in is not None:
            sessions.append({"date": open_in["timestamp"][:10], "in": open_in, "out": e})
            open_in = None
        else:
            sessions.append({"date": e["timestamp"][:10], "in": None, "out": e})
if open_in is not None:
    sessions.append({"date": open_in["timestamp"][:10], "in": open_in, "out": None})
```

This handles the edge cases that unrestricted sign-in/out opens up:

- **Normal session**: an `IN` followed by an `OUT` — both recorded, duration calculated.
- **Still signed in**: a session with no closing `OUT` yet (e.g. exporting today's data before someone has signed out, or a genuinely forgotten sign-out) — kept with `out: None` and shown as "Still signed in" in the sheet, with the duration cell left blank and excluded from the person's total.
- **Stray `OUT` with nothing open**: kept with `in: None` so the data isn't silently dropped.
- **A second `IN` while one is already open**: closes the previous session with no sign-out (defensive — shouldn't normally happen, since the kiosk auto-detects the next expected direction) and opens a new one.

The function returns a list of `(member_key, sessions)` tuples sorted by last name, where `member_key = (member_id, first_name, last_name, role)`.

### Duration Calculation

The `_duration_mins()` function calculates the time between two sign events in minutes (unchanged from before):

```python
def _duration_mins(start_event, finish_event):
    t1 = datetime.strptime(start_event["timestamp"], "%Y-%m-%d %H:%M:%S")
    t2 = datetime.strptime(finish_event["timestamp"], "%Y-%m-%d %H:%M:%S")
    mins = int((t2 - t1).total_seconds() / 60)
    return mins if mins >= 0 else None
```

Durations are formatted as "Xh YYm" (e.g. "3h 45m") by the `_fmt_duration()` helper. Each person's total ("Total time in the centre: Xh YYm") sums every session's duration across the whole exported date range — sessions with no duration (still open, or missing a sign-in/out) simply contribute nothing.

### Date and Year Formatting

Each row's date is shown as day/month only (`_day_month()`, e.g. "08/06") — the year isn't repeated on every row. Instead, `_year_label()` computes the year (or year range, e.g. "2026–2027", if the exported data spans a calendar year boundary) once per person and shows it in their name banner.

### Spreadsheet Layout

Each staff member gets their own section, with a page break before every section after the first so a new person always starts on a fresh printed page (a section can still spill onto extra pages by itself if it has a lot of sessions — that's expected, not an error):

```
Row N:    Name banner (merged, purple background) -- "Name — Role — Year"
Row N+1:  Column headers (Date, Sign In, Sign Out, Duration)
Row N+2+: One row per session, in chronological order:
            Date | Sign In time | Sign Out time (or "Still signed in") | Duration
          followed by a second row underneath -- only when at least one
          signature was captured for that session -- with the signature
          image(s) placed under the Sign In / Sign Out columns.
Row N+k:  "Total time in the centre: Xh YYm" (merged, bold)
```

If a staff member has no sign-in records at all in the exported range, their section shows "No sign-in records for this period." instead of a row list.

## Single-Person Export

Both the web dashboard and the kiosk admin panel can export just one person's sign-in/out records instead of the whole roster.

### Data Flow

1. `database.get_signs_for_member(member_id, date_from=None, date_to=None)` retrieves every sign event for one person. With no dates it returns their full history; with `date_from`/`date_to` it restricts to that range using the same `DATE(s.timestamp) >= ?` / `<= ?` filtering as the bulk export queries.
2. The caller checks the person's `person_type` and picks the matching layout function:
   - `person_type == "staff"` → `generate_staff_export()` (one row per session, as described above).
   - otherwise → `generate_export()` (per-day AM/PM sheets, as described above).
3. Because it reuses the same `generate_export()`/`generate_staff_export()` functions as the bulk exports, a single person's multi-day export gets the same one-sheet-per-day treatment — a month of records produces a month's worth of sheets, not one collapsed row.

### Entry Points

- **Dashboard:** `GET /export/person?person_id=<id>&date_from=<optional>&date_to=<optional>` (see `dashboard/app.py:export_person`). Date params are optional — omitting them exports the person's entire history. Reachable from the "Export" button on each row of the People list, the "Export Sign-in History" button on a person's edit page, and the "Export a Person's Sign-ins" card on the Exports page (which lets an admin pick a person and a date range from a form).
- **Kiosk admin panel:** the "Export" button next to "Edit" in the Member Management and Staff Management search results opens a small date-range dialog (`_ExportRangeDialog` in `kiosk_signin/screens/admin_screen.py`) with optional From/To fields, Today/7-day/30-day quick-select buttons, and an "All history" button that clears the range. Confirming calls `AdminPanelScreen._export_single_person()`, which now accepts optional `date_from`/`date_to` and passes them straight through to `database.get_signs_for_member()`. Leaving both fields blank preserves the original full-history behaviour; the saved filename gains a `_<date_from>_to_<date_to>` suffix whenever a range is given. The file still saves to the user's home directory, same as the bulk kiosk exports.

## Signature Rendering

Signatures are stored in the database as serialised Python lists of stroke coordinates `[(x1, y1, x2, y2), ...]`. The `render_signature()` function (public — it's reused outside this module, see [Last Signature Display](#last-signature-display) below) converts these into PNG images:

1. Deserialise the byte string back into a list using `ast.literal_eval()`.
2. Calculate the bounding box of all stroke coordinates.
3. Scale the strokes to fit within a target image size (160x60 pixels) with margins.
4. Create a white PIL `Image` and draw each stroke as a line.
5. Save the image to a `BytesIO` buffer as PNG.
6. Return the PNG bytes for embedding in the spreadsheet.

```python
img = Image.new("RGB", (width, height), "white")
draw = ImageDraw.Draw(img)
for (x1, y1, x2, y2) in strokes:
    draw.line([(tx(x1), ty(y1)), (tx(x2), ty(y2))], fill="black", width=2)
```

The scaling uses `min()` to maintain the signature's aspect ratio:

```python
scale = min((width - margin * 2) / range_x, (height - margin * 2) / range_y)
```

The rendered PNGs are embedded into Excel cells using `openpyxl.drawing.image.Image`.

## Last Signature Display

Outside of exports, both the kiosk and the dashboard can show a member or staff person's most recently used signature without generating a full spreadsheet:

- `database.get_last_signature(member_id)` returns the most recent `sign_ins` row for that person that has a **non-null, non-empty** signature — it deliberately skips rows with no signature (e.g. records from before signatures were made mandatory), unlike `get_last_sign()` which returns the most recent row regardless of whether it has a signature.
- Like the rest of the "current state" functions in `database.py` (`get_last_sign`, `get_today_last_sign`, `get_allowed_direction`), this is computed live from `sign_ins` on every call — there is no separate stored/cached "current signature" column anywhere in the schema.
- **Kiosk:** `ProfileScreen` and `StaffProfileScreen` each have a "Last Signature on File" section, populated in `_populate_signature()`, which renders the signature via `export_util.render_signature()` and displays it as an image with a "Last used: `<timestamp>` (`<direction>`)" caption. If the person has no sign-in history, or none of their sign-ins have a captured signature, a "No signature on file yet." placeholder is shown instead.
- **Dashboard:** the person edit page (`dashboard/templates/person_form.html`) shows the same signature as an `<img>` tag pointing at `GET /people/<id>/signature.png` (`dashboard/app.py:person_signature`), a `@login_required` route that streams the rendered PNG or returns a 404 with an empty body if there's nothing to show. The `<img>` tag's `onerror` handler swaps in "No signature on file yet." text client-side when the route 404s.

## Output Handling

Both export functions accept an `output_path` parameter that can be either a file path string (used by the kiosk's admin panel) or a file-like object (used by the dashboard's in-memory export). This is possible because `openpyxl`'s `Workbook.save()` method accepts both.

## Print Setup

Both exports configure the spreadsheet for A4 printing, fit to page width (one page wide, unlimited height), with the same custom page margins (0.4 inch left/right, 0.6 inch top/bottom) -- but different orientations:

- **Member export**: landscape (nine columns across AM/PM sessions need the extra width).
- **Staff export**: portrait, per the requirement that a staff sheet needs to fit on a normal portrait page and only spill onto extra pages when there's genuinely more than a page's worth of sessions.
