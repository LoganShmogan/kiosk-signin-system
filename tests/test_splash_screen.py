"""
Tests for screens/splash_screen.py — TapScreen and OptionsScreen.
Both are mostly static layout; the logic worth covering is navigation.
"""
from helpers import FakeApp


def test_tap_screen_tap_navigates_to_options(tk_root):
    from screens.splash_screen import TapScreen
    app = FakeApp()
    screen = TapScreen(tk_root, app)
    screen._on_tap()
    assert app.last_call == ("options", {})


def test_tap_screen_on_show_does_not_raise(tk_root):
    from screens.splash_screen import TapScreen
    screen = TapScreen(tk_root, FakeApp())
    screen.on_show()


def test_tap_screen_bind_children_binds_every_descendant(tk_root):
    """The tap-anywhere behaviour relies on _bind_children walking the whole
    tree; a click on any nested widget must still trigger _on_tap."""
    from screens.splash_screen import TapScreen
    app = FakeApp()
    screen = TapScreen(tk_root, app)
    screen.pack()
    tk_root.update()
    screen._bind_children(screen)

    # "Tap to start" label is nested a few frames deep; find it and click it.
    def _find_label(widget):
        for child in widget.winfo_children():
            try:
                if child.cget("text") == "Tap to start":
                    return child
            except Exception:
                pass
            found = _find_label(child)
            if found:
                return found
        return None

    label = _find_label(screen)
    assert label is not None
    label.event_generate("<ButtonPress-1>")
    tk_root.update()
    assert app.last_call == ("options", {})


def test_tap_screen_loads_logo_image_when_asset_present(tk_root, monkeypatch):
    """When the logo PNG exists on disk, TapScreen loads and displays it as a
    real image, instead of falling back to the styled 'KIOSK' text box (the
    asset isn't checked into this repo, so the success path is otherwise
    never exercised)."""
    import os
    from PIL import Image

    real_exists = os.path.exists

    def _fake_exists(path):
        if str(path).endswith(os.path.join("assets", "logo.png")):
            return True
        return real_exists(path)

    monkeypatch.setattr(os.path, "exists", _fake_exists)
    monkeypatch.setattr(Image, "open", lambda p: Image.new("RGB", (300, 150), "white"))

    from screens.splash_screen import TapScreen
    screen = TapScreen(tk_root, FakeApp())
    assert screen._logo_img is not None


def test_options_screen_menu_navigates_to_correct_screens(tk_root):
    from screens.splash_screen import OptionsScreen
    app = FakeApp()
    screen = OptionsScreen(tk_root, app)
    screen.pack()
    tk_root.update()

    # Buttons alternate between two columns (even index -> left, odd -> right),
    # so match by label text rather than assuming a flat traversal order.
    label_to_screen = {label: screen_name for label, screen_name, *_ in OptionsScreen.MENU}
    buttons = [
        w for col in screen.winfo_children()[1].winfo_children()
        for w in col.winfo_children()
    ]
    assert len(buttons) == len(OptionsScreen.MENU)
    for btn in buttons:
        label = btn.cget("text")
        assert label in label_to_screen
        app.calls.clear()
        btn.invoke()
        assert app.last_call == (label_to_screen[label], {})


def test_options_screen_back_button_navigates_to_tap(tk_root):
    from screens.splash_screen import OptionsScreen
    app = FakeApp()
    screen = OptionsScreen(tk_root, app)
    screen.pack()
    tk_root.update()
    bar = screen.winfo_children()[0]
    back_btn = bar.winfo_children()[0]
    back_btn.invoke()
    assert app.last_call == ("tap", {})


def test_options_screen_on_show_does_not_raise(tk_root):
    from screens.splash_screen import OptionsScreen
    screen = OptionsScreen(tk_root, FakeApp())
    screen.on_show()
