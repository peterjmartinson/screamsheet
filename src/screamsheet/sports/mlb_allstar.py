"""MLB All-Star Game screamsheet implementation."""
from typing import List, Optional, Tuple
from datetime import datetime

from .base_sports import SportsScreamsheet
from ..components.box_score import MLBAllStarBoxScoreComponent, MLBAllStarGameSummaryComponent
from ..components.game_scores import MLBAllStarGameScoresComponent
from ..providers.mlb_provider import MLBDataProvider


class MLBAllStarScreamsheet(SportsScreamsheet):
    """MLB All-Star Game special issue screamsheet."""

    def __init__(
        self,
        output_filename: str,
        date: Optional[datetime] = None,
        display_date: Optional[datetime] = None,
        favorite_teams: Optional[List[Tuple[int, str]]] = None,
    ):
        """Initialize MLB All-Star screamsheet."""
        super().__init__(
            sport_name="MLB All-Star",
            output_filename=output_filename,
            date=date,
            display_date=display_date,
            favorite_teams=favorite_teams,
        )

    def create_provider(self) -> MLBDataProvider:
        """Create MLB data provider."""
        return MLBDataProvider()

    def get_title(self) -> str:
        """Get the main title for this screamsheet."""
        return "MLB All-Star Game"

    def get_subtitle(self) -> Optional[str]:
        """Get the subtitle for this screamsheet."""
        return "Screamsheet Special Edition"

    def build_sections(self) -> list:
        """Build sections for the All-Star screamsheet."""
        sections = []
        sections.append(
            MLBAllStarGameScoresComponent(
                title="All-Star Game Score",
                provider=self.provider,
                date=self.date,
            )
        )
        sections.append(
            MLBAllStarGameSummaryComponent(
                title="All-Star Game Summary",
                provider=self.provider,
                date=self.date,
            )
        )
        sections.append(
            MLBAllStarBoxScoreComponent(
                title="All-Star Game Box Scores",
                provider=self.provider,
                date=self.date,
            )
        )
        return sections
