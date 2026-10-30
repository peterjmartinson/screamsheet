"""NFL news data provider using ESPN NFL News API and secondary RSS feeds."""
from typing import Any, Dict, List, Optional, Sequence, Union

from .news_sources import (
    ESPN_NFL_NEWS_API_URL,
    NFL_JUNK_KEYWORDS,
    ResolvedNewsSource,
    UnifiedNewsProvider,
)


class NFLNewsProvider(UnifiedNewsProvider):
    """
    Data provider for NFL news via ESPN API, NFL.com, and secondary RSS feeds.
    """

    DEFAULT_SHEET: str = "nfl_news"
    DEFAULT_CATEGORY: str = "nfl"

    JUNK_KEYWORDS: List[str] = NFL_JUNK_KEYWORDS
    _NEWS_API_URL: str = ESPN_NFL_NEWS_API_URL

    def __init__(
        self,
        favorite_teams: Optional[List[str]] = None,
        max_articles: int = 4,
        sources: Optional[Sequence[Union[str, Dict[str, Any], ResolvedNewsSource]]] = None,
        **config: Any,
    ) -> None:
        super().__init__(
            favorite_teams=favorite_teams,
            max_articles=max_articles,
            sources=sources,
            sport="nfl",
            category="nfl",
            default_sheet="nfl_news",
            junk_keywords=self.JUNK_KEYWORDS,
            similarity_threshold=0.68,
            use_requests_for_rss=True,
            min_summary_chars_before_scrape=150,
            **config,
        )
