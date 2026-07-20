import tkinter as tk
import theme
import database
from components.widgets import (
    TouchButton, FieldLabel, Divider, MutedLabel,
    StyledEntry, PopupOverlay, ScrollFrame
)


class StaffProfileScreen(tk.Frame):

    def __init__(self, parent, app):
        super().__init__(parent, bg=theme.CONTENT_BG)
        self.app   = app
        self.staff = None
        self._fields = {}
        self._build_ui()

    def _build_ui(self):
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

        self._delete_btn = TouchButton(bar, text="Delete",
                    command=self._confirm_delete,
                    bg=theme.BTN_DANGER_BG, fg="white",
                    hover_bg=theme.BTN_DANGER_HOV,
                    font_cfg=theme.F_LABEL)
        self._delete_btn.pack(side="right", padx=4, pady=8)

        self._title_lbl = tk.Label(bar, text="Staff Profile",
                                    bg=theme.PAGE_BG, fg="white", font=theme.F_H3)
        self._title_lbl.pack(side="left", padx=16)

        scroll = ScrollFrame(self, bg=theme.CONTENT_BG)
        scroll.pack(fill="both", expand=True)
        sf = scroll.inner

        col = tk.Frame(sf, bg=theme.CONTENT_BG)
        col.pack(fill="both", expand=True, padx=24, pady=12)

        tk.Label(col, text="Staff Details", bg=theme.CONTENT_BG,
                 fg=theme.BTN_BG, font=theme.F_H3).pack(anchor="w", pady=(14, 2))
        Divider(col, bg=theme.BORDER_COLOR).pack(fill="x", pady=(0, 6))

        self._fields["first_name"] = self._field(col, "First Name")
        self._fields["last_name"]  = self._field(col, "Last Name")
        self._fields["school"]     = self._field(col, "Role / Position (optional)")
        self._fields["pin"]        = self._field(col, "PIN (optional)",
                                                  hint="Leave blank for none")

        tk.Label(col, text="Last Signature on File", bg=theme.CONTENT_BG,
                 fg=theme.BTN_BG, font=theme.F_H3).pack(anchor="w", pady=(14, 2))
        Divider(col, bg=theme.BORDER_COLOR).pack(fill="x", pady=(0, 6))
        self._sig_frame = tk.Frame(col, bg=theme.CONTENT_BG)
        self._sig_frame.pack(anchor="w", pady=(0, 8), fill="x")
        self._sig_photo = None

        save_row = tk.Frame(sf, bg=theme.CONTENT_BG)
        save_row.pack(fill="x", padx=24, pady=(8, 20))
        TouchButton(save_row, text="Save Staff Member",
                    command=self._save,
                    bg=theme.BTN_SUCCESS_BG, fg="white",
                    hover_bg=theme.BTN_SUCCESS_HOV,
                    font_cfg=theme.F_H3).pack(side="left", ipady=12, ipadx=24)
        TouchButton(save_row, text="← Back",
                    command=self._go_back,
                    bg=theme.BTN_BG, fg="white",
                    font_cfg=theme.F_LABEL).pack(side="left", padx=12, ipady=12, ipadx=16)

    def _field(self, parent, label, hint=""):
        FieldLabel(parent, text=label).pack(anchor="w")
        ent = StyledEntry(parent, width=32)
        ent.pack(anchor="w", ipady=8, pady=(0, 6))
        return ent

    def _populate(self):
        m = self.staff or {}
        for key in ("first_name", "last_name", "school", "pin"):
            w = self._fields.get(key)
            if w:
                w.set_value(str(m.get(key, "") or ""))

        self._populate_signature()

    def _populate_signature(self):
        for w in self._sig_frame.winfo_children():
            w.destroy()
        self._sig_photo = None

        m = self.staff
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

    def _get(self, key):
        w = self._fields.get(key)
        return w.get_value() if w else ""

    def _save(self):
        data = {
            "id":                 self.staff["id"] if self.staff else None,
            "first_name":         self._get("first_name"),
            "last_name":          self._get("last_name"),
            "school":             self._get("school"),
            "pin":                self._get("pin"),
            "person_type":        "staff",
            "date_of_birth":      "",
            "mornings_days":      "",
            "afternoons_days":    "",
            "needs_pickup":       0,
            "activity":           "",
            "activity_time":      "",
            "activity_address":   "",
            "transport_required": 0,
            "activity_days":      "",
        }

        if not data["first_name"] or not data["last_name"]:
            p = PopupOverlay(self.winfo_toplevel(), is_error=True)
            p.set_message("First name and last name are required.")
            p.add_button("OK", p.destroy)
            return

        mid = database.upsert_member(data)
        self.staff = database.get_member(mid)

        p = PopupOverlay(self.winfo_toplevel(), is_error=False)
        p.set_message("Staff member saved successfully.")
        p.add_button("OK", p.destroy,
                     bg=theme.BTN_SUCCESS_BG, fg="white",
                     hover_bg=theme.BTN_SUCCESS_HOV)
        p.add_button("Back to Menu", lambda: (p.destroy(), self._go_back()))

    def _confirm_delete(self):
        if not self.staff:
            return
        name = f"{self.staff['first_name']} {self.staff['last_name']}"
        p = PopupOverlay(self.winfo_toplevel(), is_error=True, width=520)
        p.set_message(f"Permanently delete {name}?\nThis cannot be undone.")
        p.add_button("Cancel", p.destroy)
        p.add_button("Delete",
                     lambda: (database.delete_member(self.staff["id"]),
                              p.destroy(), self._go_back()),
                     bg=theme.BTN_DANGER_BG, fg="white",
                     hover_bg=theme.BTN_DANGER_HOV)

    def _go_back(self):
        self.app.show_screen("admin_panel")

    def on_show(self, staff=None, **_):
        self.staff = staff
        self._title_lbl.configure(
            text="Edit Staff Member" if staff else "New Staff Member"
        )
        # Hide delete button when creating a new record
        if staff:
            self._delete_btn.pack(side="right", padx=4, pady=8)
        else:
            self._delete_btn.pack_forget()
        self._populate()
