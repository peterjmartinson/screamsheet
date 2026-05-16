"""Base class for all sports screamsheets."""
import logging
from abc import abstractmethod
from typing import List, Optional, Tuple
from datetime import datetime

from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame,
    NextPageTemplate, PageBreak, Paragraph, Spacer,
)
from reportlab.platypus.flowables import KeepInFrame
from reportlab.lib.pagesizes import letter

logger = logging.getLogger(__name__)

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
        date: Optional[datetime] = None,
        display_date: Optional[datetime] = None,
        favorite_teams: Optional[List[Tuple[int, str]]] = None,
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
        """
        super().__init__(output_filename, date, display_date)
        self.sport_name = sport_name

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
    
    def get_title(self) -> str:
        """Get the main title for this screamsheet."""
        return f"{self.sport_name} Screamsheet"

    def _resolve_featured_team(self) -> Optional[Tuple[int, str]]:
        """Return the first team in the priority list that played on self.date.

        Returns:
            (team_id, team_name) tuple, or None if no team played (or no list set).
        """
        date_str = self.date.strftime("%Y-%m-%d")
        logger.info("Resolving featured team for %s on %s (%d candidates)", self.sport_name, date_str, len(self.favorite_teams))
        for tid, tname in self.favorite_teams:
            played = self.provider.has_game(tid, self.date)
            logger.info("  %s (id=%s) played on %s: %s", tname, tid, date_str, played)
            if played:
                logger.info("Featured team selected: %s (id=%s)", tname, tid)
                return (tid, tname)
        logger.warning("No favorite team played on %s — back page will be skipped", date_str)
        return None
    
    def generate(self) -> str:
        """Generate a two-page PDF: front (scores + standings) and back (box score)."""
        self.sections = self.build_sections()

        margin = 36
        page_width, page_height = letter
        frame_w = page_width - 2 * margin
        frame_h = page_height - 2 * margin

        front_frame = Frame(margin, margin, frame_w, frame_h, id="front_frame")
        back_frame  = Frame(margin, margin, frame_w, frame_h, id="back_frame")

        doc = BaseDocTemplate(
            self.output_filename,
            pagesize=letter,
            leftMargin=margin, rightMargin=margin,
            topMargin=margin,  bottomMargin=margin,
        )
        doc.addPageTemplates([
            PageTemplate(id="Front", frames=[front_frame]),
            PageTemplate(id="Back",  frames=[back_frame],  onPage=self._draw_branding_footer),
        ])

        front_content: List = []
        back_content:  List = []

        # Header always lives on the front page
        front_content.append(Paragraph(self.get_title(), self.title_style))
        subtitle = self.get_subtitle()
        if subtitle:
            front_content.append(Paragraph(f"<i>{subtitle}</i>", self.subtitle_style))
        front_content.append(Paragraph(self.get_date_string(), self.subtitle_style))
        front_content.append(Spacer(1, 12))

        for section in self.sections:
            if section.has_content():
                elements = section.render()
                if getattr(section, "page_slot", "front") == "back":
                    back_content.extend(elements)
                    back_content.append(Spacer(1, 20))
                else:
                    front_content.extend(elements)
                    front_content.append(Spacer(1, 20))

        story: List = [
            KeepInFrame(maxWidth=0, maxHeight=frame_h, content=front_content, mode="shrink")
        ]

        if back_content:
            story.append(NextPageTemplate("Back"))
            story.append(PageBreak())
            story.append(
                KeepInFrame(maxWidth=0, maxHeight=frame_h, content=back_content, mode="shrink")
            )

        doc.build(story)
        return self.output_filename

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
        
        # 3. Box Score Section — feature the first team in the priority list that played
        featured = self._resolve_featured_team()
        if featured:
            featured_id, featured_name = featured
            is_primary = bool(self.favorite_teams) and featured == self.favorite_teams[0]
            sections.append(
                BoxScoreSection(
                    title=f"{featured_name} Box Score",
                    provider=self.provider,
                    team_id=featured_id,
                    date=self.date,
                    is_primary_favorite=is_primary,
                )
            )
        
        # # 4. Game Summary Section (only if team is specified)
        # if featured:
        #     featured_id, featured_name = featured
        #     sections.append(
        #         GameSummarySection(
        #             title=f"{featured_name} Game Summary",
        #             provider=self.provider,
        #             team_id=featured_id,
        #             date=self.date
        #         )
        #     )
        
        return sections

