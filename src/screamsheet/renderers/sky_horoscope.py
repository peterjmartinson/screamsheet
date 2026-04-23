"""Horoscope section renderer for the Sky Tonight screamsheet.

Renders two personalized horoscope readings side-by-side in a 2-column layout,
one per configured person.  Section is silently skipped when no people are
configured.
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from ..base import Section
from ..config import PersonConfig
from ..llm.config import DEFAULT_LLM_CONFIG
from ..llm.summarizers import HoroscopeSummarizer
from ..providers.astro_provider import AstroDataProvider


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
    """

    def __init__(
        self,
        title: str,
        provider: Any,
        date: datetime,
        location_name: str,
        people: List[PersonConfig],
        astro_provider: Optional[AstroDataProvider] = None,
    ) -> None:
        super().__init__(title)
        self.provider = provider
        self.date = date
        self.location_name = location_name
        self.people = people
        self.astro_provider = astro_provider
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
            fontSize=11,
            leading=15,
            alignment=TA_LEFT,
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
                Paragraph(reading, self._body_style),
            ]
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
        return elements

    # ------------------------------------------------------------------
    # LLM integration
    # ------------------------------------------------------------------

    def _get_horoscope(self, person: PersonConfig) -> str:
        """Return a ~200-word horoscope for *person*, or a fallback message.

        When ``astro_provider`` is set, planet positions and aspects are sourced
        from Swiss Ephemeris (tropical zodiac, vernal-equinox anchored).  When
        not set, falls back to Skyfield positions from the sky data dict.
        """
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
            summarizer = HoroscopeSummarizer(
                gemini_api_key=gemini_key,
                grok_api_key=grok_key,
                config=DEFAULT_LLM_CONFIG,
            )

            # Transit planets: Swiss Ephemeris when available, else Skyfield fallback.
            transit_source: List[Dict[str, Any]] = astro["planets"] if astro else sky.get("planets", [])
            aspects_list: List[Dict[str, Any]] = astro["aspects"] if astro else []
            moon_phase: str = astro["moon_phase"] if astro else sky.get("moon_phase", "")

            # Enrich each transit planet with whole-sign house + dignity.
            house_map = AstroDataProvider.get_whole_sign_houses(person.ascendant) if person.ascendant else {}
            transit_enriched: List[Dict[str, Any]] = []
            for p in transit_source:
                house_num = AstroDataProvider._assign_house(p["zodiac"], person.ascendant) if person.ascendant else 0
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
                f"Sun: {person.sun_sign} | Moon: {person.moon_sign} | Ascendant: {person.ascendant}\n"
                f"{natal_line}"
            ).strip()

            # Build current_sky block.
            planet_lines: List[str] = []
            for p in transit_enriched:
                if p.get("house_number"):
                    planet_lines.append(
                        f"- {p['name']} in {p['zodiac']} "
                        f"(House {p['house_number']}: {p['house_meaning']}) [{p['dignity']}]"
                    )
                else:
                    planet_lines.append(f"- {p['name']} in {p['zodiac']} [{p['dignity']}]")

            aspects_str = ", ".join(
                f"{a['planet_a']} {a['aspect']} {a['planet_b']}" for a in aspects_list
            ) or "None"

            hits_str = "\n".join(
                f"- Transit {h['transit_planet']} conjunct natal {h['natal_planet']} (orb: {h['orb']}°)"
                for h in hits
            ) or "None"

            current_sky = (
                "Transit planets:\n" + "\n".join(planet_lines) + "\n\n"
                f"Key aspects: {aspects_str}\n\n"
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
            return str(result).strip() if result else f"Horoscope unavailable for {person.name}."
        except Exception:  # noqa: BLE001
            return f"Horoscope unavailable for {person.name}."

