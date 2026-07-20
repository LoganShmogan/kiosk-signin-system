# screens/profile_screen.py — Child Profile (scrollable, all sections merged)

import tkinter as tk
import theme
import database
from components.widgets import (
    TouchButton, MutedLabel, FieldLabel, Divider,
    StyledEntry, DayPicker, PopupOverlay, ScrollFrame
)


class ProfileScreen(tk.Frame):

    def __init__(self, parent, app):
        super().__init__(parent, bg=theme.CONTENT_BG)
        self.app    = app
        self.member = None
        self._fields        = {}
        self._cg_fields     = {}
        self._day_pickers   = {}
        self._bool_vars     = {}
        self._build_ui()

    # ── Build ──────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Top bar
        bar = tk.Frame(self, bg=theme.PAGE_BG, height=52)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        TouchButton(bar, text="← Back",
                    command=self._go_back,
                    bg=theme.BTN_ORANGE_BG, fg="white",
                    hover_bg=theme.BTN_ORANGE_HOV,
                    font_cfg=theme.F_LABEL).pack(side="left", padx=12, pady=8)

        TouchButton(bar, text="Save",
                    command=self._save,
                    bg=theme.BTN_SUCCESS_BG, fg="white",
                    hover_bg=theme.BTN_SUCCESS_HOV,
                    font_cfg=theme.F_LABEL).pack(side="right", padx=8, pady=8)

        TouchButton(bar, text="Delete",
                    command=self._confirm_delete,
                    bg=theme.BTN_DANGER_BG, fg="white",
                    hover_bg=theme.BTN_DANGER_HOV,
                    font_cfg=theme.F_LABEL).pack(side="right", padx=4, pady=8)

        tk.Label(bar, text="Profile view", bg=theme.PAGE_BG,
                 fg="white", font=theme.F_H3).pack(side="left", padx=16)

        # ── Scrollable form ────────────────────────────────────────────────────
        scroll = ScrollFrame(self, bg=theme.CONTENT_BG)
        scroll.pack(fill="both", expand=True)

        sf = scroll.inner   # place all content here

        # Two-column layout inside scroll
        cols = tk.Frame(sf, bg=theme.CONTENT_BG)
        cols.pack(fill="both", expand=True, padx=24, pady=12)

        left  = tk.Frame(cols, bg=theme.CONTENT_BG)
        right = tk.Frame(cols, bg=theme.CONTENT_BG)
        left.pack(side="left",  fill="both", expand=True, padx=(0, 16))
        right.pack(side="left", fill="both", expand=True)

        # ── LEFT: Child details ────────────────────────────────────────────────
        self._section_hdr(left, "Child Details")

        self._fields["first_name"]    = self._field(left, "First Name")
        self._fields["last_name"]     = self._field(left, "Last Name")
        self._fields["date_of_birth"] = self._field(left, "Date of Birth", hint="YYYY-MM-DD")
        self._fields["school"]        = self._field(left, "School Attending")
        self._fields["pin"]           = self._field(left, "PIN (optional)", hint="Leave blank for none")

        self._section_hdr(left, "Attendance")

        FieldLabel(left, text="Mornings attending").pack(anchor="w", pady=(4, 2))
        self._day_pickers["mornings_days"] = DayPicker(left, bg=theme.CONTENT_BG)
        self._day_pickers["mornings_days"].pack(anchor="w", pady=(0, 8))

        FieldLabel(left, text="Afternoons attending").pack(anchor="w", pady=(4, 2))
        self._day_pickers["afternoons_days"] = DayPicker(left, bg=theme.CONTENT_BG)
        self._day_pickers["afternoons_days"].pack(anchor="w", pady=(0, 8))

        FieldLabel(left, text="Will this child need pickup in the morning?").pack(anchor="w", pady=(4, 2))
        self._bool_vars["needs_pickup"] = self._yes_no_row(left)

        self._section_hdr(left, "Activity")

        self._fields["activity"]      = self._field(left, "Activity / activities")
        self._fields["activity_time"] = self._field(left, "Time of activity/s")

        self._section_hdr(left, "Transport")

        FieldLabel(left, text="Is transport to activity required?").pack(anchor="w", pady=(4, 2))
        self._bool_vars["transport_required"] = self._yes_no_row(left)

        FieldLabel(left, text="Days of activity/s").pack(anchor="w", pady=(4, 2))
        self._day_pickers["activity_days"] = DayPicker(left, bg=theme.CONTENT_BG)
        self._day_pickers["activity_days"].pack(anchor="w", pady=(0, 8))

        self._fields["activity_address"] = self._field(left, "Activity Address/es", multiline=True)

        # ── RIGHT: Caregiver + Emergency ──────────────────────────────────────
        self._section_hdr(right, "Caregiver / Parent Details")

        self._cg_fields["full_name"]      = self._field(right, "Caregiver/Parent Name")
        self._cg_fields["phone"]          = self._field(right, "Phone Number")
        self._cg_fields["email"]          = self._field(right, "Email")

        FieldLabel(right, text="Email Notifications").pack(anchor="w", pady=(4, 0))
        MutedLabel(right, text="When to notify the caregiver by email").pack(anchor="w", pady=(0, 4))
        self._notify_var = tk.StringVar(value="BOTH")
        self._notify_frame = tk.Frame(right, bg=theme.CONTENT_BG)
        self._notify_frame.pack(anchor="w", pady=(0, 8))
        for _text, _val in [("None", "NONE"), ("IN only", "IN"), ("OUT only", "OUT"), ("Both", "BOTH")]:
            tk.Button(
                self._notify_frame, text=_text,
                font=theme.F_SMALL, relief="flat", bd=0,
                cursor="hand2", highlightthickness=0,
                command=lambda v=_val: (self._notify_var.set(v), self._refresh_notify()),
            ).pack(side="left", padx=2, ipady=6, ipadx=6)
        self._refresh_notify()

        self._cg_fields["street_address"] = self._field(right, "Street Address")
        self._cg_fields["suburb"]         = self._field(right, "Suburb")
        self._cg_fields["city"]           = self._field(right, "City")

        self._section_hdr(right, "Emergency Contact")

        self._cg_fields["emergency_contact_name"]  = self._field(right, "Emergency Contact Name")
        self._cg_fields["emergency_contact_phone"] = self._field(right, "Emergency Contact Phone")
        self._cg_fields["relationship"]            = self._field(right, "Relationship to child")

        self._section_hdr(right, "Last Signature on File")
        self._sig_frame = tk.Frame(right, bg=theme.CONTENT_BG)
        self._sig_frame.pack(anchor="w", pady=(0, 8), fill="x")
        self._sig_photo = None

        # Save button at bottom inside scroll
        save_row = tk.Frame(sf, bg=theme.CONTENT_BG)
        save_row.pack(fill="x", padx=24, pady=(8, 20))
        TouchButton(save_row, text="Save Profile",
                    command=self._save,
                    bg=theme.BTN_SUCCESS_BG, fg="white",
                    hover_bg=theme.BTN_SUCCESS_HOV,
                    font_cfg=theme.F_H3).pack(side="left", ipady=12, ipadx=24)
        TouchButton(save_row, text="← Back",
                    command=self._go_back,
                    bg=theme.BTN_BG, fg="white",
                    font_cfg=theme.F_LABEL).pack(side="left", padx=12, ipady=12, ipadx=16)

    # ── Form helpers ───────────────────────────────────────────────────────────

    def _section_hdr(self, parent, title):
        tk.Label(parent, text=title, bg=theme.CONTENT_BG,
                 fg=theme.BTN_BG, font=theme.F_H3).pack(anchor="w", pady=(14, 2))
        Divider(parent, bg=theme.BORDER_COLOR).pack(fill="x", pady=(0, 6))

    def _field(self, parent, label, hint="", multiline=False):
        FieldLabel(parent, text=label).pack(anchor="w")
        if multiline:
            txt = tk.Text(parent, width=34, height=3,
                          bg=theme.ENT_BG, fg=theme.PRIMARY_TEXT,
                          font=theme.F_INPUT, relief="flat",
                          highlightthickness=2,
                          highlightbackground=theme.ENT_BORDER,
                          insertbackground=theme.PRIMARY_TEXT)
            txt.pack(anchor="w", pady=(0, 6), fill="x")
            return txt
        ent = StyledEntry(parent, width=32)
        ent.pack(anchor="w", ipady=8, pady=(0, 6))
        return ent

    def _yes_no_row(self, parent):
        var = tk.IntVar(value=0)
        row = tk.Frame(parent, bg=theme.CONTENT_BG)
        row.pack(anchor="w", pady=(0, 8))
        for text, val in [("No", 0), ("Yes", 1)]:
            b = tk.Button(
                row, text=text, width=6,
                font=theme.F_SMALL, relief="flat", bd=0,
                cursor="hand2", highlightthickness=0,
                command=lambda v=val, r=var: (r.set(v), self._refresh_yn(row, r)),
            )
            b.pack(side="left", padx=2, ipady=6)
        self._refresh_yn(row, var)
        return var

    def _refresh_notify(self):
        colours = {
            "NONE": (theme.BTN_DANGER_BG, "white"),
            "IN":   (theme.BTN_SUCCESS_BG, "white"),
            "OUT":  (theme.BTN_ORANGE_BG,  "white"),
            "BOTH": (theme.BTN_BG,          "white"),
        }
        options = ["NONE", "IN", "OUT", "BOTH"]
        for i, child in enumerate(self._notify_frame.winfo_children()):
            val = options[i]
            on = (self._notify_var.get() == val)
            active_bg, active_fg = colours[val]
            child.configure(
                bg=active_bg if on else theme.DAY_OFF_BG,
                fg=active_fg if on else theme.DAY_OFF_FG,
            )

    def _refresh_yn(self, row, var):
        for i, child in enumerate(row.winfo_children()):
            on = (var.get() == i)
            child.configure(
                bg=theme.BTN_SUCCESS_BG if (on and i == 1) else
                   theme.BTN_DANGER_BG  if (on and i == 0) else
                   theme.DAY_OFF_BG,
                fg="white" if on else theme.DAY_OFF_FG,
            )

    # ── Populate / save ────────────────────────────────────────────────────────

    def _populate(self):
        m  = self.member or {}
        cg = (database.get_caregiver(m["id"]) if m.get("id") else {}) or {}

        def _set(fields, key, val):
            w = fields.get(key)
            if w is None:
                return
            if isinstance(w, StyledEntry):
                w.set_value(str(val) if val else "")
            elif isinstance(w, tk.Text):
                w.delete("1.0", tk.END)
                if val:
                    w.insert("1.0", str(val))

        for k in ("first_name","last_name","date_of_birth","school","pin",
                  "activity","activity_time","activity_address"):
            _set(self._fields, k, m.get(k, ""))

        for k in ("mornings_days","afternoons_days","activity_days"):
            dp = self._day_pickers.get(k)
            if dp:
                dp.set_value(m.get(k, ""))

        for k, var in self._bool_vars.items():
            var.set(int(m.get(k, 0) or 0))

        for k in ("full_name","phone","email","street_address",
                  "suburb","city","emergency_contact_name",
                  "emergency_contact_phone","relationship"):
            _set(self._cg_fields, k, cg.get(k, ""))

        self._notify_var.set(cg.get("notify_on") or "BOTH")
        self._refresh_notify()

        self._populate_signature()

    def _populate_signature(self):
        for w in self._sig_frame.winfo_children():
            w.destroy()
        self._sig_photo = None

        m = self.member
        if not m or not m.get("id"):
            return

        row = database.get_last_signature(m["id"])
        if not row:
            MutedLabel(self._sig_frame, text="No signature on file yet.",
                       bg=theme.CONTENT_BG).pack(anchor="w")
            return

        try:
            import io
            import export_util
            from PIL import Image, ImageTk

            png = export_util.render_signature(row["signature"], width=220, height=90)
            if not png:
                raise ValueError("signature could not be rendered")
            img = Image.open(io.BytesIO(png))
            self._sig_photo = ImageTk.PhotoImage(img)
            tk.Label(self._sig_frame, image=self._sig_photo,
                     bg=theme.CONTENT_BG).pack(anchor="w")
            MutedLabel(self._sig_frame,
                       text=f"Last used: {row['timestamp']} ({row['direction']})",
                       bg=theme.CONTENT_BG).pack(anchor="w", pady=(2, 0))
        except Exception:
            MutedLabel(self._sig_frame, text="No signature on file yet.",
                       bg=theme.CONTENT_BG).pack(anchor="w")

    def _get(self, fields, key):
        w = fields.get(key)
        if w is None:
            return ""
        if isinstance(w, StyledEntry):
            return w.get_value()
        if isinstance(w, tk.Text):
            return w.get("1.0", tk.END).strip()
        return ""

    def _save(self):
        member_data = {
            "id":                self.member["id"] if self.member else None,
            "first_name":        self._get(self._fields, "first_name"),
            "last_name":         self._get(self._fields, "last_name"),
            "date_of_birth":     self._get(self._fields, "date_of_birth"),
            "school":            self._get(self._fields, "school"),
            "mornings_days":     self._day_pickers["mornings_days"].get_value(),
            "afternoons_days":   self._day_pickers["afternoons_days"].get_value(),
            "needs_pickup":      self._bool_vars["needs_pickup"].get(),
            "activity":          self._get(self._fields, "activity"),
            "activity_time":     self._get(self._fields, "activity_time"),
            "activity_address":  self._get(self._fields, "activity_address"),
            "transport_required":self._bool_vars["transport_required"].get(),
            "activity_days":     self._day_pickers["activity_days"].get_value(),
            "pin":               self._get(self._fields, "pin"),
        }

        if not member_data["first_name"] or not member_data["last_name"]:
            p = PopupOverlay(self.winfo_toplevel(), is_error=True)
            p.set_message("First name and last name are required.")
            p.add_button("OK", p.destroy)
            p.add_button("Back to Menu", lambda: (p.destroy(), self._go_back()))
            return

        mid = database.upsert_member(member_data)

        cg_data = {
            "member_id":               mid,
            "full_name":               self._get(self._cg_fields, "full_name"),
            "phone":                   self._get(self._cg_fields, "phone"),
            "email":                   self._get(self._cg_fields, "email"),
            "street_address":          self._get(self._cg_fields, "street_address"),
            "suburb":                  self._get(self._cg_fields, "suburb"),
            "city":                    self._get(self._cg_fields, "city"),
            "emergency_contact_name":  self._get(self._cg_fields, "emergency_contact_name"),
            "emergency_contact_phone": self._get(self._cg_fields, "emergency_contact_phone"),
            "relationship":            self._get(self._cg_fields, "relationship"),
            "notify_on":               self._notify_var.get(),
        }
        database.upsert_caregiver(cg_data)
        self.member = database.get_member(mid)

        p = PopupOverlay(self.winfo_toplevel(), is_error=False)
        p.set_message("Profile saved successfully.")
        p.add_button("OK", p.destroy,
                     bg=theme.BTN_SUCCESS_BG, fg="white",
                     hover_bg=theme.BTN_SUCCESS_HOV)
        p.add_button("Back to Menu", lambda: (p.destroy(), self._go_back()))

    def _confirm_delete(self):
        if not self.member:
            return
        name = f"{self.member['first_name']} {self.member['last_name']}"
        p = PopupOverlay(self.winfo_toplevel(), is_error=True, width=520)
        p.set_message(f"Permanently delete {name}? This cannot be undone.")
        p.add_button("Cancel", p.destroy)
        p.add_button("Delete", lambda: (database.delete_member(self.member["id"]),
                                         p.destroy(), self._go_back()),
                     bg=theme.BTN_DANGER_BG, fg="white",
                     hover_bg=theme.BTN_DANGER_HOV)

    # ── Navigation ─────────────────────────────────────────────────────────────

    def _go_back(self):
        self.app.show_screen("admin_panel")

    def on_show(self, member=None, **_):
        self.member = member
        self._populate()
