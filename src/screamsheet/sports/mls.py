"""MLS screamsheet implementation."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional, Tuple

from .base_sports import SportsScreamsheet
from ..components.box_score import MLSBoxScoreComponent
from ..components.game_scores import MLSGameScoresComponent
from ..components.standings import MLSStandingsComponent
from ..providers.mls_provider import MLSDataProvider

logger = logging.getLogger(__name__)


class MLSScreamsheet(SportsScreamsheet):
    """Major League Soccer screamsheet."""

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
        Initialize MLS screamsheet.

        Args:
            output_filename: Path to save the PDF
            team_id: MLS team ID (deprecated — use favorite_teams)
            team_name: Team name (deprecated — use favorite_teams)
            date: Target date (defaults to yesterday)
            display_date: Date shown in the subtitle header (defaults to date)
            favorite_teams: Priority-ordered list of (team_id, team_name) tuples.
            mad_fan: If True, generate an enraged hometown-fan recap when primary favorite loses.
        """
        super().__init__(
            sport_name="MLS",
            output_filename=output_filename,
            team_id=team_id,
            team_name=team_name,
            date=date,
            display_date=display_date,
            favorite_teams=favorite_teams,
            mad_fan=mad_fan,
        )

    def create_provider(self) -> MLSDataProvider:
        """Create MLS data provider."""
        return MLSDataProvider()

    def create_game_scores_component(self) -> MLSGameScoresComponent:
        """Create MLS game scores component."""
        return MLSGameScoresComponent(
            title="MLS Game Scores",
            provider=self.provider,
            date=self.date,
        )

    def create_standings_component(self) -> MLSStandingsComponent:
        """Create MLS standings component."""
        return MLSStandingsComponent(
            title="MLS Standings",
            provider=self.provider,
            date=self.date,
        )

    def create_box_score_component(
        self,
        team_id: int,
        team_name: str,
        is_primary_favorite: bool = False,
    ) -> MLSBoxScoreComponent:
        """Create MLS box score component."""
        return MLSBoxScoreComponent(
            title=f"{team_name} Box Score",
            provider=self.provider,
            team_id=team_id,
            date=self.date,
            is_primary_favorite=is_primary_favorite,
            mad_fan=self.mad_fan,
            favorite_teams=self.favorite_teams,
            team_name=team_name,
        )

    def _pick_random_team(self) -> Optional[Tuple[int, str]]:
        """Select Match of the Day as fallback when no favorite team played."""
        motd = self.provider.get_match_of_the_day(self.date)
        if motd and motd.get("home_id") and motd.get("home_team"):
            logger.info(
                "No favorite team played on %s — featuring Match of the Day: %s vs %s",
                self.date.strftime("%Y-%m-%d"),
                motd.get("home_team"),
                motd.get("away_team"),
            )
            return (int(motd["home_id"]), str(motd["home_team"]))
        return super()._pick_random_team()
