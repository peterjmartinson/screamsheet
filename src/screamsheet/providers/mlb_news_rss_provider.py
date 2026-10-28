"""MLB.com news data provider using team-specific RSS feeds."""
import feedparser  # type: ignore[import-untyped]
import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Optional
from datetime import datetime

from ..base import NewsDataProvider


class MLBNewsRssProvider(NewsDataProvider):
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
        "prospects",
    ]

    PRIMARY_SOURCE: str = "MLB.com"
    PRIMARY_SOURCE_BONUS: int = 25

    SECONDARY_FEEDS: Dict[str, str] = {
        "ESPN": "https://www.espn.com/espn/rss/mlb/news",
        "CBS Sports": "https://www.cbssports.com/rss/headlines/mlb/",
        "Yahoo Sports": "https://sports.yahoo.com/mlb/rss.xml",
        "MLB Trade Rumors": "https://feeds.feedburner.com/MlbTradeRumors",
        "FanGraphs": "https://blogs.fangraphs.com/feed/",
        "Fox Sports": "https://api.foxsports.com/v2/content/optimized-rss?partnerKey=MB0Wehpmuj2lUhuRhQaafhBjAJqaPU244mlTDK1i&size=30&tags=fs/mlb",
    }

    # CSS selectors tried in order when scraping article pages.
    _ARTICLE_SELECTORS: List[str] = [
        "div.article-template__body-text",
        "div.article-template__content",
        "div.bam-content",
        "div.article-body",
        "div.Story__Body",
        "div.caas-body",
        "div.Article-content",
        "div.entry-content",
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
        mode: str = "multi",
        primary_source: str = PRIMARY_SOURCE,
        primary_source_bonus: int = PRIMARY_SOURCE_BONUS,
        extra_feeds: Optional[Dict[str, str]] = None,
        **config: object,
    ) -> None:
        super().__init__(**config)
        self.favorite_teams: List[str] = favorite_teams or []
        self.max_articles: int = max_articles
        self.mode: str = (mode or "multi").strip().lower()
        self.primary_source: str = primary_source or self.PRIMARY_SOURCE
        self.primary_source_bonus: int = primary_source_bonus
        self.extra_feeds: Dict[str, str] = dict(extra_feeds) if extra_feeds else {}

    # ------------------------------------------------------------------
    # News-specific interface
    # ------------------------------------------------------------------

    def _raw_to_entry_dict(
        self,
        raw_entry: object,
        source_name: str,
        team_tag: Optional[str] = None,
        is_primary: bool = False,
    ) -> Optional[Dict]:
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
        entry_dict: Dict = {
            "title": title,
            "link": link,
            "summary": summary or "",
            "published_parsed": pub_parsed,
            "source": source_name,
            "is_primary_source": is_primary,
        }
        if team_tag:
            entry_dict["team_tag"] = team_tag
        return entry_dict

    def get_articles(self) -> List[Dict]:
        """Fetch up to ``max_articles`` articles across MLB.com and secondary RSS feeds.

        Articles are pooled across sources (unless ``mode == "single"``), scored
        with a heavy favorite-team boost and primary-source authority bonus, and
        clustered into unified multi-source topics.

        Returns:
            List of dicts with keys ``'slot'`` (str) and ``'entry'`` (dict).
        """
        all_entries: List[Dict] = []

        # 1. Fetch primary source: favorite team MLB.com feeds in priority order
        for team in self.favorite_teams:
            for raw_entry in self._fetch_entries(team):
                ed = self._raw_to_entry_dict(
                    raw_entry,
                    source_name=self.primary_source,
                    team_tag=team,
                    is_primary=True,
                )
                if ed:
                    all_entries.append(ed)

        # 2. Fetch primary source: general MLB.com feed
        for raw_entry in self._fetch_entries(None):
            ed = self._raw_to_entry_dict(
                raw_entry,
                source_name=self.primary_source,
                is_primary=True,
            )
            if ed:
                all_entries.append(ed)

        # 3. Fetch secondary multi-source feeds (when mode == "multi")
        if self.mode == "multi":
            feeds = dict(self.SECONDARY_FEEDS)
            feeds.update(self.extra_feeds)
            for source_name, feed_url in feeds.items():
                try:
                    feed = feedparser.parse(feed_url)
                    for raw_entry in getattr(feed, "entries", []):
                        ed = self._raw_to_entry_dict(
                            raw_entry,
                            source_name=source_name,
                            is_primary=(source_name.lower() == self.primary_source.lower()),
                        )
                        if ed:
                            all_entries.append(ed)
                except Exception:
                    continue

        return self._score_and_cluster_entries(
            entries=all_entries,
            sport="mlb",
            favorite_teams=self.favorite_teams,
            junk_keywords=self.JUNK_KEYWORDS,
            primary_source=self.primary_source,
            primary_source_bonus=self.primary_source_bonus,
            max_articles=self.max_articles,
            similarity_threshold=0.68,
        )

    def sanitize_articles(self, articles: List[Dict]) -> List[Dict]:
        """Filter junk entries and enrich each article with scraped body text.

        Any entry whose title matches ``JUNK_KEYWORDS`` is dropped.  For
        entries with an empty ``summary``, the article URL is fetched and
        paragraph text is extracted to populate the summary — giving the
        LLM real content to work with instead of an empty string.
        """
        enriched: List[Dict] = []
        scraped_cache: Dict[str, str] = {}

        def _get_scraped(url: str) -> str:
            if url not in scraped_cache:
                scraped_cache[url] = self._scrape_article_text(url)
            return scraped_cache[url]

        for item in articles:
            entry = item.get("entry") if isinstance(item, dict) else None
            if entry is None:
                continue
            if self._is_junk_article(entry):
                continue

            link = entry.get("link", "") if hasattr(entry, "get") else ""
            summary = entry.get("summary", "") if hasattr(entry, "get") else ""

            if link and not summary:
                scraped = _get_scraped(link)
                if scraped:
                    new_entry: Dict = {
                        k: (entry.get(k) if hasattr(entry, "get") else getattr(entry, k, None))
                        for k in ("title", "link", "id", "published_parsed", "summary", "source", "sources", "reports", "is_cluster", "cluster_score")
                    }
                    new_entry["summary"] = scraped
                    item = {"slot": item.get("slot", "Section"), "entry": new_entry}

            # Also enrich member reports if any report summary is empty
            cur_entry = item.get("entry")
            if isinstance(cur_entry, dict) and cur_entry.get("reports"):
                reports_updated = False
                for rep in cur_entry["reports"]:
                    if rep.get("link") and not rep.get("summary"):
                        scraped_rep = _get_scraped(rep["link"])
                        if scraped_rep:
                            rep["summary"] = scraped_rep
                            reports_updated = True
                if reports_updated and not cur_entry.get("summary"):
                    rep_summaries = [
                        r["summary"].strip()
                        for r in cur_entry["reports"]
                        if r.get("summary") and r["summary"].strip()
                    ]
                    if rep_summaries:
                        cur_entry["summary"] = "\n\n".join(dict.fromkeys(rep_summaries))

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
