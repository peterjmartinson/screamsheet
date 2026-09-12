"""MLB Trade Rumors data provider for fetching news articles."""
import re
from typing import Any, Dict, List, Optional, Set
from datetime import datetime
import feedparser

from ..base import DataProvider


class MLBTradeRumorsProvider(DataProvider):
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
        'Best of', 'MLBTR Chat', 'Front Office'
    ]
    
    def __init__(self, favorite_teams: Optional[List[str]] = None, max_articles: int = 4, **config):
        super().__init__(**config)
        self.favorite_teams = favorite_teams if favorite_teams is not None else []
        self.max_articles = max_articles
    
    def get_game_scores(self, date: datetime) -> list:
        """Not applicable for news provider."""
        return []
    
    def get_standings(self) -> None:
        """Not applicable for news provider."""
        return None
    
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
        from ..news.clustering import TopicClusterer
        from ..news.scoring import SportsNewsScorer

        feed = feedparser.parse(self.RSS_URL)
        clean_entries = [
            entry for entry in feed.entries
            if not self._is_garbage(entry)
        ]
        if not clean_entries:
            return []

        # 1. Fill favorite team slots in priority order
        selected_clusters: List[Any] = []
        seen_links: set = set()

        for team in self.favorite_teams:
            if len(selected_clusters) >= self.max_articles:
                break
            team_entries = [
                e for e in clean_entries
                if (e.get('link', '') or e.get('id', '')) not in seen_links
                and self._entry_matches_team(e, team)
            ]
            if team_entries:
                scorer = SportsNewsScorer(sport="mlb", favorite_teams=[team], junk_keywords=self.EXCLUSION_KEYWORDS)
                clusterer = TopicClusterer(similarity_threshold=0.75, scorer=scorer)
                team_clusters = clusterer.cluster(team_entries, top_n=1)
                if team_clusters:
                    best = team_clusters[0]
                    for a in best.articles:
                        seen_links.add(a.get("link", "") or a.get("id", ""))
                    selected_clusters.append(best)

        # 2. Fill remaining slots with general clean articles
        if len(selected_clusters) < self.max_articles:
            remaining_entries = [
                e for e in clean_entries
                if (e.get('link', '') or e.get('id', '')) not in seen_links
            ]
            if remaining_entries:
                needed = self.max_articles - len(selected_clusters)
                scorer = SportsNewsScorer(sport="mlb", favorite_teams=self.favorite_teams, junk_keywords=self.EXCLUSION_KEYWORDS)
                clusterer = TopicClusterer(similarity_threshold=0.75, scorer=scorer)
                general_clusters = clusterer.cluster(remaining_entries, top_n=needed)
                for gc in general_clusters:
                    selected_clusters.append(gc)
                    for a in gc.articles:
                        seen_links.add(a.get("link", "") or a.get("id", ""))

        output: List[Dict] = []
        for i, cluster in enumerate(selected_clusters):
            first_article = cluster.articles[0] if cluster.articles else {}
            pub_parsed = (
                first_article.get("published_parsed")
                if hasattr(first_article, "get")
                else getattr(first_article, "published_parsed", None)
            )
            slot_entry = {
                "title": cluster.topic,
                "summary": cluster.combined_summary,
                "link": cluster.primary_link,
                "id": cluster.primary_link,
                "source": "MLB Trade Rumors",
                "sources": ["MLB Trade Rumors"],
                "reports": [
                    {
                        "source": "MLB Trade Rumors",
                        "title": a.get("title", "") if hasattr(a, "get") else getattr(a, "title", ""),
                        "summary": a.get("summary", "") if hasattr(a, "get") else getattr(a, "summary", ""),
                        "link": a.get("link", "") if hasattr(a, "get") else getattr(a, "link", ""),
                    }
                    for a in cluster.articles
                ],
                "is_cluster": True,
                "cluster_score": cluster.score,
                "published_parsed": pub_parsed,
            }
            output.append({"slot": f"Section {i + 1}", "entry": slot_entry})

        return output
    
    def _is_garbage(self, entry: Dict) -> bool:
        """Check if an article contains blacklisted promotional keywords."""
        title = entry.get('title', '').lower()
        summary = entry.get('summary', '').lower()
        
        for keyword in self.EXCLUSION_KEYWORDS:
            if keyword.lower() in title or keyword.lower() in summary:
                return True
        return False
