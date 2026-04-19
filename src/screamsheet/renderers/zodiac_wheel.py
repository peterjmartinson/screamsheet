"""Zodiac wheel renderer for the Sky Tonight screamsheet.

Draws a full circular zodiac wheel using ReportLab vector graphics:
  - 12 alternating grayscale annular wedges labelled with 3-letter sign abbreviations
  - Planet astrological symbols at their ecliptic longitude positions
  - A semi-transparent gray overlay for zodiac signs visible above the horizon
"""
from __future__ import annotations

import math
import os
from datetime import datetime
from typing import Any, Dict, List, cast

from reportlab.graphics.shapes import (
    Drawing,
    Wedge,
    Circle,
    String,
)
from reportlab.lib.colors import (
    HexColor,
    black,
    Color,
)
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, Spacer

from ..base import Section

# ---------------------------------------------------------------------------
# Visual constants
# ---------------------------------------------------------------------------
_WHEEL_SIZE = 260          # drawing canvas size (points)
_OUTER_R = 118.0           # outer radius of the sign ring
_RIM_R = _OUTER_R * 0.90  # label radius (centre of rim band)
_INNER_R = _OUTER_R * 0.72 # inner edge of sign ring / outer edge of planet zone
_PLANET_R = _OUTER_R * 0.54  # radius at which planet symbols are placed

# Grayscale alternating wedge fills
_SIGN_COLORS = (HexColor("#F0F0F0"), HexColor("#D8D8D8"))

# Visible-sign overlay: semi-transparent gray
_VISIBLE_OVERLAY_GRAY = Color(0.5, 0.5, 0.5, alpha=0.3)

# Astrological symbols for the nine visible planets/luminaries
_PLANET_SYMBOLS: dict[str, str] = {
    "Sun":     "\u2609",  # ☉
    "Moon":    "\u263d",  # ☽
    "Mercury": "\u263f",  # ☿
    "Venus":   "\u2640",  # ♀
    "Mars":    "\u2642",  # ♂
    "Jupiter": "\u2643",  # ♃
    "Saturn":  "\u2644",  # ♄
    "Uranus":  "\u2645",  # ♅
    "Neptune": "\u2646",  # ♆
}

# Register a Unicode-capable TTF font for rendering the symbols.
# Falls back to Helvetica (symbols won't render) if none is found.
_UNICODE_FONT = "Helvetica"
_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
]
for _fp in _FONT_CANDIDATES:
    if os.path.exists(_fp):
        try:
            pdfmetrics.registerFont(TTFont("_ZodiacUnicode", _fp))
            _UNICODE_FONT = "_ZodiacUnicode"
        except Exception:
            pass
        break

_ZODIAC_SHORT = [
    "Ari", "Tau", "Gem", "Can", "Leo", "Vir",
    "Lib", "Sco", "Sag", "Cap", "Aqu", "Psc",
]
_ZODIAC_FULL = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpius", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]


class ZodiacWheelSection(Section):
    """Renders a zodiac wheel showing planet positions as a ReportLab Drawing.

    Args:
        title:    Section heading.
        provider: SkyDataProvider instance.
        date:     Target date (tonight).
    """

    def __init__(self, title: str, provider: Any, date: datetime) -> None:
        super().__init__(title)
        self.provider = provider
        self.date = date

    # ------------------------------------------------------------------
    # Section interface
    # ------------------------------------------------------------------

    def fetch_data(self) -> None:
        self.data = self.provider.get_sky_data(self.date)

    def has_content(self) -> bool:
        if self.data is None:
            self.fetch_data()
        return bool(self.data and self.data.get("planets"))

    def render(self) -> List[Any]:
        if self.data is None:
            self.fetch_data()

        styles = getSampleStyleSheet()
        elements: List[Any] = []
        elements.append(Paragraph(self.title, styles["Heading2"]))
        elements.append(Spacer(1, 4))
        elements.append(self._build_drawing())
        return elements

    # ------------------------------------------------------------------
    # Drawing construction
    # ------------------------------------------------------------------

    def _build_drawing(self) -> Drawing:
        cx = cy = _WHEEL_SIZE / 2
        d = Drawing(_WHEEL_SIZE, _WHEEL_SIZE)
        d.hAlign = "CENTER"

        sky_data: Dict[str, Any] = cast(Dict[str, Any], self.data) if isinstance(self.data, dict) else {}
        visible: List[str] = sky_data.get("visible_constellations", [])
        planets: List[Dict[str, Any]] = sky_data.get("planets", [])

        # Zodiac wedges (ecliptic 0° = Aries at right, grows CCW)
        for i, (short, full) in enumerate(zip(_ZODIAC_SHORT, _ZODIAC_FULL)):
            start_deg = i * 30
            fill = _SIGN_COLORS[i % 2]

            # Annular wedge (outer ring)
            w = Wedge(cx, cy, _OUTER_R, start_deg, start_deg + 30, radius1=_INNER_R)
            w.fillColor = fill
            w.strokeColor = black
            w.strokeWidth = 0.4
            d.add(w)

            # Visible overlay (gray tint)
            if full in visible:
                overlay = Wedge(cx, cy, _OUTER_R, start_deg, start_deg + 30, radius1=_INNER_R)
                overlay.fillColor = _VISIBLE_OVERLAY_GRAY
                overlay.strokeColor = None
                d.add(overlay)

            # Sign label on rim
            mid_rad = math.radians(start_deg + 15)
            lx = cx + _RIM_R * math.cos(mid_rad)
            ly = cy + _RIM_R * math.sin(mid_rad)
            d.add(String(lx, ly - 3, short, fontSize=6.5, textAnchor="middle",
                          fillColor=black))

        # Inner circle border
        inner_circle = Circle(cx, cy, _INNER_R)
        inner_circle.fillColor = HexColor("#FFFFFF")
        inner_circle.strokeColor = black
        inner_circle.strokeWidth = 0.5
        d.add(inner_circle)

        # Central dot
        dot = Circle(cx, cy, 2)
        dot.fillColor = black
        dot.strokeColor = None
        d.add(dot)

        # Planet symbols (astrological Unicode glyphs, or two-letter fallback)
        for planet in planets:
            lon_deg = float(planet.get("ecliptic_lon", 0))
            name = str(planet.get("name", ""))
            two_letter = str(planet.get("two_letter", name[:2]))

            angle_rad = math.radians(lon_deg)
            px = cx + _PLANET_R * math.cos(angle_rad)
            py = cy + _PLANET_R * math.sin(angle_rad)

            symbol = _PLANET_SYMBOLS.get(name, two_letter)
            font = _UNICODE_FONT if name in _PLANET_SYMBOLS else "Helvetica"

            d.add(String(px, py - 4, symbol, fontSize=10, textAnchor="middle",
                         fontName=font, fillColor=black))

        return d
