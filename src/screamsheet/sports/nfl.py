"""NFL screamsheet implementation."""
from typing import Optional
from datetime import datetime

from .base_sports import SportsScreamsheet
from ..providers.nfl_provider import NFLDataProvider


class NFLScreamsheet(SportsScreamsheet):
    """NFL-specific screamsheet."""
    
    def __init__(
        self,
        output_filename: str,
        team_id: Optional[int] = None,
        team_name: Optional[str] = None,
        date: Optional[datetime] = None
    ):
        """
        Initialize NFL screamsheet.
        
        Args:
            output_filename: Path to save the PDF
            team_id: NFL team ID
            team_name: Team name
            date: Target date (defaults to yesterday)
        """
        super().__init__(
            sport_name="NFL",
            output_filename=output_filename,
            team_id=team_id,
            team_name=team_name,
            date=date
        )
    
    def create_provider(self) -> NFLDataProvider:
        """Create NFL data provider."""
        return NFLDataProvider()
