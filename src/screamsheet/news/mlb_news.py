"""MLB News screamsheet — four articles from MLB.com team RSS feeds."""
from typing import Optional, List
from datetime import datetime

from .base_news import NewsScreamsheet
from ..base import Section
from ..renderers import WeatherSection, NewsArticlesSection
from ..providers.mlb_news_rss_provider import MLBNewsRssProvider


class MLBNewsScreamsheet(NewsScreamsheet):
    """Screamsheet for MLB.com news via team-specific RSS feeds.

    Fetches four articles, prioritising favourite teams in order before
    falling back to the general MLB news feed.  Team priority is
    configurable via ``favorite_teams`` at construction time.
    """

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
    ) -> None:
        super().__init__(
            news_source="MLB News",
            output_filename=output_filename,
            include_weather=include_weather,
            date=date,
        )
        self.favorite_teams: List[str] = favorite_teams or ["Phillies", "Padres", "Yankees"]
        self.max_articles: int = max_articles
        self.weather_lat = weather_lat
        self.weather_lon = weather_lon
        self.weather_location_name = weather_location_name
        self.provider: MLBNewsRssProvider = MLBNewsRssProvider(
            favorite_teams=self.favorite_teams,
            max_articles=self.max_articles,
        )

    def get_title(self) -> str:
        return "MLB News"

    def build_sections(self) -> List[Section]:
        """Build all sections for the MLB News screamsheet."""
        sections: List[Section] = []

        if self.include_weather:
            sections.append(WeatherSection(
                title="Weather Report",
                date=self.date,
                lat=self.weather_lat,
                lon=self.weather_lon,
                location_name=self.weather_location_name,
            ))

        sections.append(
            NewsArticlesSection(
                title="Latest News",
                provider=self.provider,
                max_articles=2,
                start_index=0,
            )
        )

        sections.append(
            NewsArticlesSection(
                title="More News",
                provider=self.provider,
                max_articles=2,
                start_index=2,
            )
        )

        return sections
