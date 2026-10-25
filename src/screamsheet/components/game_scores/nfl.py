"""NFL game scores component."""
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from ...base import DataProvider
from ...providers.nfl_provider import NFLDataProvider
from ..registry import ComponentRegistry
from .base import GameScoresComponent


@ComponentRegistry.register("nfl_game_scores")
class NFLGameScoresComponent(GameScoresComponent):
    """Self-contained NFL game scores component."""

    component_type = "nfl_game_scores"

    def __init__(
        self,
        title: str = "NFL Game Scores",
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
        return NFLDataProvider()
