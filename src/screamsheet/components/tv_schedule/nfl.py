"""NFL TV broadcast schedule component."""
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional, Tuple

from ...base import DataProvider
from ...providers.nfl_provider import NFLDataProvider
from ..registry import ComponentRegistry
from .base import TVScheduleComponent


@ComponentRegistry.register("nfl_tv_schedule")
class NFLTVScheduleComponent(TVScheduleComponent):
    """Self-contained NFL TV broadcast schedule component."""

    component_type = "nfl_tv_schedule"

    def __init__(
        self,
        title: str = "Today's Broadcasts",
        provider: Optional[DataProvider] = None,
        date: Optional[datetime] = None,
        display_date: Optional[datetime] = None,
        favorite_teams: Optional[List[Tuple[int, str]]] = None,
        schedule_items: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            title=title,
            provider=provider,
            date=date,
            display_date=display_date,
            favorite_teams=favorite_teams,
            schedule_items=schedule_items,
            **kwargs,
        )

    def create_default_provider(self) -> DataProvider:
        return NFLDataProvider()
