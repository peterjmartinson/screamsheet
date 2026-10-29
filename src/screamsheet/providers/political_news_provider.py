"""Political news data providers: RSS feeds (7 sources) and White House HTML."""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Union

import feedparser  # type: ignore[import-untyped]
import requests
from bs4 import BeautifulSoup

from ..base import NewsDataProvider
from .news_sources import (
    POLITICAL_RSS_SOURCES,
    WHITE_HOUSE_SELECTOR_CHAIN,
    WHITE_HOUSE_URL,
    ResolvedNewsSource,
    UnifiedNewsProvider,
)

logger = logging.getLogger(__name__)
_LOG_FMT = "[%(asctime)s] %(levelname)s %(name)s: %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"

if not logging.root.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter(_LOG_FMT, datefmt=_DATE_FMT))
    logging.basicConfig(level=logging.INFO, handlers=[_handler])


# ---------------------------------------------------------------------------
# PoliticalRSSProvider
# ---------------------------------------------------------------------------

class PoliticalRSSProvider(NewsDataProvider):
    """
    Fetches and normalizes news entries from RSS feeds covering political
    and world news.
    """

    RSS_SOURCES: Dict[str, str] = dict(POLITICAL_RSS_SOURCES)

    def __init__(self, **config: Any) -> None:
        super().__init__(**config)

    def get_articles(self) -> List[Dict]:
        """Fetch all RSS sources and return normalized entries within 48 hours."""
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

    def _fetch_source(self, name: str, url: str) -> List[Dict]:
        """Parse one RSS feed and return normalized entries within 48 hours."""
        feed = feedparser.parse(url)
        results = []
        for entry in feed.entries:
            normalized = self._normalize_rss_entry(entry, name)
            if normalized and self._within_48h(normalized["published"]):
                results.append(normalized)
        return results

    def _normalize_rss_entry(self, entry: Any, source_name: str) -> Optional[Dict]:
        """Convert a feedparser entry to the common dict shape."""
        title = (entry.get("title") or "").strip()
        if not title:
            return None

        published = self._published_dt(entry)
        if published is None:
            return None

        return {
            "title": title,
            "link": entry.get("link") or "",
            "published": published,
            "summary": (entry.get("summary") or entry.get("description") or "").strip(),
            "source": source_name,
        }

    def _published_dt(self, entry: Any) -> Optional[datetime]:
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

class WhiteHouseProvider(NewsDataProvider):
    """
    Scrapes press briefings and statements from https://www.whitehouse.gov/news/.
    """

    URL: str = WHITE_HOUSE_URL
    SELECTOR_CHAIN: List[Dict[str, str]] = list(WHITE_HOUSE_SELECTOR_CHAIN)
    SOURCE_NAME: str = "White House"

    _ARTICLE_SELECTORS: List[str] = [
        "div.entry-content",
        "div.wp-block-post-content",
        "section.entry-content",
        "article",
        "main",
    ]
    _SCRAPE_TIMEOUT: int = 5
    _SCRAPE_HEADERS: Dict[str, str] = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }

    def __init__(self, scrape_body: bool = True, **config: Any) -> None:
        super().__init__(**config)
        self.scrape_body = scrape_body

    def get_articles(self) -> List[Dict]:
        """Fetch the White House briefing room and return normalized entries within 48 hours."""
        try:
            html = self._fetch_html()
        except Exception as exc:  # noqa: BLE001
            logger.error("WhiteHouseProvider: fetch failed: %s", exc)
            return []

        entries = self._parse_html(html)
        logger.info("WhiteHouseProvider: %d entries within 48h", len(entries))
        return entries

    def _fetch_html(self) -> str:
        """Retrieve the briefing-room page and return its HTML."""
        response = requests.get(self.URL, timeout=10)
        response.raise_for_status()
        return response.text

    def _parse_html(self, html: str) -> List[Dict]:
        """Parse HTML with BeautifulSoup, trying each selector in SELECTOR_CHAIN."""
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

    def _extract_entry(self, container: Any, selectors: Dict) -> Optional[Dict]:
        """Extract a single normalized entry from one container element."""
        headline_tag = container.select_one(selectors["headline"])
        if not headline_tag:
            return None
        title = headline_tag.get_text(strip=True)
        if not title:
            return None
        link = headline_tag.get("href") or ""
        if link and link.startswith("/"):
            link = "https://www.whitehouse.gov" + link

        date_sel = selectors.get("date") or ""
        time_tag = container.select_one(date_sel) if date_sel else None
        published = self._parse_date(time_tag)
        if published is None:
            return None

        summary = ""
        summary_sel = selectors.get("summary") or ""
        if summary_sel:
            summary_tag = container.select_one(summary_sel)
            if summary_tag:
                summary = summary_tag.get_text(strip=True)

        if not summary and link and self.scrape_body:
            summary = self._scrape_article_text(link)

        return {
            "title": title,
            "link": link,
            "published": published,
            "summary": summary,
            "source": self.SOURCE_NAME,
        }

    def _scrape_article_text(self, url: str) -> str:
        """Fetch url and extract briefing/statement text paragraphs."""
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
        except Exception as exc:  # noqa: BLE001
            logger.debug("WhiteHouseProvider: failed to scrape %s: %s", url, exc)
            return ""

    def _parse_date(self, time_tag: Any) -> Optional[datetime]:
        """Extract a UTC-aware datetime from a ``<time>`` element."""
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
        return None

    def _within_48h(self, dt: datetime) -> bool:
        """Return True if *dt* is no older than 48 hours from now (UTC)."""
        return datetime.now(timezone.utc) - dt <= timedelta(hours=48)


# ---------------------------------------------------------------------------
# PoliticalNewsProvider — unified political news provider
# ---------------------------------------------------------------------------

class PoliticalNewsProvider(UnifiedNewsProvider):
    """
    Unified political news provider that fetches from White House and political
    RSS sources (or any cherry-picked ``sources`` list from :data:`NEWS_SOURCE_CATALOG`)
    and caches the resulting ``{'slot', 'entry'}`` list.
    """

    PRIMARY_SOURCE: str = "White House"
    PRIMARY_SOURCE_BONUS: int = 25
    DEFAULT_SHEET: str = "presidential"
    DEFAULT_CATEGORY: str = "political"

    def __init__(
        self,
        max_articles: int = 4,
        sources: Optional[Sequence[Union[str, Dict[str, Any], ResolvedNewsSource]]] = None,
        mode: str = "multi",
        primary_source: str = PRIMARY_SOURCE,
        primary_source_bonus: int = PRIMARY_SOURCE_BONUS,
        extra_feeds: Optional[Dict[str, str]] = None,
        **config: Any,
    ) -> None:
        super().__init__(
            max_articles=max_articles,
            sources=sources,
            mode=mode,
            primary_source=primary_source,
            primary_source_bonus=primary_source_bonus,
            extra_feeds=extra_feeds,
            category="political",
            default_sheet="presidential",
            junk_keywords=[],
            similarity_threshold=0.68,
            **config,
        )
        self._cache: Optional[List[Dict]] = None

    def get_articles(self) -> List[Dict]:
        """Fetch, process, and cache political news articles."""
        if self._cache is not None:
            return self._cache

        # When custom sources are cherry-picked, use the UnifiedNewsProvider pipeline
        if self._has_custom_sources:
            self._cache = super().get_articles()
            logger.info("PoliticalNewsProvider (custom sources): %d articles cached", len(self._cache))
            return self._cache

        try:
            rss = PoliticalRSSProvider().get_articles()
        except Exception as exc:  # noqa: BLE001
            logger.error("PoliticalNewsProvider: RSS fetch failed: %s", exc)
            rss = []
        try:
            wh = WhiteHouseProvider().get_articles()
        except Exception as exc:  # noqa: BLE001
            logger.error("PoliticalNewsProvider: White House fetch failed: %s", exc)
            wh = []

        from ..political.processor import PoliticalNewsProcessor  # noqa: PLC0415

        all_entries = rss + wh
        processor = PoliticalNewsProcessor()
        entries = processor.process(all_entries)
        top = entries[: self.max_articles]

        result = []
        for i, entry in enumerate(top):
            published_parsed = None
            try:
                if entry.get("published"):
                    published_parsed = entry["published"].timetuple()
            except Exception:  # noqa: BLE001
                pass

            slot_entry = {
                "title": entry.get("title", ""),
                "summary": entry.get("summary", ""),
                "link": entry.get("link", ""),
                "id": entry.get("link", ""),
                "source": entry.get("source", ""),
                "published_parsed": published_parsed,
            }
            if entry.get("sources"):
                slot_entry["sources"] = entry["sources"]
            if entry.get("reports"):
                slot_entry["reports"] = entry["reports"]
            if entry.get("is_cluster"):
                slot_entry["is_cluster"] = entry["is_cluster"]

            result.append({"slot": f"Section {i + 1}", "entry": slot_entry})

        self._cache = result
        logger.info("PoliticalNewsProvider: %d articles cached", len(result))
        return self._cache

    def sanitize_articles(self, articles: List[Dict]) -> List[Dict]:
        """Strip HTML from summary and title in each entry (Google News carries HTML)."""
        for item in articles:
            entry = item.get("entry")
            if not entry:
                continue
            entry["summary"] = self._sanitize_text(entry.get("summary") or "")
            entry["title"] = self._sanitize_text(entry.get("title") or "")
        return articles
