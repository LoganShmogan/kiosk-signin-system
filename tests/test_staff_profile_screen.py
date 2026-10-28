"""
Tests for screens/staff_profile_screen.py — kiosk-side staff create/edit/
delete form.
"""
import pytest
from helpers import FakeApp, staff_member as _staff


@pytest.fixture
def screen(tk_root, db):
    from screens.staff_profile_screen import StaffProfileScreen
    s = StaffProfileScreen(tk_root, FakeApp())
    s.pack()
    tk_root.update()
    return s


def _toplevels(root):
    return [w for w in root.winfo_children() if isinstance(w, __import__("tkinter").Toplevel)]


# ── on_show / populate ────────────────────────────────────────────────────────

def test_on_show_new_staff_sets_title_and_hides_delete(screen):
    screen.on_show(staff=None)
    assert screen._title_lbl.cget("text") == "New Staff Member"
    # winfo_manager() reflects pack()/pack_forget() bookkeeping directly, unlike
    # winfo_ismapped() which depends on the widget actually being realised on
    # the display — unreliable under a bare Xvfb server with no window manager.
    assert screen._delete_btn.winfo_manager() == ""


def test_on_show_existing_staff_sets_title_and_shows_delete(screen, tk_root, db):
    sid = db.upsert_member(_staff())
    m = db.get_member(sid)
    screen.on_show(staff=m)
    tk_root.update()
    assert screen._title_lbl.cget("text") == "Edit Staff Member"
    assert screen._delete_btn.winfo_manager() == "pack"


def test_on_show_populates_fields_from_staff(screen, db):
    sid = db.upsert_member(_staff(first_name="Sam", last_name="Taylor",
                                   school="Team Leader", pin="4321"))
    m = db.get_member(sid)
    screen.on_show(staff=m)
    assert screen._fields["first_name"].get_value() == "Sam"
    assert screen._fields["last_name"].get_value() == "Taylor"
    assert screen._fields["school"].get_value() == "Team Leader"
    assert screen._fields["pin"].get_value() == "4321"


def test_populate_signature_shows_placeholder_when_none(screen, db):
    sid = db.upsert_member(_staff())
    m = db.get_member(sid)
    screen.on_show(staff=m)
    labels = [w.cget("text") for w in screen._sig_frame.winfo_children()]
    assert "No signature on file yet." in labels


def test_populate_signature_renders_image_when_present(screen, db):
    sid = db.upsert_member(_staff())
    db.record_sign(sid, "IN", signature=b"[(0, 0, 10, 10), (10, 10, 20, 0)]")
    m = db.get_member(sid)
    screen.on_show(staff=m)
    widget_types = [type(w).__name__ for w in screen._sig_frame.winfo_children()]
    assert "Label" in widget_types  # the image label


def test_populate_signature_falls_back_on_garbage_signature(screen, db):
    sid = db.upsert_member(_staff())
    db.record_sign(sid, "IN", signature=b"not parseable")
    m = db.get_member(sid)
    screen.on_show(staff=m)
    labels = [w.cget("text") for w in screen._sig_frame.winfo_children()]
    assert "No signature on file yet." in labels


def test_populate_signature_destroys_previous_content_on_refresh(screen, db):
    """A second on_show (e.g. re-opening the profile) must clear out the
    previous placeholder/image before rendering the new state."""
    sid = db.upsert_member(_staff())
    m = db.get_member(sid)
    screen.on_show(staff=m)  # first populate -> placeholder label
    assert screen._sig_frame.winfo_children()
    screen.on_show(staff=m)  # second populate -> must destroy prior children
    labels = [w.cget("text") for w in screen._sig_frame.winfo_children()]
    assert "No signature on file yet." in labels


# ── Save ──────────────────────────────────────────────────────────────────────

def test_save_new_staff_creates_record(screen, db):
    screen.on_show(staff=None)
    screen._fields["first_name"].set_value("New")
    screen._fields["last_name"].set_value("Staffer")
    screen._fields["school"].set_value("Coordinator")
    screen._save()

    results = db.search_members("New Staffer", "staff")
    assert len(results) == 1
    assert results[0]["school"] == "Coordinator"


def test_save_sets_person_type_staff(screen, db):
    screen.on_show(staff=None)
    screen._fields["first_name"].set_value("New")
    screen._fields["last_name"].set_value("Staffer")
    screen._save()
    results = db.search_members("New Staffer", "staff")
    assert results[0]["person_type"] == "staff"


def test_save_updates_existing_staff(screen, db):
    sid = db.upsert_member(_staff(first_name="Old", last_name="Name"))
    m = db.get_member(sid)
    screen.on_show(staff=m)
    screen._fields["first_name"].set_value("Updated")
    screen._save()
    assert db.get_member(sid)["first_name"] == "Updated"


def test_save_shows_success_popup(screen, db):
    screen.on_show(staff=None)
    screen._fields["first_name"].set_value("New")
    screen._fields["last_name"].set_value("Staffer")
    screen._save()
    popups = _toplevels(screen.winfo_toplevel())
    assert len(popups) == 1
    assert "saved successfully" in popups[0]._msg.get("1.0", "end")


def test_save_missing_first_name_shows_error_and_does_not_save(screen, db):
    screen.on_show(staff=None)
    screen._fields["last_name"].set_value("OnlyLast")
    screen._save()
    assert db.search_members("OnlyLast", "staff") == []
    popups = _toplevels(screen.winfo_toplevel())
    assert "required" in popups[0]._msg.get("1.0", "end")


def test_save_missing_last_name_shows_error(screen, db):
    screen.on_show(staff=None)
    screen._fields["first_name"].set_value("OnlyFirst")
    screen._save()
    assert db.search_members("OnlyFirst", "staff") == []


def test_save_back_to_menu_button_navigates_to_admin_panel(screen, db):
    screen.on_show(staff=None)
    screen._fields["first_name"].set_value("New")
    screen._fields["last_name"].set_value("Staffer")
    screen._save()
    popup = _toplevels(screen.winfo_toplevel())[0]
    back_btn = next(b for b in popup._btn_row.winfo_children() if b.cget("text") == "Back to Menu")
    back_btn.invoke()
    assert screen.app.last_call == ("admin_panel", {})


# ── Delete ────────────────────────────────────────────────────────────────────

def test_confirm_delete_with_no_staff_does_nothing(screen):
    screen.staff = None
    screen._confirm_delete()
    assert _toplevels(screen.winfo_toplevel()) == []


def test_confirm_delete_shows_confirmation_popup(screen, db):
    sid = db.upsert_member(_staff(first_name="Delete", last_name="Me"))
    screen.staff = db.get_member(sid)
    screen._confirm_delete()
    popups = _toplevels(screen.winfo_toplevel())
    assert len(popups) == 1
    assert "Delete Me" in popups[0]._msg.get("1.0", "end")


def test_confirm_delete_cancel_does_not_delete(screen, db):
    sid = db.upsert_member(_staff())
    screen.staff = db.get_member(sid)
    screen._confirm_delete()
    popup = _toplevels(screen.winfo_toplevel())[0]
    cancel_btn = next(b for b in popup._btn_row.winfo_children() if b.cget("text") == "Cancel")
    cancel_btn.invoke()
    assert db.get_member(sid) is not None


def test_confirm_delete_delete_button_removes_staff_and_navigates(screen, db):
    sid = db.upsert_member(_staff())
    screen.staff = db.get_member(sid)
    screen._confirm_delete()
    popup = _toplevels(screen.winfo_toplevel())[0]
    delete_btn = next(b for b in popup._btn_row.winfo_children() if b.cget("text") == "Delete")
    delete_btn.invoke()
    assert db.get_member(sid) is None
    assert screen.app.last_call == ("admin_panel", {})


# ── Navigation ────────────────────────────────────────────────────────────────

def test_go_back_navigates_to_admin_panel(screen):
    screen._go_back()
    assert screen.app.last_call == ("admin_panel", {})


def test_back_button_in_bar_navigates_to_admin_panel(screen):
    bar = screen.winfo_children()[0]
    back_btn = next(w for w in bar.winfo_children() if w.cget("text") == "← Back")
    back_btn.invoke()
    assert screen.app.last_call == ("admin_panel", {})
