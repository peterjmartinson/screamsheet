"""Morning Briefing screamsheet implementation."""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..base import BaseScreamsheet, Section
from ..providers.agenda_provider import AgendaProvider
from ..providers.gmail_provider import GmailNewsProvider
from ..providers.xkcd_provider import XKCDProvider
from ..renderers.agenda import TwoColumnAgendaSection
from ..renderers.email_news import EmailNewsSection
from ..renderers.weather import WeatherSection
from ..renderers.xkcd import XKCDSection
from .constants import DEFAULT_AGENDA_ENDPOINT

logger = logging.getLogger(__name__)


class MorningBriefingScreamsheet(BaseScreamsheet):
    """
    Morning Briefing screamsheet displaying:
    - Title: "Screamsheet"
    - Subtitle: "<Subscriber>'s Morning Briefing" or "Morning Briefing"
    - Top: 5-Day Weather Forecast
    - Body (2 columns): Left Column (Today's Agenda & Tasks) | Right Column (Next 5 Days)
    - Bottom: Daily XKCD Comic Strip
    - Back page (Page 2): Summarized Email News Briefing
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
        upcoming_days: int = 1,
        include_xkcd: bool = True,
        date: Optional[datetime] = None,
        include_email_news: bool = True,
        gmail_label: str = "Morning Briefing",
        gmail_username: Optional[str] = None,
        gmail_app_password: Optional[str] = None,
        email_provider: Optional[GmailNewsProvider] = None,
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
        self.upcoming_days = upcoming_days
        self.include_xkcd = include_xkcd
        self.include_email_news = include_email_news
        self.gmail_label = gmail_label
        self.gmail_username = gmail_username
        self.gmail_app_password = gmail_app_password
        self.email_provider = email_provider
        self.provider = AgendaProvider(payload=self.payload, api_url=self.api_url)
        self.xkcd_provider = XKCDProvider() if self.include_xkcd else None

    def get_title(self) -> str:
        if self.subscriber_name:
            return f"{self.subscriber_name}'s Screamsheet"
        return "Screamsheet"

    def get_subtitle(self) -> Optional[str]:
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
                    show_description=False,
                )
            )

        # 2. Two-column Agenda
        agenda_sec = TwoColumnAgendaSection(
            date=self.date,
            provider=self.provider,
            title="Agenda",
            upcoming_days=self.upcoming_days,
        )
        sections.append(agenda_sec)

        # 3. XKCD Comic below the agenda
        if self.include_xkcd and self.xkcd_provider:
            sections.append(
                XKCDSection(
                    provider=self.xkcd_provider,
                    title="XKCD",
                )
            )

        # 4. Email News Digest on the back page
        if self.include_email_news:
            ep = self.email_provider or GmailNewsProvider(
                username=self.gmail_username,
                app_password=self.gmail_app_password,
                label=self.gmail_label,
            )
            sections.append(
                EmailNewsSection(
                    provider=ep,
                    date=self.date,
                    title="Morning News Briefing",
                )
            )

        return sections
