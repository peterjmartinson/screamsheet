"""MLB.com news data provider using team-specific RSS feeds."""
import feedparser  # type: ignore[import-untyped]
import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Optional
from datetime import datetime

from ..base import DataProvider


class MLBNewsRssProvider(DataProvider):
    """
    Data provider for MLB.com news via team-specific RSS feeds.

    Fetches articles from team feeds in priority order, then falls back
    to the general MLB news feed to fill any remaining slots.

    Team priorities are fully configurable at construction time — simply
    pass a different ``favorite_teams`` list to change which feeds are
    polled first.

    Articles whose titles contain any entry in ``JUNK_KEYWORDS`` are
    silently skipped.  The article body is scraped from the article URL
    when the RSS feed provides an empty summary (as MLB.com typically does).
    """

    # Maps team name/slug to its MLB.com RSS feed URL for all 30 MLB teams.
    # None is the sentinel key for the general MLB news feed used as fallback.
    TEAM_FEEDS: Dict[Optional[str], str] = {
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

    # Entries whose title contains any of these phrases (case-insensitive) are
    # dropped before they can occupy a slot or be passed to the LLM.
    JUNK_KEYWORDS: List[str] = [
        "Spring Breakout",
        "stream games",
    ]

    # CSS selectors tried in order when scraping MLB.com article pages.
    _ARTICLE_SELECTORS: List[str] = [
        "div.article-template__body-text",
        "div.article-template__content",
        "div.bam-content",
        "article",
        "main",
    ]

    _SCRAPE_TIMEOUT: int = 10
    _SCRAPE_HEADERS: Dict[str, str] = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; screamsheet/1.0; +https://github.com/peterjmartinson/screamsheet)"
        )
    }

    def __init__(
        self,
        favorite_teams: Optional[List[str]] = None,
        max_articles: int = 4,
        **config: object,
    ) -> None:
        super().__init__(**config)
        self.favorite_teams: List[str] = favorite_teams or []
        self.max_articles: int = max_articles

    # ------------------------------------------------------------------
    # DataProvider interface stubs (not applicable for a news provider)
    # ------------------------------------------------------------------

    def get_game_scores(self, date: datetime) -> list:
        """Not applicable for a news provider."""
        return []

    def get_standings(self) -> None:
        """Not applicable for a news provider."""
        return None

    # ------------------------------------------------------------------
    # News-specific interface
    # ------------------------------------------------------------------

    def get_articles(self) -> List[Dict]:
        """
        Fetch up to ``max_articles`` articles from MLB.com RSS feeds.

        Articles are selected in team priority order.  After exhausting
        all team feeds, the general MLB news feed fills any remaining
        slots.  Entries matching ``JUNK_KEYWORDS`` are skipped.

        Returns:
            List of dicts with keys ``'slot'`` (str) and ``'entry'`` (feedparser
            entry).  The list length equals ``max_articles``, but may be
            shorter if the feeds do not contain enough entries.
        """
        selected: List[Dict] = []
        seen_links: set = set()

        # 1. One article per team feed in priority order
        for team in self.favorite_teams:
            if len(selected) >= self.max_articles:
                break
            entry = self._first_unseen_entry(team, seen_links)
            if entry is not None:
                seen_links.add(entry.get("link", ""))
                selected.append({"slot": f"Section {len(selected) + 1}", "entry": entry})

        # 2. Fill remaining slots from the general MLB feed
        if len(selected) < self.max_articles:
            general_entries = self._fetch_entries(None)
            for entry in general_entries:
                if len(selected) >= self.max_articles:
                    break
                link = entry.get("link", "")
                if link not in seen_links and not self._is_junk_article(entry):
                    seen_links.add(link)
                    selected.append(
                        {"slot": f"Section {len(selected) + 1}", "entry": entry}
                    )

        return selected

    def sanitize_articles(self, articles: List[Dict]) -> List[Dict]:
        """
        Filter junk entries and enrich each article with scraped body text
        before delegating to the base-class sanitization pipeline.

        Any entry whose title matches ``JUNK_KEYWORDS`` is dropped.  For
        entries with an empty ``summary``, the article URL is fetched and
        paragraph text is extracted to populate the summary — giving the
        LLM real content to work with instead of an empty string.
        """
        enriched: List[Dict] = []
        for item in articles:
            entry = item.get("entry") if isinstance(item, dict) else None
            if entry is None:
                continue
            if self._is_junk_article(entry):
                continue

            link = entry.get("link", "") if hasattr(entry, "get") else ""
            summary = entry.get("summary", "") if hasattr(entry, "get") else ""

            if link and not summary:
                scraped = self._scrape_article_text(link)
                if scraped:
                    # Build a fresh dict so we don't mutate the feedparser object
                    new_entry: Dict = {
                        k: (entry.get(k) if hasattr(entry, "get") else getattr(entry, k, None))
                        for k in ("title", "link", "id", "published_parsed", "summary")
                    }
                    new_entry["summary"] = scraped
                    item = {"slot": item.get("slot", "Section"), "entry": new_entry}

            enriched.append(item)

        return super().sanitize_articles(enriched)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_junk_article(self, entry: object) -> bool:
        """Return True if the entry title contains any junk keyword."""
        title: str = entry.get("title", "") if hasattr(entry, "get") else ""  # type: ignore[union-attr]
        title_lower = title.lower()
        return any(kw.lower() in title_lower for kw in self.JUNK_KEYWORDS)

    def _scrape_article_text(self, url: str) -> str:
        """
        Fetch ``url`` and extract article body paragraphs.

        Tries a cascade of CSS selectors specific to MLB.com before falling
        back to any ``<p>`` tags found inside ``<article>`` or ``<main>``.
        Returns an empty string on any network or parse failure.
        """
        try:
            resp = requests.get(url, timeout=self._SCRAPE_TIMEOUT, headers=self._SCRAPE_HEADERS)
            if resp.status_code != 200:
                return ""
            soup = BeautifulSoup(resp.text, "html.parser")
            for selector in self._ARTICLE_SELECTORS:
                container = soup.select_one(selector)
                if container:
                    paragraphs = container.find_all("p")
                    if paragraphs:
                        return " ".join(p.get_text(" ", strip=True) for p in paragraphs)
            return ""
        except Exception:
            return ""

    def _first_unseen_entry(
        self, team: str, seen_links: set
    ) -> Optional[object]:
        """Return the first non-junk entry from ``team``'s feed not already seen."""
        for entry in self._fetch_entries(team):
            if entry.get("link", "") not in seen_links and not self._is_junk_article(entry):
                return entry
        return None

    def _get_feed_url(self, team: Optional[str]) -> Optional[str]:
        """Resolve a team string or alias to an MLB.com RSS feed URL."""
        if team is None:
            return self.TEAM_FEEDS.get(None)

        if team in self.TEAM_FEEDS:
            return self.TEAM_FEEDS[team]

        # Case-insensitive match in static map
        team_clean = str(team).strip()
        for k, v in self.TEAM_FEEDS.items():
            if k and k.lower() == team_clean.lower():
                return v

        # Database lookup fallback
        try:
            from ..db import sport_get_team_feed_slug, sport_resolve_team

            resolved = sport_resolve_team("mlb", team_clean)
            if resolved:
                slug = sport_get_team_feed_slug("mlb", resolved["team_id"])
                if slug:
                    return f"https://www.mlb.com/{slug}/feeds/news/rss.xml"
                full_name = resolved.get("full_name")
                if full_name and full_name in self.TEAM_FEEDS:
                    return self.TEAM_FEEDS[full_name]
        except Exception:
            pass

        return None

    def _fetch_entries(self, team: Optional[str]) -> List[object]:
        """Fetch and return raw feedparser entries for the given team (or general feed)."""
        url = self._get_feed_url(team)
        if url is None:
            return []
        feed = feedparser.parse(url)
        return list(feed.entries)
