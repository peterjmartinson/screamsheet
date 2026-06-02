"""French-language MLB news scraper provider (RDS.ca and TVA Sports)."""
import random
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..base import DataProvider


class FrenchMLBScraperProvider(DataProvider):
    """
    Data provider for French-language MLB news from RDS.ca and TVA Sports.

    Scrapes the MLB hub pages of two French-Canadian sports broadcasters,
    filters by favourite teams, and returns exactly two articles for use
    as LLM processing targets.

    Team matching follows the same priority-then-fallback pattern as
    :class:`~screamsheet.providers.mlb_news_rss_provider.MLBNewsRssProvider`:
    team articles are chosen in list order; remaining slots are filled
    randomly from the leftover pool.  An empty ``favorite_teams`` list
    causes two random articles to be returned.
    """

    SOURCES: List[Dict[str, str]] = [
        {"name": "RDS", "url": "https://www.rds.ca/baseball/mlb"},
        {"name": "TVA Sports", "url": "https://www.tvasports.ca/baseball/mlb"},
    ]

    # Cascade of selectors tried in order to locate article containers.
    _ARTICLE_SELECTORS: List[str] = [
        "article",
        ".item",
        ".news-item",
        "li.article-item",
    ]

    # Cascade to extract the headline from a container.
    _TITLE_SELECTORS: List[str] = ["h2 a", "h3 a", "h2", "h3", ".title", "a"]

    # Cascade to extract the body/excerpt from a container.
    _BODY_SELECTORS: List[str] = [
        ".summary",
        ".excerpt",
        ".teaser",
        ".text",
        "p",
    ]

    _SCRAPE_TIMEOUT: int = 10
    _SCRAPE_HEADERS: Dict[str, str] = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; screamsheet/1.0; "
            "+https://github.com/peterjmartinson/screamsheet)"
        )
    }

    def __init__(
        self,
        favorite_teams: Optional[List[str]] = None,
        **config: object,
    ) -> None:
        super().__init__(**config)
        self.favorite_teams: List[str] = (
            favorite_teams if favorite_teams is not None else []
        )

    # ------------------------------------------------------------------
    # DataProvider stubs (not applicable for a news scraper)
    # ------------------------------------------------------------------

    def get_game_scores(self, date: datetime) -> list:
        return []

    def get_standings(self) -> None:
        return None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get_articles(self) -> List[Dict[str, str]]:
        """
        Fetch up to two French-language MLB articles.

        Scrapes both sources, combines the article pools, then applies
        team-priority routing.  Returns fewer than two only when not
        enough articles are available across both feeds.
        """
        all_articles: List[Dict[str, str]] = []
        for source in self.SOURCES:
            all_articles.extend(self._scrape_source(source))
        return self._select_two(all_articles)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _select_two(self, articles: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Apply priority routing and return at most two articles."""
        selected: List[Dict[str, str]] = []
        used_indices: set = set()

        for team in self.favorite_teams:
            if len(selected) >= 2:
                break
            for i, article in enumerate(articles):
                if i in used_indices:
                    continue
                if team.lower() in article["title"].lower():
                    selected.append(article)
                    used_indices.add(i)
                    break

        # Fill remaining slots from unmatched articles in random order.
        unmatched = [a for i, a in enumerate(articles) if i not in used_indices]
        random.shuffle(unmatched)
        while len(selected) < 2 and unmatched:
            selected.append(unmatched.pop(0))

        return selected

    def _scrape_source(self, source: Dict[str, str]) -> List[Dict[str, str]]:
        """Fetch and parse one source URL; returns an empty list on any failure."""
        try:
            resp = requests.get(
                source["url"],
                timeout=self._SCRAPE_TIMEOUT,
                headers=self._SCRAPE_HEADERS,
            )
            if resp.status_code != 200:
                return []
            return self._parse_articles(resp.text, source["name"])
        except Exception:
            return []

    def _parse_articles(self, html: str, source_name: str) -> List[Dict[str, str]]:
        """Extract article dicts from raw HTML using the selector cascade."""
        soup = BeautifulSoup(html, "html.parser")
        containers: List[Any] = []
        for selector in self._ARTICLE_SELECTORS:
            containers = soup.select(selector)
            if containers:
                break

        articles: List[Dict[str, str]] = []
        for container in containers:
            title = self._extract_text(container, self._TITLE_SELECTORS)
            body = self._extract_text(container, self._BODY_SELECTORS)
            link_tag = container.select_one("a[href]")
            url: str = link_tag["href"] if link_tag else ""
            if title:
                articles.append(
                    {"title": title, "body": body, "source": source_name, "url": url}
                )
        return articles

    def _extract_text(self, container: Any, selectors: List[str]) -> str:
        """Return the first non-empty text found via the selector cascade."""
        for selector in selectors:
            el = container.select_one(selector)
            if el and el.get_text(strip=True):
                return el.get_text(" ", strip=True)
        return ""
