# screens/run_sheets_screen.py — Run Sheet Sign-In Screen
# Search run sheets → load pupils → sign in/out via signature screen

import tkinter as tk

import database
from components.widgets import Divider

CREAM = "#FFFCF7"
PURPLE = "#372976"
RED = "#BB2233"
BLACK = "#000000"
WHITE = "#FFFFFF"
GREEN = "#27ae60"


class RunSheetsScreen(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=CREAM)
        self.app = app
        self._search_after = None
        self._selected = []  # pupils in right panel
        self._all_runs = []  # all run groups from DB
        self._dropdown_open = False
        self._current_run_id = None  # which run sheet is loaded
        self._build_ui()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        W, H = 1280, 720
        LEFT_W = int(W * 0.55)  # 704
        RIGHT_W = W - LEFT_W  # 576

        # ══════════════════════════════════════════════════════════════════════
        # LEFT PANEL
        # ══════════════════════════════════════════════════════════════════════
        self._left = tk.Frame(self, bg=CREAM)
        self._left.place(x=0, y=0, width=LEFT_W, height=H)

        tk.Label(
            self._left,
            text="Run Sheets",
            bg=CREAM,
            fg=BLACK,
            font=("Helvetica", 13),
        ).place(x=16, y=12)

        tk.Label(
            self._left,
            text="Search run",
            bg=CREAM,
            fg=BLACK,
            font=("Helvetica", 22, "bold"),
        ).place(x=60, y=50)

        # Search entry
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", self._on_search_change)

        self._entry_x = 60
        self._entry_y = 100
        self._entry_w = LEFT_W - 120

        self._search_entry = tk.Entry(
            self._left,
            textvariable=self._search_var,
            font=("Helvetica", 16),
            relief="flat",
            bd=0,
            highlightthickness=2,
            highlightbackground=PURPLE,
            highlightcolor=PURPLE,
            bg=WHITE,
            fg=BLACK,
            insertbackground=BLACK,
        )
        self._search_entry.place(
            x=self._entry_x,
            y=self._entry_y,
            width=self._entry_w,
            height=44,
        )
        self._search_entry.bind("<FocusIn>", self._on_entry_focus)
        self._search_entry.bind("<FocusOut>", self._on_entry_blur)

        # Dropdown (run sheet list)
        self._dropdown_outer = tk.Frame(
            self._left,
            bg=WHITE,
            highlightthickness=2,
            highlightbackground=PURPLE,
        )
        self._dropdown_canvas = tk.Canvas(
            self._dropdown_outer, bg=WHITE, highlightthickness=0
        )
        dd_sb = tk.Scrollbar(
            self._dropdown_outer,
            orient="vertical", width=30,
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

        # ── Bottom buttons ────────────────────────────────────────────────────
        btn_y = H - 70

        tk.Button(
            self._left,
            text="Back",
            command=lambda: self.app.show_screen("options"),
            bg=PURPLE,
            fg=WHITE,
            font=("Helvetica", 14, "bold"),
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=24,
            pady=12,
        ).place(x=60, y=btn_y)

        tk.Button(
            self._left,
            text="Add another",
            command=self._open_add_extra,
            bg=PURPLE,
            fg=WHITE,
            font=("Helvetica", 14, "bold"),
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=24,
            pady=12,
        ).place(x=180, y=btn_y)

        tk.Button(
            self._left,
            text="Enter",
            command=self._on_enter,
            bg=PURPLE,
            fg=WHITE,
            font=("Helvetica", 14, "bold"),
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=24,
            pady=12,
        ).place(x=360, y=btn_y)

        # ── Add-extra pupil sub-panel (hidden by default) ─────────────────────
        self._extra_panel = tk.Frame(
            self._left,
            bg=WHITE,
            highlightthickness=2,
            highlightbackground=PURPLE,
        )
        # Not shown yet — placed below "Add another" button area

        self._extra_search_var = tk.StringVar()
        self._extra_search_var.trace_add("write", self._on_extra_search_change)

        tk.Label(
            self._extra_panel,
            text="Add pupil (temporary):",
            bg=WHITE,
            fg=BLACK,
            font=("Helvetica", 12, "bold"),
            padx=8,
            pady=4,
        ).pack(anchor="w")

        self._extra_entry = tk.Entry(
            self._extra_panel,
            textvariable=self._extra_search_var,
            font=("Helvetica", 14),
            relief="flat",
            bd=0,
            highlightthickness=2,
            highlightbackground=PURPLE,
            bg=WHITE,
            fg=BLACK,
            insertbackground=BLACK,
        )
        self._extra_entry.pack(fill="x", padx=8, ipady=8, pady=(0, 4))

        self._extra_list_frame = tk.Frame(self._extra_panel, bg=WHITE)
        self._extra_list_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self._extra_open = False

        # ══════════════════════════════════════════════════════════════════════
        # RIGHT PANEL — selected pupils
        # ══════════════════════════════════════════════════════════════════════
        right = tk.Frame(self, bg=CREAM)
        right.place(x=LEFT_W, y=0, width=RIGHT_W, height=H)

        hdr = tk.Frame(right, bg=CREAM)
        hdr.place(x=24, y=20, width=RIGHT_W - 48, height=36)

        tk.Label(
            hdr,
            text="Selected Pupils",
            bg=CREAM,
            fg=BLACK,
            font=("Helvetica", 18, "bold"),
        ).pack(side="left")

        tk.Label(
            hdr,
            text="(AUTO SORT)",
            bg=CREAM,
            fg=RED,
            font=("Helvetica", 12),
        ).pack(side="right")

        tk.Frame(right, bg="#cccccc", height=1).place(x=24, y=60, width=RIGHT_W - 48)

        sel_outer = tk.Frame(
            right,
            bg=WHITE,
            highlightthickness=2,
            highlightbackground=PURPLE,
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

    # ── Run sheet dropdown ─────────────────────────────────────────────────────

    def _on_entry_focus(self, _):
        self._show_dropdown()

    def _on_entry_blur(self, _):
        self.after(200, self._hide_dropdown)

    def _show_dropdown(self):
        self._dropdown_open = True
        self._populate_dropdown(self._get_filtered_runs())
        drop_y = self._entry_y + 44
        self._dropdown_outer.place(
            x=self._entry_x,
            y=drop_y,
            width=self._entry_w,
            height=260,
        )
        self._dropdown_outer.lift()

    def _hide_dropdown(self):
        self._dropdown_open = False
        self._dropdown_outer.place_forget()

    def _on_search_change(self, *_):
        if self._search_after:
            self.after_cancel(self._search_after)
        self._search_after = self.after(100, self._do_search)

    def _do_search(self):
        if not self._dropdown_open:
            self._show_dropdown()
        else:
            self._populate_dropdown(self._get_filtered_runs())

    def _get_filtered_runs(self):
        q = self._search_var.get().strip().lower()
        if not q:
            return list(self._all_runs)
        return [r for r in self._all_runs if q in r["name"].lower()]

    def _populate_dropdown(self, runs):
        for w in self._dropdown_frame.winfo_children():
            w.destroy()

        if not runs:
            tk.Label(
                self._dropdown_frame,
                text="No run sheets found.",
                bg=WHITE,
                fg="#888888",
                font=("Helvetica", 13),
                padx=12,
                pady=8,
            ).pack(anchor="w")
            return

        for r in runs:
            row = tk.Frame(self._dropdown_frame, bg=WHITE, cursor="hand2")
            row.pack(fill="x")

            lbl = tk.Label(
                row,
                text=r["name"],
                bg=WHITE,
                fg=BLACK,
                font=("Helvetica", 15),
                padx=14,
                pady=10,
                anchor="w",
            )
            lbl.pack(fill="x")
            tk.Frame(row, bg="#e0e0e0", height=1).pack(fill="x")

            for widget in (row, lbl):
                widget.bind(
                    "<Enter>",
                    lambda e, r2=row, l2=lbl: (
                        r2.configure(bg="#f0eeff"),
                        l2.configure(bg="#f0eeff"),
                    ),
                )
                widget.bind(
                    "<Leave>",
                    lambda e, r2=row, l2=lbl: (
                        r2.configure(bg=WHITE),
                        l2.configure(bg=WHITE),
                    ),
                )
                widget.bind("<ButtonPress-1>", lambda e, run=r: self._load_run(run))

    def _load_run(self, run):
        """Load every pupil on a run sheet, regardless of whether they're
        currently signed in or out — a run sheet is used both for signing a
        group IN and for signing a group OUT (e.g. an afternoon bus run signs
        out pupils who are, by definition, currently signed in), so filtering
        by current status here would make one of those directions impossible.
        Per-member eligibility for whichever direction is chosen is enforced
        later by signature_screen, exactly like the direct sign-in flow."""
        self._hide_dropdown()
        self._search_var.set(run["name"])
        self._current_run_id = run["id"]

        members = database.get_run_members(run["id"])
        self._selected = list(members)
        self._selected.sort(
            key=lambda m: (m["last_name"].lower(), m["first_name"].lower())
        )
        self._render_selected()

    # ── Extra pupil search ────────────────────────────────────────────────────

    def _open_add_extra(self):
        if self._extra_open:
            self._extra_panel.place_forget()
            self._extra_open = False
            return

        # Place just below the top search bar
        self._extra_panel.place(
            x=60,
            y=self._entry_y + 50,
            width=self._entry_w,
            height=200,
        )
        self._extra_panel.lift()
        self._extra_open = True
        self._extra_search_var.set("")
        self._populate_extra_list(database.search_members(""))

    def _on_extra_search_change(self, *_):
        q = self._extra_search_var.get().strip().lower()
        members = database.search_members(q)
        self._populate_extra_list(members)

    def _populate_extra_list(self, members):
        for w in self._extra_list_frame.winfo_children():
            w.destroy()

        selected_ids = {m["id"] for m in self._selected}

        for m in members[:8]:
            already = m["id"] in selected_ids
            name = f"{m['first_name']} {m['last_name']}"

            row = tk.Frame(self._extra_list_frame, bg=WHITE, cursor="hand2")
            row.pack(fill="x")

            lbl = tk.Label(
                row,
                text=name + (" ✓" if already else ""),
                bg=WHITE,
                fg="#aaaaaa" if already else BLACK,
                font=("Helvetica", 13),
                padx=8,
                pady=6,
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
                        "<ButtonPress-1>", lambda e, mem=m: self._add_extra(mem)
                    )

    def _add_extra(self, member):
        if any(m["id"] == member["id"] for m in self._selected):
            return
        self._selected.append(member)
        self._selected.sort(
            key=lambda m: (m["last_name"].lower(), m["first_name"].lower())
        )
        self._render_selected()
        self._populate_extra_list(
            database.search_members(self._extra_search_var.get().strip())
        )

    # ── Selected list ─────────────────────────────────────────────────────────

    def _remove_member(self, member_id):
        self._selected = [m for m in self._selected if m["id"] != member_id]
        self._render_selected()

    def _render_selected(self):
        for w in self._sel_frame.winfo_children():
            w.destroy()

        for m in self._selected:
            name = f"{m['first_name']} {m['last_name']}"
            row = tk.Frame(self._sel_frame, bg=WHITE)
            row.pack(fill="x")

            tk.Label(
                row,
                text=name,
                bg=WHITE,
                fg=BLACK,
                font=("Helvetica", 16),
                padx=16,
                pady=12,
                anchor="w",
            ).pack(side="left", fill="x", expand=True)

            tk.Button(
                row,
                text="✕",
                command=lambda mid=m["id"]: self._remove_member(mid),
                bg=RED,
                fg=WHITE,
                font=("Helvetica", 14, "bold"),
                relief="flat",
                bd=0,
                cursor="hand2",
                padx=18,
                pady=12,
            ).pack(side="right")

            tk.Frame(self._sel_frame, bg="#e0e0e0", height=1).pack(fill="x")

    # ── Enter ─────────────────────────────────────────────────────────────────

    def _on_enter(self):
        if not self._selected:
            return
        self.app.show_screen("signature", members=list(self._selected))

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def on_show(self, **_):
        self._selected = []
        self._current_run_id = None
        self._render_selected()
        self._search_var.set("")
        self._all_runs = database.search_runs("")
        self._hide_dropdown()
        if self._extra_open:
            self._extra_panel.place_forget()
            self._extra_open = False
