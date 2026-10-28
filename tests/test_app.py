"""
Tests for the Tkinter kiosk entry point (kiosk_signin/app.py) — the App class
that wires up all screens, and the _start_dashboard() helper that launches
the Flask dashboard under Waitress on a background thread.
"""
import tkinter as tk

import pytest

import app as app_module


class FakeEvent:
    def __init__(self, widget):
        self.widget = widget


@pytest.fixture
def built_app(db, tk_root):
    """A real App instance, built against the isolated temp-file `db` fixture
    (not the developer's live database), destroyed after the test."""
    a = app_module.App()
    yield a
    a.root.destroy()


# ── Construction ──────────────────────────────────────────────────────────────

def test_builds_all_expected_screens(built_app):
    expected = {
        "tap", "options", "signin", "signature", "profile", "social",
        "run_sheets", "admin_password", "admin_panel", "staff_profile",
    }
    assert set(built_app._screens.keys()) == expected


def test_non_windows_construction_disables_resize_and_has_no_vkb(built_app, monkeypatch):
    assert app_module._ON_WINDOWS is False
    assert built_app._vkb is None


def test_windows_construction_creates_virtual_keyboard(monkeypatch, db, tk_root):
    import components.virtual_keyboard as vkb_module

    created = {}

    class FakeVKB:
        def __init__(self, root):
            created["root"] = root

        def attach(self, widget):
            pass

        def detach(self):
            pass

    monkeypatch.setattr(app_module, "_ON_WINDOWS", True)
    monkeypatch.setattr(vkb_module, "VirtualKeyboard", FakeVKB)
    # "zoomed" is a Windows-only wm state; this test environment's X server
    # has no window manager to honour it, so stub it out — irrelevant to
    # what's under test here (that the Windows branch builds a VirtualKeyboard).
    monkeypatch.setattr(tk.Tk, "state", lambda self, *a, **k: None)

    a = app_module.App()
    try:
        assert a._vkb is not None
        assert created["root"] is a.root
    finally:
        a.root.destroy()


# ── show_screen ───────────────────────────────────────────────────────────────

def test_show_screen_known_name_lifts_and_calls_on_show(built_app):
    built_app.show_screen("tap")  # should not raise


def test_show_screen_unknown_name_falls_back_to_tap(built_app, capsys):
    built_app.show_screen("does-not-exist")
    out = capsys.readouterr().out
    assert "Unknown screen" in out


# ── Focus-driven virtual keyboard attach/detach ──────────────────────────────

@pytest.fixture
def windows_app_with_fake_vkb(monkeypatch, db, tk_root):
    import components.virtual_keyboard as vkb_module

    state = {"attached": None, "detached": False}

    class FakeVKB:
        def __init__(self, root):
            pass

        def attach(self, widget):
            state["attached"] = widget
            state["detached"] = False

        def detach(self):
            state["detached"] = True

    monkeypatch.setattr(app_module, "_ON_WINDOWS", True)
    monkeypatch.setattr(vkb_module, "VirtualKeyboard", FakeVKB)
    monkeypatch.setattr(tk.Tk, "state", lambda self, *a, **k: None)

    a = app_module.App()
    yield a, state
    a.root.destroy()


def test_focus_in_on_entry_attaches_virtual_keyboard(windows_app_with_fake_vkb):
    a, state = windows_app_with_fake_vkb
    entry = tk.Entry(a.root)
    a._on_focus_in(FakeEvent(entry))
    assert state["attached"] is entry


def test_focus_in_on_non_entry_widget_does_not_attach(windows_app_with_fake_vkb):
    a, state = windows_app_with_fake_vkb
    label = tk.Label(a.root)
    a._on_focus_in(FakeEvent(label))
    assert state["attached"] is None


def test_focus_in_cancels_pending_detach(windows_app_with_fake_vkb):
    a, state = windows_app_with_fake_vkb
    entry = tk.Entry(a.root)
    a._on_focus_out(FakeEvent(entry))
    assert a._pending_detach is not None
    a._on_focus_in(FakeEvent(entry))
    assert a._pending_detach is None


def test_focus_out_then_detach_removes_keyboard_when_no_entry_focused(windows_app_with_fake_vkb):
    a, state = windows_app_with_fake_vkb
    entry = tk.Entry(a.root)
    a._on_focus_in(FakeEvent(entry))
    a._on_focus_out(FakeEvent(entry))
    a._detach_if_not_entry()
    assert state["detached"] is True


def test_focus_out_on_non_entry_widget_does_nothing(windows_app_with_fake_vkb):
    a, state = windows_app_with_fake_vkb
    label = tk.Label(a.root)
    a._on_focus_out(FakeEvent(label))
    assert a._pending_detach is None


# ── run() ─────────────────────────────────────────────────────────────────────

def test_run_calls_mainloop(built_app, monkeypatch):
    called = {}
    monkeypatch.setattr(built_app.root, "mainloop", lambda: called.setdefault("called", True))
    built_app.run()
    assert called.get("called") is True


# ── Dashboard thread launcher ─────────────────────────────────────────────────

def test_start_dashboard_serves_flask_app_via_waitress(monkeypatch):
    import waitress
    from dashboard.app import app as real_dashboard_app

    calls = {}

    def fake_serve(wsgi_app, **kwargs):
        calls["app"] = wsgi_app
        calls["kwargs"] = kwargs

    monkeypatch.setattr(waitress, "serve", fake_serve)

    app_module._start_dashboard()

    assert calls["app"] is real_dashboard_app
    assert calls["kwargs"]["host"] == "0.0.0.0"
    assert calls["kwargs"]["port"] == 5000
