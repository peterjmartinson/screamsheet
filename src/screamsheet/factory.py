"""Factory for creating screamsheet instances."""
from typing import Optional, List, Tuple
from datetime import datetime

from .sports import MLBScreamsheet, NHLScreamsheet, NFLScreamsheet, NBAScreamsheet, FIFAWorldCupScreamsheet, HomeRunDerbyScreamsheet
from .news import MLBTradeRumorsScreamsheet, MLBNewsScreamsheet, NHLNewsScreamsheet, FrenchMLBNewsScreamsheet
from .political import PresidentialScreamsheet
from .sky.sky_tonight import SkyTonightScreamsheet


class ScreamsheetFactory:
    """
    Factory for creating screamsheet instances.
    
    Makes it easy to create screamsheets of different types without
    having to import and instantiate them directly.
    """
    

    @staticmethod
    def create_mlb_screamsheet(
        output_filename: str,
        team_id: Optional[int] = None,
        team_name: Optional[str] = None,
        date: Optional[datetime] = None,
        display_date: Optional[datetime] = None,
        favorite_teams: Optional[List[Tuple[int, str]]] = None,
    ) -> MLBScreamsheet:
        """
        Create an MLB screamsheet.
        
        Args:
            output_filename: Path to save the PDF
            team_id: MLB team ID (deprecated — use favorite_teams)
            team_name: Team name (deprecated — use favorite_teams)
            date: Target date for game data lookups (defaults to yesterday)
            display_date: Date shown in the subtitle header (defaults to date)
            favorite_teams: Priority-ordered list of (team_id, team_name) tuples.
            
        Returns:
            MLBScreamsheet instance
        """
        return MLBScreamsheet(
            output_filename=output_filename,
            team_id=team_id,
            team_name=team_name,
            date=date,
            display_date=display_date,
            favorite_teams=favorite_teams,
        )
    
    @staticmethod
    def create_nhl_screamsheet(
        output_filename: str,
        team_id: Optional[int] = None,
        team_name: Optional[str] = None,
        date: Optional[datetime] = None,
        display_date: Optional[datetime] = None,
        favorite_teams: Optional[List[Tuple[int, str]]] = None,
    ) -> NHLScreamsheet:
        """
        Create an NHL screamsheet.
        
        Args:
            output_filename: Path to save the PDF
            team_id: NHL team ID (deprecated — use favorite_teams)
            team_name: Team name (deprecated — use favorite_teams)
            date: Target date for game data lookups (defaults to yesterday)
            display_date: Date shown in the subtitle header (defaults to date)
            favorite_teams: Priority-ordered list of (team_id, team_name) tuples.
            
        Returns:
            NHLScreamsheet instance
        """
        return NHLScreamsheet(
            output_filename=output_filename,
            team_id=team_id,
            team_name=team_name,
            date=date,
            display_date=display_date,
            favorite_teams=favorite_teams,
        )
    
    @staticmethod
    def create_nfl_screamsheet(
        output_filename: str,
        team_id: Optional[int] = None,
        team_name: Optional[str] = None,
        date: Optional[datetime] = None,
        favorite_teams: Optional[List[Tuple[int, str]]] = None,
    ) -> NFLScreamsheet:
        """
        Create an NFL screamsheet.
        
        Args:
            output_filename: Path to save the PDF
            team_id: NFL team ID (deprecated — use favorite_teams)
            team_name: Team name (deprecated — use favorite_teams)
            date: Target date (defaults to yesterday)
            favorite_teams: Priority-ordered list of (team_id, team_name) tuples.
            
        Returns:
            NFLScreamsheet instance
        """
        return NFLScreamsheet(
            output_filename=output_filename,
            team_id=team_id,
            team_name=team_name,
            date=date,
            favorite_teams=favorite_teams,
        )
    
    @staticmethod
    def create_nba_screamsheet(
        output_filename: str,
        team_id: Optional[int] = None,
        team_name: Optional[str] = None,
        date: Optional[datetime] = None,
        display_date: Optional[datetime] = None,
        favorite_teams: Optional[List[Tuple[int, str]]] = None,
    ) -> NBAScreamsheet:
        """
        Create an NBA screamsheet.
        
        Args:
            output_filename: Path to save the PDF
            team_id: NBA team ID (deprecated — use favorite_teams)
            team_name: Team name (deprecated — use favorite_teams)
            date: Target date (defaults to yesterday)
            display_date: Date shown in the subtitle header (defaults to date)
            favorite_teams: Priority-ordered list of (team_id, team_name) tuples.
            
        Returns:
            NBAScreamsheet instance
        """
        return NBAScreamsheet(
            output_filename=output_filename,
            team_id=team_id,
            team_name=team_name,
            date=date,
            display_date=display_date,
            favorite_teams=favorite_teams,
        )
    
    @staticmethod
    def create_mlb_trade_rumors_screamsheet(
        output_filename: str,
        favorite_teams: Optional[list] = None,
        max_articles: int = 4,
        include_weather: bool = True,
        weather_lat: float = 40.02,
        weather_lon: float = -75.34,
        weather_location_name: str = "Bryn Mawr, PA",
        date: Optional[datetime] = None
    ) -> MLBTradeRumorsScreamsheet:
        """
        Create an MLB Trade Rumors news screamsheet.
        
        Args:
            output_filename: Path to save the PDF
            favorite_teams: List of favorite team names (optional)
            max_articles: Maximum number of articles (default: 4)
            include_weather: Include weather report (default: True)
            weather_lat: Latitude for weather location
            weather_lon: Longitude for weather location
            weather_location_name: Display name for weather location
            date: Target date (defaults to today)
            
        Returns:
            MLBTradeRumorsScreamsheet instance
        """
        return MLBTradeRumorsScreamsheet(
            output_filename=output_filename,
            favorite_teams=favorite_teams,
            max_articles=max_articles,
            include_weather=include_weather,
            weather_lat=weather_lat,
            weather_lon=weather_lon,
            weather_location_name=weather_location_name,
            date=date
        )
    
    @staticmethod
    def create_mlb_news_screamsheet(
        output_filename: str,
        favorite_teams: Optional[list] = None,
        include_weather: bool = True,
        weather_lat: float = 40.02,
        weather_lon: float = -75.34,
        weather_location_name: str = "Bryn Mawr, PA",
        date: Optional[datetime] = None,
    ) -> MLBNewsScreamsheet:
        """
        Create an MLB News screamsheet sourced from MLB.com team RSS feeds.

        Args:
            output_filename: Path to save the PDF.
            favorite_teams:  Teams to feature first (default: Phillies, Padres, Yankees).
            include_weather: Include weather report (default: True).
            weather_lat: Latitude for weather location.
            weather_lon: Longitude for weather location.
            weather_location_name: Display name for weather location.
            date:            Target date (defaults to today).

        Returns:
            MLBNewsScreamsheet instance
        """
        return MLBNewsScreamsheet(
            output_filename=output_filename,
            favorite_teams=favorite_teams,
            include_weather=include_weather,
            weather_lat=weather_lat,
            weather_lon=weather_lon,
            weather_location_name=weather_location_name,
            date=date,
        )

    @staticmethod
    def create_nhl_news_screamsheet(
        output_filename: str,
        favorite_teams: Optional[list] = None,
        include_weather: bool = True,
        weather_lat: float = 40.02,
        weather_lon: float = -75.34,
        weather_location_name: str = "Bryn Mawr, PA",
        date: Optional[datetime] = None,
    ) -> NHLNewsScreamsheet:
        """
        Create an NHL News screamsheet sourced from NHL.com team RSS feeds.

        Args:
            output_filename: Path to save the PDF.
            favorite_teams: Teams to feature first.
            include_weather: Include weather report (default: True).
            weather_lat: Latitude for weather location.
            weather_lon: Longitude for weather location.
            weather_location_name: Display name for weather location.
            date: Target date (defaults to today).

        Returns:
            NHLNewsScreamsheet instance
        """
        return NHLNewsScreamsheet(
            output_filename=output_filename,
            favorite_teams=favorite_teams,
            include_weather=include_weather,
            weather_lat=weather_lat,
            weather_lon=weather_lon,
            weather_location_name=weather_location_name,
            date=date,
        )

    @staticmethod
    def create_french_mlb_news_screamsheet(
        output_filename: str,
        favorite_teams: Optional[List[str]] = None,
        grok_api_key: Optional[str] = None,
        date: Optional[datetime] = None,
    ) -> FrenchMLBNewsScreamsheet:
        """
        Create a French MLB News screamsheet.

        Scrapes RDS.ca and TVA Sports for French-language MLB articles,
        rewrites them at CEFR A2 and B2/C1 via Grok, and compiles a
        back-page vocabulary lexicon.

        Args:
            output_filename: Path to save the PDF.
            favorite_teams:  Short team names used to prioritise articles
                             (e.g. ``["Blue Jays", "Phillies"]``).
            grok_api_key:    xAI API key (defaults to ``GROK_API_KEY`` env var).
            date:            Target date (defaults to today).

        Returns:
            FrenchMLBNewsScreamsheet instance.
        """
        return FrenchMLBNewsScreamsheet(
            output_filename=output_filename,
            favorite_teams=favorite_teams,
            grok_api_key=grok_api_key,
            date=date,
        )

    @staticmethod
    def create_presidential_screamsheet(
        output_filename: str,
        max_articles: int = 4,
        include_weather: bool = True,
        weather_lat: float = 38.8951,
        weather_lon: float = -77.0364,
        weather_location_name: str = "Washington, DC",
        date: Optional[datetime] = None,
    ) -> PresidentialScreamsheet:
        """
        Create a Presidential Screamsheet.

        Fetches political news from 7 RSS feeds and the White House,
        scores and deduplicates, and renders top stories to PDF.

        Args:
            output_filename: Path to save the PDF.
            max_articles:    Number of top stories to include (default: 4).
            include_weather: Include weather report at top (default: True).
            weather_lat:     Latitude for weather location.
            weather_lon:     Longitude for weather location.
            weather_location_name: Display name for weather location.
            date:            Target date (defaults to today).

        Returns:
            PresidentialScreamsheet instance
        """
        return PresidentialScreamsheet(
            output_filename=output_filename,
            max_articles=max_articles,
            include_weather=include_weather,
            weather_lat=weather_lat,
            weather_lon=weather_lon,
            weather_location_name=weather_location_name,
            date=date,
        )

    @staticmethod
    def create_worldcup_screamsheet(
        output_filename: str,
        date: Optional[datetime] = None,
    ) -> FIFAWorldCupScreamsheet:
        """
        Create a FIFA World Cup 2026 screamsheet.

        Fetches data from worldcup26.ir (no API key required).

        Args:
            output_filename: Path to save the PDF.
            date:            Target date — fixtures from this day are shown (defaults to yesterday).

        Returns:
            FIFAWorldCupScreamsheet instance
        """
        return FIFAWorldCupScreamsheet(
            output_filename=output_filename,
            date=date,
        )

    @staticmethod
    def create_sky_tonight_screamsheet(
        output_filename: str,
        lat: float = 40.0,
        lon: float = -75.0,
        location_name: str = "My Location",
        date: Optional[datetime] = None,
        people: Optional[list] = None,
    ) -> SkyTonightScreamsheet:
        """
        Create a Sky Tonight screamsheet.

        Generates a one-page PDF summarising the naked-eye night sky for
        the configured location: a zodiac wheel showing planet positions
        and a bulleted highlights section with an optional LLM remark.

        Args:
            output_filename: Path to save the PDF.
            lat:             Observer latitude (decimal degrees).
            lon:             Observer longitude (decimal degrees).
            location_name:   Display name for the observer location.
            date:            Target date (defaults to today).
            people:          Up to 2 PersonConfig entries for horoscope readings.

        Returns:
            SkyTonightScreamsheet instance
        """
        return SkyTonightScreamsheet(
            output_filename=output_filename,
            lat=lat,
            lon=lon,
            location_name=location_name,
            date=date,
            people=people or [],
        )

    @staticmethod
    def create_home_run_derby_screamsheet(
        output_filename: str,
        date: Optional[datetime] = None,
        display_date: Optional[datetime] = None,
        game_pk: Optional[int] = None,
    ) -> HomeRunDerbyScreamsheet:
        """
        Create an MLB Home Run Derby PDF screamsheet.
        
        Args:
            output_filename: Path to save the generated PDF
            date: Target date of the event
            display_date: Date shown in the header
            game_pk: Optional explicit MLB API event ID
            
        Returns:
            HomeRunDerbyScreamsheet instance
        """
        return HomeRunDerbyScreamsheet(
            output_filename=output_filename,
            date=date,
            display_date=display_date,
            game_pk=game_pk,
        )

