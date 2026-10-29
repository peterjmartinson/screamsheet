"""NHL.com and multi-source NHL news data provider."""
from datetime import timedelta
from typing import Any, Dict, List, Optional, Sequence, Union

from .news_sources import (
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

    DEFAULT_SHEET: str = "nhl_news"
    DEFAULT_CATEGORY: str = "nhl"

    TEAM_FEEDS: Dict[Optional[str], str] = NHL_TEAM_FEEDS
    JUNK_KEYWORDS: List[str] = NHL_JUNK_KEYWORDS

    _NEWS_PAGE_URL: str = "https://www.nhl.com/news"
    _RECENT_WINDOW: timedelta = timedelta(days=1)

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
            sport="nhl",
            category="nhl",
            default_sheet="nhl_news",
            junk_keywords=self.JUNK_KEYWORDS,
            similarity_threshold=0.68,
            use_requests_for_rss=True,
            **config,
        )
