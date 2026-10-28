import io
import os
import secrets
import sys
import sqlite3
import json
from datetime import date, datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # pragma: no cover
    pass

from flask_wtf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

if getattr(sys, "frozen", False):  # pragma: no cover — only true inside a PyInstaller build
    _base_dir = os.path.dirname(sys.executable)
    _template_dir = os.path.join(sys._MEIPASS, "dashboard", "templates")
    _static_dir = os.path.join(sys._MEIPASS, "dashboard", "static")
    app = Flask(__name__, template_folder=_template_dir, static_folder=_static_dir)
else:
    app = Flask(__name__)


def _resolve_secret_key():
    key = os.environ.get("DASHBOARD_SECRET_KEY")
    if not key:
        key = secrets.token_hex(32)
        print(
            "WARNING: DASHBOARD_SECRET_KEY is not set — using a random secret key "
            "for this process only. Sessions will not survive a restart. Set "
            "DASHBOARD_SECRET_KEY in the environment (or a .env file) for production."
        )
    return key


app.secret_key = _resolve_secret_key()

# The dashboard is reachable both directly over plain HTTP on the local
# network (staff/admins on the same Wi-Fi as the kiosk — see the README) and
# over HTTPS via a reverse tunnel. A browser refuses to store or send a
# Secure-flagged cookie at all over a plain HTTP connection, so forcing this
# on unconditionally breaks every LAN login (the session — and the CSRF
# token stored in it — never persists, surfacing as "CSRF session token is
# missing" on submit). Default to False so LAN access keeps working; the
# internet-facing path is still protected by the tunnel's own TLS
# termination. Set DASHBOARD_COOKIE_SECURE=true only if this is ever
# deployed somewhere reachable exclusively over HTTPS.
_cookie_secure = os.environ.get("DASHBOARD_COOKIE_SECURE", "false").strip().lower() == "true"

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=_cookie_secure,
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
)

csrf = CSRFProtect(app)
limiter = Limiter(get_remote_address, app=app, default_limits=[])


@app.after_request
def _set_security_headers(response):
    """Standard response hardening headers -- free, no external service,
    and safe for both the plain-HTTP LAN path and the HTTPS tunnel path.
    'unsafe-inline' is needed because dashboard.html/alerts.html inject
    server-rendered data via inline <script> blocks, and several templates
    use inline style="" attributes; every inline script/style is our own
    template output, never user-supplied, so this is a pragmatic choice
    over threading CSP nonces through the whole template set."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:"
    )
    if request.is_secure:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

if getattr(sys, "frozen", False):  # pragma: no cover — only true inside a PyInstaller build
    _data_dir = os.path.join(
        os.environ.get("LOCALAPPDATA", os.path.dirname(sys.executable)),
        "Kiosk Sign-In",
    ) if sys.platform == "win32" else os.path.dirname(sys.executable)
    DB_PATH = os.path.join(_data_dir, "signin_data.db")
else:
    DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "kiosk_signin", "signin_data.db")

if getattr(sys, "frozen", False):  # pragma: no cover — only true inside a PyInstaller build
    sys.path.insert(0, os.path.join(sys._MEIPASS, "kiosk_signin"))
else:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "kiosk_signin"))

from database import init_db
init_db()


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
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        if session.get("role") != "admin":
            flash("Admin access required.", "error")
            return redirect(url_for("signin"))
        return f(*args, **kwargs)
    return decorated


@app.route("/")
def index():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    if session.get("role") == "admin":
        return redirect(url_for("dashboard"))
    return redirect(url_for("signin"))


@app.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def login():
    error = None
    if request.method == "POST":
        from database import check_dashboard_login, is_dashboard_user_locked
        name = request.form.get("username", "").strip()
        pin = request.form.get("password", "").strip()
        if is_dashboard_user_locked(name):
            error = "Account temporarily locked after repeated failed logins. Try again in a few minutes."
        else:
            user = check_dashboard_login(name, pin)
            if user:
                session.clear()
                session["user_id"] = user["id"]
                session["name"] = user["name"]
                session["role"] = user["role"]
                session["member_id"] = user.get("member_id")
                session.permanent = True
                log_event("DASHBOARD_LOGIN", f"{user['role']} '{user['name']}' logged into the web dashboard")
                return redirect(url_for("dashboard" if user["role"] == "admin" else "signin"))
            log_event("DASHBOARD_LOGIN_FAILED", f"Failed login attempt for '{name}'")
            error = "Invalid name or password."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    if session.get("user_id"):
        log_event("DASHBOARD_LOGOUT", f"'{session.get('name')}' logged out of the web dashboard")
    session.clear()
    return redirect(url_for("login"))


def _parse_signature(raw: str):
    """Converts the browser's JSON stroke list (e.g. '[[1,2,3,4],...]') into
    the exact `str([(x1,y1,x2,y2), ...]).encode()` byte format the kiosk's
    SignatureCanvas.export_bytes() produces, so export_util.render_signature()
    and the /people/<id>/signature.png route keep working unmodified.
    Returns None for no signature, raises ValueError for malformed input."""
    raw = (raw or "").strip()
    if not raw:
        return None
    strokes = json.loads(raw)
    if not isinstance(strokes, list) or len(strokes) > 20000:
        raise ValueError("invalid stroke list")
    clean = []
    for s in strokes:
        if not (isinstance(s, list) and len(s) == 4
                and all(isinstance(n, (int, float)) and not isinstance(n, bool) for n in s)):
            raise ValueError("invalid stroke segment")
        clean.append(tuple(s))
    return str(clean).encode() if clean else None


@app.route("/signin", methods=["GET", "POST"])
@login_required
def signin():
    if request.method == "POST":
        from database import get_allowed_direction, record_sign, get_member
        from email_notifier import send_notification

        member_ids = [int(x) for x in request.form.getlist("member_ids") if x.strip().isdigit()]
        direction = request.form.get("direction", "").strip().upper()
        notes = request.form.get("notes", "").strip()

        if not member_ids:
            flash("Select at least one person to sign in or out.", "error")
            return redirect(url_for("signin"))
        if direction not in ("IN", "OUT"):
            flash("Choose a direction (IN or OUT).", "error")
            return redirect(url_for("signin"))

        try:
            sig_bytes = _parse_signature(request.form.get("signature_data", ""))
        except (ValueError, TypeError):
            flash("Invalid signature data — please try signing again.", "error")
            return redirect(url_for("signin"))

        allowed, blocked = [], []
        for mid in member_ids:
            if get_allowed_direction(mid) == direction:
                allowed.append(mid)
            else:
                blocked.append(mid)

        if not allowed:
            other = "OUT" if direction == "IN" else "IN"
            flash(f"Selected people need to sign {other} first.", "error")
            return redirect(url_for("signin"))

        now = datetime.now()
        for mid in allowed:
            member = get_member(mid)
            record_sign(mid, direction, notes, sig_bytes)
            send_notification(member, direction, now)

        label = "in" if direction == "IN" else "out"
        msg = f"{len(allowed)} signed {label} at {now.strftime('%H:%M')}."
        if blocked:
            msg += f" {len(blocked)} skipped (already signed {label})."
        flash(msg, "success")
        return redirect(url_for("signin"))

    return render_template("signin.html")


@app.route("/signin/search")
@login_required
def signin_search():
    from database import search_members, search_staff

    q = request.args.get("q", "").strip()
    person_type = request.args.get("type", "member")
    if not q:
        return {"results": []}

    rows = search_staff(q) if person_type == "staff" else search_members(q, "member")
    results = [{"id": r["id"], "name": f"{r['first_name']} {r['last_name']}"} for r in rows]
    return {"results": results}


@app.route("/signin/alerts")
@login_required
def signin_alerts():
    from database import get_alerts_for_members

    ids_param = request.args.get("member_ids", "")
    member_ids = [int(x) for x in ids_param.split(",") if x.strip().isdigit()]
    alert_rows = get_alerts_for_members(member_ids)
    return {"alerts": [{"message": a["message"]} for a in alert_rows]}


def _today_snapshot(conn, today):
    """Today's sign-in count, currently-signed-in count, and the list of
    who's currently in — the subset of dashboard data shared with the
    lightweight staff /status view."""
    from database import get_currently_signed_in

    today_ins = conn.execute("""
        SELECT COUNT(DISTINCT member_id) as c FROM sign_ins
        WHERE DATE(timestamp) = ? AND direction = 'IN'
    """, (today,)).fetchone()["c"]

    signed_in_list = get_currently_signed_in()
    currently_in = len(signed_in_list)

    return today_ins, currently_in, signed_in_list


@app.route("/status")
@login_required
def status():
    """Lightweight read-only view for staff: today's totals and who's
    currently signed in, with none of the historical charts or admin
    management links that /dashboard exposes."""
    today = date.today().isoformat()
    with get_conn() as conn:
        today_ins, currently_in, signed_in_list = _today_snapshot(conn, today)

    return render_template(
        "status.html",
        today=today,
        today_ins=today_ins,
        currently_in=currently_in,
        signed_in_list=signed_in_list,
    )


@app.route("/my-timesheet")
@login_required
def my_timesheet():
    """Self-service view of the logged-in staff member's own sign-in
    history. The person is resolved strictly from the session's linked
    member_id -- never from a client-supplied id -- so one staff account
    can never view another's timesheet."""
    from database import get_dashboard_user, get_signs_for_member

    user = get_dashboard_user(session["user_id"])
    if not user or not user.get("member_id"):
        flash("Your account isn't linked to a staff record yet. Ask an admin to link it "
              "from the Manage Dashboard Users page.", "error")
        return redirect(url_for("signin"))

    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    rows = get_signs_for_member(user["member_id"], date_from or None, date_to or None)
    visits = _pair_sign_in_visits(rows)

    return render_template("my_timesheet.html", visits=visits, date_from=date_from, date_to=date_to)


@app.route("/my-timesheet/download")
@login_required
def my_timesheet_download():
    from database import get_dashboard_user, get_member

    user = get_dashboard_user(session["user_id"])
    if not user or not user.get("member_id"):
        flash("Your account isn't linked to a staff record yet. Ask an admin to link it "
              "from the Manage Dashboard Users page.", "error")
        return redirect(url_for("signin"))

    person = get_member(user["member_id"])
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    fmt = request.args.get("fmt", "xlsx")

    resp = _export_person_response(person, date_from, date_to, fmt)
    return resp if resp is not None else redirect(url_for("my_timesheet"))


@app.route("/dashboard")
@admin_required
def dashboard():
    today = date.today().isoformat()
    week_start = (date.today() - timedelta(days=date.today().weekday())).isoformat()

    with get_conn() as conn:
        today_ins, currently_in, signed_in_list = _today_snapshot(conn, today)

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
    OUT with no preceding IN is kept as its own row so no event is lost.
    Each visit carries the underlying sign_ins.id for in/out (in_id/out_id,
    None if that side is missing) so the dashboard can link to editing the
    individual record's timestamp."""
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
                "person_type": row["person_type"] if "person_type" in row.keys() else None,
                "in_id": row["id"],
                "in_time": row["timestamp"],
                "in_notes": row["notes"],
                "out_id": None,
                "out_time": None,
                "out_notes": None,
            }
        else:  # OUT
            if open_visit is not None:
                open_visit["out_id"] = row["id"]
                open_visit["out_time"] = row["timestamp"]
                open_visit["out_notes"] = row["notes"]
                visits.append(open_visit)
                open_visit = None
            else:
                visits.append({
                    "member_id": mid,
                    "first_name": row["first_name"],
                    "last_name": row["last_name"],
                    "person_type": row["person_type"] if "person_type" in row.keys() else None,
                    "in_id": None,
                    "in_time": None,
                    "in_notes": None,
                    "out_id": row["id"],
                    "out_time": row["timestamp"],
                    "out_notes": row["notes"],
                })

    if open_visit is not None:
        visits.append(open_visit)

    visits.sort(key=lambda v: v["in_time"] or v["out_time"], reverse=True)
    return visits


@app.route("/logs")
@admin_required
def logs():
    page = max(1, int(request.args.get("page", 1)))
    per_page = 50
    status = request.args.get("status", "")
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")
    search = request.args.get("search", "").strip()

    # Date filters are applied to visits after pairing, not to the raw rows —
    # otherwise an IN just outside the range would leave its OUT orphaned.
    where_parts = []
    params = []
    if search:
        where_parts.append("(m.first_name || ' ' || m.last_name) LIKE ?")
        params.append(f"%{search}%")
    where_clause = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

    with get_conn() as conn:
        rows = conn.execute(
            f"""SELECT s.id, s.member_id, m.first_name, m.last_name, m.person_type,
                       s.direction, s.timestamp, s.notes
                FROM sign_ins s JOIN members m ON s.member_id=m.id
                {where_clause}
                ORDER BY s.member_id, s.timestamp, s.id""",
            params,
        ).fetchall()

    visits = _pair_sign_in_visits(rows)

    if date_from:
        visits = [v for v in visits if (v["in_time"] or v["out_time"])[:10] >= date_from]
    if date_to:
        visits = [v for v in visits if (v["in_time"] or v["out_time"])[:10] <= date_to]

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
        search=search,
    )


def _parse_sign_time(raw: str):
    """datetime-local form value -> 'YYYY-MM-DD HH:MM:00', or None if invalid."""
    try:
        return datetime.strptime(raw.strip(), "%Y-%m-%dT%H:%M").strftime("%Y-%m-%d %H:%M:00")
    except ValueError:
        return None


def _time_in_bounds(ts: str, after, before) -> bool:
    """True if ts falls strictly between the neighbouring records' timestamps.
    Keeping an edited/added record inside its neighbours means the IN/OUT
    order is preserved, so the visit it belongs to on /logs never changes
    (moving an OUT before its IN would otherwise split one visit into two)."""
    return (after is None or ts > after) and (before is None or ts < before)


def _bounds_error(after, before) -> str:
    if after and before:
        return f"Time must be after {after} and before {before} to stay part of this visit."
    if after:
        return f"Time must be after {after} to stay part of this visit."
    return f"Time must be before {before} to stay part of this visit."


def _to_input(ts):
    """'YYYY-MM-DD HH:MM:SS' -> datetime-local value, or '' for None."""
    return ts[:16].replace(" ", "T") if ts else ""


@app.route("/logs/sign/<int:sign_id>/edit", methods=["GET", "POST"])
@admin_required
def sign_edit(sign_id):
    from database import get_sign, get_sign_neighbours, update_sign_time

    sign = get_sign(sign_id)
    if not sign:
        flash("Sign-in record not found.", "error")
        return redirect(url_for("logs"))

    prev, nxt = get_sign_neighbours(sign_id)
    after = prev["timestamp"] if prev else None
    before = nxt["timestamp"] if nxt else None
    ctx = dict(sign=sign, after=after, before=before,
               value=_to_input(sign["timestamp"]), to_input=_to_input)

    if request.method == "POST":
        new_timestamp = _parse_sign_time(request.form.get("timestamp", ""))
        if new_timestamp is None:
            flash("Enter a valid date and time.", "error")
            return render_template("sign_edit.html", **ctx)
        if not _time_in_bounds(new_timestamp, after, before):
            flash(_bounds_error(after, before), "error")
            ctx["value"] = _to_input(new_timestamp)
            return render_template("sign_edit.html", **ctx)

        old_timestamp = sign["timestamp"]
        update_sign_time(sign_id, new_timestamp)
        log_event(
            "SIGN_TIME_EDITED",
            f"{sign['first_name']} {sign['last_name']}'s {sign['direction']} time "
            f"changed from {old_timestamp} to {new_timestamp}",
        )
        flash("Sign-in time updated.", "success")
        return redirect(url_for("logs"))

    return render_template("sign_edit.html", **ctx)


@app.route("/logs/sign/add", methods=["GET", "POST"])
@admin_required
def sign_add():
    from database import get_member, get_sign, get_sign_neighbours, add_sign

    member_id = request.values.get("member_id", type=int)
    direction = request.values.get("direction", "").upper()
    pair_id = request.values.get("pair_id", type=int)

    if not member_id or direction not in ("IN", "OUT"):
        flash("Invalid request.", "error")
        return redirect(url_for("logs"))

    person = get_member(member_id)
    if not person:
        flash("Person not found.", "error")
        return redirect(url_for("logs"))

    # The existing other half of the visit this record completes: a missing
    # OUT is added to an IN, a missing IN to a stray OUT.
    pair = get_sign(pair_id) if pair_id else None
    if (not pair or pair["member_id"] != member_id
            or pair["direction"] == direction):
        flash("Sign-in record not found.", "error")
        return redirect(url_for("logs"))

    prev, nxt = get_sign_neighbours(pair_id)
    if direction == "OUT":
        after, before = pair["timestamp"], (nxt["timestamp"] if nxt else None)
        default = datetime.strptime(pair["timestamp"][:16], "%Y-%m-%d %H:%M") + timedelta(minutes=1)
    else:
        after, before = (prev["timestamp"] if prev else None), pair["timestamp"]
        default = datetime.strptime(pair["timestamp"][:16], "%Y-%m-%d %H:%M")
        if pair["timestamp"][17:19] in ("", "00"):
            default -= timedelta(minutes=1)
    ctx = dict(person=person, direction=direction, pair=pair,
               after=after, before=before,
               value=default.strftime("%Y-%m-%dT%H:%M"), to_input=_to_input)

    if request.method == "POST":
        new_timestamp = _parse_sign_time(request.form.get("timestamp", ""))
        if new_timestamp is None:
            flash("Enter a valid date and time.", "error")
            return render_template("sign_add.html", **ctx)
        if not _time_in_bounds(new_timestamp, after, before):
            flash(_bounds_error(after, before), "error")
            ctx["value"] = _to_input(new_timestamp)
            return render_template("sign_add.html", **ctx)

        add_sign(member_id, direction, new_timestamp)
        log_event(
            "SIGN_TIME_ADDED",
            f"{person['first_name']} {person['last_name']}'s missing {direction} time "
            f"added as {new_timestamp}",
        )
        flash("Sign-in record added.", "success")
        return redirect(url_for("logs"))

    return render_template("sign_add.html", **ctx)


@app.route("/logs/sign/delete", methods=["POST"])
@admin_required
def sign_delete():
    """Delete one or more sign_ins records — a single IN/OUT from the edit
    page, or both halves of a visit from the logs table."""
    from database import get_sign, delete_signs

    signs = [get_sign(i) for i in request.form.getlist("sign_id", type=int)]
    signs = [s for s in signs if s]
    if not signs:
        flash("Sign-in record not found.", "error")
        return redirect(url_for("logs"))

    delete_signs([s["id"] for s in signs])
    for s in signs:
        log_event(
            "SIGN_DELETED",
            f"{s['first_name']} {s['last_name']}'s {s['direction']} at "
            f"{s['timestamp']} deleted",
        )
    flash("Sign-in record deleted." if len(signs) == 1 else "Visit deleted.", "success")
    return redirect(url_for("logs"))


@app.route("/audit")
@admin_required
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
@admin_required
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
@admin_required
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
@admin_required
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
@admin_required
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


@app.route("/run-sheets")
@login_required
def run_sheets():
    from database import list_runs

    search = request.args.get("search", "").strip()
    runs = list_runs(search)
    return render_template("run_sheets.html", runs=runs, search=search)


@app.route("/run-sheets/new", methods=["GET", "POST"])
@login_required
def run_sheet_new():
    if request.method == "POST":
        from database import create_run

        name = request.form.get("name", "").strip()
        member_ids = [int(x) for x in request.form.getlist("member_ids") if x.strip().isdigit()]
        if not name:
            flash("Run sheet name is required.", "error")
            return render_template("run_sheet_form.html", run={}, members=[], is_new=True)

        run_id = create_run(name, member_ids)
        if run_id is None:
            flash(f"A run sheet named \"{name}\" already exists.", "error")
            return render_template("run_sheet_form.html", run={"name": name}, members=[], is_new=True)

        flash("Run sheet created.", "success")
        return redirect(url_for("run_sheets"))

    return render_template("run_sheet_form.html", run={}, members=[], is_new=True)


@app.route("/run-sheets/<int:run_id>/edit", methods=["GET", "POST"])
@login_required
def run_sheet_edit(run_id):
    from database import get_run, get_run_members, update_run

    run = get_run(run_id)
    if not run:
        flash("Run sheet not found.", "error")
        return redirect(url_for("run_sheets"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        member_ids = [int(x) for x in request.form.getlist("member_ids") if x.strip().isdigit()]
        if not name:
            flash("Run sheet name is required.", "error")
            members = [{"id": m["id"], "name": f"{m['first_name']} {m['last_name']}"} for m in get_run_members(run_id)]
            return render_template("run_sheet_form.html", run=run, members=members, is_new=False)

        if not update_run(run_id, name, member_ids):
            flash(f"A run sheet named \"{name}\" already exists.", "error")
            members = [{"id": m["id"], "name": f"{m['first_name']} {m['last_name']}"} for m in get_run_members(run_id)]
            return render_template("run_sheet_form.html", run={**run, "name": name}, members=members, is_new=False)

        flash("Run sheet updated.", "success")
        return redirect(url_for("run_sheets"))

    members = [{"id": m["id"], "name": f"{m['first_name']} {m['last_name']}"} for m in get_run_members(run_id)]
    return render_template("run_sheet_form.html", run=run, members=members, is_new=False)


@app.route("/run-sheets/<int:run_id>/delete", methods=["POST"])
@login_required
def run_sheet_delete(run_id):
    from database import get_run, delete_run

    run = get_run(run_id)
    if not run:
        flash("Run sheet not found.", "error")
        return redirect(url_for("run_sheets"))
    delete_run(run_id)
    flash(f"Run sheet \"{run['name']}\" deleted.", "success")
    return redirect(url_for("run_sheets"))


@app.route("/run-sheets/search")
@login_required
def run_sheet_search():
    from database import search_runs

    q = request.args.get("q", "").strip()
    if not q:
        return {"results": []}
    results = [{"id": r["id"], "name": r["name"]} for r in search_runs(q)]
    return {"results": results}


@app.route("/run-sheets/<int:run_id>/members")
@login_required
def run_sheet_members(run_id):
    from database import get_run_members

    members = [{"id": m["id"], "name": f"{m['first_name']} {m['last_name']}"} for m in get_run_members(run_id)]
    return {"members": members}


@app.route("/signin/currently-in")
@login_required
def signin_currently_in():
    from database import get_currently_signed_in

    members = [{"id": m["id"], "name": f"{m['first_name']} {m['last_name']}"} for m in get_currently_signed_in()]
    return {"members": members}


@app.route("/alerts", methods=["GET", "POST"])
@admin_required
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
@admin_required
def alert_delete(alert_id):
    from database import delete_alert
    delete_alert(alert_id)
    log_event("ALERT_DELETED", f"Alert {alert_id} deleted via dashboard")
    flash("Alert deleted.", "success")
    return redirect(url_for("alerts"))


@app.route("/exports")
@admin_required
def exports():
    from database import search_members, search_staff

    today = date.today().isoformat()
    week_start = (date.today() - timedelta(days=date.today().weekday())).isoformat()
    members = search_members("", "member")
    staff = search_staff("")
    return render_template("exports.html", today=today, week_start=week_start,
                           members=members, staff=staff)


_EXPORT_FORMATS = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
    "csv": "text/csv",
}


def _export_person_response(person, date_from, date_to, fmt="xlsx"):
    """Build the download for one person's sign-in history in the given
    format (xlsx/pdf/csv), or flash a "no records" message and return None
    if the range is empty."""
    from database import get_signs_for_member
    from export_util import (generate_export, generate_staff_export,
                             generate_export_pdf, generate_staff_export_pdf,
                             generate_export_csv, generate_staff_export_csv)

    if fmt not in _EXPORT_FORMATS:
        fmt = "xlsx"

    signs = get_signs_for_member(person["id"], date_from or None, date_to or None)
    if not signs:
        range_msg = f" between {date_from} and {date_to}" if (date_from or date_to) else ""
        flash(f"No sign-in records found for {person['first_name']} {person['last_name']}{range_msg}.", "error")
        return None

    dates = [s["timestamp"][:10] for s in signs]
    export_from = date_from or min(dates)
    export_to = date_to or max(dates)
    person_type = person.get("person_type") or "member"

    if fmt == "pdf":
        buf = io.BytesIO()
        (generate_staff_export_pdf if person_type == "staff" else generate_export_pdf)(
            signs, export_from, export_to, buf)
    elif fmt == "csv":
        text_buf = io.StringIO()
        (generate_staff_export_csv if person_type == "staff" else generate_export_csv)(
            signs, export_from, export_to, text_buf)
        buf = io.BytesIO(text_buf.getvalue().encode("utf-8"))
    else:
        buf = io.BytesIO()
        (generate_staff_export if person_type == "staff" else generate_export)(
            signs, export_from, export_to, buf)
    buf.seek(0)

    safe_name = f"{person['first_name']}_{person['last_name']}".replace(" ", "_")
    filename = f"KioskSignIn_{safe_name}_Export_{export_from}_{export_to}.{fmt}"
    log_event("DASHBOARD_EXPORT",
              f"Sign-in history exported for {person['first_name']} {person['last_name']} "
              f"({export_from} to {export_to})")
    return send_file(buf, as_attachment=True, download_name=filename,
                     mimetype=_EXPORT_FORMATS[fmt])


@app.route("/export/staff")
@admin_required
def export_staff():
    from database import get_member, get_staff_signs_for_export
    from export_util import generate_staff_export, generate_staff_export_pdf, generate_staff_export_csv

    person_id = request.args.get("person_id", type=int)
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    fmt = request.args.get("fmt", "xlsx")
    if fmt not in _EXPORT_FORMATS:
        fmt = "xlsx"

    if person_id:
        person = get_member(person_id)
        if not person or (person.get("person_type") or "member") != "staff":
            flash("Staff member not found.", "error")
            return redirect(url_for("exports"))
        resp = _export_person_response(person, date_from, date_to, fmt)
        return resp if resp is not None else redirect(url_for("exports"))

    if not date_from or not date_to:
        return "Missing date_from or date_to parameters", 400

    signs = get_staff_signs_for_export(date_from, date_to)

    if fmt == "pdf":
        buf = io.BytesIO()
        generate_staff_export_pdf(signs, date_from, date_to, buf)
    elif fmt == "csv":
        text_buf = io.StringIO()
        generate_staff_export_csv(signs, date_from, date_to, text_buf)
        buf = io.BytesIO(text_buf.getvalue().encode("utf-8"))
    else:
        buf = io.BytesIO()
        generate_staff_export(signs, date_from, date_to, buf)
    buf.seek(0)

    filename = f"KioskSignIn_Staff_Export_{date_from}_{date_to}.{fmt}"
    log_event("DASHBOARD_EXPORT", f"Staff export downloaded: {date_from} to {date_to}")
    return send_file(buf, as_attachment=True, download_name=filename,
                     mimetype=_EXPORT_FORMATS[fmt])


@app.route("/export/person")
@admin_required
def export_person():
    from database import get_member

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
    fmt = request.args.get("fmt", "xlsx")

    resp = _export_person_response(person, date_from, date_to, fmt)
    return resp if resp is not None else redirect(request.referrer or url_for("exports"))


@app.route("/people/<int:person_id>/signature.png")
@admin_required
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


@app.route("/dashboard-users")
@admin_required
def dashboard_users():
    from database import list_dashboard_users, search_staff
    staff = search_staff("")
    staff_by_id = {s["id"]: f"{s['first_name']} {s['last_name']}" for s in staff}
    return render_template("dashboard_users.html", users=list_dashboard_users(),
                           staff=staff, staff_by_id=staff_by_id)


@app.route("/dashboard-users/new", methods=["POST"])
@admin_required
def dashboard_user_new():
    from database import create_dashboard_user, validate_dashboard_password
    name = request.form.get("name", "").strip()
    pin = request.form.get("pin", "").strip()
    role = request.form.get("role", "staff")
    member_id = request.form.get("member_id", type=int) or None
    if role not in ("admin", "staff"):
        role = "staff"
    if not name or not pin:
        flash("Name and password are required.", "error")
        return redirect(url_for("dashboard_users"))
    err = validate_dashboard_password(pin)
    if err:
        flash(err, "error")
        return redirect(url_for("dashboard_users"))
    user_id = create_dashboard_user(name, pin, role, member_id)
    if user_id is None:
        flash(f"A dashboard user named '{name}' already exists.", "error")
    else:
        flash(f"Dashboard user '{name}' created.", "success")
    return redirect(url_for("dashboard_users"))


@app.route("/dashboard-users/<int:user_id>/edit", methods=["GET", "POST"])
@admin_required
def dashboard_user_edit(user_id):
    from database import (get_dashboard_user, update_dashboard_user, set_dashboard_user_pin,
                           validate_dashboard_password, list_dashboard_users, search_staff)
    target = get_dashboard_user(user_id)
    if not target:
        flash("Dashboard user not found.", "error")
        return redirect(url_for("dashboard_users"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        role = request.form.get("role", "staff")
        if role not in ("admin", "staff"):
            role = "staff"
        member_id = request.form.get("member_id", type=int) or None
        new_pin = request.form.get("pin", "").strip()

        if not name:
            flash("Name is required.", "error")
            return render_template("dashboard_user_edit.html", user=target, staff=search_staff(""))

        admins = [u for u in list_dashboard_users() if u["role"] == "admin"]
        if target["role"] == "admin" and role != "admin" and len(admins) <= 1:
            flash("Cannot change the role of the last remaining admin account.", "error")
            return render_template("dashboard_user_edit.html", user=target, staff=search_staff(""))

        if new_pin:
            err = validate_dashboard_password(new_pin)
            if err:
                flash(err, "error")
                return render_template("dashboard_user_edit.html", user=target, staff=search_staff(""))

        if not update_dashboard_user(user_id, name, role, member_id):
            flash(f"A dashboard user named '{name}' already exists.", "error")
            return render_template("dashboard_user_edit.html", user=target, staff=search_staff(""))

        if new_pin:
            set_dashboard_user_pin(user_id, new_pin)

        flash(f"Dashboard user '{name}' updated.", "success")
        return redirect(url_for("dashboard_users"))

    return render_template("dashboard_user_edit.html", user=target, staff=search_staff(""))


@app.route("/dashboard-users/<int:user_id>/delete", methods=["POST"])
@admin_required
def dashboard_user_delete(user_id):
    from database import list_dashboard_users, delete_dashboard_user, get_dashboard_user
    target = get_dashboard_user(user_id)
    if not target:
        flash("Dashboard user not found.", "error")
        return redirect(url_for("dashboard_users"))

    admins = [u for u in list_dashboard_users() if u["role"] == "admin"]
    if target["role"] == "admin" and len(admins) <= 1:
        flash("Cannot delete the last remaining admin account.", "error")
        return redirect(url_for("dashboard_users"))

    delete_dashboard_user(user_id)
    flash(f"Dashboard user '{target['name']}' deleted.", "success")
    return redirect(url_for("dashboard_users"))


if __name__ == "__main__":  # pragma: no cover
    from waitress import serve
    serve(app, host="0.0.0.0", port=5000)
