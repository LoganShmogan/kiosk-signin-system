# screens/splash_screen.py
# TapScreen   : full-screen logo + "Tap to start", tap anywhere → Options
# OptionsScreen : menu of all sections

import tkinter as tk

import theme
from components.widgets import TouchButton

# ── Screen 1: Tap to Start ────────────────────────────────────────────────────


class TapScreen(tk.Frame):
    """Full-screen idle screen. Tap anywhere to reach Options."""

    def __init__(self, parent, app):
        super().__init__(parent, bg=theme.CONTENT_BG, cursor="hand2")
        self.app = app
        self._build_ui()

    def _build_ui(self):
        # Unobtrusive Admin button top-right
        top = tk.Frame(self, bg=theme.CONTENT_BG)
        top.pack(fill="x", padx=16, pady=(12, 0))
        TouchButton(
            top,
            text="Admin",
            command=lambda: self.app.show_screen("admin_password"),
            bg=theme.BTN_BG,
            fg="white",
            font_cfg=theme.F_SMALL,
        ).pack(side="right", ipady=4, ipadx=10)

        # Everything else is centred
        centre = tk.Frame(self, bg=theme.CONTENT_BG)
        centre.place(relx=0.5, rely=0.5, anchor="center")

        # Logo — image if available, otherwise styled text box
        self._logo_img = None
        try:
            import os

            from PIL import Image, ImageTk

            logo_path = os.path.join(
                os.path.dirname(__file__), "..", "assets", "logo.png"
            )
            if os.path.exists(logo_path):
                img = Image.open(logo_path).resize((280, 140), Image.LANCZOS)
                self._logo_img = ImageTk.PhotoImage(img)
                tk.Label(centre, image=self._logo_img, bg=theme.CONTENT_BG).pack(
                    pady=(0, 32)
                )
            else:
                raise FileNotFoundError
        except Exception:
            logo_frame = tk.Frame(
                centre,
                bg=theme.CONTENT_BG,
                highlightthickness=4,
                highlightbackground=theme.BTN_BG,
            )
            logo_frame.pack(pady=(0, 36), padx=32)
            tk.Label(
                logo_frame,
                text="KIOSK",
                bg=theme.CONTENT_BG,
                fg=theme.BTN_BG,
                font=(theme.FONT_FAMILY, 72, "bold"),
                padx=52,
                pady=22,
            ).pack()

        # "Tap to start"
        tk.Label(
            centre,
            text="Tap to start",
            bg=theme.CONTENT_BG,
            fg=theme.PRIMARY_TEXT,
            font=theme.F_H2,
        ).pack()

        # Bind tap on every widget so nothing is dead space
        for w in (self, top, centre):
            w.bind("<ButtonPress-1>", self._on_tap)
        # Children of centre get bound after pack — use a helper
        self.after(50, self._bind_children, centre)

    def _bind_children(self, parent):
        for child in parent.winfo_children():
            child.bind("<ButtonPress-1>", self._on_tap)
            self._bind_children(child)

    def _on_tap(self, event=None):
        self.app.show_screen("options")

    def on_show(self, **_):
        pass


# ── Screen 2: Options Menu ────────────────────────────────────────────────────


class OptionsScreen(tk.Frame):
    """Menu shown after tapping the tap screen."""

    MENU = [
        ("Sign In / Sign Out", "signin", theme.BTN_SUCCESS_BG, theme.BTN_SUCCESS_HOV),
        # ("Group Sign-in",           "group_signin",       theme.BTN_BG,         theme.BTN_HOVER),
        ("Run Sheets", "run_sheets", theme.BTN_BG, theme.BTN_HOVER),
        # ("Centre Enrollment",       "enrollment",         theme.BTN_BG,         theme.BTN_HOVER),
        # ("Holiday Enrollment",      "holiday_enrollment", theme.BTN_BG,         theme.BTN_HOVER),
        (
            "Social Media & Contacts",
            "social",
            theme.BTN_ORANGE_BG,
            theme.BTN_ORANGE_HOV,
        ),
    ]

    def __init__(self, parent, app):
        super().__init__(parent, bg=theme.PAGE_BG)
        self.app = app
        self._build_ui()

    def _build_ui(self):
        # Top bar
        bar = tk.Frame(self, bg=theme.PAGE_BG, height=60)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        TouchButton(
            bar,
            text="← Back",
            command=lambda: self.app.show_screen("tap"),
            bg=theme.BTN_ORANGE_BG,
            fg="white",
            hover_bg=theme.BTN_ORANGE_HOV,
            font_cfg=theme.F_LABEL,
        ).pack(side="left", padx=16, pady=10)

        TouchButton(
            bar,
            text="Admin",
            command=lambda: self.app.show_screen("admin_password"),
            bg=theme.BTN_BG,
            fg="white",
            font_cfg=theme.F_LABEL,
        ).pack(side="right", padx=16, pady=10)

        tk.Label(
            bar,
            text="Kiosk Sign-In System",
            bg=theme.PAGE_BG,
            fg="white",
            font=theme.F_H3,
        ).pack(side="left", padx=16)

        # Two-column button grid, centred vertically
        grid = tk.Frame(self, bg=theme.PAGE_BG)
        grid.place(relx=0.5, rely=0.54, anchor="center")

        left_col = tk.Frame(grid, bg=theme.PAGE_BG)
        right_col = tk.Frame(grid, bg=theme.PAGE_BG)
        left_col.pack(side="left", padx=20)
        right_col.pack(side="left", padx=20)

        for i, (label, screen, bg, hov) in enumerate(self.MENU):
            col = left_col if i % 2 == 0 else right_col
            TouchButton(
                col,
                text=label,
                command=lambda s=screen: self.app.show_screen(s),
                bg=bg,
                fg="white",
                hover_bg=hov,
                font_cfg=theme.F_H2,
                width=26,
            ).pack(pady=10, ipady=20)

    def on_show(self, **_):
        pass
