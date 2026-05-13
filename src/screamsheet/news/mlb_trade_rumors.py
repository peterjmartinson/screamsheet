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
        weather_lat: float = 40.02,
        weather_lon: float = -75.34,
        weather_location_name: str = "Bryn Mawr, PA",
        date: Optional[datetime] = None,
        masthead: str = "",
    ):
        """
        Initialize MLB Trade Rumors screamsheet.
        
        Args:
            output_filename: Path to save the PDF
            favorite_teams: List of favorite team names for prioritization
            max_articles: Maximum number of articles to include
            include_weather: Whether to include weather report
            weather_lat: Latitude for weather location
            weather_lon: Longitude for weather location
            weather_location_name: Display name for weather location
            date: Target date (defaults to today)
            masthead: Branding text for the top-right header ear box.
        """
        super().__init__(
            news_source="MLB Trade Rumors",
            output_filename=output_filename,
            include_weather=include_weather,
            date=date,
            masthead=masthead,
        )
        self.favorite_teams = favorite_teams or ['Phillies', 'Padres', 'Yankees']
        self.max_articles = max_articles
        self.weather_lat = weather_lat
        self.weather_lon = weather_lon
        self.weather_location_name = weather_location_name
        self.provider = MLBTradeRumorsProvider(
            favorite_teams=self.favorite_teams,
            max_articles=self.max_articles
        )
    
    def build_sections(self) -> List[Section]:
        """Build all sections for the MLB Trade Rumors screamsheet."""
        sections: List[Section] = []
        
        # 1. Weather Section (if enabled)
        if self.include_weather:
            sections.append(
                WeatherSection(
                    title="Weather Report",
                    date=self.date,
                    lat=self.weather_lat,
                    lon=self.weather_lon,
                    location_name=self.weather_location_name,
                )
            )
        
        # News Articles (all 4 articles)
        sections.append(
            NewsArticlesSection(
                title="Latest News",
                provider=self.provider,
                max_articles=4,
                start_index=0
            )
        )
        
        return sections
