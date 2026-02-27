"""Base class for all sports screamsheets."""
from abc import abstractmethod
from typing import List, Optional
from datetime import datetime

from ..base import BaseScreamsheet, Section, DataProvider
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
        date: Optional[datetime] = None
    ):
        """
        Initialize the sports screamsheet.
        
        Args:
            sport_name: Name of the sport (e.g., "MLB", "NHL")
            output_filename: Path to save the PDF
            team_id: ID of the team to feature (optional)
            team_name: Name of the team to feature (optional)
            date: Target date (defaults to yesterday)
        """
        super().__init__(output_filename, date)
        self.sport_name = sport_name
        self.team_id = team_id
        self.team_name = team_name
        self.provider = self.create_provider()
    
    @abstractmethod
    def create_provider(self) -> DataProvider:
        """
        Create the data provider for this sport.
        
        Returns:
            DataProvider instance for fetching sport-specific data
        """
        pass
    
    def get_title(self) -> str:
        """Get the main title for this screamsheet."""
        return f"{self.sport_name} Screamsheet"
    
    def build_sections(self) -> List[Section]:
        """Build all sections for the sports screamsheet."""
        sections = []
        
        # 1. Game Scores Section (always included)
        sections.append(
            GameScoresSection(
                title=f"{self.sport_name} Game Scores",
                provider=self.provider,
                date=self.date
            )
        )
        
        # 2. Standings Section (always included)
        sections.append(
            StandingsSection(
                title=f"{self.sport_name} Standings",
                provider=self.provider
            )
        )
        
        # 3. Box Score Section (only if team is specified)
        if self.team_id and self.team_name:
            sections.append(
                BoxScoreSection(
                    title=f"{self.team_name} Box Score",
                    provider=self.provider,
                    team_id=self.team_id,
                    date=self.date
                )
            )
        
        # # 4. Game Summary Section (only if team is specified)
        # if self.team_id and self.team_name:
        #     sections.append(
        #         GameSummarySection(
        #             title=f"{self.team_name} Game Summary",
        #             provider=self.provider,
        #             team_id=self.team_id,
        #             date=self.date
        #         )
        #     )
        
        return sections
