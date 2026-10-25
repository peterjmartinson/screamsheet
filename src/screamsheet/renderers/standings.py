"""Standings section renderer (backward-compatible wrapper around StandingsComponent)."""
from datetime import datetime
from typing import Any, List, Optional

import pandas as pd
from reportlab.platypus import Table

from ..base import DataProvider
from ..components.standings import (
    MLBStandingsComponent,
    NBAStandingsComponent,
    NFLStandingsComponent,
    NHLStandingsComponent,
    StandingsComponent,
)


class StandingsSection(StandingsComponent):
    """Backward-compatible standings section.

    Sport screamsheets now use dedicated ``MLBStandingsComponent``,
    ``NHLStandingsComponent``, ``NBAStandingsComponent``, and
    ``NFLStandingsComponent`` classes directly. ``StandingsSection`` remains
    available for legacy callers that pass a generic provider/DataFrame.
    """

    def __init__(
        self,
        title: str,
        provider: DataProvider,
        date: Optional[datetime] = None,
    ) -> None:
        super().__init__(title=title, provider=provider, date=date)

    def _build_standings_flowables(self) -> List[Any]:
        if not isinstance(self.data, pd.DataFrame) or self.data.empty:
            return []

        if (
            "conference" in self.data.columns
            and "division" in self.data.columns
            and "GP" in self.data.columns
        ):
            return [self._render_nhl_standings(self.data)]
        if "conference" in self.data.columns and "winPercent" in self.data.columns:
            return [self._render_nfl_standings(self.data)]
        if "conference" in self.data.columns:
            return [self._render_nba_standings(self.data)]
        if "division" in self.data.columns:
            return [self._render_mlb_standings(self.data)]
        return [self._render_generic_standings(self.data)]

    def _render_mlb_standings(self, standings_df: pd.DataFrame) -> Table:
        return MLBStandingsComponent.render_mlb_table(standings_df, self.centered_style)

    def _render_nhl_standings(self, standings_df: pd.DataFrame) -> Table:
        return NHLStandingsComponent.render_nhl_table(standings_df, self.centered_style)

    def _render_nfl_standings(self, standings_df: pd.DataFrame) -> Table:
        return NFLStandingsComponent.render_nfl_table(standings_df, self.centered_style)

    def _render_nba_standings(self, standings_df: pd.DataFrame) -> Table:
        return NBAStandingsComponent.render_nba_table(standings_df, self.centered_style)

    def _render_generic_standings(self, standings_df: pd.DataFrame) -> Table:
        return self.build_generic_table(standings_df)
