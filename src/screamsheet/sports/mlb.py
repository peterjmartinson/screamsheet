"""MLB screamsheet implementation."""
from typing import Optional
from datetime import datetime

from .base_sports import SportsScreamsheet
from ..providers.mlb_provider import MLBDataProvider


class MLBScreamsheet(SportsScreamsheet):
    """MLB-specific screamsheet."""
    
    def __init__(
        self,
        output_filename: str,
        team_id: Optional[int] = None,
        team_name: Optional[str] = None,
        date: Optional[datetime] = None,
        display_date: Optional[datetime] = None
    ):
        """
        Initialize MLB screamsheet.
        
        Args:
            output_filename: Path to save the PDF
            team_id: MLB team ID (e.g., 143 for Phillies)
            team_name: Team name (e.g., "Philadelphia Phillies")
            date: Target date for game data lookups (defaults to yesterday)
            display_date: Date shown in the subtitle header (defaults to date)
        """
        super().__init__(
            sport_name="MLB",
            output_filename=output_filename,
            team_id=team_id,
            team_name=team_name,
            date=date,
            display_date=display_date
        )
    
    def create_provider(self) -> MLBDataProvider:
        """Create MLB data provider."""
        return MLBDataProvider()
