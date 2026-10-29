"""Presidential Screamsheet: assembles the full political news PDF."""
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..base import Section
from ..components.news import PresidentialNewsComponent
from ..components.weather import WeatherComponent
from ..news.base_news import NewsScreamsheet
from ..providers.political_news_provider import PoliticalNewsProvider
from ..llm.summarizers import PoliticalNewsSummarizer


class PresidentialScreamsheet(NewsScreamsheet):
    """Assembles a 'Presidential Screamsheet' PDF."""

    def __init__(
        self,
        output_filename: str,
        max_articles: int = 4,
        include_weather: bool = True,
        weather_lat: float = 38.8951,
        weather_lon: float = -77.0364,
        weather_location_name: str = "Washington, DC",
        date: Optional[datetime] = None,
        mode: str = "multi",
        primary_source: str = PoliticalNewsProvider.PRIMARY_SOURCE,
        primary_source_bonus: int = PoliticalNewsProvider.PRIMARY_SOURCE_BONUS,
        extra_feeds: Optional[Dict[str, str]] = None,
        sources: Optional[List[Any]] = None,
    ):
        super().__init__(
            news_source="Presidential Screamsheet",
            output_filename=output_filename,
            include_weather=include_weather,
            date=date,
        )
        self.max_articles = max_articles
        self.weather_lat = weather_lat
        self.weather_lon = weather_lon
        self.weather_location_name = weather_location_name
        self.mode = mode
        self.primary_source = primary_source
        self.primary_source_bonus = primary_source_bonus
        self.extra_feeds = extra_feeds
        self.sources = list(sources) if sources else None
        self.provider = PoliticalNewsProvider(
            max_articles=self.max_articles,
            mode=self.mode,
            primary_source=self.primary_source,
            primary_source_bonus=self.primary_source_bonus,
            extra_feeds=self.extra_feeds,
            sources=self.sources,
        )

    def get_title(self) -> str:
        return "Presidential Screamsheet"

    def get_subtitle(self) -> Optional[str]:
        return None

    def build_sections(self) -> List[Section]:
        sections: List[Section] = []

        if self.include_weather:
            sections.append(
                WeatherComponent(
                    title="Weather Report",
                    date=self.date,
                    lat=self.weather_lat,
                    lon=self.weather_lon,
                    location_name=self.weather_location_name,
                )
            )

        sections.append(
            PresidentialNewsComponent(
                title="Top Stories",
                provider=self.provider,
                max_articles=2,
                start_index=0,
                summarizer_class=PoliticalNewsSummarizer,
            )
        )
        back_section = PresidentialNewsComponent(
            title="More Stories",
            provider=self.provider,
            max_articles=2,
            start_index=2,
            summarizer_class=PoliticalNewsSummarizer,
        )
        back_section.page_slot = "back"
        sections.append(back_section)
        return sections
