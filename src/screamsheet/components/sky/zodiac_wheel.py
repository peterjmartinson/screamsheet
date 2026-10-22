"""Zodiac wheel component for the Sky Tonight screamsheet."""
from __future__ import annotations

import math
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, cast

from reportlab.graphics.shapes import Circle, Drawing, Group, Line, String, Wedge
from reportlab.lib.colors import HexColor, black
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from ...providers.sky_provider import SkyDataProvider
from ..base import ComponentLayoutSpec, ScreamsheetComponent
from ..registry import ComponentRegistry

_WHEEL_SIZE = 520
_OUTER_R = 236.0
_RIM_R = _OUTER_R * 0.90
_INNER_R = _OUTER_R * 0.72

_PLANET_RADII: dict[str, float] = {
    "Sun": _OUTER_R * 0.36,
    "Moon": _OUTER_R * 0.40,
    "Mercury": _OUTER_R * 0.44,
    "Venus": _OUTER_R * 0.48,
    "Mars": _OUTER_R * 0.52,
    "Jupiter": _OUTER_R * 0.56,
    "Saturn": _OUTER_R * 0.60,
    "Uranus": _OUTER_R * 0.62,
    "Neptune": _OUTER_R * 0.64,
}

_VISIBLE_FILL = HexColor("#BBBBBB")
_INVISIBLE_FILL = HexColor("#FFFFFF")
_VISIBLE_TEXT = black
_INVISIBLE_TEXT = black

_PLANET_SYMBOLS: dict[str, str] = {
    "Sun": "\u2609",
    "Moon": "\u263d",
    "Mercury": "\u263f",
    "Venus": "\u2640",
    "Mars": "\u2642",
    "Jupiter": "\u2643",
    "Saturn": "\u2644",
    "Uranus": "\u2645",
    "Neptune": "\u2646",
}

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


@ComponentRegistry.register("zodiac_wheel")
class ZodiacWheelComponent(ScreamsheetComponent):
    """Renders a zodiac wheel showing planet positions as a ReportLab Drawing."""

    component_type = "zodiac_wheel"
    layout_spec = ComponentLayoutSpec(
        weight=0.60,
        component_family="zodiac_wheel",
        max_on_front_page=1,
        max_per_page=1,
    )

    def __init__(
        self,
        title: str = "",
        provider: Optional[Any] = None,
        date: Optional[datetime] = None,
        lat: float = 40.02,
        lon: float = -75.34,
        location_name: str = "Bryn Mawr, PA",
        **kwargs: Any,
    ) -> None:
        self.lat = lat
        self.lon = lon
        self.location_name = location_name
        super().__init__(
            title=title,
            provider=provider,
            date=date if date is not None else datetime.now(),
            lat=lat,
            lon=lon,
            location_name=location_name,
            **kwargs,
        )

    def create_default_provider(self) -> Any:
        return SkyDataProvider(lat=self.lat, lon=self.lon, location_name=self.location_name)

    def fetch_data(self) -> None:
        self.data = self.provider.get_sky_data(self.date)

    def has_content(self) -> bool:
        if self.data is None:
            self.fetch_data()
        return bool(self.data and self.data.get("planets"))

    def render(
        self,
        styles: Optional[Any] = None,
        max_width: Optional[float] = None,
    ) -> List[Any]:
        if self.data is None:
            self.fetch_data()

        base_styles = getSampleStyleSheet()
        elements: List[Any] = []
        if self.title:
            elements.append(Paragraph(self.title, base_styles["Heading2"]))
            elements.append(Spacer(1, 4))
        elements.append(self._build_drawing())
        elements.append(Spacer(1, 10))
        elements.extend(self._build_glossary())
        return elements

    def _build_glossary(self) -> List[Any]:
        """Compact two-row symbol/name legend for all nine planets."""
        base = getSampleStyleSheet()
        glyph_style = ParagraphStyle(
            "WheelGlyph",
            parent=base["Normal"],
            fontSize=16,
            leading=19,
            alignment=TA_CENTER,
        )
        gloss_style = ParagraphStyle(
            "WheelGloss",
            parent=base["Normal"],
            fontSize=10,
            leading=13,
            fontName="Helvetica-Bold",
            alignment=TA_CENTER,
        )
        ordered = [
            "Sun", "Moon", "Mercury", "Venus", "Mars",
            "Jupiter", "Saturn", "Uranus", "Neptune",
        ]
        symbol_cells = [
            Paragraph(
                f"<font name='{_UNICODE_FONT}' size='16'>{_PLANET_SYMBOLS[n]}</font>",
                glyph_style,
            )
            for n in ordered
        ]
        name_cells = [Paragraph(n, gloss_style) for n in ordered]
        col_w = 54
        table = Table([symbol_cells, name_cells], colWidths=[col_w] * len(ordered))
        table.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("LINEABOVE", (0, 0), (-1, 0), 0.5, HexColor("#AAAAAA")),
                ]
            )
        )
        return [table]

    def _build_drawing(self, size: float = 460.0) -> Drawing:
        """Build the vector Zodiac Wheel scaled to *size*."""
        cx = cy = size / 2.0
        d = Drawing(size, size)
        d.hAlign = "CENTER"

        scale = size / 520.0
        outer_r = _OUTER_R * scale
        rim_r = _RIM_R * scale
        inner_r = _INNER_R * scale

        sky_data: Dict[str, Any] = cast(Dict[str, Any], self.data) if isinstance(self.data, dict) else {}
        visible: List[str] = sky_data.get("visible_constellations", [])
        planets: List[Dict[str, Any]] = sky_data.get("planets", [])

        for i, full in enumerate(_ZODIAC_FULL):
            start_deg = i * 30
            is_visible = full in visible
            fill = _VISIBLE_FILL if is_visible else _INVISIBLE_FILL
            text_col = _VISIBLE_TEXT if is_visible else _INVISIBLE_TEXT

            w = Wedge(cx, cy, outer_r, start_deg, start_deg + 30, radius1=inner_r)
            w.fillColor = fill
            w.strokeColor = black
            w.strokeWidth = 0.8
            d.add(w)

            mid_deg = float(start_deg + 15)
            mid_rad = math.radians(mid_deg)
            lx = cx + rim_r * math.cos(mid_rad)
            ly = cy + rim_r * math.sin(mid_rad)
            rot_rad = math.radians(mid_deg - 90.0)
            cos_t, sin_t = math.cos(rot_rad), math.sin(rot_rad)
            s = String(
                0, -3, full, fontSize=15, textAnchor="middle", fontName="Helvetica-Bold", fillColor=text_col
            )
            g = Group(s)
            g.transform = (cos_t, sin_t, -sin_t, cos_t, lx, ly)
            d.add(g)

        inner_circle = Circle(cx, cy, inner_r)
        inner_circle.fillColor = HexColor("#FFFFFF")
        inner_circle.strokeColor = black
        inner_circle.strokeWidth = 1.0
        d.add(inner_circle)

        for i in range(12):
            angle_rad = math.radians(i * 30)
            sx = cx + inner_r * math.cos(angle_rad)
            sy = cy + inner_r * math.sin(angle_rad)
            spoke = Line(cx, cy, sx, sy)
            spoke.strokeColor = black
            spoke.strokeWidth = 0.5
            d.add(spoke)

        for planet in planets:
            lon_deg = float(planet.get("ecliptic_lon", 0))
            name = str(planet.get("name", ""))
            two_letter = str(planet.get("two_letter", name[:2]))

            radius = _PLANET_RADII.get(name, _OUTER_R * 0.54) * scale
            angle_rad = math.radians(lon_deg)
            px = cx + radius * math.cos(angle_rad)
            py = cy + radius * math.sin(angle_rad)

            symbol = _PLANET_SYMBOLS.get(name, two_letter)
            font = _UNICODE_FONT if name in _PLANET_SYMBOLS else "Helvetica"

            d.add(
                String(
                    px, py - 10, symbol, fontSize=28, textAnchor="middle", fontName=font, fillColor=black
                )
            )

        dot = Circle(cx, cy, 4)
        dot.fillColor = black
        dot.strokeColor = None
        d.add(dot)

        return d
