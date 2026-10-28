"""MLB News RSS component."""
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from ...base import DataProvider
from ...providers.mlb_news_rss_provider import MLBNewsRssProvider
from ..registry import ComponentRegistry
from .base import NewsStoryComponent


@ComponentRegistry.register("mlb_news")
class MLBNewsComponent(NewsStoryComponent):
    """Self-contained MLB.com RSS news component."""

    component_type = "mlb_news"

    def __init__(
        self,
        title: str = "MLB News",
        provider: Optional[DataProvider] = None,
        favorite_teams: Optional[List[str]] = None,
        max_articles: int = 4,
        start_index: int = 0,
        date: Optional[datetime] = None,
        mode: str = "multi",
        primary_source: str = MLBNewsRssProvider.PRIMARY_SOURCE,
        primary_source_bonus: int = MLBNewsRssProvider.PRIMARY_SOURCE_BONUS,
        extra_feeds: Optional[dict[str, str]] = None,
        **kwargs: Any,
    ) -> None:
        self.favorite_teams: List[str] = list(favorite_teams) if favorite_teams else []
        self._initial_max_articles = max_articles if max_articles is not None else 4
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
        return MLBNewsRssProvider(
            favorite_teams=self.favorite_teams,
            max_articles=max(self._initial_max_articles, 8),
            mode=self.mode,
            primary_source=self.primary_source,
            primary_source_bonus=self.primary_source_bonus,
            extra_feeds=self.extra_feeds,
        )
