"""Unified News component capable of cherry-picking any news sources from the central catalog."""
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from ...base import DataProvider
from ...providers.news_sources import UnifiedNewsProvider
from ..registry import ComponentRegistry
from .base import NewsStoryComponent


@ComponentRegistry.register("news")
@ComponentRegistry.register("unified_news")
class UnifiedNewsComponent(NewsStoryComponent):
    """Self-contained unified news component supporting arbitrary ``sources`` from :data:`NEWS_SOURCE_CATALOG`."""

    component_type = "unified_news"

    def __init__(
        self,
        title: str = "Latest News",
        provider: Optional[DataProvider] = None,
        favorite_teams: Optional[List[str]] = None,
        max_articles: int = 4,
        start_index: int = 0,
        date: Optional[datetime] = None,
        sources: Optional[List[Any]] = None,
        sport: str = "mlb",
        category: Optional[str] = None,
        default_sheet: str = "mlb_news",
        mode: str = "multi",
        primary_source: str = "",
        primary_source_bonus: int = 25,
        extra_feeds: Optional[dict[str, str]] = None,
        **kwargs: Any,
    ) -> None:
        self.favorite_teams: List[str] = list(favorite_teams) if favorite_teams else []
        self._initial_max_articles = max_articles if max_articles is not None else 4
        self.sources = list(sources) if sources else None
        self.sport = sport
        self.category = category or sport
        self.default_sheet = default_sheet
        self.mode = mode
        self.primary_source = primary_source
        self.primary_source_bonus = primary_source_bonus
        self.extra_feeds = extra_feeds
        super().__init__(
            title=title,
            provider=provider,
            max_articles=self._initial_max_articles,
            start_index=start_index,
            date=date,
            favorite_teams=self.favorite_teams,
            **kwargs,
        )

    def create_default_provider(self) -> DataProvider:
        return UnifiedNewsProvider(
            favorite_teams=self.favorite_teams,
            max_articles=max(self._initial_max_articles, 8),
            sources=self.sources,
            sport=self.sport,
            category=self.category,
            default_sheet=self.default_sheet,
            mode=self.mode,
            primary_source=self.primary_source or None,
            primary_source_bonus=self.primary_source_bonus,
            extra_feeds=self.extra_feeds,
        )
