"""NBA screamsheet implementation."""
from typing import Optional
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
        date: Optional[datetime] = None
    ):
        """
        Initialize NBA screamsheet.
        
        Args:
            output_filename: Path to save the PDF
            team_id: NBA team ID
            team_name: Team name
            date: Target date (defaults to yesterday)
        """
        super().__init__(
            sport_name="NBA",
            output_filename=output_filename,
            team_id=team_id,
            team_name=team_name,
            date=date
        )
    
    def create_provider(self) -> NBADataProvider:
        """Create NBA data provider."""
        return NBADataProvider()
