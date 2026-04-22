"""Horoscope section renderer for the Sky Tonight screamsheet.

Renders two personalized horoscope readings side-by-side in a 2-column layout,
one per configured person.  Section is silently skipped when no people are
configured.
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Any, List

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from ..base import Section
from ..config import PersonConfig
from ..llm.config import DEFAULT_LLM_CONFIG
from ..llm.summarizers import HoroscopeSummarizer


class SkyHoroscopeSection(Section):
    """Renders two horoscope readings side-by-side for configured people.

    Args:
        title:         Section heading.
        provider:      SkyDataProvider instance.
        date:          Target date (tonight).
        location_name: Observer location (passed to the LLM prompt).
        people:        List of up to 2 PersonConfig entries.  If empty,
                       ``has_content()`` returns False and the section is
                       omitted from the PDF.
    """

    def __init__(
        self,
        title: str,
        provider: Any,
        date: datetime,
        location_name: str,
        people: List[PersonConfig],
    ) -> None:
        super().__init__(title)
        self.provider = provider
        self.date = date
        self.location_name = location_name
        self.people = people

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
        sky = self.provider.get_sky_data(self.date)
        self.data = sky

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
        """Return a ~200-word horoscope for *person*, or a fallback message."""
        sky = self.data or {}

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
            planets_str = ", ".join(
                f"{p['name']} in {p['zodiac']}"
                for p in sky.get("planets", [])
                if p.get("name") not in {"Uranus", "Neptune"}
            )
            llm_choice = "gemini" if gemini_key else "grok"
            result = summarizer.generate_summary(
                llm_choice=llm_choice,
                data={
                    "name": person.name,
                    "birth_date": person.birth_date,
                    "birth_time": person.birth_time,
                    "birth_location": person.birth_location,
                    "sun_sign": person.sun_sign,
                    "moon_sign": person.moon_sign,
                    "ascendant": person.ascendant,
                    "planets": planets_str,
                    "moon_phase": sky.get("moon_phase", ""),
                    "date": self.date.strftime("%B %d, %Y"),
                    "location": self.location_name,
                },
            )
            return str(result).strip() if result else f"Horoscope unavailable for {person.name}."
        except Exception:  # noqa: BLE001
            return f"Horoscope unavailable for {person.name}."
