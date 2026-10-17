from datetime import datetime
from pathlib import Path

APP_TITLE = "F1 Tracker"
VERSION = "2.1.0"
WINDOW_SIZE = (1320, 840)
MIN_WINDOW_SIZE = (960, 600)

# ---------------------------------------------------------------------------
# F1-inspired dark theme
# ---------------------------------------------------------------------------
BG_DARK = "#0E1116"
BG_SIDEBAR = "#12161E"
BG_PANEL = "#171D26"
BG_PANEL_2 = "#1E2631"
BG_INPUT = "#10151B"
BORDER = "#232B35"
BORDER_STRONG = "#2E3946"

TEXT = "#F2F5F7"
TEXT_MUTED = "#8B96A5"
TEXT_DIM = "#566070"

ACCENT = "#E10600"
ACCENT_HOVER = "#FF1801"
ACCENT_SOFT = "#2A1518"

GOLD = "#FFD700"
SILVER = "#C0C0C0"
BRONZE = "#CD7F32"

SUCCESS = "#2ECC71"
WARNING = "#F5B94D"
INFO = "#4FC3F7"
DANGER = "#E74C3C"

# Bundled display font (assets/fonts); falls back to the platform UI font.
FONT = "Titillium Web"
FONT_FALLBACKS = ("Segoe UI", "SF Pro Display", "Inter", "Cantarell", "Noto Sans", "DejaVu Sans")

# ---------------------------------------------------------------------------
# Paths / network
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = PROJECT_ROOT / "assets"
CACHE_DIR = PROJECT_ROOT / "cache"

JOLPICA_BASE_URL = "https://api.jolpi.ca/ergast/f1"
HTTP_USER_AGENT = "F1Tracker/2.1 (desktop; PyQt6)"
FONTS_DIR = ASSETS_DIR / "fonts"
HTTP_CACHE_DIR = CACHE_DIR / "jolpica"
# Data for the season in progress changes after every race weekend; older
# seasons are final and cached forever.
LIVE_CACHE_TTL_SECONDS = 30 * 60
F1_SEASON_RANGE = (1950, datetime.now().year)

# ---------------------------------------------------------------------------
# Team colours (matched by substring, most specific first)
# ---------------------------------------------------------------------------
TEAM_COLORS: tuple[tuple[str, str], ...] = (
    ("red bull", "#3671C6"),
    ("racing bulls", "#6692FF"),
    ("rb f1", "#6692FF"),
    ("cash app rb", "#6692FF"),
    ("alphatauri", "#5E8FAA"),
    ("toro rosso", "#469BFF"),
    ("mercedes", "#27F4D2"),
    ("ferrari", "#E8002D"),
    ("mclaren", "#FF8000"),
    ("aston martin", "#229971"),
    ("alpine", "#0093CC"),
    ("williams", "#64C4FF"),
    ("haas", "#B6BABD"),
    ("audi", "#FF2D00"),
    ("kick sauber", "#52E252"),
    ("stake", "#52E252"),
    ("alfa romeo", "#B12039"),
    ("sauber", "#52E252"),
    ("cadillac", "#C9A84C"),
    ("racing point", "#F596C8"),
    ("force india", "#F596C8"),
    ("renault", "#FFF500"),
    ("lotus", "#FFB800"),
    ("brawn", "#B8FD6E"),
    ("toyota", "#CC0000"),
    ("bmw", "#0066CC"),
    ("jordan", "#F9D71C"),
    ("benetton", "#00A6E0"),
    ("tyrrell", "#1E5AA8"),
    ("brabham", "#2E8B57"),
    ("minardi", "#C8C8C8"),
)