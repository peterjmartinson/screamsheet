"""International Soccer screamsheet implementation."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ..base import BaseScreamsheet, Section
from ..components.box_score import SoccerBoxScoreComponent
from ..components.game_scores import SoccerGameScoresComponent
from ..components.standings import SoccerStandingsComponent
from ..providers.soccer_provider import (
    AL_NASSR_TEAM_ID,
    PORTUGAL_TEAM_ID,
    SoccerDataProvider,
)

logger = logging.getLogger(__name__)


class SoccerScreamsheet(BaseScreamsheet):
    """
    Two-page International Football/Soccer Screamsheet.
    Tailored for Cristiano Ronaldo, Al-Nassr, and marquee European football fans.

    Page 1: Multi-league game scores and dual mini-standings.
    Page 2: Match of the Day deep dive (lineups, ratings, metrics, timeline, narrative)
            or off-day special fallback (CR7 road to 1,000 goals + upcoming fixtures).
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
        **kwargs: Any,
    ) -> None:
        super().__init__(
            output_filename=output_filename,
            date=date,
            display_date=display_date,
            suppress_empty=False,
        )
        self.sport_name = "Soccer"
        self.mad_fan = mad_fan

        if favorite_teams is not None:
            self.favorite_teams = favorite_teams
        elif team_id is not None and team_name is not None:
            self.favorite_teams = [(team_id, team_name)]
        else:
            self.favorite_teams = [
                (AL_NASSR_TEAM_ID, "Al-Nassr"),
                (PORTUGAL_TEAM_ID, "Portugal"),
            ]

        self.provider = SoccerDataProvider()
        if not self.branding:
            self.branding = "DISTRACTEDFORTUNE.COM/SCREAMSHEET"

    def get_title(self) -> str:
        return "Football Screamsheet"

    def get_subtitle(self) -> str:
        return ""

    def build_sections(self) -> List[Section]:
        sections: List[Section] = []

        # 1. Front page: multi-league game scores
        sections.append(
            SoccerGameScoresComponent(
                title="Scores",
                provider=self.provider,
                date=self.date,
            )
        )

        # 2. Front page: dual mini-standings (Saudi Pro League & Premier League)
        sections.append(
            SoccerStandingsComponent(
                title="League Standings",
                provider=self.provider,
                date=self.date,
            )
        )

        # 3. Back page: Match of the Day deep dive or off-day fallback
        sections.append(
            SoccerBoxScoreComponent(
                title="Match of the Day",
                provider=self.provider,
                date=self.date,
                favorite_teams=self.favorite_teams,
            )
        )

        return sections
