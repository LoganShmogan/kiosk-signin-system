# screens/signature_screen.py — Sign In / Sign Out screen
# Full screen layout, single button row bottom-right.

import tkinter as tk
from datetime import datetime

import database
import email_notifier
from components.widgets import SignatureCanvas, PopupOverlay

CREAM   = "#FFFCF7"
PURPLE  = "#372976"
RED     = "#BB2233"
GREEN   = "#27ae60"
GREEN_H = "#2ecc71"
BLACK   = "#000000"
WHITE   = "#FFFFFF"
MUTED   = "#888888"


class SignatureScreen(tk.Frame):

    def __init__(self, parent, app):
        super().__init__(parent, bg=CREAM)
        self.app     = app
        self.members = []
        self._direction = tk.StringVar(value="IN")
        self._build_ui()

    # ── Build ──────────────────────────────────────────────────────────────────

    def _build_ui(self):
        W, H = 1280, 720

        # ── LEFT column  (x=0, width=580) ────────────────────────────────────
        left = tk.Frame(self, bg=CREAM)
        left.place(x=0, y=0, width=580, height=H)

        # "Signing for:" heading
        tk.Label(
            left, text="Signing for:",
            bg=CREAM, fg=BLACK,
            font=("Helvetica", 26, "bold"),
        ).place(x=48, y=32)

        # Pupils list box
        pupils_box = tk.Frame(
            left, bg=WHITE,
            highlightthickness=2, highlightbackground=PURPLE,
        )
        pupils_box.place(x=48, y=80, width=500, height=150)

        self._pupils_canvas = tk.Canvas(
            pupils_box, bg=WHITE, highlightthickness=0
        )
        p_sb = tk.Scrollbar(
            pupils_box, orient="vertical", width=30, command=self._pupils_canvas.yview
        )
        self._pupils_canvas.configure(yscrollcommand=p_sb.set)
        self._pupils_canvas.pack(side="left", fill="both", expand=True)
        p_sb.pack(side="right", fill="y")

        self._pupils_frame = tk.Frame(self._pupils_canvas, bg=WHITE)
        p_win = self._pupils_canvas.create_window(
            (0, 0), window=self._pupils_frame, anchor="nw"
        )
        self._pupils_frame.bind(
            "<Configure>",
            lambda e: self._pupils_canvas.configure(
                scrollregion=self._pupils_canvas.bbox("all")
            ),
        )
        self._pupils_canvas.bind(
            "<Configure>",
            lambda e: self._pupils_canvas.itemconfig(p_win, width=e.width),
        )

        # Date / Time stamp labels
        tk.Label(
            left, text="Date/Time Stamp",
            bg=CREAM, fg=BLACK,
            font=("Helvetica", 13),
        ).place(x=48, y=252)

        tk.Label(
            left, text="(AUTO STAMP)",
            bg=CREAM, fg=RED,
            font=("Helvetica", 11),
        ).place(x=330, y=255)

        # Date box
        date_box = tk.Frame(
            left, bg=WHITE,
            highlightthickness=2, highlightbackground=PURPLE,
        )
        date_box.place(x=48, y=278, width=220, height=44)
        self._date_lbl = tk.Label(
            date_box, text="",
            bg=WHITE, fg=BLACK,
            font=("Helvetica", 15),
            padx=10,
        )
        self._date_lbl.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Time box
        time_box = tk.Frame(
            left, bg=WHITE,
            highlightthickness=2, highlightbackground=PURPLE,
        )
        time_box.place(x=288, y=278, width=220, height=44)
        self._time_lbl = tk.Label(
            time_box, text="",
            bg=WHITE, fg=BLACK,
            font=("Helvetica", 15),
            padx=10,
        )
        self._time_lbl.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Notes label + text box
        tk.Label(
            left, text="Notes",
            bg=CREAM, fg=BLACK,
            font=("Helvetica", 13),
        ).place(x=48, y=344)

        notes_box = tk.Frame(
            left, bg=WHITE,
            highlightthickness=2, highlightbackground=PURPLE,
        )
        notes_box.place(x=48, y=368, width=500, height=200)
        self._notes = tk.Text(
            notes_box,
            bg=WHITE, fg=BLACK,
            font=("Helvetica", 13),
            relief="flat", bd=0,
            insertbackground=BLACK,
            wrap="word",
        )
        self._notes.pack(fill="both", expand=True, padx=6, pady=6)

        # ── RIGHT column  (x=620, width=620) ─────────────────────────────────
        right = tk.Frame(self, bg=CREAM)
        right.place(x=620, y=0, width=620, height=H)

        # Sign-in/out label
        tk.Label(
            right, text="Sign-in/out",
            bg=CREAM, fg=BLACK,
            font=("Helvetica", 13),
        ).place(x=32, y=32)

        # IN button
        self._btn_in = tk.Button(
            right, text="IN",
            bg=GREEN, fg=WHITE,
            activebackground=GREEN_H, activeforeground=WHITE,
            font=("Helvetica", 28, "bold"),
            relief="flat", bd=0, cursor="hand2",
            command=lambda: self._set_dir("IN"),
        )
        self._btn_in.place(x=32, y=62, width=240, height=160)

        # OUT button
        self._btn_out = tk.Button(
            right, text="OUT",
            bg=PURPLE, fg=WHITE,
            activebackground="#4a3a8a", activeforeground=WHITE,
            font=("Helvetica", 28, "bold"),
            relief="flat", bd=0, cursor="hand2",
            command=lambda: self._set_dir("OUT"),
        )
        self._btn_out.place(x=296, y=62, width=240, height=160)

        # Signature label
        tk.Label(
            right, text="Signature",
            bg=CREAM, fg=BLACK,
            font=("Helvetica", 13),
        ).place(x=32, y=248)

        # Signature canvas
        sig_box = tk.Frame(
            right, bg=WHITE,
            highlightthickness=2, highlightbackground=PURPLE,
        )
        sig_box.place(x=32, y=272, width=536, height=260)
        self._sig = SignatureCanvas(sig_box, width=532, height=256)
        self._sig.pack(fill="both", expand=True)

        # Clear signature link
        tk.Button(
            right, text="Clear signature",
            command=self._sig.clear,
            bg=CREAM, fg=MUTED,
            font=("Helvetica", 11),
            relief="flat", bd=0, cursor="hand2",
        ).place(x=32, y=540)

        # ── Bottom-right button row ───────────────────────────────────────────
        btn_y = H - 64

        # DONE (rightmost)
        tk.Button(
            self, text="DONE",
            command=self._submit,
            bg=GREEN, fg=WHITE,
            activebackground=GREEN_H, activeforeground=WHITE,
            font=("Helvetica", 14, "bold"),
            relief="flat", bd=0, cursor="hand2",
            padx=28, pady=14,
        ).place(x=W - 148, y=btn_y)

        # EXIT
        tk.Button(
            self, text="EXIT",
            command=lambda: self.app.show_screen("options"),
            bg=RED, fg=WHITE,
            activebackground="#c0392b", activeforeground=WHITE,
            font=("Helvetica", 14, "bold"),
            relief="flat", bd=0, cursor="hand2",
            padx=28, pady=14,
        ).place(x=W - 284, y=btn_y)

        # BACK
        tk.Button(
            self, text="BACK",
            command=self._go_back,
            bg=PURPLE, fg=WHITE,
            activebackground="#4a3a8a", activeforeground=WHITE,
            font=("Helvetica", 14, "bold"),
            relief="flat", bd=0, cursor="hand2",
            padx=28, pady=14,
        ).place(x=W - 420, y=btn_y)

    # ── Direction toggle ───────────────────────────────────────────────────────

    def _set_dir(self, direction):
        self._direction.set(direction)
        if direction == "IN":
            self._btn_in.configure(bg=GREEN, activebackground=GREEN_H)
            self._btn_out.configure(bg=PURPLE, activebackground="#4a3a8a")
        else:
            self._btn_in.configure(bg=PURPLE, activebackground="#4a3a8a")
            self._btn_out.configure(bg=RED, activebackground="#c0392b")

    # ── Submit ─────────────────────────────────────────────────────────────────

    def _submit(self):
        if not self.members:
            return

        direction = self._direction.get()
        notes     = self._notes.get("1.0", tk.END).strip()
        sig_bytes = self._sig.export_bytes()

        allowed  = []
        blocked  = []

        for member in self.members:
            allowed_dir = database.get_allowed_direction(member["id"])
            if allowed_dir != direction:
                blocked.append(member)
            else:
                allowed.append(member)

        if not allowed:
            names = ", ".join(
                f"{m['first_name']} {m['last_name']}" for m in blocked
            )
            other = "OUT" if direction == "IN" else "IN"
            msg = f"These pupils need to sign {other} first:\n\n{names}"
            popup = PopupOverlay(
                self.winfo_toplevel(), is_error=True, width=520, height=290
            )
            popup.set_message(msg)
            popup.add_button("OK", popup.destroy)
            popup.add_button("Back to Menu",
                             lambda: (popup.destroy(), self.app.show_screen("options")))
            return

        now = datetime.now()
        for member in allowed:
            database.record_sign(member["id"], direction, notes, sig_bytes)
            email_notifier.send_notification(member, direction, now)

        label = "in" if direction == "IN" else "out"
        if len(allowed) == 1:
            name = f"{allowed[0]['first_name']} {allowed[0]['last_name']}"
            msg  = f"{name} has been signed {label} at {datetime.now().strftime('%H:%M')}."
        else:
            msg = (
                f"{len(allowed)} pupils have been signed {label} at "
                f"{datetime.now().strftime('%H:%M')}."
            )

        extra_height = 0
        if blocked:
            skipped_names = ", ".join(
                f"{m['first_name']} {m['last_name']}" for m in blocked
            )
            msg += f"\n\nNot eligible (skipped): {skipped_names}"
            extra_height = 70

        popup = PopupOverlay(
            self.winfo_toplevel(), is_error=False,
            width=520, height=230 + extra_height
        )
        popup.set_message(msg)
        popup.add_button(
            "Done",
            lambda: (popup.destroy(), self.app.show_screen("options")),
            bg=GREEN, fg=WHITE, hover_bg=GREEN_H,
        )

    # ── Navigation ─────────────────────────────────────────────────────────────

    def _go_back(self):
        self.app.show_screen("signin")

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def on_show(self, members=None, member=None, **_):
        if members is not None:
            self.members = members
        elif member is not None:
            self.members = [member]
        else:
            self.members = []

        # Render pupil list
        for w in self._pupils_frame.winfo_children():
            w.destroy()
        for m in self.members:
            tk.Label(
                self._pupils_frame,
                text=f"{m['first_name']} {m['last_name']}",
                bg=WHITE, fg=BLACK,
                font=("Helvetica", 15),
                padx=12, pady=8,
                anchor="w",
            ).pack(fill="x")
            tk.Frame(self._pupils_frame, bg="#e0e0e0", height=1).pack(fill="x")

        # Timestamp
        now = datetime.now()
        self._date_lbl.configure(text=now.strftime("%d/%m/%Y"))
        self._time_lbl.configure(text=now.strftime("%H:%M:%S"))

        # Clear
        self._sig.clear()
        self._notes.delete("1.0", tk.END)

        # Pre-fill notes from first member's activity (single member only)
        if len(self.members) == 1:
            m = database.get_member(self.members[0]["id"])
            if m and m.get("activity"):
                note = f"Activity: {m['activity']}"
                if m.get("activity_time"):
                    note += f" — {m['activity_time']}"
                self._notes.insert("1.0", note)

        # Auto-detect direction based on today's sign state
        if self.members:
            last = database.get_today_last_sign(self.members[0]["id"])
            if last and last["direction"] == "IN":
                self._set_dir("OUT")
            else:
                self._set_dir("IN")
