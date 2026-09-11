"""NFL screamsheet implementation."""
from typing import List, Optional, Tuple
from datetime import datetime

from .base_sports import SportsScreamsheet
from .nfl_router import ScreamSheetRouter, NFLDayStrategy
from ..providers.nfl_provider import NFLDataProvider
from ..providers.nfl_news_provider import NFLNewsProvider
from ..base import Section
from ..renderers import (
    GameScoresSection,
    StandingsSection,
    BoxScoreSection,
    NFLInjuriesSection,
    NewsArticlesSection,
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
        mad_fan: bool = False,
    ):
        """
        Initialize NFL screamsheet.
        
        Args:
            output_filename: Path to save the PDF
            team_id: NFL team ID (deprecated — use favorite_teams)
            team_name: Team name (deprecated — use favorite_teams)
            date: Target date (defaults to yesterday)
            favorite_teams: Priority-ordered list of (team_id, team_name) tuples.
            mad_fan: If True, enable enraged hometown-fan recap on loss. Defaults to False.
        """
        super().__init__(
            sport_name="NFL",
            output_filename=output_filename,
            team_id=team_id,
            team_name=team_name,
            date=date,
            favorite_teams=favorite_teams,
            mad_fan=mad_fan,
        )
        self.router = ScreamSheetRouter(override_date=self.date)
        self.strategy = self.router.get_strategy(self.date)
        # Create news provider for non-game days
        fav_team_names = [t[1] for t in self.favorite_teams] if self.favorite_teams else []
        self.news_provider = NFLNewsProvider(favorite_teams=fav_team_names, max_articles=4)
    
    def create_provider(self) -> NFLDataProvider:
        """Create NFL data provider."""
        return NFLDataProvider()
    
    def get_subtitle(self) -> Optional[str]:
        """Return clean, human-readable day subtitle in italics."""
        from .nfl_router import DAY_SUBTITLE_MAP
        return DAY_SUBTITLE_MAP.get(self.strategy, self.strategy.value)

    def get_date_string(self) -> str:
        """Return the formatted date string without cluttered season/week labels."""
        return self.date.strftime("%B %d, %Y")

    def build_sections(self) -> List[Section]:
        """Build sections dynamically based on game availability and day strategy.

        Page distribution rule:
        - Page 1 (front): Game Scores and Standings (or Standings + Injuries on front).
        - Page 2 (back): Narrative Game Summaries (MNF/TNF/Sunday) or News Articles.
        """
        sections: List[Section] = []
        
        # Check if completed games were played on self.date
        completed_teams = self.provider.get_all_teams_for_date(self.date)
        has_games_played = len(completed_teams) > 0

        # Resolve featured team according to favorite_teams priority, falling back to random completed game
        featured = self._resolve_featured_team()
        featured_id = featured[0] if featured else (self.favorite_teams[0][0] if self.favorite_teams else 0)
        featured_name = featured[1] if featured else (self.favorite_teams[0][1] if self.favorite_teams else "NFL")

        # 1. Monday (RECAP) or any day when games were played yesterday (including Tuesday MNF or Friday TNF)
        if has_games_played or self.strategy == NFLDayStrategy.RECAP:
            sections.append(GameScoresSection(title="NFL Game Scores", provider=self.provider, date=self.date))
            sections.append(StandingsSection(title="NFL Standings", provider=self.provider, date=self.date))
            if featured and featured_id:
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
            else:
                back_news = NewsArticlesSection(title="NFL Headlines & Recap", provider=self.news_provider, max_articles=4)
                back_news.page_slot = "back"
                sections.append(back_news)

        # 2. Tuesday: STANDINGS_AND_INJURIES (when no MNF game played)
        elif self.strategy == NFLDayStrategy.STANDINGS_AND_INJURIES:
            sections.append(StandingsSection(title="NFL Standings & Division Check", provider=self.provider, date=self.date))
            if featured_id:
                sections.append(NFLInjuriesSection(title=f"{featured_name} Injury Report", provider=self.provider, team_id=featured_id))
            back_news = NewsArticlesSection(title="NFL News & Injury Analysis", provider=self.news_provider, max_articles=4)
            back_news.page_slot = "back"
            sections.append(back_news)

        # 3. Wednesday: FILM_ROOM
        elif self.strategy == NFLDayStrategy.FILM_ROOM:
            sections.append(StandingsSection(title="NFL Standings & Power Metrics", provider=self.provider, date=self.date))
            if featured_id:
                sections.append(NFLInjuriesSection(title=f"{featured_name} Practice & Roster Notes", provider=self.provider, team_id=featured_id))
            back_news = NewsArticlesSection(title="NFL Film Room & League Intel", provider=self.news_provider, max_articles=4)
            back_news.page_slot = "back"
            sections.append(back_news)

        # 4. Thursday: TNF_SCOUTING
        elif self.strategy == NFLDayStrategy.TNF_SCOUTING:
            sections.append(StandingsSection(title="NFL Standings", provider=self.provider, date=self.date))
            if featured_id:
                sections.append(NFLInjuriesSection(title=f"{featured_name} Injury & Depth Report", provider=self.provider, team_id=featured_id))
            back_news = NewsArticlesSection(title="Thursday Night Football Scouting & News", provider=self.news_provider, max_articles=4)
            back_news.page_slot = "back"
            sections.append(back_news)

        # 5. Friday: KEYS_TO_VICTORY (when no Thursday game played)
        elif self.strategy == NFLDayStrategy.KEYS_TO_VICTORY:
            sections.append(StandingsSection(title="NFL Standings & Playoff Picture", provider=self.provider, date=self.date))
            if featured_id:
                sections.append(NFLInjuriesSection(title=f"{featured_name} Final Injury Designations", provider=self.provider, team_id=featured_id))
            back_news = NewsArticlesSection(title="Weekend Keys to Victory & News", provider=self.news_provider, max_articles=4)
            back_news.page_slot = "back"
            sections.append(back_news)

        # 6. Saturday: WEEKEND_PREP
        elif self.strategy == NFLDayStrategy.WEEKEND_PREP:
            sections.append(StandingsSection(title="NFL Standings", provider=self.provider, date=self.date))
            if featured_id:
                sections.append(NFLInjuriesSection(title=f"{featured_name} Gameday Status Report", provider=self.provider, team_id=featured_id))
            back_news = NewsArticlesSection(title="Weekend Matchup Previews & Headlines", provider=self.news_provider, max_articles=4)
            back_news.page_slot = "back"
            sections.append(back_news)

        # 7. Sunday: GAMEDAY_CARD
        else:
            sections.append(StandingsSection(title="NFL Standings", provider=self.provider, date=self.date))
            if featured_id:
                sections.append(NFLInjuriesSection(title=f"{featured_name} Inactives & Lineup Notes", provider=self.provider, team_id=featured_id))
            back_news = NewsArticlesSection(title="Sunday Gameday News & Roster Updates", provider=self.news_provider, max_articles=4)
            back_news.page_slot = "back"
            sections.append(back_news)

        return sections
