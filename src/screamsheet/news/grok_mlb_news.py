"""Grok MLB News screamsheet implementation.

Four articles, each sourced and written by Grok searching live MLB news
from the past 24 hours.  Layout is identical to the MLB Trade Rumors
screamsheet.
"""
from typing import Optional, List
from datetime import datetime

from .base_news import NewsScreamsheet
from ..base import Section
from ..renderers import WeatherSection
from ..renderers.grok_articles import GrokGeneratedArticlesSection
from ..providers.grok_mlb_news_provider import GrokMLBNewsProvider


class GrokMLBNewsScreamsheet(NewsScreamsheet):
    """Screamsheet powered by Grok live MLB news search."""

    def __init__(
        self,
        output_filename: str,
        favorite_teams: Optional[List[str]] = None,
        max_articles: int = 4,
        include_weather: bool = True,
        date: Optional[datetime] = None,
    ):
        super().__init__(
            news_source='MLB News from X',
            output_filename=output_filename,
            include_weather=include_weather,
            date=date,
        )
        self.favorite_teams = favorite_teams or ['Phillies', 'Padres', 'Yankees']
        self.max_articles = max_articles
        # Provider is instantiated once; both renderers share it so articles
        # are fetched in a single pass and cached on self.provider._articles.
        self.provider = GrokMLBNewsProvider(
            favorite_teams=self.favorite_teams,
            max_articles=self.max_articles,
        )

    def build_sections(self) -> List[Section]:
        sections = []

        if self.include_weather:
            sections.append(WeatherSection(title='Weather Report', date=self.date))

        sections.append(GrokGeneratedArticlesSection(
            title='MLB News',
            provider=self.provider,
            max_articles=2,
            start_index=0,
        ))

        sections.append(GrokGeneratedArticlesSection(
            title='More MLB News',
            provider=self.provider,
            max_articles=2,
            start_index=2,
        ))

        return sections
