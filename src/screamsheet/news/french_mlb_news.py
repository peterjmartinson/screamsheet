"""French MLB News screamsheet — levelled French articles with back-page lexicon."""
import os
from datetime import datetime
from typing import List, Optional

from .base_news import NewsScreamsheet
from ..base import Section
from ..providers.french_mlb_content_provider import FrenchMLBContentProvider
from ..providers.french_mlb_scraper_provider import FrenchMLBScraperProvider
from ..renderers.french_articles import FrenchArticlesSection
from ..renderers.french_lexicon import FrenchLexiconSection


class FrenchMLBNewsScreamsheet(NewsScreamsheet):
    """
    Two-page screamsheet for French-language MLB news.

    **Front page**: a two-column layout showing the same story rewritten
    at CEFR A2 (left) and CEFR B2/C1 (right), powered by Grok.

    **Back page**: "Le Lexique Essentiel" vocabulary table and
    "Les Tournures de Phrase" idioms block.

    Articles are scraped from RDS.ca and TVA Sports and filtered by
    ``favorite_teams`` in priority order, falling back to random picks
    when no team match is found.
    """

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

        front = FrenchArticlesSection(title="MLB en Fran\u00e7ais", content=content)
        back = FrenchLexiconSection(title="Le Lexique", content=content)

        return [front, back]
