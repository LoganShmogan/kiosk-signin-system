import io
import os
import sys
import sqlite3
import json
from datetime import date, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash

if getattr(sys, "frozen", False):
    _base_dir = os.path.dirname(sys.executable)
    _template_dir = os.path.join(sys._MEIPASS, "dashboard", "templates")
    _static_dir = os.path.join(sys._MEIPASS, "dashboard", "static")
    app = Flask(__name__, template_folder=_template_dir, static_folder=_static_dir)
else:
    app = Flask(__name__)

app.secret_key = "kiosk-dashboard-secret-key"

if getattr(sys, "frozen", False):
    _data_dir = os.path.join(
        os.environ.get("LOCALAPPDATA", os.path.dirname(sys.executable)),
        "Kiosk Sign-In",
    ) if sys.platform == "win32" else os.path.dirname(sys.executable)
    DB_PATH = os.path.join(_data_dir, "signin_data.db")
else:
    DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "kiosk_signin", "signin_data.db")

if getattr(sys, "frozen", False):
    sys.path.insert(0, os.path.join(sys._MEIPASS, "kiosk_signin"))
else:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "kiosk_signin"))

DASHBOARD_USER = "admin"
DASHBOARD_PASS = "1234"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def log_event(event_type: str, description: str):
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO audit_log (event_type, description) VALUES (?, ?)",
                (event_type, description),
            )
    except Exception:
        pass


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


@app.route("/")
def index():
    if session.get("logged_in"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        if username == DASHBOARD_USER and password == DASHBOARD_PASS:
            session["logged_in"] = True
            log_event("DASHBOARD_LOGIN", "Admin logged into the web dashboard")
            return redirect(url_for("dashboard"))
        error = "Invalid username or password."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    log_event("DASHBOARD_LOGOUT", "Admin logged out of the web dashboard")
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    today = date.today().isoformat()
    week_start = (date.today() - timedelta(days=date.today().weekday())).isoformat()

    with get_conn() as conn:
        today_ins = conn.execute("""
            SELECT COUNT(DISTINCT member_id) as c FROM sign_ins
            WHERE DATE(timestamp) = ? AND direction = 'IN'
        """, (today,)).fetchone()["c"]

        currently_in = conn.execute("""
            SELECT COUNT(*) as c FROM (
                SELECT s.member_id FROM sign_ins s
                WHERE DATE(s.timestamp) = ?
                AND s.direction = 'IN'
                AND s.id = (
                    SELECT MAX(id) FROM sign_ins s2
                    WHERE s2.member_id = s.member_id
                    AND DATE(s2.timestamp) = ?
                )
            )
        """, (today, today)).fetchone()["c"]

        total_members = conn.execute("SELECT COUNT(*) as c FROM members").fetchone()["c"]

        week_ins = conn.execute("""
            SELECT COUNT(DISTINCT member_id) as c FROM sign_ins
            WHERE DATE(timestamp) >= ? AND direction = 'IN'
        """, (week_start,)).fetchone()["c"]

        # Daily totals — last 30 days
        daily_rows = conn.execute("""
            SELECT DATE(timestamp) as day, COUNT(*) as total
            FROM sign_ins
            WHERE DATE(timestamp) >= DATE('now', '-30 days')
            GROUP BY day ORDER BY day
        """).fetchall()
        daily_map = {r["day"]: r["total"] for r in daily_rows}
        daily_labels = []
        daily_values = []
        for i in range(30, -1, -1):
            d = (date.today() - timedelta(days=i)).isoformat()
            daily_labels.append(d[5:])  # MM-DD
            daily_values.append(daily_map.get(d, 0))

        # Peak hours (all time)
        hour_rows = conn.execute("""
            SELECT CAST(strftime('%H', timestamp) AS INTEGER) as hour, COUNT(*) as total
            FROM sign_ins GROUP BY hour ORDER BY hour
        """).fetchall()
        hour_map = {r["hour"]: r["total"] for r in hour_rows}
        hour_labels = [f"{h:02d}:00" for h in range(24)]
        hour_values = [hour_map.get(h, 0) for h in range(24)]

        # Weekly totals — last 12 weeks
        weekly_rows = conn.execute("""
            SELECT strftime('%Y-W%W', timestamp) as week, COUNT(*) as total
            FROM sign_ins
            WHERE DATE(timestamp) >= DATE('now', '-84 days')
            GROUP BY week ORDER BY week
        """).fetchall()
        weekly_labels = [r["week"] for r in weekly_rows]
        weekly_values = [r["total"] for r in weekly_rows]

        # Monthly totals — last 12 months
        monthly_rows = conn.execute("""
            SELECT strftime('%Y-%m', timestamp) as month, COUNT(*) as total
            FROM sign_ins
            WHERE DATE(timestamp) >= DATE('now', '-365 days')
            GROUP BY month ORDER BY month
        """).fetchall()
        monthly_labels = [r["month"] for r in monthly_rows]
        monthly_values = [r["total"] for r in monthly_rows]

        # Who is currently signed in
        signed_in_list = conn.execute("""
            SELECT m.first_name, m.last_name, s.timestamp
            FROM members m
            JOIN sign_ins s ON s.member_id = m.id
            WHERE DATE(s.timestamp) = ?
            AND s.direction = 'IN'
            AND s.id = (
                SELECT MAX(id) FROM sign_ins s2
                WHERE s2.member_id = m.id AND DATE(s2.timestamp) = ?
            )
            ORDER BY m.last_name, m.first_name
        """, (today, today)).fetchall()
        signed_in_list = [dict(r) for r in signed_in_list]

    return render_template(
        "dashboard.html",
        today=today,
        today_ins=today_ins,
        currently_in=currently_in,
        total_members=total_members,
        week_ins=week_ins,
        daily_labels=json.dumps(daily_labels),
        daily_values=json.dumps(daily_values),
        hour_labels=json.dumps(hour_labels),
        hour_values=json.dumps(hour_values),
        weekly_labels=json.dumps(weekly_labels),
        weekly_values=json.dumps(weekly_values),
        monthly_labels=json.dumps(monthly_labels),
        monthly_values=json.dumps(monthly_values),
        signed_in_list=signed_in_list,
    )


def _pair_sign_in_visits(rows):
    """Collapse a chronological list of IN/OUT sign_ins rows (ordered by
    member_id, then timestamp) into one visit per row: an IN paired with
    the OUT that follows it for the same member. An IN with no later OUT
    is a visit that's still open (the person is currently signed in); an
    OUT with no preceding IN is kept as its own row so no event is lost."""
    visits = []
    open_visit = None
    current_member = None
    for row in rows:
        mid = row["member_id"]
        if mid != current_member:
            if open_visit is not None:
                visits.append(open_visit)
            open_visit = None
            current_member = mid

        if row["direction"] == "IN":
            if open_visit is not None:
                visits.append(open_visit)
            open_visit = {
                "member_id": mid,
                "first_name": row["first_name"],
                "last_name": row["last_name"],
                "in_time": row["timestamp"],
                "in_notes": row["notes"],
                "out_time": None,
                "out_notes": None,
            }
        else:  # OUT
            if open_visit is not None:
                open_visit["out_time"] = row["timestamp"]
                open_visit["out_notes"] = row["notes"]
                visits.append(open_visit)
                open_visit = None
            else:
                visits.append({
                    "member_id": mid,
                    "first_name": row["first_name"],
                    "last_name": row["last_name"],
                    "in_time": None,
                    "in_notes": None,
                    "out_time": row["timestamp"],
                    "out_notes": row["notes"],
                })

    if open_visit is not None:
        visits.append(open_visit)

    visits.sort(key=lambda v: v["in_time"] or v["out_time"], reverse=True)
    return visits


@app.route("/logs")
@login_required
def logs():
    page = max(1, int(request.args.get("page", 1)))
    per_page = 50
    status = request.args.get("status", "")
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")

    where_parts = []
    params = []
    if date_from:
        where_parts.append("DATE(s.timestamp) >= ?")
        params.append(date_from)
    if date_to:
        where_parts.append("DATE(s.timestamp) <= ?")
        params.append(date_to)
    where_clause = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

    with get_conn() as conn:
        rows = conn.execute(
            f"""SELECT s.member_id, m.first_name, m.last_name, s.direction, s.timestamp, s.notes
                FROM sign_ins s JOIN members m ON s.member_id=m.id
                {where_clause}
                ORDER BY s.member_id, s.timestamp, s.id""",
            params,
        ).fetchall()

    visits = _pair_sign_in_visits(rows)

    if status == "OPEN":
        visits = [v for v in visits if v["out_time"] is None]
    elif status == "CLOSED":
        visits = [v for v in visits if v["out_time"] is not None]

    total = len(visits)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, total_pages)
    offset = (page - 1) * per_page
    visits = visits[offset:offset + per_page]

    return render_template(
        "logs.html",
        rows=visits,
        page=page,
        total_pages=total_pages,
        total=total,
        status=status,
        date_from=date_from,
        date_to=date_to,
    )


@app.route("/audit")
@login_required
def audit():
    page = max(1, int(request.args.get("page", 1)))
    per_page = 50

    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) as c FROM audit_log").fetchone()["c"]
        offset = (page - 1) * per_page
        rows = conn.execute(
            "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            (per_page, offset),
        ).fetchall()
        rows = [dict(r) for r in rows]

    total_pages = max(1, (total + per_page - 1) // per_page)
    return render_template(
        "audit.html",
        rows=rows,
        page=page,
        total_pages=total_pages,
        total=total,
    )


@app.route("/people")
@login_required
def people():
    person_type = request.args.get("type", "member")
    search = request.args.get("search", "").strip()
    page = max(1, int(request.args.get("page", 1)))
    per_page = 50

    where_parts = ["(m.person_type = ? OR (? = 'member' AND m.person_type IS NULL))"]
    params = [person_type, person_type]

    if search:
        where_parts.append("(m.first_name LIKE ? OR m.last_name LIKE ?)")
        q = f"%{search}%"
        params.extend([q, q])

    where_clause = "WHERE " + " AND ".join(where_parts)

    with get_conn() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) as c FROM members m {where_clause}", params
        ).fetchone()["c"]

        offset = (page - 1) * per_page

        if person_type == "staff":
            rows = conn.execute(
                f"""SELECT m.id, m.first_name, m.last_name, m.school AS role,
                           m.date_of_birth, m.created_at
                    FROM members m {where_clause}
                    ORDER BY m.last_name, m.first_name
                    LIMIT ? OFFSET ?""",
                params + [per_page, offset],
            ).fetchall()
        else:
            rows = conn.execute(
                f"""SELECT m.id, m.first_name, m.last_name, m.school,
                           m.date_of_birth, m.created_at,
                           (SELECT GROUP_CONCAT(c.full_name, ', ')
                            FROM caregivers c WHERE c.member_id = m.id) AS caregivers
                    FROM members m {where_clause}
                    ORDER BY m.last_name, m.first_name
                    LIMIT ? OFFSET ?""",
                params + [per_page, offset],
            ).fetchall()

        rows = [dict(r) for r in rows]

    total_pages = max(1, (total + per_page - 1) // per_page)
    return render_template(
        "people.html",
        rows=rows,
        page=page,
        total_pages=total_pages,
        total=total,
        person_type=person_type,
        search=search,
    )


@app.route("/people/new", methods=["GET", "POST"])
@login_required
def person_new():
    person_type = request.args.get("type", "member")
    if request.method == "POST":
        person_type = request.form.get("person_type", "member")
        from database import upsert_member, upsert_caregiver
        data = {
            "first_name":         request.form.get("first_name", "").strip(),
            "last_name":          request.form.get("last_name", "").strip(),
            "date_of_birth":      request.form.get("date_of_birth", "").strip(),
            "school":             request.form.get("school", "").strip(),
            "pin":                request.form.get("pin", "").strip(),
            "person_type":        person_type,
            "mornings_days":      ",".join(request.form.getlist("mornings_days")),
            "afternoons_days":    ",".join(request.form.getlist("afternoons_days")),
            "needs_pickup":       1 if request.form.get("needs_pickup") == "1" else 0,
            "activity":           request.form.get("activity", "").strip(),
            "activity_time":      request.form.get("activity_time", "").strip(),
            "activity_address":   request.form.get("activity_address", "").strip(),
            "transport_required": 1 if request.form.get("transport_required") == "1" else 0,
            "activity_days":      ",".join(request.form.getlist("activity_days")),
        }
        if not data["first_name"] or not data["last_name"]:
            flash("First name and last name are required.", "error")
            return render_template("person_form.html", person=data, person_type=person_type,
                                   caregiver={}, is_new=True)
        member_id = upsert_member(data)
        if person_type == "member":
            cg_data = {
                "member_id":              member_id,
                "full_name":              request.form.get("cg_full_name", "").strip(),
                "phone":                  request.form.get("cg_phone", "").strip(),
                "email":                  request.form.get("cg_email", "").strip(),
                "street_address":         request.form.get("cg_street_address", "").strip(),
                "suburb":                 request.form.get("cg_suburb", "").strip(),
                "city":                   request.form.get("cg_city", "").strip(),
                "emergency_contact_name": request.form.get("cg_emergency_contact_name", "").strip(),
                "emergency_contact_phone": request.form.get("cg_emergency_contact_phone", "").strip(),
                "relationship":           request.form.get("cg_relationship", "").strip() or "Parent/Guardian",
                "notify_on":              request.form.get("cg_notify_on", "BOTH"),
            }
            upsert_caregiver(cg_data)
        flash(f"{'Staff member' if person_type == 'staff' else 'Member'} created.", "success")
        return redirect(url_for("person_edit", person_id=member_id))

    return render_template("person_form.html", person={}, person_type=person_type,
                           caregiver={}, is_new=True)


@app.route("/people/<int:person_id>", methods=["GET", "POST"])
@login_required
def person_edit(person_id):
    from database import get_member, get_caregiver, upsert_member, upsert_caregiver
    person = get_member(person_id)
    if not person:
        flash("Person not found.", "error")
        return redirect(url_for("people"))

    person_type = person.get("person_type") or "member"

    if request.method == "POST":
        data = {
            "id":                 person_id,
            "first_name":         request.form.get("first_name", "").strip(),
            "last_name":          request.form.get("last_name", "").strip(),
            "date_of_birth":      request.form.get("date_of_birth", "").strip(),
            "school":             request.form.get("school", "").strip(),
            "pin":                request.form.get("pin", "").strip(),
            "person_type":        person_type,
            "mornings_days":      ",".join(request.form.getlist("mornings_days")),
            "afternoons_days":    ",".join(request.form.getlist("afternoons_days")),
            "needs_pickup":       1 if request.form.get("needs_pickup") == "1" else 0,
            "activity":           request.form.get("activity", "").strip(),
            "activity_time":      request.form.get("activity_time", "").strip(),
            "activity_address":   request.form.get("activity_address", "").strip(),
            "transport_required": 1 if request.form.get("transport_required") == "1" else 0,
            "activity_days":      ",".join(request.form.getlist("activity_days")),
        }
        if not data["first_name"] or not data["last_name"]:
            flash("First name and last name are required.", "error")
            caregiver = get_caregiver(person_id) or {}
            return render_template("person_form.html", person=data, person_type=person_type,
                                   caregiver=caregiver, is_new=False)
        upsert_member(data)
        if person_type == "member":
            cg_data = {
                "member_id":              person_id,
                "full_name":              request.form.get("cg_full_name", "").strip(),
                "phone":                  request.form.get("cg_phone", "").strip(),
                "email":                  request.form.get("cg_email", "").strip(),
                "street_address":         request.form.get("cg_street_address", "").strip(),
                "suburb":                 request.form.get("cg_suburb", "").strip(),
                "city":                   request.form.get("cg_city", "").strip(),
                "emergency_contact_name": request.form.get("cg_emergency_contact_name", "").strip(),
                "emergency_contact_phone": request.form.get("cg_emergency_contact_phone", "").strip(),
                "relationship":           request.form.get("cg_relationship", "").strip() or "Parent/Guardian",
                "notify_on":              request.form.get("cg_notify_on", "BOTH"),
            }
            upsert_caregiver(cg_data)
        flash("Changes saved.", "success")
        return redirect(url_for("person_edit", person_id=person_id))

    caregiver = get_caregiver(person_id) or {} if person_type == "member" else {}
    return render_template("person_form.html", person=person, person_type=person_type,
                           caregiver=caregiver, is_new=False)


@app.route("/people/<int:person_id>/delete", methods=["POST"])
@login_required
def person_delete(person_id):
    from database import get_member, delete_member
    person = get_member(person_id)
    if not person:
        flash("Person not found.", "error")
        return redirect(url_for("people"))
    person_type = person.get("person_type") or "member"
    delete_member(person_id)
    flash(f"{person['first_name']} {person['last_name']} has been deleted.", "success")
    return redirect(url_for("people", type=person_type))


@app.route("/alerts", methods=["GET", "POST"])
@login_required
def alerts():
    from database import create_alert, get_alerts, search_runs, search_members

    if request.method == "POST":
        scope = request.form.get("scope", "all")
        message = request.form.get("message", "").strip()
        if not message:
            flash("Alert message cannot be empty.", "error")
            return redirect(url_for("alerts"))

        target_id = None
        if scope == "run":
            target_id = request.form.get("run_id", type=int)
            if not target_id:
                flash("Select a run sheet.", "error")
                return redirect(url_for("alerts"))
        elif scope == "member":
            target_id = request.form.get("member_id", type=int)
            if not target_id:
                flash("Select a person.", "error")
                return redirect(url_for("alerts"))
        elif scope != "all":
            flash("Invalid alert scope.", "error")
            return redirect(url_for("alerts"))

        duration_hours = None
        expiry_unit = request.form.get("expiry_unit", "none")
        if expiry_unit != "none":
            amount = request.form.get("expiry_amount", type=float)
            multipliers = {"hours": 1, "days": 24, "weeks": 168, "months": 720}
            if not amount or amount <= 0:
                flash("Enter a valid duration.", "error")
                return redirect(url_for("alerts"))
            duration_hours = amount * multipliers.get(expiry_unit, 1)

        create_alert(scope, target_id, message, duration_hours)
        log_event("ALERT_CREATED", f"Alert created via dashboard ({scope}): {message[:60]}")
        flash("Alert created.", "success")
        return redirect(url_for("alerts"))

    runs = search_runs("")
    members = search_members("")
    run_map = {r["id"]: r["name"] for r in runs}
    member_map = {m["id"]: f"{m['first_name']} {m['last_name']}" for m in members}

    alert_rows = get_alerts()
    for a in alert_rows:
        if a["scope"] == "all":
            a["target_name"] = "All Members"
        elif a["scope"] == "run":
            a["target_name"] = run_map.get(a["target_id"], "(deleted run)")
        else:
            a["target_name"] = member_map.get(a["target_id"], "(deleted person)")

    return render_template("alerts.html", alerts=alert_rows, runs=runs, members=members)


@app.route("/alerts/<int:alert_id>/delete", methods=["POST"])
@login_required
def alert_delete(alert_id):
    from database import delete_alert
    delete_alert(alert_id)
    log_event("ALERT_DELETED", f"Alert {alert_id} deleted via dashboard")
    flash("Alert deleted.", "success")
    return redirect(url_for("alerts"))


@app.route("/exports")
@login_required
def exports():
    from database import search_members, search_staff

    today = date.today().isoformat()
    week_start = (date.today() - timedelta(days=date.today().weekday())).isoformat()
    members = search_members("", "member")
    staff = search_staff("")
    return render_template("exports.html", today=today, week_start=week_start,
                           members=members, staff=staff)


@app.route("/export/members")
@login_required
def export_members():
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")
    if not date_from or not date_to:
        return "Missing date_from or date_to parameters", 400

    from database import get_signs_for_export
    from export_util import generate_export

    signs = get_signs_for_export(date_from, date_to)

    buf = io.BytesIO()
    generate_export(signs, date_from, date_to, buf)
    buf.seek(0)

    filename = f"Members_Export_{date_from}_{date_to}.xlsx"
    log_event("DASHBOARD_EXPORT", f"Member export downloaded: {date_from} to {date_to}")
    return send_file(buf, as_attachment=True, download_name=filename,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.route("/export/staff")
@login_required
def export_staff():
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")
    if not date_from or not date_to:
        return "Missing date_from or date_to parameters", 400

    from database import get_staff_signs_for_export
    from export_util import generate_staff_export

    signs = get_staff_signs_for_export(date_from, date_to)

    buf = io.BytesIO()
    generate_staff_export(signs, date_from, date_to, buf)
    buf.seek(0)

    filename = f"Staff_Export_{date_from}_{date_to}.xlsx"
    log_event("DASHBOARD_EXPORT", f"Staff export downloaded: {date_from} to {date_to}")
    return send_file(buf, as_attachment=True, download_name=filename,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.route("/export/person")
@login_required
def export_person():
    from database import get_member, get_signs_for_member
    from export_util import generate_export, generate_staff_export

    person_id = request.args.get("person_id", type=int)
    if not person_id:
        flash("Select a person to export.", "error")
        return redirect(url_for("exports"))

    person = get_member(person_id)
    if not person:
        flash("Person not found.", "error")
        return redirect(url_for("people"))

    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()

    signs = get_signs_for_member(person_id, date_from or None, date_to or None)
    if not signs:
        range_msg = f" between {date_from} and {date_to}" if (date_from or date_to) else ""
        flash(f"No sign-in records found for {person['first_name']} {person['last_name']}{range_msg}.", "error")
        return redirect(request.referrer or url_for("exports"))

    dates = [s["timestamp"][:10] for s in signs]
    export_from = date_from or min(dates)
    export_to = date_to or max(dates)

    buf = io.BytesIO()
    person_type = person.get("person_type") or "member"
    if person_type == "staff":
        generate_staff_export(signs, export_from, export_to, buf)
    else:
        generate_export(signs, export_from, export_to, buf)
    buf.seek(0)

    safe_name = f"{person['first_name']}_{person['last_name']}".replace(" ", "_")
    filename = f"{safe_name}_Export_{export_from}_{export_to}.xlsx"
    log_event("DASHBOARD_EXPORT",
              f"Sign-in history exported for {person['first_name']} {person['last_name']} "
              f"({export_from} to {export_to})")
    return send_file(buf, as_attachment=True, download_name=filename,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.route("/people/<int:person_id>/signature.png")
@login_required
def person_signature(person_id):
    from database import get_last_signature
    from export_util import render_signature

    row = get_last_signature(person_id)
    if not row:
        return "", 404

    png = render_signature(row["signature"], width=240, height=90)
    if not png:
        return "", 404

    return send_file(io.BytesIO(png), mimetype="image/png")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
