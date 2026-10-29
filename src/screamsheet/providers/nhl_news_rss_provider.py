"""NHL.com and multi-source NHL news data provider."""
from datetime import timedelta
from typing import Any, Dict, List, Optional, Sequence, Union

from .news_sources import (
    NEWS_SOURCE_CATALOG,
    NHL_JUNK_KEYWORDS,
    NHL_TEAM_FEEDS,
    ResolvedNewsSource,
    UnifiedNewsProvider,
)


class NHLNewsRssProvider(UnifiedNewsProvider):
    """
    Data provider for NHL news via NHL.com pages and secondary RSS feeds.

    Fetches articles from NHL.com (primary source) and secondary outlets,
    scores all candidates with an authority bonus for NHL.com and heavy
    favorite-team tier boosts, and clusters stories across outlets.
    """

    PRIMARY_SOURCE: str = "NHL.com"
    PRIMARY_SOURCE_BONUS: int = 25
    DEFAULT_SHEET: str = "nhl_news"
    DEFAULT_CATEGORY: str = "nhl"

    SECONDARY_FEEDS: Dict[str, str] = {
        spec.name: spec.url
        for spec in NEWS_SOURCE_CATALOG.values()
        if spec.category == "nhl" and spec.kind == "rss"
    }

    TEAM_FEEDS: Dict[Optional[str], str] = NHL_TEAM_FEEDS
    JUNK_KEYWORDS: List[str] = NHL_JUNK_KEYWORDS

    _NEWS_PAGE_URL: str = "https://www.nhl.com/news"
    _RECENT_WINDOW: timedelta = timedelta(days=1)

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
            sport="nhl",
            category="nhl",
            default_sheet="nhl_news",
            junk_keywords=self.JUNK_KEYWORDS,
            similarity_threshold=0.68,
            use_requests_for_rss=True,
            replace_secondary_with_extra=True,
            **config,
        )
