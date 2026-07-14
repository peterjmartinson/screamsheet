"""FIFA World Cup 2026 screamsheet."""
from __future__ import annotations

import logging
import random
from typing import Any, Dict, List, Optional

from reportlab.platypus import Paragraph, Spacer
from reportlab.lib.pagesizes import letter

from ..base import BaseScreamsheet, Section
from ..providers.worldcup26_provider import WorldCup26Provider, PRIORITY_TEAM_NAMES
from ..renderers.worldcup_game_scores import WorldCupGameScoresSection
from ..renderers.worldcup_standings import WorldCupStandingsSection
from ..renderers.worldcup_box_score import WorldCupBoxScoreSection

logger = logging.getLogger(__name__)


class FIFAWorldCupScreamsheet(BaseScreamsheet):
    """Generates a two-page World Cup 2026 screamsheet.

    Front page:
      Top    – Yesterday's scores (all completed fixtures)
      Bottom – Group standings

    Back page:
      Left   – Event narrative / game summary for the featured fixture
      Right  – Per-player box score table
    """

    def __init__(
        self,
        output_filename: str,
        **kwargs: Any,
    ) -> None:
        from datetime import datetime, timedelta

        date = kwargs.pop("date", None) or (datetime.now() - timedelta(days=1))
        display_date = kwargs.pop("display_date", None)
        super().__init__(output_filename=output_filename, date=date, display_date=display_date)
        self.provider = WorldCup26Provider()

    # ------------------------------------------------------------------
    # BaseScreamsheet interface
    # ------------------------------------------------------------------

    def get_title(self) -> str:
        return "FIFA World Cup 2026"

    def get_subtitle(self) -> str:
        return ""

    # ------------------------------------------------------------------
    # Featured fixture resolution
    # ------------------------------------------------------------------

    def _resolve_featured_fixture(self) -> Optional[Dict[str, Any]]:
        """Return the first priority-team fixture, or random from yesterday."""
        games = self.provider.get_game_scores(self.date)
        completed = [
            g for g in games
            if g.get("status_short") in self.provider.COMPLETED_STATUSES
        ]
        if not completed:
            logger.warning("No completed World Cup fixtures on %s", self.date.strftime("%Y-%m-%d"))
            return None

        for name in PRIORITY_TEAM_NAMES:
            for g in completed:
                if g.get("home_team") == name or g.get("away_team") == name:
                    logger.info("Featured fixture: %s vs %s (priority: %s)", g.get("away_team"), g.get("home_team"), name)
                    return g

        chosen = random.choice(completed)
        logger.info("Featured fixture (random): %s vs %s", chosen.get("away_team"), chosen.get("home_team"))
        return chosen

    # ------------------------------------------------------------------
    # Section construction
    # ------------------------------------------------------------------

    def build_sections(self) -> List[Section]:
        sections: List[Section] = []

        # Front / top: scores
        sections.append(
            WorldCupGameScoresSection(
                title="World Cup Scores",
                provider=self.provider,
                date=self.date,
            )
        )

        # Front / bottom: group standings
        sections.append(
            WorldCupStandingsSection(
                title="Group Standings",
                provider=self.provider,
            )
        )

        # Back: box score for the featured fixture
        featured = self._resolve_featured_fixture()
        if featured:
            fid: int = int(featured["fixture_id"])
            away = featured.get("away_team") or ""
            home = featured.get("home_team") or ""
            sections.append(
                WorldCupBoxScoreSection(
                    title=f"{away} vs {home}",
                    provider=self.provider,
                    fixture_id=fid,
                    date=self.date,
                )
            )

        return sections

    # ------------------------------------------------------------------
    # PDF generation
    # ------------------------------------------------------------------

