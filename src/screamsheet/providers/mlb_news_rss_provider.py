"""MLB.com and multi-source MLB news data provider."""
from typing import Any, Dict, List, Optional, Sequence, Union

from .news_sources import (
    MLB_JUNK_KEYWORDS,
    MLB_TEAM_FEEDS,
    NEWS_SOURCE_CATALOG,
    ResolvedNewsSource,
    UnifiedNewsProvider,
)


class MLBNewsRssProvider(UnifiedNewsProvider):
    """
    Data provider for MLB.com news via team-specific RSS feeds and secondary outlets.

    Delegates fetching, team-alias matching, junk filtering, body scraping,
    and multi-source clustering to :class:`~screamsheet.providers.news_sources.UnifiedNewsProvider`.
    """

    TEAM_FEEDS: Dict[Optional[str], str] = MLB_TEAM_FEEDS
    JUNK_KEYWORDS: List[str] = MLB_JUNK_KEYWORDS
    PRIMARY_SOURCE: str = "MLB.com"
    PRIMARY_SOURCE_BONUS: int = 25
    DEFAULT_SHEET: str = "mlb_news"
    DEFAULT_CATEGORY: str = "mlb"

    SECONDARY_FEEDS: Dict[str, str] = {
        spec.name: spec.url
        for spec in NEWS_SOURCE_CATALOG.values()
        if spec.category == "mlb" and spec.kind == "rss"
    }

    def __init__(
        self,
        favorite_teams: Optional[List[str]] = None,
        max_articles: int = 4,
        mode: str = "multi",
        primary_source: str = PRIMARY_SOURCE,
        primary_source_bonus: int = PRIMARY_SOURCE_BONUS,
        extra_feeds: Optional[Dict[str, str]] = None,
        sources: Optional[Sequence[Union[str, Dict[str, Any], ResolvedNewsSource]]] = None,
        **config: Any,
    ) -> None:
        super().__init__(
            favorite_teams=favorite_teams,
            max_articles=max_articles,
            sources=sources,
            mode=mode,
            primary_source=primary_source or self.PRIMARY_SOURCE,
            primary_source_bonus=primary_source_bonus,
            extra_feeds=extra_feeds,
            sport="mlb",
            category="mlb",
            default_sheet="mlb_news",
            junk_keywords=self.JUNK_KEYWORDS,
            similarity_threshold=0.68,
            **config,
        )
