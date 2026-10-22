"""NBA screamsheet implementation."""
from typing import List, Optional, Tuple
from datetime import datetime

from .base_sports import SportsScreamsheet
from ..components.box_score import NBABoxScoreComponent
from ..components.game_scores import NBAGameScoresComponent
from ..components.standings import NBAStandingsComponent
from ..providers.nba_provider import NBADataProvider


class NBAScreamsheet(SportsScreamsheet):
    """NBA-specific screamsheet."""
    
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
        Initialize NBA screamsheet.
        
        Args:
            output_filename: Path to save the PDF
            team_id: NBA team ID (deprecated — use favorite_teams)
            team_name: Team name (deprecated — use favorite_teams)
            date: Target date (defaults to yesterday)
            display_date: Date shown in the subtitle header (defaults to date)
            favorite_teams: Priority-ordered list of (team_id, team_name) tuples.
            mad_fan: If True, generate an enraged hometown-fan recap when the primary
                favorite team loses. Defaults to False.
        """
        super().__init__(
            sport_name="NBA",
            output_filename=output_filename,
            team_id=team_id,
            team_name=team_name,
            date=date,
            display_date=display_date,
            favorite_teams=favorite_teams,
            mad_fan=mad_fan,
        )
    
    def create_provider(self) -> NBADataProvider:
        """Create NBA data provider."""
        return NBADataProvider()

    def create_game_scores_component(self) -> NBAGameScoresComponent:
        """Create NBA game scores component."""
        return NBAGameScoresComponent(
            title="NBA Game Scores",
            provider=self.provider,
            date=self.date,
        )

    def create_standings_component(self) -> NBAStandingsComponent:
        """Create NBA standings component."""
        return NBAStandingsComponent(
            title="NBA Standings",
            provider=self.provider,
            date=self.date,
        )

    def create_box_score_component(
        self,
        team_id: int,
        team_name: str,
        is_primary_favorite: bool = False,
    ) -> NBABoxScoreComponent:
        """Create NBA box score component."""
        return NBABoxScoreComponent(
            title=f"{team_name} Box Score",
            provider=self.provider,
            team_id=team_id,
            date=self.date,
            is_primary_favorite=is_primary_favorite,
            mad_fan=self.mad_fan,
        )
