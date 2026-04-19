"""Sky Tonight screamsheet — one-page summary of the naked-eye night sky."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from ..base import BaseScreamsheet, Section
from ..providers.sky_provider import SkyDataProvider
from ..renderers.zodiac_wheel import ZodiacWheelSection
from ..renderers.sky_highlights import SkyHighlightsSection


class SkyTonightScreamsheet(BaseScreamsheet):
    """Generates a one-page PDF summarising tonight's naked-eye sky.

    Sections:
        1. ZodiacWheelSection  — circular zodiac wheel with planet markers
        2. SkyHighlightsSection — bulleted highlights + LLM-generated remark

    Args:
        output_filename: Path for the generated PDF.
        lat:             Observer latitude (decimal degrees).
        lon:             Observer longitude (decimal degrees).
        location_name:   Display name for the observer location.
        date:            Target date; defaults to *today* (not yesterday).
    """

    def __init__(
        self,
        output_filename: str,
        lat: float,
        lon: float,
        location_name: str,
        date: Optional[datetime] = None,
    ) -> None:
        # Default to *today* — we're describing tonight's sky, not last night's.
        super().__init__(output_filename, date=date if date is not None else datetime.now())
        self.lat = lat
        self.lon = lon
        self.location_name = location_name
        self.provider = SkyDataProvider(lat=lat, lon=lon, location_name=location_name)

    # ------------------------------------------------------------------
    # BaseScreamsheet interface
    # ------------------------------------------------------------------

    def get_title(self) -> str:
        return "Sky Tonight Screamsheet"

    def get_subtitle(self) -> Optional[str]:
        return self.location_name

    def build_sections(self) -> List[Section]:
        return [
            ZodiacWheelSection(
                title="Tonight's Zodiac Wheel",
                provider=self.provider,
                date=self.date,
            ),
            SkyHighlightsSection(
                title="Sky Highlights",
                provider=self.provider,
                date=self.date,
                location_name=self.location_name,
            ),
        ]
