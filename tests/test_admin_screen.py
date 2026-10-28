"""
Tests for screens/admin_screen.py — the password gate, and the admin panel's
today's-log, password change, bulk/single exports, member & staff management,
run sheet editor, and alerts subsystem.
"""
import pytest
from helpers import FakeApp, member as _member, staff_member as _staff


def _toplevels(root):
    return [w for w in root.winfo_children() if isinstance(w, __import__("tkinter").Toplevel)]


def _clear_seed_runs(db):
    """The dev seed data (init_db) always creates a 'Group A' run sheet
    with sample members. Tests exercising a genuinely empty run list need
    to remove it first."""
    for r in db.search_runs(""):
        db.delete_run(r["id"])


# ══════════════════════════════════════════════════════════════════════════════
# _ExportRangeDialog
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def dialog(tk_root):
    from screens.admin_screen import _ExportRangeDialog
    calls = []
    d = _ExportRangeDialog(tk_root, "Jane Doe", lambda f, t: calls.append((f, t)))
    d.update()
    d._calls = calls
    return d


def test_export_range_dialog_shows_person_name(dialog):
    # The header label is the 2nd child (after the accent bar).
    header = dialog.winfo_children()[1]
    assert "Jane Doe" in header.cget("text")


def test_export_range_dialog_set_range_fills_dates(dialog):
    dialog._set_range(6)
    assert dialog._from.get() != ""
    assert dialog._to.get() != ""


def test_export_range_dialog_clear_range_empties_dates(dialog):
    dialog._set_range(6)
    dialog._clear_range()
    assert dialog._from.get() == ""
    assert dialog._to.get() == ""


def test_export_range_dialog_confirm_with_blank_dates_calls_back(dialog):
    dialog._confirm()
    assert dialog._calls == [("", "")]


def test_export_range_dialog_confirm_with_valid_dates(dialog):
    dialog._from.insert(0, "2026-01-01")
    dialog._to.insert(0, "2026-01-31")
    dialog._confirm()
    assert dialog._calls == [("2026-01-01", "2026-01-31")]


def test_export_range_dialog_confirm_with_invalid_date_shows_error(dialog):
    dialog._from.insert(0, "not-a-date")
    dialog._confirm()
    assert dialog._calls == []
    assert "YYYY-MM-DD" in dialog._error.cget("text")


def test_export_range_dialog_cancel_button_destroys_without_callback(dialog):
    btn_row = dialog.winfo_children()[-1]
    cancel_btn = next(b for b in btn_row.winfo_children() if b.cget("text") == "Cancel")
    cancel_btn.invoke()
    assert dialog._calls == []


# ══════════════════════════════════════════════════════════════════════════════
# AdminPasswordScreen
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def pw_screen(tk_root, db):
    from screens.admin_screen import AdminPasswordScreen
    s = AdminPasswordScreen(tk_root, FakeApp())
    s.pack()
    tk_root.update()
    return s


def test_password_screen_correct_password_navigates_to_admin_panel(pw_screen, db):
    pw_screen._pw_entry.insert(0, "admin1234")
    pw_screen._attempt()
    assert pw_screen.app.last_call == ("admin_panel", {})
    assert pw_screen._pw_entry.get() == ""


def test_password_screen_wrong_password_shows_error_and_clears(pw_screen, db):
    pw_screen._pw_entry.insert(0, "wrong")
    pw_screen._attempt()
    assert pw_screen.app.calls == []
    assert pw_screen._pw_entry.get() == ""
    popups = _toplevels(pw_screen.winfo_toplevel())
    assert len(popups) == 1
    assert "Incorrect password" in popups[0]._msg.get("1.0", "end")


def test_password_screen_on_show_clears_entry(pw_screen, db):
    pw_screen._pw_entry.insert(0, "leftover")
    pw_screen.on_show()
    assert pw_screen._pw_entry.get() == ""


# ══════════════════════════════════════════════════════════════════════════════
# AdminPanelScreen
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def panel(tk_root, db):
    from screens.admin_screen import AdminPanelScreen
    s = AdminPanelScreen(tk_root, FakeApp())
    s.pack()
    tk_root.update()
    return s


@pytest.fixture
def home_dir(tmp_path, monkeypatch):
    """Redirect the admin panel's export file writes away from the real
    home directory (~), which os.path.expanduser("~") would otherwise use."""
    import os
    monkeypatch.setattr(os.path, "expanduser", lambda p: str(tmp_path))
    return tmp_path


@pytest.fixture
def broken_home_dir(monkeypatch):
    """Point the export's "home directory" at a path whose parent doesn't
    exist, so wb.save() raises and the except-branch status message shows."""
    import os
    monkeypatch.setattr(os.path, "expanduser", lambda p: "/no/such/directory")


# ── Today's log ────────────────────────────────────────────────────────────

def test_load_log_shows_placeholder_when_empty(panel, db):
    panel._load_log()
    labels = [w.cget("text") for w in panel._log_frame.winfo_children()]
    assert "No sign-ins today." in labels


def test_load_log_lists_todays_signs(panel, db):
    mid = db.upsert_member(_member(first_name="Logged", last_name="Person"))
    db.record_sign(mid, "IN")
    panel._load_log()
    rows = panel._log_frame.winfo_children()
    assert len(rows) == 1
    texts = [w.cget("text") for w in rows[0].winfo_children()]
    assert "Logged Person" in texts
    assert "IN" in texts


def test_load_log_reload_clears_previous_rows(panel, db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")
    panel._load_log()
    panel._load_log()
    assert len(panel._log_frame.winfo_children()) == 1


# ── Password change ────────────────────────────────────────────────────────

def test_change_pw_empty_shows_error(panel, db):
    panel._change_pw()
    assert "cannot be empty" in panel._pw_status.cget("text")


def test_change_pw_mismatch_shows_error(panel, db):
    panel._new_pw.insert(0, "newpass1")
    panel._conf_pw.insert(0, "different")
    panel._change_pw()
    assert "do not match" in panel._pw_status.cget("text")


def test_change_pw_too_short_shows_error(panel, db):
    panel._new_pw.insert(0, "abc")
    panel._conf_pw.insert(0, "abc")
    panel._change_pw()
    assert "at least 6 characters" in panel._pw_status.cget("text")


def test_change_pw_success_updates_password_and_clears_fields(panel, db):
    panel._new_pw.insert(0, "newpass1")
    panel._conf_pw.insert(0, "newpass1")
    panel._change_pw()
    assert "updated" in panel._pw_status.cget("text")
    assert panel._new_pw.get() == ""
    assert panel._conf_pw.get() == ""
    assert db.check_admin_password("newpass1")
    assert not db.check_admin_password("admin1234")


# ── Bulk member export ─────────────────────────────────────────────────────

def test_set_date_range_fills_member_export_dates(panel):
    panel._set_date_range(6)
    assert panel._export_from.get() != ""
    assert panel._export_to.get() != ""


def test_do_export_invalid_date_shows_error(panel, db):
    panel._export_from.insert(0, "not-a-date")
    panel._export_to.insert(0, "2026-01-01")
    panel._do_export()
    assert "Invalid date format" in panel._export_status.cget("text")


def test_do_export_no_data_shows_message(panel, db, home_dir):
    panel._set_date_range(0)
    panel._do_export()
    assert "No sign-in data found" in panel._export_status.cget("text")


def test_do_export_success_writes_file(panel, db, home_dir):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")
    panel._set_date_range(0)
    panel._do_export()
    assert panel._export_status.cget("text").startswith("✓ Saved:")
    assert any(home_dir.glob("Members_Export_*.xlsx"))


def test_do_export_write_failure_shows_error_status(panel, db, broken_home_dir):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")
    panel._set_date_range(0)
    panel._do_export()
    assert panel._export_status.cget("text").startswith("✗ Export failed:")


# ── Bulk staff export ──────────────────────────────────────────────────────

def test_set_staff_date_range_fills_staff_export_dates(panel):
    panel._set_staff_date_range(13)
    assert panel._staff_export_from.get() != ""
    assert panel._staff_export_to.get() != ""


def test_do_staff_export_invalid_date_shows_error(panel, db):
    panel._staff_export_from.insert(0, "bad")
    panel._staff_export_to.insert(0, "2026-01-01")
    panel._do_staff_export()
    assert "Invalid date format" in panel._staff_export_status.cget("text")


def test_do_staff_export_no_data_shows_message(panel, db, home_dir):
    panel._set_staff_date_range(13)
    panel._do_staff_export()
    assert "No staff sign-in data found" in panel._staff_export_status.cget("text")


def test_do_staff_export_success_writes_file(panel, db, home_dir):
    sid = db.upsert_member(_staff())
    db.record_sign(sid, "IN")
    panel._set_staff_date_range(13)
    panel._do_staff_export()
    assert panel._staff_export_status.cget("text").startswith("✓ Saved:")
    assert any(home_dir.glob("Staff_Export_*.xlsx"))


def test_do_staff_export_write_failure_shows_error_status(panel, db, broken_home_dir):
    sid = db.upsert_member(_staff())
    db.record_sign(sid, "IN")
    panel._set_staff_date_range(13)
    panel._do_staff_export()
    assert panel._staff_export_status.cget("text").startswith("✗ Export failed:")


# ── Single-person export ───────────────────────────────────────────────────

def test_export_single_person_no_records_shows_popup(panel, db, home_dir):
    mid = db.upsert_member(_member(first_name="No", last_name="Records"))
    m = db.get_member(mid)
    panel._export_single_person(m, is_staff=False)
    popups = _toplevels(panel.winfo_toplevel())
    assert len(popups) == 1
    assert "No sign-in records found for No Records" in popups[0]._msg.get("1.0", "end")


def test_export_single_person_member_success(panel, db, home_dir):
    mid = db.upsert_member(_member(first_name="Full", last_name="History"))
    db.record_sign(mid, "IN")
    m = db.get_member(mid)
    panel._export_single_person(m, is_staff=False)
    popups = _toplevels(panel.winfo_toplevel())
    assert len(popups) == 1
    assert "saved to" in popups[0]._msg.get("1.0", "end")
    assert any(home_dir.glob("Full_History_SignIn_History.xlsx"))


def test_export_single_person_write_failure_shows_error_popup(panel, db, broken_home_dir):
    mid = db.upsert_member(_member(first_name="Will", last_name="Fail"))
    db.record_sign(mid, "IN")
    m = db.get_member(mid)
    panel._export_single_person(m, is_staff=False)
    popups = _toplevels(panel.winfo_toplevel())
    assert len(popups) == 1
    assert "Export failed" in popups[0]._msg.get("1.0", "end")


def test_export_single_person_staff_success(panel, db, home_dir):
    sid = db.upsert_member(_staff(first_name="Staff", last_name="Person"))
    db.record_sign(sid, "IN")
    m = db.get_member(sid)
    panel._export_single_person(m, is_staff=True)
    assert any(home_dir.glob("Staff_Person_SignIn_History.xlsx"))


def test_export_single_person_with_date_range_uses_range_filename(panel, db, home_dir):
    mid = db.upsert_member(_member(first_name="Ranged", last_name="Person"))
    db.record_sign(mid, "IN")
    m = db.get_member(mid)
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    panel._export_single_person(m, is_staff=False, date_from=today, date_to=today)
    assert any(home_dir.glob(f"Ranged_Person_SignIn_History_{today}_to_{today}.xlsx"))


def test_prompt_export_dates_opens_dialog(panel, db):
    mid = db.upsert_member(_member())
    m = db.get_member(mid)
    panel._prompt_export_dates(m, is_staff=False)
    popups = _toplevels(panel.winfo_toplevel())
    assert len(popups) == 1


# ── Member management ──────────────────────────────────────────────────────

def test_load_members_list_shows_placeholder_when_empty(panel, db):
    panel._load_members_list("zzz_no_such_member")
    labels = [w.cget("text") for w in panel._members_list_frame.winfo_children()]
    assert "No members found." in labels


def test_load_members_list_shows_matching_members(panel, db):
    db.upsert_member(_member(first_name="Findme", last_name="Member"))
    panel._load_members_list("Findme")
    row = panel._members_list_frame.winfo_children()[0]
    label = row.winfo_children()[0]
    assert label.cget("text") == "Findme Member"


def test_member_search_var_triggers_list_reload(panel, db):
    db.upsert_member(_member(first_name="Traced", last_name="Member"))
    panel._member_search_var.set("Traced")
    labels = [row.winfo_children()[0].cget("text") for row in panel._members_list_frame.winfo_children()]
    assert "Traced Member" in labels


def test_member_row_edit_button_navigates_to_profile(panel, db):
    mid = db.upsert_member(_member(first_name="Edit", last_name="Target"))
    panel._load_members_list("Edit Target")
    row = panel._members_list_frame.winfo_children()[0]
    edit_btn = next(b for b in row.winfo_children() if b.cget("text") == "Edit")
    edit_btn.invoke()
    screen_name, kwargs = panel.app.last_call
    assert screen_name == "profile"
    assert kwargs["member"]["id"] == mid


def test_member_row_export_button_opens_dialog(panel, db):
    db.upsert_member(_member(first_name="Export", last_name="Target"))
    panel._load_members_list("Export Target")
    row = panel._members_list_frame.winfo_children()[0]
    export_btn = next(b for b in row.winfo_children() if b.cget("text") == "Export")
    export_btn.invoke()
    assert len(_toplevels(panel.winfo_toplevel())) == 1


# ── Staff management ────────────────────────────────────────────────────────

def test_load_staff_list_shows_placeholder_when_empty(panel, db):
    panel._load_staff_list("zzz_no_such_staff")
    labels = [w.cget("text") for w in panel._staff_list_frame.winfo_children()]
    assert "No staff members found." in labels


def test_load_staff_list_shows_role(panel, db):
    db.upsert_member(_staff(first_name="Sam", last_name="Taylor", school="Team Leader"))
    panel._load_staff_list("Sam")
    row = panel._staff_list_frame.winfo_children()[0]
    label = row.winfo_children()[0]
    assert label.cget("text") == "Sam Taylor  —  Team Leader"


def test_load_staff_list_without_role_omits_dash(panel, db):
    db.upsert_member(_staff(first_name="NoRole", last_name="Staffer", school=""))
    panel._load_staff_list("NoRole")
    row = panel._staff_list_frame.winfo_children()[0]
    label = row.winfo_children()[0]
    assert label.cget("text") == "NoRole Staffer"


def test_staff_row_edit_button_navigates_to_staff_profile(panel, db):
    sid = db.upsert_member(_staff(first_name="Edit", last_name="Staffer"))
    panel._load_staff_list("Edit Staffer")
    row = panel._staff_list_frame.winfo_children()[0]
    edit_btn = next(b for b in row.winfo_children() if b.cget("text") == "Edit")
    edit_btn.invoke()
    screen_name, kwargs = panel.app.last_call
    assert screen_name == "staff_profile"
    assert kwargs["staff"]["id"] == sid


# ── Run sheet management ────────────────────────────────────────────────────

def test_load_runs_list_shows_placeholder_when_empty(panel, db):
    _clear_seed_runs(db)
    panel._load_runs_list()
    labels = [w.cget("text") for w in panel._runs_list_frame.winfo_children()]
    assert "No run sheets yet." in labels


def test_load_runs_list_shows_pupil_count(panel, db):
    _clear_seed_runs(db)
    mid = db.upsert_member(_member())
    db.upsert_run("Morning Bus", [mid])
    panel._load_runs_list()
    row = panel._runs_list_frame.winfo_children()[0]
    texts = [w.cget("text") for w in row.winfo_children()]
    assert "Morning Bus" in texts
    assert "(1 pupil)" in texts


def test_load_runs_list_pluralizes_pupil_count(panel, db):
    _clear_seed_runs(db)
    mid1 = db.upsert_member(_member(first_name="One"))
    mid2 = db.upsert_member(_member(first_name="Two"))
    db.upsert_run("Bus", [mid1, mid2])
    panel._load_runs_list()
    row = panel._runs_list_frame.winfo_children()[0]
    texts = [w.cget("text") for w in row.winfo_children()]
    assert "(2 pupils)" in texts


def test_load_runs_list_reload_clears_previous_rows(panel, db):
    _clear_seed_runs(db)
    db.upsert_run("Bus", [])
    panel._load_runs_list()
    panel._load_runs_list()
    assert len(panel._runs_list_frame.winfo_children()) == 1


def test_render_pupil_results_marks_already_assigned(panel, db):
    mid = db.upsert_member(_member(first_name="Assigned", last_name="Pupil"))
    m = db.get_member(mid)
    panel._run_member_ids = [mid]
    panel._render_pupil_results([m])
    row = panel._run_pupil_results.winfo_children()[0]
    assert row.winfo_children()[0].cget("text") == "Assigned Pupil ✓"


def test_add_to_run_appends_id_and_clears_search(panel, db):
    mid = db.upsert_member(_member())
    m = db.get_member(mid)
    panel._run_pupil_search_var.set("something")
    panel._add_to_run(m)
    assert panel._run_member_ids == [mid]
    assert panel._run_pupil_search_var.get() == ""


def test_add_to_run_does_not_duplicate(panel, db):
    mid = db.upsert_member(_member())
    m = db.get_member(mid)
    panel._add_to_run(m)
    panel._add_to_run(m)
    assert panel._run_member_ids == [mid]


def test_render_assigned_shows_placeholder_when_empty(panel, db):
    panel._run_member_ids = []
    panel._render_assigned()
    labels = [w.cget("text") for w in panel._run_assigned_frame.winfo_children()]
    assert "No pupils assigned yet." in labels


def test_render_assigned_lists_names(panel, db):
    mid = db.upsert_member(_member(first_name="Assigned", last_name="One"))
    panel._run_member_ids = [mid]
    panel._render_assigned()
    row = panel._run_assigned_frame.winfo_children()[0]
    label = row.winfo_children()[0]
    assert label.cget("text") == "Assigned One"


def test_render_assigned_skips_deleted_member_ids(panel, db):
    """A run sheet can reference a member that's since been deleted; the
    assigned-pupils panel must skip it rather than crash on a None lookup."""
    mid = db.upsert_member(_member())
    db.delete_member(mid)
    panel._run_member_ids = [mid]
    panel._render_assigned()
    assert panel._run_assigned_frame.winfo_children() == []


def test_remove_from_run_removes_id(panel, db):
    mid = db.upsert_member(_member())
    panel._run_member_ids = [mid]
    panel._remove_from_run(mid)
    assert panel._run_member_ids == []


def test_remove_button_in_assigned_list_removes_pupil(panel, db):
    mid = db.upsert_member(_member())
    panel._run_member_ids = [mid]
    panel._render_assigned()
    row = panel._run_assigned_frame.winfo_children()[0]
    remove_btn = next(w for w in row.winfo_children() if _safe_text(w) == "✕")
    remove_btn.invoke()
    assert panel._run_member_ids == []


def test_edit_run_loads_name_and_members(panel, db):
    mid = db.upsert_member(_member())
    run_id = db.upsert_run("Morning Bus", [mid])
    run = {"id": run_id, "name": "Morning Bus"}
    panel._edit_run(run)
    assert panel._editing_run_id == run_id
    assert panel._run_name_entry.get() == "Morning Bus"
    assert panel._run_member_ids == [mid]
    assert "Editing: Morning Bus" in panel._run_editor_title.cget("text")


def test_clear_run_editor_resets_state(panel, db):
    mid = db.upsert_member(_member())
    run_id = db.upsert_run("Morning Bus", [mid])
    panel._edit_run({"id": run_id, "name": "Morning Bus"})
    panel._clear_run_editor()
    assert panel._editing_run_id is None
    assert panel._run_name_entry.get() == ""
    assert panel._run_member_ids == []
    assert panel._run_editor_title.cget("text") == "New Run Sheet"


def test_save_run_requires_name(panel, db):
    mid = db.upsert_member(_member())
    panel._run_member_ids = [mid]
    panel._save_run()
    assert "name is required" in panel._run_status.cget("text")


def test_save_run_requires_at_least_one_pupil(panel, db):
    panel._run_name_entry.insert(0, "Empty Run")
    panel._save_run()
    assert "Assign at least one pupil" in panel._run_status.cget("text")


def test_save_run_creates_run_and_clears_editor(panel, db):
    mid = db.upsert_member(_member())
    panel._run_name_entry.insert(0, "New Run")
    panel._run_member_ids = [mid]
    panel._save_run()
    assert db.search_runs("New Run") != []
    assert panel._run_name_entry.get() == ""


def test_confirm_delete_run_delete_button_removes_run(panel, db):
    run_id = db.upsert_run("Doomed Run", [])
    panel._confirm_delete_run({"id": run_id, "name": "Doomed Run"})
    popup = _toplevels(panel.winfo_toplevel())[0]
    delete_btn = next(b for b in popup._btn_row.winfo_children() if b.cget("text") == "Delete")
    delete_btn.invoke()
    assert db.search_runs("Doomed Run") == []
    assert "Deleted 'Doomed Run'" in panel._run_status.cget("text")


def test_confirm_delete_run_cancel_keeps_run(panel, db):
    run_id = db.upsert_run("Kept Run", [])
    panel._confirm_delete_run({"id": run_id, "name": "Kept Run"})
    popup = _toplevels(panel.winfo_toplevel())[0]
    cancel_btn = next(b for b in popup._btn_row.winfo_children() if b.cget("text") == "Cancel")
    cancel_btn.invoke()
    assert db.search_runs("Kept Run") != []


# ── Alerts ──────────────────────────────────────────────────────────────────

def test_set_alert_scope_all_hides_both_pickers(panel):
    panel._set_alert_scope("all")
    # winfo_manager() reflects pack()/pack_forget() bookkeeping directly, unlike
    # winfo_ismapped() which depends on the widget actually being realised on
    # the display — unreliable under a bare Xvfb server with no window manager.
    assert panel._alert_run_frame.winfo_manager() == ""
    assert panel._alert_member_frame.winfo_manager() == ""


def test_set_alert_scope_run_shows_run_picker(panel, db):
    db.upsert_run("Some Run", [])
    panel._set_alert_scope("run")
    panel.update()
    assert panel._alert_run_frame.winfo_manager() == "pack"
    assert panel._alert_member_frame.winfo_manager() == ""


def test_set_alert_scope_member_shows_member_picker(panel):
    panel._set_alert_scope("member")
    panel.update()
    assert panel._alert_member_frame.winfo_manager() == "pack"
    assert panel._alert_run_frame.winfo_manager() == ""


def test_refresh_alert_run_menu_no_runs(panel, db):
    _clear_seed_runs(db)
    panel._refresh_alert_run_menu()
    assert panel._alert_run_var.get() == "No run sheets yet"


def test_refresh_alert_run_menu_selects_first_run(panel, db):
    _clear_seed_runs(db)
    db.upsert_run("Alpha Run", [])
    db.upsert_run("Beta Run", [])
    panel._refresh_alert_run_menu()
    assert panel._alert_run_var.get() in ("Alpha Run", "Beta Run")
    assert len(panel._alert_runs_cache) == 2


def test_select_alert_member_sets_id_and_label(panel, db):
    mid = db.upsert_member(_member(first_name="Chosen", last_name="One"))
    m = db.get_member(mid)
    panel._select_alert_member(m)
    assert panel._alert_member_id == mid
    assert "Chosen One" in panel._alert_member_selected_lbl.cget("text")


def test_render_alert_member_results_click_selects(panel, db):
    mid = db.upsert_member(_member(first_name="Click", last_name="Target"))
    m = db.get_member(mid)
    panel._set_alert_scope("member")  # maps _alert_member_frame so clicks are delivered
    panel._render_alert_member_results([m])
    panel.update()
    row = panel._alert_member_results.winfo_children()[0]
    row.event_generate("<ButtonPress-1>")
    panel.update()
    assert panel._alert_member_id == mid


def test_save_alert_empty_message_shows_error(panel, db):
    panel._save_alert()
    assert "cannot be empty" in panel._alert_status.cget("text")


def test_save_alert_scope_all_success(panel, db):
    panel._alert_message.insert("1.0", "Centre closed")
    panel._alert_expiry_unit.set("No expiry")
    panel._save_alert()
    assert "created" in panel._alert_status.cget("text")
    assert any(a["message"] == "Centre closed" for a in db.get_alerts())


def test_save_alert_scope_run_without_selection_when_no_runs_shows_error(panel, db):
    _clear_seed_runs(db)
    panel._set_alert_scope("run")  # no runs exist -> var becomes "No run sheets yet"
    panel._alert_message.insert("1.0", "Run alert")
    panel._save_alert()
    assert "Select a run sheet" in panel._alert_status.cget("text")


def test_save_alert_scope_run_success(panel, db):
    _clear_seed_runs(db)
    run_id = db.upsert_run("Target Run", [])
    panel._set_alert_scope("run")
    panel._alert_message.insert("1.0", "Run alert")
    panel._save_alert()
    assert any(a["scope"] == "run" and a["target_id"] == run_id for a in db.get_alerts())


def test_save_alert_scope_member_without_selection_shows_error(panel, db):
    panel._set_alert_scope("member")
    panel._alert_message.insert("1.0", "Member alert")
    panel._save_alert()
    assert "Search and select a person" in panel._alert_status.cget("text")


def test_save_alert_scope_member_success(panel, db):
    mid = db.upsert_member(_member())
    m = db.get_member(mid)
    panel._set_alert_scope("member")
    panel._select_alert_member(m)
    panel._alert_message.insert("1.0", "Member alert")
    panel._save_alert()
    assert any(a["scope"] == "member" and a["target_id"] == mid for a in db.get_alerts())


def test_save_alert_with_expiry_sets_expiry(panel, db):
    panel._alert_message.insert("1.0", "Expiring alert")
    panel._alert_expiry_unit.set("Days")
    panel._alert_expiry_amount_var.set("1")
    panel._save_alert()
    alert = next(a for a in db.get_alerts() if a["message"] == "Expiring alert")
    assert alert["expires_at"] is not None


def test_save_alert_invalid_expiry_amount_shows_error(panel, db):
    panel._alert_message.insert("1.0", "Bad duration")
    panel._alert_expiry_unit.set("Days")
    panel._alert_expiry_amount_var.set("0")
    panel._save_alert()
    assert "Enter a valid duration" in panel._alert_status.cget("text")


def test_save_alert_non_numeric_expiry_amount_shows_error(panel, db):
    panel._alert_message.insert("1.0", "Bad duration")
    panel._alert_expiry_unit.set("Days")
    panel._alert_expiry_amount_var.set("not-a-number")
    panel._save_alert()
    assert "Enter a valid duration" in panel._alert_status.cget("text")


def test_save_alert_clears_form_on_success(panel, db):
    mid = db.upsert_member(_member())
    m = db.get_member(mid)
    panel._set_alert_scope("member")
    panel._select_alert_member(m)
    panel._alert_message.insert("1.0", "Some message")
    panel._save_alert()
    assert panel._alert_message.get("1.0", "end").strip() == ""
    assert panel._alert_member_id is None
    assert panel._alert_member_selected_lbl.cget("text") == "No one selected."


def test_describe_alert_target_all(panel, db):
    assert panel._describe_alert_target({"scope": "all"}) == "ALL MEMBERS"


def test_describe_alert_target_run(panel, db):
    run_id = db.upsert_run("Named Run", [])
    assert panel._describe_alert_target({"scope": "run", "target_id": run_id}) == "RUN: Named Run"


def test_describe_alert_target_deleted_run(panel, db):
    assert panel._describe_alert_target({"scope": "run", "target_id": 999999}) == "RUN: (deleted)"


def test_describe_alert_target_member(panel, db):
    mid = db.upsert_member(_member(first_name="Named", last_name="Person"))
    assert panel._describe_alert_target({"scope": "member", "target_id": mid}) == "PERSON: Named Person"


def test_describe_alert_target_deleted_member(panel, db):
    assert panel._describe_alert_target({"scope": "member", "target_id": 999999}) == "PERSON: (deleted)"


def test_load_alerts_list_shows_placeholder_when_empty(panel, db):
    panel._load_alerts_list()
    labels = [w.cget("text") for w in panel._alerts_list_frame.winfo_children()]
    assert "No active alerts." in labels


def test_load_alerts_list_shows_alert_message(panel, db):
    db.create_alert("all", None, "Test alert message")
    panel._load_alerts_list()
    all_texts = []
    for row in panel._alerts_list_frame.winfo_children():
        for w in getattr(row, "winfo_children", lambda: [])():
            try:
                all_texts.append(w.cget("text"))
            except Exception:
                pass
    assert "Test alert message" in all_texts


def test_delete_alert_removes_it_and_reloads_list(panel, db):
    alert_id = db.create_alert("all", None, "To delete")
    panel._delete_alert({"id": alert_id})
    assert not any(a["id"] == alert_id for a in db.get_alerts())


def test_delete_alert_button_in_list_removes_alert(panel, db):
    db.create_alert("all", None, "Delete via button")
    panel._load_alerts_list()
    row = panel._alerts_list_frame.winfo_children()[0]
    delete_btn = next(w for w in row.winfo_children() if hasattr(w, "cget")
                        and _safe_text(w) == "Delete Alert")
    delete_btn.invoke()
    assert db.get_alerts() == []


def _safe_text(w):
    try:
        return w.cget("text")
    except Exception:
        return None


# ── Lifecycle ────────────────────────────────────────────────────────────────

def test_on_show_resets_run_editor(panel, db):
    mid = db.upsert_member(_member())
    panel._run_member_ids = [mid]
    panel._editing_run_id = 123
    panel.on_show()
    assert panel._run_member_ids == []
    assert panel._editing_run_id is None


def test_on_show_clears_search_fields(panel, db):
    panel._member_search_var.set("leftover")
    panel._staff_search_var.set("leftover")
    panel.on_show()
    assert panel._member_search_var.get() == ""
    assert panel._staff_search_var.get() == ""


def test_on_show_sets_default_export_ranges(panel, db):
    panel.on_show()
    assert panel._export_from.get() == panel._export_to.get()  # "today" range
    assert panel._staff_export_from.get() != panel._staff_export_to.get()  # 14-day range


def test_on_show_resets_alert_form(panel, db):
    panel._alert_message.insert("1.0", "leftover")
    panel._alert_member_id = 42
    panel.on_show()
    assert panel._alert_message.get("1.0", "end").strip() == ""
    assert panel._alert_member_id is None
    assert panel._alert_scope.get() == "all"


# ── Navigation ───────────────────────────────────────────────────────────────

def test_back_button_navigates_to_options(panel):
    bar = panel.winfo_children()[0]
    back_btn = next(w for w in bar.winfo_children() if w.cget("text") == "← Back")
    back_btn.invoke()
    assert panel.app.last_call == ("options", {})
