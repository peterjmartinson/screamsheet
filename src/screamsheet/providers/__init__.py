"""Data providers for different sports and news sources."""
from .mlb_provider import MLBDataProvider
from .nhl_provider import NHLDataProvider
from .nfl_provider import NFLDataProvider
from .nba_provider import NBADataProvider
from .mlb_trade_rumors_provider import MLBTradeRumorsProvider
from .mlb_news_rss_provider import MLBNewsRssProvider
from .nhl_news_rss_provider import NHLNewsRssProvider
from .nfl_news_provider import NFLNewsProvider
from .political_news_provider import (
    PoliticalNewsProvider,
    PoliticalRSSProvider,
    WhiteHouseProvider,
)
from .news_sources import (
    DEFAULT_SHEET_SOURCES,
    NEWS_SOURCE_CATALOG,
    NewsSourceSpec,
    ResolvedNewsSource,
    UnifiedNewsProvider,
    resolve_news_sources,
)
from .weather_provider import WeatherProvider

__all__ = [
    "MLBDataProvider",
    "NHLDataProvider",
    "NFLDataProvider",
    "NBADataProvider",
    "MLBTradeRumorsProvider",
    "MLBNewsRssProvider",
    "NHLNewsRssProvider",
    "NFLNewsProvider",
    "PoliticalNewsProvider",
    "PoliticalRSSProvider",
    "WhiteHouseProvider",
    "UnifiedNewsProvider",
    "NEWS_SOURCE_CATALOG",
    "NewsSourceSpec",
    "ResolvedNewsSource",
    "DEFAULT_SHEET_SOURCES",
    "resolve_news_sources",
    "WeatherProvider",
]
