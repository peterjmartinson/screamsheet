"""NFL screamsheet implementation."""
from typing import List, Optional, Tuple
from datetime import datetime

from .base_sports import SportsScreamsheet
from .nfl_router import ScreamSheetRouter, NFLDayStrategy
from ..providers.nfl_provider import NFLDataProvider
from ..base import Section
from ..renderers import (
    GameScoresSection,
    StandingsSection,
    GameSummarySection,
    NFLInjuriesSection,
)


class NFLScreamsheet(SportsScreamsheet):
    """NFL-specific screamsheet with day-of-week strategy routing."""
    
    def __init__(
        self,
        output_filename: str,
        team_id: Optional[int] = None,
        team_name: Optional[str] = None,
        date: Optional[datetime] = None,
        favorite_teams: Optional[List[Tuple[int, str]]] = None,
    ):
        """
        Initialize NFL screamsheet.
        
        Args:
            output_filename: Path to save the PDF
            team_id: NFL team ID (deprecated — use favorite_teams)
            team_name: Team name (deprecated — use favorite_teams)
            date: Target date (defaults to yesterday)
            favorite_teams: Priority-ordered list of (team_id, team_name) tuples.
        """
        super().__init__(
            sport_name="NFL",
            output_filename=output_filename,
            team_id=team_id,
            team_name=team_name,
            date=date,
            favorite_teams=favorite_teams,
        )
        self.router = ScreamSheetRouter(override_date=self.date)
        self.strategy = self.router.get_strategy(self.date)
    
    def create_provider(self) -> NFLDataProvider:
        """Create NFL data provider."""
        return NFLDataProvider()
    
    def get_date_string(self) -> str:
        """Return the formatted date string with NFL week info."""
        date_str = self.date.strftime("%B %d, %Y")
        
        # Add week information if available from provider
        week_info = self.provider._get_current_week(self.date) if hasattr(self.provider, '_get_current_week') else getattr(self.provider, 'current_week', None)
        if week_info:
            season_name = week_info.get('SeasonName', '')
            week_detail = week_info.get('WeekDetail', '')
            
            # Format: "Postseason, Wild Card (Jan 7-13) • STRATEGY"
            if season_name and week_detail:
                return f"{date_str}\n{season_name}, {week_detail} • {self.strategy.value}"
            elif season_name:
                return f"{date_str}\n{season_name} • {self.strategy.value}"
        
        return f"{date_str} • {self.strategy.value}"


    def build_sections(self) -> List[Section]:
        """Build sections dynamically based on DayStrategy."""
        sections = []
        featured = self._resolve_featured_team()
        featured_id = featured[0] if featured else (self.favorite_teams[0][0] if self.favorite_teams else 0)
        featured_name = featured[1] if featured else (self.favorite_teams[0][1] if self.favorite_teams else "NFL")

        if self.strategy == NFLDayStrategy.RECAP:
            # Monday: Scores + Standings + Recap/Summary
            sections.append(GameScoresSection(title="NFL Weekly Scores", provider=self.provider, date=self.date))
            sections.append(StandingsSection(title="NFL Standings", provider=self.provider))
            if featured_id:
                sections.append(GameSummarySection(title=f"{featured_name} Game Summary", provider=self.provider, team_id=featured_id, date=self.date))

        elif self.strategy in (NFLDayStrategy.STANDINGS_AND_INJURIES, NFLDayStrategy.KEYS_TO_VICTORY):
            # Tuesday / Friday: Standings + Injuries
            sections.append(StandingsSection(title="NFL Standings", provider=self.provider))
            if featured_id:
                sections.append(NFLInjuriesSection(title=f"{featured_name} Injury Report", provider=self.provider, team_id=featured_id))

        elif self.strategy in (NFLDayStrategy.FILM_ROOM, NFLDayStrategy.TNF_SCOUTING, NFLDayStrategy.WEEKEND_PREP, NFLDayStrategy.GAMEDAY_CARD):
            # Other days: Scores + Standings (+ Injuries if available)
            sections.append(GameScoresSection(title="NFL Slate & Scores", provider=self.provider, date=self.date))
            sections.append(StandingsSection(title="NFL Standings", provider=self.provider))
            if featured_id:
                sections.append(NFLInjuriesSection(title=f"{featured_name} Report", provider=self.provider, team_id=featured_id))

        return sections
