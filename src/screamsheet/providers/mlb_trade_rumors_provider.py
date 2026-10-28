"""MLB Trade Rumors data provider for fetching news articles."""
import re
from typing import Any, Dict, List, Optional, Set
from datetime import datetime
import feedparser

from ..base import NewsDataProvider


class MLBTradeRumorsProvider(NewsDataProvider):
    """
    Data provider for MLB Trade Rumors news via RSS feed.
    
    Provides access to:
    - News articles from MLB Trade Rumors
    - Filtered and prioritized by favorite teams (using team names and aliases)
    """
    
    RSS_URL = 'https://feeds.feedburner.com/MlbTradeRumors'
    EXCLUSION_KEYWORDS = [
        'Top 50', 'Contest', 'Prediction', 'Subscribers', 'Email List',
        'Presents Our', 'Podcast', 'Live Chat', 'Q&A', 'Ask Us Anything',
        'Best of', 'MLBTR Chat', 'Front Office', 'Prospects'
    ]
    
    PRIMARY_SOURCE = "MLB Trade Rumors"
    PRIMARY_SOURCE_BONUS = 0

    def __init__(
        self,
        favorite_teams: Optional[List[str]] = None,
        max_articles: int = 4,
        mode: str = "single",
        primary_source: str = PRIMARY_SOURCE,
        primary_source_bonus: int = PRIMARY_SOURCE_BONUS,
        extra_feeds: Optional[Dict[str, str]] = None,
        **config: Any,
    ):
        super().__init__(**config)
        self.favorite_teams = favorite_teams if favorite_teams is not None else []
        self.max_articles = max_articles
        self.mode = mode
        self.primary_source = primary_source
        self.primary_source_bonus = primary_source_bonus
        self.secondary_feeds: Dict[str, str] = dict(extra_feeds) if extra_feeds else {}
    
    def _get_team_match_patterns(self, team_name: str) -> List[str]:
        """Return a list of matching keywords/aliases for a team name."""
        keywords: Set[str] = {team_name.strip()}

        # Try screamsheet.db resolution
        try:
            from ..db import sport_get_team_aliases, sport_resolve_team

            resolved = sport_resolve_team("mlb", team_name)
            if resolved:
                aliases = sport_get_team_aliases("mlb", resolved["team_id"])
                for a in aliases:
                    keywords.add(a)
                if resolved.get("full_name"):
                    keywords.add(resolved["full_name"])
                if resolved.get("abbrev"):
                    keywords.add(resolved["abbrev"])
        except Exception:
            pass

        # Fallback heuristic: split words (e.g. "Milwaukee Brewers" -> "Brewers", "Milwaukee")
        parts = team_name.strip().split()
        if len(parts) > 1:
            keywords.add(parts[-1])  # Nickname
            keywords.add(" ".join(parts[:-1]))  # City / Region

        return [k.lower() for k in keywords if len(k) > 1]

    def _entry_matches_team(self, entry: Dict[str, Any], team_name: str) -> bool:
        """Check if an RSS entry matches a favorite team name or any of its aliases."""
        title = entry.get('title', '').lower()
        summary = entry.get('summary', '').lower()
        patterns = self._get_team_match_patterns(team_name)

        for pat in patterns:
            # Word-boundary matching for short or hyphenated terms
            regex = r'(?:\b|\A)' + re.escape(pat) + r'(?:\b|\Z)'
            if re.search(regex, title) or re.search(regex, summary):
                return True
        return False

    def get_articles(self) -> List[Dict]:
        """Fetch, score, and cluster articles from MLB Trade Rumors.

        Articles are prioritized by favorite teams and clustered into semantic
        topics to eliminate redundancy.
        """
        all_entries: List[Dict[str, Any]] = []
        seen_links: set = set()

        feed = feedparser.parse(self.RSS_URL)
        for entry in feed.entries:
            if self._is_garbage(entry):
                continue
            link = entry.get("link", "") or entry.get("id", "")
            if not link or link in seen_links:
                continue
            seen_links.add(link)
            matched_team = next(
                (team for team in self.favorite_teams if self._entry_matches_team(entry, team)),
                None,
            )
            entry_dict: Dict[str, Any] = {
                "title": entry.get("title", "") if hasattr(entry, "get") else getattr(entry, "title", ""),
                "link": link,
                "summary": entry.get("summary", "") if hasattr(entry, "get") else getattr(entry, "summary", ""),
                "published_parsed": (
                    entry.get("published_parsed")
                    if hasattr(entry, "get")
                    else getattr(entry, "published_parsed", None)
                ),
                "source": self.primary_source,
                "is_primary_source": True,
            }
            if matched_team:
                entry_dict["team_tag"] = matched_team
            all_entries.append(entry_dict)

        if self.mode == "multi" and self.secondary_feeds:
            for source_name, feed_url in self.secondary_feeds.items():
                try:
                    sec_feed = feedparser.parse(feed_url)
                except Exception:
                    continue
                for entry in getattr(sec_feed, "entries", []):
                    if self._is_garbage(entry):
                        continue
                    link = entry.get("link", "") or entry.get("id", "")
                    if not link or link in seen_links:
                        continue
                    seen_links.add(link)
                    matched_team = next(
                        (team for team in self.favorite_teams if self._entry_matches_team(entry, team)),
                        None,
                    )
                    sec_dict: Dict[str, Any] = {
                        "title": entry.get("title", "") if hasattr(entry, "get") else getattr(entry, "title", ""),
                        "link": link,
                        "summary": entry.get("summary", "") if hasattr(entry, "get") else getattr(entry, "summary", ""),
                        "published_parsed": (
                            entry.get("published_parsed")
                            if hasattr(entry, "get")
                            else getattr(entry, "published_parsed", None)
                        ),
                        "source": source_name,
                    }
                    if matched_team:
                        sec_dict["team_tag"] = matched_team
                    all_entries.append(sec_dict)

        return self._score_and_cluster_entries(
            entries=all_entries,
            sport="mlb",
            favorite_teams=self.favorite_teams,
            junk_keywords=self.EXCLUSION_KEYWORDS,
            max_articles=self.max_articles,
            primary_source=self.primary_source,
            primary_source_bonus=self.primary_source_bonus,
            similarity_threshold=0.75,
            default_source=self.primary_source,
        )
    
    def _is_garbage(self, entry: Dict) -> bool:
        """Check if an article contains blacklisted promotional keywords."""
        title = entry.get('title', '').lower()
        summary = entry.get('summary', '').lower()
        
        for keyword in self.EXCLUSION_KEYWORDS:
            if keyword.lower() in title or keyword.lower() in summary:
                return True
        return False
