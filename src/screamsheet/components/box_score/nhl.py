"""NHL box score component."""
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional, Tuple

from ...base import DataProvider
from ...providers.nhl_provider import NHLDataProvider
from ..registry import ComponentRegistry
from .base import BoxScoreComponent


@ComponentRegistry.register("nhl_box_score")
class NHLBoxScoreComponent(BoxScoreComponent):
    """Self-contained NHL box score component."""

    component_type = "nhl_box_score"

    def __init__(
        self,
        title: str = "NHL Box Score",
        provider: Optional[DataProvider] = None,
        team_id: Optional[int] = None,
        date: Optional[datetime] = None,
        is_primary_favorite: bool = False,
        mad_fan: bool = False,
        favorite_teams: Optional[List[Tuple[int, str]]] = None,
        team_name: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            title=title,
            provider=provider,
            team_id=team_id,
            date=date,
            is_primary_favorite=is_primary_favorite,
            mad_fan=mad_fan,
            favorite_teams=favorite_teams,
            team_name=team_name,
            **kwargs,
        )

    def create_default_provider(self) -> DataProvider:
        return NHLDataProvider()
