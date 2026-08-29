"""Morning Briefing screamsheet implementation."""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..base import BaseScreamsheet, Section
from ..providers.agenda_provider import AgendaProvider
from ..renderers.agenda import TwoColumnAgendaSection
from ..renderers.weather import WeatherSection
from .constants import DEFAULT_AGENDA_ENDPOINT

logger = logging.getLogger(__name__)


class MorningBriefingScreamsheet(BaseScreamsheet):
    """
    Morning Briefing screamsheet displaying:
    - Title: "Screamsheet"
    - Subtitle: "<Subscriber>'s Morning Briefing" or "Morning Briefing"
    - Top: 5-Day Weather Forecast
    - Body (2 columns): Left Column (Today's Agenda & Tasks) | Right Column (Next 5 Days)
    """

    def __init__(
        self,
        output_filename: str,
        subscriber_name: str = "",
        payload: Optional[Dict[str, Any]] = None,
        api_url: str = DEFAULT_AGENDA_ENDPOINT,
        include_weather: bool = True,
        weather_lat: float = 40.02,
        weather_lon: float = -75.34,
        weather_location_name: str = "Bryn Mawr, PA",
        date: Optional[datetime] = None,
    ):
        target_date = date if date is not None else datetime.now()
        super().__init__(output_filename, date=target_date, display_date=target_date)

        self.subscriber_name = subscriber_name
        self.payload = payload or {}
        self.api_url = api_url
        self.include_weather = include_weather
        self.weather_lat = weather_lat
        self.weather_lon = weather_lon
        self.weather_location_name = weather_location_name
        self.provider = AgendaProvider(payload=self.payload, api_url=self.api_url)

    def get_title(self) -> str:
        return "Screamsheet"

    def get_subtitle(self) -> Optional[str]:
        if self.subscriber_name:
            return f"{self.subscriber_name}'s Morning Briefing"
        return "Morning Briefing"

    def build_sections(self) -> List[Section]:
        sections: List[Section] = []

        # 1. Weather at the top
        if self.include_weather:
            sections.append(
                WeatherSection(
                    title="Weather Forecast",
                    date=self.date,
                    lat=self.weather_lat,
                    lon=self.weather_lon,
                    location_name=self.weather_location_name,
                )
            )

        # 2. Two-column Agenda (Today on Left, Next 5 Days on Right)
        agenda_sec = TwoColumnAgendaSection(
            date=self.date,
            provider=self.provider,
            title="Agenda",
        )
        sections.append(agenda_sec)

        return sections
