"""Base class for all sports screamsheets."""
import logging
import random
from abc import abstractmethod
from typing import List, Optional, Tuple
from datetime import datetime

from reportlab.platypus import (
    Paragraph, Spacer,
)
from reportlab.lib.pagesizes import letter

logger = logging.getLogger(__name__)

from ..base import BaseScreamsheet, Section, DataProvider
from ..components.box_score import BoxScoreComponent
from ..components.game_scores import GameScoresComponent
from ..components.standings import StandingsComponent
from ..renderers import (
    GameScoresSection,
    StandingsSection,
    BoxScoreSection,
    GameSummarySection,
)


class SportsScreamsheet(BaseScreamsheet):
    """
    Base class for all sports screamsheets.
    
    Sports screamsheets have a common structure:
    1. Game scores from yesterday
    2. League standings
    3. Box score for a specific team (if they played)
    4. Game summary for that team (if they played)
    
    Subclasses provide sport-specific data providers and configuration.
    """
    
    def __init__(
        self,
        sport_name: str,
        output_filename: str,
        team_id: Optional[int] = None,
        team_name: Optional[str] = None,
        date: Optional[datetime] = None,
        display_date: Optional[datetime] = None,
        favorite_teams: Optional[List[Tuple[int, str]]] = None,
        mad_fan: bool = False,
    ):
        """
        Initialize the sports screamsheet.
        
        Args:
            sport_name: Name of the sport (e.g., "MLB", "NHL")
            output_filename: Path to save the PDF
            team_id: ID of the team to feature (optional, deprecated — use favorite_teams)
            team_name: Name of the team to feature (optional, deprecated — use favorite_teams)
            date: Target date for game data lookups (defaults to yesterday)
            display_date: Date shown in the subtitle header (defaults to date)
            favorite_teams: Priority-ordered list of (team_id, team_name) tuples. The
                first team that played on `date` will be featured. When provided,
                team_id and team_name are ignored.
            mad_fan: If True, generate an enraged hometown-fan recap when the primary
                favorite team loses. Defaults to False.
        """
        super().__init__(output_filename, date, display_date)
        self.sport_name = sport_name
        self.mad_fan = mad_fan

        # Build the canonical priority list.
        # favorite_teams wins; otherwise fall back to the legacy single-team args.
        if favorite_teams is not None:
            self.favorite_teams: List[Tuple[int, str]] = favorite_teams
        elif team_id is not None and team_name is not None:
            self.favorite_teams = [(team_id, team_name)]
        else:
            self.favorite_teams = []

        # Keep legacy attributes for backward-compat (tests that read .team_id / .team_name).
        self.team_id: Optional[int] = team_id
        self.team_name: Optional[str] = team_name

        self.provider = self.create_provider()
    
    @abstractmethod
    def create_provider(self) -> DataProvider:
        """
        Create the data provider for this sport.
        
        Returns:
            DataProvider instance for fetching sport-specific data
        """
        pass

    def create_game_scores_component(self) -> GameScoresComponent:
        """Create the game scores component for this sport."""
        return GameScoresComponent(
            title=f"{self.sport_name} Game Scores",
            provider=self.provider,
            date=self.date,
        )

    def create_standings_component(self) -> StandingsComponent:
        """Create the standings component for this sport."""
        return StandingsSection(
            title=f"{self.sport_name} Standings",
            provider=self.provider,
            date=self.date,
        )

    def create_box_score_component(
        self,
        team_id: int,
        team_name: str,
        is_primary_favorite: bool = False,
    ) -> BoxScoreComponent:
        """Create the box score component for this sport."""
        return BoxScoreComponent(
            title=f"{team_name} Box Score",
            provider=self.provider,
            team_id=team_id,
            date=self.date,
            is_primary_favorite=is_primary_favorite,
            mad_fan=self.mad_fan,
        )
    
    def get_title(self) -> str:
        """Get the main title for this screamsheet."""
        return f"{self.sport_name} Screamsheet"

    def _pick_random_team(self) -> Optional[Tuple[int, str]]:
        """Return a random (team_id, team_name) from completed games on self.date.

        Used as a fallback when no favourite team played.  Returns None when
        the provider reports no completed games for the date.
        """
        teams = self.provider.get_all_teams_for_date(self.date)
        if not teams:
            logger.warning(
                "No completed games found for %s on %s — back page will be skipped",
                self.sport_name,
                self.date.strftime("%Y-%m-%d"),
            )
            return None
        chosen = random.choice(teams)
        logger.info(
            "Fallback team selected at random: %s (id=%s)", chosen[1], chosen[0]
        )
        return chosen

    def _resolve_featured_team(self) -> Optional[Tuple[int, str]]:
        """Return the first team in the priority list that played on self.date.

        If no favourite played, falls back to a random completed game via
        _pick_random_team().  Returns None only if no games were played at all.

        Returns:
            (team_id, team_name) tuple, or None if no games found.
        """
        date_str = self.date.strftime("%Y-%m-%d")
        logger.info("Resolving featured team for %s on %s (%d candidates)", self.sport_name, date_str, len(self.favorite_teams))
        for tid, tname in self.favorite_teams:
            played = self.provider.has_game(tid, self.date)
            logger.info("  %s (id=%s) played on %s: %s", tname, tid, date_str, played)
            if played:
                logger.info("Featured team selected: %s (id=%s)", tname, tid)
                return (tid, tname)
        logger.info("No favourite team played on %s — falling back to random game", date_str)
        return self._pick_random_team()
    
    def build_sections(self) -> List[Section]:
        """Build all sections for the sports screamsheet."""
        sections = []
        
        # 1. Game Scores Component (always included)
        sections.append(self.create_game_scores_component())
        
        # 2. Standings Component (always included)
        sections.append(self.create_standings_component())
        
        # 3. Box Score Component — feature the first team in the priority list that played
        featured = self._resolve_featured_team()
        if featured:
            featured_id, featured_name = featured
            is_primary = bool(self.favorite_teams) and featured == self.favorite_teams[0]
            sections.append(
                self.create_box_score_component(
                    team_id=featured_id,
                    team_name=featured_name,
                    is_primary_favorite=is_primary,
                )
            )
        
        return sections
