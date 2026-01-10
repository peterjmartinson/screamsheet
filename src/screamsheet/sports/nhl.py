"""NHL screamsheet implementation."""
from typing import Optional
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
        date: Optional[datetime] = None
    ):
        """
        Initialize NHL screamsheet.
        
        Args:
            output_filename: Path to save the PDF
            team_id: NHL team ID (e.g., 4 for Flyers)
            team_name: Team name (e.g., "Philadelphia Flyers")
            date: Target date (defaults to yesterday)
        """
        super().__init__(
            sport_name="NHL",
            output_filename=output_filename,
            team_id=team_id,
            team_name=team_name,
            date=date
        )
    
    def create_provider(self) -> NHLDataProvider:
        """Create NHL data provider."""
        return NHLDataProvider()
