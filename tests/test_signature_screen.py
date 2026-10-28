"""
Tests for screens/signature_screen.py — signature capture, direction
blocking, and sign-in/out submission.
"""
import pytest
from helpers import FakeApp, member as _member


@pytest.fixture
def screen(tk_root, db, monkeypatch):
    import email_notifier
    monkeypatch.setattr(email_notifier, "send_notification", lambda *a, **k: None)
    from screens.signature_screen import SignatureScreen
    s = SignatureScreen(tk_root, FakeApp())
    s.pack()
    tk_root.update()
    return s


def _toplevels(root):
    return [w for w in root.winfo_children() if isinstance(w, __import__("tkinter").Toplevel)]


# ── Direction toggle ──────────────────────────────────────────────────────────

def test_set_dir_in_colors_in_green(screen):
    screen._set_dir("IN")
    assert screen._btn_in.cget("bg") == "#27ae60"  # GREEN
    assert screen._btn_out.cget("bg") == "#372976"  # PURPLE


def test_set_dir_out_colors_out_red(screen):
    screen._set_dir("OUT")
    assert screen._btn_out.cget("bg") == "#BB2233"  # RED
    assert screen._btn_in.cget("bg") == "#372976"   # PURPLE


# ── on_show ────────────────────────────────────────────────────────────────

def test_on_show_with_members_list_populates_members(screen, db):
    m = {"id": 1, "first_name": "A", "last_name": "B"}
    screen.on_show(members=[m])
    assert screen.members == [m]


def test_on_show_with_single_member_kwarg(screen, db):
    m = {"id": 1, "first_name": "A", "last_name": "B"}
    screen.on_show(member=m)
    assert screen.members == [m]


def test_on_show_with_neither_clears_members(screen, db):
    screen.members = [{"id": 1, "first_name": "A", "last_name": "B"}]
    screen.on_show()
    assert screen.members == []


def test_on_show_populates_pupil_list_labels(screen, db):
    m = {"id": 1, "first_name": "Jane", "last_name": "Doe"}
    screen.on_show(members=[m])
    labels = []
    for w in screen._pupils_frame.winfo_children():
        try:
            labels.append(w.cget("text"))
        except Exception:
            pass
    assert "Jane Doe" in labels


def test_on_show_clears_signature_and_notes(screen, db):
    class _Evt:
        def __init__(self, x, y):
            self.x, self.y = x, y
    screen._sig._start(_Evt(0, 0))
    screen._sig._draw(_Evt(10, 10))
    screen._notes.insert("1.0", "leftover text")

    screen.on_show(members=[])
    assert not screen._sig.has_signature()
    assert screen._notes.get("1.0", "end").strip() == ""


def test_on_show_prefills_notes_from_single_member_activity(screen, db):
    mid = db.upsert_member(_member(activity="Soccer", activity_time="3pm"))
    m = db.get_member(mid)
    screen.on_show(members=[m])
    assert "Activity: Soccer" in screen._notes.get("1.0", "end")
    assert "3pm" in screen._notes.get("1.0", "end")


def test_on_show_multiple_members_does_not_prefill_notes(screen, db):
    mid1 = db.upsert_member(_member(first_name="One", activity="Soccer"))
    mid2 = db.upsert_member(_member(first_name="Two", activity="Chess"))
    members = [db.get_member(mid1), db.get_member(mid2)]
    screen.on_show(members=members)
    assert screen._notes.get("1.0", "end").strip() == ""


def test_on_show_auto_detects_in_when_no_sign_today(screen, db):
    mid = db.upsert_member(_member())
    m = db.get_member(mid)
    screen.on_show(members=[m])
    assert screen._direction.get() == "IN"


def test_on_show_auto_detects_out_after_sign_in(screen, db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")
    m = db.get_member(mid)
    screen.on_show(members=[m])
    assert screen._direction.get() == "OUT"


def test_on_show_clears_previous_pupil_labels(screen, db):
    """A second on_show must destroy the previous pupil-list labels before
    rendering the new set, not just append to them."""
    m1 = {"id": 1, "first_name": "A", "last_name": "B"}
    m2 = {"id": 2, "first_name": "C", "last_name": "D"}
    screen.on_show(members=[m1])
    assert screen._pupils_frame.winfo_children()
    screen.on_show(members=[m2])
    labels = []
    for w in screen._pupils_frame.winfo_children():
        try:
            labels.append(w.cget("text"))
        except Exception:
            pass
    assert labels == ["C D"]


# ── Submit: allowed sign-in ───────────────────────────────────────────────────

def test_submit_with_no_members_does_nothing(screen, db):
    screen.members = []
    screen._submit()
    assert _toplevels(screen.winfo_toplevel()) == []


def test_submit_records_sign_for_allowed_member(screen, db):
    mid = db.upsert_member(_member())
    m = db.get_member(mid)
    screen.members = [m]
    screen._set_dir("IN")
    screen._submit()

    last = db.get_last_sign(mid)
    assert last is not None
    assert last["direction"] == "IN"


def test_submit_records_notes(screen, db):
    mid = db.upsert_member(_member())
    m = db.get_member(mid)
    screen.members = [m]
    screen._set_dir("IN")
    screen._notes.insert("1.0", "  some notes  ")
    screen._submit()

    last = db.get_last_sign(mid)
    assert last["notes"] == "some notes"


def test_submit_records_signature_bytes(screen, db):
    mid = db.upsert_member(_member())
    m = db.get_member(mid)
    screen.members = [m]
    screen._set_dir("IN")

    class _Evt:
        def __init__(self, x, y):
            self.x, self.y = x, y
    screen._sig._start(_Evt(0, 0))
    screen._sig._draw(_Evt(10, 10))
    screen._submit()

    last = db.get_last_sign(mid)
    assert last["signature"] is not None


def test_submit_without_signature_still_records_sign(screen, db):
    """Signature is optional: submitting with an empty canvas must not be
    blocked, and the sign event is recorded with signature=None."""
    mid = db.upsert_member(_member())
    m = db.get_member(mid)
    screen.members = [m]
    screen._set_dir("IN")
    assert not screen._sig.has_signature()
    screen._submit()

    last = db.get_last_sign(mid)
    assert last is not None
    assert not last["signature"]


def test_submit_shows_success_popup(screen, db):
    mid = db.upsert_member(_member(first_name="Solo", last_name="Signer"))
    m = db.get_member(mid)
    screen.members = [m]
    screen._set_dir("IN")
    screen._submit()

    popups = _toplevels(screen.winfo_toplevel())
    assert len(popups) == 1
    assert "Solo Signer" in popups[0]._msg.get("1.0", "end")
    assert "signed in" in popups[0]._msg.get("1.0", "end")


def test_submit_done_button_navigates_to_options(screen, db):
    mid = db.upsert_member(_member())
    m = db.get_member(mid)
    screen.members = [m]
    screen._set_dir("IN")
    screen._submit()

    popup = _toplevels(screen.winfo_toplevel())[0]
    popup._btn_row.winfo_children()[0].invoke()
    assert screen.app.last_call == ("options", {})


# ── Submit: blocked direction ─────────────────────────────────────────────────

def test_submit_blocks_member_signed_in_wrong_direction(screen, db):
    mid = db.upsert_member(_member())
    db.record_sign(mid, "IN")  # already signed in -> allowed direction is OUT
    m = db.get_member(mid)
    screen.members = [m]
    screen._set_dir("IN")  # trying to sign IN again should be blocked
    screen._submit()

    # No new sign recorded beyond the original IN.
    signs_today = db.get_today_signs()
    assert len([s for s in signs_today if s["member_id"] == mid]) == 1


def test_submit_all_blocked_shows_error_popup(screen, db):
    mid = db.upsert_member(_member(first_name="Blocked", last_name="Person"))
    db.record_sign(mid, "IN")
    m = db.get_member(mid)
    screen.members = [m]
    screen._set_dir("IN")
    screen._submit()

    popups = _toplevels(screen.winfo_toplevel())
    assert len(popups) == 1
    msg = popups[0]._msg.get("1.0", "end")
    assert "Blocked Person" in msg
    assert "sign OUT first" in msg


def test_submit_partial_block_signs_allowed_and_skips_blocked(screen, db):
    ok_id = db.upsert_member(_member(first_name="Ok", last_name="One"))
    blocked_id = db.upsert_member(_member(first_name="Blocked", last_name="Two"))
    db.record_sign(blocked_id, "IN")  # blocked_id can only sign OUT now

    screen.members = [db.get_member(ok_id), db.get_member(blocked_id)]
    screen._set_dir("IN")
    screen._submit()

    assert db.get_last_sign(ok_id)["direction"] == "IN"
    signs_today = db.get_today_signs()
    assert len([s for s in signs_today if s["member_id"] == blocked_id]) == 1

    popups = _toplevels(screen.winfo_toplevel())
    msg = popups[0]._msg.get("1.0", "end")
    assert "Not eligible (skipped): Blocked Two" in msg


def test_submit_multiple_allowed_members_shows_count_message(screen, db):
    """With 2+ allowed members, the confirmation uses the plural 'N pupils
    have been signed ...' wording rather than the single-name message."""
    mid1 = db.upsert_member(_member(first_name="One", last_name="A"))
    mid2 = db.upsert_member(_member(first_name="Two", last_name="B"))
    screen.members = [db.get_member(mid1), db.get_member(mid2)]
    screen._set_dir("IN")
    screen._submit()

    popups = _toplevels(screen.winfo_toplevel())
    assert len(popups) == 1
    msg = popups[0]._msg.get("1.0", "end")
    assert "2 pupils have been signed in at" in msg


# ── Navigation ────────────────────────────────────────────────────────────────

def test_go_back_navigates_to_signin(screen):
    screen._go_back()
    assert screen.app.last_call == ("signin", {})


def _find_by_text(widget, text):
    for w in widget.winfo_children():
        try:
            if w.cget("text") == text:
                return w
        except Exception:
            pass
        found = _find_by_text(w, text)
        if found is not None:
            return found
    return None


def test_clear_signature_button_clears_canvas(screen):
    class _Evt:
        def __init__(self, x, y):
            self.x, self.y = x, y
    screen._sig._start(_Evt(0, 0))
    screen._sig._draw(_Evt(5, 5))
    assert screen._sig.has_signature()

    clear_btn = _find_by_text(screen, "Clear signature")
    assert clear_btn is not None
    clear_btn.invoke()
    assert not screen._sig.has_signature()


def test_exit_button_navigates_to_options(screen):
    exit_btn = _find_by_text(screen, "EXIT")
    assert exit_btn is not None
    exit_btn.invoke()
    assert screen.app.last_call == ("options", {})
