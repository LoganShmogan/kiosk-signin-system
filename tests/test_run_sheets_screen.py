"""
Tests for screens/run_sheets_screen.py — run sheet search/load, the
already-signed-in filter, ad-hoc "add another" pupil search, and the
selected-pupil list feeding into the signature screen.
"""
import pytest
from helpers import FakeApp, member as _member


@pytest.fixture
def screen(tk_root, db):
    from screens.run_sheets_screen import RunSheetsScreen
    s = RunSheetsScreen(tk_root, FakeApp())
    s.pack()
    tk_root.update()
    return s


def _toplevels(root):
    return [w for w in root.winfo_children() if isinstance(w, __import__("tkinter").Toplevel)]


def _run(rid, name):
    return {"id": rid, "name": name}


# ── Run search/filter ──────────────────────────────────────────────────────────

def test_get_filtered_runs_empty_query_returns_all(screen):
    screen._all_runs = [_run(1, "Morning Bus"), _run(2, "Afternoon Bus")]
    assert len(screen._get_filtered_runs()) == 2


def test_get_filtered_runs_matches_substring_anywhere(screen):
    screen._all_runs = [_run(1, "Morning Bus"), _run(2, "Afternoon Walk")]
    screen._search_var.set("bus")
    assert [r["id"] for r in screen._get_filtered_runs()] == [1]


def test_get_filtered_runs_case_insensitive(screen):
    screen._all_runs = [_run(1, "Morning Bus")]
    screen._search_var.set("MORNING")
    assert [r["id"] for r in screen._get_filtered_runs()] == [1]


def test_populate_dropdown_shows_none_found_message(screen):
    screen._populate_dropdown([])
    labels = [w.cget("text") for w in screen._dropdown_frame.winfo_children()]
    assert labels == ["No run sheets found."]


def test_populate_dropdown_lists_run_names(screen):
    screen._populate_dropdown([_run(1, "Morning Bus")])
    row = screen._dropdown_frame.winfo_children()[0]
    assert row.winfo_children()[0].cget("text") == "Morning Bus"


def test_entry_focus_shows_dropdown(screen):
    screen._on_entry_focus(None)
    assert screen._dropdown_open is True


def test_entry_blur_schedules_hide(screen):
    screen._show_dropdown()
    screen._on_entry_blur(None)
    screen._hide_dropdown()
    assert screen._dropdown_open is False


def test_do_search_opens_dropdown_when_closed(screen):
    screen._all_runs = [_run(1, "Morning Bus")]
    assert screen._dropdown_open is False
    screen._do_search()
    assert screen._dropdown_open is True


def test_do_search_repopulates_when_already_open(screen):
    screen._all_runs = [_run(1, "Morning Bus"), _run(2, "Afternoon Walk")]
    screen._show_dropdown()
    screen._search_var.set("walk")
    screen._do_search()
    labels = [row.winfo_children()[0].cget("text") for row in screen._dropdown_frame.winfo_children()]
    assert labels == ["Afternoon Walk"]


# ── Loading a run sheet ────────────────────────────────────────────────────────

def test_load_run_sets_current_run_id_and_search_text(screen, db):
    mid = db.upsert_member(_member())
    run_id = db.upsert_run("Morning Bus", [mid])
    screen._load_run(_run(run_id, "Morning Bus"))
    assert screen._current_run_id == run_id
    assert screen._search_var.get() == "Morning Bus"


def test_load_run_loads_eligible_members(screen, db):
    mid = db.upsert_member(_member(first_name="Rider", last_name="One"))
    run_id = db.upsert_run("Morning Bus", [mid])
    screen._load_run(_run(run_id, "Morning Bus"))
    assert [m["id"] for m in screen._selected] == [mid]


def test_load_run_includes_members_already_signed_in(screen, db):
    """A member who is currently signed IN must still load onto the run
    sheet — they're exactly who a sign-OUT run (e.g. an afternoon bus run)
    needs to select. Excluding them would make run sheets unusable for
    signing anyone out."""
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")
    run_id = db.upsert_run("Morning Bus", [mid])
    screen._load_run(_run(run_id, "Morning Bus"))
    assert [m["id"] for m in screen._selected] == [mid]


def test_load_run_includes_members_already_signed_out(screen, db):
    """A member who signed IN then OUT today is eligible again (unrestricted
    sign-in/out) so the run load must not exclude them."""
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")
    db.record_sign(mid, "OUT")
    run_id = db.upsert_run("Morning Bus", [mid])
    screen._load_run(_run(run_id, "Morning Bus"))
    assert [m["id"] for m in screen._selected] == [mid]


def test_load_run_shows_no_popup_for_already_signed_in_members(screen, db):
    """Loading a run sheet no longer pops up an "already signed in" warning —
    those members are loaded normally so they can be signed out."""
    import time
    mid = db.upsert_member(_member(first_name="Already", last_name="In"))
    db.record_sign(mid, "IN")
    run_id = db.upsert_run("Morning Bus", [mid])
    screen._load_run(_run(run_id, "Morning Bus"))
    time.sleep(0.15)
    screen.update()
    assert _toplevels(screen.winfo_toplevel()) == []


def test_load_run_hides_dropdown(screen, db):
    screen._show_dropdown()
    run_id = db.upsert_run("Morning Bus", [])
    screen._load_run(_run(run_id, "Morning Bus"))
    assert screen._dropdown_open is False


def test_load_run_multiple_members_sorted_by_name(screen, db):
    mid1 = db.upsert_member(_member(first_name="Zed", last_name="Zeta"))
    mid2 = db.upsert_member(_member(first_name="Amy", last_name="Alpha"))
    run_id = db.upsert_run("Bus", [mid1, mid2])
    screen._load_run(_run(run_id, "Bus"))
    assert [m["id"] for m in screen._selected] == [mid2, mid1]


# ── Add extra pupil ────────────────────────────────────────────────────────────

def test_open_add_extra_toggles_panel(screen, db):
    assert screen._extra_open is False
    screen._open_add_extra()
    assert screen._extra_open is True
    screen._open_add_extra()
    assert screen._extra_open is False


def test_open_add_extra_populates_all_members(screen, db):
    db.upsert_member(_member(first_name="Extra", last_name="Pupil"))
    screen._open_add_extra()
    labels = [row.winfo_children()[0].cget("text") for row in screen._extra_list_frame.winfo_children()]
    assert any("Extra Pupil" in l for l in labels)


def test_extra_search_filters_list(screen, db):
    db.upsert_member(_member(first_name="Findme", last_name="Person"))
    db.upsert_member(_member(first_name="Other", last_name="Person"))
    screen._open_add_extra()
    screen._extra_search_var.set("Findme")
    labels = [row.winfo_children()[0].cget("text") for row in screen._extra_list_frame.winfo_children()]
    assert labels == ["Findme Person"]


def test_populate_extra_list_limits_to_eight(screen, db):
    for i in range(10):
        db.upsert_member(_member(first_name=f"P{i}", last_name="Test"))
    screen._populate_extra_list(db.search_members(""))
    assert len(screen._extra_list_frame.winfo_children()) <= 8


def test_populate_extra_list_marks_already_selected(screen, db):
    mid = db.upsert_member(_member(first_name="Already", last_name="Selected"))
    m = db.get_member(mid)
    screen._selected = [m]
    screen._populate_extra_list([m])
    row = screen._extra_list_frame.winfo_children()[0]
    assert row.winfo_children()[0].cget("text") == "Already Selected ✓"


def test_add_extra_appends_member(screen, db):
    mid = db.upsert_member(_member())
    m = db.get_member(mid)
    screen._add_extra(m)
    assert [x["id"] for x in screen._selected] == [mid]


def test_add_extra_ignores_duplicate(screen, db):
    mid = db.upsert_member(_member())
    m = db.get_member(mid)
    screen._add_extra(m)
    screen._add_extra(m)
    assert len(screen._selected) == 1


def test_add_extra_row_click_adds_member(screen, db):
    mid = db.upsert_member(_member(first_name="Click", last_name="Me"))
    m = db.get_member(mid)
    screen._open_add_extra()
    screen.update()
    row = next(r for r in screen._extra_list_frame.winfo_children()
               if r.winfo_children()[0].cget("text") == "Click Me")
    row.event_generate("<ButtonPress-1>")
    screen.update()
    assert any(x["id"] == mid for x in screen._selected)


# ── Selected list / remove ─────────────────────────────────────────────────────

def test_remove_member_removes_from_selected(screen, db):
    mid = db.upsert_member(_member())
    m = db.get_member(mid)
    screen._selected = [m]
    screen._render_selected()
    screen._remove_member(mid)
    assert screen._selected == []


def test_remove_button_in_selected_list_removes_member(screen, db):
    mid = db.upsert_member(_member())
    m = db.get_member(mid)
    screen._selected = [m]
    screen._render_selected()
    row = screen._sel_frame.winfo_children()[0]
    remove_btn = next(w for w in row.winfo_children() if isinstance(w, __import__("tkinter").Button))
    remove_btn.invoke()
    assert screen._selected == []


# ── Enter ──────────────────────────────────────────────────────────────────────

def test_on_enter_with_no_selection_does_nothing(screen):
    screen._selected = []
    screen._on_enter()
    assert screen.app.calls == []


def test_on_enter_navigates_to_signature_with_selected(screen, db):
    mid = db.upsert_member(_member())
    m = db.get_member(mid)
    screen._selected = [m]
    screen._on_enter()
    assert screen.app.last_call == ("signature", {"members": [m]})


# ── Lifecycle ──────────────────────────────────────────────────────────────────

def test_on_show_resets_state(screen, db):
    db.upsert_run("Some Run", [])
    screen._selected = [{"id": 1, "first_name": "Stale", "last_name": "Data"}]
    screen._current_run_id = 999
    screen._extra_open = True
    screen._extra_panel.place(x=0, y=0)

    screen.on_show()

    assert screen._selected == []
    assert screen._current_run_id is None
    assert screen._extra_open is False
    assert len(screen._all_runs) >= 1


def test_on_show_clears_search_text(screen, db):
    screen._search_var.set("leftover")
    screen.on_show()
    assert screen._search_var.get() == ""


# ── Navigation ─────────────────────────────────────────────────────────────────

def test_back_button_navigates_to_options(screen):
    back_btn = next(
        w for w in screen._left.winfo_children()
        if isinstance(w, __import__("tkinter").Button) and w.cget("text") == "Back"
    )
    back_btn.invoke()
    assert screen.app.last_call == ("options", {})
