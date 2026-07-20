# components/widgets.py — Reusable touch-friendly widgets

import tkinter as tk
import theme


# ── Base touch button ─────────────────────────────────────────────────────────

class TouchButton(tk.Button):
    """Large, touch-friendly button with hover colour transitions."""

    def __init__(self, parent, text, command=None,
                 bg=None, fg=None, hover_bg=None, font_cfg=None,
                 width=None, height=None, **kwargs):
        bg       = bg       or theme.BTN_BG
        fg       = fg       or theme.SECONDARY_TEXT
        hover_bg = hover_bg or theme.BTN_HOVER
        font_cfg = font_cfg or theme.F_BTN
        self._bg       = bg
        self._hover_bg = hover_bg

        super().__init__(
            parent, text=text, command=command,
            bg=bg, fg=fg,
            activebackground=hover_bg, activeforeground=fg,
            font=font_cfg, relief="flat", bd=0,
            cursor="hand2", highlightthickness=0, **kwargs,
        )
        if width:  self.configure(width=width)
        if height: self.configure(height=height)

        self.bind("<Enter>", lambda e: self.configure(bg=self._hover_bg))
        self.bind("<Leave>", lambda e: self.configure(bg=self._bg))

    def update_colors(self, bg, hover_bg, fg=None):
        self._bg       = bg
        self._hover_bg = hover_bg
        cfg = dict(bg=bg, activebackground=hover_bg)
        if fg:
            cfg["fg"] = fg
            cfg["activeforeground"] = fg
        self.configure(**cfg)


# ── Labels ────────────────────────────────────────────────────────────────────

class MutedLabel(tk.Label):
    def __init__(self, parent, text, bg=None, fg=None, **kwargs):
        super().__init__(parent, text=text,
                         bg=bg or theme.CONTENT_BG,
                         fg=fg or theme.CREAM_MUTED,
                         font=theme.F_SMALL, **kwargs)


class FieldLabel(tk.Label):
    """Small label above an input field."""
    def __init__(self, parent, text, bg=None, **kwargs):
        super().__init__(parent, text=text,
                         bg=bg or theme.CONTENT_BG,
                         fg=theme.CREAM_MUTED,
                         font=theme.F_TINY, **kwargs)


# ── Divider ───────────────────────────────────────────────────────────────────

class Divider(tk.Frame):
    def __init__(self, parent, bg=None, **kwargs):
        super().__init__(parent, height=1,
                         bg=bg or theme.BORDER_COLOR, **kwargs)


# ── Styled Entry ──────────────────────────────────────────────────────────────

class StyledEntry(tk.Entry):
    def __init__(self, parent, bg=None, **kwargs):
        super().__init__(parent, **kwargs)
        theme.style_entry(self, bg=bg)
        if bg:
            self.configure(bg=bg)

    def get_value(self):
        return self.get()

    def set_value(self, val):
        self.delete(0, tk.END)
        if val:
            self.insert(0, val)


# ── Day Picker ────────────────────────────────────────────────────────────────

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]

class DayPicker(tk.Frame):
    """Row of Mon-Fri toggle buttons. State stored as comma-sep string."""

    def __init__(self, parent, bg=None, **kwargs):
        super().__init__(parent, bg=bg or theme.CONTENT_BG, **kwargs)
        self._vars   = {}
        self._btns   = {}
        for day in DAYS:
            v = tk.BooleanVar(value=False)
            self._vars[day] = v
            btn = tk.Button(
                self, text=day, width=5,
                bg=theme.DAY_OFF_BG, fg=theme.DAY_OFF_FG,
                activebackground=theme.DAY_ON_BG,
                activeforeground=theme.DAY_ON_FG,
                font=theme.F_SMALL, relief="flat", bd=0,
                cursor="hand2", highlightthickness=1,
                highlightbackground=theme.BORDER_COLOR,
                command=lambda d=day: self._toggle(d),
            )
            btn.pack(side="left", padx=2)
            self._btns[day] = btn

    def _toggle(self, day):
        self._vars[day].set(not self._vars[day].get())
        self._refresh(day)

    def _refresh(self, day):
        on = self._vars[day].get()
        btn = self._btns[day]
        btn.configure(
            bg=theme.DAY_ON_BG if on else theme.DAY_OFF_BG,
            fg=theme.DAY_ON_FG if on else theme.DAY_OFF_FG,
        )

    def get_value(self) -> str:
        return ",".join(d for d in DAYS if self._vars[d].get())

    def set_value(self, val: str):
        selected = set((val or "").split(","))
        for day in DAYS:
            self._vars[day].set(day in selected)
            self._refresh(day)


# ── Popup Overlay ─────────────────────────────────────────────────────────────

class PopupOverlay(tk.Toplevel):
    def __init__(self, root, title="", is_error=False, width=500, height=260):
        super().__init__(root)
        self.overrideredirect(True)
        self.configure(bg=theme.CONTENT_BG,
                       highlightthickness=2,
                       highlightbackground=theme.BORDER_COLOR)
        self._root = root
        self._width = width
        self._min_height = height
        self._max_height = root.winfo_screenheight() - 80
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        x = (sw - width) // 2
        y = (sh - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.grab_set()

        accent = theme.ERROR_BG if is_error else theme.SUCCESS_BG
        status_text = title or ("ERROR" if is_error else "SUCCESS")

        self._accent_bar = tk.Frame(self, bg=accent, height=10)
        self._accent_bar.pack(fill="x")

        _header_row = tk.Frame(self, bg=theme.CONTENT_BG)
        _header_row.pack(fill="x", padx=20, pady=(12, 0))
        self._status_label = tk.Label(_header_row, text=status_text, bg=accent, fg="white",
                                      font=theme.F_H3, padx=16, pady=4)
        self._status_label.pack(side="left")

        self._btn_row = tk.Frame(self, bg=theme.CONTENT_BG)
        self._btn_row.pack(pady=(8, 4))

        self._divider = Divider(self, bg=theme.BORDER_COLOR)
        self._divider.pack(fill="x", padx=20, pady=4)

        _msg_container = tk.Frame(self, bg=theme.CONTENT_BG)
        _msg_container.pack(padx=20, pady=8, fill="both", expand=True)

        _scrollbar = tk.Scrollbar(_msg_container, width=30)
        _scrollbar.pack(side="right", fill="y")

        self._msg = tk.Text(_msg_container, bg=theme.CONTENT_BG,
                            fg=theme.PRIMARY_TEXT, font=theme.F_BODY,
                            wrap="word", relief="flat", borderwidth=0,
                            highlightthickness=0, cursor="arrow",
                            yscrollcommand=_scrollbar.set, state="disabled")
        self._msg.pack(side="left", fill="both", expand=True)
        _scrollbar.config(command=self._msg.yview)

    def set_message(self, msg):
        self._msg.configure(state="normal")
        self._msg.delete("1.0", "end")
        self._msg.insert("1.0", msg)
        self._msg.configure(state="disabled")
        self._schedule_resize()

    def _schedule_resize(self):
        if hasattr(self, "_resize_job"):
            try:
                self.after_cancel(self._resize_job)
            except Exception:
                pass
        self._resize_job = self.after(30, self._auto_size)

    def _auto_size(self):
        self.update_idletasks()
        try:
            result = self._msg.count("1.0", "end", "displaylines")
            lines = result[0] if result else 1
        except Exception:
            lines = 3
        try:
            lh = int(self._msg.tk.call("font", "metrics", self._msg.cget("font"), "-linespace"))
        except Exception:
            lh = 20
        try:
            # winfo_reqheight() on the Toplevel sums all children including buttons.
            # Subtract the Text widget's own required height, then add actual text height.
            req = self.winfo_reqheight()
            msg_req = self._msg.winfo_reqheight()
            chrome = max(req - msg_req, 180)
        except Exception:
            chrome = 200
        total = max(self._min_height, min(chrome + lines * (lh + 2), self._max_height))
        sw, sh = self._root.winfo_screenwidth(), self._root.winfo_screenheight()
        x = (sw - self._width) // 2
        y = (sh - total) // 2
        self.geometry(f"{self._width}x{total}+{x}+{y}")

    def add_button(self, label, command, bg=None, fg=None, hover_bg=None):
        btn = TouchButton(
            self._btn_row, text=label, command=command,
            bg=bg or theme.BTN_BG,
            fg=fg or theme.SECONDARY_TEXT,
            hover_bg=hover_bg or theme.BTN_HOVER,
            font_cfg=theme.F_LABEL,
        )
        btn.pack(side="left", padx=6, ipady=6, ipadx=10)
        self._schedule_resize()


# ── Signature Canvas ──────────────────────────────────────────────────────────

class SignatureCanvas(tk.Canvas):
    def __init__(self, parent, width=320, height=130, **kwargs):
        super().__init__(parent, width=width, height=height,
                         bg="white", cursor="pencil",
                         highlightthickness=2,
                         highlightbackground=theme.ENT_BORDER, **kwargs)
        self._last_x = self._last_y = None
        self._strokes = []
        self.bind("<ButtonPress-1>",   self._start)
        self.bind("<B1-Motion>",       self._draw)
        self.bind("<ButtonRelease-1>", self._end)
        # Prevent Windows touch scroll events from propagating up and stealing
        # the pointer mid-stroke.
        self.bind("<MouseWheel>", lambda e: "break")

    def _start(self, e):
        self._last_x, self._last_y = e.x, e.y
        try:
            self.grab_set()
        except tk.TclError:
            pass

    def _draw(self, e):
        if self._last_x is not None:
            self.create_line(self._last_x, self._last_y, e.x, e.y,
                             fill="black", width=2, smooth=True, capstyle="round")
            self._strokes.append((self._last_x, self._last_y, e.x, e.y))
        self._last_x, self._last_y = e.x, e.y

    def _end(self, _):
        self._last_x = self._last_y = None
        try:
            self.grab_release()
        except tk.TclError:
            pass

    def clear(self):
        self.delete("all")
        self._strokes.clear()

    def has_signature(self):
        return len(self._strokes) > 0

    def export_bytes(self):
        if not self._strokes:
            return None
        return str(self._strokes).encode()


# ── Notice Card ───────────────────────────────────────────────────────────────

class NoticeCard(tk.Frame):
    def __init__(self, parent, title, body, posted_at="", **kwargs):
        super().__init__(parent, bg="white", padx=10, pady=8,
                         highlightthickness=1,
                         highlightbackground=theme.BORDER_COLOR, **kwargs)
        if title:
            tk.Label(self, text=title, bg="white",
                     fg=theme.PRIMARY_TEXT, font=theme.F_LABEL,
                     wraplength=380, justify="left", anchor="w").pack(fill="x")
        preview = body[:200] + ("…" if len(body) > 200 else "")
        tk.Label(self, text=preview, bg="white",
                 fg=theme.CREAM_MUTED, font=theme.F_SMALL,
                 wraplength=380, justify="left", anchor="w").pack(fill="x", pady=(2, 0))
        if posted_at:
            tk.Label(self, text=posted_at, bg="white",
                     fg=theme.CREAM_MUTED, font=theme.F_TINY,
                     anchor="e").pack(anchor="e", pady=(4, 0))


# ── Member List Item ──────────────────────────────────────────────────────────

class MemberListItem(tk.Frame):
    def __init__(self, parent, member: dict, on_select, bg=None, **kwargs):
        _bg = bg or theme.CONTENT_BG
        super().__init__(parent, bg=_bg, cursor="hand2",
                         pady=2, padx=4, **kwargs)
        name = f"{member['first_name']} {member['last_name']}"
        self._label = tk.Label(self, text=name, bg=_bg,
                               fg=theme.PRIMARY_TEXT, font=theme.F_BODY,
                               anchor="w")
        self._label.pack(fill="x", ipady=6)
        Divider(self, bg=theme.BORDER_COLOR).pack(fill="x")
        self._bg   = _bg
        self._hovbg = theme.BORDER_COLOR
        for w in (self, self._label):
            w.bind("<Enter>",        lambda e: self._hover(True))
            w.bind("<Leave>",        lambda e: self._hover(False))
            w.bind("<ButtonPress-1>", lambda e, m=member: on_select(m))

    def _hover(self, active):
        col = self._hovbg if active else self._bg
        self.configure(bg=col)
        self._label.configure(bg=col)


# ── On-Screen Keyboard ────────────────────────────────────────────────────────

class OnScreenKeyboard(tk.Frame):
    """
    Full QWERTY on-screen keyboard that types into a linked Entry widget.
    Call .attach(entry_widget) to link it.
    """

    ROWS = [
        list("QWERTYUIOP"),
        list("ASDFGHJKL"),
        ["SHIFT"] + list("ZXCVBNM") + ["⌫"],
        ["123", "SPACE", "."],
    ]
    NUMS = [
        list("1234567890"),
        list("!@#$%^&*()"),
        ["-", "_", "=", "+", "[", "]", ",", ".", "/", "?"],
        ["ABC", "SPACE", "⌫"],
    ]

    def __init__(self, parent, bg=None, on_hide=None, **kwargs):
        _bg = bg or theme.PAGE_BG
        super().__init__(parent, bg=_bg, padx=4, pady=4, **kwargs)
        self._entry    = None
        self._shifted  = False
        self._nummode  = False
        self._on_hide  = on_hide
        self._bg       = _bg
        self._build()

    def attach(self, entry):
        self._entry = entry

    def _build(self):
        self._row_frames = []
        for _ in range(4):
            f = tk.Frame(self, bg=self._bg)
            f.pack(pady=2)
            self._row_frames.append(f)
        self._render_keys()

    def _render_keys(self):
        for f in self._row_frames:
            for w in f.winfo_children():
                w.destroy()

        rows = self.NUMS if self._nummode else self.ROWS
        for i, row in enumerate(rows):
            f = self._row_frames[i]
            for key in row:
                display = key
                if key == "SPACE":
                    w = 18
                elif key in ("SHIFT", "⌫", "123", "ABC"):
                    w = 7
                else:
                    w = 4

                is_special = key in ("SHIFT", "⌫", "SPACE", "123", "ABC", ".")
                btn_bg = theme.BTN_ORANGE_BG if is_special else theme.BTN_BG
                btn_hv = theme.BTN_ORANGE_HOV if is_special else theme.BTN_HOVER

                if key == "SHIFT" and self._shifted:
                    btn_bg = theme.BTN_SUCCESS_BG
                    btn_hv = theme.BTN_SUCCESS_HOV

                disp = key
                if not self._nummode and key not in ("SHIFT","⌫","SPACE","123"):
                    disp = key.upper() if self._shifted else key.lower()

                b = tk.Button(
                    f, text=disp, width=w,
                    bg=btn_bg, fg="white",
                    activebackground=btn_hv, activeforeground="white",
                    font=theme.F_SMALL, relief="flat", bd=0,
                    cursor="hand2", highlightthickness=0,
                    command=lambda k=key: self._press(k),
                )
                b.pack(side="left", padx=1, ipady=6)

    def _press(self, key):
        if self._entry is None:
            return
        if key == "⌫":
            cur = self._entry.get()
            if cur:
                self._entry.delete(len(cur)-1, tk.END)
        elif key == "SPACE":
            self._entry.insert(tk.END, " ")
        elif key == "SHIFT":
            self._shifted = not self._shifted
            self._render_keys()
            return
        elif key == "123":
            self._nummode = True
            self._render_keys()
            return
        elif key == "ABC":
            self._nummode = False
            self._render_keys()
            return
        else:
            char = key.upper() if self._shifted else key.lower()
            if self._nummode:
                char = key
            self._entry.insert(tk.END, char)
            if self._shifted:
                self._shifted = False
                self._render_keys()
                return
        # Trigger any trace callbacks
        self._entry.event_generate("<<Modified>>")


# ── PIN Pad ───────────────────────────────────────────────────────────────────

class PINPad(tk.Frame):
    """Numeric PIN entry pad."""

    def __init__(self, parent, on_confirm=None, bg=None, **kwargs):
        _bg = bg or theme.CONTENT_BG
        super().__init__(parent, bg=_bg, **kwargs)
        self._on_confirm = on_confirm
        self._bg = _bg
        self._pin_var = tk.StringVar()

        # Display
        disp_row = tk.Frame(self, bg=_bg)
        disp_row.pack(pady=(0, 8))
        self._disp = tk.Entry(disp_row, textvariable=self._pin_var,
                               show="•", width=12, state="readonly",
                               font=theme.F_H2, relief="flat", bd=0,
                               highlightthickness=2,
                               highlightbackground=theme.ENT_BORDER,
                               readonlybackground=theme.ENT_BG,
                               fg=theme.PRIMARY_TEXT)
        self._disp.pack()

        # Grid
        keys = [
            ["1","2","3"],
            ["4","5","6"],
            ["7","8","9"],
            ["DEL","0","ENT"],
        ]
        for row in keys:
            r = tk.Frame(self, bg=_bg)
            r.pack(pady=2)
            for k in row:
                bg_col = (theme.BTN_DANGER_BG if k == "DEL"
                          else theme.BTN_SUCCESS_BG if k == "ENT"
                          else theme.BTN_BG)
                hv_col = (theme.BTN_DANGER_HOV if k == "DEL"
                          else theme.BTN_SUCCESS_HOV if k == "ENT"
                          else theme.BTN_HOVER)
                tk.Button(
                    r, text=k, width=5,
                    bg=bg_col, fg="white",
                    activebackground=hv_col, activeforeground="white",
                    font=theme.F_H3, relief="flat", bd=0,
                    cursor="hand2", highlightthickness=0,
                    command=lambda x=k: self._press(x),
                ).pack(side="left", padx=4, ipady=10)

    def _press(self, key):
        if key == "DEL":
            cur = self._pin_var.get()
            self._pin_var.set(cur[:-1])
        elif key == "ENT":
            if self._on_confirm:
                self._on_confirm(self._pin_var.get())
        else:
            if len(self._pin_var.get()) < 8:
                self._pin_var.set(self._pin_var.get() + key)

    def clear(self):
        self._pin_var.set("")

    def get_pin(self):
        return self._pin_var.get()


# ── Scrollable Frame helper ───────────────────────────────────────────────────

class ScrollFrame(tk.Frame):
    """A frame with an internal scrollable canvas. Touch-scroll enabled."""

    def __init__(self, parent, bg=None, **kwargs):
        _bg = bg or theme.CONTENT_BG
        super().__init__(parent, bg=_bg, **kwargs)
        self._bg = _bg

        self._canvas = tk.Canvas(self, bg=_bg, highlightthickness=0)
        self._sb     = tk.Scrollbar(self, orient="vertical", width=30,
                                    command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._sb.set)
        self._canvas.pack(side="left", fill="both", expand=True)
        self._sb.pack(side="right", fill="y")

        self.inner = tk.Frame(self._canvas, bg=_bg)
        self._win  = self._canvas.create_window((0, 0), window=self.inner, anchor="nw")

        self.inner.bind("<Configure>", self._on_inner_resize)
        self._canvas.bind("<Configure>", self._on_canvas_resize)

        # Touch scroll
        self._canvas.bind("<ButtonPress-1>",  self._ts_start)
        self._canvas.bind("<B1-Motion>",       self._ts_move)
        self.inner.bind("<ButtonPress-1>",     self._ts_start)
        self.inner.bind("<B1-Motion>",         self._ts_move)

        # Mousewheel
        self._canvas.bind("<MouseWheel>",      self._on_wheel)
        self._canvas.bind("<Button-4>",        lambda e: self._canvas.yview_scroll(-1, "units"))
        self._canvas.bind("<Button-5>",        lambda e: self._canvas.yview_scroll(1,  "units"))

    def _on_inner_resize(self, e):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_resize(self, e):
        self._canvas.itemconfig(self._win, width=e.width)

    def _ts_start(self, e): self._ty0 = e.y_root
    def _ts_move(self, e):
        delta = self._ty0 - e.y_root
        self._canvas.yview_scroll(int(delta / 8), "units")
        self._ty0 = e.y_root

    def _on_wheel(self, e):
        self._canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

    def scroll_to_top(self):
        self._canvas.yview_moveto(0)
