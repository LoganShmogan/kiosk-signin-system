# screens/social_screen.py — Social Media & Contacts Screen

import tkinter as tk

import theme
from components.widgets import Divider, TouchButton


class SocialScreen(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=theme.CONTENT_BG)
        self.app = app
        self._build_ui()

    def _build_ui(self):
        # Top bar
        bar = tk.Frame(self, bg=theme.PAGE_BG, height=52)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        TouchButton(
            bar,
            text="← Back",
            command=lambda: self.app.show_screen("options"),
            bg=theme.BTN_ORANGE_BG,
            fg="white",
            hover_bg=theme.BTN_ORANGE_HOV,
            font_cfg=theme.F_LABEL,
        ).pack(side="left", padx=12, pady=8)

        TouchButton(
            bar,
            text="Exit",
            command=lambda: self.app.show_screen("options"),
            bg=theme.BTN_DANGER_BG,
            fg="white",
            hover_bg=theme.BTN_DANGER_HOV,
            font_cfg=theme.F_LABEL,
        ).pack(side="right", padx=8, pady=8)

        tk.Label(
            bar,
            text="Social Media & Contacts",
            bg=theme.PAGE_BG,
            fg="white",
            font=theme.F_H3,
        ).pack(side="left", padx=16)

        # Centred content
        centre = tk.Frame(self, bg=theme.CONTENT_BG)
        centre.place(relx=0.5, rely=0.5, anchor="center")

        # Two info cards side by side
        cards_row = tk.Frame(centre, bg=theme.CONTENT_BG)
        cards_row.pack()

        self._info_card(
            cards_row,
            "Social Media",
            [
                ("Facebook", "Parent / Caregiver Page", theme.LINK_TEXT),
                ("Website", "www.example-kiosk.org", theme.LINK_TEXT),
            ],
        )

        tk.Frame(cards_row, bg=theme.BORDER_COLOR, width=2, height=160).pack(
            side="left", padx=24, fill="y"
        )

        self._info_card(
            cards_row,
            "Contacts",
            [
                ("Phone", "+1 555 0100", theme.PRIMARY_TEXT),
                ("Email", "info@example-kiosk.org", theme.LINK_TEXT),
            ],
        )

        Divider(centre, bg=theme.BORDER_COLOR).pack(fill="x", pady=20)

        # Action buttons
        btn_row = tk.Frame(centre, bg=theme.CONTENT_BG)
        btn_row.pack()

        TouchButton(
            btn_row,
            text="← Back",
            command=lambda: self.app.show_screen("options"),
            bg=theme.BTN_BG,
            fg="white",
            font_cfg=theme.F_LABEL,
        ).pack(side="left", padx=8, ipady=10, ipadx=16)

        TouchButton(
            btn_row,
            text="Exit",
            command=lambda: self.app.show_screen("options"),
            bg=theme.BTN_DANGER_BG,
            fg="white",
            hover_bg=theme.BTN_DANGER_HOV,
            font_cfg=theme.F_LABEL,
        ).pack(side="left", padx=8, ipady=10, ipadx=16)

    def _info_card(self, parent, title, items):
        card = tk.Frame(
            parent,
            bg=theme.CONTENT_BG,
            highlightthickness=2,
            highlightbackground=theme.BORDER_COLOR,
            padx=24,
            pady=20,
        )
        card.pack(side="left", padx=8)

        tk.Label(
            card,
            text=title,
            bg=theme.CONTENT_BG,
            fg=theme.PRIMARY_TEXT,
            font=theme.F_H3,
        ).pack(anchor="w", pady=(0, 12))

        for label, value, fg in items:
            row = tk.Frame(card, bg=theme.CONTENT_BG)
            row.pack(fill="x", pady=4)
            tk.Label(
                row,
                text=f"{label}:",
                bg=theme.CONTENT_BG,
                fg=theme.CREAM_MUTED,
                font=theme.F_LABEL,
                width=10,
                anchor="w",
            ).pack(side="left")
            tk.Label(
                row, text=value, bg=theme.CONTENT_BG, fg=fg, font=theme.F_BODY
            ).pack(side="left")

    def on_show(self, **_):
        pass
