"""NFL news data provider using ESPN NFL News API."""
import logging
import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Optional
from datetime import datetime
from urllib.parse import urljoin

from ..base import DataProvider

logger = logging.getLogger(__name__)


class NFLNewsProvider(DataProvider):
    """
    Data provider for NFL news via ESPN API and story scraping.
    """

    # Entries whose title contains any of these phrases (case-insensitive) are skipped.
    JUNK_KEYWORDS: List[str] = [
        "betting",
        "how to bet",
        "prop bet",
        "odds, tips",
        "stream games",
        "fantasy football",
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
        **config: object,
    ) -> None:
        super().__init__(**config)
        self.favorite_teams: List[str] = favorite_teams or []
        self.max_articles: int = max_articles

    def get_game_scores(self, date: datetime) -> list:
        return []

    def get_standings(self) -> None:
        return None

    def get_articles(self) -> List[Dict]:
        """
        Fetch up to ``max_articles`` non-junk articles from ESPN NFL news.
        """
        raw_articles = self._fetch_news_articles()
        selected: List[Dict] = []
        seen_links: set = set()

        # 1. Match favorite teams first if specified
        if self.favorite_teams:
            for team in self.favorite_teams:
                team_clean = str(team).lower()
                for art in raw_articles:
                    if len(selected) >= self.max_articles:
                        break
                    link = art.get("link", "")
                    if link in seen_links or self._is_junk_article(art):
                        continue
                    headline = art.get("title", "").lower()
                    desc = art.get("summary", "").lower()
                    if team_clean in headline or team_clean in desc:
                        seen_links.add(link)
                        selected.append({
                            "slot": f"Section {len(selected) + 1}",
                            "entry": art,
                        })

        # 2. Fill remaining slots from general league news
        for art in raw_articles:
            if len(selected) >= self.max_articles:
                break
            link = art.get("link", "")
            if link not in seen_links and not self._is_junk_article(art):
                seen_links.add(link)
                selected.append({
                    "slot": f"Section {len(selected) + 1}",
                    "entry": art,
                })

        return selected

    def sanitize_articles(self, articles: List[Dict]) -> List[Dict]:
        """
        Enrich articles with scraped body text if available.
        """
        enriched: List[Dict] = []
        for item in articles:
            entry = item.get("entry") if isinstance(item, dict) else None
            if entry is None:
                continue
            if self._is_junk_article(entry):
                continue

            link = entry.get("link", "")
            summary = entry.get("summary", "")

            # If summary is brief (under 150 chars) or link available, attempt to enrich
            if link and len(summary) < 150:
                scraped = self._scrape_article_text(link)
                if scraped:
                    new_entry = dict(entry)
                    new_entry["summary"] = scraped
                    item = {"slot": item.get("slot", "Section"), "entry": new_entry}

            enriched.append(item)

        return super().sanitize_articles(enriched)

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
