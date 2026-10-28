"""NFL news data provider using ESPN NFL News API and secondary RSS feeds."""
import logging
import feedparser
import requests
from bs4 import BeautifulSoup
from typing import Any, Dict, List, Optional
from datetime import datetime
from urllib.parse import urljoin

from ..base import NewsDataProvider

logger = logging.getLogger(__name__)


class NFLNewsProvider(NewsDataProvider):
    """
    Data provider for NFL news via ESPN API, NFL.com, and secondary RSS feeds.
    """

    PRIMARY_SOURCE: str = "NFL.com"
    PRIMARY_SOURCE_BONUS: int = 25

    SECONDARY_FEEDS: Dict[str, str] = {
        "NFL.com": "https://www.nfl.com/rss/rsslanding?searchString=home",
        "ProFootballTalk": "https://profootballtalk.nbcsports.com/feed/",
        "CBS Sports": "https://www.cbssports.com/rss/headlines/nfl/",
        "Yahoo Sports": "https://sports.yahoo.com/nfl/rss.xml",
        "NFL Trade Rumors": "https://nfltraderumors.co/feed/",
        "Fox Sports": "https://api.foxsports.com/v2/content/optimized-rss?partnerKey=MB0Wehpmuj2lUhuRhQaafhBjAJqaPU244mlTDK1i&size=30&tags=fs/nfl",
    }

    # Entries whose title contains any of these phrases (case-insensitive) are skipped.
    JUNK_KEYWORDS: List[str] = [
        "betting",
        "how to bet",
        "prop bet",
        "odds, tips",
        "stream games",
        "fantasy football",
        "prospects",
    ]

    _NEWS_API_URL: str = "http://site.api.espn.com/apis/site/v2/sports/football/nfl/news"
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
        mode: str = "multi",
        primary_source: str = PRIMARY_SOURCE,
        primary_source_bonus: int = PRIMARY_SOURCE_BONUS,
        extra_feeds: Optional[Dict[str, str]] = None,
        **config: object,
    ) -> None:
        super().__init__(**config)
        self.favorite_teams: List[str] = favorite_teams or []
        self.max_articles: int = max_articles
        self.mode: str = mode
        self.primary_source: str = primary_source
        self.primary_source_bonus: int = primary_source_bonus
        self.secondary_feeds: Dict[str, str] = (
            dict(extra_feeds) if extra_feeds is not None else dict(self.SECONDARY_FEEDS)
        )

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

    def get_articles(self) -> List[Dict]:
        """
        Fetch up to ``max_articles`` non-junk articles from ESPN NFL news and
        secondary RSS feeds, scored and clustered across sources.
        """
        all_entries: List[Dict[str, Any]] = []
        seen_links: set = set()

        for art in self._fetch_news_articles():
            link = art.get("link", "")
            if not link or link in seen_links or self._is_junk_article(art):
                continue
            seen_links.add(link)
            entry_copy = dict(art)
            matched_team = self._match_favorite_team(entry_copy)
            if matched_team:
                entry_copy["team_tag"] = matched_team
            if entry_copy.get("source", "").lower() == self.primary_source.lower():
                entry_copy["is_primary_source"] = True
            all_entries.append(entry_copy)

        if self.mode == "multi":
            for source_name, feed_url in self.secondary_feeds.items():
                for raw_entry in self._fetch_rss_entries(feed_url):
                    link = (
                        raw_entry.get("link", "")
                        if hasattr(raw_entry, "get")
                        else getattr(raw_entry, "link", "")
                    )
                    if not link or link in seen_links or self._is_junk_article(raw_entry):
                        continue
                    seen_links.add(link)
                    sec_entry: Dict[str, Any] = {
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
                        "source": source_name,
                        "is_primary_source": source_name.lower() == self.primary_source.lower(),
                    }
                    matched_team = self._match_favorite_team(sec_entry)
                    if matched_team:
                        sec_entry["team_tag"] = matched_team
                    all_entries.append(sec_entry)

        return self._score_and_cluster_entries(
            entries=all_entries,
            sport="nfl",
            favorite_teams=[str(t) for t in self.favorite_teams],
            junk_keywords=self.JUNK_KEYWORDS,
            max_articles=self.max_articles,
            primary_source=self.primary_source,
            primary_source_bonus=self.primary_source_bonus,
            similarity_threshold=0.68,
            default_source="ESPN",
        )

    def sanitize_articles(self, articles: List[Dict]) -> List[Dict]:
        """
        Enrich articles with scraped body text if available.
        """
        enriched: List[Dict] = []
        scrape_cache: Dict[str, str] = {}

        def _scrape_cached(url: str) -> str:
            if url not in scrape_cache:
                scrape_cache[url] = self._scrape_article_text(url)
            return scrape_cache[url]

        for item in articles:
            entry = item.get("entry") if isinstance(item, dict) else None
            if entry is None:
                continue
            if self._is_junk_article(entry):
                continue

            link = entry.get("link", "")
            summary = entry.get("summary", "")
            new_entry = dict(entry)

            # If summary is brief (under 150 chars) or link available, attempt to enrich
            if link and len(summary) < 150:
                scraped = _scrape_cached(link)
                if scraped:
                    new_entry["summary"] = scraped

            if new_entry.get("reports"):
                updated_reports = []
                for rep in new_entry["reports"]:
                    rep_copy = dict(rep)
                    rep_link = rep_copy.get("link", "")
                    rep_summary = rep_copy.get("summary", "")
                    if rep_link and len(rep_summary) < 150:
                        scraped_rep = _scrape_cached(rep_link)
                        if scraped_rep:
                            rep_copy["summary"] = scraped_rep
                    updated_reports.append(rep_copy)
                new_entry["reports"] = updated_reports

                if len(new_entry.get("summary", "")) < 150:
                    combined = [
                        f"[{r.get('source', 'ESPN')}] {r.get('summary', '')}"
                        for r in updated_reports
                        if r.get("summary")
                    ]
                    if combined:
                        new_entry["summary"] = "\n\n".join(combined)

            item = {"slot": item.get("slot", "Section"), "entry": new_entry}
            enriched.append(item)

        return super().sanitize_articles(enriched)

    def _fetch_rss_entries(self, feed_url: str) -> List[object]:
        """Fetch and parse a secondary RSS feed URL."""
        try:
            resp = requests.get(
                feed_url, timeout=self._SCRAPE_TIMEOUT, headers=self._SCRAPE_HEADERS
            )
            text = getattr(resp, "text", "")
            if resp.status_code != 200 or not isinstance(text, str) or not text:
                return []
            feed = feedparser.parse(text)
            return list(getattr(feed, "entries", []))
        except Exception:
            return []

    def _is_junk_article(self, entry: object) -> bool:
        """Return True if title matches junk or betting keywords."""
        title = entry.get("title", "") if hasattr(entry, "get") else ""
        title_lower = title.lower()
        return any(kw in title_lower for kw in self.JUNK_KEYWORDS)

    def _fetch_news_articles(self) -> List[Dict]:
        """Fetch raw articles list from ESPN API."""
        try:
            resp = requests.get(self._NEWS_API_URL, timeout=self._SCRAPE_TIMEOUT)
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

                articles.append({
                    "title": headline,
                    "link": link,
                    "summary": description,
                    "source": "ESPN",
                    "published": pub_date_str,
                    "published_parsed": published_parsed,
                })
            return articles
        except Exception as e:
            logger.warning("Error fetching ESPN NFL news: %s", e)
            return []

    def _scrape_article_text(self, url: str) -> str:
        """Extract article paragraph content from ESPN story URL."""
        try:
            resp = requests.get(url, timeout=self._SCRAPE_TIMEOUT, headers=self._SCRAPE_HEADERS)
            if resp.status_code != 200:
                return ""
            soup = BeautifulSoup(resp.text, "html.parser")
            selectors = [
                "div.article-body",
                "div.Story__Body",
                "section.article-body",
                "article",
            ]
            for sel in selectors:
                container = soup.select_one(sel)
                if container:
                    paragraphs = container.find_all("p")
                    if paragraphs:
                        return " ".join(p.get_text(" ", strip=True) for p in paragraphs)
            return ""
        except Exception:
            return ""
