"""MLB News screamsheet — four articles from MLB.com and secondary RSS feeds."""
from typing import Any, Dict, Optional, List
from datetime import datetime

from .base_news import NewsScreamsheet
from ..base import Section
from ..components.news import MLBNewsComponent
from ..components.weather import WeatherComponent
from ..providers.mlb_news_rss_provider import MLBNewsRssProvider


class MLBNewsScreamsheet(NewsScreamsheet):
    """Screamsheet for MLB news via MLB.com and secondary RSS feeds."""

    def __init__(
        self,
        output_filename: str,
        favorite_teams: Optional[List[str]] = None,
        max_articles: int = 4,
        include_weather: bool = True,
        weather_lat: float = 40.02,
        weather_lon: float = -75.34,
        weather_location_name: str = "Bryn Mawr, PA",
        date: Optional[datetime] = None,
        mode: str = "multi",
        primary_source: str = MLBNewsRssProvider.PRIMARY_SOURCE,
        primary_source_bonus: int = MLBNewsRssProvider.PRIMARY_SOURCE_BONUS,
        extra_feeds: Optional[Dict[str, str]] = None,
        sources: Optional[List[Any]] = None,
    ) -> None:
        super().__init__(
            news_source="MLB News",
            output_filename=output_filename,
            include_weather=include_weather,
            date=date,
        )
        self.favorite_teams: List[str] = favorite_teams or []
        self.max_articles: int = max_articles
        self.weather_lat = weather_lat
        self.weather_lon = weather_lon
        self.weather_location_name = weather_location_name
        self.mode = mode
        self.primary_source = primary_source
        self.primary_source_bonus = primary_source_bonus
        self.extra_feeds = extra_feeds
        self.sources = list(sources) if sources else None
        self.provider: MLBNewsRssProvider = MLBNewsRssProvider(
            favorite_teams=self.favorite_teams,
            max_articles=self.max_articles,
            mode=self.mode,
            primary_source=self.primary_source,
            primary_source_bonus=self.primary_source_bonus,
            extra_feeds=self.extra_feeds,
            sources=self.sources,
        )

    def get_title(self) -> str:
        return "MLB News"

    def build_sections(self) -> List[Section]:
        """Build all sections for the MLB News screamsheet."""
        sections: List[Section] = []

        if self.include_weather:
            sections.append(WeatherComponent(
                title="Weather Report",
                date=self.date,
                lat=self.weather_lat,
                lon=self.weather_lon,
                location_name=self.weather_location_name,
            ))

        sections.append(
            MLBNewsComponent(
                title="Latest News",
                provider=self.provider,
                max_articles=2,
                start_index=0,
            )
        )

        back_section = MLBNewsComponent(
            title="More News",
            provider=self.provider,
            max_articles=2,
            start_index=2,
        )
        back_section.page_slot = "back"
        sections.append(back_section)

        return sections
