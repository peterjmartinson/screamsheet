"""Sky Tonight screamsheet — one-page summary of the naked-eye night sky."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional

from reportlab.platypus import Paragraph, Spacer

from ..base import BaseScreamsheet, Section
from ..config import PersonConfig
from ..providers.astro_provider import AstroDataProvider
from ..providers.sky_provider import SkyDataProvider
from ..renderers.zodiac_wheel import ZodiacWheelSection
from ..renderers.sky_highlights import SkyHighlightsSection
from ..renderers.sky_horoscope import SkyHoroscopeSection

logger = logging.getLogger(__name__)


class SkyTonightScreamsheet(BaseScreamsheet):
    """Generates a two-page PDF summarising tonight's naked-eye sky.

    Front page: zodiac wheel.
    Back page:  sky highlights + personalized horoscope readings (if people are configured).

    Sections:
        1. ZodiacWheelSection  — circular zodiac wheel with planet markers
        2. SkyHighlightsSection — bulleted highlights + LLM-generated remark
        3. SkyHoroscopeSection — two-column horoscope readings (back page)

    Args:
        output_filename: Path for the generated PDF.
        lat:             Observer latitude (decimal degrees).
        lon:             Observer longitude (decimal degrees).
        location_name:   Display name for the observer location.
        date:            Target date; defaults to *today* (not yesterday).
        people:          Up to 2 PersonConfig entries for horoscope readings.
    """

    def __init__(
        self,
        output_filename: str,
        lat: float,
        lon: float,
        location_name: str,
        date: Optional[datetime] = None,
        people: Optional[List[PersonConfig]] = None,
    ) -> None:
        # Default to *today* — we're describing tonight's sky, not last night's.
        super().__init__(output_filename, date=date if date is not None else datetime.now())
        self.lat = lat
        self.lon = lon
        self.location_name = location_name
        self.people: List[PersonConfig] = people if people is not None else []
        self.provider = SkyDataProvider(lat=lat, lon=lon, location_name=location_name)
        self.astro_provider = AstroDataProvider()

    # ------------------------------------------------------------------
    # BaseScreamsheet interface
    # ------------------------------------------------------------------

    def get_title(self) -> str:
        return "Sky Tonight Screamsheet"

    def get_subtitle(self) -> Optional[str]:
        return self.location_name

    def build_sections(self) -> List[Section]:
        horoscope_section = SkyHoroscopeSection(
            title="Horoscopes",
            provider=self.provider,
            date=self.date,
            location_name=self.location_name,
            people=self.people,
            astro_provider=self.astro_provider,
        )
        horoscope_section.page_slot = "back"

        highlights_section = SkyHighlightsSection(
            title="Sky Highlights",
            provider=self.provider,
            date=self.date,
            location_name=self.location_name,
        )

        return [
            ZodiacWheelSection(
                title="Tonight's Zodiac Wheel",
                provider=self.provider,
                date=self.date,
            ),
            highlights_section,
            horoscope_section,
        ]

    def generate(self) -> str:
        """Generate a two-page PDF: zodiac wheel + highlights on front, horoscopes on back."""
        logger.info("Building sections for %s", self.get_title())
        self.sections = self.build_sections()
        logger.info("Sections built: %d total", len(self.sections))

        front_content: List = []
        back_content: List = []

        # Header
        front_content.append(Paragraph(self.get_title(), self.title_style))
        subtitle = self.get_subtitle()
        if subtitle:
            front_content.append(Paragraph(f"<i>{subtitle}</i>", self.subtitle_style))
        front_content.append(Paragraph(self.get_date_string(), self.subtitle_style))
        front_content.append(Spacer(1, 12))

        for section in self.sections:
            if section.has_content():
                elements = section.render()
                if getattr(section, "page_slot", "front") == "back":
                    back_content.extend(elements)
                    back_content.append(Spacer(1, 20))
                    logger.info("Section '%s' → back page (%d flowables)", section.title, len(elements))
                else:
                    front_content.extend(elements)
                    front_content.append(Spacer(1, 20))
                    logger.info("Section '%s' → front page (%d flowables)", section.title, len(elements))

        return self._build_two_page_pdf(front_content, back_content)
