# theme.py — Colours, fonts, and style helpers
# Figma-accurate: cream content areas on purple outer background

# ── Colours ──────────────────────────────────────────────────────────────────

PAGE_BG         = "#372976"   # Deep purple — outer background / top bars
CONTENT_BG      = "#F5F3EE"   # Cream — main content areas (Figma accurate)

# Entry fields
ENT_BG          = "#FFFFFF"
ENT_BORDER      = "#372976"   # Purple border on cream bg
ENT_BORDER_FOCUS= "#d1d004"   # Yellow on focus

# Buttons — primary (purple on cream)
BTN_BG          = "#372976"   # Purple
BTN_HOVER       = "#4a3a8a"
BTN_TEXT        = "#FFFFFF"

# Accent yellow (admin / secondary actions)
BTN_YELLOW_BG   = "#d1d004"
BTN_YELLOW_HOV  = "#eded00"
BTN_YELLOW_TEXT = "#000000"

# Danger / sign-out
BTN_DANGER_BG   = "#c0392b"
BTN_DANGER_HOV  = "#e74c3c"

# Success / sign-in
BTN_SUCCESS_BG  = "#27ae60"
BTN_SUCCESS_HOV = "#2ecc71"

# Orange
BTN_ORANGE_BG   = "#c98330"
BTN_ORANGE_HOV  = "#d49a4a"

# Day-picker button (toggled ON)
DAY_ON_BG       = "#372976"
DAY_ON_FG       = "#FFFFFF"
DAY_OFF_BG      = "#E0DCF0"
DAY_OFF_FG      = "#372976"

# Text
PRIMARY_TEXT    = "#1a1a2e"   # Near-black on cream
SECONDARY_TEXT  = "#FFFFFF"   # White on purple
MUTED_TEXT      = "#7a6fb0"   # Muted purple-grey
CREAM_MUTED     = "#8a8070"   # Muted on cream

# Status
ERROR_BG        = "#c0392b"
SUCCESS_BG      = "#27ae60"

# Separator / border
BORDER_COLOR    = "#d0cbe8"   # Light border on cream
PURPLE_BORDER   = "#4a3a8a"   # Border on purple bg

# Link
LINK_TEXT       = "#372976"

# ── Fonts ─────────────────────────────────────────────────────────────────────
FONT_FAMILY = "Montserrat"

def font(size=14, weight="normal", family=None):
    return (family or FONT_FAMILY, size, weight)

F_H1    = font(32, "bold")
F_H2    = font(24, "bold")
F_H3    = font(18, "bold")
F_BODY  = font(14)
F_SMALL = font(12)
F_BTN   = font(15, "bold")
F_LABEL = font(13, "bold")
F_INPUT = font(14)
F_TINY  = font(11)
F_HUGE  = font(48, "bold")


# ── Widget style helpers ──────────────────────────────────────────────────────

def style_entry(ent, width=28, bg=None):
    ent.configure(
        bg=bg or ENT_BG,
        fg=PRIMARY_TEXT,
        font=F_INPUT,
        relief="flat",
        bd=0,
        highlightthickness=2,
        highlightbackground=ENT_BORDER,
        highlightcolor=ENT_BORDER_FOCUS,
        insertbackground=PRIMARY_TEXT,
        width=width,
    )
