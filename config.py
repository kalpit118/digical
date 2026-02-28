"""
DigiCal Configuration Settings
"""
import os

# Application Settings
APP_NAME = "DigiCal Business Calculator"
VERSION = "1.0.0"

# Display Settings (Optimized for 720x480 Raspberry Pi Display - Landscape)
WINDOW_WIDTH = 720
WINDOW_HEIGHT = 480
DISPLAY_FONT = ("Consolas", 24, "bold")   # LCD/segmented-style font
BUTTON_FONT = ("Segoe UI", 12)
LABEL_FONT = ("Segoe UI", 11)

# ── Neumorphic Palettes ────────────────────────────────────────────────────────

# LIGHT palette  – soft sage-green background
NEU_LIGHT = {
    "bg":           "#DDE6ED",   # base surface
    "bg_dark":      "#C8D4DF",   # slightly darker variant (inset feel)
    "shadow_dark":  "#B2BFC8",   # outset shadow – dark side
    "shadow_lite":  "#FFFFFF",   # outset shadow – light side
    "display_bg":   "#C8D4DF",   # display inner area
    "display_fg":   "#1A2332",   # high-contrast dark text (LCD dark on light)
    "btn_bg":       "#DDE6ED",
    "btn_fg":       "#2B3A4A",
    "operator_fg":  "#1E7A56",   # teal-green accent
    "equals_bg":    "#2E8B57",   # sea-green confirm
    "equals_fg":    "#FFFFFF",
    "mode_fg":      "#2C5F8A",   # muted blue
    "mode_bg":      "#C8D4DF",
    "accent":       "#2E8B57",
    "text":         "#2B3A4A",
    "subtext":      "#6E8090",
    "success":      "#2E8B57",
    "danger":       "#B03A2E",
    "warning":      "#B07D1E",
    "hdr_bg":       "#C8D4DF",
    "separator":    "#B2BFC8",
    "entry_bg":     "#E8EEF4",
    "entry_fg":     "#1A2332",
    "listbox_bg":   "#C8D4DF",
    "listbox_fg":   "#1A2332",
    "tree_odd":     "#D5DFE9",
    "tree_even":    "#C8D4DF",
    "tree_fg":      "#1A2332",
}

# DARK palette  – deep slate with green accents
NEU_DARK = {
    "bg":           "#1E2530",
    "bg_dark":      "#161C26",
    "shadow_dark":  "#10161E",
    "shadow_lite":  "#283040",
    "display_bg":   "#161C26",
    "display_fg":   "#9ADDB0",   # soft green glow – LCD green-on-dark
    "btn_bg":       "#1E2530",
    "btn_fg":       "#BDD0E0",
    "operator_fg":  "#4DB888",
    "equals_bg":    "#2D8A58",
    "equals_fg":    "#FFFFFF",
    "mode_fg":      "#5E8FC8",
    "mode_bg":      "#283040",
    "accent":       "#4DB888",
    "text":         "#BDD0E0",
    "subtext":      "#4E6070",
    "success":      "#4DB888",
    "danger":       "#E55A4E",
    "warning":      "#D4A020",
    "hdr_bg":       "#161C26",
    "separator":    "#283040",
    "entry_bg":     "#283040",
    "entry_fg":     "#BDD0E0",
    "listbox_bg":   "#161C26",
    "listbox_fg":   "#9ADDB0",
    "tree_odd":     "#232E3C",
    "tree_even":    "#1A2330",
    "tree_fg":      "#BDD0E0",
}

# Legacy aliases – kept so nothing outside gui.py/config.py breaks
BG_COLOR     = NEU_LIGHT["bg"]
DISPLAY_BG   = NEU_LIGHT["display_bg"]
DISPLAY_FG   = NEU_LIGHT["display_fg"]
BUTTON_BG    = NEU_LIGHT["btn_bg"]
BUTTON_FG    = NEU_LIGHT["btn_fg"]
BUTTON_ACTIVE = NEU_LIGHT["bg_dark"]
OPERATOR_BG  = NEU_LIGHT["mode_bg"]
EQUALS_BG    = NEU_LIGHT["equals_bg"]
MODE_BG      = NEU_LIGHT["mode_bg"]


def get_theme(dark: bool) -> dict:
    """Return the active neumorphic colour palette."""
    return NEU_DARK if dark else NEU_LIGHT


# Database Settings
DB_PATH = os.path.join(os.path.dirname(__file__), "digical.db")

# Currency Settings
CURRENCY_SYMBOL = "₹"

# Payment Methods
PAYMENT_METHODS = ["UPI", "Cash", "Due"]

# Default Categories
DEFAULT_SALES_CATEGORIES = [
    "Product Sales",
    "Service Sales",
    "Consulting",
    "Other Income"
]

DEFAULT_EXPENSE_CATEGORIES = [
    "Rent",
    "Utilities",
    "Supplies",
    "Salaries",
    "Marketing",
    "Transportation",
    "Other Expenses"
]

DEFAULT_PRODUCT_CATEGORIES = [
    "Electronics",
    "Food & Beverages",
    "Clothing & Apparel",
    "Stationery & Office",
    "Medical & Health",
    "Household & Home",
    "Beauty & Personal Care",
    "Sports & Fitness",
    "Tools & Hardware",
    "Other"
]

# History Settings
MAX_HISTORY_ITEMS = 100

# Graph settings (Optimized for 720x480 display)
GRAPH_FIGSIZE = (5.5, 3.5)
GRAPH_DPI = 90

# Web Portal settings
WEB_HOST = '0.0.0.0'
WEB_PORT = 8888
API_REFRESH_INTERVAL = 30
