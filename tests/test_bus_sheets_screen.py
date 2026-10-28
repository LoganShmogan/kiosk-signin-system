"""
Tests for screens/bus_sheets_screen.py — today's sign-in list for bus duty.
"""
from helpers import FakeApp, member as _member


def _row_texts(row):
    return [w.cget("text") for w in row.winfo_children() if hasattr(w, "cget")]


def test_bus_sheets_shows_no_signins_message_when_empty(tk_root, db):
    from screens.bus_sheets_screen import BusSheetsScreen
    screen = BusSheetsScreen(tk_root, FakeApp())
    screen.pack()
    tk_root.update()
    screen._load_sheet()

    inner = screen._scroll.inner
    labels = [w.cget("text") for w in inner.winfo_children()]
    assert "No sign-ins recorded today." in labels


def test_bus_sheets_lists_todays_sign_ins(tk_root, db):
    from screens.bus_sheets_screen import BusSheetsScreen
    mid = db.upsert_member(_member(first_name="Bus", last_name="Rider", school="Test School"))
    db.record_sign(mid, "IN")

    screen = BusSheetsScreen(tk_root, FakeApp())
    screen.pack()
    tk_root.update()
    screen._load_sheet()

    from components.widgets import Divider
    inner = screen._scroll.inner
    rows = [w for w in inner.winfo_children()
            if isinstance(w, __import__("tkinter").Frame) and not isinstance(w, Divider)]
    assert len(rows) == 1
    texts = _row_texts(rows[0])
    assert "Bus Rider" in texts
    assert "Test School" in texts
    assert "IN" in texts


def test_bus_sheets_updates_date_label(tk_root, db):
    from screens.bus_sheets_screen import BusSheetsScreen
    screen = BusSheetsScreen(tk_root, FakeApp())
    screen.pack()
    tk_root.update()
    screen._load_sheet()
    assert screen._date_lbl.cget("text").startswith("Date: ")


def test_bus_sheets_on_show_loads_sheet(tk_root, db):
    from screens.bus_sheets_screen import BusSheetsScreen
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")

    screen = BusSheetsScreen(tk_root, FakeApp())
    screen.pack()
    tk_root.update()
    screen.on_show()

    inner = screen._scroll.inner
    assert len(inner.winfo_children()) > 0


def test_bus_sheets_reload_clears_previous_rows(tk_root, db):
    """Calling _load_sheet twice must not duplicate rows from the first load."""
    from screens.bus_sheets_screen import BusSheetsScreen
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")

    screen = BusSheetsScreen(tk_root, FakeApp())
    screen.pack()
    tk_root.update()
    screen._load_sheet()
    first_count = len(screen._scroll.inner.winfo_children())
    screen._load_sheet()
    second_count = len(screen._scroll.inner.winfo_children())
    assert first_count == second_count


def test_bus_sheets_refresh_button_reloads(tk_root, db):
    from screens.bus_sheets_screen import BusSheetsScreen
    screen = BusSheetsScreen(tk_root, FakeApp())
    screen.pack()
    tk_root.update()

    bar = screen.winfo_children()[0]
    refresh_btn = next(w for w in bar.winfo_children() if w.cget("text") == "Refresh")
    refresh_btn.invoke()
    assert screen._date_lbl.cget("text").startswith("Date: ")


def test_bus_sheets_back_button_navigates_to_options(tk_root, db):
    from screens.bus_sheets_screen import BusSheetsScreen
    app = FakeApp()
    screen = BusSheetsScreen(tk_root, app)
    screen.pack()
    tk_root.update()

    bar = screen.winfo_children()[0]
    back_btn = next(w for w in bar.winfo_children() if w.cget("text") == "← Back")
    back_btn.invoke()
    assert app.last_call == ("options", {})
