"""
Tests for screens/social_screen.py — a static Social Media & Contacts
info screen. No real business logic beyond back/exit navigation.
"""
from helpers import FakeApp


def test_social_screen_constructs_without_error(tk_root):
    from screens.social_screen import SocialScreen
    app = FakeApp()
    screen = SocialScreen(tk_root, app)
    screen.pack()
    tk_root.update()


def test_social_screen_back_and_exit_navigate_to_options(tk_root):
    from screens.social_screen import SocialScreen
    app = FakeApp()
    screen = SocialScreen(tk_root, app)
    screen.pack()
    tk_root.update()

    top_bar = screen.winfo_children()[0]
    back_btn, exit_btn = top_bar.winfo_children()[0], top_bar.winfo_children()[1]
    assert back_btn.cget("text") == "← Back"
    assert exit_btn.cget("text") == "Exit"

    back_btn.invoke()
    assert app.last_call == ("options", {})
    exit_btn.invoke()
    assert app.last_call == ("options", {})


def test_social_screen_on_show_does_not_raise(tk_root):
    from screens.social_screen import SocialScreen
    app = FakeApp()
    screen = SocialScreen(tk_root, app)
    screen.on_show()


# ── Placeholder contact info guard ────────────────────────────────────────────
# Reads the module source directly so the placeholder contact info can't be
# accidentally reverted to real business details.

import pathlib

SOURCE = (
    pathlib.Path(__file__).resolve().parent.parent
    / "kiosk_signin"
    / "screens"
    / "social_screen.py"
).read_text()

REAL_STRINGS = [
    "Littlemonkeys.co.nz",
    "afterschooladventures@littlemonkeys.nz",
    "+64 027 288 1800",
]

FAKE_STRINGS = [
    "www.example-kiosk.org",
    "info@example-kiosk.org",
    "+1 555 0100",
]


def test_no_real_business_contact_info_present():
    for real in REAL_STRINGS:
        assert real not in SOURCE, f"Real business info leaked back in: {real!r}"


def test_placeholder_contact_info_present():
    for fake in FAKE_STRINGS:
        assert fake in SOURCE, f"Expected placeholder missing: {fake!r}"
