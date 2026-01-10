"""MLB Trade Rumors screamsheet implementation."""
from typing import Optional, List
from datetime import datetime

from .base_news import NewsScreamsheet
from ..base import Section
from ..renderers import WeatherSection, NewsArticlesSection
from ..providers.mlb_trade_rumors_provider import MLBTradeRumorsProvider


class MLBTradeRumorsScreamsheet(NewsScreamsheet):
    """Screamsheet for MLB Trade Rumors news."""
    
    def __init__(
        self,
        output_filename: str,
        favorite_teams: Optional[List[str]] = None,
        max_articles: int = 4,
        include_weather: bool = True,
        date: Optional[datetime] = None
    ):
        """
        Initialize MLB Trade Rumors screamsheet.
        
        Args:
            output_filename: Path to save the PDF
            favorite_teams: List of favorite team names for prioritization
            max_articles: Maximum number of articles to include
            include_weather: Whether to include weather report
            date: Target date (defaults to today)
        """
        super().__init__(
            news_source="MLB Trade Rumors",
            output_filename=output_filename,
            include_weather=include_weather,
            date=date
        )
        self.favorite_teams = favorite_teams or ['Phillies', 'Padres', 'Yankees']
        self.max_articles = max_articles
        self.provider = MLBTradeRumorsProvider(
            favorite_teams=self.favorite_teams,
            max_articles=self.max_articles
        )
    
    def build_sections(self) -> List[Section]:
        """Build all sections for the MLB Trade Rumors screamsheet."""
        sections = []
        
        # 1. Weather Section (if enabled)
        if self.include_weather:
            sections.append(
                WeatherSection(
                    title="Weather Report",
                    date=self.date
                )
            )
        
        # 2. News Articles Section
        sections.append(
            NewsArticlesSection(
                title="Latest News",
                provider=self.provider,
                max_articles=self.max_articles
            )
        )
        
        return sections
