"""
Regression guard for screens/social_screen.py.

Reads the module source directly (no Tk/display needed) to make sure the
placeholder contact info hasn't been accidentally reverted to real business
details.
"""
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
