"""Factory for creating screamsheet instances."""
from typing import Optional
from datetime import datetime

from .sports import MLBScreamsheet, NHLScreamsheet, NFLScreamsheet, NBAScreamsheet
from .news import MLBTradeRumorsScreamsheet, MLBNewsScreamsheet, PlayersTribuneScreamsheet, FanGraphsScreamsheet, GrokMLBNewsScreamsheet
from .political import PresidentialScreamsheet


class ScreamsheetFactory:
    """
    Factory for creating screamsheet instances.
    
    Makes it easy to create screamsheets of different types without
    having to import and instantiate them directly.
    """
    
    # Team ID constants for convenience
    # MLB Teams
    MLB_ANGELS = 108
    MLB_ASTROS = 117
    MLB_ATHLETICS = 133
    MLB_BLUEJAYS = 141
    MLB_BRAVES = 144
    MLB_BREWERS = 158
    MLB_CARDINALS = 138
    MLB_CUBS = 112
    MLB_DIAMONDBACKS = 109
    MLB_DODGERS = 119
    MLB_GIANTS = 137
    MLB_GUARDIANS = 114
    MLB_MARINERS = 136
    MLB_MARLINS = 146
    MLB_METS = 121
    MLB_NATIONALS = 120
    MLB_ORIOLES = 110
    MLB_PADRES = 135
    MLB_PHILLIES = 143
    MLB_PIRATES = 134
    MLB_RANGERS = 140
    MLB_RAYS = 139
    MLB_REDSOX = 111
    MLB_REDS = 113
    MLB_ROCKIES = 115
    MLB_ROYALS = 118
    MLB_TIGERS = 116
    MLB_TWINS = 142
    MLB_WHITESOX = 145
    MLB_YANKEES = 147
    
    # NHL Teams (add more as needed)
    NHL_FLYERS = 4
    
    @staticmethod
    def create_mlb_screamsheet(
        output_filename: str,
        team_id: Optional[int] = None,
        team_name: Optional[str] = None,
        date: Optional[datetime] = None,
        display_date: Optional[datetime] = None
    ) -> MLBScreamsheet:
        """
        Create an MLB screamsheet.
        
        Args:
            output_filename: Path to save the PDF
            team_id: MLB team ID (optional, e.g., 143 for Phillies)
            team_name: Team name (optional, e.g., "Philadelphia Phillies")
            date: Target date for game data lookups (defaults to yesterday)
            display_date: Date shown in the subtitle header (defaults to date)
            
        Returns:
            MLBScreamsheet instance
        """
        return MLBScreamsheet(
            output_filename=output_filename,
            team_id=team_id,
            team_name=team_name,
            date=date,
            display_date=display_date
        )
    
    @staticmethod
    def create_nhl_screamsheet(
        output_filename: str,
        team_id: Optional[int] = None,
        team_name: Optional[str] = None,
        date: Optional[datetime] = None,
        display_date: Optional[datetime] = None
    ) -> NHLScreamsheet:
        """
        Create an NHL screamsheet.
        
        Args:
            output_filename: Path to save the PDF
            team_id: NHL team ID (optional, e.g., 4 for Flyers)
            team_name: Team name (optional, e.g., "Philadelphia Flyers")
            date: Target date for game data lookups (defaults to yesterday)
            display_date: Date shown in the subtitle header (defaults to date)
            
        Returns:
            NHLScreamsheet instance
        """
        return NHLScreamsheet(
            output_filename=output_filename,
            team_id=team_id,
            team_name=team_name,
            date=date,
            display_date=display_date
        )
    
    @staticmethod
    def create_nfl_screamsheet(
        output_filename: str,
        team_id: Optional[int] = None,
        team_name: Optional[str] = None,
        date: Optional[datetime] = None
    ) -> NFLScreamsheet:
        """
        Create an NFL screamsheet.
        
        Args:
            output_filename: Path to save the PDF
            team_id: NFL team ID (optional)
            team_name: Team name (optional)
            date: Target date (defaults to yesterday)
            
        Returns:
            NFLScreamsheet instance
        """
        return NFLScreamsheet(
            output_filename=output_filename,
            team_id=team_id,
            team_name=team_name,
            date=date
        )
    
    @staticmethod
    def create_nba_screamsheet(
        output_filename: str,
        team_id: Optional[int] = None,
        team_name: Optional[str] = None,
        date: Optional[datetime] = None
    ) -> NBAScreamsheet:
        """
        Create an NBA screamsheet.
        
        Args:
            output_filename: Path to save the PDF
            team_id: NBA team ID (optional)
            team_name: Team name (optional)
            date: Target date (defaults to yesterday)
            
        Returns:
            NBAScreamsheet instance
        """
        return NBAScreamsheet(
            output_filename=output_filename,
            team_id=team_id,
            team_name=team_name,
            date=date
        )
    
    @staticmethod
    def create_mlb_trade_rumors_screamsheet(
        output_filename: str,
        favorite_teams: Optional[list] = None,
        max_articles: int = 4,
        include_weather: bool = True,
        date: Optional[datetime] = None
    ) -> MLBTradeRumorsScreamsheet:
        """
        Create an MLB Trade Rumors news screamsheet.
        
        Args:
            output_filename: Path to save the PDF
            favorite_teams: List of favorite team names (optional)
            max_articles: Maximum number of articles (default: 4)
            include_weather: Include weather report (default: True)
            date: Target date (defaults to today)
            
        Returns:
            MLBTradeRumorsScreamsheet instance
        """
        return MLBTradeRumorsScreamsheet(
            output_filename=output_filename,
            favorite_teams=favorite_teams,
            max_articles=max_articles,
            include_weather=include_weather,
            date=date
        )
    
    @staticmethod
    def create_mlb_news_screamsheet(
        output_filename: str,
        favorite_teams: Optional[list] = None,
        include_weather: bool = True,
        date: Optional[datetime] = None,
    ) -> MLBNewsScreamsheet:
        """
        Create an MLB News screamsheet sourced from MLB.com team RSS feeds.

        Args:
            output_filename: Path to save the PDF.
            favorite_teams:  Teams to feature first (default: Phillies, Padres, Yankees).
            include_weather: Include weather report (default: True).
            date:            Target date (defaults to today).

        Returns:
            MLBNewsScreamsheet instance
        """
        return MLBNewsScreamsheet(
            output_filename=output_filename,
            favorite_teams=favorite_teams,
            include_weather=include_weather,
            date=date,
        )

    @staticmethod
    def create_players_tribune_screamsheet(
        output_filename: str,
        max_articles: int = 4,
        include_weather: bool = True,
        date: Optional[datetime] = None
    ) -> PlayersTribuneScreamsheet:
        """
        Create a Players' Tribune news screamsheet.
        
        Args:
            output_filename: Path to save the PDF
            max_articles: Maximum number of articles (default: 4)
            include_weather: Include weather report (default: True)
            date: Target date (defaults to today)
            
        Returns:
            PlayersTribuneScreamsheet instance
        """
        return PlayersTribuneScreamsheet(
            output_filename=output_filename,
            max_articles=max_articles,
            include_weather=include_weather,
            date=date
        )

    @staticmethod
    def create_fangraphs_screamsheet(
        output_filename: str,
        max_articles: int = 4,
        include_weather: bool = True,
        date: Optional[datetime] = None,
    ) -> FanGraphsScreamsheet:
        """
        Create a FanGraphs Blogs news screamsheet.
        """
        return FanGraphsScreamsheet(
            output_filename=output_filename,
            max_articles=max_articles,
            include_weather=include_weather,
            date=date,
        )

    @staticmethod
    def create_grok_mlb_news_screamsheet(
        output_filename: str,
        favorite_teams: Optional[list] = None,
        max_articles: int = 4,
        include_weather: bool = True,
        date: Optional[datetime] = None,
    ) -> GrokMLBNewsScreamsheet:
        """
        Create a Grok MLB News screamsheet.

        Grok searches live MLB news from the past 24 hours and writes
        each article from scratch.  No RSS feed required.

        Args:
            output_filename: Path to save the PDF.
            favorite_teams:  Teams to feature first (default: Phillies, Padres, Yankees).
            max_articles:    Number of articles to generate (default: 4).
            include_weather: Include weather report (default: True).
            date:            Target date (defaults to today).

        Returns:
            GrokMLBNewsScreamsheet instance
        """
        return GrokMLBNewsScreamsheet(
            output_filename=output_filename,
            favorite_teams=favorite_teams,
            max_articles=max_articles,
            include_weather=include_weather,
            date=date,
        )

    @staticmethod
    def create_presidential_screamsheet(
        output_filename: str,
        max_articles: int = 4,
        date: Optional[datetime] = None,
    ) -> PresidentialScreamsheet:
        """
        Create a Presidential Screamsheet.

        Fetches political news from 7 RSS feeds and the White House,
        scores and deduplicates, and renders top stories to PDF.

        Args:
            output_filename: Path to save the PDF.
            max_articles:    Number of top stories to include (default: 4).
            date:            Target date (defaults to today).

        Returns:
            PresidentialScreamsheet instance
        """
        return PresidentialScreamsheet(
            output_filename=output_filename,
            max_articles=max_articles,
            date=date,
        )
