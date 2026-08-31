"""Horoscope section renderer for the Sky Tonight screamsheet.

Renders two personalized horoscope readings side-by-side in a 2-column layout,
one per configured person.  Section is silently skipped when no people are
configured.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, HRFlowable

from ..base import Section
from ..config import PersonConfig
from ..llm.config import DEFAULT_LLM_CONFIG
from ..llm.summarizers import HoroscopeSummarizer
from ..providers.astro_provider import AstroDataProvider

logger = logging.getLogger(__name__)

# Register Unicode-capable TTF fonts for rendering astrological symbols
_UNICODE_FONT = "Helvetica"
_UNICODE_FONT_BOLD = "Helvetica-Bold"

from reportlab.pdfbase.pdfmetrics import registerFontFamily

_FONT_CANDIDATES = [
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/truetype/freefont/FreeSans.ttf", "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"),
    ("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf", "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"),
]
for _reg, _bold in _FONT_CANDIDATES:
    if os.path.exists(_reg):
        try:
            pdfmetrics.registerFont(TTFont("_HoroUnicode", _reg))
            _UNICODE_FONT = "_HoroUnicode"
            if os.path.exists(_bold):
                pdfmetrics.registerFont(TTFont("_HoroUnicodeBold", _bold))
                _UNICODE_FONT_BOLD = "_HoroUnicodeBold"
                registerFontFamily("_HoroUnicode", normal="_HoroUnicode", bold="_HoroUnicodeBold", italic="_HoroUnicode", boldItalic="_HoroUnicodeBold")
            else:
                _UNICODE_FONT_BOLD = "_HoroUnicode"
                registerFontFamily("_HoroUnicode", normal="_HoroUnicode", bold="_HoroUnicode", italic="_HoroUnicode", boldItalic="_HoroUnicode")
        except Exception:
            pass
        break


# Set of astrological unicode glyphs for selective enlargement
_ASTRO_GLYPHS = set("☉☽☿♀♂♃♄♅♆♇☌□△☍⚻♈♉♊♋♌♍♎♏♐♑♒♓∗✱*")


def _enlarge_astro_glyphs(text: str, size: int = 11) -> str:
    """Enlarge astrological symbols within text using ReportLab inline font tags."""
    # Normalize missing font sextile glyph U+26B9 to standard asterisk operator U+2217 (∗)
    normalized = text.replace("\u26b9", "\u2217")
    chars = []
    for ch in normalized:
        if ch in _ASTRO_GLYPHS:
            chars.append(f"<font size='{size}'>{ch}</font>")
        else:
            chars.append(ch)
    return "".join(chars)


class SkyHoroscopeSection(Section):
    """Renders two horoscope readings side-by-side for configured people.

    Args:
        title:          Section heading.
        provider:       SkyDataProvider instance (Skyfield — used for Zodiac/highlights).
        date:           Target date (tonight).
        location_name:  Observer location (passed to the LLM prompt).
        people:         List of up to 2 PersonConfig entries.  If empty,
                        ``has_content()`` returns False and the section is
                        omitted from the PDF.
        astro_provider: Optional AstroDataProvider (Swiss Ephemeris).  When
                        supplied, planet positions and aspects for the horoscope
                        are sourced from Swiss Ephemeris instead of Skyfield.
        horoscope_style: Default prompt style ("kepler" or "playbook").
    """

    def __init__(
        self,
        title: str,
        provider: Any,
        date: datetime,
        location_name: str,
        people: List[PersonConfig],
        astro_provider: Optional[AstroDataProvider] = None,
        horoscope_style: str = "kepler",
    ) -> None:
        super().__init__(title)
        self.page_slot = "back"
        self.provider = provider
        self.date = date
        self.location_name = location_name
        self.people = people
        self.astro_provider = astro_provider
        self.horoscope_style = horoscope_style
        self.astro_data: Optional[dict] = None
        self.natal_data: Dict[str, List[Dict[str, Any]]] = {}

        base = getSampleStyleSheet()
        self._heading_style = base["Heading2"]
        self._name_style = ParagraphStyle(
            "HoroName",
            parent=base["Normal"],
            fontSize=11,
            leading=14,
            fontName="Helvetica-Bold",
            spaceAfter=4,
        )
        self._body_style = ParagraphStyle(
            "HoroBody",
            parent=base["Normal"],
            fontSize=10,
            leading=13.5,
            alignment=TA_LEFT,
        )
        self._aspect_style = ParagraphStyle(
            "HoroAspect",
            parent=base["Normal"],
            fontName=_UNICODE_FONT,
            fontSize=8.5,
            leading=11.5,
            alignment=TA_LEFT,
            textColor=HexColor("#222222"),
        )
        self._legend_style = ParagraphStyle(
            "HoroLegend",
            parent=base["Normal"],
            fontName=_UNICODE_FONT,
            fontSize=7.5,
            leading=10,
            alignment=TA_CENTER,
            textColor=HexColor("#555555"),
        )

    # ------------------------------------------------------------------
    # Section interface
    # ------------------------------------------------------------------

    def has_content(self) -> bool:
        return len(self.people) > 0

    def fetch_data(self) -> None:
        self.data = self.provider.get_sky_data(self.date)
        self.natal_data = {}
        if self.astro_provider is not None:
            self.astro_data = self.astro_provider.get_horoscope_data(self.date)
            for person in self.people:
                if person.birth_date and person.birth_time:
                    self.natal_data[person.name] = self.astro_provider.get_natal_positions(
                        person.birth_date, person.birth_time
                    )

    def render(self) -> List[Any]:
        if self.data is None:
            self.fetch_data()

        elements: List[Any] = []
        elements.append(Paragraph(self.title, self._heading_style))
        elements.append(Spacer(1, 4))

        # Build one column of flowable content per person (up to 2).
        col_contents: List[List[Any]] = []
        for person in self.people[:2]:
            reading = self._get_horoscope(person)
            col: List[Any] = [
                Paragraph(person.name, self._name_style),
            ]
            # Split by double or single newlines to preserve paragraphs and aspect bullets
            paragraphs = [p.strip() for p in reading.split("\n") if p.strip()]
            for p_text in paragraphs:
                if p_text.startswith("•") or p_text.startswith("-"):
                    # Aspect / influence list items
                    p_clean = p_text.lstrip("•- ").strip()
                    # Enlarge only the glyphs (to 11.5pt) while keeping text and degrees at normal 9pt
                    p_enlarged = _enlarge_astro_glyphs(p_clean, size=12)
                    line_html = f"&bull; {p_enlarged}"

                    col.append(Paragraph(line_html, self._aspect_style))
                    col.append(Spacer(1, 2))
                else:
                    # Bold only the lead-in prefix if present
                    lower_p = p_text.lower()
                    if lower_p.startswith("where to watch your step:"):
                        prefix_len = len("where to watch your step:")
                        lead = p_text[:prefix_len]
                        rest = p_text[prefix_len:]
                        p_html = f"<b>{lead}</b>{rest}"
                    elif lower_p.startswith("your move:"):
                        prefix_len = len("your move:")
                        lead = p_text[:prefix_len]
                        rest = p_text[prefix_len:]
                        p_html = f"<b>{lead}</b>{rest}"
                    elif lower_p.startswith("key influences & aspects:") or lower_p.startswith("key influences and aspects:"):
                        p_html = f"<b>{p_text}</b>"
                    else:
                        p_html = p_text

                    col.append(Paragraph(p_html, self._body_style))
                    col.append(Spacer(1, 4))

            col_contents.append(col)

        # Pad to exactly 2 columns so the Table always has 2 cells.
        while len(col_contents) < 2:
            col_contents.append([Paragraph("", self._body_style)])

        # 540pt usable width, 10pt gutter → ~265pt per column.
        col_w = 265.0
        gutter = 10.0
        table = Table(
            [col_contents],
            colWidths=[col_w, col_w],
            spaceBefore=0,
            spaceAfter=0,
        )
        table.setStyle(TableStyle([
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING",   (0, 0), (0, -1),  0),
            ("RIGHTPADDING",  (0, 0), (0, -1),  gutter),
            ("LEFTPADDING",   (1, 0), (1, -1),  gutter),
            ("RIGHTPADDING",  (1, 0), (1, -1),  0),
            ("LINEAFTER",     (0, 0), (0, -1),  0.5, HexColor("#CCCCCC")),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 6))

        # Aspect Symbol Legend anchored at the bottom of the page (glyphs enlarged)
        legend_text = (
            "<b>Aspects:</b> &nbsp; "
            "<font size='10'>&#x260C;</font> Conjunction (0&deg;) &nbsp;&bull;&nbsp; "
            "<font size='10'>&#x2217;</font> Sextile (60&deg;) &nbsp;&bull;&nbsp; "
            "<font size='10'>&#x25A1;</font> Square (90&deg;) &nbsp;&bull;&nbsp; "
            "<font size='10'>&#x25B3;</font> Trine (120&deg;) &nbsp;&bull;&nbsp; "
            "<font size='10'>&#x260D;</font> Opposition (180&deg;)"
        )
        elements.append(HRFlowable(width="100%", thickness=0.4, color=HexColor("#DDDDDD"), spaceAfter=3))
        elements.append(Paragraph(legend_text, self._legend_style))
        return elements

    def render_markdown(self) -> str:
        """Render horoscope readings sequentially for each person."""
        if not self.has_content():
            return ""
        if self.data is None:
            self.fetch_data()
        
        lines = []
        for person in self.people:
            reading = self._get_horoscope(person)
            lines.append(f"### {person.name}\n\n{reading}")
        
        return "\n\n---\n\n".join(lines)


    # ------------------------------------------------------------------
    # LLM integration
    # ------------------------------------------------------------------

    def _get_horoscope(self, person: PersonConfig) -> str:
        """Return a ~200-word horoscope for *person*, or a fallback message.

        When ``astro_provider`` is set, planet positions and aspects are sourced
        from Swiss Ephemeris (tropical zodiac, vernal-equinox anchored).  When
        not set, falls back to Skyfield positions from the sky data dict.
        """
        logger.info("Generating horoscope for %s", person.name)
        sky: Dict[str, Any] = self.data or {}
        astro = self.astro_data
        natal_planets = self.natal_data.get(person.name, [])

        gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        grok_key = os.getenv("GROK_API_KEY") or os.getenv("XAI_API_KEY")

        if not gemini_key and not grok_key:
            return (
                f"No API key configured — horoscope unavailable for {person.name}. "
                "Set GEMINI_API_KEY or GROK_API_KEY to enable readings."
            )

        try:
            person_style = getattr(person, "horoscope_style", None) or self.horoscope_style or "kepler"
            logger.info("Generating horoscope for %s using style='%s'", person.name, person_style)
            summarizer = HoroscopeSummarizer(
                gemini_api_key=gemini_key,
                grok_api_key=grok_key,
                config=DEFAULT_LLM_CONFIG,
                style=person_style,
            )

            # Transit planets: Swiss Ephemeris when available, else Skyfield fallback.
            transit_source: List[Dict[str, Any]] = astro["planets"] if astro else sky.get("planets", [])
            aspects_list: List[Dict[str, Any]] = astro["aspects"] if astro else []
            moon_phase: str = astro["moon_phase"] if astro else sky.get("moon_phase", "")
            ingresses: List[Dict[str, Any]] = astro.get("ingresses", []) if astro else []
            eclipses: List[Dict[str, Any]] = astro.get("eclipses", []) if astro else []

            # Auto-compute Sun, Moon, and Ascendant signs if omitted in config
            sun_sign = person.sun_sign
            moon_sign = person.moon_sign
            ascendant = person.ascendant

            if person.birth_date and (not sun_sign or not moon_sign or not ascendant):
                obs_lat = person.lat if person.lat is not None else getattr(self.provider, "lat", None)
                obs_lon = person.lon if person.lon is not None else getattr(self.provider, "lon", None)
                computed = AstroDataProvider.compute_natal_signs(
                    person.birth_date,
                    person.birth_time,
                    location_str=person.birth_location,
                    lat=obs_lat,
                    lon=obs_lon,
                )
                sun_sign = sun_sign or computed.get("sun_sign", "")
                moon_sign = moon_sign or computed.get("moon_sign", "")
                ascendant = ascendant or computed.get("ascendant", "")

            # Enrich each transit planet with whole-sign house + dignity.
            house_map = AstroDataProvider.get_whole_sign_houses(ascendant) if ascendant else {}
            transit_enriched: List[Dict[str, Any]] = []
            for p in transit_source:
                house_num = AstroDataProvider._assign_house(p["zodiac"], ascendant) if ascendant else 0
                house_info = house_map.get(house_num, {})
                dignity = AstroDataProvider._get_planet_dignity(p["name"], p["zodiac"])
                transit_enriched.append({
                    **p,
                    "house_number": house_num,
                    "house_meaning": house_info.get("meaning", ""),
                    "dignity": dignity,
                })

            # Hits: transit planets within 3° of natal planets.
            hits = AstroDataProvider._find_transit_hits(transit_source, natal_planets) if natal_planets else []

            # Build subject_natal block.
            natal_planet_str = ", ".join(
                f"{p['name']} in {p['zodiac']}" for p in natal_planets
            )
            natal_line = f"Natal planets: {natal_planet_str}\n" if natal_planet_str else ""
            subject_natal = (
                f"Sun: {sun_sign} | Moon: {moon_sign} | Ascendant: {ascendant}\n"
                f"{natal_line}"
            ).strip()

            # Build current_sky block.
            planet_lines: List[str] = []
            for p in transit_enriched:
                motion_str = f" ({p['motion_status']})" if p.get("motion_status") and p["motion_status"] != "Direct" else ""
                if p.get("house_number"):
                    planet_lines.append(
                        f"- {p['name']}{motion_str} in {p['zodiac']} "
                        f"(House {p['house_number']}: {p['house_meaning']}) [{p['dignity']}]"
                    )
                else:
                    planet_lines.append(f"- {p['name']}{motion_str} in {p['zodiac']} [{p['dignity']}]")

            aspects_str = ", ".join(
                a.get("formatted", f"{a['planet_a']} {a['aspect']} {a['planet_b']} (orb {a['orb']}°)") for a in aspects_list
            ) or "None"

            hits_str = "\n".join(
                f"- Transit {h['transit_planet']} conjunct natal {h['natal_planet']} (orb: {h['orb']}°)"
                for h in hits
            ) or "None"

            ingresses_str = "\n".join(f"- {i['formatted']}" for i in ingresses) if ingresses else "None"
            eclipses_str = "\n".join(f"- {e['formatted']}" for e in eclipses) if eclipses else "None"

            current_sky = (
                "Transit planets:\n" + "\n".join(planet_lines) + "\n\n"
                f"Key aspects: {aspects_str}\n\n"
                f"Sign ingresses today:\n{ingresses_str}\n\n"
                f"Astrological eclipses:\n{eclipses_str}\n\n"
                f"Hits (transit conjunct natal, orb ≤3°):\n{hits_str}\n\n"
                f"Moon phase: {moon_phase}"
            )

            llm_choice = "gemini" if gemini_key else "grok"
            result = summarizer.generate_summary(
                llm_choice=llm_choice,
                data={
                    "name": person.name,
                    "birth_date": person.birth_date,
                    "birth_time": person.birth_time,
                    "birth_location": person.birth_location,
                    "date": self.date.strftime("%B %d, %Y"),
                    "location": self.location_name,
                    "subject_natal": subject_natal,
                    "current_sky": current_sky,
                },
            )
            result_text = str(result).strip() if result else f"Horoscope unavailable for {person.name}."
            word_count = len(result_text.split())
            logger.info("Horoscope for %s complete: %d words", person.name, word_count)
            return result_text
        except Exception as exc:  # noqa: BLE001
            logger.warning("Horoscope generation failed for %s: %s", person.name, exc)
            return f"Horoscope unavailable for {person.name}."

