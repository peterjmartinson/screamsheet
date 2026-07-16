"""MLB All-Star Game screamsheet implementation."""
from typing import List, Optional, Tuple
from datetime import datetime

from .base_sports import SportsScreamsheet
from ..providers.mlb_provider import MLBDataProvider
from ..renderers.allstar_renderers import (
    AllStarGameScoresSection,
    AllStarGameSummarySection,
    AllStarSideBySideBoxScoreSection,
)


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
        # 1. Game score (AL vs NL) on front page
        sections.append(
            AllStarGameScoresSection(
                title="All-Star Game Score",
                provider=self.provider,
                date=self.date,
            )
        )
        # 2. Expanded ~500-word game summary on front page (no standings)
        sections.append(
            AllStarGameSummarySection(
                title="All-Star Game Summary",
                provider=self.provider,
                date=self.date,
            )
        )
        # 3. Side-by-side box scores on back page (AL left, NL right)
        sections.append(
            AllStarSideBySideBoxScoreSection(
                title="All-Star Game Box Scores",
                provider=self.provider,
                date=self.date,
            )
        )
        return sections
