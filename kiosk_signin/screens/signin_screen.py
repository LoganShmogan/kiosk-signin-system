# screens/signin_screen.py — Main Sign-In Screen
# Left (55%): search + dropdown list
# Right (45%): selected pupils

import tkinter as tk

import database
from components.widgets import Divider, PopupOverlay

CREAM  = "#FFFCF7"
PURPLE = "#372976"
RED    = "#BB2233"
BLACK  = "#000000"
WHITE  = "#FFFFFF"


class SignInScreen(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=CREAM)
        self.app            = app
        self._search_after  = None
        self._hide_after    = None
        self._selected      = []
        self._all_members   = []
        self._dropdown_open = False
        self._build_ui()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        W, H    = 1280, 720
        LEFT_W  = int(W * 0.55)   # 704
        RIGHT_W = W - LEFT_W       # 576

        # ══════════════════════════════════════════════════════════════════════
        # LEFT PANEL
        # ══════════════════════════════════════════════════════════════════════
        # Use place so we can also place the dropdown overlay inside it
        self._left = tk.Frame(self, bg=CREAM)
        self._left.place(x=0, y=0, width=LEFT_W, height=H)

        tk.Label(
            self._left, text="Sign-in",
            bg=CREAM, fg=BLACK,
            font=("Helvetica", 13),
        ).place(x=16, y=12)

        # "Search name" label
        tk.Label(
            self._left, text="Search name",
            bg=CREAM, fg=BLACK,
            font=("Helvetica", 22, "bold"),
        ).place(x=60, y=50)

        # Search entry
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", self._on_search_change)

        self._search_entry = tk.Entry(
            self._left,
            textvariable=self._search_var,
            font=("Helvetica", 16),
            relief="flat", bd=0,
            highlightthickness=2,
            highlightbackground=PURPLE,
            highlightcolor=PURPLE,
            bg=WHITE, fg=BLACK,
            insertbackground=BLACK,
        )
        # Entry sits at y=100, spans from x=60 to LEFT_W-60
        self._entry_x = 60
        self._entry_y = 100
        self._entry_w = LEFT_W - 120
        self._search_entry.place(
            x=self._entry_x, y=self._entry_y,
            width=self._entry_w, height=44,
        )
        self._search_entry.bind("<FocusIn>",  self._on_entry_focus)
        self._search_entry.bind("<FocusOut>", self._on_entry_blur)

        # Dropdown — placed just below the entry, inside self._left
        self._dropdown_outer = tk.Frame(
            self._left, bg=WHITE,
            highlightthickness=2, highlightbackground=PURPLE,
        )
        # Not shown yet

        self._dropdown_canvas = tk.Canvas(
            self._dropdown_outer, bg=WHITE, highlightthickness=0
        )
        dd_sb = tk.Scrollbar(
            self._dropdown_outer, orient="vertical", width=30,
            command=self._dropdown_canvas.yview,
        )
        self._dropdown_canvas.configure(yscrollcommand=dd_sb.set)
        self._dropdown_canvas.pack(side="left", fill="both", expand=True)
        dd_sb.pack(side="right", fill="y")

        self._dropdown_frame = tk.Frame(self._dropdown_canvas, bg=WHITE)
        self._dd_win = self._dropdown_canvas.create_window(
            (0, 0), window=self._dropdown_frame, anchor="nw"
        )
        self._dropdown_frame.bind(
            "<Configure>",
            lambda e: self._dropdown_canvas.configure(
                scrollregion=self._dropdown_canvas.bbox("all")
            ),
        )
        self._dropdown_canvas.bind(
            "<Configure>",
            lambda e: self._dropdown_canvas.itemconfig(self._dd_win, width=e.width),
        )

        # Back / Enter buttons at bottom of left panel
        tk.Button(
            self._left, text="Back",
            command=lambda: self.app.show_screen("options"),
            bg=PURPLE, fg=WHITE,
            font=("Helvetica", 14, "bold"),
            relief="flat", bd=0, cursor="hand2",
            padx=24, pady=12,
        ).place(x=60, y=H - 70)

        tk.Button(
            self._left, text="Enter",
            command=self._on_enter,
            bg=PURPLE, fg=WHITE,
            font=("Helvetica", 14, "bold"),
            relief="flat", bd=0, cursor="hand2",
            padx=24, pady=12,
        ).place(x=180, y=H - 70)

        # ══════════════════════════════════════════════════════════════════════
        # RIGHT PANEL — selected pupils
        # ══════════════════════════════════════════════════════════════════════
        right = tk.Frame(self, bg=CREAM)
        right.place(x=LEFT_W, y=0, width=RIGHT_W, height=H)

        hdr = tk.Frame(right, bg=CREAM)
        hdr.place(x=24, y=20, width=RIGHT_W - 48, height=36)

        tk.Label(
            hdr, text="Selected Pupils",
            bg=CREAM, fg=BLACK,
            font=("Helvetica", 18, "bold"),
        ).pack(side="left")

        tk.Label(
            hdr, text="(AUTO SORT)",
            bg=CREAM, fg=RED,
            font=("Helvetica", 12),
        ).pack(side="right")

        # Divider
        tk.Frame(right, bg="#cccccc", height=1).place(
            x=24, y=60, width=RIGHT_W - 48
        )

        # Scrollable list box
        sel_outer = tk.Frame(
            right, bg=WHITE,
            highlightthickness=2, highlightbackground=PURPLE,
        )
        sel_outer.place(x=24, y=72, width=RIGHT_W - 48, height=H - 112)

        self._sel_canvas = tk.Canvas(sel_outer, bg=WHITE, highlightthickness=0)
        sel_sb = tk.Scrollbar(
            sel_outer, orient="vertical", width=30, command=self._sel_canvas.yview
        )
        self._sel_canvas.configure(yscrollcommand=sel_sb.set)
        self._sel_canvas.pack(side="left", fill="both", expand=True)
        sel_sb.pack(side="right", fill="y")

        self._sel_frame = tk.Frame(self._sel_canvas, bg=WHITE)
        sel_win = self._sel_canvas.create_window(
            (0, 0), window=self._sel_frame, anchor="nw"
        )
        self._sel_frame.bind(
            "<Configure>",
            lambda e: self._sel_canvas.configure(
                scrollregion=self._sel_canvas.bbox("all")
            ),
        )
        self._sel_canvas.bind(
            "<Configure>",
            lambda e: self._sel_canvas.itemconfig(sel_win, width=e.width),
        )

    # ── Dropdown show / hide ───────────────────────────────────────────────────

    def _on_entry_focus(self, _):
        if self._hide_after:
            self.after_cancel(self._hide_after)
            self._hide_after = None
        self._show_dropdown()

    def _on_entry_blur(self, _):
        # Small delay so a click on a list item fires before we hide
        self._hide_after = self.after(200, self._hide_dropdown)

    def _show_dropdown(self):
        self._dropdown_open = True
        self._populate_dropdown(self._get_filtered())
        drop_y = self._entry_y + 44   # just below the entry
        self._dropdown_outer.place(
            x=self._entry_x,
            y=drop_y,
            width=self._entry_w,
            height=260,
        )
        self._dropdown_outer.lift()

    def _hide_dropdown(self):
        self._hide_after = None
        self._dropdown_open = False
        self._dropdown_outer.place_forget()

    # ── Search & filter ────────────────────────────────────────────────────────

    def _on_search_change(self, *_):
        if self._search_after:
            self.after_cancel(self._search_after)
        self._search_after = self.after(100, self._do_search)

    def _do_search(self):
        # Re-open dropdown if user started typing (covers programmatic set too)
        if not self._dropdown_open:
            self._show_dropdown()
        else:
            self._populate_dropdown(self._get_filtered())

    def _get_filtered(self):
        q = self._search_var.get().strip().lower()
        if not q:
            members = list(self._all_members)
        else:
            members = []
            for m in self._all_members:
                last  = m["last_name"].lower()
                first = m["first_name"].lower()
                full  = f"{first} {last}"
                if last.startswith(q) or first.startswith(q) or q in full:
                    members.append(m)
        members.sort(key=lambda m: (m["last_name"].lower(), m["first_name"].lower()))
        return members

    # ── Dropdown population ───────────────────────────────────────────────────

    def _populate_dropdown(self, members):
        for w in self._dropdown_frame.winfo_children():
            w.destroy()

        self._dropdown_canvas.yview_moveto(0)
        selected_ids = {m["id"] for m in self._selected}

        if not members:
            tk.Label(
                self._dropdown_frame, text="No members found.",
                bg=WHITE, fg="#888888",
                font=("Helvetica", 13),
                padx=12, pady=8,
            ).pack(anchor="w")
            return

        for m in members:
            already = m["id"] in selected_ids
            name    = f"{m['first_name']} {m['last_name']}"

            row = tk.Frame(self._dropdown_frame, bg=WHITE, cursor="hand2")
            row.pack(fill="x")

            lbl = tk.Label(
                row,
                text=name + (" ✓" if already else ""),
                bg=WHITE,
                fg="#aaaaaa" if already else BLACK,
                font=("Helvetica", 15),
                padx=14, pady=10,
                anchor="w",
            )
            lbl.pack(fill="x")

            tk.Frame(row, bg="#e0e0e0", height=1).pack(fill="x")

            if not already:
                for widget in (row, lbl):
                    widget.bind(
                        "<Enter>",
                        lambda e, r=row, l=lbl: (
                            r.configure(bg="#f0eeff"),
                            l.configure(bg="#f0eeff"),
                        ),
                    )
                    widget.bind(
                        "<Leave>",
                        lambda e, r=row, l=lbl: (
                            r.configure(bg=WHITE),
                            l.configure(bg=WHITE),
                        ),
                    )
                    widget.bind(
                        "<ButtonPress-1>",
                        lambda e, mem=m: self._add_member(mem),
                    )

    # ── Selected list ─────────────────────────────────────────────────────────

    def _add_member(self, member):
        if any(m["id"] == member["id"] for m in self._selected):
            return
        self._selected.append(member)
        self._selected.sort(
            key=lambda m: (m["last_name"].lower(), m["first_name"].lower())
        )
        self._render_selected()
        # Clear the search text for the next lookup, but keep focus on the
        # entry (rather than letting it blur) so the virtual keyboard stays
        # attached instead of closing after every selection.
        self._search_var.set("")
        self._search_entry.focus_set()
        if self._dropdown_open:
            self._populate_dropdown(self._get_filtered())

    def _remove_member(self, member_id):
        self._selected = [m for m in self._selected if m["id"] != member_id]
        self._render_selected()
        if self._dropdown_open:
            self._populate_dropdown(self._get_filtered())

    def _render_selected(self):
        for w in self._sel_frame.winfo_children():
            w.destroy()

        for m in self._selected:
            name = f"{m['first_name']} {m['last_name']}"
            row  = tk.Frame(self._sel_frame, bg=WHITE)
            row.pack(fill="x")

            tk.Label(
                row, text=name,
                bg=WHITE, fg=BLACK,
                font=("Helvetica", 16),
                padx=16, pady=12,
                anchor="w",
            ).pack(side="left", fill="x", expand=True)

            tk.Button(
                row, text="✕",
                command=lambda mid=m["id"]: self._remove_member(mid),
                bg=RED, fg=WHITE,
                font=("Helvetica", 14, "bold"),
                relief="flat", bd=0, cursor="hand2",
                padx=18, pady=12,
            ).pack(side="right")

            tk.Frame(self._sel_frame, bg="#e0e0e0", height=1).pack(fill="x")

    # ── Enter ─────────────────────────────────────────────────────────────────

    def _on_enter(self):
        if not self._selected:
            return
        members = list(self._selected)
        alerts = database.get_alerts_for_members([m["id"] for m in members])
        if alerts:
            self._show_alerts_popup(alerts, members)
        else:
            self.app.show_screen("signature", members=members)

    def _show_alerts_popup(self, alerts, members):
        popup = PopupOverlay(self.winfo_toplevel(), title="ALERT",
                              is_error=True, width=560)
        popup.set_message("\n\n".join(a["message"] for a in alerts))

        def _dismiss():
            popup.destroy()
            self.app.show_screen("signature", members=members)

        popup.add_button("Dismiss", _dismiss)

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def on_show(self, **_):
        self._selected = []
        self._render_selected()
        self._search_var.set("")
        self._all_members = database.search_members("")
        self._hide_dropdown()
