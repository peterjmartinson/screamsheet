"""MLB game scores component."""
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from ...base import DataProvider
from ...providers.mlb_provider import MLBDataProvider
from ..registry import ComponentRegistry
from .base import GameScoresComponent


@ComponentRegistry.register("mlb_game_scores")
class MLBGameScoresComponent(GameScoresComponent):
    """Self-contained MLB game scores component."""

    component_type = "mlb_game_scores"

    def __init__(
        self,
        title: str = "MLB Game Scores",
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
        return MLBDataProvider()
