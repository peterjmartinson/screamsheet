"""NFL news data provider using ESPN NFL News API and secondary RSS feeds."""
import re
from typing import Any, Dict, List, Optional, Sequence, Union

from .news_sources import (
    ESPN_NFL_NEWS_API_URL,
    NFL_JUNK_KEYWORDS,
    ResolvedNewsSource,
    UnifiedNewsProvider,
)

INJURY_KEYWORD_PATTERN = re.compile(
    r"\b(injury|injuries|injured|ir|injured reserve|concussion|surgery|torn|sprain|sprained|"
    r"hamstring|knee|ankle|achilles|mri|fracture|fractured|carted|doubtful|questionable|"
    r"inactive|inactives|rehab)\b",
    re.IGNORECASE,
)


class NFLNewsProvider(UnifiedNewsProvider):
    """
    Data provider for NFL news via ESPN API, NFL.com, and secondary RSS feeds.
    """

    DEFAULT_SHEET: str = "nfl_news"
    DEFAULT_CATEGORY: str = "nfl"

    JUNK_KEYWORDS: List[str] = NFL_JUNK_KEYWORDS
    _NEWS_API_URL: str = ESPN_NFL_NEWS_API_URL

    def __init__(
        self,
        favorite_teams: Optional[List[str]] = None,
        max_articles: int = 4,
        sources: Optional[Sequence[Union[str, Dict[str, Any], ResolvedNewsSource]]] = None,
        injury_focus: bool = False,
        **config: Any,
    ) -> None:
        super().__init__(
            favorite_teams=favorite_teams,
            max_articles=max_articles,
            sources=sources,
            sport="nfl",
            category="nfl",
            default_sheet="nfl_news",
            junk_keywords=self.JUNK_KEYWORDS,
            similarity_threshold=0.68,
            use_requests_for_rss=True,
            min_summary_chars_before_scrape=150,
            **config,
        )
        self.injury_focus = injury_focus

    @staticmethod
    def is_injury_article(entry: Dict[str, Any]) -> bool:
        """Return True if the article title or summary indicates an injury or roster availability update."""
        text = f"{entry.get('title', '')} {entry.get('summary', '')}"
        return bool(INJURY_KEYWORD_PATTERN.search(text))

    def get_articles(self) -> List[Dict]:
        """Fetch, score, and cluster articles. If injury_focus is True, enforces injury stories."""
        if not self.injury_focus:
            return super().get_articles()

        active_sources = self._get_active_sources()
        source_bonuses = self._get_source_bonuses(active_sources)
        all_entries: List[Dict[str, Any]] = []
        seen_links: set = set()

        # Collect raw entries across all active sources
        for src in active_sources:
            if src.kind == "espn_api":
                for art in self._fetch_news_articles(api_url=src.url, source_name=src.name):
                    link = art.get("link", "")
                    if not link or link in seen_links or self._is_junk_article(art):
                        continue
                    seen_links.add(link)
                    entry_copy = dict(art)
                    matched_team = self._match_favorite_team(entry_copy)
                    if matched_team:
                        entry_copy["team_tag"] = matched_team
                    entry_copy["source_bonus"] = src.bonus
                    all_entries.append(entry_copy)
            else:  # kind == "rss"
                for raw_entry in self._fetch_rss_entries(src.url):
                    if self._is_junk_article(raw_entry):
                        continue
                    link = (
                        (raw_entry.get("link", "") or raw_entry.get("id", ""))
                        if hasattr(raw_entry, "get")
                        else getattr(raw_entry, "link", "")
                    )
                    if not link or link in seen_links:
                        continue
                    seen_links.add(link)
                    matched_team = self._match_any_favorite_team(raw_entry)
                    title = (
                        raw_entry.get("title", "")
                        if hasattr(raw_entry, "get")
                        else getattr(raw_entry, "title", "")
                    )
                    summary = (
                        (raw_entry.get("summary", "") or raw_entry.get("description", ""))
                        if hasattr(raw_entry, "get")
                        else getattr(raw_entry, "summary", "")
                    )
                    pub_parsed = (
                        (raw_entry.get("published_parsed") or raw_entry.get("updated_parsed"))
                        if hasattr(raw_entry, "get")
                        else getattr(raw_entry, "published_parsed", None)
                    )
                    rss_dict: Dict[str, Any] = {
                        "title": title,
                        "link": link,
                        "summary": summary or "",
                        "published_parsed": pub_parsed,
                        "source": src.name,
                        "source_bonus": src.bonus,
                    }
                    if matched_team:
                        rss_dict["team_tag"] = matched_team
                    all_entries.append(rss_dict)

        injury_entries = [e for e in all_entries if self.is_injury_article(e)]

        # If we have enough injury entries to fill the requested slots, cluster exclusively from them
        if len(injury_entries) >= self.max_articles:
            target_entries = injury_entries
        else:
            # Otherwise boost injury entries so they rank first, and backfill with general news
            for e in injury_entries:
                e["source_bonus"] = e.get("source_bonus", 0) + 100
            target_entries = injury_entries + [e for e in all_entries if e not in injury_entries]

        default_source = active_sources[0].name if active_sources else ""
        return self._score_and_cluster_entries(
            entries=target_entries,
            sport=self.sport,
            favorite_teams=[str(t) for t in self.favorite_teams],
            junk_keywords=self.JUNK_KEYWORDS,
            max_articles=self.max_articles,
            similarity_threshold=self.similarity_threshold,
            default_source=default_source,
            source_bonuses=source_bonuses,
        )

