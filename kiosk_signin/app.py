#!/usr/bin/env python3
import os
import sys
import threading
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import database
import theme
from screens.admin_screen import AdminPanelScreen, AdminPasswordScreen
from screens.profile_screen import ProfileScreen
from screens.staff_profile_screen import StaffProfileScreen
from screens.run_sheets_screen import RunSheetsScreen
from screens.signature_screen import SignatureScreen
from screens.signin_screen import SignInScreen
from screens.social_screen import SocialScreen
from screens.splash_screen import OptionsScreen, TapScreen

_ON_WINDOWS = sys.platform == "win32"


class App:
    def __init__(self):
        database.init_db()

        self.root = tk.Tk()
        self.root.title("Kiosk Sign-In System")
        self.root.configure(bg=theme.PAGE_BG)

        if _ON_WINDOWS:
            self.root.state("zoomed")
            from components.virtual_keyboard import VirtualKeyboard
            self._vkb = VirtualKeyboard(self.root)
        else:
            # Fullscreen disabled on Linux — a system on-screen keyboard needs the
            # window manager to resize the window when the keyboard appears.
            self.root.geometry("1280x720")
            self.root.resizable(False, False)
            self._vkb = None

        self._pending_detach = None

        self.root.bind("<Control-q>", lambda e: self.root.destroy())
        self.root.bind("<Escape>",    lambda e: None)
        self.root.bind_all("<FocusIn>",  self._on_focus_in)
        self.root.bind_all("<FocusOut>", self._on_focus_out)

        self._screens = {
            "tap":            TapScreen(self.root, self),
            "options":        OptionsScreen(self.root, self),
            "signin":         SignInScreen(self.root, self),
            "signature":      SignatureScreen(self.root, self),
            "profile":        ProfileScreen(self.root, self),
            "social":         SocialScreen(self.root, self),
            "run_sheets":     RunSheetsScreen(self.root, self),
            "admin_password":  AdminPasswordScreen(self.root, self),
            "admin_panel":     AdminPanelScreen(self.root, self),
            "staff_profile":   StaffProfileScreen(self.root, self),
        }

        for screen in self._screens.values():
            screen.place(x=0, y=0, relwidth=1, relheight=1)

        self.show_screen("tap")

    def _on_focus_in(self, event):
        if isinstance(event.widget, tk.Entry) and self._vkb:
            if self._pending_detach:
                self.root.after_cancel(self._pending_detach)
                self._pending_detach = None
            self._vkb.attach(event.widget)

    def _on_focus_out(self, event):
        if isinstance(event.widget, tk.Entry) and self._vkb:
            self._pending_detach = self.root.after(400, self._detach_if_not_entry)

    def _detach_if_not_entry(self):
        self._pending_detach = None
        if self._vkb and not isinstance(self.root.focus_get(), tk.Entry):
            self._vkb.detach()

    def show_screen(self, name: str, **kwargs):
        if name not in self._screens:
            print(f"[App] Unknown screen '{name}' — going to tap")
            name = "tap"
        screen = self._screens[name]
        screen.lift()
        if hasattr(screen, "on_show"):
            screen.on_show(**kwargs)

    def run(self):
        self.root.mainloop()


def _start_dashboard():
    project_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from dashboard.app import app as dashboard_app
    from waitress import serve
    serve(dashboard_app, host="0.0.0.0", port=5000)


if __name__ == "__main__":
    # Build the kiosk app (which calls database.init_db(), importing
    # werkzeug.security) fully on the main thread before starting the
    # dashboard thread. Starting the thread first let it race the main
    # thread to import werkzeug for the first time concurrently — harmless
    # under a normal Python install, but PyInstaller's frozen import
    # machinery isn't thread-safe for this, producing an intermittent
    # "partially initialized module" ImportError on the packaged .exe.
    kiosk_app = App()
    dashboard_thread = threading.Thread(target=_start_dashboard, daemon=True)
    dashboard_thread.start()
    kiosk_app.run()
