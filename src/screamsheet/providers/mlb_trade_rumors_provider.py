"""MLB Trade Rumors data provider for fetching news articles."""
from typing import Any, Dict, List, Optional, Sequence, Union
import feedparser  # type: ignore[import-untyped]

from .news_sources import (
    MLB_TRADE_RUMORS_JUNK_KEYWORDS,
    NEWS_SOURCE_CATALOG,
    ResolvedNewsSource,
    UnifiedNewsProvider,
)


class MLBTradeRumorsProvider(UnifiedNewsProvider):
    """
    Data provider for MLB Trade Rumors news via RSS feed (and optional extra sources).

    Provides access to:
    - News articles from MLB Trade Rumors (and any cherry-picked catalog sources)
    - Filtered and prioritized by favorite teams (using team names and aliases)
    """

    RSS_URL: str = NEWS_SOURCE_CATALOG["mlb_trade_rumors"].url
    EXCLUSION_KEYWORDS: List[str] = MLB_TRADE_RUMORS_JUNK_KEYWORDS

    PRIMARY_SOURCE: str = "MLB Trade Rumors"
    PRIMARY_SOURCE_BONUS: int = 0
    DEFAULT_SHEET: str = "mlb_trade_rumors"
    DEFAULT_CATEGORY: str = "mlb"
    SIMILARITY_THRESHOLD: float = 0.75

    def __init__(
        self,
        favorite_teams: Optional[List[str]] = None,
        max_articles: int = 4,
        mode: str = "single",
        primary_source: str = PRIMARY_SOURCE,
        primary_source_bonus: int = PRIMARY_SOURCE_BONUS,
        extra_feeds: Optional[Dict[str, str]] = None,
        sources: Optional[Sequence[Union[str, Dict[str, Any], ResolvedNewsSource]]] = None,
        **config: Any,
    ) -> None:
        self.secondary_feeds: Dict[str, str] = dict(extra_feeds) if extra_feeds else {}
        super().__init__(
            favorite_teams=favorite_teams,
            max_articles=max_articles,
            sources=sources,
            mode=mode,
            primary_source=primary_source,
            primary_source_bonus=primary_source_bonus,
            extra_feeds=extra_feeds,
            sport="mlb",
            category="mlb",
            default_sheet="mlb_trade_rumors",
            junk_keywords=self.EXCLUSION_KEYWORDS,
            similarity_threshold=0.75,
            check_summary_for_junk=True,
            **config,
        )

    def _parse_rss_feed(self, url_or_text: str) -> Any:
        """Use module-level feedparser so unit test patches on mlb_trade_rumors_provider.feedparser.parse intercept calls."""
        return feedparser.parse(url_or_text)

    def _get_active_sources(self) -> List[ResolvedNewsSource]:
        active = super()._get_active_sources()
        if not self._has_custom_sources:
            for src in active:
                if src.id == "mlb_trade_rumors":
                    src.url = self.RSS_URL
                    src.name = self.primary_source
        return active
