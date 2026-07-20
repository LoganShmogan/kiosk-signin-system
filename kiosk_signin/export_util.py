import ast
import io
import os
from collections import defaultdict
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.pagebreak import Break

try:
    from PIL import Image, ImageDraw
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


def render_signature(sig_bytes: bytes, width=160, height=60) -> bytes | None:
    """Convert stroke data (stored as a serialised list) into a PNG byte string."""
    if not sig_bytes or not PIL_AVAILABLE:
        return None
    try:
        strokes = ast.literal_eval(sig_bytes.decode())
    except Exception:
        return None
    if not strokes:
        return None

    xs = [c for s in strokes for c in (s[0], s[2])]
    ys = [c for s in strokes for c in (s[1], s[3])]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    range_x = max(max_x - min_x, 1)
    range_y = max(max_y - min_y, 1)

    margin  = 6
    scale   = min((width - margin * 2) / range_x, (height - margin * 2) / range_y)

    def tx(x): return int((x - min_x) * scale) + margin
    def ty(y): return int((y - min_y) * scale) + margin

    img  = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    for (x1, y1, x2, y2) in strokes:
        draw.line([(tx(x1), ty(y1)), (tx(x2), ty(y2))], fill="black", width=2)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _build_pupil_rows(signs: list) -> list:
    """
    Group raw sign events by pupil and produce one summary row per pupil:
      name, am_in, am_in_sig, am_out, am_out_sig,
             pm_in, pm_in_sig, pm_out, pm_out_sig

    AM = before 12:00, PM = 12:00 onwards.
    Only the first IN and first OUT per half-day are recorded.
    """
    from collections import defaultdict

    by_member = defaultdict(list)
    for s in signs:
        by_member[(s["member_id"], s["first_name"], s["last_name"])].append(s)

    rows = []
    for (mid, fname, lname), events in by_member.items():
        am_in = am_out = pm_in = pm_out = None

        for e in events:
            ts = e["timestamp"]
            try:
                hour = int(ts[11:13])
            except Exception:
                hour = 0
            is_am = hour < 12

            if is_am:
                if e["direction"] == "IN"  and am_in  is None: am_in  = e
                if e["direction"] == "OUT" and am_out is None: am_out = e
            else:
                if e["direction"] == "IN"  and pm_in  is None: pm_in  = e
                if e["direction"] == "OUT" and pm_out is None: pm_out = e

        rows.append({
            "name":       f"{fname} {lname}",
            "am_in":      am_in ["timestamp"][11:16] if am_in  else "",
            "am_in_sig":  am_in ["signature"]        if am_in  else None,
            "am_out":     am_out["timestamp"][11:16] if am_out else "",
            "am_out_sig": am_out["signature"]        if am_out else None,
            "pm_in":      pm_in ["timestamp"][11:16] if pm_in  else "",
            "pm_in_sig":  pm_in ["signature"]        if pm_in  else None,
            "pm_out":     pm_out["timestamp"][11:16] if pm_out else "",
            "pm_out_sig": pm_out["signature"]        if pm_out else None,
        })

    rows.sort(key=lambda r: r["name"].lower())
    return rows


HEADERS = [
    "Name",
    "Sign In", "Signature",
    "Sign Out", "Signature",
    "Sign In", "Signature",
    "Sign Out", "Signature",
]
COL_WIDTHS = [16, 7, 18, 7, 18, 7, 18, 7, 18]
ROW_HEIGHT  = 45

HEADER_FILL = PatternFill("solid", start_color="372976")
HEADER_FONT = Font(name="Arial", bold=True, color="FFFFFF", size=11)
DATA_FONT   = Font(name="Arial", size=11)
ALT_FILL    = PatternFill("solid", start_color="F0EDE8")
THIN        = Side(style="thin", color="D0CBE8")
BORDER      = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
CENTER      = Alignment(horizontal="center", vertical="center", wrap_text=True)
LEFT        = Alignment(horizontal="left",   vertical="center", wrap_text=True)


def _write_pupil_sheet(ws, day_signs: list, sheet_label: str) -> None:
    """Populate one worksheet with a single day's pupil sign-in/out rows."""
    rows = _build_pupil_rows(day_signs)

    ws.merge_cells("A1:I1")
    ws["A1"] = f"Kiosk Sign-In Export  |  {sheet_label}"
    ws["A1"].font      = Font(name="Arial", bold=True, size=13, color="372976")
    ws["A1"].alignment = CENTER
    ws.row_dimensions[1].height = 28

    ws.merge_cells("B2:E2")
    ws["B2"] = "AM"
    ws.merge_cells("F2:I2")
    ws["F2"] = "PM"
    for cell in (ws["B2"], ws["F2"]):
        cell.font      = Font(name="Arial", bold=True, size=11, color="FFFFFF")
        cell.fill      = PatternFill("solid", start_color="4a3a8a")
        cell.alignment = CENTER
    ws.row_dimensions[2].height = 20

    for col_idx, (hdr, width) in enumerate(zip(HEADERS, COL_WIDTHS), start=1):
        cell = ws.cell(row=3, column=col_idx, value=hdr)
        cell.font      = HEADER_FONT
        cell.fill      = HEADER_FILL
        cell.alignment = CENTER
        cell.border    = BORDER
        ws.column_dimensions[get_column_letter(col_idx)].width = width
    ws.row_dimensions[3].height = 20

    for r_idx, row in enumerate(rows, start=4):
        fill = ALT_FILL if r_idx % 2 == 0 else None
        ws.row_dimensions[r_idx].height = ROW_HEIGHT

        values = [
            row["name"],
            row["am_in"],  None,
            row["am_out"], None,
            row["pm_in"],  None,
            row["pm_out"], None,
        ]
        sig_cols = {3: row["am_in_sig"], 5: row["am_out_sig"],
                    7: row["pm_in_sig"], 9: row["pm_out_sig"]}

        for col_idx, val in enumerate(values, start=1):
            cell = ws.cell(row=r_idx, column=col_idx,
                           value=val if val is not None else "")
            cell.font      = DATA_FONT
            cell.alignment = CENTER if col_idx > 1 else LEFT
            cell.border    = BORDER
            if fill:
                cell.fill = fill

        for col_idx, sig_bytes in sig_cols.items():
            png = render_signature(sig_bytes) if sig_bytes else None
            if png:
                from openpyxl.drawing.image import Image as XLImage
                img_obj = XLImage(io.BytesIO(png))
                img_obj.width  = 120
                img_obj.height = 38
                ws.add_image(img_obj, f"{get_column_letter(col_idx)}{r_idx}")
            else:
                cell = ws.cell(row=r_idx, column=col_idx,
                               value="No sig" if sig_bytes is None else "—")
                cell.font      = Font(name="Arial", size=9, color="999999", italic=True)
                cell.alignment = CENTER
                cell.border    = BORDER
                if fill:
                    cell.fill = fill

    ws.freeze_panes = "A4"

    from openpyxl.worksheet.page import PageMargins
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize   = 9          # A4
    ws.page_setup.fitToPage   = True
    ws.page_setup.fitToWidth  = 1
    ws.page_setup.fitToHeight = 0
    ws.page_margins = PageMargins(left=0.4, right=0.4, top=0.6, bottom=0.6)


def generate_export(signs: list, date_from: str, date_to: str, output_path) -> str:
    """Build the .xlsx file and write it to output_path (file path or file-like object).

    One worksheet is created per calendar day found in `signs`, each holding that
    day's pupils and their AM/PM sign-in/out times. Grouping every day's events
    into a single sheet used to keep only the very first IN/OUT ever seen per
    pupil across the whole range — splitting by day means every day's sign-ins
    and sign-outs are kept, not just the first day's.
    """
    signs_by_date = defaultdict(list)
    for s in signs:
        signs_by_date[s["timestamp"][:10]].append(s)

    wb = Workbook()
    wb.remove(wb.active)

    dates = sorted(signs_by_date.keys()) or [date_from or date_to or "Sign-in Export"]
    for day in dates:
        ws = wb.create_sheet(title=day[:31])
        _write_pupil_sheet(ws, signs_by_date.get(day, []), day)

    wb.save(output_path)
    return output_path


# ── Staff export ───────────────────────────────────────────────────────────────
# Staff sign in/out with no restriction on time of day or count — so each row
# is one sign-in/out session (not a fixed AM/PM slot), in the order it happened.

STAFF_HEADERS    = ["Date", "Sign In", "Sign Out", "Duration"]
STAFF_COL_WIDTHS = [10, 14, 18, 12]

STAFF_NAME_FILL   = PatternFill("solid", start_color="372976")
STAFF_NAME_FONT   = Font(name="Arial", bold=True, size=12, color="FFFFFF")
STAFF_SUBHDR_FILL = PatternFill("solid", start_color="4a3a8a")
STAFF_SUBHDR_FONT = Font(name="Arial", bold=True, size=10, color="FFFFFF")
TOTAL_FONT        = Font(name="Arial", bold=True, size=11)
STILL_IN_FONT     = Font(name="Arial", size=11, italic=True, color="BB2233")

SIG_ROW_HEIGHT = 34


def _duration_mins(start_event, finish_event):
    """Minutes between two sign events, or None if either is missing."""
    if not start_event or not finish_event:
        return None
    try:
        t1 = datetime.strptime(start_event["timestamp"], "%Y-%m-%d %H:%M:%S")
        t2 = datetime.strptime(finish_event["timestamp"], "%Y-%m-%d %H:%M:%S")
        mins = int((t2 - t1).total_seconds() / 60)
        return mins if mins >= 0 else None
    except Exception:
        return None


def _fmt_duration(mins) -> str:
    """Format minutes as 'Xh YYm', or '' if None."""
    if mins is None:
        return ""
    return f"{mins // 60}h {mins % 60:02d}m"


def _day_month(date_str: str) -> str:
    """'YYYY-MM-DD' -> 'DD/MM' (no year — the year is shown once, per person)."""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%d/%m")
    except Exception:
        return date_str


def _year_label(sessions: list) -> str:
    """Single year ('2026') or a range ('2026–2027') covering all sessions."""
    years = sorted({s["date"][:4] for s in sessions if s.get("date")})
    if not years:
        return ""
    return years[0] if len(years) == 1 else f"{years[0]}–{years[-1]}"


def _build_staff_sessions(signs: list) -> list:
    """
    Groups raw sign events by staff member and pairs them into sessions.

    Returns a list of (member_key, sessions) tuples sorted by last name, where
    member_key = (member_id, first_name, last_name, role) and sessions is a
    chronologically ordered list of dicts:
        {"date": "YYYY-MM-DD", "in": event_or_None, "out": event_or_None}

    Sign-ins/outs aren't restricted to a time of day or a fixed count per day,
    so sessions are built by simple alternation: the first IN opens a session
    and the next OUT closes it. A stray IN while one is already open closes
    the previous session with no sign-out; a stray OUT with nothing open opens
    a session with no sign-in. A session still open at the end of the data
    (signed in, not yet signed out) is included with out=None.
    """
    by_member: dict = {}
    order: list = []
    for s in signs:
        key = (s["member_id"], s["first_name"], s["last_name"], s.get("role") or "")
        if key not in by_member:
            by_member[key] = []
            order.append(key)
        by_member[key].append(s)

    result = []
    for key in order:
        events = sorted(by_member[key], key=lambda e: e["timestamp"])
        sessions = []
        open_in = None
        for e in events:
            if e["direction"] == "IN":
                if open_in is not None:
                    sessions.append({"date": open_in["timestamp"][:10],
                                      "in": open_in, "out": None})
                open_in = e
            else:  # OUT
                if open_in is not None:
                    sessions.append({"date": open_in["timestamp"][:10],
                                      "in": open_in, "out": e})
                    open_in = None
                else:
                    sessions.append({"date": e["timestamp"][:10],
                                      "in": None, "out": e})
        if open_in is not None:
            sessions.append({"date": open_in["timestamp"][:10], "in": open_in, "out": None})
        result.append((key, sessions))

    result.sort(key=lambda x: (x[0][2].lower(), x[0][1].lower()))
    return result


def generate_staff_export(signs: list, date_from: str, date_to: str, output_path) -> str:
    """Build the staff sign-in/out .xlsx. output_path can be a file path or file-like object.

    Portrait layout: one row per sign-in/out session (Date | Sign In | Sign Out |
    Duration), with a second row underneath for signature images when present.
    Each person gets their own section (name, role and year up top, a total
    time-in-centre line at the bottom) and starts on a fresh printed page.
    """
    staff_sessions = _build_staff_sessions(signs)

    wb = Workbook()
    ws = wb.active
    ws.title = "Staff Sign-in Export"

    for col_idx, width in enumerate(STAFF_COL_WIDTHS, start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    last_col = get_column_letter(len(STAFF_HEADERS))

    # ── Title ──────────────────────────────────────────────────────────────────
    ws.merge_cells(f"A1:{last_col}1")
    ws["A1"]           = f"Staff Sign-in Export  |  {date_from}  to  {date_to}"
    ws["A1"].font      = Font(name="Arial", bold=True, size=13, color="372976")
    ws["A1"].alignment = CENTER
    ws.row_dimensions[1].height = 28

    current_row = 2

    for person_idx, ((mid, fname, lname, role), sessions) in enumerate(staff_sessions):

        if person_idx > 0:
            ws.row_breaks.append(Break(id=current_row - 1))

        current_row += 1   # blank spacer

        # ── Person name banner ─────────────────────────────────────────────────
        name = f"{fname} {lname}"
        parts = [name]
        if role:
            parts.append(role)
        year_label = _year_label(sessions)
        if year_label:
            parts.append(year_label)
        banner_text = "  —  ".join(parts)
        ws.merge_cells(f"A{current_row}:{last_col}{current_row}")
        c           = ws[f"A{current_row}"]
        c.value     = banner_text
        c.font      = STAFF_NAME_FONT
        c.fill      = STAFF_NAME_FILL
        c.alignment = LEFT
        ws.row_dimensions[current_row].height = 26
        current_row += 1

        # ── Column headers ─────────────────────────────────────────────────────
        for col_idx, hdr in enumerate(STAFF_HEADERS, start=1):
            cell           = ws.cell(row=current_row, column=col_idx, value=hdr)
            cell.font      = STAFF_SUBHDR_FONT
            cell.fill      = STAFF_SUBHDR_FILL
            cell.alignment = CENTER
            cell.border    = BORDER
        ws.row_dimensions[current_row].height = 20
        current_row += 1

        # ── One (or two) rows per session ───────────────────────────────────────
        total_mins = 0
        if not sessions:
            ws.merge_cells(f"A{current_row}:{last_col}{current_row}")
            mc           = ws[f"A{current_row}"]
            mc.value     = "No sign-in records for this period."
            mc.font      = Font(name="Arial", size=10, italic=True, color="999999")
            mc.alignment = CENTER
            current_row += 1
        else:
            for s_idx, sess in enumerate(sessions):
                in_evt, out_evt = sess["in"], sess["out"]
                mins = _duration_mins(in_evt, out_evt)
                if mins is not None:
                    total_mins += mins

                row_fill = ALT_FILL if s_idx % 2 == 0 else None
                ws.row_dimensions[current_row].height = ROW_HEIGHT

                in_text  = in_evt["timestamp"][11:16] if in_evt else ""
                if out_evt is not None:
                    out_text, out_font = out_evt["timestamp"][11:16], DATA_FONT
                else:
                    out_text, out_font = "Still signed in", STILL_IN_FONT

                values = [
                    (_day_month(sess["date"]), DATA_FONT, LEFT),
                    (in_text,                  DATA_FONT, CENTER),
                    (out_text,                 out_font,  CENTER),
                    (_fmt_duration(mins),      TOTAL_FONT, CENTER),
                ]
                for col_idx, (val, font, align) in enumerate(values, start=1):
                    cell           = ws.cell(row=current_row, column=col_idx, value=val)
                    cell.font      = font
                    cell.alignment = align
                    cell.border    = BORDER
                    if row_fill:
                        cell.fill = row_fill
                current_row += 1

                in_sig  = in_evt["signature"]  if in_evt  else None
                out_sig = out_evt["signature"] if out_evt else None
                if in_sig or out_sig:
                    ws.row_dimensions[current_row].height = SIG_ROW_HEIGHT
                    for col_idx in range(1, len(STAFF_HEADERS) + 1):
                        cell        = ws.cell(row=current_row, column=col_idx, value="")
                        cell.border = BORDER
                        if row_fill:
                            cell.fill = row_fill
                    for col_idx, sig_bytes in ((2, in_sig), (3, out_sig)):
                        png = render_signature(sig_bytes) if sig_bytes else None
                        if png:
                            from openpyxl.drawing.image import Image as XLImage
                            img_obj        = XLImage(io.BytesIO(png))
                            img_obj.width  = 100
                            img_obj.height = 32
                            ws.add_image(img_obj, f"{get_column_letter(col_idx)}{current_row}")
                    current_row += 1

        # ── Total time in the centre ─────────────────────────────────────────────
        ws.merge_cells(f"A{current_row}:{last_col}{current_row}")
        tc           = ws[f"A{current_row}"]
        tc.value     = f"Total time in the centre: {_fmt_duration(total_mins)}"
        tc.font      = TOTAL_FONT
        tc.fill      = ALT_FILL
        tc.alignment = LEFT
        ws.row_dimensions[current_row].height = 22
        current_row += 1

    from openpyxl.worksheet.page import PageMargins
    ws.page_setup.orientation = "portrait"
    ws.page_setup.paperSize   = 9
    ws.page_setup.fitToPage   = True
    ws.page_setup.fitToWidth  = 1
    ws.page_setup.fitToHeight = 0
    ws.page_margins = PageMargins(left=0.4, right=0.4, top=0.6, bottom=0.6)

    wb.save(output_path)
    return output_path
