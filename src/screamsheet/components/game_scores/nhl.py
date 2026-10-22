"""NHL game scores component."""
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from ...base import DataProvider
from ...providers.nhl_provider import NHLDataProvider
from ..registry import ComponentRegistry
from .base import GameScoresComponent


@ComponentRegistry.register("nhl_game_scores")
class NHLGameScoresComponent(GameScoresComponent):
    """Self-contained NHL game scores component."""

    component_type = "nhl_game_scores"

    def __init__(
        self,
        title: str = "NHL Game Scores",
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
        return NHLDataProvider()
