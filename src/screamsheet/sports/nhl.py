"""NHL screamsheet implementation."""
from typing import List, Optional, Tuple
from datetime import datetime

from .base_sports import SportsScreamsheet
from ..providers.nhl_provider import NHLDataProvider


class NHLScreamsheet(SportsScreamsheet):
    """NHL-specific screamsheet."""
    
    def __init__(
        self,
        output_filename: str,
        team_id: Optional[int] = None,
        team_name: Optional[str] = None,
        date: Optional[datetime] = None,
        display_date: Optional[datetime] = None,
        favorite_teams: Optional[List[Tuple[int, str]]] = None,
        mad_fan: bool = False,
    ):
        """
        Initialize NHL screamsheet.
        
        Args:
            output_filename: Path to save the PDF
            team_id: NHL team ID (deprecated — use favorite_teams)
            team_name: Team name (deprecated — use favorite_teams)
            date: Target date for game data lookups (defaults to yesterday)
            display_date: Date shown in the subtitle header (defaults to date)
            favorite_teams: Priority-ordered list of (team_id, team_name) tuples.
            mad_fan: If True, generate an enraged hometown-fan recap when the primary
                favorite team loses. Defaults to False.
        """
        super().__init__(
            sport_name="NHL",
            output_filename=output_filename,
            team_id=team_id,
            team_name=team_name,
            date=date,
            display_date=display_date,
            favorite_teams=favorite_teams,
            mad_fan=mad_fan,
        )
    
    def create_provider(self) -> NHLDataProvider:
        """Create NHL data provider."""
        return NHLDataProvider()
