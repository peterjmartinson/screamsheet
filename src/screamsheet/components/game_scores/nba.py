"""NBA game scores component."""
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from ...base import DataProvider
from ...providers.nba_provider import NBADataProvider
from ..registry import ComponentRegistry
from .base import GameScoresComponent


@ComponentRegistry.register("nba_game_scores")
class NBAGameScoresComponent(GameScoresComponent):
    """Self-contained NBA game scores component."""

    component_type = "nba_game_scores"

    def __init__(
        self,
        title: str = "NBA Game Scores",
        provider: Optional[DataProvider] = None,
        date: Optional[datetime] = None,
        upcoming_games: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            title=title,
            provider=provider,
            date=date,
            upcoming_games=upcoming_games,
            **kwargs,
        )

    def create_default_provider(self) -> DataProvider:
        return NBADataProvider()
