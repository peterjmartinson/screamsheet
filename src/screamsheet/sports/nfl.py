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
    
    def get_date_string(self) -> str:
        """Return the formatted date string with NFL week info."""
        date_str = self.date.strftime("%B %d, %Y")
        
        # Add week information if available from provider
        if hasattr(self.provider, 'current_week') and self.provider.current_week:
            week_info = self.provider.current_week
            season_name = week_info.get('SeasonName', '')
            week_detail = week_info.get('WeekDetail', '')
            
            # Format: "Postseason, Wild Card (Jan 7-13)"
            if season_name and week_detail:
                return f"{date_str}\n{season_name}, {week_detail}"
            elif season_name:
                return f"{date_str}\n{season_name}"
        
        return date_str
