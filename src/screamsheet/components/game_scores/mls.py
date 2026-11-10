"""MLS game scores component."""
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from ...base import DataProvider
from ...providers.mls_provider import MLSDataProvider
from ..registry import ComponentRegistry
from .base import GameScoresComponent


@ComponentRegistry.register("mls_game_scores")
class MLSGameScoresComponent(GameScoresComponent):
    """Self-contained MLS game scores component."""

    component_type = "mls_game_scores"

    def __init__(
        self,
        title: str = "MLS Game Scores",
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
        return MLSDataProvider()
