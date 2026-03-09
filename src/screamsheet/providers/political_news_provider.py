"""Political news data providers: RSS feeds (7 sources) and White House HTML."""
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
import time as _time

import feedparser
import requests
from bs4 import BeautifulSoup

from ..base import DataProvider

logger = logging.getLogger(__name__)
_LOG_FMT = "[%(asctime)s] %(levelname)s %(name)s: %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"

# Configure a handler only if the root logger has none (avoids duplicate output
# when the application has already configured logging).
if not logging.root.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter(_LOG_FMT, datefmt=_DATE_FMT))
    logging.basicConfig(level=logging.INFO, handlers=[_handler])


# ---------------------------------------------------------------------------
# PoliticalRSSProvider
# ---------------------------------------------------------------------------

class PoliticalRSSProvider(DataProvider):
    """
    Fetches and normalizes news entries from 7 RSS feeds covering political
    and world news.

    Each entry is normalized to::

        {
            'title':     str,
            'link':      str,
            'published': datetime,   # UTC-aware; entries missing a date are dropped
            'summary':   str,        # empty string when absent
            'source':    str,        # human-readable source name
        }

    Entries older than 48 hours are filtered out.  One source failing does
    not abort the others.
    """

    RSS_SOURCES: Dict[str, str] = {
        # Reuters deprecated its public RSS; replaced with The Guardian world feed
        "The Guardian":    "https://www.theguardian.com/world/rss",
        # AP deprecated its public RSS; replaced with Google News top-headlines
        "Google News":     "https://news.google.com/rss/headlines/section/topic/NATION.en_US?hl=en-US&gl=US&ceid=US:en",
        "BBC":             "https://feeds.bbci.co.uk/news/rss.xml",
        "NYT":             "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
        "Politico":        "https://rss.politico.com/congress.xml",
        "NPR":             "https://feeds.npr.org/1001/rss.xml",
        "Washington Post": "https://feeds.washingtonpost.com/rss/national",
    }

    def __init__(self, **config):
        super().__init__(**config)

    # ------------------------------------------------------------------
    # DataProvider stubs
    # ------------------------------------------------------------------

    def get_game_scores(self, date: datetime) -> list:
        """Not applicable for news provider."""
        return []

    def get_standings(self) -> None:
        """Not applicable for news provider."""
        return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_articles(self) -> List[Dict]:
        """
        Fetch all RSS sources and return normalized entries within 48 hours.

        Returns:
            Flat list of normalized entry dicts across all sources.
        """
        all_entries: List[Dict] = []
        for name, url in self.RSS_SOURCES.items():
            try:
                entries = self._fetch_source(name, url)
                logger.info(
                    "PoliticalRSSProvider: %s — %d entries within 48h", name, len(entries)
                )
                all_entries.extend(entries)
            except Exception as exc:  # noqa: BLE001
                logger.error("PoliticalRSSProvider: %s failed: %s", name, exc)
        return all_entries

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fetch_source(self, name: str, url: str) -> List[Dict]:
        """Parse one RSS feed and return normalized entries within 48 hours."""
        feed = feedparser.parse(url)
        results = []
        for entry in feed.entries:
            normalized = self._normalize_rss_entry(entry, name)
            if normalized and self._within_48h(normalized["published"]):
                results.append(normalized)
        return results

    def _normalize_rss_entry(self, entry, source_name: str) -> Optional[Dict]:
        """
        Convert a feedparser entry to the common dict shape.

        Returns None if the entry lacks a usable title or a parseable date.
        """
        title = (entry.get("title") or "").strip()
        if not title:
            return None

        published = self._published_dt(entry)
        if published is None:
            return None

        return {
            "title":     title,
            "link":      entry.get("link") or "",
            "published": published,
            "summary":   (entry.get("summary") or entry.get("description") or "").strip(),
            "source":    source_name,
        }

    def _published_dt(self, entry) -> Optional[datetime]:
        """Convert feedparser published_parsed (struct_time, UTC) to an aware datetime."""
        struct = entry.get("published_parsed") or entry.get("updated_parsed")
        if struct is None:
            return None
        try:
            return datetime(*struct[:6], tzinfo=timezone.utc)
        except Exception:  # noqa: BLE001
            return None

    def _within_48h(self, dt: datetime) -> bool:
        """Return True if *dt* is no older than 48 hours from now (UTC)."""
        return datetime.now(timezone.utc) - dt <= timedelta(hours=48)


# ---------------------------------------------------------------------------
# WhiteHouseProvider
# ---------------------------------------------------------------------------

class WhiteHouseProvider(DataProvider):
    """
    Scrapes press briefings and statements from https://www.whitehouse.gov/briefing-room/.

    Uses a cascading selector chain so the provider degrades gracefully when
    the site's markup changes.  Each selector dict has four keys:

    * ``container``  — CSS selector for the repeating article wrapper
    * ``headline``   — CSS selector (relative to container) for the title ``<a>``
    * ``date``       — CSS selector (relative to container) for the ``<time>`` tag
    * ``summary``    — CSS selector (relative to container) for a teaser paragraph

    Output matches the same dict shape as :class:`PoliticalRSSProvider`.
    """

    # /briefing-room/ redirects to /news/ — use the canonical URL directly
    URL = "https://www.whitehouse.gov/news/"

    # Ordered fallback: try specific selectors first, generic ones last.
    # Primary selectors confirmed against live page as of March 2026 (WordPress
    # block theme with li.wp-block-post containers).
    SELECTOR_CHAIN: List[Dict] = [
        {
            "container": "li.wp-block-post",
            "headline":  "h2.wp-block-post-title a",
            "date":      "div.wp-block-post-date time",
            "summary":   "",   # page does not include a teaser snippet
        },
        {
            "container": "article",
            "headline":  "h2 a",
            "date":      "time",
            "summary":   "p",
        },
        {
            "container": "li.news-item",
            "headline":  "a.news-item__title",
            "date":      "time",
            "summary":   "",
        },
    ]

    SOURCE_NAME = "White House"

    def __init__(self, **config):
        super().__init__(**config)

    # ------------------------------------------------------------------
    # DataProvider stubs
    # ------------------------------------------------------------------

    def get_game_scores(self, date: datetime) -> list:
        """Not applicable for news provider."""
        return []

    def get_standings(self) -> None:
        """Not applicable for news provider."""
        return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_articles(self) -> List[Dict]:
        """
        Fetch the White House briefing room and return normalized entries
        within 48 hours.

        Returns:
            List of normalized entry dicts.
        """
        try:
            html = self._fetch_html()
        except Exception as exc:  # noqa: BLE001
            logger.error("WhiteHouseProvider: fetch failed: %s", exc)
            return []

        entries = self._parse_html(html)
        logger.info(
            "WhiteHouseProvider: %d entries within 48h", len(entries)
        )
        return entries

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fetch_html(self) -> str:
        """Retrieve the briefing-room page and return its HTML."""
        response = requests.get(self.URL, timeout=10)
        response.raise_for_status()
        return response.text

    def _parse_html(self, html: str) -> List[Dict]:
        """
        Parse HTML with BeautifulSoup, trying each selector in SELECTOR_CHAIN
        until results are found.
        """
        soup = BeautifulSoup(html, "html.parser")

        for selectors in self.SELECTOR_CHAIN:
            containers = soup.select(selectors["container"])
            if not containers:
                continue

            results = []
            for container in containers:
                entry = self._extract_entry(container, selectors)
                if entry and self._within_48h(entry["published"]):
                    results.append(entry)

            if results:
                return results

        logger.warning("WhiteHouseProvider: no entries matched any selector")
        return []

    def _extract_entry(self, container, selectors: Dict) -> Optional[Dict]:
        """Extract a single normalized entry from one container element."""
        # Headline / link
        headline_tag = container.select_one(selectors["headline"])
        if not headline_tag:
            return None
        title = headline_tag.get_text(strip=True)
        if not title:
            return None
        link = headline_tag.get("href") or ""
        if link and link.startswith("/"):
            link = "https://www.whitehouse.gov" + link

        # Date
        date_sel = selectors.get("date") or ""
        time_tag = container.select_one(date_sel) if date_sel else None
        published = self._parse_date(time_tag)
        if published is None:
            return None

        # Summary (optional)
        summary = ""
        summary_sel = selectors.get("summary") or ""
        if summary_sel:
            summary_tag = container.select_one(summary_sel)
            if summary_tag:
                summary = summary_tag.get_text(strip=True)

        return {
            "title":     title,
            "link":      link,
            "published": published,
            "summary":   summary,
            "source":    self.SOURCE_NAME,
        }

    def _parse_date(self, time_tag) -> Optional[datetime]:
        """
        Extract a UTC-aware datetime from a ``<time>`` element.

        Tries the ``datetime`` attribute first; falls back to parsing the
        tag's visible text.  Returns None on failure.
        """
        if time_tag is None:
            return None

        raw = time_tag.get("datetime") or time_tag.get_text(strip=True)
        if not raw:
            return None

        for fmt in (
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d",
            "%B %d, %Y",
            "%b %d, %Y",
        ):
            try:
                dt = datetime.strptime(raw, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue

    def _within_48h(self, dt: datetime) -> bool:
        """Return True if *dt* is no older than 48 hours from now (UTC)."""
        return datetime.now(timezone.utc) - dt <= timedelta(hours=48)


if __name__ == "__main__":
    from collections import Counter

    print("=" * 60)
    print("RSS FEEDS")
    print("=" * 60)
    rss_articles = PoliticalRSSProvider().get_articles()
    by_source = Counter(a["source"] for a in rss_articles)
    print(f"Total entries (last 48h): {len(rss_articles)}")
    for source, count in sorted(by_source.items()):
        print(f"  {source}: {count} entries")

    if rss_articles:
        print("\nFirst 3 entries:")
        for entry in rss_articles[:3]:
            print(f"\n  [{entry['source']}]  {entry['published'].strftime('%Y-%m-%d %H:%M')} UTC")
            print(f"  Title:   {entry['title']}")
            print(f"  Link:    {entry['link']}")
            if entry["summary"]:
                print(f"  Summary: {entry['summary'][:120]}...")

    print()
    print("=" * 60)
    print("WHITE HOUSE")
    print("=" * 60)
    wh_articles = WhiteHouseProvider().get_articles()
    print(f"Total entries (last 48h): {len(wh_articles)}")
    for entry in wh_articles:
        print(f"\n  {entry['published'].strftime('%Y-%m-%d %H:%M')} UTC")
        print(f"  Title: {entry['title']}")
        print(f"  Link:  {entry['link']}")
