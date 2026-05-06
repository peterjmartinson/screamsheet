"""Base class for all sports screamsheets."""
import io
import logging
from abc import abstractmethod
from typing import List, Optional, Tuple
from datetime import datetime

from reportlab.platypus import SimpleDocTemplate
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

    def generate(self) -> str:
        """Generate the PDF with iterative overflow compression.

        Before writing to disk, the story is rendered to a BytesIO buffer.  If
        Platypus reports more than one page, the ``row_padding`` on every
        ``StandingsSection`` is decremented (floor: 1) and the story is rebuilt.
        Up to three compression attempts are made; then the final story is
        written to ``self.output_filename``.
        """
        self.sections = self.build_sections()

        _doc_kwargs = dict(
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36,
        )

        # Iterative compression loop
        for _attempt in range(3):
            story = self._build_story()
            buf = io.BytesIO()
            probe = SimpleDocTemplate(buf, **_doc_kwargs)
            probe.build(story)
            if probe.page <= 1:
                break
            for sec in self.sections:
                if isinstance(sec, StandingsSection):
                    sec.row_padding = max(1, sec.row_padding - 1)

        # Final build to disk
        story = self._build_story()
        doc = SimpleDocTemplate(self.output_filename, **_doc_kwargs)
        if self.brand_footer_text:
            footer_text = self.brand_footer_text

            def _draw_brand_footer(canvas: object, doc: object) -> None:  # type: ignore[override]
                import reportlab.lib.pagesizes as _ps
                c = canvas  # type: ignore[attr-defined]
                c.saveState()
                c.setFont("Helvetica-Bold", 8)
                c.drawCentredString(_ps.letter[0] / 2, 18, footer_text)
                c.restoreState()

            doc.build(story, onFirstPage=_draw_brand_footer, onLaterPages=_draw_brand_footer)
        else:
            doc.build(story)

        return self.output_filename
