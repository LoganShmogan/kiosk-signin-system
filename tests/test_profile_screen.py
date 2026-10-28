"""
Tests for screens/profile_screen.py — kiosk-side member create/edit/delete
form, including caregiver details, day pickers, and yes/no toggles.
"""
import pytest
from helpers import FakeApp, member as _member, caregiver as _caregiver


@pytest.fixture
def screen(tk_root, db):
    from screens.profile_screen import ProfileScreen
    s = ProfileScreen(tk_root, FakeApp())
    s.pack()
    tk_root.update()
    return s


def _toplevels(root):
    return [w for w in root.winfo_children() if isinstance(w, __import__("tkinter").Toplevel)]


# ── Populate ──────────────────────────────────────────────────────────────────

def test_populate_fills_member_fields(screen, db):
    mid = db.upsert_member(_member(first_name="Jess", last_name="Allen", school="Central School"))
    m = db.get_member(mid)
    screen.on_show(member=m)
    assert screen._fields["first_name"].get_value() == "Jess"
    assert screen._fields["last_name"].get_value() == "Allen"
    assert screen._fields["school"].get_value() == "Central School"


def test_populate_fills_day_pickers(screen, db):
    mid = db.upsert_member(_member(mornings_days="Mon,Wed", afternoons_days="Tue,Thu"))
    m = db.get_member(mid)
    screen.on_show(member=m)
    assert screen._day_pickers["mornings_days"].get_value() == "Mon,Wed"
    assert screen._day_pickers["afternoons_days"].get_value() == "Tue,Thu"


def test_populate_fills_bool_vars(screen, db):
    mid = db.upsert_member(_member(needs_pickup=1, transport_required=0))
    m = db.get_member(mid)
    screen.on_show(member=m)
    assert screen._bool_vars["needs_pickup"].get() == 1
    assert screen._bool_vars["transport_required"].get() == 0


def test_populate_fills_activity_address_multiline(screen, db):
    mid = db.upsert_member(_member(activity_address="123 Field Rd"))
    m = db.get_member(mid)
    screen.on_show(member=m)
    assert screen._fields["activity_address"].get("1.0", "end").strip() == "123 Field Rd"


def test_populate_fills_caregiver_fields(screen, db):
    mid = db.upsert_member(_member())
    db.upsert_caregiver(_caregiver(mid, full_name="Parent One", phone="0211234"))
    m = db.get_member(mid)
    screen.on_show(member=m)
    assert screen._cg_fields["full_name"].get_value() == "Parent One"
    assert screen._cg_fields["phone"].get_value() == "0211234"


def test_populate_sets_notify_var_from_caregiver(screen, db):
    mid = db.upsert_member(_member())
    db.upsert_caregiver(_caregiver(mid, notify_on="IN"))
    m = db.get_member(mid)
    screen.on_show(member=m)
    assert screen._notify_var.get() == "IN"


def test_populate_new_member_defaults_notify_both(screen, db):
    screen.on_show(member=None)
    assert screen._notify_var.get() == "BOTH"


def test_populate_signature_shows_placeholder_when_none(screen, db):
    mid = db.upsert_member(_member())
    m = db.get_member(mid)
    screen.on_show(member=m)
    labels = [w.cget("text") for w in screen._sig_frame.winfo_children()]
    assert "No signature on file yet." in labels


def test_populate_signature_renders_image_when_present(screen, db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN", signature=b"[(0, 0, 10, 10), (10, 10, 20, 0)]")
    m = db.get_member(mid)
    screen.on_show(member=m)
    widget_types = [type(w).__name__ for w in screen._sig_frame.winfo_children()]
    assert "Label" in widget_types


def test_populate_signature_falls_back_on_garbage_signature(screen, db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN", signature=b"not parseable")
    m = db.get_member(mid)
    screen.on_show(member=m)
    labels = [w.cget("text") for w in screen._sig_frame.winfo_children()]
    assert "No signature on file yet." in labels


def test_populate_signature_destroys_previous_content_on_refresh(screen, db):
    """A second on_show (e.g. re-opening the profile) must clear out the
    previous placeholder/image before rendering the new state."""
    mid = db.upsert_member(_member())
    m = db.get_member(mid)
    screen.on_show(member=m)  # first populate -> placeholder label
    assert screen._sig_frame.winfo_children()
    screen.on_show(member=m)  # second populate -> must destroy prior children
    labels = [w.cget("text") for w in screen._sig_frame.winfo_children()]
    assert "No signature on file yet." in labels


def test_populate_skips_missing_field_widget(screen, db):
    """_set()'s internal helper must no-op (not raise) when a field key has
    no corresponding widget, rather than assuming every key is present."""
    mid = db.upsert_member(_member(first_name="Jess", last_name="Allen"))
    m = db.get_member(mid)
    del screen._fields["first_name"]
    screen.on_show(member=m)  # must not raise
    assert "first_name" not in screen._fields
    assert screen._fields["last_name"].get_value() == "Allen"


# ── Yes/No and notify toggles ─────────────────────────────────────────────────

def _find_yes_no_rows(widget):
    """Depth-first search for every Frame whose direct children are exactly
    the "No"/"Yes" toggle buttons built by _yes_no_row."""
    import tkinter as tk
    rows = []
    for child in widget.winfo_children():
        if isinstance(child, tk.Frame):
            kids = child.winfo_children()
            if len(kids) == 2:
                try:
                    if [k.cget("text") for k in kids] == ["No", "Yes"]:
                        rows.append(child)
                except Exception:
                    pass
        rows.extend(_find_yes_no_rows(child))
    return rows


def test_yes_no_row_click_yes_updates_var_and_color(screen):
    # needs_pickup's row is built before transport_required's, so it's first.
    row = _find_yes_no_rows(screen)[0]
    no_btn, yes_btn = row.winfo_children()
    yes_btn.invoke()
    assert screen._bool_vars["needs_pickup"].get() == 1
    assert yes_btn.cget("bg") == "#27ae60"  # BTN_SUCCESS_BG
    assert no_btn.cget("bg") == "#E0DCF0"   # DAY_OFF_BG (unselected)


def test_yes_no_row_click_no_resets_var(screen):
    row = _find_yes_no_rows(screen)[0]
    no_btn, yes_btn = row.winfo_children()
    yes_btn.invoke()
    no_btn.invoke()
    assert screen._bool_vars["needs_pickup"].get() == 0


def test_refresh_notify_highlights_selected_option(screen):
    screen._notify_var.set("OUT")
    screen._refresh_notify()
    options = ["NONE", "IN", "OUT", "BOTH"]
    children = screen._notify_frame.winfo_children()
    idx = options.index("OUT")
    assert children[idx].cget("bg") == "#c98330"  # BTN_ORANGE_BG
    assert children[idx].cget("fg") == "white"
    # A non-selected option falls back to the unselected colours.
    other = children[options.index("NONE")]
    assert other.cget("bg") == "#E0DCF0"  # DAY_OFF_BG


def test_notify_button_click_updates_var(screen):
    children = screen._notify_frame.winfo_children()
    options = ["NONE", "IN", "OUT", "BOTH"]
    in_btn = children[options.index("IN")]
    in_btn.invoke()
    assert screen._notify_var.get() == "IN"


# ── Save ──────────────────────────────────────────────────────────────────────

def test_save_new_member_creates_record(screen, db):
    screen.on_show(member=None)
    screen._fields["first_name"].set_value("New")
    screen._fields["last_name"].set_value("Child")
    screen._save()
    results = db.search_members("New Child", "member")
    assert len(results) == 1


def test_save_creates_caregiver_record(screen, db):
    screen.on_show(member=None)
    screen._fields["first_name"].set_value("New")
    screen._fields["last_name"].set_value("Child")
    screen._cg_fields["full_name"].set_value("Caregiver Name")
    screen._save()
    mid = db.search_members("New Child", "member")[0]["id"]
    cg = db.get_caregiver(mid)
    assert cg["full_name"] == "Caregiver Name"


def test_save_stores_day_pickers_and_bool_vars(screen, db):
    screen.on_show(member=None)
    screen._fields["first_name"].set_value("Day")
    screen._fields["last_name"].set_value("Picker")
    screen._day_pickers["mornings_days"].set_value("Mon,Fri")
    screen._bool_vars["needs_pickup"].set(1)
    screen._save()
    m = db.search_members("Day Picker", "member")[0]
    assert m["mornings_days"] == "Mon,Fri"
    assert m["needs_pickup"] == 1


def test_save_updates_existing_member(screen, db):
    mid = db.upsert_member(_member(first_name="Old", last_name="Name"))
    m = db.get_member(mid)
    screen.on_show(member=m)
    screen._fields["first_name"].set_value("Updated")
    screen._save()
    assert db.get_member(mid)["first_name"] == "Updated"


def test_save_missing_first_name_shows_error_and_does_not_save(screen, db):
    screen.on_show(member=None)
    screen._fields["last_name"].set_value("OnlyLast")
    screen._save()
    assert db.search_members("OnlyLast", "member") == []
    popups = _toplevels(screen.winfo_toplevel())
    assert "required" in popups[0]._msg.get("1.0", "end")


def test_save_shows_success_popup(screen, db):
    screen.on_show(member=None)
    screen._fields["first_name"].set_value("New")
    screen._fields["last_name"].set_value("Child")
    screen._save()
    popups = _toplevels(screen.winfo_toplevel())
    assert len(popups) == 1
    assert "saved successfully" in popups[0]._msg.get("1.0", "end")


def test_save_error_back_to_menu_navigates(screen, db):
    screen.on_show(member=None)
    screen._save()  # no names -> error popup
    popup = _toplevels(screen.winfo_toplevel())[0]
    back_btn = next(b for b in popup._btn_row.winfo_children() if b.cget("text") == "Back to Menu")
    back_btn.invoke()
    assert screen.app.last_call == ("admin_panel", {})


# ── Delete ────────────────────────────────────────────────────────────────────

def test_confirm_delete_with_no_member_does_nothing(screen):
    screen.member = None
    screen._confirm_delete()
    assert _toplevels(screen.winfo_toplevel()) == []


def test_confirm_delete_delete_button_removes_member(screen, db):
    mid = db.upsert_member(_member(first_name="Delete", last_name="Me"))
    screen.member = db.get_member(mid)
    screen._confirm_delete()
    popup = _toplevels(screen.winfo_toplevel())[0]
    delete_btn = next(b for b in popup._btn_row.winfo_children() if b.cget("text") == "Delete")
    delete_btn.invoke()
    assert db.get_member(mid) is None
    assert screen.app.last_call == ("admin_panel", {})


def test_confirm_delete_cancel_does_not_delete(screen, db):
    mid = db.upsert_member(_member())
    screen.member = db.get_member(mid)
    screen._confirm_delete()
    popup = _toplevels(screen.winfo_toplevel())[0]
    cancel_btn = next(b for b in popup._btn_row.winfo_children() if b.cget("text") == "Cancel")
    cancel_btn.invoke()
    assert db.get_member(mid) is not None


def test_get_returns_empty_string_for_missing_field_key(screen):
    assert screen._get(screen._fields, "does_not_exist") == ""


def test_get_returns_empty_string_for_unsupported_widget_type(screen, tk_root):
    import tkinter as tk
    screen._fields["_dummy"] = tk.Label(tk_root, text="x")
    assert screen._get(screen._fields, "_dummy") == ""


# ── Navigation ────────────────────────────────────────────────────────────────

def test_go_back_navigates_to_admin_panel(screen):
    screen._go_back()
    assert screen.app.last_call == ("admin_panel", {})
