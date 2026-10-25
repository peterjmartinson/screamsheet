"""French MLB News screamsheet — levelled French articles with back-page lexicon."""
import os
from datetime import datetime
from typing import List, Optional

from .base_news import NewsScreamsheet
from ..base import Section
from ..components.news import FrenchMLBArticlesComponent, FrenchMLBLexiconComponent
from ..providers.french_mlb_content_provider import FrenchMLBContentProvider
from ..providers.french_mlb_scraper_provider import FrenchMLBScraperProvider


class FrenchMLBNewsScreamsheet(NewsScreamsheet):
    """Two-page screamsheet for French-language MLB news."""

    def __init__(
        self,
        output_filename: str,
        favorite_teams: Optional[List[str]] = None,
        grok_api_key: Optional[str] = None,
        date: Optional[datetime] = None,
    ) -> None:
        super().__init__(
            news_source="RDS \u00b7 TVA Sports",
            output_filename=output_filename,
            include_weather=False,
            date=date,
        )
        self.favorite_teams: List[str] = favorite_teams or []
        self._grok_api_key = grok_api_key or os.getenv("GROK_API_KEY")

    def get_title(self) -> str:
        return "MLB en Fran\u00e7ais"

    def build_sections(self) -> List[Section]:
        """Scrape articles, generate LLM content, build front + back sections."""
        scraper = FrenchMLBScraperProvider(favorite_teams=self.favorite_teams)
        articles = scraper.get_articles()

        content_provider = FrenchMLBContentProvider(grok_api_key=self._grok_api_key)
        content = content_provider.generate(articles)

        front = FrenchMLBArticlesComponent(title="MLB en Fran\u00e7ais", content=content)
        back = FrenchMLBLexiconComponent(title="Le Lexique", content=content)

        return [front, back]
