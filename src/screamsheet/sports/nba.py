"""NBA screamsheet implementation."""
from typing import List, Optional, Tuple
from datetime import datetime

from .base_sports import SportsScreamsheet
from ..providers.nba_provider import NBADataProvider


class NBAScreamsheet(SportsScreamsheet):
    """NBA-specific screamsheet."""
    
    def __init__(
        self,
        output_filename: str,
        team_id: Optional[int] = None,
        team_name: Optional[str] = None,
        date: Optional[datetime] = None,
        favorite_teams: Optional[List[Tuple[int, str]]] = None,
    ):
        """
        Initialize NBA screamsheet.
        
        Args:
            output_filename: Path to save the PDF
            team_id: NBA team ID (deprecated — use favorite_teams)
            team_name: Team name (deprecated — use favorite_teams)
            date: Target date (defaults to yesterday)
            favorite_teams: Priority-ordered list of (team_id, team_name) tuples.
        """
        super().__init__(
            sport_name="NBA",
            output_filename=output_filename,
            team_id=team_id,
            team_name=team_name,
            date=date,
            favorite_teams=favorite_teams,
        )
    
    def create_provider(self) -> NBADataProvider:
        """Create NBA data provider."""
        return NBADataProvider()
