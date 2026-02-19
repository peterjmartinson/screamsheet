"""The Players' Tribune screamsheet implementation."""
from typing import Optional, List
from datetime import datetime

from .base_news import NewsScreamsheet
from ..base import Section
from ..renderers import WeatherSection, NewsArticlesSection
from ..providers.players_tribune_provider import PlayersTribuneProvider


class PlayersTribuneScreamsheet(NewsScreamsheet):
    """Screamsheet for The Players' Tribune news."""
    
    def __init__(
        self,
        output_filename: str,
        max_articles: int = 4,
        include_weather: bool = True,
        date: Optional[datetime] = None
    ):
        """
        Initialize The Players' Tribune screamsheet.
        
        Args:
            output_filename: Path to save the PDF
            max_articles: Maximum number of articles to include
            include_weather: Whether to include weather report
            date: Target date (defaults to today)
        """
        super().__init__(
            news_source="The Players' Tribune",
            output_filename=output_filename,
            include_weather=include_weather,
            date=date
        )
        self.max_articles = max_articles
        self.provider = PlayersTribuneProvider(max_articles=self.max_articles)
    
    def build_sections(self) -> List[Section]:
        """Build all sections for The Players' Tribune screamsheet."""
        sections = []
        
        # 1. Weather Section (if enabled)
        if self.include_weather:
            sections.append(
                WeatherSection(
                    title="Weather Report",
                    date=self.date
                )
            )
        
        # 2. Front Page News Articles (first 2 articles)
        sections.append(
            NewsArticlesSection(
                title="The Players' Tribune",
                provider=self.provider,
                max_articles=2,
                start_index=0
            )
        )
        
        # 3. Back Page News Articles (next 2 articles)
        sections.append(
            NewsArticlesSection(
                title="More Stories",
                provider=self.provider,
                max_articles=2,
                start_index=2
            )
        )
        
        return sections
