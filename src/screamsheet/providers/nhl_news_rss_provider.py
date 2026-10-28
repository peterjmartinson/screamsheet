"""NHL.com and multi-source NHL news data provider."""
import feedparser
import requests
from bs4 import BeautifulSoup
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

from ..base import NewsDataProvider


class NHLNewsRssProvider(NewsDataProvider):
    """
    Data provider for NHL news via NHL.com pages and secondary RSS feeds.

    Fetches articles from NHL.com (primary source) and secondary outlets,
    scores all candidates with an authority bonus for NHL.com and heavy
    favorite-team tier boosts, and clusters stories across outlets.
    """

    PRIMARY_SOURCE: str = "NHL.com"
    PRIMARY_SOURCE_BONUS: int = 25

    SECONDARY_FEEDS: Dict[str, str] = {
        "ESPN": "https://www.espn.com/espn/rss/nhl/news",
        "CBS Sports": "https://www.cbssports.com/rss/headlines/nhl/",
        "Yahoo Sports": "https://sports.yahoo.com/nhl/rss.xml",
        "ProHockeyRumors": "https://www.prohockeyrumors.com/feed",
        "The Hockey News": "https://thehockeynews.com/.rss/full/",
        "Sportsnet": "https://www.sportsnet.ca/hockey/nhl/feed/",
    }

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
        self._article_cache: Dict[Optional[str], List[Dict]] = {}

    # ------------------------------------------------------------------
    # News-specific interface
    # ------------------------------------------------------------------

    def get_articles(self) -> List[Dict]:
        """Fetch up to ``max_articles`` articles from NHL.com and secondary feeds.

        Articles are scored with favorite team tier weighting and primary source
        bonuses, then clustered into semantic topics so multi-source coverage is unified.

        Returns:
            List of dicts with keys ``'slot'`` (str) and ``'entry'`` (dict).
            The list length equals ``max_articles``, but may be shorter if
            the feeds do not contain enough recent entries.
        """
        all_entries: List[Dict[str, Any]] = []
        seen_links: set = set()

        # 1. Collect candidate entries from favorite team feeds (tagged with team_tag)
        for team in self.favorite_teams:
            for raw_entry in self._fetch_entries(team):
                if not self._team_matches_entry(team, raw_entry):
                    continue
                link = raw_entry.get("link", "") if hasattr(raw_entry, "get") else getattr(raw_entry, "link", "")
                if link and link not in seen_links and not self._is_junk_article(raw_entry):
                    seen_links.add(link)
                    all_entries.append(
                        {
                            "title": raw_entry.get("title", "") if hasattr(raw_entry, "get") else getattr(raw_entry, "title", ""),
                            "link": link,
                            "summary": raw_entry.get("summary", "") if hasattr(raw_entry, "get") else getattr(raw_entry, "summary", ""),
                            "published_parsed": (
                                raw_entry.get("published_parsed")
                                if hasattr(raw_entry, "get")
                                else getattr(raw_entry, "published_parsed", None)
                            ),
                            "source": self.primary_source,
                            "team_tag": team,
                            "is_primary_source": True,
                        }
                    )

        # 2. Collect candidate entries from the general NHL.com feed
        for raw_entry in self._fetch_entries(None):
            link = raw_entry.get("link", "") if hasattr(raw_entry, "get") else getattr(raw_entry, "link", "")
            if link and link not in seen_links and not self._is_junk_article(raw_entry):
                seen_links.add(link)
                matched_team = next(
                    (t for t in self.favorite_teams if self._team_matches_entry(t, raw_entry)),
                    None,
                )
                entry_dict: Dict[str, Any] = {
                    "title": raw_entry.get("title", "") if hasattr(raw_entry, "get") else getattr(raw_entry, "title", ""),
                    "link": link,
                    "summary": raw_entry.get("summary", "") if hasattr(raw_entry, "get") else getattr(raw_entry, "summary", ""),
                    "published_parsed": (
                        raw_entry.get("published_parsed")
                        if hasattr(raw_entry, "get")
                        else getattr(raw_entry, "published_parsed", None)
                    ),
                    "source": self.primary_source,
                    "is_primary_source": True,
                }
                if matched_team:
                    entry_dict["team_tag"] = matched_team
                all_entries.append(entry_dict)

        # 3. In multi-source mode, poll secondary RSS feeds
        if self.mode == "multi":
            for source_name, feed_url in self.secondary_feeds.items():
                for raw_entry in self._fetch_rss_entries(feed_url):
                    link = raw_entry.get("link", "") if hasattr(raw_entry, "get") else getattr(raw_entry, "link", "")
                    if link and link not in seen_links and not self._is_junk_article(raw_entry):
                        seen_links.add(link)
                        matched_team = next(
                            (t for t in self.favorite_teams if self._team_matches_entry(t, raw_entry)),
                            None,
                        )
                        sec_entry: Dict[str, Any] = {
                            "title": raw_entry.get("title", "") if hasattr(raw_entry, "get") else getattr(raw_entry, "title", ""),
                            "link": link,
                            "summary": raw_entry.get("summary", "") if hasattr(raw_entry, "get") else getattr(raw_entry, "summary", ""),
                            "published_parsed": (
                                raw_entry.get("published_parsed")
                                if hasattr(raw_entry, "get")
                                else getattr(raw_entry, "published_parsed", None)
                            ),
                            "source": source_name,
                        }
                        if matched_team:
                            sec_entry["team_tag"] = matched_team
                        all_entries.append(sec_entry)

        return self._score_and_cluster_entries(
            entries=all_entries,
            sport="nhl",
            favorite_teams=self.favorite_teams,
            junk_keywords=self.JUNK_KEYWORDS,
            max_articles=self.max_articles,
            primary_source=self.primary_source,
            primary_source_bonus=self.primary_source_bonus,
            similarity_threshold=0.68,
            default_source=self.primary_source,
        )

    def sanitize_articles(self, articles: List[Dict]) -> List[Dict]:
        """
        Filter junk entries and enrich each article with scraped body text
        before delegating to the base-class sanitization pipeline.

        Any entry whose title matches ``JUNK_KEYWORDS`` is dropped. For
        entries with an empty ``summary``, the article URL is fetched and
        paragraph text is extracted to populate the summary.
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

            link = entry.get("link", "") if hasattr(entry, "get") else ""
            summary = entry.get("summary", "") if hasattr(entry, "get") else ""

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

            if link and not summary:
                scraped = _scrape_cached(link)
                if scraped:
                    new_entry["summary"] = scraped

            # Also enrich member reports if any report summary is empty
            if new_entry.get("reports"):
                updated_reports = []
                for rep in new_entry["reports"]:
                    rep_copy = dict(rep)
                    if rep_copy.get("link") and not rep_copy.get("summary"):
                        scraped_rep = _scrape_cached(rep_copy["link"])
                        if scraped_rep:
                            rep_copy["summary"] = scraped_rep
                    updated_reports.append(rep_copy)
                new_entry["reports"] = updated_reports

                if not new_entry.get("summary"):
                    combined = [
                        f"[{r.get('source', self.primary_source)}] {r.get('summary', '')}"
                        for r in updated_reports
                        if r.get("summary")
                    ]
                    if combined:
                        new_entry["summary"] = "\n\n".join(combined)

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

    def _fetch_rss_entries(self, feed_url: str) -> List[object]:
        """Fetch and parse a secondary RSS feed URL."""
        try:
            resp = requests.get(
                feed_url, timeout=self._SCRAPE_TIMEOUT, headers=self._SCRAPE_HEADERS
            )
            if resp.status_code != 200 or not getattr(resp, "text", ""):
                return []
            feed = feedparser.parse(resp.text)
            return list(getattr(feed, "entries", []))
        except Exception:
            return []

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
