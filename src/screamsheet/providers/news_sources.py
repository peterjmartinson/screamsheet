"""Central catalog of news sources and unified news provider for Screamsheet.

All RSS feeds, HTML scrapers, and JSON news APIs across MLB, NHL, NFL, and
Presidential/Political screamsheets are registered here in
:data:`NEWS_SOURCE_CATALOG`.

Individual screamsheets or custom order components can cherry-pick any
combination of sources and assign per-source authority bonuses via the
``sources`` configuration list:

.. code-block:: yaml

    sources:
      - id: mlb_com
        bonus: 25
      - espn_mlb
      - fangraphs
      - mlb_trade_rumors
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Set, Union
from unittest.mock import MagicMock
from urllib.parse import urljoin

import feedparser  # type: ignore[import-untyped]
import requests
from bs4 import BeautifulSoup

from ..base import NewsDataProvider

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Team Feed Maps & Junk Keyword Lists
# ---------------------------------------------------------------------------

MLB_TEAM_FEEDS: Dict[Optional[str], str] = {
    # General
    None: "https://www.mlb.com/feeds/news/rss.xml",
    # All 30 MLB teams (short names, slugs, and aliases)
    "Angels": "https://www.mlb.com/angels/feeds/news/rss.xml",
    "angels": "https://www.mlb.com/angels/feeds/news/rss.xml",
    "Los Angeles Angels": "https://www.mlb.com/angels/feeds/news/rss.xml",
    "D-backs": "https://www.mlb.com/dbacks/feeds/news/rss.xml",
    "Diamondbacks": "https://www.mlb.com/dbacks/feeds/news/rss.xml",
    "dbacks": "https://www.mlb.com/dbacks/feeds/news/rss.xml",
    "Arizona Diamondbacks": "https://www.mlb.com/dbacks/feeds/news/rss.xml",
    "Orioles": "https://www.mlb.com/orioles/feeds/news/rss.xml",
    "orioles": "https://www.mlb.com/orioles/feeds/news/rss.xml",
    "Baltimore Orioles": "https://www.mlb.com/orioles/feeds/news/rss.xml",
    "Red Sox": "https://www.mlb.com/redsox/feeds/news/rss.xml",
    "RedSox": "https://www.mlb.com/redsox/feeds/news/rss.xml",
    "redsox": "https://www.mlb.com/redsox/feeds/news/rss.xml",
    "Boston Red Sox": "https://www.mlb.com/redsox/feeds/news/rss.xml",
    "Cubs": "https://www.mlb.com/cubs/feeds/news/rss.xml",
    "cubs": "https://www.mlb.com/cubs/feeds/news/rss.xml",
    "Chicago Cubs": "https://www.mlb.com/cubs/feeds/news/rss.xml",
    "Reds": "https://www.mlb.com/reds/feeds/news/rss.xml",
    "reds": "https://www.mlb.com/reds/feeds/news/rss.xml",
    "Cincinnati Reds": "https://www.mlb.com/reds/feeds/news/rss.xml",
    "Guardians": "https://www.mlb.com/guardians/feeds/news/rss.xml",
    "guardians": "https://www.mlb.com/guardians/feeds/news/rss.xml",
    "Cleveland Guardians": "https://www.mlb.com/guardians/feeds/news/rss.xml",
    "Rockies": "https://www.mlb.com/rockies/feeds/news/rss.xml",
    "rockies": "https://www.mlb.com/rockies/feeds/news/rss.xml",
    "Colorado Rockies": "https://www.mlb.com/rockies/feeds/news/rss.xml",
    "Tigers": "https://www.mlb.com/tigers/feeds/news/rss.xml",
    "tigers": "https://www.mlb.com/tigers/feeds/news/rss.xml",
    "Detroit Tigers": "https://www.mlb.com/tigers/feeds/news/rss.xml",
    "Astros": "https://www.mlb.com/astros/feeds/news/rss.xml",
    "astros": "https://www.mlb.com/astros/feeds/news/rss.xml",
    "Houston Astros": "https://www.mlb.com/astros/feeds/news/rss.xml",
    "Royals": "https://www.mlb.com/royals/feeds/news/rss.xml",
    "royals": "https://www.mlb.com/royals/feeds/news/rss.xml",
    "Kansas City Royals": "https://www.mlb.com/royals/feeds/news/rss.xml",
    "Dodgers": "https://www.mlb.com/dodgers/feeds/news/rss.xml",
    "dodgers": "https://www.mlb.com/dodgers/feeds/news/rss.xml",
    "Los Angeles Dodgers": "https://www.mlb.com/dodgers/feeds/news/rss.xml",
    "Nationals": "https://www.mlb.com/nationals/feeds/news/rss.xml",
    "nationals": "https://www.mlb.com/nationals/feeds/news/rss.xml",
    "Washington Nationals": "https://www.mlb.com/nationals/feeds/news/rss.xml",
    "Mets": "https://www.mlb.com/mets/feeds/news/rss.xml",
    "mets": "https://www.mlb.com/mets/feeds/news/rss.xml",
    "New York Mets": "https://www.mlb.com/mets/feeds/news/rss.xml",
    "Athletics": "https://www.mlb.com/athletics/feeds/news/rss.xml",
    "athletics": "https://www.mlb.com/athletics/feeds/news/rss.xml",
    "Oakland Athletics": "https://www.mlb.com/athletics/feeds/news/rss.xml",
    "Pirates": "https://www.mlb.com/pirates/feeds/news/rss.xml",
    "pirates": "https://www.mlb.com/pirates/feeds/news/rss.xml",
    "Pittsburgh Pirates": "https://www.mlb.com/pirates/feeds/news/rss.xml",
    "Padres": "https://www.mlb.com/padres/feeds/news/rss.xml",
    "padres": "https://www.mlb.com/padres/feeds/news/rss.xml",
    "San Diego Padres": "https://www.mlb.com/padres/feeds/news/rss.xml",
    "Mariners": "https://www.mlb.com/mariners/feeds/news/rss.xml",
    "mariners": "https://www.mlb.com/mariners/feeds/news/rss.xml",
    "Seattle Mariners": "https://www.mlb.com/mariners/feeds/news/rss.xml",
    "Giants": "https://www.mlb.com/giants/feeds/news/rss.xml",
    "giants": "https://www.mlb.com/giants/feeds/news/rss.xml",
    "San Francisco Giants": "https://www.mlb.com/giants/feeds/news/rss.xml",
    "Cardinals": "https://www.mlb.com/cardinals/feeds/news/rss.xml",
    "cardinals": "https://www.mlb.com/cardinals/feeds/news/rss.xml",
    "St. Louis Cardinals": "https://www.mlb.com/cardinals/feeds/news/rss.xml",
    "Rays": "https://www.mlb.com/rays/feeds/news/rss.xml",
    "rays": "https://www.mlb.com/rays/feeds/news/rss.xml",
    "Tampa Bay Rays": "https://www.mlb.com/rays/feeds/news/rss.xml",
    "Rangers": "https://www.mlb.com/rangers/feeds/news/rss.xml",
    "rangers": "https://www.mlb.com/rangers/feeds/news/rss.xml",
    "Texas Rangers": "https://www.mlb.com/rangers/feeds/news/rss.xml",
    "Blue Jays": "https://www.mlb.com/bluejays/feeds/news/rss.xml",
    "BlueJays": "https://www.mlb.com/bluejays/feeds/news/rss.xml",
    "bluejays": "https://www.mlb.com/bluejays/feeds/news/rss.xml",
    "Toronto Blue Jays": "https://www.mlb.com/bluejays/feeds/news/rss.xml",
    "Twins": "https://www.mlb.com/twins/feeds/news/rss.xml",
    "twins": "https://www.mlb.com/twins/feeds/news/rss.xml",
    "Minnesota Twins": "https://www.mlb.com/twins/feeds/news/rss.xml",
    "Phillies": "https://www.mlb.com/phillies/feeds/news/rss.xml",
    "phillies": "https://www.mlb.com/phillies/feeds/news/rss.xml",
    "Philadelphia Phillies": "https://www.mlb.com/phillies/feeds/news/rss.xml",
    "Braves": "https://www.mlb.com/braves/feeds/news/rss.xml",
    "braves": "https://www.mlb.com/braves/feeds/news/rss.xml",
    "Atlanta Braves": "https://www.mlb.com/braves/feeds/news/rss.xml",
    "White Sox": "https://www.mlb.com/whitesox/feeds/news/rss.xml",
    "WhiteSox": "https://www.mlb.com/whitesox/feeds/news/rss.xml",
    "whitesox": "https://www.mlb.com/whitesox/feeds/news/rss.xml",
    "Chicago White Sox": "https://www.mlb.com/whitesox/feeds/news/rss.xml",
    "Marlins": "https://www.mlb.com/marlins/feeds/news/rss.xml",
    "marlins": "https://www.mlb.com/marlins/feeds/news/rss.xml",
    "Miami Marlins": "https://www.mlb.com/marlins/feeds/news/rss.xml",
    "Yankees": "https://www.mlb.com/yankees/feeds/news/rss.xml",
    "yankees": "https://www.mlb.com/yankees/feeds/news/rss.xml",
    "New York Yankees": "https://www.mlb.com/yankees/feeds/news/rss.xml",
    "Brewers": "https://www.mlb.com/brewers/feeds/news/rss.xml",
    "brewers": "https://www.mlb.com/brewers/feeds/news/rss.xml",
    "Milwaukee Brewers": "https://www.mlb.com/brewers/feeds/news/rss.xml",
}

NHL_TEAM_FEEDS: Dict[Optional[str], str] = {
    "Ducks": "https://www.nhl.com/anaheimducks/rss/news.xml",
    "Bruins": "https://www.nhl.com/bostonbruins/rss/news.xml",
    "Sabres": "https://www.nhl.com/buffalosabres/rss/news.xml",
    "Flames": "https://www.nhl.com/calgaryflames/rss/news.xml",
    "Hurricanes": "https://www.nhl.com/carolinahurricanes/rss/news.xml",
    "Blackhawks": "https://www.nhl.com/chicagoblackhawks/rss/news.xml",
    "Avalanche": "https://www.nhl.com/coloradoavalanche/rss/news.xml",
    "Blue Jackets": "https://www.nhl.com/columbusbluejackets/rss/news.xml",
    "Stars": "https://www.nhl.com/dallasstars/rss/news.xml",
    "Red Wings": "https://www.nhl.com/detroitredwings/rss/news.xml",
    "Oilers": "https://www.nhl.com/edmontonoilers/rss/news.xml",
    "Panthers": "https://www.nhl.com/floridapanthers/rss/news.xml",
    "Kings": "https://www.nhl.com/losangeleskings/rss/news.xml",
    "Wild": "https://www.nhl.com/minnesotawild/rss/news.xml",
    "Canadiens": "https://www.nhl.com/montrealcanadiens/rss/news.xml",
    "Predators": "https://www.nhl.com/nashvillepredators/rss/news.xml",
    "Devils": "https://www.nhl.com/newjerseydevils/rss/news.xml",
    "Islanders": "https://www.nhl.com/newyorkislanders/rss/news.xml",
    "Rangers": "https://www.nhl.com/newyorkrangers/rss/news.xml",
    "Senators": "https://www.nhl.com/ottawasenators/rss/news.xml",
    "Flyers": "https://www.nhl.com/philadelphiaflyers/rss/news.xml",
    "Penguins": "https://www.nhl.com/pittsburghpenguins/rss/news.xml",
    "Sharks": "https://www.nhl.com/sanjosesharks/rss/news.xml",
    "Kraken": "https://www.nhl.com/seattlekraken/rss/news.xml",
    "Blues": "https://www.nhl.com/stlouisblues/rss/news.xml",
    "Lightning": "https://www.nhl.com/tampabaylightning/rss/news.xml",
    "Maple Leafs": "https://www.nhl.com/torontomapleleafs/rss/news.xml",
    "Utah Hockey Club": "https://www.nhl.com/utahhockeyclub/rss/news.xml",
    "Canucks": "https://www.nhl.com/vancouvercanucks/rss/news.xml",
    "Golden Knights": "https://www.nhl.com/vegasgoldenknights/rss/news.xml",
    "Capitals": "https://www.nhl.com/washingtoncapitals/rss/news.xml",
    "Jets": "https://www.nhl.com/winnipegjets/rss/news.xml",
    None: "https://www.nhl.com/news",
}

MLB_JUNK_KEYWORDS: List[str] = [
    "Spring Breakout",
    "stream games",
    "prospects",
]

MLB_TRADE_RUMORS_JUNK_KEYWORDS: List[str] = [
    "Top 50",
    "Contest",
    "Prediction",
    "Subscribers",
    "Email List",
    "Presents Our",
    "Podcast",
    "Live Chat",
    "Q&A",
    "Ask Us Anything",
    "Best of",
    "MLBTR Chat",
    "Front Office",
    "Prospects",
]

NHL_JUNK_KEYWORDS: List[str] = [
    "stream games",
    "fantasy",
]

NFL_JUNK_KEYWORDS: List[str] = [
    "betting",
    "how to bet",
    "prop bet",
    "odds, tips",
    "stream games",
    "fantasy football",
    "prospects",
]

ESPN_NFL_NEWS_API_URL: str = (
    "http://site.api.espn.com/apis/site/v2/sports/football/nfl/news"
)

WHITE_HOUSE_URL: str = "https://www.whitehouse.gov/news/"

WHITE_HOUSE_SELECTOR_CHAIN: List[Dict[str, str]] = [
    {
        "container": "li.wp-block-post",
        "headline": "h2.wp-block-post-title a",
        "date": "div.wp-block-post-date time",
        "summary": "",
    },
    {
        "container": "article",
        "headline": "h2 a",
        "date": "time",
        "summary": "p",
    },
    {
        "container": "li.news-item",
        "headline": "a.news-item__title",
        "date": "time",
        "summary": "",
    },
]

POLITICAL_RSS_SOURCES: Dict[str, str] = {
    "The Guardian": "https://www.theguardian.com/world/rss",
    "Google News": "https://news.google.com/rss/headlines/section/topic/NATION.en_US?hl=en-US&gl=US&ceid=US:en",
    "BBC": "https://feeds.bbci.co.uk/news/rss.xml",
    "NYT": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "Politico": "https://rss.politico.com/congress.xml",
    "NPR": "https://feeds.npr.org/1001/rss.xml",
    "Washington Post": "https://feeds.washingtonpost.com/rss/national",
}


# ---------------------------------------------------------------------------
# Source Catalog Definitions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NewsSourceSpec:
    """Immutable specification of a news source in the central catalog."""

    id: str
    name: str
    category: str  # "mlb", "nhl", "nfl", "political"
    kind: str  # "rss", "mlb_team_rss", "nhl_html", "espn_api", "white_house_html"
    url: str = ""
    default_bonus: int = 0
    team_feeds: Optional[Dict[Optional[str], str]] = None


@dataclass
class ResolvedNewsSource:
    """A concrete news source instance with an active authority bonus."""

    id: str
    name: str
    category: str
    kind: str
    url: str
    bonus: int = 0
    team_feeds: Optional[Dict[Optional[str], str]] = None


NEWS_SOURCE_CATALOG: Dict[str, NewsSourceSpec] = {
    # --- MLB ---
    "mlb_com": NewsSourceSpec(
        id="mlb_com",
        name="MLB.com",
        category="mlb",
        kind="mlb_team_rss",
        url=MLB_TEAM_FEEDS[None],
        default_bonus=25,
        team_feeds=MLB_TEAM_FEEDS,
    ),
    "espn_mlb": NewsSourceSpec(
        id="espn_mlb",
        name="ESPN",
        category="mlb",
        kind="rss",
        url="https://www.espn.com/espn/rss/mlb/news",
        default_bonus=0,
    ),
    "cbs_mlb": NewsSourceSpec(
        id="cbs_mlb",
        name="CBS Sports",
        category="mlb",
        kind="rss",
        url="https://www.cbssports.com/rss/headlines/mlb/",
        default_bonus=0,
    ),
    "yahoo_mlb": NewsSourceSpec(
        id="yahoo_mlb",
        name="Yahoo Sports",
        category="mlb",
        kind="rss",
        url="https://sports.yahoo.com/mlb/rss.xml",
        default_bonus=0,
    ),
    "mlb_trade_rumors": NewsSourceSpec(
        id="mlb_trade_rumors",
        name="MLB Trade Rumors",
        category="mlb",
        kind="rss",
        url="https://feeds.feedburner.com/MlbTradeRumors",
        default_bonus=0,
    ),
    "fangraphs": NewsSourceSpec(
        id="fangraphs",
        name="FanGraphs",
        category="mlb",
        kind="rss",
        url="https://blogs.fangraphs.com/feed/",
        default_bonus=0,
    ),
    "fox_mlb": NewsSourceSpec(
        id="fox_mlb",
        name="Fox Sports",
        category="mlb",
        kind="rss",
        url="https://api.foxsports.com/v2/content/optimized-rss?partnerKey=MB0Wehpmuj2lUhuRhQaafhBjAJqaPU244mlTDK1i&size=30&tags=fs/mlb",
        default_bonus=0,
    ),
    # --- NHL ---
    "nhl_com": NewsSourceSpec(
        id="nhl_com",
        name="NHL.com",
        category="nhl",
        kind="nhl_html",
        url="https://www.nhl.com/news",
        default_bonus=25,
        team_feeds=NHL_TEAM_FEEDS,
    ),
    "espn_nhl": NewsSourceSpec(
        id="espn_nhl",
        name="ESPN",
        category="nhl",
        kind="rss",
        url="https://www.espn.com/espn/rss/nhl/news",
        default_bonus=0,
    ),
    "cbs_nhl": NewsSourceSpec(
        id="cbs_nhl",
        name="CBS Sports",
        category="nhl",
        kind="rss",
        url="https://www.cbssports.com/rss/headlines/nhl/",
        default_bonus=0,
    ),
    "yahoo_nhl": NewsSourceSpec(
        id="yahoo_nhl",
        name="Yahoo Sports",
        category="nhl",
        kind="rss",
        url="https://sports.yahoo.com/nhl/rss.xml",
        default_bonus=0,
    ),
    "pro_hockey_rumors": NewsSourceSpec(
        id="pro_hockey_rumors",
        name="ProHockeyRumors",
        category="nhl",
        kind="rss",
        url="https://www.prohockeyrumors.com/feed",
        default_bonus=0,
    ),
    "the_hockey_news": NewsSourceSpec(
        id="the_hockey_news",
        name="The Hockey News",
        category="nhl",
        kind="rss",
        url="https://thehockeynews.com/.rss/full/",
        default_bonus=0,
    ),
    "sportsnet_nhl": NewsSourceSpec(
        id="sportsnet_nhl",
        name="Sportsnet",
        category="nhl",
        kind="rss",
        url="https://www.sportsnet.ca/hockey/nhl/feed/",
        default_bonus=0,
    ),
    # --- NFL ---
    "espn_nfl": NewsSourceSpec(
        id="espn_nfl",
        name="ESPN",
        category="nfl",
        kind="espn_api",
        url=ESPN_NFL_NEWS_API_URL,
        default_bonus=0,
    ),
    "nfl_com": NewsSourceSpec(
        id="nfl_com",
        name="NFL.com",
        category="nfl",
        kind="rss",
        url="https://www.nfl.com/rss/rsslanding?searchString=home",
        default_bonus=25,
    ),
    "pro_football_talk": NewsSourceSpec(
        id="pro_football_talk",
        name="ProFootballTalk",
        category="nfl",
        kind="rss",
        url="https://profootballtalk.nbcsports.com/feed/",
        default_bonus=0,
    ),
    "cbs_nfl": NewsSourceSpec(
        id="cbs_nfl",
        name="CBS Sports",
        category="nfl",
        kind="rss",
        url="https://www.cbssports.com/rss/headlines/nfl/",
        default_bonus=0,
    ),
    "yahoo_nfl": NewsSourceSpec(
        id="yahoo_nfl",
        name="Yahoo Sports",
        category="nfl",
        kind="rss",
        url="https://sports.yahoo.com/nfl/rss.xml",
        default_bonus=0,
    ),
    "nfl_trade_rumors": NewsSourceSpec(
        id="nfl_trade_rumors",
        name="NFL Trade Rumors",
        category="nfl",
        kind="rss",
        url="https://nfltraderumors.co/feed/",
        default_bonus=0,
    ),
    "fox_nfl": NewsSourceSpec(
        id="fox_nfl",
        name="Fox Sports",
        category="nfl",
        kind="rss",
        url="https://api.foxsports.com/v2/content/optimized-rss?partnerKey=MB0Wehpmuj2lUhuRhQaafhBjAJqaPU244mlTDK1i&size=30&tags=fs/nfl",
        default_bonus=0,
    ),
    # --- Political / Presidential ---
    "white_house": NewsSourceSpec(
        id="white_house",
        name="White House",
        category="political",
        kind="white_house_html",
        url=WHITE_HOUSE_URL,
        default_bonus=25,
    ),
    "the_guardian": NewsSourceSpec(
        id="the_guardian",
        name="The Guardian",
        category="political",
        kind="rss",
        url="https://www.theguardian.com/world/rss",
        default_bonus=0,
    ),
    "google_news": NewsSourceSpec(
        id="google_news",
        name="Google News",
        category="political",
        kind="rss",
        url="https://news.google.com/rss/headlines/section/topic/NATION.en_US?hl=en-US&gl=US&ceid=US:en",
        default_bonus=0,
    ),
    "bbc": NewsSourceSpec(
        id="bbc",
        name="BBC",
        category="political",
        kind="rss",
        url="https://feeds.bbci.co.uk/news/rss.xml",
        default_bonus=0,
    ),
    "nyt": NewsSourceSpec(
        id="nyt",
        name="NYT",
        category="political",
        kind="rss",
        url="https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
        default_bonus=0,
    ),
    "politico": NewsSourceSpec(
        id="politico",
        name="Politico",
        category="political",
        kind="rss",
        url="https://rss.politico.com/congress.xml",
        default_bonus=0,
    ),
    "npr": NewsSourceSpec(
        id="npr",
        name="NPR",
        category="political",
        kind="rss",
        url="https://feeds.npr.org/1001/rss.xml",
        default_bonus=0,
    ),
    "washington_post": NewsSourceSpec(
        id="washington_post",
        name="Washington Post",
        category="political",
        kind="rss",
        url="https://feeds.washingtonpost.com/rss/national",
        default_bonus=0,
    ),
}


DEFAULT_SHEET_SOURCES: Dict[str, List[Union[str, Dict[str, Any]]]] = {
    "mlb_news": [
        {"id": "mlb_com", "bonus": 25},
        "espn_mlb",
        "cbs_mlb",
        "yahoo_mlb",
        "mlb_trade_rumors",
        "fangraphs",
        "fox_mlb",
    ],
    "mlb_trade_rumors": [
        {"id": "mlb_trade_rumors", "bonus": 0},
    ],
    "nhl_news": [
        {"id": "nhl_com", "bonus": 25},
        "espn_nhl",
        "cbs_nhl",
        "yahoo_nhl",
        "pro_hockey_rumors",
        "the_hockey_news",
        "sportsnet_nhl",
    ],
    "nfl_news": [
        "espn_nfl",
        {"id": "nfl_com", "bonus": 25},
        "pro_football_talk",
        "cbs_nfl",
        "yahoo_nfl",
        "nfl_trade_rumors",
        "fox_nfl",
    ],
    "presidential": [
        {"id": "white_house", "bonus": 25},
        "the_guardian",
        "google_news",
        "bbc",
        "nyt",
        "politico",
        "npr",
        "washington_post",
    ],
}

SINGLE_MODE_SHEET_SOURCES: Dict[str, List[Union[str, Dict[str, Any]]]] = {
    "mlb_news": [{"id": "mlb_com", "bonus": 25}],
    "mlb_trade_rumors": [{"id": "mlb_trade_rumors", "bonus": 0}],
    "nhl_news": [{"id": "nhl_com", "bonus": 25}],
    "nfl_news": ["espn_nfl"],
    "presidential": [{"id": "white_house", "bonus": 25}],
}


def lookup_source_spec(
    key: str, category: Optional[str] = None
) -> Optional[NewsSourceSpec]:
    """Find a :class:`NewsSourceSpec` by ID or display name."""
    cleaned = key.strip()
    if not cleaned:
        return None

    low = cleaned.lower()
    if low in NEWS_SOURCE_CATALOG:
        return NEWS_SOURCE_CATALOG[low]

    # Try category-scoped ID suffix (e.g., "espn" + category="mlb" -> "espn_mlb")
    if category:
        cat_id = f"{low}_{category.lower()}"
        if cat_id in NEWS_SOURCE_CATALOG:
            return NEWS_SOURCE_CATALOG[cat_id]

    # Match by display name within the requested category first
    if category:
        for spec in NEWS_SOURCE_CATALOG.values():
            if spec.category == category.lower() and spec.name.lower() == low:
                return spec

    # Match by display name globally
    for spec in NEWS_SOURCE_CATALOG.values():
        if spec.name.lower() == low:
            return spec

    return None


def resolve_news_sources(
    sources: Optional[Sequence[Union[str, Dict[str, Any], ResolvedNewsSource]]] = None,
    default_sheet: str = "mlb_news",
    category: Optional[str] = None,
    mode: str = "multi",
    primary_source: Optional[str] = None,
    primary_source_bonus: Optional[int] = None,
    extra_feeds: Optional[Dict[str, str]] = None,
    replace_secondary_with_extra: bool = False,
) -> List[ResolvedNewsSource]:
    """Normalize a user-supplied ``sources`` list or legacy parameters into :class:`ResolvedNewsSource` items.

    Supports:
    - String catalog IDs: ``"espn_mlb"``, ``"mlb_com"``, ``"white_house"``
    - String display names: ``"MLB.com"``, ``"FanGraphs"``
    - Dicts with catalog ID + bonus: ``{"id": "mlb_com", "bonus": 25}``
    - Ad-hoc custom RSS dicts: ``{"name": "Custom", "url": "https://...", "bonus": 10}``
    - Legacy ``mode`` ("single" vs "multi") and ``extra_feeds`` when ``sources`` is omitted.
    """
    mode_clean = (mode or "multi").strip().lower()
    cat = (category or "").strip().lower() or None

    raw_items: Sequence[Union[str, Dict[str, Any], ResolvedNewsSource]]
    explicit_sources = sources is not None and len(sources) > 0

    if explicit_sources:
        raw_items = list(sources)  # type: ignore[arg-type]
    else:
        if mode_clean == "single" and default_sheet in SINGLE_MODE_SHEET_SOURCES:
            raw_items = list(SINGLE_MODE_SHEET_SOURCES[default_sheet])
        else:
            raw_items = list(DEFAULT_SHEET_SOURCES.get(default_sheet, []))

    resolved: List[ResolvedNewsSource] = []

    for item in raw_items:
        if isinstance(item, ResolvedNewsSource):
            resolved.append(item)
            continue

        if isinstance(item, str):
            spec = lookup_source_spec(item, category=cat)
            if spec is not None:
                resolved.append(
                    ResolvedNewsSource(
                        id=spec.id,
                        name=spec.name,
                        category=spec.category,
                        kind=spec.kind,
                        url=spec.url,
                        bonus=spec.default_bonus,
                        team_feeds=spec.team_feeds,
                    )
                )
            elif item.startswith(("http://", "https://")):
                resolved.append(
                    ResolvedNewsSource(
                        id=item,
                        name=item,
                        category=cat or "custom",
                        kind="rss",
                        url=item,
                        bonus=0,
                    )
                )
            else:
                logger.warning("Unknown news source ID '%s' ignored.", item)
            continue

        if isinstance(item, dict):
            raw_id = str(
                item.get("id") or item.get("source") or item.get("name") or ""
            ).strip()
            custom_url = str(item.get("url") or "").strip()
            raw_bonus = item.get("bonus", item.get("weight"))
            spec = lookup_source_spec(raw_id, category=cat) if raw_id else None

            if spec is not None and not custom_url:
                bonus_val = (
                    int(raw_bonus)
                    if raw_bonus is not None
                    else spec.default_bonus
                )
                resolved.append(
                    ResolvedNewsSource(
                        id=spec.id,
                        name=str(item.get("name") or spec.name),
                        category=spec.category,
                        kind=spec.kind,
                        url=spec.url,
                        bonus=bonus_val,
                        team_feeds=spec.team_feeds,
                    )
                )
            elif custom_url:
                name_val = str(item.get("name") or item.get("id") or custom_url)
                bonus_val = int(raw_bonus) if raw_bonus is not None else 0
                resolved.append(
                    ResolvedNewsSource(
                        id=raw_id or name_val.lower().replace(" ", "_"),
                        name=name_val,
                        category=cat or "custom",
                        kind=str(item.get("kind") or "rss"),
                        url=custom_url,
                        bonus=bonus_val,
                    )
                )
            else:
                logger.warning("Invalid news source dict '%s' ignored.", item)

    # Apply legacy extra_feeds when explicit sources were not passed
    if not explicit_sources and mode_clean == "multi" and extra_feeds:
        if replace_secondary_with_extra and resolved:
            # Keep the primary non-RSS source (e.g. nhl_com html or espn_nfl api) and replace secondary RSS feeds
            primary_kept = [
                r for r in resolved if r.kind in ("mlb_team_rss", "nhl_html", "espn_api", "white_house_html")
            ]
            if not primary_kept:
                primary_kept = resolved[:1]
            resolved = primary_kept
            for source_name, feed_url in extra_feeds.items():
                spec = lookup_source_spec(source_name, category=cat)
                bonus_val = spec.default_bonus if spec else 0
                resolved.append(
                    ResolvedNewsSource(
                        id=spec.id if spec else source_name.lower().replace(" ", "_"),
                        name=source_name,
                        category=cat or "custom",
                        kind="rss",
                        url=feed_url,
                        bonus=bonus_val,
                    )
                )
        else:
            existing_names = {r.name.lower(): r for r in resolved}
            for source_name, feed_url in extra_feeds.items():
                if source_name.lower() in existing_names:
                    existing_names[source_name.lower()].url = feed_url
                else:
                    resolved.append(
                        ResolvedNewsSource(
                            id=source_name.lower().replace(" ", "_"),
                            name=source_name,
                            category=cat or "custom",
                            kind="rss",
                            url=feed_url,
                            bonus=0,
                        )
                    )

    # Apply legacy primary_source / primary_source_bonus override if specified
    if primary_source and primary_source_bonus is not None:
        ps_low = primary_source.strip().lower()
        for r in resolved:
            if r.name.lower() == ps_low or r.id.lower() == ps_low:
                r.bonus = int(primary_source_bonus)

    return resolved


# ---------------------------------------------------------------------------
# UnifiedNewsProvider
# ---------------------------------------------------------------------------

class UnifiedNewsProvider(NewsDataProvider):
    """Unified multi-source news provider capable of polling any combination of catalog sources.

    Supports all fetcher types in :data:`NEWS_SOURCE_CATALOG`:
    - ``mlb_team_rss``: MLB.com team-specific RSS feeds + general fallback feed
    - ``nhl_html``: NHL.com team/general news HTML card scraping
    - ``espn_api``: ESPN Site v2 JSON news endpoint
    - ``white_house_html``: White House briefing room HTML scraper
    - ``rss``: Standard RSS/Atom feeds via ``feedparser``
    """

    TEAM_FEEDS: Dict[Optional[str], str] = MLB_TEAM_FEEDS
    JUNK_KEYWORDS: List[str] = MLB_JUNK_KEYWORDS
    PRIMARY_SOURCE: str = "MLB.com"
    PRIMARY_SOURCE_BONUS: int = 25
    DEFAULT_SHEET: str = "mlb_news"
    DEFAULT_CATEGORY: str = "mlb"
    SIMILARITY_THRESHOLD: float = 0.68

    _ARTICLE_SELECTORS: List[str] = [
        "div.article-template__body-text",
        "div.article-template__content",
        "div.bam-content",
        "div.article-detail__body",
        "div.article-detail__content",
        "section.article-summary",
        "div.article-body",
        "section.article-body",
        "div.Story__Body",
        "div.caas-body",
        "div.Article-content",
        "div.entry-content",
        "div.wp-block-post-content",
        "section.entry-content",
        "article",
        "main",
    ]

    _SCRAPE_TIMEOUT: int = 10
    _RECENT_WINDOW: timedelta = timedelta(days=1)
    _SCRAPE_HEADERS: Dict[str, str] = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; screamsheet/1.0; +https://github.com/peterjmartinson/screamsheet)"
        )
    }

    def __init__(
        self,
        favorite_teams: Optional[List[str]] = None,
        max_articles: int = 4,
        sources: Optional[Sequence[Union[str, Dict[str, Any], ResolvedNewsSource]]] = None,
        mode: str = "multi",
        primary_source: Optional[str] = None,
        primary_source_bonus: Optional[int] = None,
        extra_feeds: Optional[Dict[str, str]] = None,
        sport: Optional[str] = None,
        category: Optional[str] = None,
        default_sheet: Optional[str] = None,
        junk_keywords: Optional[List[str]] = None,
        similarity_threshold: Optional[float] = None,
        use_requests_for_rss: bool = False,
        check_summary_for_junk: bool = False,
        min_summary_chars_before_scrape: int = 1,
        replace_secondary_with_extra: bool = False,
        **config: Any,
    ) -> None:
        super().__init__(**config)
        self.favorite_teams: List[str] = list(favorite_teams) if favorite_teams else []
        self.max_articles: int = max_articles
        self.mode: str = (mode or "multi").strip().lower()
        self.category: str = (category or sport or self.DEFAULT_CATEGORY).strip().lower()
        self.sport: str = (sport or (self.category if self.category != "political" else "mlb")).strip().lower()
        self.default_sheet: str = default_sheet or self.DEFAULT_SHEET
        self.primary_source: str = (
            primary_source if primary_source is not None else self.PRIMARY_SOURCE
        )
        self.primary_source_bonus: int = (
            int(primary_source_bonus)
            if primary_source_bonus is not None
            else self.PRIMARY_SOURCE_BONUS
        )
        self.extra_feeds: Dict[str, str] = dict(extra_feeds) if extra_feeds else {}
        if junk_keywords is not None:
            self.JUNK_KEYWORDS = list(junk_keywords)
        self.similarity_threshold: float = (
            similarity_threshold
            if similarity_threshold is not None
            else self.SIMILARITY_THRESHOLD
        )
        self._use_requests_for_rss: bool = use_requests_for_rss
        self._check_summary_for_junk: bool = check_summary_for_junk
        self._min_summary_chars_before_scrape: int = min_summary_chars_before_scrape
        self._replace_secondary_with_extra: bool = replace_secondary_with_extra
        self._has_custom_sources: bool = sources is not None and len(sources) > 0
        self._raw_sources = list(sources) if sources is not None else None
        self._article_cache: Dict[Optional[str], List[Dict]] = {}

        self.resolved_sources: List[ResolvedNewsSource] = resolve_news_sources(
            sources=sources,
            default_sheet=self.default_sheet,
            category=self.category,
            mode=self.mode,
            primary_source=self.primary_source,
            primary_source_bonus=self.primary_source_bonus,
            extra_feeds=self.extra_feeds if self.extra_feeds else None,
            replace_secondary_with_extra=self._replace_secondary_with_extra,
        )

    def _get_active_sources(self) -> List[ResolvedNewsSource]:
        """Return resolved sources, respecting runtime updates to mode or extra_feeds."""
        if self._has_custom_sources:
            return self.resolved_sources
        return resolve_news_sources(
            sources=None,
            default_sheet=self.default_sheet,
            category=self.category,
            mode=self.mode,
            primary_source=self.primary_source,
            primary_source_bonus=self.primary_source_bonus,
            extra_feeds=self.extra_feeds if self.extra_feeds else None,
            replace_secondary_with_extra=self._replace_secondary_with_extra,
        )

    def _get_source_bonuses(self, active_sources: List[ResolvedNewsSource]) -> Dict[str, int]:
        bonuses: Dict[str, int] = {}
        for src in active_sources:
            if src.bonus > 0:
                bonuses[src.name.lower()] = src.bonus
        if self.primary_source and self.primary_source_bonus > 0:
            bonuses.setdefault(self.primary_source.lower(), self.primary_source_bonus)
        return bonuses

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_articles(self) -> List[Dict]:
        """Fetch, score, and cluster articles across all configured sources."""
        active_sources = self._get_active_sources()
        source_bonuses = self._get_source_bonuses(active_sources)
        all_entries: List[Dict[str, Any]] = []
        seen_links: set = set()

        for src in active_sources:
            is_primary = (
                src.bonus > 0
                or (bool(self.primary_source) and src.name.lower() == self.primary_source.lower())
            )
            if src.kind == "mlb_team_rss":
                # 1. Favorite team MLB.com feeds in priority order
                for team in self.favorite_teams:
                    for raw_entry in self._fetch_entries(team):
                        ed = self._raw_to_entry_dict(
                            raw_entry,
                            source_name=self.primary_source if src.id == "mlb_com" else src.name,
                            team_tag=team,
                            is_primary=is_primary,
                            source_bonus=src.bonus,
                        )
                        if ed:
                            all_entries.append(ed)
                # 2. General MLB.com feed
                for raw_entry in self._fetch_entries(None):
                    ed = self._raw_to_entry_dict(
                        raw_entry,
                        source_name=self.primary_source if src.id == "mlb_com" else src.name,
                        is_primary=is_primary,
                        source_bonus=src.bonus,
                    )
                    if ed:
                        all_entries.append(ed)

            elif src.kind == "nhl_html":
                src_label = self.primary_source if src.id == "nhl_com" else src.name
                # 1. Favorite team NHL.com pages
                for team in self.favorite_teams:
                    for raw_entry in self._fetch_nhl_entries(team, team_feeds=src.team_feeds, news_url=src.url):
                        if not self._team_matches_entry(team, raw_entry):
                            continue
                        link = (
                            raw_entry.get("link", "")
                            if hasattr(raw_entry, "get")
                            else getattr(raw_entry, "link", "")
                        )
                        if link and link not in seen_links and not self._is_junk_article(raw_entry):
                            seen_links.add(link)
                            all_entries.append(
                                {
                                    "title": (
                                        raw_entry.get("title", "")
                                        if hasattr(raw_entry, "get")
                                        else getattr(raw_entry, "title", "")
                                    ),
                                    "link": link,
                                    "summary": (
                                        raw_entry.get("summary", "")
                                        if hasattr(raw_entry, "get")
                                        else getattr(raw_entry, "summary", "")
                                    ),
                                    "published_parsed": (
                                        raw_entry.get("published_parsed")
                                        if hasattr(raw_entry, "get")
                                        else getattr(raw_entry, "published_parsed", None)
                                    ),
                                    "source": src_label,
                                    "team_tag": team,
                                    "is_primary_source": is_primary,
                                    "source_bonus": src.bonus,
                                }
                            )
                # 2. General NHL.com page
                for raw_entry in self._fetch_nhl_entries(None, team_feeds=src.team_feeds, news_url=src.url):
                    link = (
                        raw_entry.get("link", "")
                        if hasattr(raw_entry, "get")
                        else getattr(raw_entry, "link", "")
                    )
                    if link and link not in seen_links and not self._is_junk_article(raw_entry):
                        seen_links.add(link)
                        matched_team = next(
                            (t for t in self.favorite_teams if self._team_matches_entry(t, raw_entry)),
                            None,
                        )
                        entry_dict: Dict[str, Any] = {
                            "title": (
                                raw_entry.get("title", "")
                                if hasattr(raw_entry, "get")
                                else getattr(raw_entry, "title", "")
                            ),
                            "link": link,
                            "summary": (
                                raw_entry.get("summary", "")
                                if hasattr(raw_entry, "get")
                                else getattr(raw_entry, "summary", "")
                            ),
                            "published_parsed": (
                                raw_entry.get("published_parsed")
                                if hasattr(raw_entry, "get")
                                else getattr(raw_entry, "published_parsed", None)
                            ),
                            "source": src_label,
                            "is_primary_source": is_primary,
                            "source_bonus": src.bonus,
                        }
                        if matched_team:
                            entry_dict["team_tag"] = matched_team
                        all_entries.append(entry_dict)

            elif src.kind == "espn_api":
                for art in self._fetch_news_articles(api_url=src.url, source_name=src.name):
                    link = art.get("link", "")
                    if not link or link in seen_links or self._is_junk_article(art):
                        continue
                    seen_links.add(link)
                    entry_copy = dict(art)
                    matched_team = self._match_favorite_team(entry_copy)
                    if matched_team:
                        entry_copy["team_tag"] = matched_team
                    entry_copy["is_primary_source"] = is_primary
                    entry_copy["source_bonus"] = src.bonus
                    all_entries.append(entry_copy)

            elif src.kind == "white_house_html":
                for wh_art in self._fetch_white_house_entries(url=src.url, source_name=src.name):
                    link = wh_art.get("link", "")
                    if link and link in seen_links:
                        continue
                    if link:
                        seen_links.add(link)
                    wh_copy = dict(wh_art)
                    wh_copy["is_primary_source"] = True
                    wh_copy["source_bonus"] = src.bonus
                    if wh_copy.get("published") and not wh_copy.get("published_parsed"):
                        try:
                            wh_copy["published_parsed"] = wh_copy["published"].timetuple()
                        except Exception:
                            pass
                    all_entries.append(wh_copy)

            else:  # kind == "rss"
                for raw_entry in self._fetch_rss_entries(src.url):
                    if self._check_summary_for_junk:
                        if self._is_garbage(raw_entry):
                            continue
                    elif self._is_junk_article(raw_entry):
                        continue

                    link = (
                        (raw_entry.get("link", "") or raw_entry.get("id", ""))
                        if hasattr(raw_entry, "get")
                        else getattr(raw_entry, "link", "")
                    )
                    if not link or link in seen_links:
                        continue
                    seen_links.add(link)

                    matched_team = self._match_any_favorite_team(raw_entry)
                    title = (
                        raw_entry.get("title", "")
                        if hasattr(raw_entry, "get")
                        else getattr(raw_entry, "title", "")
                    )
                    summary = (
                        (raw_entry.get("summary", "") or raw_entry.get("description", ""))
                        if hasattr(raw_entry, "get")
                        else getattr(raw_entry, "summary", "")
                    )
                    pub_parsed = (
                        (raw_entry.get("published_parsed") or raw_entry.get("updated_parsed"))
                        if hasattr(raw_entry, "get")
                        else getattr(raw_entry, "published_parsed", None)
                    )
                    rss_dict: Dict[str, Any] = {
                        "title": title,
                        "link": link,
                        "summary": summary or "",
                        "published_parsed": pub_parsed,
                        "source": src.name,
                        "is_primary_source": is_primary,
                        "source_bonus": src.bonus,
                    }
                    if pub_parsed is not None:
                        try:
                            rss_dict["published"] = datetime(*pub_parsed[:6], tzinfo=timezone.utc)
                        except Exception:
                            pass
                    if matched_team:
                        rss_dict["team_tag"] = matched_team
                    all_entries.append(rss_dict)

        if self.category == "political":
            return self._score_and_cluster_political_entries(
                entries=all_entries,
                source_bonuses=source_bonuses,
            )

        default_source = self.primary_source
        if self.default_sheet == "nfl_news" and default_source == "NFL.com":
            default_source = "ESPN"

        return self._score_and_cluster_entries(
            entries=all_entries,
            sport=self.sport,
            favorite_teams=[str(t) for t in self.favorite_teams],
            junk_keywords=self.JUNK_KEYWORDS,
            primary_source=self.primary_source,
            primary_source_bonus=self.primary_source_bonus,
            max_articles=self.max_articles,
            similarity_threshold=self.similarity_threshold,
            default_source=default_source,
            source_bonuses=source_bonuses,
        )

    def _score_and_cluster_political_entries(
        self,
        entries: List[Dict[str, Any]],
        source_bonuses: Optional[Dict[str, int]] = None,
    ) -> List[Dict[str, Any]]:
        """Score and cluster political entries using PoliticalNewsScorer and TopicClusterer."""
        from ..news.clustering import TopicClusterer
        from ..news.scoring import ClusterScorer, PoliticalNewsScorer

        if not entries:
            return []

        deduped: List[Dict[str, Any]] = []
        seen_links: set = set()
        now = datetime.now(timezone.utc)
        for entry in entries:
            pub = entry.get("published")
            if isinstance(pub, datetime):
                if pub.tzinfo is None:
                    pub = pub.replace(tzinfo=timezone.utc)
                if now - pub > timedelta(hours=48):
                    continue
            link = str(entry.get("link") or entry.get("id") or "").strip()
            if link:
                if link in seen_links:
                    continue
                seen_links.add(link)
            deduped.append(entry)

        if not deduped:
            return []

        wh_bonus = (source_bonuses or {}).get("white house", 25)
        scorer = PoliticalNewsScorer(
            white_house_bonus=wh_bonus,
            source_bonuses=source_bonuses,
        )
        clusterer = TopicClusterer(
            similarity_threshold=self.similarity_threshold,
            scorer=scorer,
            cluster_scorer=ClusterScorer(),
        )
        clusters = clusterer.cluster(deduped, top_n=self.max_articles)

        result: List[Dict[str, Any]] = []
        for i, cluster in enumerate(clusters):
            published_parsed = None
            if cluster.published:
                try:
                    published_parsed = cluster.published.timetuple()
                except Exception:
                    pass
            elif cluster.articles:
                first = cluster.articles[0]
                published_parsed = first.get("published_parsed")

            slot_entry: Dict[str, Any] = {
                "title": cluster.topic,
                "summary": cluster.combined_summary,
                "link": cluster.primary_link,
                "id": cluster.primary_link,
                "source": ", ".join(cluster.sources),
                "sources": cluster.sources,
                "published_parsed": published_parsed,
                "reports": [
                    {
                        "source": a.get("source", "Unknown"),
                        "title": a.get("title", ""),
                        "summary": a.get("summary", ""),
                        "link": a.get("link", ""),
                    }
                    for a in cluster.articles
                ],
                "is_cluster": True,
                "cluster_score": cluster.score,
            }
            result.append({"slot": f"Section {i + 1}", "entry": slot_entry})
        return result

    def sanitize_articles(self, articles: List[Dict]) -> List[Dict]:
        """Filter junk entries and enrich articles with scraped body text when summary is short/empty."""
        enriched: List[Dict] = []
        scrape_cache: Dict[str, str] = {}

        def _scrape_cached(url: str) -> str:
            if url not in scrape_cache:
                scrape_cache[url] = self._scrape_article_text(url)
            return scrape_cache[url]

        min_chars = self._min_summary_chars_before_scrape

        for item in articles:
            entry = item.get("entry") if isinstance(item, dict) else None
            if entry is None:
                continue
            if self._is_junk_article(entry):
                continue

            link = entry.get("link", "") if hasattr(entry, "get") else ""
            summary = (entry.get("summary", "") if hasattr(entry, "get") else "") or ""

            new_entry: Dict[str, Any] = {
                k: (entry.get(k) if hasattr(entry, "get") else getattr(entry, k, None))
                for k in (
                    "title",
                    "link",
                    "id",
                    "published_parsed",
                    "summary",
                    "source",
                    "sources",
                    "reports",
                    "is_cluster",
                    "cluster_score",
                )
            }

            if link and len(summary) < min_chars:
                scraped = _scrape_cached(link)
                if scraped:
                    new_entry["summary"] = scraped

            if new_entry.get("reports"):
                updated_reports = []
                reports_updated = False
                for rep in new_entry["reports"]:
                    rep_copy = dict(rep)
                    rep_link = rep_copy.get("link", "")
                    rep_summary = rep_copy.get("summary", "") or ""
                    if rep_link and len(rep_summary) < min_chars:
                        scraped_rep = _scrape_cached(rep_link)
                        if scraped_rep:
                            rep_copy["summary"] = scraped_rep
                            reports_updated = True
                    updated_reports.append(rep_copy)
                new_entry["reports"] = updated_reports

                if len(new_entry.get("summary") or "") < min_chars and (reports_updated or updated_reports):
                    rep_summaries = [
                        r["summary"].strip()
                        for r in updated_reports
                        if r.get("summary") and r["summary"].strip()
                    ]
                    if rep_summaries:
                        new_entry["summary"] = "\n\n".join(dict.fromkeys(rep_summaries))

            enriched.append({"slot": item.get("slot", "Section"), "entry": new_entry})

        return super().sanitize_articles(enriched)

    # ------------------------------------------------------------------
    # Team Matching & Junk Filtering Helpers
    # ------------------------------------------------------------------

    def _raw_to_entry_dict(
        self,
        raw_entry: object,
        source_name: str,
        team_tag: Optional[str] = None,
        is_primary: bool = False,
        source_bonus: int = 0,
    ) -> Optional[Dict[str, Any]]:
        link = (
            raw_entry.get("link", "")
            if hasattr(raw_entry, "get")
            else getattr(raw_entry, "link", "")
        )
        if not link or self._is_junk_article(raw_entry):
            return None
        title = (
            raw_entry.get("title", "")
            if hasattr(raw_entry, "get")
            else getattr(raw_entry, "title", "")
        )
        summary = (
            raw_entry.get("summary", "") or raw_entry.get("description", "")
            if hasattr(raw_entry, "get")
            else getattr(raw_entry, "summary", "")
        )
        pub_parsed = (
            raw_entry.get("published_parsed")
            if hasattr(raw_entry, "get")
            else getattr(raw_entry, "published_parsed", None)
        )
        entry_dict: Dict[str, Any] = {
            "title": title,
            "link": link,
            "summary": summary or "",
            "published_parsed": pub_parsed,
            "source": source_name,
            "is_primary_source": is_primary,
            "source_bonus": source_bonus,
        }
        if team_tag:
            entry_dict["team_tag"] = team_tag
        return entry_dict

    def _is_junk_article(self, entry: object) -> bool:
        """Return True if the entry title contains any junk keyword."""
        title: str = entry.get("title", "") if hasattr(entry, "get") else getattr(entry, "title", "")  # type: ignore[union-attr]
        title_lower = (title or "").lower()
        return any(kw.lower() in title_lower for kw in self.JUNK_KEYWORDS)

    def _is_garbage(self, entry: object) -> bool:
        """Return True if the entry title or summary contains any junk/exclusion keyword."""
        title: str = entry.get("title", "") if hasattr(entry, "get") else getattr(entry, "title", "")  # type: ignore[union-attr]
        summary: str = entry.get("summary", "") if hasattr(entry, "get") else getattr(entry, "summary", "")  # type: ignore[union-attr]
        title_lower = (title or "").lower()
        summary_lower = (summary or "").lower()
        keywords = getattr(self, "EXCLUSION_KEYWORDS", self.JUNK_KEYWORDS)
        for keyword in keywords:
            kw_low = keyword.lower()
            if kw_low in title_lower or kw_low in summary_lower:
                return True
        return False

    def _get_team_match_patterns(self, team_name: str) -> List[str]:
        """Return a list of matching keywords/aliases for a team name."""
        keywords: Set[str] = {team_name.strip()}
        try:
            from ..db import sport_get_team_aliases, sport_resolve_team

            resolved = sport_resolve_team(self.sport, team_name)
            if resolved:
                aliases = sport_get_team_aliases(self.sport, resolved["team_id"])
                for a in aliases:
                    keywords.add(a)
                if resolved.get("full_name"):
                    keywords.add(resolved["full_name"])
                if resolved.get("abbrev"):
                    keywords.add(resolved["abbrev"])
        except Exception:
            pass

        parts = team_name.strip().split()
        if len(parts) > 1:
            keywords.add(parts[-1])
            keywords.add(" ".join(parts[:-1]))

        return [k.lower() for k in keywords if len(k) > 1]

    def _entry_matches_team(self, entry: object, team_name: str) -> bool:
        """Check if an RSS entry matches a favorite team name or any of its aliases."""
        title = (entry.get("title", "") if hasattr(entry, "get") else getattr(entry, "title", "")) or ""
        summary = (entry.get("summary", "") if hasattr(entry, "get") else getattr(entry, "summary", "")) or ""
        title_low = title.lower()
        summary_low = summary.lower()
        patterns = self._get_team_match_patterns(team_name)

        for pat in patterns:
            regex = r"(?:\b|\A)" + re.escape(pat) + r"(?:\b|\Z)"
            if re.search(regex, title_low) or re.search(regex, summary_low):
                return True
        return False

    def _team_matches_entry(self, team: str, entry: object) -> bool:
        """Return True when ``entry`` looks like it belongs to ``team`` (NHL style)."""
        title = (entry.get("title", "") if hasattr(entry, "get") else getattr(entry, "title", "")) or ""
        link = (entry.get("link", "") if hasattr(entry, "get") else getattr(entry, "link", "")) or ""
        haystack = f"{title} {link}".lower()

        team_lower = team.lower().strip()
        aliases = {team_lower}

        if team_lower == "golden knights":
            aliases.update({"vegas golden knights", "vegas", "knights"})
        elif team_lower == "maple leafs":
            aliases.update({"toronto maple leafs", "leafs", "toronto"})
        elif team_lower == "blue jackets":
            aliases.update({"columbus blue jackets", "bluejackets", "columbus"})
        elif team_lower == "red wings":
            aliases.update({"detroit red wings", "redwings", "detroit"})
        elif team_lower == "hurricanes":
            aliases.update({"carolina hurricanes", "carolina"})

        return any(alias in haystack for alias in aliases)

    def _match_favorite_team(self, entry: Dict[str, Any]) -> Optional[str]:
        """Return the highest-priority favorite team matching the entry, if any."""
        headline = str(entry.get("title", "")).lower()
        desc = str(entry.get("summary", "")).lower()
        for team in self.favorite_teams:
            team_str = str(team)
            team_clean = team_str.lower()
            if team_clean and (team_clean in headline or team_clean in desc):
                return team_str
        return None

    def _match_any_favorite_team(self, entry: object) -> Optional[str]:
        """Match an entry against favorite_teams using sport-appropriate alias matching."""
        for team in self.favorite_teams:
            team_str = str(team)
            if self.sport == "nhl" and self._team_matches_entry(team_str, entry):
                return team_str
            if self._entry_matches_team(entry, team_str):
                return team_str
        return None

    # ------------------------------------------------------------------
    # Source Fetchers
    # ------------------------------------------------------------------

    def _parse_rss_feed(self, url_or_text: str) -> Any:
        """Parse an RSS URL or XML string with feedparser."""
        return feedparser.parse(url_or_text)

    def _fetch_rss_entries(self, feed_url: str) -> List[object]:
        """Fetch and parse an RSS feed URL."""
        if (
            (self._use_requests_for_rss or isinstance(requests.get, MagicMock))
            and not isinstance(feedparser.parse, MagicMock)
        ):
            try:
                resp = requests.get(
                    feed_url, timeout=self._SCRAPE_TIMEOUT, headers=self._SCRAPE_HEADERS
                )
                text = getattr(resp, "text", "")
                if resp.status_code != 200 or not isinstance(text, str) or not text:
                    return []
                feed = self._parse_rss_feed(text)
                return list(getattr(feed, "entries", []))
            except Exception:
                return []

        try:
            feed = self._parse_rss_feed(feed_url)
            return list(getattr(feed, "entries", []))
        except Exception:
            return []

    def _get_feed_url(self, team: Optional[str]) -> Optional[str]:
        """Resolve a team string or alias to a team RSS feed URL."""
        if team is None:
            return self.TEAM_FEEDS.get(None)

        if team in self.TEAM_FEEDS:
            return self.TEAM_FEEDS[team]

        team_clean = str(team).strip()
        for k, v in self.TEAM_FEEDS.items():
            if k and k.lower() == team_clean.lower():
                return v

        try:
            from ..db import sport_get_team_feed_slug, sport_resolve_team

            resolved = sport_resolve_team(self.sport, team_clean)
            if resolved:
                slug = sport_get_team_feed_slug(self.sport, resolved["team_id"])
                if slug and self.sport == "mlb":
                    return f"https://www.mlb.com/{slug}/feeds/news/rss.xml"
                full_name = resolved.get("full_name")
                if full_name and full_name in self.TEAM_FEEDS:
                    return self.TEAM_FEEDS[full_name]
        except Exception:
            pass

        return None

    def _fetch_entries(self, team: Optional[str]) -> List[object]:
        """Fetch raw entries for the given team (or general feed)."""
        if self.sport == "nhl":
            return self._fetch_nhl_entries(team)
        url = self._get_feed_url(team)
        if url is None:
            return []
        feed = self._parse_rss_feed(url)
        return list(getattr(feed, "entries", []))

    def _first_unseen_entry(self, team: str, seen_links: set) -> Optional[object]:
        """Return the first non-junk entry from ``team``'s feed not already seen."""
        for entry in self._fetch_entries(team):
            if self.sport == "nhl" and not self._team_matches_entry(team, entry):
                continue
            link = entry.get("link", "") if hasattr(entry, "get") else getattr(entry, "link", "")
            if link not in seen_links and not self._is_junk_article(entry):
                return entry
        return None

    # --- NHL HTML scraper helpers ---

    def _parse_recent_articles(self, html: str, base_url: str) -> List[Dict]:
        """Extract recent article cards from an NHL.com news page."""
        soup = BeautifulSoup(html, "html.parser")
        now = datetime.now(timezone.utc)
        recent: List[Dict] = []

        for card in soup.select("a.nhl-c-card-wrap"):
            href = card.get("href", "")
            if not href:
                continue

            title_tag = card.select_one("h3.fa-text__title")
            image_tag = card.select_one("img[alt]")
            title = ""
            if title_tag:
                title = title_tag.get_text(" ", strip=True)
            elif image_tag:
                title = image_tag.get("alt", "").strip()
            if not title:
                continue

            time_tag = card.select_one("time[datetime]")
            published_parsed = None
            published_text = ""
            if time_tag is not None:
                published_text = time_tag.get_text(" ", strip=True)
                datetime_attr = time_tag.get("datetime", "")
                if datetime_attr:
                    try:
                        published_dt = datetime.fromisoformat(
                            datetime_attr.replace("Z", "+00:00")
                        )
                        if published_dt.tzinfo is None:
                            published_dt = published_dt.replace(tzinfo=timezone.utc)
                        else:
                            published_dt = published_dt.astimezone(timezone.utc)
                        if now - published_dt > self._RECENT_WINDOW:
                            continue
                        published_parsed = published_dt.timetuple()
                    except ValueError:
                        published_parsed = None

            entry = {
                "title": title,
                "link": urljoin(base_url, href),
                "summary": "",
                "published": published_text,
                "published_parsed": published_parsed,
            }
            recent.append(entry)

        return recent

    def _fetch_page_articles(self, url: str) -> List[Dict]:
        """Fetch and cache article cards from an NHL.com page."""
        if url in self._article_cache:
            return self._article_cache[url]

        try:
            resp = requests.get(
                url, timeout=self._SCRAPE_TIMEOUT, headers=self._SCRAPE_HEADERS
            )
            if resp.status_code != 200:
                self._article_cache[url] = []
                return []
            entries = self._parse_recent_articles(resp.text, url)
        except Exception:
            entries = []

        self._article_cache[url] = entries
        return entries

    def _fetch_nhl_entries(
        self,
        team: Optional[str],
        team_feeds: Optional[Dict[Optional[str], str]] = None,
        news_url: Optional[str] = None,
    ) -> List[object]:
        """Fetch recent NHL.com article cards for the given team or general page."""
        feeds_map = team_feeds if team_feeds is not None else self.TEAM_FEEDS
        fallback_url = news_url or getattr(self, "_NEWS_PAGE_URL", "https://www.nhl.com/news")
        if team is None:
            return self._fetch_page_articles(fallback_url)

        team_url = feeds_map.get(team)
        entries = self._fetch_page_articles(team_url) if team_url else []
        if entries:
            return entries

        return self._fetch_page_articles(fallback_url)

    # --- ESPN API fetcher ---

    def _fetch_news_articles(
        self,
        api_url: Optional[str] = None,
        source_name: str = "ESPN",
    ) -> List[Dict]:
        """Fetch raw articles list from ESPN API."""
        target_url = api_url or getattr(self, "_NEWS_API_URL", ESPN_NFL_NEWS_API_URL)
        try:
            resp = requests.get(target_url, timeout=self._SCRAPE_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            articles = []
            for item in data.get("articles", []):
                headline = item.get("headline", "")
                description = item.get("description", "")
                link = item.get("links", {}).get("web", {}).get("href", "")
                pub_date_str = item.get("published", "")

                published_parsed = None
                if pub_date_str:
                    try:
                        dt = datetime.fromisoformat(pub_date_str.replace("Z", "+00:00"))
                        published_parsed = dt.timetuple()
                    except (ValueError, TypeError):
                        published_parsed = None

                articles.append(
                    {
                        "title": headline,
                        "link": link,
                        "summary": description,
                        "source": source_name,
                        "published": pub_date_str,
                        "published_parsed": published_parsed,
                    }
                )
            return articles
        except Exception as e:
            logger.warning("Error fetching ESPN news (%s): %s", target_url, e)
            return []

    # --- White House HTML fetcher ---

    def _fetch_white_house_entries(
        self,
        url: str = WHITE_HOUSE_URL,
        source_name: str = "White House",
    ) -> List[Dict]:
        """Fetch White House briefing room entries using WhiteHouseProvider."""
        try:
            from .political_news_provider import WhiteHouseProvider

            wh = WhiteHouseProvider()
            wh.URL = url
            wh.SOURCE_NAME = source_name
            return wh.get_articles()
        except Exception as exc:
            logger.warning("Error fetching White House articles: %s", exc)
            return []

    # --- Article Body Scraping ---

    def _scrape_article_text(self, url: str) -> str:
        """Fetch ``url`` and extract article body paragraphs."""
        if not url:
            return ""
        try:
            resp = requests.get(
                url, timeout=self._SCRAPE_TIMEOUT, headers=self._SCRAPE_HEADERS
            )
            if resp.status_code != 200:
                return ""
            soup = BeautifulSoup(resp.text, "html.parser")
            for selector in self._ARTICLE_SELECTORS:
                container = soup.select_one(selector)
                if container:
                    paragraphs = container.find_all("p")
                    if paragraphs:
                        text = " ".join(p.get_text(" ", strip=True) for p in paragraphs)
                        if text.strip():
                            return text.strip()
            return ""
        except Exception:
            return ""
