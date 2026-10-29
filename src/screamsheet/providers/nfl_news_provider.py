"""NFL news data provider using ESPN NFL News API and secondary RSS feeds."""
from typing import Any, Dict, List, Optional, Sequence, Union

from .news_sources import (
    ESPN_NFL_NEWS_API_URL,
    NEWS_SOURCE_CATALOG,
    NFL_JUNK_KEYWORDS,
    ResolvedNewsSource,
    UnifiedNewsProvider,
)


class NFLNewsProvider(UnifiedNewsProvider):
    """
    Data provider for NFL news via ESPN API, NFL.com, and secondary RSS feeds.
    """

    PRIMARY_SOURCE: str = "NFL.com"
    PRIMARY_SOURCE_BONUS: int = 25
    DEFAULT_SHEET: str = "nfl_news"
    DEFAULT_CATEGORY: str = "nfl"

    SECONDARY_FEEDS: Dict[str, str] = {
        spec.name: spec.url
        for spec in NEWS_SOURCE_CATALOG.values()
        if spec.category == "nfl" and spec.kind == "rss"
    }

    JUNK_KEYWORDS: List[str] = NFL_JUNK_KEYWORDS
    _NEWS_API_URL: str = ESPN_NFL_NEWS_API_URL

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
        self.secondary_feeds: Dict[str, str] = (
            dict(extra_feeds) if extra_feeds is not None else dict(self.SECONDARY_FEEDS)
        )
        super().__init__(
            favorite_teams=favorite_teams,
            max_articles=max_articles,
            sources=sources,
            mode=mode,
            primary_source=primary_source,
            primary_source_bonus=primary_source_bonus,
            extra_feeds=extra_feeds,
            sport="nfl",
            category="nfl",
            default_sheet="nfl_news",
            junk_keywords=self.JUNK_KEYWORDS,
            similarity_threshold=0.68,
            use_requests_for_rss=True,
            min_summary_chars_before_scrape=150,
            replace_secondary_with_extra=True,
            **config,
        )
