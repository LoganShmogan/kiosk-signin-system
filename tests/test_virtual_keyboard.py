"""
Tests for the VirtualKeyboard component (components/virtual_keyboard.py).

Layout / logic tests run on any platform (no display needed).
Tkinter behaviour tests require a display; they are skipped automatically when
one is not available (e.g. headless CI).
"""
import pytest

from components.virtual_keyboard import _NORMAL, _SHIFTED, _WIDE_IPX


# ── Layout correctness (no Tk needed) ────────────────────────────────────────

def test_row_count_matches():
    assert len(_NORMAL) == len(_SHIFTED)


def test_each_row_same_length():
    for r_n, r_s in zip(_NORMAL, _SHIFTED):
        assert len(r_n) == len(r_s), f"Row length mismatch: {r_n} vs {r_s}"


def test_no_empty_key_labels():
    for row in _NORMAL + _SHIFTED:
        for key in row:
            assert key, "Found an empty key label"


def test_numbers_row_has_14_keys():
    # 13 symbol keys + ⌫
    assert len(_NORMAL[0]) == 14


def test_qwerty_row_has_13_keys():
    assert len(_NORMAL[1]) == 13


def test_asdf_row_has_12_keys():
    assert len(_NORMAL[2]) == 12


def test_zxcv_row_has_12_keys():
    # ⇧ + 10 letters + ⇧
    assert len(_NORMAL[3]) == 12


def test_space_row_is_just_space():
    assert _NORMAL[4] == ["Space"]
    assert _SHIFTED[4] == ["Space"]


def test_backspace_present_in_numbers_row():
    assert "⌫" in _NORMAL[0]
    assert "⌫" in _SHIFTED[0]


def test_enter_present_in_asdf_row():
    assert "↵" in _NORMAL[2]
    assert "↵" in _SHIFTED[2]


def test_shift_keys_at_ends_of_zxcv_row():
    assert _NORMAL[3][0] == "⇧"
    assert _NORMAL[3][-1] == "⇧"


def test_shift_produces_uppercase_letters():
    for n, s in zip(_NORMAL[1], _SHIFTED[1]):
        if n.isalpha():
            assert s == n.upper(), f"Expected {n!r} → {n.upper()!r}, got {s!r}"


def test_shift_row2_produces_uppercase():
    for n, s in zip(_NORMAL[2], _SHIFTED[2]):
        if n.isalpha():
            assert s == n.upper()


def test_shift_produces_number_row_symbols():
    expected = {
        "1": "!", "2": "@", "3": "#", "4": "$", "5": "%",
        "6": "^", "7": "&", "8": "*", "9": "(", "0": ")",
    }
    for n, s in zip(_NORMAL[0], _SHIFTED[0]):
        if n in expected:
            assert s == expected[n], f"Expected {n!r} → {expected[n]!r}, got {s!r}"


def test_backtick_shifts_to_tilde():
    assert _NORMAL[0][0] == "`"
    assert _SHIFTED[0][0] == "~"


def test_wide_ipx_keys_all_exist_in_layout():
    all_keys = {k for row in _NORMAL for k in row}
    for key in _WIDE_IPX:
        assert key in all_keys, f"_WIDE_IPX key {key!r} is not present in the layout"


def test_wide_ipx_values_are_positive_ints():
    for key, val in _WIDE_IPX.items():
        assert isinstance(val, int) and val > 0, f"Bad _WIDE_IPX value for {key!r}: {val}"


def test_backspace_is_not_shifted_to_something_else():
    # ⌫ should stay ⌫ in both modes
    row_n, row_s = _NORMAL[0], _SHIFTED[0]
    assert row_n[-1] == "⌫"
    assert row_s[-1] == "⌫"


# ── Tkinter behaviour ─────────────────────────────────────────────────────────

@pytest.fixture
def tk_root():
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        yield root
        root.destroy()
    except Exception:
        pytest.skip("no display available")


@pytest.fixture
def vkb(tk_root):
    from components.virtual_keyboard import VirtualKeyboard
    return VirtualKeyboard(tk_root)


@pytest.fixture
def entry(tk_root):
    import tkinter as tk
    e = tk.Entry(tk_root)
    e.pack()
    tk_root.update()
    return e


# ── Initial state ─────────────────────────────────────────────────────────────

def test_initial_target_is_none(vkb):
    assert vkb._target is None


def test_initial_shifted_is_false(vkb):
    assert vkb._shifted is False


def test_initial_window_is_none(vkb):
    assert vkb._win is None


# ── attach / detach ───────────────────────────────────────────────────────────

def test_attach_creates_window(vkb, entry):
    vkb.attach(entry)
    assert vkb._win is not None
    assert vkb._win.winfo_exists()


def test_attach_sets_target(vkb, entry):
    vkb.attach(entry)
    assert vkb._target is entry


def test_attach_populates_buttons(vkb, entry):
    vkb.attach(entry)
    assert len(vkb._btns) > 0


def test_attach_again_reuses_window(vkb, entry):
    vkb.attach(entry)
    win_id = id(vkb._win)
    vkb.attach(entry)
    assert id(vkb._win) == win_id


def test_detach_clears_target(vkb, entry):
    vkb.attach(entry)
    vkb.detach()
    assert vkb._target is None


def test_detach_window_still_exists(vkb, entry):
    vkb.attach(entry)
    vkb.detach()
    assert vkb._win.winfo_exists()


def test_attach_different_entry_updates_target(vkb, entry, tk_root):
    import tkinter as tk
    entry2 = tk.Entry(tk_root)
    entry2.pack()
    vkb.attach(entry)
    vkb.attach(entry2)
    assert vkb._target is entry2


# ── Typing characters ─────────────────────────────────────────────────────────

def test_type_single_letter(vkb, entry):
    vkb.attach(entry)
    vkb._on_key("a", "A")
    assert entry.get() == "a"


def test_type_word(vkb, entry):
    vkb.attach(entry)
    for ch in "hello":
        vkb._on_key(ch, ch.upper())
    assert entry.get() == "hello"


def test_type_number(vkb, entry):
    vkb.attach(entry)
    for ch in "42":
        vkb._on_key(ch, {"4": "$", "2": "@"}[ch])
    assert entry.get() == "42"


def test_space_inserts_space(vkb, entry):
    vkb.attach(entry)
    for ch in "hi":
        vkb._on_key(ch, ch.upper())
    vkb._on_key("Space", "Space")
    for ch in "there":
        vkb._on_key(ch, ch.upper())
    assert entry.get() == "hi there"


def test_enter_does_not_change_text(vkb, entry):
    vkb.attach(entry)
    entry.insert(0, "hello")
    vkb._on_key("↵", "↵")
    assert entry.get() == "hello"


def test_backspace_removes_last_char(vkb, entry):
    vkb.attach(entry)
    for ch in "hello":
        vkb._on_key(ch, ch.upper())
    vkb._on_key("⌫", "⌫")
    assert entry.get() == "hell"


def test_backspace_on_empty_entry_does_not_crash(vkb, entry):
    vkb.attach(entry)
    vkb._on_key("⌫", "⌫")   # should not raise
    assert entry.get() == ""


# ── Shift behaviour ───────────────────────────────────────────────────────────

def test_shift_key_enables_shift(vkb, entry):
    vkb.attach(entry)
    vkb._on_key("⇧", "⇧")
    assert vkb._shifted is True


def test_shift_key_twice_disables_shift(vkb, entry):
    vkb.attach(entry)
    vkb._on_key("⇧", "⇧")
    vkb._on_key("⇧", "⇧")
    assert vkb._shifted is False


def test_shift_types_uppercase(vkb, entry):
    vkb.attach(entry)
    vkb._on_key("⇧", "⇧")
    vkb._on_key("a", "A")
    assert entry.get() == "A"


def test_shift_types_symbol_from_number(vkb, entry):
    vkb.attach(entry)
    vkb._on_key("⇧", "⇧")
    vkb._on_key("1", "!")
    assert entry.get() == "!"


def test_shift_auto_releases_after_letter(vkb, entry):
    vkb.attach(entry)
    vkb._on_key("⇧", "⇧")
    vkb._on_key("a", "A")
    assert vkb._shifted is False


def test_shift_auto_releases_after_symbol(vkb, entry):
    vkb.attach(entry)
    vkb._on_key("⇧", "⇧")
    vkb._on_key("1", "!")
    assert vkb._shifted is False


def test_shift_stays_on_after_backspace(vkb, entry):
    vkb.attach(entry)
    for ch in "ab":
        vkb._on_key(ch, ch.upper())
    vkb._on_key("⇧", "⇧")
    vkb._on_key("⌫", "⌫")
    assert vkb._shifted is True


def test_mixed_case_typing(vkb, entry):
    vkb.attach(entry)
    vkb._on_key("h", "H")
    vkb._on_key("⇧", "⇧")
    vkb._on_key("i", "I")   # shift auto-releases
    vkb._on_key("Space", "Space")
    vkb._on_key("⇧", "⇧")
    vkb._on_key("t", "T")
    for ch in "here":
        vkb._on_key(ch, ch.upper())
    assert entry.get() == "hI There"


# ── Shift display update ──────────────────────────────────────────────────────

def test_shift_display_shows_uppercase(vkb, entry):
    vkb.attach(entry)
    vkb._shifted = True
    vkb._update_shift_display()
    labels = [btn.cget("text") for btn, _, _ in vkb._btns]
    assert "Q" in labels
    assert "A" in labels
    assert "q" not in labels


def test_shift_display_reverts_to_lowercase(vkb, entry):
    vkb.attach(entry)
    vkb._shifted = True
    vkb._update_shift_display()
    vkb._shifted = False
    vkb._update_shift_display()
    labels = [btn.cget("text") for btn, _, _ in vkb._btns]
    assert "q" in labels
    assert "Q" not in labels


def test_shift_button_highlight_when_active(vkb, entry):
    from components.virtual_keyboard import _SHIFT_ACTIVE
    vkb.attach(entry)
    vkb._shifted = True
    vkb._update_shift_display()
    shift_bgs = [
        btn.cget("bg")
        for btn, normal, _ in vkb._btns
        if normal == "⇧"
    ]
    assert all(bg == _SHIFT_ACTIVE for bg in shift_bgs)


def test_shift_button_normal_color_when_inactive(vkb, entry):
    from components.virtual_keyboard import _KEY_BG_SPEC
    vkb.attach(entry)
    vkb._shifted = False
    vkb._update_shift_display()
    shift_bgs = [
        btn.cget("bg")
        for btn, normal, _ in vkb._btns
        if normal == "⇧"
    ]
    assert all(bg == _KEY_BG_SPEC for bg in shift_bgs)


def test_button_count_matches_total_keys(vkb, entry):
    vkb.attach(entry)
    total_keys = sum(len(row) for row in _NORMAL)
    assert len(vkb._btns) == total_keys
