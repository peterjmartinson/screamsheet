"""Horoscope component for the Sky Tonight screamsheet."""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import HRFlowable, Paragraph, Spacer, Table, TableStyle

from ...config import PersonConfig, _parse_person
from ...llm.config import DEFAULT_LLM_CONFIG
from ...llm.summarizers import HoroscopeSummarizer
from ...providers.astro_provider import AstroDataProvider
from ...providers.sky_provider import SkyDataProvider
from ..base import ComponentLayoutSpec, ScreamsheetComponent
from ..registry import ComponentRegistry

# Keep logger name compatible with existing test_logging_quality.py assertions
logger = logging.getLogger("screamsheet.renderers.sky_horoscope")

_UNICODE_FONT = "Helvetica"
_UNICODE_FONT_BOLD = "Helvetica-Bold"

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
                registerFontFamily(
                    "_HoroUnicode",
                    normal="_HoroUnicode",
                    bold="_HoroUnicodeBold",
                    italic="_HoroUnicode",
                    boldItalic="_HoroUnicodeBold",
                )
            else:
                _UNICODE_FONT_BOLD = "_HoroUnicode"
                registerFontFamily(
                    "_HoroUnicode",
                    normal="_HoroUnicode",
                    bold="_HoroUnicode",
                    italic="_HoroUnicode",
                    boldItalic="_HoroUnicode",
                )
        except Exception:
            pass
        break

_ASTRO_GLYPHS = set("☉☽☿♀♂♃♄♅♆♇☌□△☍⚻♈♉♊♋♌♍♎♏♐♑♒♓∗✱*")


def _enlarge_astro_glyphs(text: str, size: int = 11) -> str:
    """Enlarge astrological symbols within text using ReportLab inline font tags."""
    normalized = text.replace("\u26b9", "\u2217")
    chars = []
    for ch in normalized:
        if ch in _ASTRO_GLYPHS:
            chars.append(f"<font size='{size}'>{ch}</font>")
        else:
            chars.append(ch)
    return "".join(chars)


@ComponentRegistry.register("sky_horoscope")
@ComponentRegistry.register("horoscope")
class SkyHoroscopeComponent(ScreamsheetComponent):
    """Renders horoscope reading(s) in a single-column slot or a 2-column table."""

    component_type = "sky_horoscope"
    layout_spec = ComponentLayoutSpec(
        weight=0.75,
        columns=1,
        full_page_only=False,
        component_family="sky_horoscope",
        max_on_front_page=2,
        max_per_page=2,
        renders_own_header=True,
    )

    def __init__(
        self,
        title: str = "Horoscopes",
        provider: Optional[Any] = None,
        date: Optional[datetime] = None,
        location_name: str = "Bryn Mawr, PA",
        people: Optional[List[PersonConfig]] = None,
        person: Optional[Any] = None,
        name: Optional[str] = None,
        birth_date: str = "",
        birth_time: str = "",
        birth_location: str = "",
        sun_sign: str = "",
        moon_sign: str = "",
        ascendant: str = "",
        extra_instructions: Any = None,
        astro_provider: Optional[AstroDataProvider] = None,
        horoscope_style: str = "kepler",
        lat: float = 40.02,
        lon: float = -75.34,
        _use_default_astro: bool = True,
        **kwargs: Any,
    ) -> None:
        self.lat = lat
        self.lon = lon
        self.location_name = location_name
        super().__init__(
            title=title,
            provider=provider,
            date=date if date is not None else datetime.now(),
            page_slot="back",
            location_name=location_name,
            people=people,
            horoscope_style=horoscope_style,
            **kwargs,
        )
        raw_people = list(people or [])
        if person is not None:
            raw_people.append(person)
        if name:
            raw_people.append(
                PersonConfig(
                    name=str(name),
                    birth_date=str(birth_date),
                    birth_time=str(birth_time),
                    birth_location=str(birth_location),
                    sun_sign=str(sun_sign),
                    moon_sign=str(moon_sign),
                    ascendant=str(ascendant),
                    horoscope_style=horoscope_style,
                    extra_instructions=extra_instructions,
                )
            )
        parsed_people: List[Any] = []
        for p in raw_people:
            if isinstance(p, dict):
                parsed_people.append(_parse_person(p))
            else:
                parsed_people.append(p)
        self.people: List[Any] = parsed_people
        self.astro_provider = (
            astro_provider
            if astro_provider is not None
            else (AstroDataProvider() if _use_default_astro else None)
        )
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

    def create_default_provider(self) -> Any:
        return SkyDataProvider(lat=self.lat, lon=self.lon, location_name=self.location_name)

    def has_content(self) -> bool:
        return len(self.people) > 0

    def expand_page_units(self) -> List[ScreamsheetComponent]:
        """Expand into one single-column horoscope unit per configured person."""
        if not self.has_content():
            return []
        if len(self.people) <= 1:
            return [self]
        units: List[ScreamsheetComponent] = []
        for p in self.people:
            unit = SkyHoroscopeComponent(
                title=self.title,
                provider=self.provider,
                date=self.date,
                location_name=self.location_name,
                people=[p],
                astro_provider=self.astro_provider,
                horoscope_style=self.horoscope_style,
                lat=self.lat,
                lon=self.lon,
                layout_spec=self.layout_spec,
                _use_default_astro=(self.astro_provider is not None),
            )
            units.append(unit)
        return units

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

    def _build_person_column_flowables(self, person: Any) -> List[Any]:
        """Build flowables for a single person's horoscope reading."""
        reading = self._get_horoscope(person)
        col: List[Any] = [
            Paragraph(person.name, self._name_style),
        ]
        paragraphs = [p.strip() for p in reading.split("\n") if p.strip()]
        for p_text in paragraphs:
            if p_text.startswith("•") or p_text.startswith("-"):
                p_clean = p_text.lstrip("•- ").strip()
                p_enlarged = _enlarge_astro_glyphs(p_clean, size=12)
                line_html = f"&bull; {p_enlarged}"

                col.append(Paragraph(line_html, self._aspect_style))
                col.append(Spacer(1, 2))
            else:
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
                elif lower_p.startswith("key influences & aspects:") or lower_p.startswith(
                    "key influences and aspects:"
                ):
                    p_html = f"<b>{p_text}</b>"
                else:
                    p_html = p_text

                col.append(Paragraph(p_html, self._body_style))
                col.append(Spacer(1, 4))
        return col

    def _build_legend_flowables(self) -> List[Any]:
        legend_text = (
            "<b>Aspects:</b> &nbsp; "
            "<font size='10'>&#x260C;</font> Conjunction (0&deg;) &nbsp;&bull;&nbsp; "
            "<font size='10'>&#x2217;</font> Sextile (60&deg;) &nbsp;&bull;&nbsp; "
            "<font size='10'>&#x25A1;</font> Square (90&deg;) &nbsp;&bull;&nbsp; "
            "<font size='10'>&#x25B3;</font> Trine (120&deg;) &nbsp;&bull;&nbsp; "
            "<font size='10'>&#x260D;</font> Opposition (180&deg;)"
        )
        return [
            HRFlowable(width="100%", thickness=0.4, color=HexColor("#DDDDDD"), spaceAfter=3),
            Paragraph(legend_text, self._legend_style),
        ]

    def render(
        self,
        styles: Optional[Any] = None,
        max_width: Optional[float] = None,
    ) -> List[Any]:
        if self.data is None:
            self.fetch_data()

        if max_width is not None and max_width <= 280 and self.layout_spec.columns == 1:
            if not self.people:
                return []
            elements: List[Any] = []
            if self.title:
                header_text = "Horoscope" if (self.title == "Horoscopes" and len(self.people) == 1) else self.title
                elements.append(Paragraph(header_text, self._heading_style))
                elements.append(Spacer(1, 4))
            elements.extend(self._build_person_column_flowables(self.people[0]))
            elements.append(Spacer(1, 4))
            elements.extend(self._build_legend_flowables())
            return elements

        elements = []
        elements.append(Paragraph(self.title, self._heading_style))
        elements.append(Spacer(1, 4))

        col_contents: List[List[Any]] = [
            self._build_person_column_flowables(person)
            for person in self.people[:2]
        ]

        while len(col_contents) < 2:
            col_contents.append([Paragraph("", self._body_style)])

        col_w = 265.0
        gutter = 10.0
        table = Table(
            [col_contents],
            colWidths=[col_w, col_w],
            spaceBefore=0,
            spaceAfter=0,
        )
        table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (0, -1), 0),
                    ("RIGHTPADDING", (0, 0), (0, -1), gutter),
                    ("LEFTPADDING", (1, 0), (1, -1), gutter),
                    ("RIGHTPADDING", (1, 0), (1, -1), 0),
                    ("LINEAFTER", (0, 0), (0, -1), 0.5, HexColor("#CCCCCC")),
                ]
            )
        )
        elements.append(table)
        elements.append(Spacer(1, 6))
        elements.extend(self._build_legend_flowables())
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

    def _get_horoscope(self, person: PersonConfig) -> str:
        """Return a ~200-word horoscope for *person*, or a fallback message."""
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
            # Support test patching on screamsheet.renderers.sky_horoscope.HoroscopeSummarizer
            renderer_mod = sys.modules.get("screamsheet.renderers.sky_horoscope")
            summarizer_cls = getattr(renderer_mod, "HoroscopeSummarizer", HoroscopeSummarizer)
            summarizer = summarizer_cls(
                gemini_api_key=gemini_key,
                grok_api_key=grok_key,
                config=DEFAULT_LLM_CONFIG,
                style=person_style,
            )

            transit_source: List[Dict[str, Any]] = astro["planets"] if astro else sky.get("planets", [])
            aspects_list: List[Dict[str, Any]] = astro["aspects"] if astro else []
            moon_phase: str = astro["moon_phase"] if astro else sky.get("moon_phase", "")
            ingresses: List[Dict[str, Any]] = astro.get("ingresses", []) if astro else []
            eclipses: List[Dict[str, Any]] = astro.get("eclipses", []) if astro else []

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

            house_map = AstroDataProvider.get_whole_sign_houses(ascendant) if ascendant else {}
            transit_enriched: List[Dict[str, Any]] = []
            for p in transit_source:
                house_num = AstroDataProvider._assign_house(p["zodiac"], ascendant) if ascendant else 0
                house_info = house_map.get(house_num, {})
                dignity = AstroDataProvider._get_planet_dignity(p["name"], p["zodiac"])
                transit_enriched.append(
                    {
                        **p,
                        "house_number": house_num,
                        "house_meaning": house_info.get("meaning", ""),
                        "dignity": dignity,
                    }
                )

            hits = AstroDataProvider._find_transit_hits(transit_source, natal_planets) if natal_planets else []

            natal_planet_str = ", ".join(f"{p['name']} in {p['zodiac']}" for p in natal_planets)
            natal_line = f"Natal planets: {natal_planet_str}\n" if natal_planet_str else ""
            subject_natal = f"Sun: {sun_sign} | Moon: {moon_sign} | Ascendant: {ascendant}\n{natal_line}".strip()

            planet_lines: List[str] = []
            for p in transit_enriched:
                motion_str = (
                    f" ({p['motion_status']})"
                    if p.get("motion_status") and p["motion_status"] != "Direct"
                    else ""
                )
                if p.get("house_number"):
                    planet_lines.append(
                        f"- {p['name']}{motion_str} in {p['zodiac']} "
                        f"(House {p['house_number']}: {p['house_meaning']}) [{p['dignity']}]"
                    )
                else:
                    planet_lines.append(f"- {p['name']}{motion_str} in {p['zodiac']} [{p['dignity']}]")

            aspects_str = (
                ", ".join(
                    a.get("formatted", f"{a['planet_a']} {a['aspect']} {a['planet_b']} (orb {a['orb']}°)")
                    for a in aspects_list
                )
                or "None"
            )

            hits_str = (
                "\n".join(
                    f"- Transit {h['transit_planet']} conjunct natal {h['natal_planet']} (orb: {h['orb']}°)"
                    for h in hits
                )
                or "None"
            )

            ingresses_str = "\n".join(f"- {i['formatted']}" for i in ingresses) if ingresses else "None"
            eclipses_str = "\n".join(f"- {e['formatted']}" for e in eclipses) if eclipses else "None"

            current_sky = (
                "Transit planets:\n"
                + "\n".join(planet_lines)
                + "\n\n"
                f"Key aspects: {aspects_str}\n\n"
                f"Sign ingresses today:\n{ingresses_str}\n\n"
                f"Astrological eclipses:\n{eclipses_str}\n\n"
                f"Hits (transit conjunct natal, orb ≤3°):\n{hits_str}\n\n"
                f"Moon phase: {moon_phase}"
            )

            data_payload = {
                "name": person.name,
                "birth_date": person.birth_date,
                "birth_time": person.birth_time,
                "birth_location": person.birth_location,
                "date": self.date.strftime("%B %d, %Y"),
                "location": self.location_name,
                "subject_natal": subject_natal,
                "current_sky": current_sky,
            }
            extra = getattr(person, "extra_instructions", None)
            if extra:
                data_payload["extra_instructions"] = extra

            llm_choice = "gemini" if gemini_key else "grok"
            result = summarizer.generate_summary(
                llm_choice=llm_choice,
                data=data_payload,
            )
            result_text = str(result).strip() if result else f"Horoscope unavailable for {person.name}."
            word_count = len(result_text.split())
            logger.info("Horoscope for %s complete: %d words", person.name, word_count)
            return result_text
        except Exception as exc:
            logger.warning("Horoscope generation failed for %s: %s", person.name, exc)
            return f"Horoscope unavailable for {person.name}."
