"""Data provider interface for fetching data from various sources."""
from abc import ABC, abstractmethod
from typing import Any, Optional
from datetime import datetime


class DataProvider(ABC):
    """
    Base class for data providers.
    
    Data providers are responsible for fetching data from various sources:
    - APIs (REST, GraphQL, etc.)
    - Python packages (nba_api, etc.)
    - Web scraping
    - Local files
    - Databases
    
    Each sport/news source implements its own provider.
    """
    
    def __init__(self, **config):
        """
        Initialize the data provider.
        
        Args:
            **config: Configuration parameters for the provider
        """
        self.config = config
    
    @abstractmethod
    def get_game_scores(self, date: datetime) -> list:
        """
        Get game scores for a specific date.
        
        Args:
            date: The date to fetch scores for
            
        Returns:
            List of game score dictionaries
        """
        pass
    
    @abstractmethod
    def get_standings(self) -> Any:
        """
        Get current league standings.
        
        Returns:
            Standings data (format varies by provider)
        """
        pass
    
    def get_box_score(self, team_id: int, date: datetime) -> Optional[Any]:
        """
        Get box score for a specific team and date.
        
        Args:
            team_id: The team ID
            date: The date to fetch box score for
            
        Returns:
            Box score data or None if not available
        """
        return None
    
    def get_game_summary(self, team_id: int, date: datetime) -> Optional[str]:
        """
        Get game summary for a specific team and date.
        
        Args:
            team_id: The team ID
            date: The date to fetch summary for
            
        Returns:
            Game summary text or None if not available
        """
        return None
