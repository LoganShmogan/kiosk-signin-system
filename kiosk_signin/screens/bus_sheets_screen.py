# screens/bus_sheets_screen.py — Bus Sheets Screen

import tkinter as tk
from datetime import datetime

import theme
import database
from components.widgets import TouchButton, Divider, MutedLabel, ScrollFrame


class BusSheetsScreen(tk.Frame):

    def __init__(self, parent, app):
        super().__init__(parent, bg=theme.CONTENT_BG)
        self.app = app
        self._build_ui()

    def _build_ui(self):
        # Top bar
        bar = tk.Frame(self, bg=theme.PAGE_BG, height=52)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        TouchButton(bar, text="← Back",
                    command=lambda: self.app.show_screen("options"),
                    bg=theme.BTN_ORANGE_BG, fg="white",
                    hover_bg=theme.BTN_ORANGE_HOV,
                    font_cfg=theme.F_LABEL).pack(side="left", padx=12, pady=8)

        TouchButton(bar, text="Refresh",
                    command=self._load_sheet,
                    bg=theme.BTN_BG, fg="white",
                    font_cfg=theme.F_LABEL).pack(side="right", padx=8, pady=8)

        tk.Label(bar, text="Bus Sheets — Today's Sign-ins",
                 bg=theme.PAGE_BG, fg="white", font=theme.F_H3).pack(side="left", padx=16)

        # Date label
        self._date_lbl = tk.Label(self, text="",
                                   bg=theme.CONTENT_BG, fg=theme.CREAM_MUTED,
                                   font=theme.F_LABEL)
        self._date_lbl.pack(anchor="w", padx=24, pady=(12, 4))

        Divider(self, bg=theme.BORDER_COLOR).pack(fill="x", padx=24, pady=(0, 8))

        # Table header
        hdr = tk.Frame(self, bg=theme.BTN_BG)
        hdr.pack(fill="x", padx=24)
        for col, w in [("Name", 28), ("School", 22), ("Direction", 12), ("Time", 14)]:
            tk.Label(hdr, text=col, bg=theme.BTN_BG, fg="white",
                     font=theme.F_LABEL, width=w, anchor="w",
                     padx=8, pady=6).pack(side="left")

        # Scrollable rows
        self._scroll = ScrollFrame(self, bg=theme.CONTENT_BG)
        self._scroll.pack(fill="both", expand=True, padx=24, pady=(0, 16))

    def _load_sheet(self):
        today = datetime.now().strftime("%A %-d %B %Y")
        self._date_lbl.configure(text=f"Date: {today}")

        sf = self._scroll.inner
        for w in sf.winfo_children():
            w.destroy()

        signs = database.get_today_signs()
        if not signs:
            MutedLabel(sf, text="No sign-ins recorded today.",
                       bg=theme.CONTENT_BG).pack(pady=24)
            return

        for i, s in enumerate(signs):
            row_bg = "#F0EDE8" if i % 2 == 0 else theme.CONTENT_BG
            row = tk.Frame(sf, bg=row_bg)
            row.pack(fill="x")

            name   = f"{s['first_name']} {s['last_name']}"
            school = ""
            member = database.get_member(s["member_id"])
            if member:
                school = member.get("school", "")

            ts    = s.get("timestamp", "")
            time_ = ts[11:16] if len(ts) >= 16 else ts
            direc = s.get("direction", "")
            dir_fg = theme.BTN_SUCCESS_BG if direc == "IN" else theme.BTN_DANGER_BG

            for text, w, fg in [
                (name,   28, theme.PRIMARY_TEXT),
                (school, 22, theme.CREAM_MUTED),
                (direc,  12, dir_fg),
                (time_,  14, theme.PRIMARY_TEXT),
            ]:
                tk.Label(row, text=text, bg=row_bg, fg=fg,
                         font=theme.F_BODY, width=w, anchor="w",
                         padx=8, pady=8).pack(side="left")

            Divider(sf, bg=theme.BORDER_COLOR).pack(fill="x")

    def on_show(self, **_):
        self._load_sheet()
