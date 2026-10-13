"""College Football Screamsheet implementation."""
import logging
from datetime import datetime
from typing import List, Optional, Tuple

from ..base import Section
from ..providers.cfb_provider import CFBDataProvider
from ..renderers import (
    BoxScoreSection,
    GameScoresSection,
    StandingsSection,
)
from .base_sports import SportsScreamsheet

logger = logging.getLogger(__name__)


class CFBScreamsheet(SportsScreamsheet):
    """College Football screamsheet.

    Front page (Page 1):
      - College Football Game Scores (Top 25 rankings, major games, favorite teams)
      - AP Top 25 Rankings (in a 2-column spread: 1-13 and 14-25)

    Back page (Page 2):
      - Featured Game Box Score (Linescore, team stats, top performers)
      - Narrative Game Recap and 3 Key Takeaways
    """

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
        super().__init__(
            sport_name="College Football",
            output_filename=output_filename,
            team_id=team_id,
            team_name=team_name,
            date=date,
            display_date=display_date,
            favorite_teams=favorite_teams,
            mad_fan=mad_fan,
        )

    def create_provider(self) -> CFBDataProvider:
        """Create College Football data provider."""
        return CFBDataProvider()

    def get_title(self) -> str:
        """Return the main header title."""
        return "COLLEGE FOOTBALL"

    def get_subtitle(self) -> Optional[str]:
        """Return optional subtitle."""
        return "Saturday Gameday Recap"

    def get_date_string(self) -> str:
        """Return formatted date string for header."""
        return (self.display_date or self.date).strftime("%A, %B %d, %Y")

    def build_sections(self) -> List[Section]:
        """Build front and back page sections for College Football."""
        sections: List[Section] = []

        # 1. Front page top: Game Scores
        scores_section = GameScoresSection(
            title="College Football Game Scores",
            provider=self.provider,
            date=self.date,
        )
        scores_section.page_slot = "front"
        sections.append(scores_section)

        # 2. Front page bottom: AP Top 25 Rankings
        standings_section = StandingsSection(
            title="AP Top 25 Rankings",
            provider=self.provider,
            date=self.date,
        )
        standings_section.page_slot = "front"
        sections.append(standings_section)

        # 3. Back page: Box Score & Narrative Summary
        featured = self._resolve_featured_team()
        if featured and featured[0]:
            featured_id, featured_name = featured
            is_primary = bool(self.favorite_teams) and featured == self.favorite_teams[0]
            box_section = BoxScoreSection(
                title=f"{featured_name} Box Score",
                provider=self.provider,
                team_id=featured_id,
                date=self.date,
                is_primary_favorite=is_primary,
                mad_fan=self.mad_fan,
            )
            box_section.page_slot = "back"
            sections.append(box_section)

        return sections
