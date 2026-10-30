"""MLB.com and multi-source MLB news data provider."""
from typing import Any, Dict, List, Optional, Sequence, Union

from .news_sources import (
    MLB_JUNK_KEYWORDS,
    MLB_TEAM_FEEDS,
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
    DEFAULT_SHEET: str = "mlb_news"
    DEFAULT_CATEGORY: str = "mlb"

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
            sport="mlb",
            category="mlb",
            default_sheet="mlb_news",
            junk_keywords=self.JUNK_KEYWORDS,
            similarity_threshold=0.68,
            **config,
        )
