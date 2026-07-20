"""virtual_keyboard.py — Full QWERTY on-screen keyboard for the Windows kiosk."""
import tkinter as tk

import theme

# ── Key layout ────────────────────────────────────────────────────────────────

_NORMAL = [
    ["`","1","2","3","4","5","6","7","8","9","0","-","=","⌫"],
    ["q","w","e","r","t","y","u","i","o","p","[","]","\\"],
    ["a","s","d","f","g","h","j","k","l",";","'","↵"],
    ["⇧","z","x","c","v","b","n","m",",",".","/","⇧"],
    ["Space"],
]

_SHIFTED = [
    ["~","!","@","#","$","%","^","&","*","(",")","_","+","⌫"],
    ["Q","W","E","R","T","Y","U","I","O","P","{","}","|"],
    ["A","S","D","F","G","H","J","K","L",":",'"',"↵"],
    ["⇧","Z","X","C","V","B","N","M","<",">","?","⇧"],
    ["Space"],
]

# Extra horizontal padding (ipadx) relative to a regular key (ipadx=10)
_WIDE_IPX = {"⌫": 26, "↵": 34, "⇧": 26}

_KEY_BG        = "#4a3a8a"   # regular key
_KEY_BG_SPEC   = "#5c4ba0"   # special action keys (⌫ ↵ ⇧)
_KB_BG         = "#1e1540"   # keyboard panel background
_KEY_FG        = "#ffffff"
_SHIFT_ACTIVE  = theme.BTN_YELLOW_BG
_SHIFT_ACT_FG  = theme.BTN_YELLOW_TEXT
_KEY_PRESS_BG  = theme.BTN_YELLOW_BG


class VirtualKeyboard:
    """Floating on-screen keyboard.  Call attach(entry) to show it."""

    def __init__(self, root: tk.Tk):
        self._root             = root
        self._target: tk.Entry | None = None
        self._shifted          = False
        self._win: tk.Toplevel | None = None
        self._suppress_attach  = False
        # list of (Button widget, normal_label, shifted_label)
        self._btns: list[tuple[tk.Button, str, str]] = []

    # ── Public API ─────────────────────────────────────────────────────────────

    def attach(self, entry: tk.Entry):
        """Direct keyboard to *entry* and show it."""
        if self._suppress_attach:
            return
        self._target = entry
        if self._win is None or not self._win.winfo_exists():
            self._build()
        else:
            self._win.deiconify()
        self._position()

    def detach(self):
        """Hide the keyboard."""
        self._target = None
        self._suppress_attach = True
        if self._win and self._win.winfo_exists():
            self._root.focus_set()
            self._win.withdraw()
        self._root.after(300, self._clear_suppress)

    def _clear_suppress(self):
        self._suppress_attach = False

    # ── Build ──────────────────────────────────────────────────────────────────

    def _build(self):
        win = tk.Toplevel(self._root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg=_KB_BG)
        self._win = win

        header = tk.Frame(win, bg=_KB_BG)
        header.pack(fill=tk.X, padx=6, pady=(6, 0))

        tk.Label(
            header, text="Keyboard",
            bg=_KB_BG, fg="#b0a8d0",
            font=theme.font(10),
        ).pack(side=tk.LEFT)

        tk.Button(
            header, text="✕  Close",
            command=self.detach,
            bg=theme.BTN_DANGER_BG, fg="white",
            font=theme.font(10, "bold"),
            relief="flat", bd=0,
            padx=10, pady=2,
            cursor="hand2", takefocus=False,
        ).pack(side=tk.RIGHT)

        self._btns = []
        for row_n, row_s in zip(_NORMAL, _SHIFTED):
            row_fr = tk.Frame(win, bg=_KB_BG)
            row_fr.pack(fill=tk.X, padx=6, pady=3)
            for n, s in zip(row_n, row_s):
                btn = self._make_key(row_fr, n, s)
                self._btns.append((btn, n, s))

        self._position()

    def _make_key(self, parent: tk.Frame, normal: str, shifted: str) -> tk.Button:
        is_special = normal in ("⌫", "↵", "⇧")
        bg = _KEY_BG_SPEC if is_special else _KEY_BG

        btn = tk.Button(
            parent,
            text=normal,
            font=theme.font(13, "bold"),
            fg=_KEY_FG,
            bg=bg,
            activebackground=_KEY_PRESS_BG,
            activeforeground=_SHIFT_ACT_FG,
            relief="flat", bd=0,
            highlightthickness=1,
            highlightbackground="#2a1f5e",
            cursor="hand2",
            takefocus=False,
        )

        if normal == "Space":
            btn.configure(text="Space")
            btn.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=10, padx=2)
        else:
            ipadx = _WIDE_IPX.get(normal, 10)
            btn.pack(side=tk.LEFT, ipady=10, ipadx=ipadx, padx=2)

        btn.configure(command=lambda n=normal, s=shifted: self._on_key(n, s))
        return btn

    # ── Key press ──────────────────────────────────────────────────────────────

    def _on_key(self, normal: str, shifted: str):
        char = shifted if self._shifted else normal

        if self._target:
            if char == "⌫":
                cursor = self._target.index(tk.INSERT)
                if cursor > 0:
                    self._target.delete(cursor - 1, cursor)
            elif char == "↵":
                self._target.event_generate("<Return>")
            elif char == "Space":
                self._target.insert(tk.INSERT, " ")
            elif char not in ("⇧",):
                self._target.insert(tk.INSERT, char)

        if normal == "⇧":
            self._shifted = not self._shifted
            self._update_shift_display()
            if self._target:
                self._target.focus_set()
            return

        # Auto-release shift after one character
        if self._shifted and normal not in ("⌫",):
            self._shifted = False
            self._update_shift_display()

        if self._target:
            self._target.focus_set()

    def _update_shift_display(self):
        for btn, normal, shifted in self._btns:
            btn.configure(text=shifted if self._shifted else normal)
            if normal == "⇧":
                if self._shifted:
                    btn.configure(bg=_SHIFT_ACTIVE, fg=_SHIFT_ACT_FG)
                else:
                    btn.configure(bg=_KEY_BG_SPEC, fg=_KEY_FG)

    # ── Position ───────────────────────────────────────────────────────────────

    def _position(self):
        if self._win is None:
            return
        self._win.update_idletasks()
        sw = self._root.winfo_screenwidth()
        sh = self._root.winfo_screenheight()
        kw = self._win.winfo_reqwidth()
        kh = self._win.winfo_reqheight()
        x  = max(0, (sw - kw) // 2)
        y  = sh - kh - 2
        self._win.geometry(f"{kw}x{kh}+{x}+{y}")
