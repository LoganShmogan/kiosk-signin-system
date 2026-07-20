# screens/admin_screen.py — Admin Password Gate + Settings Panel
# Now includes: Run Sheet management, Sign-in/out Export

import tkinter as tk
import os
from datetime import datetime, timedelta

import theme
import database
from components.widgets import (
    TouchButton, MutedLabel, FieldLabel, Divider,
    StyledEntry, PopupOverlay, ScrollFrame
)


# ── Export date-range picker ────────────────────────────────────────────────

class _ExportRangeDialog(tk.Toplevel):
    """Small modal asking for an optional From/To date range before exporting
    one person's sign-in history. Leaving both fields blank exports their
    full history, matching the previous (date-range-less) behaviour."""

    def __init__(self, root, person_name, on_confirm):
        super().__init__(root)
        self._on_confirm = on_confirm
        self.overrideredirect(True)
        self.configure(bg=theme.CONTENT_BG,
                       highlightthickness=2,
                       highlightbackground=theme.BORDER_COLOR)
        width, height = 420, 260
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        x, y = (sw - width) // 2, (sh - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.grab_set()

        tk.Frame(self, bg=theme.SUCCESS_BG, height=10).pack(fill="x")

        tk.Label(self, text=f"Export sign-in history — {person_name}",
                 bg=theme.CONTENT_BG, fg=theme.PRIMARY_TEXT,
                 font=theme.F_H3, wraplength=380, justify="left"
                 ).pack(anchor="w", padx=20, pady=(12, 8))

        MutedLabel(self, text="Leave both dates blank to export full history.",
                   bg=theme.CONTENT_BG).pack(anchor="w", padx=20)

        date_row = tk.Frame(self, bg=theme.CONTENT_BG)
        date_row.pack(anchor="w", padx=20, pady=(10, 4))
        FieldLabel(date_row, text="From (YYYY-MM-DD):").pack(side="left", padx=(0, 6))
        self._from = tk.Entry(date_row, width=13, font=theme.F_INPUT,
                              relief="flat", bd=0, highlightthickness=2,
                              highlightbackground=theme.ENT_BORDER,
                              bg=theme.ENT_BG, fg=theme.PRIMARY_TEXT,
                              insertbackground=theme.PRIMARY_TEXT)
        self._from.pack(side="left", ipady=8)
        FieldLabel(date_row, text="  To:").pack(side="left", padx=(10, 6))
        self._to = tk.Entry(date_row, width=13, font=theme.F_INPUT,
                            relief="flat", bd=0, highlightthickness=2,
                            highlightbackground=theme.ENT_BORDER,
                            bg=theme.ENT_BG, fg=theme.PRIMARY_TEXT,
                            insertbackground=theme.PRIMARY_TEXT)
        self._to.pack(side="left", ipady=8)

        qr_row = tk.Frame(self, bg=theme.CONTENT_BG)
        qr_row.pack(anchor="w", padx=20, pady=(6, 4))
        for label, days in [("Today", 0), ("Last 7 days", 6), ("Last 30 days", 29)]:
            TouchButton(qr_row, text=label,
                        command=lambda d=days: self._set_range(d),
                        bg=theme.BORDER_COLOR, fg=theme.PRIMARY_TEXT,
                        hover_bg=theme.BTN_BG,
                        font_cfg=theme.F_TINY).pack(side="left", padx=(0, 6),
                                                    ipady=4, ipadx=6)
        TouchButton(qr_row, text="All history",
                    command=self._clear_range,
                    bg=theme.BORDER_COLOR, fg=theme.PRIMARY_TEXT,
                    hover_bg=theme.BTN_BG,
                    font_cfg=theme.F_TINY).pack(side="left", ipady=4, ipadx=6)

        self._error = MutedLabel(self, text="", bg=theme.CONTENT_BG)
        self._error.pack(anchor="w", padx=20, pady=(4, 0))

        btn_row = tk.Frame(self, bg=theme.CONTENT_BG)
        btn_row.pack(pady=(10, 4))
        TouchButton(btn_row, text="Cancel", command=self.destroy,
                    bg=theme.BTN_BG, fg=theme.SECONDARY_TEXT,
                    hover_bg=theme.BTN_HOVER,
                    font_cfg=theme.F_LABEL).pack(side="left", padx=6, ipady=6, ipadx=10)
        TouchButton(btn_row, text="Export", command=self._confirm,
                    bg=theme.BTN_SUCCESS_BG, fg="white",
                    hover_bg=theme.BTN_SUCCESS_HOV,
                    font_cfg=theme.F_LABEL).pack(side="left", padx=6, ipady=6, ipadx=10)

    def _set_range(self, days_back):
        today = datetime.now().strftime("%Y-%m-%d")
        from_day = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        self._from.delete(0, tk.END)
        self._from.insert(0, from_day)
        self._to.delete(0, tk.END)
        self._to.insert(0, today)

    def _clear_range(self):
        self._from.delete(0, tk.END)
        self._to.delete(0, tk.END)

    def _confirm(self):
        date_from = self._from.get().strip()
        date_to   = self._to.get().strip()
        for val in (date_from, date_to):
            if val:
                try:
                    datetime.strptime(val, "%Y-%m-%d")
                except ValueError:
                    self._error.configure(text="Dates must be in YYYY-MM-DD format.")
                    return
        self.destroy()
        self._on_confirm(date_from, date_to)


# ── Password Gate ─────────────────────────────────────────────────────────────

class AdminPasswordScreen(tk.Frame):

    def __init__(self, parent, app):
        super().__init__(parent, bg=theme.CONTENT_BG)
        self.app = app
        self._build_ui()

    def _build_ui(self):
        bar = tk.Frame(self, bg=theme.PAGE_BG, height=52)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        TouchButton(bar, text="← Back",
                    command=lambda: self.app.show_screen("options"),
                    bg=theme.BTN_ORANGE_BG, fg="white",
                    hover_bg=theme.BTN_ORANGE_HOV,
                    font_cfg=theme.F_LABEL).pack(side="left", padx=12, pady=8)

        tk.Label(bar, text="Admin Access", bg=theme.PAGE_BG,
                 fg="white", font=theme.F_H3).pack(side="left", padx=16)

        outer = tk.Frame(self, bg=theme.CONTENT_BG)
        outer.place(relx=0.5, rely=0.45, anchor="center")

        tk.Label(outer, text="PASSWORD PROTECTED",
                 bg=theme.CONTENT_BG, fg=theme.PRIMARY_TEXT,
                 font=theme.F_H2).pack(pady=(0, 8))
        MutedLabel(outer, text="Enter the admin password to continue.",
                   bg=theme.CONTENT_BG).pack()
        Divider(outer, bg=theme.BORDER_COLOR).pack(fill="x", pady=12)

        self._pw_entry = tk.Entry(outer, show="•", width=24,
                                   font=theme.F_H3, relief="flat", bd=0,
                                   highlightthickness=2,
                                   highlightbackground=theme.ENT_BORDER,
                                   bg=theme.ENT_BG, fg=theme.PRIMARY_TEXT,
                                   insertbackground=theme.PRIMARY_TEXT)
        self._pw_entry.pack(ipady=12, pady=(0, 16))
        self._pw_entry.bind("<Return>", lambda e: self._attempt())

        btn_row = tk.Frame(outer, bg=theme.CONTENT_BG)
        btn_row.pack()
        TouchButton(btn_row, text="Cancel",
                    command=lambda: self.app.show_screen("options"),
                    bg=theme.CONTENT_BG, fg=theme.CREAM_MUTED,
                    hover_bg=theme.BORDER_COLOR,
                    font_cfg=theme.F_LABEL).pack(side="left", padx=6,
                                                  ipady=10, ipadx=14)
        TouchButton(btn_row, text="Enter",
                    command=self._attempt,
                    bg=theme.BTN_BG, fg="white",
                    font_cfg=theme.F_LABEL).pack(side="left", padx=6,
                                                  ipady=10, ipadx=14)

    def _attempt(self):
        pw = self._pw_entry.get()
        if database.check_admin_password(pw):
            self._pw_entry.delete(0, tk.END)
            self.app.show_screen("admin_panel")
        else:
            p = PopupOverlay(self.winfo_toplevel(), is_error=True)
            p.set_message("Incorrect password. Please try again.")
            p.add_button("OK", p.destroy)
            self._pw_entry.delete(0, tk.END)

    def on_show(self, **_):
        self._pw_entry.delete(0, tk.END)
        self.after(100, self._pw_entry.focus_set)


# ── Admin Panel ───────────────────────────────────────────────────────────────

class AdminPanelScreen(tk.Frame):

    def __init__(self, parent, app):
        super().__init__(parent, bg=theme.CONTENT_BG)
        self.app = app
        self._run_member_ids = []   # member IDs being built for new run sheet
        self._editing_run_id = None # None = new, int = editing existing
        self._alert_member_id = None   # selected person for a 'member'-scope alert
        self._alert_runs_cache = []
        self._build_ui()

    def _build_ui(self):
        bar = tk.Frame(self, bg=theme.PAGE_BG, height=52)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        TouchButton(bar, text="← Back",
                    command=lambda: self.app.show_screen("options"),
                    bg=theme.BTN_ORANGE_BG, fg="white",
                    hover_bg=theme.BTN_ORANGE_HOV,
                    font_cfg=theme.F_LABEL).pack(side="left", padx=12, pady=8)

        tk.Label(bar, text="Admin Settings", bg=theme.PAGE_BG,
                 fg="white", font=theme.F_H3).pack(side="left", padx=16)

        scroll = ScrollFrame(self, bg=theme.CONTENT_BG)
        scroll.pack(fill="both", expand=True)
        sf = scroll.inner

        col = tk.Frame(sf, bg=theme.CONTENT_BG)
        col.pack(fill="both", expand=True, padx=24, pady=12)

        # ── Today's log ────────────────────────────────────────────────────────
        self._section(col, "Today's Sign-in Log")

        refresh_row = tk.Frame(col, bg=theme.CONTENT_BG)
        refresh_row.pack(fill="x", pady=(0, 6))
        self._log_date_lbl = tk.Label(refresh_row, text="",
                                       bg=theme.CONTENT_BG, fg=theme.CREAM_MUTED,
                                       font=theme.F_SMALL)
        self._log_date_lbl.pack(side="left")
        TouchButton(refresh_row, text="⟳ Refresh",
                    command=self._load_log,
                    bg=theme.BTN_BG, fg="white",
                    font_cfg=theme.F_TINY).pack(side="right", ipady=4, ipadx=8)

        log_hdr = tk.Frame(col, bg=theme.BTN_BG)
        log_hdr.pack(fill="x")
        for col_name, w in [("Name", 20), ("Dir", 6), ("Time", 10), ("Notes", 20)]:
            tk.Label(log_hdr, text=col_name, bg=theme.BTN_BG, fg="white",
                     font=theme.F_TINY, width=w, anchor="w",
                     padx=6, pady=4).pack(side="left")

        self._log_frame = tk.Frame(col, bg=theme.CONTENT_BG,
                                    highlightthickness=1,
                                    highlightbackground=theme.BORDER_COLOR)
        self._log_frame.pack(fill="x", pady=(0, 12))

        Divider(col, bg=theme.BORDER_COLOR).pack(fill="x", pady=12)

        # ── Member Export ───────────────────────────────────────────────────────
        self._section(col, "Export Member Sign-in Data")

        MutedLabel(col, text=(
            "Exports all members' sign-in and sign-out times (with signatures)\n"
            "to an Excel (.xlsx) file for the selected date range."
        ), bg=theme.CONTENT_BG).pack(anchor="w", pady=(0, 8))

        mem_date_row = tk.Frame(col, bg=theme.CONTENT_BG)
        mem_date_row.pack(anchor="w", pady=(0, 6))

        FieldLabel(mem_date_row, text="From (YYYY-MM-DD):").pack(side="left", padx=(0, 6))
        self._export_from = tk.Entry(mem_date_row, width=13, font=theme.F_INPUT,
                                      relief="flat", bd=0, highlightthickness=2,
                                      highlightbackground=theme.ENT_BORDER,
                                      bg=theme.ENT_BG, fg=theme.PRIMARY_TEXT,
                                      insertbackground=theme.PRIMARY_TEXT)
        self._export_from.pack(side="left", ipady=8)

        FieldLabel(mem_date_row, text="  To:").pack(side="left", padx=(10, 6))
        self._export_to = tk.Entry(mem_date_row, width=13, font=theme.F_INPUT,
                                    relief="flat", bd=0, highlightthickness=2,
                                    highlightbackground=theme.ENT_BORDER,
                                    bg=theme.ENT_BG, fg=theme.PRIMARY_TEXT,
                                    insertbackground=theme.PRIMARY_TEXT)
        self._export_to.pack(side="left", ipady=8)

        mem_qr_row = tk.Frame(col, bg=theme.CONTENT_BG)
        mem_qr_row.pack(anchor="w", pady=(4, 8))
        for label, days in [("Today", 0), ("Last 7 days", 6), ("Last 30 days", 29)]:
            TouchButton(mem_qr_row, text=label,
                        command=lambda d=days: self._set_date_range(d),
                        bg=theme.BORDER_COLOR, fg=theme.PRIMARY_TEXT,
                        hover_bg=theme.BTN_BG,
                        font_cfg=theme.F_TINY).pack(side="left", padx=(0, 6),
                                                    ipady=4, ipadx=8)

        mem_exp_btn_row = tk.Frame(col, bg=theme.CONTENT_BG)
        mem_exp_btn_row.pack(anchor="w")
        TouchButton(mem_exp_btn_row, text="Export Members to Excel (.xlsx)",
                    command=self._do_export,
                    bg=theme.BTN_SUCCESS_BG, fg="white",
                    hover_bg=theme.BTN_SUCCESS_HOV,
                    font_cfg=theme.F_LABEL).pack(side="left", ipady=10, ipadx=12)

        self._export_status = MutedLabel(col, text="", bg=theme.CONTENT_BG)
        self._export_status.pack(anchor="w", pady=6)

        Divider(col, bg=theme.BORDER_COLOR).pack(fill="x", pady=12)

        # ── Staff Export ────────────────────────────────────────────────────────
        self._section(col, "Export Staff Sign-in Data")

        MutedLabel(col, text=(
            "Exports all staff sign-in and sign-out times (with signatures)\n"
            "to an Excel (.xlsx) file for the selected date range."
        ), bg=theme.CONTENT_BG).pack(anchor="w", pady=(0, 8))

        staff_date_row = tk.Frame(col, bg=theme.CONTENT_BG)
        staff_date_row.pack(anchor="w", pady=(0, 6))

        FieldLabel(staff_date_row, text="From (YYYY-MM-DD):").pack(side="left", padx=(0, 6))
        self._staff_export_from = tk.Entry(staff_date_row, width=13, font=theme.F_INPUT,
                                            relief="flat", bd=0, highlightthickness=2,
                                            highlightbackground=theme.ENT_BORDER,
                                            bg=theme.ENT_BG, fg=theme.PRIMARY_TEXT,
                                            insertbackground=theme.PRIMARY_TEXT)
        self._staff_export_from.pack(side="left", ipady=8)

        FieldLabel(staff_date_row, text="  To:").pack(side="left", padx=(10, 6))
        self._staff_export_to = tk.Entry(staff_date_row, width=13, font=theme.F_INPUT,
                                          relief="flat", bd=0, highlightthickness=2,
                                          highlightbackground=theme.ENT_BORDER,
                                          bg=theme.ENT_BG, fg=theme.PRIMARY_TEXT,
                                          insertbackground=theme.PRIMARY_TEXT)
        self._staff_export_to.pack(side="left", ipady=8)

        staff_qr_row = tk.Frame(col, bg=theme.CONTENT_BG)
        staff_qr_row.pack(anchor="w", pady=(4, 8))
        for label, days in [("Last 14 days", 13), ("Last 30 days", 29)]:
            TouchButton(staff_qr_row, text=label,
                        command=lambda d=days: self._set_staff_date_range(d),
                        bg=theme.BORDER_COLOR, fg=theme.PRIMARY_TEXT,
                        hover_bg=theme.BTN_BG,
                        font_cfg=theme.F_TINY).pack(side="left", padx=(0, 6),
                                                    ipady=4, ipadx=8)

        staff_exp_btn_row = tk.Frame(col, bg=theme.CONTENT_BG)
        staff_exp_btn_row.pack(anchor="w")
        TouchButton(staff_exp_btn_row, text="Export Staff to Excel (.xlsx)",
                    command=self._do_staff_export,
                    bg=theme.BTN_SUCCESS_BG, fg="white",
                    hover_bg=theme.BTN_SUCCESS_HOV,
                    font_cfg=theme.F_LABEL).pack(side="left", ipady=10, ipadx=12)

        self._staff_export_status = MutedLabel(col, text="", bg=theme.CONTENT_BG)
        self._staff_export_status.pack(anchor="w", pady=6)

        Divider(col, bg=theme.BORDER_COLOR).pack(fill="x", pady=12)

        # ── Password ────────────────────────────────────────────────────────────
        self._section(col, "Change Admin Password")

        FieldLabel(col, text="New Password").pack(anchor="w")
        self._new_pw = tk.Entry(col, show="•", width=28, font=theme.F_INPUT,
                                 relief="flat", bd=0, highlightthickness=2,
                                 highlightbackground=theme.ENT_BORDER,
                                 bg=theme.ENT_BG, fg=theme.PRIMARY_TEXT,
                                 insertbackground=theme.PRIMARY_TEXT)
        self._new_pw.pack(anchor="w", ipady=10, pady=(0, 6))

        FieldLabel(col, text="Confirm Password").pack(anchor="w")
        self._conf_pw = tk.Entry(col, show="•", width=28, font=theme.F_INPUT,
                                  relief="flat", bd=0, highlightthickness=2,
                                  highlightbackground=theme.ENT_BORDER,
                                  bg=theme.ENT_BG, fg=theme.PRIMARY_TEXT,
                                  insertbackground=theme.PRIMARY_TEXT)
        self._conf_pw.pack(anchor="w", ipady=10, pady=(0, 8))

        TouchButton(col, text="Update Password",
                    command=self._change_pw,
                    bg=theme.BTN_BG, fg="white",
                    font_cfg=theme.F_LABEL).pack(anchor="w", ipady=8, ipadx=12)

        self._pw_status = MutedLabel(col, text="", bg=theme.CONTENT_BG)
        self._pw_status.pack(anchor="w", pady=4)

        Divider(col, bg=theme.BORDER_COLOR).pack(fill="x", pady=12)

        # ── Member management ──────────────────────────────────────────────────
        self._section(col, "Member Management")

        TouchButton(col, text="+ Add New Member",
                    command=lambda: self.app.show_screen("profile", member=None),
                    bg=theme.BTN_SUCCESS_BG, fg="white",
                    hover_bg=theme.BTN_SUCCESS_HOV,
                    font_cfg=theme.F_LABEL).pack(anchor="w", ipady=10, ipadx=12)

        mem_search_row = tk.Frame(col, bg=theme.CONTENT_BG)
        mem_search_row.pack(fill="x", pady=(8, 4))
        self._member_search_var = tk.StringVar()
        self._member_search_var.trace_add("write", self._on_member_search)
        tk.Entry(mem_search_row,
                 textvariable=self._member_search_var,
                 width=28, font=theme.F_INPUT,
                 relief="flat", bd=0, highlightthickness=2,
                 highlightbackground=theme.ENT_BORDER,
                 bg=theme.ENT_BG, fg=theme.PRIMARY_TEXT,
                 insertbackground=theme.PRIMARY_TEXT).pack(side="left", ipady=8, fill="x", expand=True)

        mem_list_hdr = tk.Frame(col, bg=theme.BTN_BG)
        mem_list_hdr.pack(fill="x")
        tk.Label(mem_list_hdr, text="Members", bg=theme.BTN_BG,
                 fg="white", font=theme.F_TINY, padx=8, pady=4,
                 anchor="w").pack(side="left", fill="x", expand=True)

        self._members_list_frame = tk.Frame(col, bg=theme.CONTENT_BG,
                                             highlightthickness=1,
                                             highlightbackground=theme.BORDER_COLOR)
        self._members_list_frame.pack(fill="x", pady=(0, 8))

        Divider(col, bg=theme.BORDER_COLOR).pack(fill="x", pady=12)

        # ── Staff management ───────────────────────────────────────────────────
        self._section(col, "Staff Management")

        TouchButton(col, text="+ Add New Staff Member",
                    command=lambda: self.app.show_screen("staff_profile", staff=None),
                    bg=theme.BTN_SUCCESS_BG, fg="white",
                    hover_bg=theme.BTN_SUCCESS_HOV,
                    font_cfg=theme.F_LABEL).pack(anchor="w", ipady=10, ipadx=12)

        staff_search_row = tk.Frame(col, bg=theme.CONTENT_BG)
        staff_search_row.pack(fill="x", pady=(8, 4))
        self._staff_search_var = tk.StringVar()
        self._staff_search_var.trace_add("write", self._on_staff_search)
        tk.Entry(staff_search_row,
                 textvariable=self._staff_search_var,
                 width=28, font=theme.F_INPUT,
                 relief="flat", bd=0, highlightthickness=2,
                 highlightbackground=theme.ENT_BORDER,
                 bg=theme.ENT_BG, fg=theme.PRIMARY_TEXT,
                 insertbackground=theme.PRIMARY_TEXT).pack(side="left", ipady=8, fill="x", expand=True)

        staff_list_hdr = tk.Frame(col, bg=theme.BTN_BG)
        staff_list_hdr.pack(fill="x")
        tk.Label(staff_list_hdr, text="Staff", bg=theme.BTN_BG,
                 fg="white", font=theme.F_TINY, padx=8, pady=4,
                 anchor="w").pack(side="left", fill="x", expand=True)

        self._staff_list_frame = tk.Frame(col, bg=theme.CONTENT_BG,
                                           highlightthickness=1,
                                           highlightbackground=theme.BORDER_COLOR)
        self._staff_list_frame.pack(fill="x", pady=(0, 8))

        Divider(col, bg=theme.BORDER_COLOR).pack(fill="x", pady=12)

        # ── Run Sheet Management ───────────────────────────────────────────────
        self._section(col, "Run Sheet Management")

        MutedLabel(col, text="Create or edit run sheets and assign pupils to them.",
                   bg=theme.CONTENT_BG).pack(anchor="w", pady=(0, 8))

        # Existing run sheets list
        rs_list_hdr = tk.Frame(col, bg=theme.BTN_BG)
        rs_list_hdr.pack(fill="x")
        tk.Label(rs_list_hdr, text="Existing Run Sheets", bg=theme.BTN_BG,
                 fg="white", font=theme.F_TINY, padx=8, pady=4,
                 anchor="w").pack(side="left", fill="x", expand=True)

        self._runs_list_frame = tk.Frame(col, bg=theme.CONTENT_BG,
                                          highlightthickness=1,
                                          highlightbackground=theme.BORDER_COLOR)
        self._runs_list_frame.pack(fill="x", pady=(0, 8))

        # ── Run sheet editor ───────────────────────────────────────────────────
        editor_frame = tk.Frame(col, bg=theme.CONTENT_BG,
                                 highlightthickness=1,
                                 highlightbackground=theme.BORDER_COLOR,
                                 padx=10, pady=8)
        editor_frame.pack(fill="x", pady=(0, 4))

        self._run_editor_title = tk.Label(editor_frame, text="New Run Sheet",
                                           bg=theme.CONTENT_BG, fg=theme.BTN_BG,
                                           font=theme.F_LABEL)
        self._run_editor_title.pack(anchor="w", pady=(0, 4))

        FieldLabel(editor_frame, text="Run Sheet Name").pack(anchor="w")
        self._run_name_entry = tk.Entry(editor_frame, width=28, font=theme.F_INPUT,
                                         relief="flat", bd=0, highlightthickness=2,
                                         highlightbackground=theme.ENT_BORDER,
                                         bg=theme.ENT_BG, fg=theme.PRIMARY_TEXT,
                                         insertbackground=theme.PRIMARY_TEXT)
        self._run_name_entry.pack(anchor="w", ipady=8, pady=(0, 8))

        FieldLabel(editor_frame, text="Search & Add Pupils").pack(anchor="w")
        self._run_pupil_search_var = tk.StringVar()
        self._run_pupil_search_var.trace_add("write", self._on_run_pupil_search)
        self._run_pupil_entry = tk.Entry(editor_frame,
                                          textvariable=self._run_pupil_search_var,
                                          width=28, font=theme.F_INPUT,
                                          relief="flat", bd=0, highlightthickness=2,
                                          highlightbackground=theme.ENT_BORDER,
                                          bg=theme.ENT_BG, fg=theme.PRIMARY_TEXT,
                                          insertbackground=theme.PRIMARY_TEXT)
        self._run_pupil_entry.pack(anchor="w", ipady=8, pady=(0, 4))

        # Pupil search results
        self._run_pupil_results = tk.Frame(editor_frame, bg=theme.CONTENT_BG,
                                            highlightthickness=1,
                                            highlightbackground=theme.BORDER_COLOR)
        self._run_pupil_results.pack(fill="x", pady=(0, 8))

        # Assigned pupils list
        FieldLabel(editor_frame, text="Assigned Pupils").pack(anchor="w")
        self._run_assigned_frame = tk.Frame(editor_frame, bg=theme.CONTENT_BG,
                                             highlightthickness=1,
                                             highlightbackground=theme.BORDER_COLOR)
        self._run_assigned_frame.pack(fill="x", pady=(0, 8))

        # Save / cancel row
        save_row = tk.Frame(editor_frame, bg=theme.CONTENT_BG)
        save_row.pack(anchor="w")
        TouchButton(save_row, text="Save Run Sheet",
                    command=self._save_run,
                    bg=theme.BTN_SUCCESS_BG, fg="white",
                    hover_bg=theme.BTN_SUCCESS_HOV,
                    font_cfg=theme.F_LABEL).pack(side="left", padx=(0, 8),
                                                  ipady=8, ipadx=10)
        TouchButton(save_row, text="Clear",
                    command=self._clear_run_editor,
                    bg=theme.CONTENT_BG, fg=theme.CREAM_MUTED,
                    hover_bg=theme.BORDER_COLOR,
                    font_cfg=theme.F_LABEL).pack(side="left", ipady=8, ipadx=10)

        self._run_status = MutedLabel(col, text="", bg=theme.CONTENT_BG)
        self._run_status.pack(anchor="w", pady=4)

        Divider(col, bg=theme.BORDER_COLOR).pack(fill="x", pady=12)

        # ── Alerts ──────────────────────────────────────────────────────────────
        self._section(col, "Member / Run Alerts")

        MutedLabel(col, text=(
            "Create a message that pops up on the kiosk sign-in screen when the\n"
            "targeted person(s) are being signed in or out."
        ), bg=theme.CONTENT_BG).pack(anchor="w", pady=(0, 8))

        alert_editor = tk.Frame(col, bg=theme.CONTENT_BG,
                                 highlightthickness=1,
                                 highlightbackground=theme.BORDER_COLOR,
                                 padx=10, pady=8)
        alert_editor.pack(fill="x", pady=(0, 4))

        FieldLabel(alert_editor, text="Applies To").pack(anchor="w")
        scope_row = tk.Frame(alert_editor, bg=theme.CONTENT_BG)
        scope_row.pack(anchor="w", pady=(0, 8))

        self._alert_scope = tk.StringVar(value="all")
        self._alert_scope_btns = {}
        for label, val in [("All Members", "all"), ("A Run", "run"), ("Single Person", "member")]:
            b = TouchButton(scope_row, text=label,
                             command=lambda v=val: self._set_alert_scope(v),
                             bg=theme.BTN_BG, fg="white",
                             font_cfg=theme.F_TINY)
            b.pack(side="left", padx=(0, 6), ipady=6, ipadx=8)
            self._alert_scope_btns[val] = b

        # Run target picker (shown only when scope == 'run')
        self._alert_run_frame = tk.Frame(alert_editor, bg=theme.CONTENT_BG)
        FieldLabel(self._alert_run_frame, text="Run Sheet").pack(anchor="w")
        self._alert_run_var = tk.StringVar()
        self._alert_run_menu = tk.OptionMenu(self._alert_run_frame, self._alert_run_var, "")
        self._alert_run_menu.configure(font=theme.F_INPUT, bg=theme.ENT_BG,
                                        fg=theme.PRIMARY_TEXT, relief="flat",
                                        highlightthickness=1,
                                        highlightbackground=theme.ENT_BORDER)
        self._alert_run_menu.pack(anchor="w", pady=(0, 8), ipady=4)

        # Person target picker (shown only when scope == 'member')
        self._alert_member_frame = tk.Frame(alert_editor, bg=theme.CONTENT_BG)
        FieldLabel(self._alert_member_frame, text="Search Person").pack(anchor="w")
        self._alert_member_search_var = tk.StringVar()
        self._alert_member_search_var.trace_add("write", self._on_alert_member_search)
        tk.Entry(self._alert_member_frame,
                 textvariable=self._alert_member_search_var,
                 width=28, font=theme.F_INPUT,
                 relief="flat", bd=0, highlightthickness=2,
                 highlightbackground=theme.ENT_BORDER,
                 bg=theme.ENT_BG, fg=theme.PRIMARY_TEXT,
                 insertbackground=theme.PRIMARY_TEXT).pack(anchor="w", ipady=8, pady=(0, 4))
        self._alert_member_results = tk.Frame(self._alert_member_frame, bg=theme.CONTENT_BG,
                                               highlightthickness=1,
                                               highlightbackground=theme.BORDER_COLOR)
        self._alert_member_results.pack(fill="x", pady=(0, 4))
        self._alert_member_selected_lbl = MutedLabel(
            self._alert_member_frame, text="No one selected.", bg=theme.CONTENT_BG)
        self._alert_member_selected_lbl.pack(anchor="w", pady=(0, 8))

        alert_msg_label = FieldLabel(alert_editor, text="Message")
        alert_msg_label.pack(anchor="w")
        self._alert_message_anchor = alert_msg_label
        self._alert_message = tk.Text(alert_editor, width=40, height=3, font=theme.F_INPUT,
                                       relief="flat", bd=0, highlightthickness=2,
                                       highlightbackground=theme.ENT_BORDER,
                                       bg=theme.ENT_BG, fg=theme.PRIMARY_TEXT,
                                       insertbackground=theme.PRIMARY_TEXT, wrap="word")
        self._alert_message.pack(anchor="w", pady=(0, 8), fill="x")

        FieldLabel(alert_editor, text="Stay Up For").pack(anchor="w")
        duration_row = tk.Frame(alert_editor, bg=theme.CONTENT_BG)
        duration_row.pack(anchor="w", pady=(0, 8))

        self._alert_expiry_unit = tk.StringVar(value="Hours")
        self._alert_expiry_menu = tk.OptionMenu(duration_row, self._alert_expiry_unit,
                                                 "No expiry", "Hours", "Days", "Weeks", "Months")
        self._alert_expiry_menu.configure(font=theme.F_INPUT, bg=theme.ENT_BG,
                                           fg=theme.PRIMARY_TEXT, relief="flat",
                                           highlightthickness=1,
                                           highlightbackground=theme.ENT_BORDER)
        self._alert_expiry_menu.pack(side="left", ipady=4, padx=(0, 6))

        self._alert_expiry_amount_var = tk.StringVar(value="24")
        tk.Entry(duration_row, textvariable=self._alert_expiry_amount_var,
                 width=6, font=theme.F_INPUT,
                 relief="flat", bd=0, highlightthickness=2,
                 highlightbackground=theme.ENT_BORDER,
                 bg=theme.ENT_BG, fg=theme.PRIMARY_TEXT,
                 insertbackground=theme.PRIMARY_TEXT).pack(side="left", ipady=8)

        TouchButton(alert_editor, text="Create Alert",
                    command=self._save_alert,
                    bg=theme.BTN_SUCCESS_BG, fg="white",
                    hover_bg=theme.BTN_SUCCESS_HOV,
                    font_cfg=theme.F_LABEL).pack(anchor="w", ipady=8, ipadx=12)

        self._alert_status = MutedLabel(col, text="", bg=theme.CONTENT_BG)
        self._alert_status.pack(anchor="w", pady=4)

        alert_list_hdr = tk.Frame(col, bg=theme.BTN_BG)
        alert_list_hdr.pack(fill="x")
        tk.Label(alert_list_hdr, text="Active Alerts", bg=theme.BTN_BG,
                 fg="white", font=theme.F_TINY, padx=8, pady=4,
                 anchor="w").pack(side="left", fill="x", expand=True)

        self._alerts_list_frame = tk.Frame(col, bg=theme.CONTENT_BG,
                                            highlightthickness=1,
                                            highlightbackground=theme.BORDER_COLOR)
        self._alerts_list_frame.pack(fill="x", pady=(0, 8))

        Divider(col, bg=theme.BORDER_COLOR).pack(fill="x", pady=12)

        # ── Holiday periods ────────────────────────────────────────────────────
        self._section(col, "Holiday Periods")
        MutedLabel(col, text="Manage holiday period enrollment.",
                   bg=theme.CONTENT_BG).pack(anchor="w", pady=(0, 8))
        TouchButton(col, text="Manage Holiday Enrollment",
                    command=lambda: self.app.show_screen("holiday_enrollment"),
                    bg=theme.BTN_BG, fg="white",
                    font_cfg=theme.F_LABEL).pack(anchor="w", ipady=8, ipadx=12)

    # ── Section helper ─────────────────────────────────────────────────────────

    def _section(self, parent, title):
        tk.Label(parent, text=title, bg=theme.CONTENT_BG,
                 fg=theme.BTN_BG, font=theme.F_H3).pack(anchor="w", pady=(12, 2))
        Divider(parent, bg=theme.BORDER_COLOR).pack(fill="x", pady=(0, 8))

    # ── Today's log ────────────────────────────────────────────────────────────

    def _load_log(self):
        _now = datetime.now()
        today = _now.strftime("%A") + " " + str(_now.day) + _now.strftime(" %B %Y")
        self._log_date_lbl.configure(text=today)
        for w in self._log_frame.winfo_children():
            w.destroy()
        signs = database.get_today_signs()
        if not signs:
            MutedLabel(self._log_frame, text="No sign-ins today.",
                       bg=theme.CONTENT_BG).pack(pady=8, padx=8)
            return
        for i, s in enumerate(signs):
            row_bg = "#F0EDE8" if i % 2 == 0 else theme.CONTENT_BG
            row = tk.Frame(self._log_frame, bg=row_bg)
            row.pack(fill="x")
            name  = f"{s['first_name']} {s['last_name']}"
            ts    = s.get("timestamp", "")
            time_ = ts[11:16] if len(ts) >= 16 else ts
            direc = s.get("direction", "")
            notes = (s.get("notes", "") or "")[:30]
            dir_fg = theme.BTN_SUCCESS_BG if direc == "IN" else theme.BTN_DANGER_BG
            for text, w, fg in [
                (name,  20, theme.PRIMARY_TEXT),
                (direc,  6, dir_fg),
                (time_, 10, theme.PRIMARY_TEXT),
                (notes, 20, theme.CREAM_MUTED),
            ]:
                tk.Label(row, text=text, bg=row_bg, fg=fg,
                         font=theme.F_TINY, width=w, anchor="w",
                         padx=6, pady=5).pack(side="left")

    # ── Password ───────────────────────────────────────────────────────────────

    def _change_pw(self):
        new  = self._new_pw.get()
        conf = self._conf_pw.get()
        if not new:
            self._pw_status.configure(text="Password cannot be empty.")
            return
        if new != conf:
            self._pw_status.configure(text="Passwords do not match.")
            return
        if len(new) < 6:
            self._pw_status.configure(text="Must be at least 6 characters.")
            return
        database.set_admin_password(new)
        self._new_pw.delete(0, tk.END)
        self._conf_pw.delete(0, tk.END)
        self._pw_status.configure(text="✓ Password updated.")

    # ── Export ─────────────────────────────────────────────────────────────────

    def _set_date_range(self, days_back: int):
        today    = datetime.now().strftime("%Y-%m-%d")
        from_day = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        self._export_from.delete(0, tk.END)
        self._export_from.insert(0, from_day)
        self._export_to.delete(0, tk.END)
        self._export_to.insert(0, today)

    def _set_staff_date_range(self, days_back: int):
        today    = datetime.now().strftime("%Y-%m-%d")
        from_day = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        self._staff_export_from.delete(0, tk.END)
        self._staff_export_from.insert(0, from_day)
        self._staff_export_to.delete(0, tk.END)
        self._staff_export_to.insert(0, today)

    def _do_export(self):
        date_from = self._export_from.get().strip()
        date_to   = self._export_to.get().strip()

        try:
            datetime.strptime(date_from, "%Y-%m-%d")
            datetime.strptime(date_to,   "%Y-%m-%d")
        except ValueError:
            self._export_status.configure(
                text="✗ Invalid date format. Use YYYY-MM-DD.")
            return

        self._export_status.configure(text="Generating export…")
        self.update_idletasks()

        try:
            import export_util
            signs = database.get_signs_for_export(date_from, date_to)

            if not signs:
                self._export_status.configure(
                    text="No sign-in data found for that date range.")
                return

            home     = os.path.expanduser("~")
            filename = f"Members_Export_{date_from}_to_{date_to}.xlsx"
            out_path = os.path.join(home, filename)

            export_util.generate_export(signs, date_from, date_to, out_path)
            self._export_status.configure(text=f"✓ Saved: {out_path}")
        except Exception as exc:
            self._export_status.configure(
                text=f"✗ Export failed: {str(exc)[:80]}")

    def _do_staff_export(self):
        date_from = self._staff_export_from.get().strip()
        date_to   = self._staff_export_to.get().strip()

        try:
            datetime.strptime(date_from, "%Y-%m-%d")
            datetime.strptime(date_to,   "%Y-%m-%d")
        except ValueError:
            self._staff_export_status.configure(
                text="✗ Invalid date format. Use YYYY-MM-DD.")
            return

        self._staff_export_status.configure(text="Generating export…")
        self.update_idletasks()

        try:
            import export_util
            signs = database.get_staff_signs_for_export(date_from, date_to)

            if not signs:
                self._staff_export_status.configure(
                    text="No staff sign-in data found for that date range.")
                return

            home     = os.path.expanduser("~")
            filename = f"Staff_Export_{date_from}_to_{date_to}.xlsx"
            out_path = os.path.join(home, filename)

            export_util.generate_staff_export(signs, date_from, date_to, out_path)
            self._staff_export_status.configure(text=f"✓ Saved: {out_path}")
        except Exception as exc:
            self._staff_export_status.configure(
                text=f"✗ Export failed: {str(exc)[:80]}")

    def _prompt_export_dates(self, person, is_staff):
        name = f"{person['first_name']} {person['last_name']}"
        _ExportRangeDialog(
            self.winfo_toplevel(), name,
            lambda date_from, date_to: self._export_single_person(
                person, is_staff, date_from, date_to))

    def _export_single_person(self, person, is_staff, date_from="", date_to=""):
        """Export one person's sign-in/out history to Excel, same layout as
        the bulk member/staff exports. date_from/date_to are optional — when
        both are blank, the person's full history is exported."""
        name = f"{person['first_name']} {person['last_name']}"

        try:
            import export_util
            signs = database.get_signs_for_member(
                person["id"], date_from or None, date_to or None)

            if not signs:
                range_msg = (f" between {date_from} and {date_to}"
                             if (date_from or date_to) else "")
                p = PopupOverlay(self.winfo_toplevel(), is_error=True)
                p.set_message(f"No sign-in records found for {name}{range_msg}.")
                p.add_button("OK", p.destroy)
                return

            dates = [s["timestamp"][:10] for s in signs]
            export_from = date_from or min(dates)
            export_to   = date_to or max(dates)

            home       = os.path.expanduser("~")
            safe_name  = name.replace(" ", "_")
            if date_from or date_to:
                filename = f"{safe_name}_SignIn_History_{export_from}_to_{export_to}.xlsx"
            else:
                filename = f"{safe_name}_SignIn_History.xlsx"
            out_path   = os.path.join(home, filename)

            if is_staff:
                export_util.generate_staff_export(signs, export_from, export_to, out_path)
            else:
                export_util.generate_export(signs, export_from, export_to, out_path)

            p = PopupOverlay(self.winfo_toplevel())
            p.set_message(f"Sign-in history for {name} saved to:\n{out_path}")
            p.add_button("OK", p.destroy)
        except Exception as exc:
            p = PopupOverlay(self.winfo_toplevel(), is_error=True)
            p.set_message(f"Export failed: {str(exc)[:120]}")
            p.add_button("OK", p.destroy)

    # ── Member management ──────────────────────────────────────────────────────

    def _on_member_search(self, *_):
        self._load_members_list(self._member_search_var.get().strip())

    def _load_members_list(self, query=""):
        for w in self._members_list_frame.winfo_children():
            w.destroy()

        members = database.search_members(query, "member")
        if not members:
            MutedLabel(self._members_list_frame,
                       text="No members found.",
                       bg=theme.CONTENT_BG).pack(pady=6, padx=8, anchor="w")
            return

        for m in members:
            row = tk.Frame(self._members_list_frame, bg=theme.CONTENT_BG)
            row.pack(fill="x", padx=4, pady=2)
            name = f"{m['first_name']} {m['last_name']}"
            tk.Label(row, text=name,
                     bg=theme.CONTENT_BG, fg=theme.PRIMARY_TEXT,
                     font=theme.F_BODY, anchor="w").pack(side="left", padx=(4, 0), fill="x", expand=True)
            TouchButton(row, text="Edit",
                        command=lambda mem=m: self.app.show_screen("profile", member=mem),
                        bg=theme.BTN_BG, fg="white",
                        font_cfg=theme.F_TINY).pack(side="right", padx=4,
                                                    ipady=2, ipadx=6)
            TouchButton(row, text="Export",
                        command=lambda mem=m: self._prompt_export_dates(mem, is_staff=False),
                        bg=theme.BTN_SUCCESS_BG, fg="white",
                        hover_bg=theme.BTN_SUCCESS_HOV,
                        font_cfg=theme.F_TINY).pack(side="right", padx=4,
                                                    ipady=2, ipadx=6)

    # ── Staff management ───────────────────────────────────────────────────────

    def _on_staff_search(self, *_):
        self._load_staff_list(self._staff_search_var.get().strip())

    def _load_staff_list(self, query=""):
        for w in self._staff_list_frame.winfo_children():
            w.destroy()

        staff = database.search_staff(query)
        if not staff:
            MutedLabel(self._staff_list_frame,
                       text="No staff members found.",
                       bg=theme.CONTENT_BG).pack(pady=6, padx=8, anchor="w")
            return

        for s in staff:
            row = tk.Frame(self._staff_list_frame, bg=theme.CONTENT_BG)
            row.pack(fill="x", padx=4, pady=2)
            name = f"{s['first_name']} {s['last_name']}"
            role = s.get("school") or ""
            display = f"{name}  —  {role}" if role else name
            tk.Label(row, text=display,
                     bg=theme.CONTENT_BG, fg=theme.PRIMARY_TEXT,
                     font=theme.F_BODY, anchor="w").pack(side="left", padx=(4, 0), fill="x", expand=True)
            TouchButton(row, text="Edit",
                        command=lambda st=s: self.app.show_screen("staff_profile", staff=st),
                        bg=theme.BTN_BG, fg="white",
                        font_cfg=theme.F_TINY).pack(side="right", padx=4,
                                                    ipady=2, ipadx=6)
            TouchButton(row, text="Export",
                        command=lambda st=s: self._prompt_export_dates(st, is_staff=True),
                        bg=theme.BTN_SUCCESS_BG, fg="white",
                        hover_bg=theme.BTN_SUCCESS_HOV,
                        font_cfg=theme.F_TINY).pack(side="right", padx=4,
                                                    ipady=2, ipadx=6)

    # ── Run sheet management ───────────────────────────────────────────────────

    def _load_runs_list(self):
        """Refresh the existing run sheets panel."""
        for w in self._runs_list_frame.winfo_children():
            w.destroy()

        runs = database.search_runs("")
        if not runs:
            MutedLabel(self._runs_list_frame,
                       text="No run sheets yet.",
                       bg=theme.CONTENT_BG).pack(pady=6, padx=8, anchor="w")
            return

        for run in runs:
            row = tk.Frame(self._runs_list_frame, bg=theme.CONTENT_BG)
            row.pack(fill="x", padx=4, pady=2)

            members = database.get_run_members(run["id"])
            count   = len(members)

            tk.Label(row, text=run["name"],
                     bg=theme.CONTENT_BG, fg=theme.PRIMARY_TEXT,
                     font=theme.F_BODY, anchor="w").pack(side="left", padx=(4, 0))
            tk.Label(row, text=f"({count} pupil{'s' if count != 1 else ''})",
                     bg=theme.CONTENT_BG, fg=theme.CREAM_MUTED,
                     font=theme.F_SMALL).pack(side="left", padx=4)

            TouchButton(row, text="Edit",
                        command=lambda r=run: self._edit_run(r),
                        bg=theme.BTN_BG, fg="white",
                        font_cfg=theme.F_TINY).pack(side="right", padx=(4, 0),
                                                    ipady=2, ipadx=6)
            TouchButton(row, text="Delete",
                        command=lambda r=run: self._confirm_delete_run(r),
                        bg=theme.BTN_DANGER_BG, fg="white",
                        hover_bg=theme.BTN_DANGER_HOV,
                        font_cfg=theme.F_TINY).pack(side="right", padx=4,
                                                    ipady=2, ipadx=6)

    def _on_run_pupil_search(self, *_):
        q = self._run_pupil_search_var.get().strip()
        members = database.search_members(q)
        self._render_pupil_results(members)

    def _render_pupil_results(self, members):
        for w in self._run_pupil_results.winfo_children():
            w.destroy()

        for m in members[:6]:
            already = m["id"] in self._run_member_ids
            name    = f"{m['first_name']} {m['last_name']}"
            row     = tk.Frame(self._run_pupil_results,
                               bg=theme.CONTENT_BG, cursor="hand2")
            row.pack(fill="x")
            lbl = tk.Label(row,
                           text=name + (" ✓" if already else ""),
                           bg=theme.CONTENT_BG,
                           fg=theme.CREAM_MUTED if already else theme.PRIMARY_TEXT,
                           font=theme.F_SMALL, padx=6, pady=4, anchor="w")
            lbl.pack(fill="x")
            tk.Frame(row, bg=theme.BORDER_COLOR, height=1).pack(fill="x")

            if not already:
                for widget in (row, lbl):
                    widget.bind("<Enter>",
                        lambda e, r=row, l=lbl: (
                            r.configure(bg=theme.BORDER_COLOR),
                            l.configure(bg=theme.BORDER_COLOR)))
                    widget.bind("<Leave>",
                        lambda e, r=row, l=lbl: (
                            r.configure(bg=theme.CONTENT_BG),
                            l.configure(bg=theme.CONTENT_BG)))
                    widget.bind("<ButtonPress-1>",
                        lambda e, mem=m: self._add_to_run(mem))

    def _add_to_run(self, member):
        if member["id"] not in self._run_member_ids:
            self._run_member_ids.append(member["id"])
        self._render_assigned()
        self._run_pupil_search_var.set("")

    def _render_assigned(self):
        for w in self._run_assigned_frame.winfo_children():
            w.destroy()

        if not self._run_member_ids:
            MutedLabel(self._run_assigned_frame,
                       text="No pupils assigned yet.",
                       bg=theme.CONTENT_BG).pack(pady=4, padx=6, anchor="w")
            return

        for mid in self._run_member_ids:
            m = database.get_member(mid)
            if not m:
                continue
            name = f"{m['first_name']} {m['last_name']}"
            row  = tk.Frame(self._run_assigned_frame, bg=theme.CONTENT_BG)
            row.pack(fill="x", padx=4, pady=1)
            tk.Label(row, text=name, bg=theme.CONTENT_BG,
                     fg=theme.PRIMARY_TEXT, font=theme.F_SMALL,
                     anchor="w").pack(side="left", fill="x", expand=True, padx=4)
            TouchButton(row, text="✕",
                        command=lambda m_id=mid: self._remove_from_run(m_id),
                        bg=theme.BTN_DANGER_BG, fg="white",
                        hover_bg=theme.BTN_DANGER_HOV,
                        font_cfg=theme.F_TINY).pack(side="right", ipady=2, ipadx=4)

    def _remove_from_run(self, member_id):
        self._run_member_ids = [m for m in self._run_member_ids if m != member_id]
        self._render_assigned()

    def _edit_run(self, run):
        self._editing_run_id = run["id"]
        self._run_editor_title.configure(text=f"Editing: {run['name']}")
        self._run_name_entry.delete(0, tk.END)
        self._run_name_entry.insert(0, run["name"])
        members = database.get_run_members(run["id"])
        self._run_member_ids = [m["id"] for m in members]
        self._render_assigned()
        self._run_status.configure(text="")

    def _clear_run_editor(self):
        self._editing_run_id = None
        self._run_editor_title.configure(text="New Run Sheet")
        self._run_name_entry.delete(0, tk.END)
        self._run_member_ids = []
        self._render_assigned()
        self._run_pupil_search_var.set("")
        self._run_status.configure(text="")

    def _save_run(self):
        name = self._run_name_entry.get().strip()
        if not name:
            self._run_status.configure(text="Run sheet name is required.")
            return
        if not self._run_member_ids:
            self._run_status.configure(text="Assign at least one pupil.")
            return

        database.upsert_run(name, self._run_member_ids)
        self._run_status.configure(text=f"✓ Run sheet '{name}' saved.")
        self._clear_run_editor()
        self._load_runs_list()

    def _confirm_delete_run(self, run):
        p = PopupOverlay(self.winfo_toplevel(), is_error=True, width=500)
        p.set_message(
            f"Permanently delete run sheet '{run['name']}'?\n"
            "Pupils will not be deleted — only the run sheet."
        )
        p.add_button("Cancel", p.destroy)
        p.add_button("Delete",
                     lambda: (database.delete_run(run["id"]),
                              p.destroy(),
                              self._load_runs_list(),
                              self._run_status.configure(
                                  text=f"Deleted '{run['name']}'.")),
                     bg=theme.BTN_DANGER_BG, fg="white",
                     hover_bg=theme.BTN_DANGER_HOV)

    # ── Alerts ─────────────────────────────────────────────────────────────────

    def _set_alert_scope(self, scope):
        self._alert_scope.set(scope)
        for val, btn in self._alert_scope_btns.items():
            if val == scope:
                btn.update_colors(theme.BTN_SUCCESS_BG, theme.BTN_SUCCESS_HOV)
            else:
                btn.update_colors(theme.BTN_BG, theme.BTN_HOVER)

        self._alert_run_frame.pack_forget()
        self._alert_member_frame.pack_forget()
        if scope == "run":
            self._refresh_alert_run_menu()
            self._alert_run_frame.pack(anchor="w", fill="x",
                                        before=self._alert_message_anchor)
        elif scope == "member":
            self._alert_member_frame.pack(anchor="w", fill="x",
                                           before=self._alert_message_anchor)

    def _refresh_alert_run_menu(self):
        self._alert_runs_cache = database.search_runs("")
        menu = self._alert_run_menu["menu"]
        menu.delete(0, "end")
        if not self._alert_runs_cache:
            self._alert_run_var.set("No run sheets yet")
            return
        self._alert_run_var.set(self._alert_runs_cache[0]["name"])
        for r in self._alert_runs_cache:
            menu.add_command(label=r["name"],
                              command=lambda v=r["name"]: self._alert_run_var.set(v))

    def _on_alert_member_search(self, *_):
        q = self._alert_member_search_var.get().strip()
        self._render_alert_member_results(database.search_members(q))

    def _render_alert_member_results(self, members):
        for w in self._alert_member_results.winfo_children():
            w.destroy()

        for m in members[:6]:
            name = f"{m['first_name']} {m['last_name']}"
            row  = tk.Frame(self._alert_member_results,
                            bg=theme.CONTENT_BG, cursor="hand2")
            row.pack(fill="x")
            lbl = tk.Label(row, text=name, bg=theme.CONTENT_BG,
                           fg=theme.PRIMARY_TEXT, font=theme.F_SMALL,
                           padx=6, pady=4, anchor="w")
            lbl.pack(fill="x")
            tk.Frame(row, bg=theme.BORDER_COLOR, height=1).pack(fill="x")

            for widget in (row, lbl):
                widget.bind("<Enter>",
                    lambda e, r=row, l=lbl: (
                        r.configure(bg=theme.BORDER_COLOR),
                        l.configure(bg=theme.BORDER_COLOR)))
                widget.bind("<Leave>",
                    lambda e, r=row, l=lbl: (
                        r.configure(bg=theme.CONTENT_BG),
                        l.configure(bg=theme.CONTENT_BG)))
                widget.bind("<ButtonPress-1>",
                    lambda e, mem=m: self._select_alert_member(mem))

    def _select_alert_member(self, member):
        self._alert_member_id = member["id"]
        self._alert_member_selected_lbl.configure(
            text=f"Selected: {member['first_name']} {member['last_name']}")
        self._alert_member_search_var.set("")

    _ALERT_UNIT_HOURS = {"Hours": 1, "Days": 24, "Weeks": 168, "Months": 720}

    def _save_alert(self):
        scope   = self._alert_scope.get()
        message = self._alert_message.get("1.0", "end").strip()
        if not message:
            self._alert_status.configure(text="Alert message cannot be empty.")
            return

        target_id = None
        if scope == "run":
            name = self._alert_run_var.get()
            run  = next((r for r in self._alert_runs_cache if r["name"] == name), None)
            if not run:
                self._alert_status.configure(text="Select a run sheet.")
                return
            target_id = run["id"]
        elif scope == "member":
            if not self._alert_member_id:
                self._alert_status.configure(text="Search and select a person.")
                return
            target_id = self._alert_member_id

        duration_hours = None
        unit = self._alert_expiry_unit.get()
        if unit != "No expiry":
            try:
                amount = float(self._alert_expiry_amount_var.get())
            except ValueError:
                amount = 0
            if amount <= 0:
                self._alert_status.configure(text="Enter a valid duration.")
                return
            duration_hours = amount * self._ALERT_UNIT_HOURS[unit]

        database.create_alert(scope, target_id, message, duration_hours)
        self._alert_message.delete("1.0", "end")
        self._alert_member_id = None
        self._alert_member_selected_lbl.configure(text="No one selected.")
        self._alert_status.configure(text="✓ Alert created.")
        self._load_alerts_list()

    def _describe_alert_target(self, alert):
        if alert["scope"] == "all":
            return "ALL MEMBERS"
        if alert["scope"] == "run":
            run = next((r for r in database.search_runs("")
                        if r["id"] == alert["target_id"]), None)
            return f"RUN: {run['name']}" if run else "RUN: (deleted)"
        m = database.get_member(alert["target_id"])
        return f"PERSON: {m['first_name']} {m['last_name']}" if m else "PERSON: (deleted)"

    def _load_alerts_list(self):
        for w in self._alerts_list_frame.winfo_children():
            w.destroy()

        alerts = database.get_alerts()
        if not alerts:
            MutedLabel(self._alerts_list_frame, text="No active alerts.",
                       bg=theme.CONTENT_BG).pack(pady=6, padx=8, anchor="w")
            return

        for a in alerts:
            row = tk.Frame(self._alerts_list_frame, bg=theme.CONTENT_BG)
            row.pack(fill="x", padx=4, pady=4)
            tk.Label(row, text=self._describe_alert_target(a),
                     bg=theme.CONTENT_BG, fg=theme.BTN_BG,
                     font=theme.F_TINY, anchor="w").pack(anchor="w")
            tk.Label(row, text=a["message"],
                     bg=theme.CONTENT_BG, fg=theme.PRIMARY_TEXT,
                     font=theme.F_BODY, anchor="w", justify="left",
                     wraplength=520).pack(anchor="w", fill="x")
            expires_text = f"Expires: {a['expires_at'][:16]}" if a.get("expires_at") else "No expiry"
            MutedLabel(row, text=expires_text, bg=theme.CONTENT_BG).pack(anchor="w")
            TouchButton(row, text="Delete Alert",
                        command=lambda al=a: self._delete_alert(al),
                        bg=theme.BTN_DANGER_BG, fg="white",
                        hover_bg=theme.BTN_DANGER_HOV,
                        font_cfg=theme.F_TINY).pack(anchor="e", pady=(4, 0),
                                                    ipady=2, ipadx=6)
            Divider(self._alerts_list_frame, bg=theme.BORDER_COLOR).pack(fill="x")

    def _delete_alert(self, alert):
        database.delete_alert(alert["id"])
        self._load_alerts_list()

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def on_show(self, **_):
        self._load_log()
        self._load_runs_list()
        self._clear_run_editor()
        self._render_pupil_results(database.search_members(""))
        self._member_search_var.set("")
        self._load_members_list()
        self._staff_search_var.set("")
        self._load_staff_list()
        self._pw_status.configure(text="")
        self._export_status.configure(text="")
        self._staff_export_status.configure(text="")
        self._set_date_range(0)          # member export defaults to today
        self._set_staff_date_range(13)   # staff export defaults to last 14 days
        self._alert_message.delete("1.0", "end")
        self._alert_member_id = None
        self._alert_member_selected_lbl.configure(text="No one selected.")
        self._alert_member_search_var.set("")
        self._set_alert_scope("all")
        self._alert_status.configure(text="")
        self._load_alerts_list()
