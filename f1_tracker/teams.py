from __future__ import annotations

import colorsys
import hashlib
from functools import lru_cache

from f1_tracker.config import TEAM_COLORS


@lru_cache(maxsize=256)
def team_color(name: str | None) -> str:
    """Livery colour for a constructor name; stable generated hue otherwise."""
    key = (name or "").strip().lower()
    if not key or key == "-":
        return "#566070"
    for needle, color in TEAM_COLORS:
        if needle in key:
            return color
    hue = int(hashlib.md5(key.encode("utf-8")).hexdigest()[:6], 16) / 0xFFFFFF
    r, g, b = colorsys.hls_to_rgb(hue, 0.6, 0.55)
    return f"#{int(r * 255):02X}{int(g * 255):02X}{int(b * 255):02X}"
