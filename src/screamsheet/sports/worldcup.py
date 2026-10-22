"""FIFA World Cup 2026 screamsheet."""
from __future__ import annotations

import logging
import random
from typing import Any, Dict, List, Optional

from ..base import BaseScreamsheet, Section
from ..components.box_score import WorldCupBoxScoreComponent
from ..components.game_scores import WorldCupGameScoresComponent
from ..components.standings import WorldCupStandingsComponent
from ..providers.worldcup26_provider import WorldCup26Provider, PRIORITY_TEAM_NAMES

logger = logging.getLogger(__name__)


class FIFAWorldCupScreamsheet(BaseScreamsheet):
    """Generates a two-page World Cup 2026 screamsheet."""

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

    def get_title(self) -> str:
        return "FIFA World Cup 2026"

    def get_subtitle(self) -> str:
        return ""

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

    def build_sections(self) -> List[Section]:
        sections: List[Section] = []

        sections.append(
            WorldCupGameScoresComponent(
                title="World Cup Scores",
                provider=self.provider,
                date=self.date,
            )
        )

        sections.append(
            WorldCupStandingsComponent(
                title="Group Standings",
                provider=self.provider,
                date=self.date,
            )
        )

        featured = self._resolve_featured_fixture()
        if featured:
            fid: int = int(featured["fixture_id"])
            away = featured.get("away_team") or ""
            home = featured.get("home_team") or ""
            sections.append(
                WorldCupBoxScoreComponent(
                    title=f"{away} vs {home}",
                    provider=self.provider,
                    fixture_id=fid,
                    date=self.date,
                )
            )

        return sections
