"""FanGraphs Blogs screamsheet implementation."""
from typing import Optional, List
from datetime import datetime

from .base_news import NewsScreamsheet
from ..base import Section
from ..renderers import WeatherSection, NewsArticlesSection
from ..providers.fangraphs_provider import FanGraphsProvider


class FanGraphsScreamsheet(NewsScreamsheet):
    """Screamsheet for FanGraphs blogs."""

    def __init__(
        self,
        output_filename: str,
        max_articles: int = 4,
        include_weather: bool = True,
        date: Optional[datetime] = None,
    ):
        super().__init__(
            news_source="FanGraphs Blogs",
            output_filename=output_filename,
            include_weather=include_weather,
            date=date,
        )
        self.max_articles = max_articles
        self.provider = FanGraphsProvider(max_articles=self.max_articles)

    def build_sections(self) -> List[Section]:
        sections = []

        if self.include_weather:
            sections.append(
                WeatherSection(
                    title="Weather Report",
                    date=self.date,
                )
            )

        sections.append(
            NewsArticlesSection(
                title="FanGraphs Blogs",
                provider=self.provider,
                max_articles=2,
                start_index=0,
            )
        )

        sections.append(
            NewsArticlesSection(
                title="More from FanGraphs",
                provider=self.provider,
                max_articles=2,
                start_index=2,
            )
        )

        return sections
