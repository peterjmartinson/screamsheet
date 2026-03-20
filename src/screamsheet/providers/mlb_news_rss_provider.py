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

    # Maps team name to its MLB.com RSS feed URL.
    # None is the sentinel key for the general MLB news feed used as fallback.
    TEAM_FEEDS: Dict[Optional[str], str] = {
        "Phillies": "https://www.mlb.com/phillies/feeds/news/rss.xml",
        "Padres": "https://www.mlb.com/padres/feeds/news/rss.xml",
        "Yankees": "https://www.mlb.com/yankees/feeds/news/rss.xml",
        "Dodgers": "https://www.mlb.com/dodgers/feeds/news/rss.xml",
        "Mets": "https://www.mlb.com/mets/feeds/news/rss.xml",
        "Braves": "https://www.mlb.com/braves/feeds/news/rss.xml",
        "Astros": "https://www.mlb.com/astros/feeds/news/rss.xml",
        "Cubs": "https://www.mlb.com/cubs/feeds/news/rss.xml",
        "RedSox": "https://www.mlb.com/red-sox/feeds/news/rss.xml",
        "Giants": "https://www.mlb.com/giants/feeds/news/rss.xml",
        None: "https://www.mlb.com/feeds/news/rss.xml",
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
        self.favorite_teams: List[str] = favorite_teams or ["Phillies", "Padres", "Yankees"]
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

    def _fetch_entries(self, team: Optional[str]) -> List[object]:
        """Fetch and return raw feedparser entries for the given team (or general feed)."""
        url = self.TEAM_FEEDS.get(team)
        if url is None:
            return []
        feed = feedparser.parse(url)
        return list(feed.entries)

