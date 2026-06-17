"""NHL.com news data provider using team-specific news pages."""
import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Optional
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

from ..base import DataProvider


class NHLNewsRssProvider(DataProvider):
    """
    Data provider for NHL.com news via team-specific news pages.

    Fetches articles from NHL.com in team-priority order, then falls back
    to the general NHL news page to fill any remaining slots.

    Team priorities are fully configurable at construction time - simply
    pass a different ``favorite_teams`` list to change which feeds are
    polled first.

    Articles whose titles contain any entry in ``JUNK_KEYWORDS`` are
    silently skipped. The article body is scraped from the article URL
    when the RSS feed provides an empty summary.
    """

    # Maps team name to its NHL.com news URL.
    # None is the sentinel key for the general NHL news page used as fallback.
    TEAM_FEEDS: Dict[Optional[str], str] = {
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

    # Entries whose title contains any of these phrases (case-insensitive) are
    # dropped before they can occupy a slot or be passed to the LLM.
    JUNK_KEYWORDS: List[str] = [
        "stream games",
        "fantasy",
    ]

    # CSS selectors tried in order when scraping NHL.com article pages.
    _ARTICLE_SELECTORS: List[str] = [
        "div.article-detail__body",
        "div.article-detail__content",
        "section.article-summary",
        "article",
        "main",
    ]

    _SCRAPE_TIMEOUT: int = 10
    _NEWS_PAGE_URL: str = "https://www.nhl.com/news"
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
        **config: object,
    ) -> None:
        super().__init__(**config)
        self.favorite_teams: List[str] = favorite_teams or []
        self.max_articles: int = max_articles
        self._article_cache: Dict[Optional[str], List[Dict]] = {}

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
        Fetch up to ``max_articles`` articles from NHL.com RSS feeds.

        Articles are selected in team priority order. After exhausting
        all team feeds, the general NHL news feed fills any remaining
        slots. Entries matching ``JUNK_KEYWORDS`` are skipped.

        Returns:
            List of dicts with keys ``'slot'`` (str) and ``'entry'`` (dict).
            The list length equals ``max_articles``, but may be shorter if
            the page does not contain enough recent entries.
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

        # 2. Fill remaining slots from the general NHL feed
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

        Any entry whose title matches ``JUNK_KEYWORDS`` is dropped. For
        entries with an empty ``summary``, the article URL is fetched and
        paragraph text is extracted to populate the summary.
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

    def _team_matches_entry(self, team: str, entry: object) -> bool:
        """Return True when ``entry`` looks like it belongs to ``team``."""
        title = entry.get("title", "") if hasattr(entry, "get") else ""
        link = entry.get("link", "") if hasattr(entry, "get") else ""
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
                        published_dt = datetime.fromisoformat(datetime_attr.replace("Z", "+00:00"))
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
            resp = requests.get(url, timeout=self._SCRAPE_TIMEOUT, headers=self._SCRAPE_HEADERS)
            if resp.status_code != 200:
                self._article_cache[url] = []
                return []
            entries = self._parse_recent_articles(resp.text, url)
        except Exception:
            entries = []

        self._article_cache[url] = entries
        return entries

    def _scrape_article_text(self, url: str) -> str:
        """
        Fetch ``url`` and extract article body paragraphs.

        Tries a cascade of CSS selectors specific to NHL.com before falling
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
            if not self._team_matches_entry(team, entry):
                continue
            if entry.get("link", "") not in seen_links and not self._is_junk_article(entry):
                return entry
        return None

    def _fetch_entries(self, team: Optional[str]) -> List[object]:
        """Fetch and return recent article cards for the given team or the general feed."""
        if team is None:
            return self._fetch_page_articles(self._NEWS_PAGE_URL)

        team_url = self.TEAM_FEEDS.get(team)
        entries = self._fetch_page_articles(team_url) if team_url else []
        if entries:
            return entries

        # The NHL team pages are heavily dynamic. Fall back to the general
        # news page and filter by team name / slugs so we still get stories.
        return self._fetch_page_articles(self._NEWS_PAGE_URL)
