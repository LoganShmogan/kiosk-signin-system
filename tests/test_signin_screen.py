"""
Tests for screens/signin_screen.py — member search, selection, and the
alert-aware "Enter" flow into the signature screen.
"""
import pytest
from helpers import FakeApp, member as _member


@pytest.fixture
def screen(tk_root, db):
    from screens.signin_screen import SignInScreen
    s = SignInScreen(tk_root, FakeApp())
    s.pack()
    tk_root.update()
    return s


def _toplevels(root):
    return [w for w in root.winfo_children() if isinstance(w, __import__("tkinter").Toplevel)]


def _m(mid, first, last):
    return {"id": mid, "first_name": first, "last_name": last}


# ── Filtering ─────────────────────────────────────────────────────────────────

def test_get_filtered_empty_query_returns_all_sorted(screen):
    screen._all_members = [_m(1, "Bob", "Zeta"), _m(2, "Amy", "Alpha")]
    screen._search_var.set("")
    result = screen._get_filtered()
    assert [m["id"] for m in result] == [2, 1]


def test_get_filtered_matches_last_name_prefix(screen):
    screen._all_members = [_m(1, "Amy", "Smith"), _m(2, "Bob", "Jones")]
    screen._search_var.set("smi")
    assert [m["id"] for m in screen._get_filtered()] == [1]


def test_get_filtered_matches_first_name_prefix(screen):
    screen._all_members = [_m(1, "Amy", "Smith"), _m(2, "Bob", "Jones")]
    screen._search_var.set("bo")
    assert [m["id"] for m in screen._get_filtered()] == [2]


def test_get_filtered_matches_substring_of_full_name(screen):
    screen._all_members = [_m(1, "Amy", "Smith")]
    screen._search_var.set("y sm")
    assert [m["id"] for m in screen._get_filtered()] == [1]


def test_get_filtered_is_case_insensitive(screen):
    screen._all_members = [_m(1, "Amy", "Smith")]
    screen._search_var.set("AMY")
    assert [m["id"] for m in screen._get_filtered()] == [1]


def test_get_filtered_no_match_returns_empty(screen):
    screen._all_members = [_m(1, "Amy", "Smith")]
    screen._search_var.set("zzz")
    assert screen._get_filtered() == []


# ── Selection ──────────────────────────────────────────────────────────────────

def test_add_member_appends_and_sorts(screen):
    screen._add_member(_m(1, "Bob", "Zeta"))
    screen._add_member(_m(2, "Amy", "Alpha"))
    assert [m["id"] for m in screen._selected] == [2, 1]


def test_add_member_ignores_duplicate(screen):
    screen._add_member(_m(1, "Amy", "Smith"))
    screen._add_member(_m(1, "Amy", "Smith"))
    assert len(screen._selected) == 1


def test_remove_member_by_id(screen):
    screen._add_member(_m(1, "Amy", "Smith"))
    screen._add_member(_m(2, "Bob", "Jones"))
    screen._remove_member(1)
    assert [m["id"] for m in screen._selected] == [2]


def test_add_member_clears_search_text(screen):
    screen._search_var.set("smi")
    screen._add_member(_m(1, "Amy", "Smith"))
    assert screen._search_var.get() == ""


def test_add_member_refocuses_search_entry(screen, monkeypatch):
    """Refocusing the entry (rather than letting it blur) is what keeps the
    virtual keyboard attached after a selection — see app.py's FocusIn/
    FocusOut handlers. Asserted by patching focus_set() rather than checking
    real OS-level focus_get(), since the latter depends on a window manager
    granting the toplevel input focus — not guaranteed under a headless
    Xvfb display with no window manager (e.g. CI)."""
    calls = []
    monkeypatch.setattr(screen._search_entry, "focus_set", lambda: calls.append(True))
    screen._add_member(_m(1, "Amy", "Smith"))
    assert calls == [True]


def test_render_selected_shows_names(screen):
    screen._add_member(_m(1, "Amy", "Smith"))
    labels = []
    for row in screen._sel_frame.winfo_children():
        for w in row.winfo_children() if hasattr(row, "winfo_children") else []:
            try:
                labels.append(w.cget("text"))
            except Exception:
                pass
    assert "Amy Smith" in labels


def test_remove_button_in_selected_list_removes_member(screen):
    screen._add_member(_m(1, "Amy", "Smith"))
    row = screen._sel_frame.winfo_children()[0]
    remove_btn = next(w for w in row.winfo_children() if isinstance(w, __import__("tkinter").Button))
    remove_btn.invoke()
    assert screen._selected == []


# ── Dropdown population ───────────────────────────────────────────────────────

def test_populate_dropdown_shows_no_members_found_when_empty(screen):
    screen._populate_dropdown([])
    labels = [w.cget("text") for w in screen._dropdown_frame.winfo_children()]
    assert labels == ["No members found."]


def test_populate_dropdown_marks_already_selected_with_checkmark(screen):
    m1 = _m(1, "Amy", "Smith")
    screen._add_member(m1)
    screen._populate_dropdown([m1])
    row = screen._dropdown_frame.winfo_children()[0]
    label = row.winfo_children()[0]
    assert label.cget("text") == "Amy Smith ✓"


def test_populate_dropdown_clicking_unselected_row_adds_member(screen):
    m1 = _m(1, "Amy", "Smith")
    screen._all_members = [m1]
    screen._show_dropdown()  # places the dropdown so synthetic events are delivered
    screen.update()
    row = screen._dropdown_frame.winfo_children()[0]
    row.event_generate("<ButtonPress-1>")
    screen.update()
    assert any(m["id"] == 1 for m in screen._selected)


# ── Dropdown show/hide ─────────────────────────────────────────────────────────

def test_show_dropdown_sets_open_flag(screen):
    screen._show_dropdown()
    assert screen._dropdown_open is True


def test_hide_dropdown_clears_open_flag(screen):
    screen._show_dropdown()
    screen._hide_dropdown()
    assert screen._dropdown_open is False


def test_entry_focus_shows_dropdown(screen):
    screen._on_entry_focus(None)
    assert screen._dropdown_open is True


def test_entry_focus_cancels_pending_hide(screen):
    screen._on_entry_blur(None)
    assert screen._hide_after is not None
    screen._on_entry_focus(None)
    assert screen._hide_after is None


def test_entry_blur_schedules_hide(screen):
    screen._show_dropdown()
    screen._on_entry_blur(None)
    assert screen._hide_after is not None
    # Run the scheduled callback directly rather than waiting out the real delay.
    screen._hide_dropdown()
    assert screen._dropdown_open is False


def test_do_search_opens_dropdown_when_closed(screen):
    screen._all_members = [_m(1, "Amy", "Smith")]
    assert screen._dropdown_open is False
    screen._do_search()
    assert screen._dropdown_open is True


def test_do_search_repopulates_when_already_open(screen):
    screen._all_members = [_m(1, "Amy", "Smith"), _m(2, "Bob", "Jones")]
    screen._show_dropdown()
    screen._search_var.set("bob")
    screen._do_search()
    labels = [row.winfo_children()[0].cget("text") for row in screen._dropdown_frame.winfo_children()]
    assert labels == ["Bob Jones"]


def test_remove_member_repopulates_open_dropdown(screen):
    m1 = _m(1, "Amy", "Smith")
    screen._all_members = [m1]
    screen._add_member(m1)
    screen._show_dropdown()
    screen._remove_member(1)
    # The checkmark should be gone now that the member was removed while open.
    row = screen._dropdown_frame.winfo_children()[0]
    label = row.winfo_children()[0]
    assert label.cget("text") == "Amy Smith"


# ── Enter / alerts ─────────────────────────────────────────────────────────────

def test_on_enter_with_no_selection_does_nothing(screen):
    screen._selected = []
    screen._on_enter()
    assert screen.app.calls == []


def test_on_enter_without_alerts_navigates_to_signature(screen, db):
    mid = db.upsert_member(_member())
    m = db.get_member(mid)
    screen._selected = [m]
    screen._on_enter()
    assert screen.app.last_call == ("signature", {"members": [m]})


def test_on_enter_with_alert_shows_popup_instead_of_navigating(screen, db):
    mid = db.upsert_member(_member())
    m = db.get_member(mid)
    db.create_alert("member", mid, "Heads up about this pupil")
    screen._selected = [m]
    screen._on_enter()

    assert screen.app.calls == []
    popups = _toplevels(screen.winfo_toplevel())
    assert len(popups) == 1
    assert "Heads up about this pupil" in popups[0]._msg.get("1.0", "end")


def test_dismissing_alert_popup_navigates_to_signature(screen, db):
    mid = db.upsert_member(_member())
    m = db.get_member(mid)
    db.create_alert("all", None, "Centre-wide notice")
    screen._selected = [m]
    screen._on_enter()

    popup = _toplevels(screen.winfo_toplevel())[0]
    popup._btn_row.winfo_children()[0].invoke()
    assert screen.app.last_call == ("signature", {"members": [m]})


def test_on_enter_alert_for_other_member_does_not_block(screen, db):
    mid1 = db.upsert_member(_member(first_name="One"))
    mid2 = db.upsert_member(_member(first_name="Two"))
    db.create_alert("member", mid2, "Only for Two")
    m1 = db.get_member(mid1)
    screen._selected = [m1]
    screen._on_enter()
    assert screen.app.last_call == ("signature", {"members": [m1]})


# ── Lifecycle ─────────────────────────────────────────────────────────────────

def test_on_show_resets_selection_and_loads_members(screen, db):
    mid = db.upsert_member(_member())
    screen._selected = [{"id": 999, "first_name": "Stale", "last_name": "Data"}]
    screen.on_show()
    assert screen._selected == []
    assert any(m["id"] == mid for m in screen._all_members)


def test_on_show_clears_search_text(screen, db):
    screen._search_var.set("leftover")
    screen.on_show()
    assert screen._search_var.get() == ""


def test_on_show_hides_dropdown(screen, db):
    screen._show_dropdown()
    screen.on_show()
    assert screen._dropdown_open is False


# ── Navigation ────────────────────────────────────────────────────────────────

def test_back_button_navigates_to_options(screen):
    back_btn = next(
        w for w in screen._left.winfo_children()
        if isinstance(w, __import__("tkinter").Button) and w.cget("text") == "Back"
    )
    back_btn.invoke()
    assert screen.app.last_call == ("options", {})
