"""
Tests for components/widgets.py — the reusable Tk widgets used across kiosk
screens. Tkinter behaviour tests require a display; they are skipped
automatically when one is not available (e.g. headless CI). The `tk_root`
fixture lives in conftest.py and is shared with the screen test modules.
"""


# ── TouchButton ───────────────────────────────────────────────────────────────

def test_touch_button_hover_changes_background(tk_root):
    from components.widgets import TouchButton
    btn = TouchButton(tk_root, text="Go", bg="#111111", hover_bg="#222222")
    btn.pack()
    tk_root.update()
    btn.event_generate("<Enter>")
    tk_root.update()
    assert btn.cget("bg") == "#222222"
    btn.event_generate("<Leave>")
    tk_root.update()
    assert btn.cget("bg") == "#111111"


def test_touch_button_update_colors_changes_hover_target(tk_root):
    from components.widgets import TouchButton
    btn = TouchButton(tk_root, text="Go", bg="#111111", hover_bg="#222222")
    btn.pack()
    tk_root.update()
    btn.update_colors(bg="#333333", hover_bg="#444444")
    btn.event_generate("<Enter>")
    tk_root.update()
    assert btn.cget("bg") == "#444444"
    btn.event_generate("<Leave>")
    tk_root.update()
    assert btn.cget("bg") == "#333333"


def test_touch_button_click_fires_command(tk_root):
    from components.widgets import TouchButton
    calls = []
    btn = TouchButton(tk_root, text="Go", command=lambda: calls.append(1))
    btn.invoke()
    assert calls == [1]


def test_touch_button_update_colors_can_change_fg(tk_root):
    from components.widgets import TouchButton
    btn = TouchButton(tk_root, text="Go", fg="#000000")
    btn.update_colors(bg="#333333", hover_bg="#444444", fg="#ffffff")
    assert btn.cget("fg") == "#ffffff"


# ── Labels / Divider ──────────────────────────────────────────────────────────

def test_muted_label_uses_custom_colors(tk_root):
    from components.widgets import MutedLabel
    lbl = MutedLabel(tk_root, "Hello", bg="#101010", fg="#efefef")
    assert lbl.cget("text") == "Hello"
    assert lbl.cget("bg") == "#101010"
    assert lbl.cget("fg") == "#efefef"


def test_field_label_uses_custom_bg(tk_root):
    from components.widgets import FieldLabel
    lbl = FieldLabel(tk_root, "Name", bg="#101010")
    assert lbl.cget("text") == "Name"
    assert lbl.cget("bg") == "#101010"


def test_divider_uses_custom_bg(tk_root):
    from components.widgets import Divider
    d = Divider(tk_root, bg="#123456")
    assert d.cget("bg") == "#123456"


# ── StyledEntry ───────────────────────────────────────────────────────────────

def test_styled_entry_get_set_value(tk_root):
    from components.widgets import StyledEntry
    e = StyledEntry(tk_root)
    e.set_value("hello")
    assert e.get_value() == "hello"


def test_styled_entry_custom_bg_applied(tk_root):
    from components.widgets import StyledEntry
    e = StyledEntry(tk_root, bg="#abcdef")
    assert e.cget("bg") == "#abcdef"


def test_styled_entry_set_value_replaces_existing_text(tk_root):
    from components.widgets import StyledEntry
    e = StyledEntry(tk_root)
    e.set_value("first")
    e.set_value("second")
    assert e.get_value() == "second"


def test_styled_entry_set_value_none_clears(tk_root):
    from components.widgets import StyledEntry
    e = StyledEntry(tk_root)
    e.set_value("first")
    e.set_value(None)
    assert e.get_value() == ""


# ── DayPicker ─────────────────────────────────────────────────────────────────

def test_day_picker_starts_empty(tk_root):
    from components.widgets import DayPicker
    dp = DayPicker(tk_root)
    assert dp.get_value() == ""


def test_day_picker_toggle_selects_day(tk_root):
    from components.widgets import DayPicker
    dp = DayPicker(tk_root)
    dp._toggle("Mon")
    assert dp.get_value() == "Mon"


def test_day_picker_toggle_twice_deselects(tk_root):
    from components.widgets import DayPicker
    dp = DayPicker(tk_root)
    dp._toggle("Mon")
    dp._toggle("Mon")
    assert dp.get_value() == ""


def test_day_picker_multiple_days_preserve_order(tk_root):
    from components.widgets import DayPicker
    dp = DayPicker(tk_root)
    dp._toggle("Wed")
    dp._toggle("Mon")
    dp._toggle("Fri")
    assert dp.get_value() == "Mon,Wed,Fri"


def test_day_picker_set_value_round_trips(tk_root):
    from components.widgets import DayPicker
    dp = DayPicker(tk_root)
    dp.set_value("Tue,Thu")
    assert dp.get_value() == "Tue,Thu"


def test_day_picker_set_value_empty_string(tk_root):
    from components.widgets import DayPicker
    dp = DayPicker(tk_root)
    dp.set_value("Mon,Tue")
    dp.set_value("")
    assert dp.get_value() == ""


def test_day_picker_set_value_none(tk_root):
    from components.widgets import DayPicker
    dp = DayPicker(tk_root)
    dp.set_value("Mon")
    dp.set_value(None)
    assert dp.get_value() == ""


# ── SignatureCanvas ───────────────────────────────────────────────────────────

def test_signature_canvas_starts_with_no_signature(tk_root):
    from components.widgets import SignatureCanvas
    c = SignatureCanvas(tk_root)
    assert not c.has_signature()
    assert c.export_bytes() is None


def test_signature_canvas_stroke_produces_signature(tk_root):
    from components.widgets import SignatureCanvas
    import tkinter as tk

    class _Evt:
        def __init__(self, x, y):
            self.x, self.y = x, y

    c = SignatureCanvas(tk_root)
    c._start(_Evt(0, 0))
    c._draw(_Evt(10, 10))
    c._draw(_Evt(20, 0))
    c._end(_Evt(20, 0))
    assert c.has_signature()
    data = c.export_bytes()
    assert data is not None
    # Must round-trip through the same literal-eval format export_util expects.
    import ast
    strokes = ast.literal_eval(data.decode())
    assert strokes == [(0, 0, 10, 10), (10, 10, 20, 0)]


def test_signature_canvas_clear_resets_state(tk_root):
    from components.widgets import SignatureCanvas

    class _Evt:
        def __init__(self, x, y):
            self.x, self.y = x, y

    c = SignatureCanvas(tk_root)
    c._start(_Evt(0, 0))
    c._draw(_Evt(10, 10))
    c._end(_Evt(10, 10))
    assert c.has_signature()
    c.clear()
    assert not c.has_signature()
    assert c.export_bytes() is None


def test_signature_canvas_draw_without_press_is_ignored(tk_root):
    """A <B1-Motion> event with no preceding press must not record a stroke
    (guards against a stray drag event with no start point)."""
    from components.widgets import SignatureCanvas

    class _Evt:
        def __init__(self, x, y):
            self.x, self.y = x, y

    c = SignatureCanvas(tk_root)
    c._draw(_Evt(10, 10))
    assert not c.has_signature()


def test_signature_canvas_start_grab_set_tclerror_is_ignored(tk_root, monkeypatch):
    from components.widgets import SignatureCanvas
    import tkinter as tk

    class _Evt:
        def __init__(self, x, y):
            self.x, self.y = x, y

    c = SignatureCanvas(tk_root)

    def _boom():
        raise tk.TclError("grab failed")
    monkeypatch.setattr(c, "grab_set", _boom)
    c._start(_Evt(0, 0))  # must not raise
    assert c._last_x == 0 and c._last_y == 0


def test_signature_canvas_end_grab_release_tclerror_is_ignored(tk_root, monkeypatch):
    from components.widgets import SignatureCanvas
    import tkinter as tk

    class _Evt:
        def __init__(self, x, y):
            self.x, self.y = x, y

    c = SignatureCanvas(tk_root)

    def _boom():
        raise tk.TclError("release failed")
    monkeypatch.setattr(c, "grab_release", _boom)
    c._end(_Evt(0, 0))  # must not raise
    assert c._last_x is None and c._last_y is None


# ── PopupOverlay ──────────────────────────────────────────────────────────────

def test_popup_overlay_set_message_updates_text(tk_root):
    from components.widgets import PopupOverlay
    p = PopupOverlay(tk_root, is_error=False)
    p.set_message("Hello there")
    text = p._msg.get("1.0", "end").strip()
    assert text == "Hello there"
    p.destroy()


def test_popup_overlay_error_uses_error_status_text(tk_root):
    from components.widgets import PopupOverlay
    p = PopupOverlay(tk_root, is_error=True)
    assert p._status_label.cget("text") == "ERROR"
    p.destroy()


def test_popup_overlay_success_uses_success_status_text(tk_root):
    from components.widgets import PopupOverlay
    p = PopupOverlay(tk_root, is_error=False)
    assert p._status_label.cget("text") == "SUCCESS"
    p.destroy()


def test_popup_overlay_custom_title_overrides_status_text(tk_root):
    from components.widgets import PopupOverlay
    p = PopupOverlay(tk_root, title="Confirm Delete")
    assert p._status_label.cget("text") == "Confirm Delete"
    p.destroy()


def test_popup_overlay_add_button_adds_clickable_button(tk_root):
    from components.widgets import PopupOverlay
    calls = []
    p = PopupOverlay(tk_root)
    p.add_button("OK", lambda: calls.append(1))
    btns = p._btn_row.winfo_children()
    assert len(btns) == 1
    btns[0].invoke()
    assert calls == [1]
    p.destroy()


def test_popup_overlay_auto_size_runs_without_error(tk_root):
    # _auto_size normally fires 30ms later via .after(); calling it directly
    # makes the resize math deterministic for the test.
    from components.widgets import PopupOverlay
    p = PopupOverlay(tk_root)
    p.set_message("A message long enough to wrap across a couple of lines "
                  "so the auto-resize logic has real geometry to compute.")
    p._auto_size()
    p.destroy()


def test_popup_overlay_schedule_resize_cancels_pending_job(tk_root):
    # Calling set_message twice in a row must cancel the first pending
    # _auto_size job rather than leaving two scheduled.
    from components.widgets import PopupOverlay
    p = PopupOverlay(tk_root)
    p.set_message("First")
    p.set_message("Second")
    p.destroy()


def test_popup_overlay_schedule_resize_after_cancel_error_is_ignored(tk_root, monkeypatch):
    # A stale/expired job id can make after_cancel raise; that must be
    # swallowed rather than propagate out of _schedule_resize.
    from components.widgets import PopupOverlay
    p = PopupOverlay(tk_root)
    p._schedule_resize()  # sets self._resize_job for the first time

    def _boom(job):
        raise RuntimeError("stale job")
    monkeypatch.setattr(p, "after_cancel", _boom)
    p._schedule_resize()  # after_cancel now raises -> except Exception: pass
    p.destroy()


def test_popup_overlay_auto_size_count_error_falls_back(tk_root, monkeypatch):
    from components.widgets import PopupOverlay
    p = PopupOverlay(tk_root)

    def _boom(*a, **k):
        raise RuntimeError("count failed")
    monkeypatch.setattr(p._msg, "count", _boom)
    p._auto_size()  # must not raise; falls back to lines = 3
    p.destroy()


def test_popup_overlay_auto_size_font_metrics_error_falls_back(tk_root, monkeypatch):
    from components.widgets import PopupOverlay
    p = PopupOverlay(tk_root)

    def _boom(*a, **k):
        raise RuntimeError("cget failed")
    monkeypatch.setattr(p._msg, "cget", _boom)
    p._auto_size()  # must not raise; falls back to lh = 20
    p.destroy()


def test_popup_overlay_auto_size_reqheight_error_falls_back(tk_root, monkeypatch):
    from components.widgets import PopupOverlay
    p = PopupOverlay(tk_root)

    def _boom():
        raise RuntimeError("reqheight failed")
    monkeypatch.setattr(p, "winfo_reqheight", _boom)
    p._auto_size()  # must not raise; falls back to chrome = 200
    p.destroy()


# ── ScrollFrame ───────────────────────────────────────────────────────────────

def test_scroll_frame_scroll_to_top_does_not_raise(tk_root):
    from components.widgets import ScrollFrame
    sf = ScrollFrame(tk_root)
    sf.scroll_to_top()  # just needs to not raise


def test_scroll_frame_resize_and_scroll_handlers_do_not_raise(tk_root):
    from components.widgets import ScrollFrame

    class _Evt:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    sf = ScrollFrame(tk_root)
    sf.pack(fill="both", expand=True)
    tk_root.update()

    sf._on_inner_resize(_Evt())
    sf._on_canvas_resize(_Evt(width=200))
    sf._ts_start(_Evt(y_root=100))
    sf._ts_move(_Evt(y_root=90))
    sf._on_wheel(_Evt(delta=120))
